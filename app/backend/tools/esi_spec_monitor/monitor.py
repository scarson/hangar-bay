# ABOUTME: Projects EVE's ESI meta OpenAPI document down to the endpoints and fields Hangar Bay
# ABOUTME: consumes, diffs that projection against the committed snapshot, and reports what moved.
"""ESI spec drift monitor.

Run `--check` (the default) to compare the live spec against `snapshot.json`, or
`--update` to rewrite the snapshot after reviewing what changed. Updating is meant to
be a deliberate act inside a PR — the same shape as bumping a lockfile — so nothing
here ever rewrites the snapshot on its own.

**Why a projection and not a whole-spec diff.** The full document is 182 paths and
changes constantly in areas Hangar Bay never calls; a diff of all of it would be noise,
and an ignored monitor is worse than none. `manifest.py` names what we depend on, and
only that is compared.

**Why no live data calls.** The only request made is for the static
`https://esi.evetech.net/meta/openapi.json` (rate-limit group `meta`, 150/15m), plus
`/meta/compatibility-dates`. ESI's shared error budget — 100 errors in 60 s buys a
blanket 420 across every endpoint — must never be spent by a monitor.

**Compatibility dates.** ESI replaced route versioning with the `X-Compatibility-Date`
header. A request that omits it is served the *oldest* published date, and the meta spec
answers per date (`Vary: X-Compatibility-Date`, and `info.version` echoes the date
served). So the snapshot holds two views: `pinned`, the shape our client actually
receives today, and `newest_compatibility_date`, the shape we would receive if we
adopted the newest published date. The list of published dates is deliberately NOT
snapshotted — CCP publishes one every few weeks and almost none of them touch our
routes, so snapshotting the list would fire the monitor on schedule rather than on news.

Standard library only, on purpose: the scheduled workflow then needs no dependency
install, and the monitor cannot be broken by an unrelated change to the backend's deps.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from esi_spec_monitor.manifest import MANIFEST, Endpoint

SPEC_URL = "https://esi.evetech.net/meta/openapi.json"
COMPATIBILITY_DATES_URL = "https://esi.evetech.net/meta/compatibility-dates"
SNAPSHOT_PATH = Path(__file__).resolve().parent / "snapshot.json"

# ESI's best practices ask for an agent that identifies the application and a way to
# reach a human; CCP has publicly named generic agents as an offence.
USER_AGENT = (
    "hangar-bay-esi-spec-monitor/1.0 "
    "(+https://github.com/scarson/hangar-bay; samuel.carson@gmail.com)"
)

PINNED_VIEW = "pinned"
NEWEST_VIEW = "newest_compatibility_date"

# The compatibility date Hangar Bay's ESIClient sends on every request. It is duplicated
# here rather than imported because this tool is deliberately standard-library only, so
# that an unrelated change to the backend's dependency tree cannot break the monitor.
# The duplication is guarded: tests/core/test_esi_compatibility_date.py fails if this
# constant and Settings.ESI_COMPATIBILITY_DATE ever disagree. Keep them in lockstep —
# a monitor watching a date the application does not request reports a safety it cannot
# actually see, which is worse than having no monitor at all.
PINNED_COMPATIBILITY_DATE = "2026-07-21"

BREAKING = "breaking"
INFORMATIONAL = "informational"

# How deep the response-field projection descends. ESI nests at most a couple of
# levels in the shapes we consume (`/universe/ids` returns category -> [{id, name}]);
# the cap stops a future recursive schema from exploding the snapshot.
MAX_FIELD_DEPTH = 4


@dataclass(frozen=True)
class Finding:
    """One reported difference. `consumer` is what makes it actionable."""

    kind: str
    severity: str
    view: str
    endpoint: str
    subject: str
    detail: str
    consumer: str = ""
    call_path: str = ""


# --- spec projection --------------------------------------------------------


def _resolve(spec: dict, node: dict) -> dict:
    """Follow a local `$ref`. An unresolvable ref raises rather than yielding {}.

    Projecting a broken ref as "this endpoint has no fields" would be
    indistinguishable from CCP deleting every field on the route.
    """
    seen = 0
    while "$ref" in node:
        seen += 1
        if seen > 10:
            raise ValueError(f"$ref cycle at {node['$ref']}")
        ref = node["$ref"]
        if not ref.startswith("#/"):
            raise KeyError(f"unsupported non-local $ref: {ref}")
        target: Any = spec
        for part in ref[2:].split("/"):
            target = target[part]  # KeyError on a dangling ref, deliberately
        node = target
    return node


def _describe(node: dict) -> dict:
    """The comparable scalar description of one schema node."""
    described: dict[str, Any] = {"type": node.get("type")}
    if "format" in node:
        described["format"] = node["format"]
    if "enum" in node:
        described["enum"] = sorted(node["enum"])
    return described


def _describe_array(spec: dict, node: dict) -> dict:
    """An array's description, including its element type when elements are scalars.

    Without this an array of enum strings (a station's `services`) and an array of
    integers project identically as `{"type": "array"}`, so a change to what the
    list contains would pass unnoticed. Arrays of objects need no element summary:
    their properties are projected individually as `name[].property`.
    """
    described = _describe(node)
    items = _resolve(spec, node.get("items") or {})
    if items and not items.get("properties"):
        described["items"] = _describe(items)
    return described


def _flatten_fields(spec: dict, node: dict, prefix: str, out: dict, depth: int) -> None:
    """Walk a response schema into flat `name` / `parent.child` / `[].name` keys."""
    if depth > MAX_FIELD_DEPTH:
        return
    node = _resolve(spec, node)
    if node.get("type") == "array":
        items = node.get("items")
        if items is not None:
            _flatten_fields(spec, items, f"{prefix}[].", out, depth + 1)
        return
    required = set(node.get("required", []))
    for name, raw in sorted(node.get("properties", {}).items()):
        child = _resolve(spec, raw)
        key = f"{prefix}{name}"
        summary = _describe_array(spec, child) if child.get("type") == "array" else _describe(child)
        out[key] = {**summary, "required": name in required}
        if child.get("type") in ("object", "array"):
            separator = "" if child.get("type") == "array" else "."
            _flatten_fields(spec, child, f"{key}{separator}", out, depth + 1)


def _response_fields(spec: dict, operation: dict) -> dict:
    """Flatten the 200 response's JSON body. A 200 without a body projects as {}."""
    schema = (
        operation.get("responses", {})
        .get("200", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema")
    )
    if not schema:
        return {}
    out: dict[str, dict] = {}
    _flatten_fields(spec, schema, "", out, 0)
    return out


def _parameters(spec: dict, operation: dict) -> dict:
    """Project parameters keyed `in:name`, resolving the shared `$ref` ones.

    The shared parameters are not boilerplate to us: `If-None-Match` is what the
    ETag-conditional fetch in `ESIClient.get_esi_data_with_etag_caching` rides on.
    """
    out: dict[str, dict] = {}
    for raw in operation.get("parameters", []):
        param = _resolve(spec, raw)
        key = f"{param.get('in')}:{param.get('name')}"
        described = _describe(_resolve(spec, param.get("schema", {})))
        if param.get("name") == "X-Compatibility-Date":
            # Its enum echoes whichever date this copy of the spec was served for, so
            # keeping it would make the snapshot restate the served date on every
            # operation — the monitor would then fire each time CCP publishes a new
            # date, which is a calendar event, not drift in a route we consume. The
            # served date is snapshotted once, at the top level.
            described.pop("enum", None)
        out[key] = {**described, "required": bool(param.get("required", False))}
    # One of three redundant layers holding "a cosmetic reshuffle by CCP must not
    # produce a snapshot diff", alongside the property sort in `_flatten_fields` and
    # `sort_keys` in `serialize`. Any one suffices, so
    # test_projection_is_stable_across_key_ordering goes red only if all three go.
    return dict(sorted(out.items()))


def _security(spec: dict, operation: dict) -> list:
    """Normalize the auth requirement. `[]` means the route is public.

    An operation without its own `security` inherits the document's, which for ESI
    is absent entirely — so absent means public here, but the fallback is explicit
    rather than assumed, because a document-level `security` appearing is exactly
    the silent break this monitor exists to catch.
    """
    requirements = operation.get("security", spec.get("security", []))
    return sorted(
        [scheme, sorted(scopes)]
        for requirement in requirements
        for scheme, scopes in requirement.items()
    )


def _request_body(spec: dict, operation: dict) -> dict | None:
    body = operation.get("requestBody")
    if body is None:
        return None
    schema = body.get("content", {}).get("application/json", {}).get("schema", {})
    return {
        "required": bool(body.get("required", False)),
        "schema": _resolve(spec, schema),
    }


def _normalize(names: Iterable[str]) -> set[str]:
    """Field keys with any leading array marker stripped, for manifest lookups.

    A manifest naming `contract_id` should match the projected `[].contract_id`
    of a list-returning route; making authors write `[].contract_id` would trade
    a readable dependency document for a mechanical detail.
    """
    normalized = set()
    for name in names:
        normalized.add(name)
        if name.startswith("[]."):
            normalized.add(name[3:])
    return normalized


def _project_endpoint(spec: dict, endpoint: Endpoint) -> dict:
    operation = spec.get("paths", {}).get(endpoint.spec_path, {}).get(endpoint.method)
    if operation is None:
        return {"present": False}

    fields = _response_fields(spec, operation)
    available = _normalize(fields)
    known_absent = {a.name: a for a in endpoint.known_absent_fields}

    return {
        "present": True,
        "call_path": endpoint.call_path,
        "caller": endpoint.caller,
        "operation_id": operation.get("operationId"),
        "security": _security(spec, operation),
        "server_cache_mode": operation.get("x-server-cache-mode"),
        "operation_compatibility_date": operation.get("x-compatibility-date"),
        "parameters": _parameters(spec, operation),
        "request_body": _request_body(spec, operation),
        "response_statuses": sorted(operation.get("responses", {})),
        "response_fields": fields,
        "consumers": dict(sorted(endpoint.consumed_fields.items())),
        "known_absent_fields": {
            name: {"consumer": a.consumer, "consequence": a.consequence}
            for name, a in sorted(known_absent.items())
        },
        "consumed_fields_absent_from_spec": sorted(
            name for name in endpoint.consumed_fields if name not in available
        ),
        "known_absent_fields_now_present": sorted(
            name for name in known_absent if name in available
        ),
    }


def project(spec: dict, manifest: Sequence[Endpoint] = MANIFEST) -> dict:
    """Reduce the whole spec to just what Hangar Bay depends on."""
    return {endpoint.key: _project_endpoint(spec, endpoint) for endpoint in manifest}


def build_snapshot(
    pinned_spec: dict,
    newest_spec: dict,
    manifest: Sequence[Endpoint] = MANIFEST,
) -> dict:
    """Assemble the committed document from the two compatibility-date views."""
    return {
        "readme": (
            "Committed projection of https://esi.evetech.net/meta/openapi.json, "
            "narrowed to the endpoints and fields Hangar Bay consumes. Regenerate "
            "with `pdm run esi-spec-monitor --update` and review the diff; never "
            "update it to silence a failure you have not understood."
        ),
        "spec_url": SPEC_URL,
        "pinned_compatibility_date": pinned_spec.get("info", {}).get("version"),
        "views": {
            PINNED_VIEW: project(pinned_spec, manifest),
            NEWEST_VIEW: project(newest_spec, manifest),
        },
    }


# --- comparison -------------------------------------------------------------


@dataclass
class _Context:
    """Everything a per-endpoint diff needs to describe what it found."""

    view: str
    endpoint: str
    old: dict
    new: dict
    findings: list = field(default_factory=list)

    @property
    def call_path(self) -> str:
        return self.old.get("call_path") or self.new.get("call_path") or ""

    def consumer_for(self, subject: str) -> str:
        consumers = self.new.get("consumers") or self.old.get("consumers") or {}
        name = subject[3:] if subject.startswith("[].") else subject
        return consumers.get(subject) or consumers.get(name) or ""

    def add(self, kind: str, severity: str, subject: str, detail: str, consumer: str = "") -> None:
        self.findings.append(
            Finding(
                kind=kind,
                # Nothing at the newest published date is breaking yet: it is not the
                # shape our client receives. It becomes breaking when ESI raises the
                # floor a header-less request is served, which the pinned view catches.
                severity=INFORMATIONAL if self.view == NEWEST_VIEW else severity,
                view=self.view,
                endpoint=self.endpoint,
                subject=subject,
                detail=detail,
                consumer=consumer or self.consumer_for(subject),
                call_path=self.call_path,
            )
        )


def _severity(ctx: _Context, subject: str, when_consumed: str) -> str:
    """A change to a field we read is breaking; the same change elsewhere is news."""
    return when_consumed if ctx.consumer_for(subject) else INFORMATIONAL


def _diff_scalars(ctx: _Context) -> None:
    """Operation-level attributes that are single values."""
    checks = (
        ("security", "AUTH_CHANGED", BREAKING),
        ("operation_id", "OPERATION_ID_CHANGED", INFORMATIONAL),
        # ESI is converting routes from clock expiry to event-driven invalidation
        # (ESI-2). A conversion does not break the client — it reads Cache-Control
        # first — but it removes the signal any Expires-derived scheduling rests on,
        # so it needs a decision rather than a note.
        ("server_cache_mode", "CACHE_MODE_CHANGED", BREAKING),
        (
            "operation_compatibility_date",
            "OPERATION_COMPATIBILITY_DATE_CHANGED",
            INFORMATIONAL,
        ),
        ("request_body", "REQUEST_BODY_CHANGED", BREAKING),
    )
    for key, kind, severity in checks:
        before, after = ctx.old.get(key), ctx.new.get(key)
        if before != after:
            ctx.add(kind, severity, key, f"{json.dumps(before)} -> {json.dumps(after)}")


def _diff_keyed(
    ctx: _Context,
    key: str,
    kinds: tuple[str, str],
    on_common: Callable[[_Context, str, dict, dict], None],
    added_severity: str = INFORMATIONAL,
    removed_severity: str | None = BREAKING,
) -> None:
    """Diff a name -> descriptor mapping (response fields, or parameters).

    `removed_severity=None` means "breaking only if we consume this name" — right
    for response fields, where ESI dropping something we never read is news rather
    than a break. Parameters pass a fixed BREAKING instead: they are not in the
    consumer map at all, and losing one (If-None-Match, say) breaks the client
    regardless of which response fields it happens to read.
    """
    before, after = ctx.old.get(key, {}), ctx.new.get(key, {})
    added_kind, removed_kind = kinds
    for name in sorted(set(after) - set(before)):
        ctx.add(added_kind, added_severity, name, f"added as {json.dumps(after[name])}")
    for name in sorted(set(before) - set(after)):
        severity = removed_severity or _severity(ctx, name, BREAKING)
        ctx.add(removed_kind, severity, name, f"was {json.dumps(before[name])}")
    for name in sorted(set(before) & set(after)):
        on_common(ctx, name, before[name], after[name])


def _items_note(descriptor: dict) -> str:
    items = descriptor.get("items")
    return f" of {items.get('type')}" if items else ""


def _shape_of(descriptor: dict) -> tuple:
    """Everything about a field except whether it is required and its enum members."""
    return (
        descriptor.get("type"),
        descriptor.get("format"),
        json.dumps(descriptor.get("items"), sort_keys=True),
    )


def _diff_field_shape(ctx: _Context, name: str, before: dict, after: dict) -> None:
    if _shape_of(before) != _shape_of(after):
        ctx.add(
            "FIELD_TYPE_CHANGED",
            _severity(ctx, name, BREAKING),
            name,
            f"{before.get('type')}/{before.get('format')}"
            f"{_items_note(before)} -> {after.get('type')}/{after.get('format')}"
            f"{_items_note(after)}",
        )
    if before.get("enum") != after.get("enum"):
        # We branch on enum values (`type` gates item enrichment to
        # item_exchange/auction), so a new member falls through silently.
        ctx.add(
            "FIELD_ENUM_CHANGED",
            _severity(ctx, name, BREAKING),
            name,
            f"{json.dumps(before.get('enum'))} -> {json.dumps(after.get('enum'))}",
        )
    if before.get("required") != after.get("required"):
        became_required = bool(after.get("required"))
        ctx.add(
            "FIELD_BECAME_REQUIRED" if became_required else "FIELD_BECAME_OPTIONAL",
            INFORMATIONAL if became_required else _severity(ctx, name, BREAKING),
            name,
            f"required {before.get('required')} -> {after.get('required')}",
        )


def _diff_parameter_shape(ctx: _Context, name: str, before: dict, after: dict) -> None:
    if before != after:
        ctx.add(
            "PARAMETER_CHANGED",
            BREAKING,
            name,
            f"{json.dumps(before)} -> {json.dumps(after)}",
        )


def _relabel_known_absent_arrivals(ctx: _Context) -> None:
    """A declared-absent field arriving is its own headline, not a generic addition.

    These are the ESI-3 traps: fields our code reads that the public routes have
    never carried. If one shows up, the filter it powers becomes implementable —
    which is the actionable news, so it must not read as routine churn.
    """
    known_absent = ctx.new.get("known_absent_fields") or {}
    if not known_absent:
        return
    for index, finding in enumerate(ctx.findings):
        if finding.kind != "FIELD_ADDED":
            continue
        name = finding.subject[3:] if finding.subject.startswith("[].") else finding.subject
        record = known_absent.get(name)
        if record is None:
            continue
        ctx.findings[index] = Finding(
            kind="KNOWN_ABSENT_FIELD_APPEARED",
            severity=INFORMATIONAL,
            view=ctx.view,
            endpoint=ctx.endpoint,
            subject=name,
            detail=f"{finding.detail}; previously undocumented on this route",
            consumer=f"{record['consumer']} — today: {record['consequence']}",
            call_path=ctx.call_path,
        )


def _diff_manifest_consistency(ctx: _Context) -> None:
    """Report manifest/spec disagreements that the field diff did not already explain.

    A consumed field can go missing because the spec dropped it (already reported as
    FIELD_REMOVED) or because someone added a name to the manifest that ESI never
    documented. Only the second needs its own finding.
    """
    explained = {f.subject for f in ctx.findings} | {
        f.subject[3:] for f in ctx.findings if f.subject.startswith("[].")
    }
    before = set(ctx.old.get("consumed_fields_absent_from_spec", []))
    after = set(ctx.new.get("consumed_fields_absent_from_spec", []))
    for name in sorted(after - before - explained):
        ctx.add(
            "MANIFEST_FIELD_UNDOCUMENTED",
            BREAKING,
            name,
            "listed in the manifest as consumed, but absent from the spec",
        )
    for name in sorted(before - after - explained):
        ctx.add(
            "MANIFEST_FIELD_DOCUMENTED",
            INFORMATIONAL,
            name,
            "consumed field is documented again",
        )

    # The mirror case: a known-absent declaration that the spec contradicts. When the
    # spec starts carrying the field, `_relabel_known_absent_arrivals` has already
    # said so; anything left over is a manifest that claims a field is undocumented
    # when it is documented — the monitor understating its own coverage.
    stale = set(ctx.new.get("known_absent_fields_now_present", [])) - set(
        ctx.old.get("known_absent_fields_now_present", [])
    )
    for name in sorted(stale - explained):
        ctx.add(
            "KNOWN_ABSENT_DECLARATION_STALE",
            BREAKING,
            name,
            "declared known-absent in the manifest, but the spec documents it",
        )


def _diff_endpoint(view: str, key: str, old: dict, new: dict) -> list[Finding]:
    ctx = _Context(view=view, endpoint=key, old=old, new=new)

    if old.get("present") and not new.get("present"):
        ctx.add(
            "ENDPOINT_MISSING",
            BREAKING,
            key,
            f"{old.get('call_path', key)} is gone from the spec; called by "
            f"{old.get('caller', 'unknown caller')}",
        )
        return ctx.findings
    if not old.get("present") and new.get("present"):
        ctx.add("ENDPOINT_RESTORED", INFORMATIONAL, key, f"{new.get('call_path', key)} is back")
        return ctx.findings
    if not old.get("present") and not new.get("present"):
        return ctx.findings

    _diff_scalars(ctx)
    _diff_keyed(ctx, "response_fields", ("FIELD_ADDED", "FIELD_REMOVED"), _diff_field_shape,
                removed_severity=None)
    _diff_keyed(ctx, "parameters", ("PARAMETER_ADDED", "PARAMETER_REMOVED"),
                _diff_parameter_shape)
    _diff_status_codes(ctx)
    _relabel_known_absent_arrivals(ctx)
    _diff_manifest_consistency(ctx)
    return ctx.findings


def _diff_status_codes(ctx: _Context) -> None:
    before = set(ctx.old.get("response_statuses", []))
    after = set(ctx.new.get("response_statuses", []))
    for code in sorted(after - before):
        ctx.add("RESPONSE_STATUS_ADDED", INFORMATIONAL, code, f"new response status {code}")
    for code in sorted(before - after):
        ctx.add("RESPONSE_STATUS_REMOVED", BREAKING, code, f"response status {code} is gone")


def compare_snapshots(old: dict, new: dict) -> list[Finding]:
    """Every difference between two snapshots, breaking findings first."""
    findings: list[Finding] = []

    before_date = old.get("pinned_compatibility_date")
    after_date = new.get("pinned_compatibility_date")
    if before_date != after_date:
        findings.append(
            Finding(
                kind="PINNED_COMPATIBILITY_DATE_CHANGED",
                severity=BREAKING,
                view=PINNED_VIEW,
                endpoint="(spec)",
                subject="info.version",
                detail=(
                    f"{before_date} -> {after_date}: a request that omits "
                    "X-Compatibility-Date is served this date, so the floor our client "
                    "is pinned to has moved"
                ),
            )
        )

    for view in (PINNED_VIEW, NEWEST_VIEW):
        old_view = old.get("views", {}).get(view, {})
        new_view = new.get("views", {}).get(view, {})
        for key in sorted(set(old_view) | set(new_view)):
            findings.extend(
                _diff_endpoint(view, key, old_view.get(key, {}), new_view.get(key, {}))
            )

    findings.sort(key=lambda f: (f.severity != BREAKING, f.view != PINNED_VIEW, f.endpoint, f.subject))
    return findings


def format_report(findings: Sequence[Finding]) -> str:
    """A message that names the endpoint, the field, what moved, and who reads it."""
    if not findings:
        return "ESI spec monitor: no drift — the committed snapshot still matches the live spec."

    breaking = [f for f in findings if f.severity == BREAKING]
    lines = [
        f"ESI spec monitor: {len(findings)} change(s) against the committed snapshot "
        f"({len(breaking)} breaking).",
        "",
    ]
    for finding in findings:
        marker = "BREAKING" if finding.severity == BREAKING else "note    "
        where = finding.call_path or finding.endpoint
        lines.append(f"[{marker}] {finding.kind} — {where}")
        lines.append(f"           field: {finding.subject}")
        lines.append(f"           change: {finding.detail}")
        if finding.consumer:
            lines.append(f"           consumed by: {finding.consumer}")
        if finding.view == NEWEST_VIEW:
            lines.append(
                "           (seen only at the newest published compatibility date — "
                "not what our client receives today)"
            )
        lines.append("")
    lines.append(
        "If these changes are understood and accepted, re-run with --update and commit "
        "the snapshot in a PR that says why."
    )
    return "\n".join(lines)


# --- fetching ---------------------------------------------------------------


def _get_json(url: str, compatibility_date: str | None = None, timeout: float = 30.0) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    if compatibility_date:
        request.add_header("X-Compatibility-Date", compatibility_date)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_specs(get_json: Callable[..., dict] = _get_json) -> tuple[dict, dict, str]:
    """The pinned spec, the newest-compatibility-date spec, and that newest date.

    Three requests to static meta documents, no data endpoints, so ESI's shared
    error budget is untouched.
    """
    pinned = get_json(SPEC_URL, compatibility_date=PINNED_COMPATIBILITY_DATE)
    dates = get_json(COMPATIBILITY_DATES_URL).get("compatibility_dates", [])
    if not dates:
        raise ValueError(f"{COMPATIBILITY_DATES_URL} listed no compatibility dates")
    newest = max(dates)
    return pinned, get_json(SPEC_URL, compatibility_date=newest), newest


# --- CLI --------------------------------------------------------------------


def serialize(snapshot: dict) -> str:
    """The exact bytes committed to snapshot.json.

    `sort_keys` is what makes the committed file a stable artifact: without it the
    file would re-order whenever ESI re-ordered anything in its own document, and a
    reviewer would face a large diff that means nothing.
    """
    return json.dumps(snapshot, indent=2, sort_keys=True) + "\n"


def _write_snapshot(snapshot: dict, path: Path) -> None:
    path.write_text(serialize(snapshot), encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--update",
        action="store_true",
        help="rewrite the committed snapshot from the live spec (review the diff!)",
    )
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT_PATH)
    args = parser.parse_args(argv)

    try:
        pinned_spec, newest_spec, newest_date = fetch_specs()
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as exc:
        # An unreachable ESI is not drift. Say so distinctly so nobody reads a
        # network blip as a schema change and "fixes" it by updating the snapshot.
        print(f"ESI spec monitor: could not retrieve the spec — {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 2

    current = build_snapshot(pinned_spec, newest_spec)
    print(f"newest published compatibility date: {newest_date}")
    print(f"compatibility date Hangar Bay sends: {current['pinned_compatibility_date']}")

    if args.update:
        _write_snapshot(current, args.snapshot)
        print(f"snapshot written to {args.snapshot}")
        return 0

    if not args.snapshot.exists():
        print(f"no snapshot at {args.snapshot}; run with --update to create it", file=sys.stderr)
        return 2

    committed = json.loads(args.snapshot.read_text(encoding="utf-8"))
    findings = compare_snapshots(committed, current)
    print(format_report(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
