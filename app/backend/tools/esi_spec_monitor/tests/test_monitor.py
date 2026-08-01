# ABOUTME: Unit tests for the ESI spec monitor's projection and comparison logic — the part
# ABOUTME: that can be silently wrong, so every drift kind is proven detected and no-change proven quiet.
"""Tests for the drift detector itself.

These build fixture OpenAPI documents rather than hitting the network: the question
under test is "does the comparison notice X", and a live sample cannot answer that
reliably because it only contains whatever CCP happens to be serving today. The
predecessor to this monitor was a set of VCR cassettes whose replay made the tests
structurally unable to fail; the discipline here is the opposite — every assertion
is that a specific, deliberately-introduced mutation IS reported.
"""

from __future__ import annotations

import copy

import pytest

from esi_spec_monitor.manifest import Endpoint, KnownAbsentField
from esi_spec_monitor.monitor import (
    build_snapshot,
    compare_snapshots,
    format_report,
    project,
    serialize,
)

# --- fixtures ---------------------------------------------------------------

WIDGET = Endpoint(
    spec_path="/widgets/{widget_id}",
    method="get",
    call_path="/v1/widgets/{widget_id}/",
    caller="core/widget_client.py WidgetClient.get_widget",
    consumed_fields={
        "widget_id": "widget_service._build_rows -> Widget.widget_id",
        "colour": "widget_service._build_rows -> Widget.colour",
    },
    known_absent_fields=(
        KnownAbsentField(
            name="sparkle",
            consumer="widget_service._build_rows -> Widget.sparkle",
            consequence="always NULL; the sparkle filter matches zero rows",
        ),
    ),
)

GADGET = Endpoint(
    spec_path="/gadgets",
    method="post",
    call_path="/v2/gadgets/",
    caller="core/widget_client.py WidgetClient.resolve_gadgets",
    consumed_fields={"id": "widget_service -> the gadget id map key"},
)

FIXTURE_MANIFEST = (WIDGET, GADGET)


def _spec() -> dict:
    """A minimal but structurally faithful ESI-shaped OpenAPI document."""
    return {
        "openapi": "3.1.0",
        "info": {"version": "2020-01-01"},
        "components": {
            "schemas": {
                "WidgetsWidgetIdGet": {
                    "type": "object",
                    "properties": {
                        "widget_id": {"type": "integer", "format": "int64"},
                        "colour": {
                            "type": "string",
                            "enum": ["red", "green"],
                        },
                        "mass": {"type": "number", "format": "double"},
                    },
                    "required": ["widget_id", "colour"],
                },
                "GadgetsPost": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer", "format": "int64"},
                            "name": {"type": "string"},
                        },
                        "required": ["id", "name"],
                    },
                },
            }
        },
        "paths": {
            "/widgets/{widget_id}": {
                "get": {
                    "operationId": "GetWidgetsWidgetId",
                    "parameters": [
                        {
                            "in": "path",
                            "name": "widget_id",
                            "required": True,
                            "schema": {"type": "integer", "format": "int64"},
                        },
                        {"in": "query", "name": "page", "schema": {"type": "integer"}},
                    ],
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/WidgetsWidgetIdGet"
                                    }
                                }
                            }
                        },
                        "default": {"content": {"application/json": {"schema": {}}}},
                    },
                    "x-server-cache-mode": "ttl-based",
                    "x-compatibility-date": "2020-01-01",
                }
            },
            "/gadgets": {
                "post": {
                    "operationId": "PostGadgets",
                    "parameters": [],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {"type": "integer"},
                                    "maxItems": 1000,
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/GadgetsPost"}
                                }
                            }
                        }
                    },
                    "x-compatibility-date": "2020-01-01",
                }
            },
        },
    }


def _snapshot(spec: dict | None = None, newest: dict | None = None) -> dict:
    """Build a snapshot, defaulting both compatibility-date views to the same spec."""
    base = spec if spec is not None else _spec()
    return build_snapshot(base, newest if newest is not None else base, FIXTURE_MANIFEST)


def _findings(mutate) -> list:
    """Compare a baseline against a snapshot whose PINNED view alone was mutated.

    Isolating the pinned view keeps each assertion about one drift kind rather than
    about the view dimension; `test_a_change_at_both_dates_is_reported_once_per_view`
    covers the case where a change lands at every compatibility date at once.
    """
    spec = _spec()
    mutate(spec)
    return compare_snapshots(_snapshot(), _snapshot(spec, newest=_spec()))


def _kinds(findings) -> set[str]:
    return {f.kind for f in findings}


# --- the case that matters most: nothing changed ----------------------------


def test_identical_specs_produce_no_findings():
    assert compare_snapshots(_snapshot(), _snapshot()) == []


def test_reserialised_snapshot_still_produces_no_findings():
    """A snapshot round-tripped through JSON must compare equal to a fresh one.

    The committed snapshot is read back from disk as plain JSON, so if the
    projection emits anything JSON cannot represent losslessly (a tuple, a set,
    a non-string key) the monitor would report drift on every single run.
    """
    import json

    fresh = _snapshot()
    round_tripped = json.loads(json.dumps(fresh))
    assert compare_snapshots(round_tripped, fresh) == []


def test_an_unconsumed_part_of_the_spec_changing_is_not_reported():
    """The projection is a lens: churn outside the manifest must stay invisible."""

    def mutate(spec):
        spec["paths"]["/sprockets"] = {"get": {"operationId": "GetSprockets"}}
        spec["components"]["schemas"]["Unrelated"] = {"type": "object"}

    assert _findings(mutate) == []


# --- the required drift kinds -----------------------------------------------


def test_removed_field_is_reported_with_its_consumer():
    def mutate(spec):
        del spec["components"]["schemas"]["WidgetsWidgetIdGet"]["properties"]["colour"]
        spec["components"]["schemas"]["WidgetsWidgetIdGet"]["required"] = ["widget_id"]

    findings = _findings(mutate)
    removed = [f for f in findings if f.kind == "FIELD_REMOVED"]
    assert len(removed) == 1
    assert removed[0].endpoint == "GET /widgets/{widget_id}"
    assert removed[0].subject == "colour"
    assert removed[0].severity == "breaking"
    assert "widget_service._build_rows -> Widget.colour" in removed[0].consumer


def test_added_field_is_reported_as_informational():
    def mutate(spec):
        spec["components"]["schemas"]["WidgetsWidgetIdGet"]["properties"]["hue"] = {
            "type": "string"
        }

    findings = _findings(mutate)
    added = [f for f in findings if f.kind == "FIELD_ADDED"]
    assert len(added) == 1
    assert added[0].subject == "hue"
    assert added[0].severity == "informational"


def test_changed_field_type_is_reported():
    def mutate(spec):
        spec["components"]["schemas"]["WidgetsWidgetIdGet"]["properties"]["widget_id"][
            "type"
        ] = "string"

    findings = _findings(mutate)
    changed = [f for f in findings if f.kind == "FIELD_TYPE_CHANGED"]
    assert len(changed) == 1
    assert changed[0].subject == "widget_id"
    assert changed[0].severity == "breaking"
    assert "integer" in changed[0].detail and "string" in changed[0].detail


def test_removed_endpoint_is_reported():
    def mutate(spec):
        del spec["paths"]["/widgets/{widget_id}"]

    findings = _findings(mutate)
    assert "ENDPOINT_MISSING" in _kinds(findings)
    missing = [f for f in findings if f.kind == "ENDPOINT_MISSING"][0]
    assert missing.severity == "breaking"
    # The call path is what a reader greps for, so the report must quote it.
    assert "/v1/widgets/{widget_id}/" in missing.detail
    # One clear headline, not a field-by-field teardown of the vanished endpoint.
    assert [f for f in findings if f.endpoint == "GET /widgets/{widget_id}"] == [missing]


def test_added_auth_requirement_is_reported():
    def mutate(spec):
        spec["paths"]["/widgets/{widget_id}"]["get"]["security"] = [
            {"OAuth2": ["esi-widgets.read_widgets.v1"]}
        ]

    findings = _findings(mutate)
    auth = [f for f in findings if f.kind == "AUTH_CHANGED"]
    assert len(auth) == 1
    assert auth[0].severity == "breaking"
    assert "esi-widgets.read_widgets.v1" in auth[0].detail


# --- the rest of the drift surface ------------------------------------------


def test_required_field_becoming_optional_is_reported():
    def mutate(spec):
        spec["components"]["schemas"]["WidgetsWidgetIdGet"]["required"] = ["widget_id"]

    findings = _findings(mutate)
    assert [f.kind for f in findings] == ["FIELD_BECAME_OPTIONAL"]
    assert findings[0].subject == "colour"
    # A field we read losing its guarantee is a real hazard, not a note.
    assert findings[0].severity == "breaking"


def test_optional_field_becoming_required_is_reported():
    def mutate(spec):
        spec["components"]["schemas"]["WidgetsWidgetIdGet"]["required"].append("mass")

    findings = _findings(mutate)
    assert [f.kind for f in findings] == ["FIELD_BECAME_REQUIRED"]
    assert findings[0].subject == "mass"
    assert findings[0].severity == "informational"


def test_enum_change_is_reported():
    def mutate(spec):
        spec["components"]["schemas"]["WidgetsWidgetIdGet"]["properties"]["colour"][
            "enum"
        ] = ["red", "green", "blue"]

    findings = _findings(mutate)
    assert [f.kind for f in findings] == ["FIELD_ENUM_CHANGED"]
    assert "blue" in findings[0].detail
    # We branch on enum values, so a new member can silently fall through.
    assert findings[0].severity == "breaking"


def test_nested_field_is_projected_and_its_removal_reported():
    def mutate(spec):
        del spec["components"]["schemas"]["GadgetsPost"]["items"]["properties"]["name"]
        spec["components"]["schemas"]["GadgetsPost"]["items"]["required"] = ["id"]

    findings = _findings(mutate)
    removed = [f for f in findings if f.kind == "FIELD_REMOVED"]
    assert [f.subject for f in removed] == ["[].name"]


def test_removed_query_parameter_is_reported():
    def mutate(spec):
        spec["paths"]["/widgets/{widget_id}"]["get"]["parameters"] = [
            p
            for p in spec["paths"]["/widgets/{widget_id}"]["get"]["parameters"]
            if p["name"] != "page"
        ]

    findings = _findings(mutate)
    assert [f.kind for f in findings] == ["PARAMETER_REMOVED"]
    assert findings[0].subject == "query:page"
    assert findings[0].severity == "breaking"


def test_changed_response_status_set_is_reported():
    def mutate(spec):
        spec["paths"]["/widgets/{widget_id}"]["get"]["responses"]["204"] = {
            "content": {"application/json": {"schema": {}}}
        }

    findings = _findings(mutate)
    assert [f.kind for f in findings] == ["RESPONSE_STATUS_ADDED"]
    assert findings[0].subject == "204"


def test_request_body_change_is_reported():
    def mutate(spec):
        body = spec["paths"]["/gadgets"]["post"]["requestBody"]
        body["content"]["application/json"]["schema"]["maxItems"] = 100

    findings = _findings(mutate)
    assert [f.kind for f in findings] == ["REQUEST_BODY_CHANGED"]
    assert "100" in findings[0].detail


def test_server_cache_mode_change_is_reported():
    """ESI-2: routes are converting from clock expiry to event-driven invalidation."""

    def mutate(spec):
        spec["paths"]["/widgets/{widget_id}"]["get"][
            "x-server-cache-mode"
        ] = "event-based"

    findings = _findings(mutate)
    assert [f.kind for f in findings] == ["CACHE_MODE_CHANGED"]
    assert "event-based" in findings[0].detail


def test_operation_compatibility_date_change_is_reported():
    def mutate(spec):
        spec["paths"]["/widgets/{widget_id}"]["get"]["x-compatibility-date"] = "2026-07-21"

    findings = _findings(mutate)
    assert [f.kind for f in findings] == ["OPERATION_COMPATIBILITY_DATE_CHANGED"]


def test_pinned_compatibility_date_change_is_reported():
    """Omitting X-Compatibility-Date pins us to the oldest date; CCP can raise that floor."""
    before = _snapshot()
    spec = _spec()
    spec["info"]["version"] = "2025-04-01"
    findings = compare_snapshots(before, _snapshot(spec))
    assert [f.kind for f in findings] == ["PINNED_COMPATIBILITY_DATE_CHANGED"]
    assert findings[0].severity == "breaking"


def test_drift_at_the_newest_compatibility_date_is_reported_separately():
    """Our shape today is unchanged, but adopting the newest date would change it."""
    newest = _spec()
    del newest["components"]["schemas"]["WidgetsWidgetIdGet"]["properties"]["colour"]
    newest["components"]["schemas"]["WidgetsWidgetIdGet"]["required"] = ["widget_id"]

    findings = compare_snapshots(_snapshot(), _snapshot(newest=newest))
    assert [f.kind for f in findings] == ["FIELD_REMOVED"]
    assert findings[0].view == "newest_compatibility_date"
    # It is not breaking *yet* — it only bites when the pinned floor moves.
    assert findings[0].severity == "informational"


def test_a_change_at_both_dates_is_reported_once_per_view():
    """A route removal (ESI's spring cleaning) lands at every compatibility date."""
    mutated = _spec()
    del mutated["paths"]["/widgets/{widget_id}"]

    findings = compare_snapshots(_snapshot(), _snapshot(mutated))
    assert [f.kind for f in findings] == ["ENDPOINT_MISSING", "ENDPOINT_MISSING"]
    assert [f.view for f in findings] == ["pinned", "newest_compatibility_date"]
    # The one our client actually receives is the breaking one, and leads.
    assert [f.severity for f in findings] == ["breaking", "informational"]


# --- manifest/spec consistency (the ESI-3 family) ---------------------------


def test_consumed_field_absent_from_the_spec_is_recorded_in_the_projection():
    spec = _spec()
    del spec["components"]["schemas"]["WidgetsWidgetIdGet"]["properties"]["colour"]
    projection = project(spec, FIXTURE_MANIFEST)
    entry = projection["GET /widgets/{widget_id}"]
    assert entry["consumed_fields_absent_from_spec"] == ["colour"]


def test_known_absent_field_appearing_is_reported():
    """If ESI starts sending it, the filter it powers becomes implementable — that is news."""

    def mutate(spec):
        spec["components"]["schemas"]["WidgetsWidgetIdGet"]["properties"]["sparkle"] = {
            "type": "boolean"
        }

    findings = _findings(mutate)
    kinds = _kinds(findings)
    assert "KNOWN_ABSENT_FIELD_APPEARED" in kinds
    appeared = [f for f in findings if f.kind == "KNOWN_ABSENT_FIELD_APPEARED"][0]
    assert appeared.subject == "sparkle"
    assert "sparkle filter matches zero rows" in appeared.consumer


def test_known_absent_field_is_not_also_reported_as_a_plain_addition():
    """One event, one finding — a declared-absent field arriving is not generic news."""

    def mutate(spec):
        spec["components"]["schemas"]["WidgetsWidgetIdGet"]["properties"]["sparkle"] = {
            "type": "boolean"
        }

    findings = _findings(mutate)
    assert [f.kind for f in findings] == ["KNOWN_ABSENT_FIELD_APPEARED"]


def test_a_known_absent_declaration_the_spec_contradicts_is_reported():
    """Guards the monitor against understating its own coverage.

    Declaring a field known-absent when ESI documents it would quietly exempt that
    field from the drift checks. The spec here is unchanged — only the manifest is
    wrong — so nothing else in the comparison would notice.
    """
    spec = _spec()
    honest = build_snapshot(spec, spec, FIXTURE_MANIFEST)
    mislabelled = build_snapshot(
        spec,
        spec,
        (
            Endpoint(
                spec_path=WIDGET.spec_path,
                method=WIDGET.method,
                call_path=WIDGET.call_path,
                caller=WIDGET.caller,
                consumed_fields=WIDGET.consumed_fields,
                known_absent_fields=WIDGET.known_absent_fields
                + (
                    KnownAbsentField(
                        name="mass",
                        consumer="widget_service -> Widget.mass",
                        consequence="claimed absent, but the spec has carried it all along",
                    ),
                ),
            ),
            GADGET,
        ),
    )

    findings = compare_snapshots(honest, mislabelled)
    stale = [f for f in findings if f.kind == "KNOWN_ABSENT_DECLARATION_STALE"]
    assert [f.subject for f in stale] == ["mass", "mass"]  # once per compatibility view
    assert stale[0].severity == "breaking"


def test_baseline_projection_declares_no_missing_consumed_fields():
    projection = project(_spec(), FIXTURE_MANIFEST)
    for entry in projection.values():
        assert entry["consumed_fields_absent_from_spec"] == []
        assert entry["known_absent_fields_now_present"] == []


# --- reporting --------------------------------------------------------------


def test_report_names_endpoint_field_change_and_consumer():
    def mutate(spec):
        del spec["components"]["schemas"]["WidgetsWidgetIdGet"]["properties"]["colour"]
        spec["components"]["schemas"]["WidgetsWidgetIdGet"]["required"] = ["widget_id"]

    report = format_report(_findings(mutate))
    assert "/v1/widgets/{widget_id}/" in report
    assert "colour" in report
    assert "FIELD_REMOVED" in report
    assert "widget_service._build_rows -> Widget.colour" in report


def test_report_leads_with_breaking_findings():
    def mutate(spec):
        spec["components"]["schemas"]["WidgetsWidgetIdGet"]["properties"]["hue"] = {
            "type": "string"
        }
        del spec["components"]["schemas"]["WidgetsWidgetIdGet"]["properties"]["colour"]
        spec["components"]["schemas"]["WidgetsWidgetIdGet"]["required"] = ["widget_id"]

    report = format_report(_findings(mutate))
    assert report.index("FIELD_REMOVED") < report.index("FIELD_ADDED")


def test_report_for_no_findings_says_so_and_mentions_no_endpoint():
    report = format_report([])
    assert "no drift" in report.lower()
    assert "/widgets/" not in report


# --- projection details worth pinning ---------------------------------------


def test_the_compatibility_date_headers_enum_is_not_snapshotted():
    """That enum echoes the date the spec copy was served for, not a route's shape.

    Snapshotting it would make every operation restate the served date, so publishing
    a new compatibility date — a calendar event CCP performs every few weeks, usually
    touching none of our routes — would fire the monitor. That is precisely the
    cry-wolf failure that gets a monitor muted.
    """
    pinned = _spec()
    newest = _spec()
    for spec, date in ((pinned, "2020-01-01"), (newest, "2026-07-21")):
        spec["paths"]["/widgets/{widget_id}"]["get"]["parameters"].append(
            {
                "in": "header",
                "name": "X-Compatibility-Date",
                "required": True,
                "schema": {"type": "string", "format": "date", "enum": [date]},
            }
        )

    projected = project(pinned, FIXTURE_MANIFEST)["GET /widgets/{widget_id}"]
    assert "enum" not in projected["parameters"]["header:X-Compatibility-Date"]
    assert projected["parameters"]["header:X-Compatibility-Date"]["required"] is True
    assert compare_snapshots(_snapshot(pinned), _snapshot(pinned, newest=newest)) == []


def test_array_of_scalars_records_its_element_type():
    """Otherwise a list of enum strings and a list of integers project identically."""
    spec = _spec()
    spec["components"]["schemas"]["WidgetsWidgetIdGet"]["properties"]["services"] = {
        "type": "array",
        "items": {"type": "string", "enum": ["docking", "market"]},
    }
    projected = project(spec, FIXTURE_MANIFEST)["GET /widgets/{widget_id}"]
    assert projected["response_fields"]["services"]["items"] == {
        "type": "string",
        "enum": ["docking", "market"],
    }


def test_changed_array_element_type_is_reported():
    baseline_with_tags = _spec()
    baseline_with_tags["components"]["schemas"]["WidgetsWidgetIdGet"]["properties"][
        "tags"
    ] = {"type": "array", "items": {"type": "string"}}
    widened = copy.deepcopy(baseline_with_tags)
    widened["components"]["schemas"]["WidgetsWidgetIdGet"]["properties"]["tags"][
        "items"
    ] = {"type": "integer"}

    findings = compare_snapshots(
        _snapshot(baseline_with_tags), _snapshot(widened, newest=baseline_with_tags)
    )
    assert [f.kind for f in findings] == ["FIELD_TYPE_CHANGED"]
    assert findings[0].subject == "tags"


def test_projection_records_public_endpoints_as_unauthenticated():
    projection = project(_spec(), FIXTURE_MANIFEST)
    assert projection["GET /widgets/{widget_id}"]["security"] == []


def test_projection_marks_a_missing_endpoint_rather_than_omitting_it():
    """An absent endpoint must be an explicit False, not a missing key.

    A key that simply disappears from the snapshot would compare as "nothing there
    before, nothing there now" against a stale baseline, which is how a monitor
    goes quiet at the exact moment it should shout.
    """
    spec = _spec()
    del spec["paths"]["/gadgets"]
    projection = project(spec, FIXTURE_MANIFEST)
    assert projection["POST /gadgets"] == {"present": False}


def test_projection_is_stable_across_key_ordering():
    """Snapshot equality must not depend on the order the spec happens to list things.

    Path keys, schema properties and the parameter *list* are all orderings CCP can
    change without changing meaning. If any of them leaked into the projection, the
    monitor would report drift for a cosmetic reshuffle — noise that trains readers
    to update the snapshot without reading it.
    """
    spec = _spec()
    shuffled = copy.deepcopy(spec)
    shuffled["paths"] = dict(reversed(list(shuffled["paths"].items())))
    props = shuffled["components"]["schemas"]["WidgetsWidgetIdGet"]["properties"]
    shuffled["components"]["schemas"]["WidgetsWidgetIdGet"]["properties"] = dict(
        reversed(list(props.items()))
    )
    operation = shuffled["paths"]["/widgets/{widget_id}"]["get"]
    operation["parameters"] = list(reversed(operation["parameters"]))

    assert compare_snapshots(_snapshot(spec), _snapshot(shuffled)) == []
    # And the committed artifact itself: a reshuffle must not produce a file diff.
    assert serialize(_snapshot(spec)) == serialize(_snapshot(shuffled))


def test_unresolvable_ref_raises_rather_than_projecting_an_empty_shape():
    """A broken $ref must not silently project as "this endpoint has no fields".

    That failure mode would look identical to "CCP removed every field", and the
    quiet version of it — projecting {} and comparing clean — is worse still.
    """
    spec = _spec()
    spec["paths"]["/widgets/{widget_id}"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"] = {"$ref": "#/components/schemas/DoesNotExist"}
    with pytest.raises(KeyError):
        project(spec, FIXTURE_MANIFEST)
