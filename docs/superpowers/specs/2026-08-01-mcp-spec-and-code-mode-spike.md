<!-- ABOUTME: Bounded spike answering two questions — what the 2026-07-28 MCP spec revision changed (especially authorization), -->
<!-- ABOUTME: and whether Hangar Bay's MCP surface should be discrete tools or "code mode". Corrects/confirms the 2026-08-01 surface research. -->

# MCP spec state + code-mode spike

**Date:** 2026-08-01
**Status:** Research spike. No decisions taken; no application code touched.
**Scope:** Two questions only — (1) what changed in the recent MCP spec revision(s), authorization in particular; (2) normal tool-based MCP vs. "code mode" for Hangar Bay.
**Companions:** `2026-08-01-mcp-surface-research.md` (the prior position this spike audits), `2026-08-01-contract-coverage-gap-analysis.md` §7 (its decision-relevant summary).

---

## Verdicts

**Q1 — What changed, and does it move us?**
**Nothing material has changed since the prior research, and the prior research's authorization conclusion survives verification against the specification text verbatim.** Deciding reason: `2026-07-28` is still the *current* revision as of today with an empty draft changelog, and the normative sentences the prior doc rested on — "Authorization is **OPTIONAL** for MCP implementations", "MCP clients **MUST NOT** send tokens to the MCP server other than ones issued by the MCP server's authorization server", "MCP servers **MUST NOT** accept or transit any other tokens" — are present unaltered, so EVE SSO still cannot be the MCP authorization server and a read-only public server is still fully conformant with no authorization at all.

**Q2 — Tools or code mode?**
**Discrete hand-written tools. Not code mode, and not a hybrid, for v1.** Deciding reason: code mode's published win is overwhelmingly *tool-definition* and *intermediate-data* tokens across many tools and many servers (Anthropic's worked example: 150,000 → 2,000 tokens across two large connectors), and Hangar Bay would ship ~7 tools totalling an estimated 2,500–4,000 definition tokens against measured result payloads of ~540 tokens for a 5-row concise answer — there is no token problem to solve, and buying a code-execution sandbox to solve it would add the single largest new attack surface and operating cost in the project for a saving that rounds to zero.

---

## Q1 — What actually changed in the MCP specification

### 1.1 Revision state as of 2026-08-01

| Fact | Value | Source |
|---|---|---|
| Current revision | **`2026-07-28`** | [Versioning](https://modelcontextprotocol.io/specification/versioning): "The **current** protocol version is **2026-07-28**." |
| Previous revision | `2025-11-25` | [2026-07-28 changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog) — "changes made … since the previous revision, 2025-11-25" |
| Lineage | 2024-11-05 → 2025-03-26 → 2025-06-18 → 2025-11-25 → 2026-07-28 | versioning page + changelog |
| Draft revision beyond current | **None.** `/specification/draft/changelog` reads, in full: "Changes since the most recent release will accumulate here." | fetched 2026-08-01 |
| Spec release blog | 2026-07-28 | [blog.modelcontextprotocol.io/posts/2026-07-28](https://blog.modelcontextprotocol.io/posts/2026-07-28/) |
| Official Python SDK | **v2.0.0, released 2026-07-28**; `v1.29.0` same day is the v1 maintenance line (v1.x → security fixes only) | [python-sdk releases](https://github.com/modelcontextprotocol/python-sdk/releases) |
| Claude client support | "Support is being rolled out across Claude products **soon**" — no dates given | [claude.com/blog/bringing-mcp-2026-07-28-to-claude](https://claude.com/blog/bringing-mcp-2026-07-28-to-claude), 2026-07-28 |

So: the prior research was written *four days* after the revision landed and is aimed at the right target. There is no newer revision to chase. The next thing to watch is not a spec date but a **client** date — Claude's rollout.

### 1.2 Dated changelog table (2025-11-25 → 2026-07-28)

All rows from the [official changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog), revision dated 2026-07-28. "Affects us" is judged for a **read-only, public, unauthenticated, ~7-tool** Hangar Bay server.

| # | Change | Kind | Affects us? |
|---|---|---|---|
| M1 | Protocol-level sessions and `Mcp-Session-Id` removed from Streamable HTTP; list endpoints no longer vary per-connection; cross-call state uses server-minted handles passed as ordinary tool arguments (SEP-2567) | Breaking | **Yes, positively.** A stateless server runs behind Render's load balancer with no shared session store. Our pagination cursor becomes an ordinary tool argument, which is what we wanted anyway. |
| M2 | Protocol made stateless: `initialize`/`notifications/initialized` handshake removed; every request carries version + client capabilities in `_meta`; `UnsupportedProtocolVersionError` on mismatch (SEP-2575) | Breaking | **Yes.** Handled by the SDK. Removes the "long-lived connection" mental model entirely. |
| M3 | `server/discover` RPC added — servers **MUST** implement it (SEP-2575) | Breaking | Yes — mandatory, SDK-provided. |
| M4 | HTTP GET endpoint and `resources/subscribe`/`unsubscribe` replaced by `subscriptions/listen` (single long-lived POST-response stream, opt-in notification types) (SEP-2575) | Breaking | Only if we ever build the "watch this type" resource-subscription idea. Not v1. |
| M5 | `ping`, `logging/setLevel`, `notifications/roots/list_changed` removed; log level per-request via `_meta` | Breaking | No. |
| M6 | Tasks moved out of core into the `io.modelcontextprotocol/tasks` extension; polling via `tasks/get`, `tasks/update`; `tasks/list` removed (SEP-2663) | Breaking | No — nothing we'd do is long-running. |
| M7 | **MRTR** (Multi Round-Trip Requests) replaces all server-initiated requests; server returns `InputRequiredResult` with `inputRequests`, client retries with `inputResponses` (SEP-2322) | Breaking | Yes, if we use elicitation for name disambiguation. Elicitation is **not** deprecated — it now travels inside `inputRequests` as `elicitation/create`. |
| M8 | All results carry a required `resultType` (`"complete"` / `"input_required"`) (SEP-2322) | Breaking | Yes — SDK-handled. |
| M9 | SSE resumability and message redelivery removed (`Last-Event-ID`, SSE event IDs); a broken stream loses the in-flight request (SEP-2575) | Breaking | Marginal. Our responses are small and non-streaming. |
| m1 | `extensions` field added to client/server capabilities | Minor | Only if we adopt an extension. |
| m2 | OpenTelemetry trace-context conventions documented for `_meta` (`traceparent`, `tracestate`, `baggage`) (SEP-414) | Minor | **Yes, positively** — we already ship to Grafana Cloud via Alloy. |
| m3 | Servers **SHOULD** return `tools/list` in deterministic order (client caching + LLM prompt-cache hits) | Minor | Yes, trivial. |
| m4 | `Mcp-Method` / `Mcp-Name` headers **REQUIRED** on Streamable HTTP POSTs; `x-mcp-header` mirrors tool params into `Mcp-Param-{Name}` headers (SEP-2243) | Minor | **Yes** — see §1.4; this is a genuinely useful new lever for edge rate limiting. |
| m5 | `ttlMs` + `cacheScope` **required** on `tools/list`, `prompts/list`, `resources/list`, `resources/read`, `resources/templates/list` via `CacheableResult` (SEP-2549) | Minor | **Yes, positively.** `cacheScope: "public"` on a public read-only server lets shared intermediaries cache. Note: these fields are on *list/read* results, **not** on `tools/call` results. |
| m6 | Resource-not-found error code `-32002` → `-32602` | Minor | No. |
| m7 | Authorization servers **SHOULD** include `iss` per RFC 9207; clients **MUST** validate it (SEP-2468) | Minor (auth) | Only if we ever run an AS. |
| m8 | Clients **MUST** specify `application_type` during DCR (OIDC redirect-URI conflicts) (SEP-837) | Minor (auth) | No — client-side. |
| m9 | Client credentials bound to issuing AS; **MUST** key by issuer, **MUST NOT** reuse across AS, **MUST** re-register on AS change (SEP-2352) | Minor (auth) | No — client-side. |
| m10 | `inputSchema`/`outputSchema` loosened to any JSON Schema 2020-12 keywords; `structuredContent` may be **any JSON value**; `$ref` resolution requirements and composition-keyword bounds added (SEP-2106) | Minor | **Yes, mildly positively** — a top-level array `structuredContent` is now explicitly legal. |
| m11 | `notifications/elicitation/complete` and the URL-mode `elicitationId` (both new in 2025-11-25) removed; correlation now via server-encoded `requestState` | Minor | Yes if we use elicitation. |
| m12 | Error-code allocation policy: `-32000..-32019` implementation-defined, `-32020..-32099` reserved for the spec; `HeaderMismatch` renumbered to `-32020` | Minor | Yes — our rate-limit errors must live in `-32000..-32019` or be plain HTTP 429. |
| D1 | **Roots, Sampling, Logging deprecated** (SEP-2577); earliest removal = first revision on/after **2027-07-28** | Deprecation | No — we use none of them. |
| D2 | HTTP+SSE transport reclassified Deprecated (deprecated since 2025-03-26) | Deprecation | No. |
| D3 | `includeContext: "thisServer"/"allServers"` reclassified Deprecated | Deprecation | No. |
| D4 | **OAuth 2.0 Dynamic Client Registration (RFC 7591) deprecated** in favour of Client ID Metadata Documents (PR #2858); earliest removal on/after 2027-07-28 | Deprecation (auth) | **Yes** — see §1.3; this is the one auth change that *reduces* our hypothetical cost. |
| G1 | Feature lifecycle + deprecation policy adopted: Active/Deprecated/Removed, minimum **twelve-month** window, 90-day expedited exception (SEP-2596) | Governance | Yes — bounds protocol-churn risk. |
| P1 | PR-based SEP workflow formalised (`seps/` directory, PR-derived numbering) (SEP-1850) | Process | No. |

Also verified directly against the machine-readable schema (`schema/2026-07-28/schema.json`, 181 KB, fetched 2026-08-01):

- `ToolAnnotations` still carries `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`, `title` — all documented as **hints**, and the tools page warns clients **MUST** treat annotations as untrusted from untrusted servers.
- `CallToolResult` has **no cursor field**. Tool-result pagination remains entirely application-level, re-confirming the prior doc.

### 1.3 Authorization, in detail

This is the section the prior doc's most consequential conclusion rests on, so it was verified sentence by sentence against [the authorization spec](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization) and [its security considerations](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/security-considerations).

**Is authorization mandatory?** No. Verbatim: *"Authorization is **OPTIONAL** for MCP implementations."* A fully public, unauthenticated MCP server is conformant. **This is unchanged and it is the load-bearing fact for a read-only Hangar Bay v1.**

**What is required of a *protected* remote server?**

| Requirement | Normative text | Status |
|---|---|---|
| Server role | *"A protected MCP server acts as an OAuth 2.1 resource server"* | Unchanged |
| RFC 9728 Protected Resource Metadata | *"MCP servers **MUST** implement OAuth 2.0 Protected Resource Metadata … MCP clients **MUST** use [it] for authorization server discovery"* | Unchanged, still MUST |
| RFC 8707 Resource Indicators | *"MCP clients **MUST** implement Resource Indicators for OAuth 2.0 …"*; the `resource` parameter **MUST** be in both authorization and token requests, **MUST** identify the MCP server, **MUST** be the canonical URI; and clients **MUST** send it *"regardless of whether authorization servers support it"* | Unchanged, still MUST |
| Audience validation | *"MCP servers **MUST** validate that access tokens were issued specifically for them as the intended audience"* | Unchanged |
| Token passthrough ban | *"MCP clients **MUST NOT** send tokens to the MCP server other than ones issued by the MCP server's authorization server."* / *"MCP servers **MUST NOT** accept or transit any other tokens."* | Unchanged |
| AS metadata | AS **MUST** provide RFC 8414 **or** OIDC Discovery 1.0; clients **MUST** support both | Unchanged |
| PKCE | Clients **MUST** implement PKCE, **MUST** use `S256`, **MUST** verify PKCE support via AS metadata or refuse to proceed | Unchanged |
| RFC 9207 `iss` | AS **SHOULD** include `iss`; clients **MUST** validate a present `iss`. Spec states a future revision is *expected* to upgrade this to MUST | **New in 2026-07-28** |
| Client registration | CIMD **SHOULD** be supported by AS and clients; **DCR is deprecated**, "retained for backwards compatibility" | **Changed in 2026-07-28** |

**Is an operator-run OAuth 2.1 authorization server still mandatory for a protected server?** **Yes, effectively — with one nuance the prior doc under-stated.** The spec says the AS *"may be hosted with the resource server or a separate entity"* and that *"the implementation details of the authorization server are beyond the scope of this specification."* So Hangar Bay could implement a minimal AS **in-process** rather than renting AuthKit/Auth0/Stytch/Keycloak. That does not change the *nature* of the work — it is still OAuth 2.1 with PKCE/S256, RFC 8414 or OIDC metadata, RFC 9728 protected-resource metadata, RFC 8707 audience-bound tokens, RFC 9207 `iss`, CIMD fetch-and-validate, refresh-token rotation for public clients — but it does mean "rent an IdP" is not a hard requirement, only a build-vs-buy choice.

**Has anything changed that lets a federated upstream IdP like EVE SSO be used more directly?** **No.** Three findings, all verified:

1. **The federation pattern is explicitly the *only* sanctioned shape, and it is normatively described.** From security considerations, verbatim: *"If the MCP server makes requests to upstream APIs, it may act as an OAuth client to them. The access token used at the upstream API is a separate token, issued by the upstream authorization server. The MCP server **MUST NOT** pass through the token it received from the MCP client."* That is precisely the prior doc's three-layer architecture — EVE SSO upstream, an MCP-audience AS in the middle, the MCP server as pure resource server — written into the spec. It is **confirmation**, not relaxation.
2. **`ext-auth` exists but does not help us.** The 2026-07-28 revision introduced official [authorization extensions](https://github.com/modelcontextprotocol/ext-auth): **Enterprise-Managed Authorization** (stable) and **OAuth Client Credentials** (draft). EMA (from SEP-990) is the closest thing in the ecosystem to "use an existing IdP directly": the client obtains an ID token from a corporate IdP, exchanges it for an **ID-JAG** (Identity Assertion JWT Authorization Grant), and presents the ID-JAG to the **MCP Authorization Server**, which validates it and mints an MCP access token. Read the flow carefully — *the MCP Authorization Server is still in the diagram, still minting the token, still audience-binding it.* EMA relocates *policy* to the IdP; it does not remove the AS. And it requires the IdP to issue ID-JAGs, which EVE SSO does not.
3. **The three EVE SSO blockers the prior doc named are untouched by this revision.** No dynamic registration and no CIMD (manual portal registration only); no RFC 8707 resource-indicator support; wrong audience (`aud = [client_id, "EVE Online"]`, not our canonical URI). Nothing in `2026-07-28` creates a path for a token minted by a third party with the wrong audience to be accepted.

**One genuine, modest relaxation: CIMD replaces DCR.** Under the 2025-06-18/2025-11-25 regime, a public MCP server whose users arrive with arbitrary unknown clients effectively had to expose an RFC 7591 `/register` endpoint — a write endpoint, with client-record storage, abuse surface, and cleanup. Under CIMD the client's `client_id` *is* an HTTPS URL; the AS fetches, validates that `client_id` matches the URL exactly, validates redirect URIs against the document, and caches per HTTP cache headers. No registration endpoint, no client store, no re-registration when the AS changes ("Client IDs based on Client ID Metadata Documents are portable across authorization servers"). The new cost is an **outbound fetch of an attacker-supplied URL**, i.e. SSRF exposure, which the spec flags: authorization servers **SHOULD** consider SSRF risks and **MAY** apply domain-based trust policies. Net: a hypothetical Hangar Bay AS is somewhat cheaper and somewhat differently risky than it was in 2025. It is still a milestone, not a task.

### 1.4 Transport and lifecycle, for a read-only public server specifically

- **Single POST endpoint.** *"The server **MUST** provide a single HTTP endpoint path … that supports POST."* No GET stream, no DELETE, no session header. A 2026-07-28-only server **SHOULD** answer GET/DELETE with `405`, ignore `Mcp-Session-Id`, and ignore `Last-Event-ID`.
- **Stateless deployment is now the default posture,** which suits Render: no sticky sessions, no shared session store. It does *not* relieve the M4 constraint that we pin to one instance via the `scheduler-pin` disk — that pin exists for the APScheduler singleton, not for MCP.
- **Origin validation is a MUST:** *"Servers **MUST** validate the `Origin` header on all incoming connections to prevent DNS rebinding attacks,"* responding `403` on a present-and-invalid Origin. This is a new day-one implementation requirement for us and interacts with PROXY-1 — if MCP is mounted on its own hostname (`mcp.hangarbay.app`), the allowed-origin set must be decided at the edge and in the app.
- **Required headers `Mcp-Method` and `Mcp-Name`, and `x-mcp-header`.** Servers **MUST** reject header/body mismatches with `400` + `-32020`. The upside is concrete: an edge (Render rewrite, or a CDN in front) can rate-limit and route on `Mcp-Name` *without parsing the JSON body*. §4a of the prior doc wanted per-tool rate limiting; `Mcp-Name` makes that implementable at the edge rather than only in the app.
- **`X-Accel-Buffering: no`** is a SHOULD when opening SSE streams. Irrelevant if every tool returns a single JSON object, which ours should.
- **Caching:** `ttlMs` + `cacheScope: "public"` on `tools/list` is free and valuable for us — a static tool list on a public server is the ideal case for intermediary caching. `tools/call` results carry no such fields; freshness for those stays inside our own payload (`data_as_of` / `data_stale`), exactly as the prior doc specified.
- **Elicitation survives, reshaped.** Not in the deprecated registry. It is now an `inputRequests` entry inside an `InputRequiredResult`, correlated via server-encoded `requestState`. The prior doc's warning stands and is if anything stronger: *"the JSON-RPC `id` **MUST** be different between the initial request and the retry"*, and `requestState` is fully attacker-controlled round-trip state.
- **Tool output:** `outputSchema` still means servers **MUST** conform and clients **SHOULD** validate; the backwards-compatibility guidance is unchanged — *"a tool that returns structured content SHOULD also return the serialized JSON in a TextContent block."* The prior doc's operational rule ("make `content` self-sufficient") is exactly right and is now also the spec's own advice.
- **Rate limiting is still a server MUST:** the tools page lists, under "Servers **MUST**": validate all tool inputs, implement proper access controls, **rate limit tool invocations**, sanitize tool outputs.
- **Stateful-tools guidance is non-normative but present**, and says what the prior doc reported: opaque high-entropy handles, bounded lifetime, retention policy stated *in the tool description*, actionable expiry errors, and — for unauthenticated servers — the explicit acknowledgement that *"the handle is necessarily a bearer token."*

---

## Corrections to `2026-08-01-mcp-surface-research.md`

Audited every protocol/auth claim in that document against primary sources. **The document holds up unusually well.** There are no reversals. Below is every claim examined, with its status.

### Confirmed verbatim (no change needed)

| Prior claim | Evidence |
|---|---|
| Current revision is `2026-07-28`; lineage as listed | [Versioning page](https://modelcontextprotocol.io/specification/versioning) |
| `initialize` handshake and protocol sessions removed; per-request `_meta` version negotiation; state via server-minted opaque handles as tool arguments | Changelog M1, M2 |
| `server/discover` mandatory for servers | Changelog M3 |
| MRTR replaces all server-initiated requests; every result carries `resultType` | Changelog M7, M8 |
| `subscriptions/listen` replaces `resources/subscribe` | Changelog M4 |
| Sampling, Roots, Logging deprecated with a 12-month runway | Changelog D1 + [deprecated registry](https://modelcontextprotocol.io/specification/2026-07-28/deprecated): earliest removal "first revision released on or after 2027-07-28" |
| `ttlMs` + `cacheScope` now required; `"public"` shareable across auth contexts | Changelog m5 |
| No tool-result pagination anywhere in MCP; opaque-cursor MUST binds list operations only | `CallToolResult` has no cursor field in `schema.json`; tools page routes pagination only through `tools/list` |
| Error codes: `-32020..-32099` reserved for the spec, `-32000..-32019` implementation-defined | Changelog m12; [error-code policy](https://modelcontextprotocol.io/specification/2026-07-28/basic/index#error-codes) |
| Spec says servers MUST rate-limit tool invocations | Tools page, Security Considerations |
| MCP server is an OAuth 2.1 Resource Server; MUST implement RFC 9728; clients MUST use RFC 8707; clients MUST NOT send other tokens; servers MUST NOT accept or transit them | Authorization page, quoted in §1.3 above |
| "You cannot hand an EVE SSO token to the MCP server" | Direct consequence of the two MUST NOTs; still true |
| DCR is now deprecated | Changelog D4; deprecated registry |
| Authorization is OPTIONAL; a fully public server is conformant | *"Authorization is **OPTIONAL** for MCP implementations."* |
| EVE SSO cannot be the MCP AS — no DCR/CIMD, no RFC 8707, wrong audience | Blockers unaffected by this revision; nothing in `2026-07-28` creates a path |
| Correct architecture = resource server + an AS we operate or rent + EVE SSO federated upstream, EVE tokens never visible to the MCP client | Now *normatively described* in security considerations (upstream-API paragraph quoted in §1.3) — **strengthened** |
| Errors as prompts: tool-execution errors in-result with `isError: true`, actionable text | Tools page, Error Handling |
| Structured output first-class: `outputSchema` + `structuredContent`, JSON echoed in a text block | Tools page, Structured Content / Output Schema |
| Official Python SDK v2.0.0 shipped 2026-07-28 with stable `2026-07-28` support and serves earlier revisions from the same server; `FastMCP` renamed `MCPServer` | [Releases](https://github.com/modelcontextprotocol/python-sdk/releases); [What's new in v2](https://py.sdk.modelcontextprotocol.io/whats-new/): *"the same `streamable_http_app()` answers a 2025-era client's `initialize` and a 2026-era client's requests with nothing to configure"* |
| Client adoption lags the spec | Claude's own 2026-07-28 post says only *"Support is being rolled out across Claude products soon"* — no dates |
| Elicitation active but treat as enhancement, never load-bearing; always return an `ambiguous` array | Elicitation absent from the deprecated registry; MRTR reshaping confirmed |

### Weakened or needing a caveat

1. **"[SDK v2] ships provisional middleware (rate limiting/access control)."** — **Weakened.** The official SDK v2 middleware story is real but thinner than that reads. `py.sdk.modelcontextprotocol.io/whats-new/` describes middleware as *partially* added, with **OpenTelemetry tracing the middleware that ships enabled by default**, and explicitly lists code-execution sandboxing and **rate-limiting middleware** as *not covered*. Practical consequence: **plan to write the rate limiter ourselves** (or terminate it at the edge on `Mcp-Name`, per §1.4). Do not budget on the SDK providing it. *(Confidence: high on "not shipped by default"; medium on "no rate-limit middleware exists anywhere in the package" — I read the release notes and the what's-new page, not the full API reference.)*

2. **"an Authorization Server Hangar Bay operates or rents (AuthKit/Auth0/Stytch/Descope)"** — **Incomplete, not wrong.** The spec permits the AS to be *"hosted with the resource server"*, so self-hosting a minimal AS in the FastAPI app is a third option the prior doc did not list. It does not change the verdict (still a milestone), but the framing "you must go buy an IdP" is stronger than the spec requires.

3. **"`ttlMs` + `cacheScope` are now REQUIRED on list/read/discover results"** — **Precise scope worth pinning.** Required on `tools/list`, `prompts/list`, `resources/list`, `resources/read`, `resources/templates/list`. **Not** on `tools/call`. The prior doc's phrasing could be read as covering tool results, which would be wrong — and it matters, because it means MCP gives us no protocol-level channel for result freshness. Our own `data_as_of` payload fields remain the only mechanism.

4. **"Dynamic Client Registration is now *deprecated*" (§4c, listed among the costs)** — **Confirmed but mis-signed.** It is listed alongside PKCE/discovery/RFC 9207 as part of the burden. It is actually the one item on that list that got *cheaper*: CIMD removes the `/register` endpoint and the client store entirely (§1.3). The new cost is SSRF exposure on metadata fetch.

### Confirmed with new supporting detail worth carrying forward

5. **Origin validation.** The prior doc's hosting section flagged the SDK's transport-security/`421 Misdirected Request` trap. The spec-level requirement behind it is stricter than "configure a hostname": servers **MUST** validate `Origin` and **MUST** return `403` on a present-and-invalid one. Worth a `docs/pitfalls/` entry when this is built, next to PROXY-1.

6. **`Mcp-Name` header (new in this revision) is the missing piece of §4a's rate-limiting design.** Per-tool rate limiting is now enforceable at the edge without body parsing. The prior doc proposed per-tool limits without a mechanism; this is the mechanism.

7. **`ext-auth` / Enterprise-Managed Authorization did not exist in the prior doc's frame at all.** It is new official surface (stable, 2026-07-28, SEP-990). It changes nothing for us — see §1.3 point 2 — but "we looked and it doesn't help" is worth recording so a future session doesn't re-derive it.

### Nothing found that reverses a conclusion

To be explicit, because the prior doc was written days after a breaking revision and the natural expectation is that something rotted: **no conclusion in `2026-08-01-mcp-surface-research.md` on protocol state, authorization, hosting, or tool-surface shape was found to be wrong.** The four items above are refinements, not reversals. This is a "confirmed" report, and it should not be dressed up as anything more eventful.

---

## Q2 — Tool-based MCP vs. code mode, for Hangar Bay

### 2.1 What code mode is, and what the published evidence actually says

**Primary source, verified first-hand:** Anthropic, [*Code execution with MCP: building more efficient agents*](https://www.anthropic.com/engineering/code-execution-with-mcp), **published 2025-11-04**.

The mechanism: instead of presenting many tool definitions in-context and passing every intermediate result through the model, the MCP servers' tools are projected as a **filesystem of typed modules** (e.g. `servers/google-drive/getDocument.ts`). The model explores that tree on demand and **writes code** that imports only what it needs. Data is filtered, joined, and reduced *inside the execution environment*; only the final small result enters context.

The headline number, quoted verbatim: *"This reduces the token usage from 150,000 tokens to 2,000 tokens—a time and cost saving of 98.7%."*

**What that number is measuring matters more than its size.** The worked example spans **two large third-party connectors** (Google Drive and Salesforce), and the 150,000 tokens are dominated by (a) loading *all* tool definitions for those connectors up front and (b) round-tripping a **full document transcript** through the model twice — once as a tool result, once as a tool argument. Both are properties of *many tools across multiple servers with large intermediate payloads*. Neither describes a single server with seven tools returning ten rows.

Benefits Anthropic claims: progressive tool disclosure, context-efficient filtering of large result sets, real control flow (loops/conditionals/error handling), privacy-preserving intermediate data (including automatic PII tokenisation), state persistence via the filesystem, and reusable saved functions ("skills").

The cost, quoted verbatim: *"Code execution introduces its own complexity. Running agent-generated code requires a secure execution environment with appropriate sandboxing, resource limits, and monitoring."* The post explicitly frames this as something to weigh against implementation cost.

**The other flagship implementation, verified first-hand:** Cloudflare, [*Code Mode: the better way to use MCP*](https://blog.cloudflare.com/code-mode/), **published 2025-09-26** (Kenton Varda, Sunil Pai). Same idea, different substrate: MCP tools are converted into a **TypeScript API**, the LLM writes TypeScript against it, and that code runs in a **V8 isolate on Cloudflare Workers with no internet access** — its *only* external reach is RPC bindings that proxy back to an agent supervisor which holds the credentials. Two things are worth recording precisely, because both cut against adopting the pattern casually:

- **Cloudflare publishes no numbers.** They argue qualitatively that agents can "handle many more tools, and more complex tools", and that chaining wastes tokens because "the output of each tool call must feed into the LLM's neural network, just to be copied over to the inputs of the next call". There is no benchmark, no token figure, no accuracy measurement in the post.
- **It is platform-specific, and the enabling primitive was not generally available.** The Dynamic Worker Loader API the design depends on was in **closed beta** for production use at publication (local development only otherwise). Whether it has since gone GA is **unverified**.

The credential architecture is the genuinely instructive part: the sandbox never holds credentials, and the supervisor mediates every outbound call. Any Hangar Bay code-mode design would have to reproduce that property, and §2.4 is about what it would cost us to do so.

**Spec status of code mode: there isn't any.** Verified by reading the [extensions overview](https://modelcontextprotocol.io/docs/extensions/overview) and the [2026-07-28 changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog) in full. The official extension set is exactly three things — **OAuth Client Credentials** (draft), **Enterprise-Managed Authorization** (stable), **MCP Apps** (UI), **MCP Tasks** (async) — and none of them is code execution. The `2026-07-28` core protocol has no code-execution, sandbox, or script primitive. The Python SDK v2 "What's new" page lists code-execution sandboxing under **not covered**. So code mode in 2026 is a **client-side and vendor-side pattern layered on ordinary MCP tools**, not a protocol feature. Anything we built would be a bespoke `execute_query`-style tool of our own invention, with the sandbox entirely our problem.

**Third-party benchmark evidence: none found that bears on our case.** Neither flagship post publishes a controlled comparison. Anthropic's figure is a single worked example, not a benchmark; Cloudflare publishes no figure at all. The curation evidence the prior doc assembled (Copilot 40→13 tools, a 107-tool cliff-edge experiment, the AutoMCP survey finding hand-written servers expose a median 19% of available operations) argues for *fewer, better tools* — which is the recommendation here — and says nothing about code mode versus a seven-tool surface. **A controlled tool-mode-vs-code-mode comparison at small tool counts appears not to exist in public;** if one does, this spike did not find it, and that absence is itself the honest finding rather than a gap to paper over.

### 2.2 Hangar Bay's actual numbers (measured, 2026-08-01, against live production)

All measurements taken from `https://hangarbay.app/api/v1/contracts/` on 2026-08-01. Sample: **500 contract rows** drawn from 10 pages spread across the corpus (pages 2, 11, 37, 64, 89, 150, 222, 401, 555, 660 at `size=50`). Corpus total at measurement time: **33,872 contracts**. Token figures use the rough **≈4 characters per token** heuristic — JSON typically tokenises somewhat worse than that, so treat these as optimistic by perhaps 10–20%.

**Row sizes:**

| Shape | Mean | Median | p95 | Max |
|---|---|---|---|---|
| Current REST row (full `items` eager-loaded) | **1,232 B** | 765 B | 1,990 B | **55,699 B** |
| Proposed `concise` MCP projection (no `items`; `item_count` + 3 `headline_items`) | **432 B** | 426 B | 492 B | 538 B |

Items per contract: mean 3.09, median 1, p95 7, **max 244**.

**Result-payload token cost:**

| Rows returned | Full REST shape | `concise` MCP shape |
|---|---|---|
| 5 | ~1,540 tok | **~540 tok** |
| 10 | ~3,080 tok | **~1,080 tok** |
| 25 | ~7,700 tok | ~2,700 tok |
| 50 | ~15,400 tok | ~5,400 tok |
| **Entire corpus (33,872)** | ~10.4 M tok | ~3.7 M tok |

**Tool-definition cost:** the proposed `hangarbay_search_contracts` definition in the prior doc is 1,482 characters ≈ **~370 tokens** as written; a real definition with per-parameter descriptions is plausibly 2–3× that. Estimating the workhorse at ~800–1,100 tokens and six smaller tools at ~200–500 each gives a **whole-surface budget of roughly 2,500–4,000 tokens.** For calibration, the prior doc's cited figure for a 53-tool endpoint mirror is 15,000–25,000 definition tokens.

**Read those two numbers next to each other.** Code mode's primary lever is *not paying for tool definitions you don't use*. Our entire seven-tool surface costs about what **two to four `concise` search results** cost. There is no definition-token problem. The corpus is large; the *answers* are not — and the answers are all the model ever sees, because filtering happens in PostgreSQL either way.

**The variance number is the one that actually deserves attention:** max full row = **55,699 bytes**, from a single contract with 244 items. That is ~14,000 tokens in one row — over half of the 25,000-token Claude Code MCP output cap the prior doc reports (that cap figure is second-hand and was not re-verified here) from a *single* result. This is a real hazard, and it is an argument for the `concise` projection and a hard server-side cap. It is **not** an argument for code mode: code mode would have the model write code that fetches that row into a sandbox and summarises it, when the correct fix is for the server to never emit it.

### 2.3 Does composition actually need code execution here?

Tested the two exemplar queries empirically against live production.

**"Find me a cheap fitted Ishtar near Jita."** `search=Ishtar&sort_by=price&sort_direction=asc&size=5` returns 31 total matches in ~150 ms. The top five by price:

| Price | Item count | Location |
|---|---|---|
| 0 ISK | **244** | Jita IV - Moon 4 |
| 0 ISK | 11 | Jita IV - Moon 4 |
| 1,000,000 ISK | **143** | Jita IV - Moon 4 |
| 7,649,999 ISK | 1 | Jita IV - Moon 4 |
| 7,654,000 ISK | 1 | Jita IV - Moon 4 |

Every one of these is wrong for the query. The 0-ISK and 1M-ISK hits are bulk junk contracts that happen to *contain* an Ishtar among 244 items; the 7.6M hits are single items that are not a fitted ship. **This is a relevance and domain-ranking failure, not a token-volume failure.** No amount of model-written code fixes it, because the code would be operating on the same badly-ranked candidate set. What fixes it is server-side ranking that knows what "fitted" means in EVE (hull + modules in one contract, priced within a sane band of hull value). That work lands in `services/`, identically, under either shape. **The hard part of Hangar Bay's MCP surface is domain semantics, and code mode contributes nothing to it.**

**"What BPCs with ME 10 are under 50M?"** Verified live: `min_me=10&max_price=50000000&search=Blueprint` returns **15,592** — *identical* to the same query without `min_me`. The parameter is accepted and silently ignored (FASTAPI-2). Separately, `min_runs=5` returns **0** rows, because it filters `ContractItem.raw_quantity`, which is NULL for every row under public ingestion (ESI-3). **This query is unanswerable today under any surface shape**, because ME/TE are not in the database and runs are not ingested from the public route. Code mode would let a model write a beautifully composed query against columns that hold nothing — and, worse, an inert filter returning 15,592 rows *looks like a successful answer*. This is the freshness/honesty hazard in its sharpest form, and it argues for a surface where the *server* controls which filters exist and what an empty or inert result is allowed to say.

**Where composition genuinely would help,** and honestly: cross-cutting analysis over many result sets — "chart Gila BPC price distribution by station over the last week", the P3 market-analysis persona. That is exactly what `hangarbay_market_summary` (prior doc §3d) exists for. One aggregate tool that does `GROUP BY` in PostgreSQL beats both a code sandbox and fifty rows the model averages by hand. Aggregation belongs in the database, not in a sandbox that has to pull the rows out first.

### 2.4 Security posture of executing model-written code against our API

Concrete, for our actual deployment. Production today (`render.yaml`) is **one** Render web service, `runtime: docker`, `plan: starter`, `region: ohio`, pinned to a **single instance** by a 1 GB `scheduler-pin` disk (the APScheduler singleton constraint), plus one Postgres and one Key Value store. There is no second compute tier, no isolate host, no job runner.

Adding a code-execution surface means choosing one of:

| Option | Isolation boundary | Fit with our deployment | Cost/complexity |
|---|---|---|---|
| In-process Python `exec` with an allowlist | **None that holds.** CPython sandboxing is a well-known dead end | Trivially "fits" | Unacceptable. A code-exec RCE inside the process holding `DATABASE_URL`, `TOKEN_CIPHER_KEYS`, and the ESI client credentials |
| Pyodide / WASM in-process | WASM linear memory; no host FS or sockets by default | Runs inside the API container | Real but slow to start; must re-expose our API *into* the sandbox, which reintroduces the whole authorization question at a second boundary; memory pressure on a starter instance |
| Separate Render service running a Deno/Node isolate | OS process + separate service | New service, new deploy, new secret boundary | Doubles the deployable surface; Deno permissions are the actual security control and must be got exactly right |
| Cloudflare Workers isolates / Dynamic Worker Loader (their "Code Mode" substrate) | V8 isolate per execution, no internet, RPC bindings only; vendor-operated | **Poor** — we are a Python FastAPI app on Render. Adopting it means standing up a second platform, and the loader API was in closed beta as of 2025-09-26 (current status unverified) | New vendor, new deploy pipeline, cross-cloud latency to our Postgres, and the model would write **TypeScript** against a Python service |
| gVisor / Firecracker microVM | Kernel-level | Not available on Render's managed platform | Would require leaving Render for the exec tier |
| Hosted sandbox vendor (E2B, Modal, etc.) | Vendor microVM/container | Bolt-on | New vendor, new billing, per-execution latency, and our data leaves our perimeter |

Every row is a material increase in attack surface and operating cost, in service of a token saving that §2.2 shows is roughly zero for us.

There is also a **licence-shaped** problem that is specific to this project and does not appear in any vendor's code-mode writeup. The [EVE Developer License Agreement](https://developers.eveonline.com/license-agreement) forbids charging for access (§4.1), so **every sandbox CPU-second is unrecoverable cost** — there is no paid tier to put it behind. And an execution surface is the most abusable endpoint imaginable for a service that today has **no API rate limiting at all** (prior doc §4a, still true). A tool surface has a bounded per-call cost we can weight and price into a token bucket; `execute(code)` has an unbounded one. Read together with the prior doc's Risk 1 ("becoming a free backend"), code mode converts a bandwidth problem into a compute problem, which is strictly worse under a licence that forbids monetisation.

### 2.5 Trade-off comparison

| Dimension | Discrete tools (~7, hand-written) | Code mode (`execute` + typed API) | Hybrid (tools + one query/aggregate tool) |
|---|---|---|---|
| Tool-definition tokens | **~2,500–4,000** (est.) | ~500–1,500 (small execution surface + docs the model must still read) | ~3,000–4,500 |
| Typical answer payload (5 rows, measured) | **~540 tok** | ~540 tok — *identical*, same rows come back | ~540 tok |
| Worst-case single result (measured) | Server-capped by projection | Sandbox can pull the 55.7 KB row and anything else | Server-capped |
| Composition / multi-step filtering | Weak by design; each call is one question | **Strong** — real control flow | Aggregation in SQL covers the realistic cases |
| Domain relevance ("fitted Ishtar") | Server-side ranking; the hard work, done once, benefits everyone | **No help** — same bad candidate set, now ranked by a model guessing | Same as tools |
| Freshness / honesty enforcement | **Strong.** Server controls every field; `data_as_of`/`data_stale`/`coverage` in every payload; no filter exists unless it works | **Weak.** Model composes its own output shape; freshness fields are trivially dropped en route to prose; inert columns look like real answers | Strong, if the aggregate tool stamps the same envelope |
| Attack surface | Ordinary parameterised API | **Largest single addition in the project's history** — arbitrary code near DB creds and ESI creds | Ordinary API |
| New infrastructure | None (mount in the existing FastAPI app) | A sandbox tier: new service or new vendor | None |
| Abuse cost profile | Bounded per call; weightable token bucket | Unbounded CPU per call; unrecoverable under the EVE licence (§4.1 forbids charging) | Bounded; aggregates weighted higher |
| Protocol support | First-class; **the only primitive with universal client support** | **No spec support at all** in `2026-07-28`; vendor/client pattern only | First-class |
| Cost to rebuild on a future breaking revision | ~7 hand-written tools ≈ a week (prior doc §Risk 3) | Tools *plus* a sandbox contract | ~8 tools |

### 2.6 Hybrid shapes considered, and why they still lose

The brief asked not to force a binary. Three hybrids were considered:

- **Tools + a read-only SQL tool (`query_contracts(sql)`).** Superficially attractive — PostgreSQL already does the filtering. Rejected: it is a catch-all passthrough, which the prior doc records as an explicit **Anthropic connector-review rejection criterion**; it welds our internal schema to a public contract (renaming a column becomes a breaking change for every agent); and it exports the FASTAPI-2/ESI-3 trap wholesale — a model would write `WHERE me >= 10` against a column that does not exist, or `raw_quantity >= 5` against one that is always NULL, and get a plausible-looking answer either way. A read-only role and statement timeouts mitigate the *security* risk but none of the *honesty* risk.
- **Tools + a sandbox for the analysis persona only (P3).** Rejected on cost/benefit: P3 is explicitly the smallest persona (~20% of value at most, prior doc §2) and the *most likely to abuse the endpoint*. Buying a sandbox tier for it inverts the priority order. `hangarbay_market_summary` serves it at a fraction of the cost.
- **Tools now, code mode later behind a flag.** This is not really a hybrid — it is the recommended path stated as a sequence, and it is fine. The point is that nothing about a well-designed tool surface forecloses adding an execution surface later. The typed projection the tools return *is* the typed API a code-mode surface would expose. Building tools first is therefore not a bet against code mode; it is the prerequisite for doing code mode well if it ever earns its way in.

### 2.7 Recommendation, and what would change it

**Recommendation: discrete hand-written tools, as designed in `2026-08-01-mcp-surface-research.md` §3. Do not build a code-execution surface for v1, and do not reserve design space for one.**

**The deciding reason, in one sentence:** code mode buys context-window efficiency, and Hangar Bay does not have a context-window problem — it has a *domain-semantics* problem (ranking "fitted Ishtar" correctly) and an *honesty* problem (never laundering stale, inert, or partially-valued data into confident prose), and code mode makes the second one strictly worse while contributing nothing to the first.

The honesty point is worth stating on its own, because it is the project's stated hard requirement. Under a tool surface, the server decides what every field is called and guarantees `data_as_of`, `data_stale`, and `coverage` ride on every payload — the prior doc's §4b discipline, including the crucial detail that staleness must escalate *in text* ("⚠ Data is 3.6 days old") because a boolean gets summarised away. Under code mode, the model composes the output shape; every one of those guarantees becomes advisory. A surface whose central risk is confident prose over uncertain data should not hand the prose-shaping step to the model.

**What would change this answer:**

1. **Result sizes grow by an order of magnitude.** If coverage expands to all of New Eden and the natural answer becomes hundreds of rows rather than five to ten, the arithmetic in §2.2 shifts. Trigger: a realistic single answer routinely exceeding ~10,000 tokens.
2. **The tool count passes ~20–30.** The prior doc reports (second-hand, not re-verified here) that Anthropic's docs put tool-selection degradation at 30–50 tools. We are at 7. If a future surface genuinely needs 25+, progressive disclosure starts paying for itself.
3. **Code execution becomes a spec feature with SDK support.** Today it is neither (§2.1). If a SEP lands an official execution extension with a reference implementation in the Python SDK, the sandbox stops being wholly our problem and the cost column changes materially.
4. **A managed sandbox becomes free-at-our-scale and inside our perimeter** — e.g. Render ships a first-party isolate primitive that runs in our existing service with our existing secrets *not* reachable. Unlikely; but it is the specific thing that would collapse the §2.4 cost column.
5. **A genuine multi-server composition use case appears.** Code mode's flagship number is a *cross-connector* number. If Hangar Bay's value became "join our contracts against three other EVE data services in one step", the calculus changes. Today the prior doc's §1d finding cuts the other way: we are the only party holding this index, so there is nothing to join against.
6. **Contrary evidence emerges that tool-mode accuracy is materially worse at small tool counts.** The curation evidence the prior doc collected (Copilot 40→13 tools, a 107-tool cliff-edge experiment — both second-hand, not re-verified here) is all at *large* tool counts. If someone publishes a controlled result showing code mode wins at *seven* tools, that would be new information.

**Sequencing is unchanged from the prior doc and this spike found no reason to move it:** the MCP surface — of any shape — stays downstream of M5's trust work (dead-contract filtering, freshness envelope, retiring the always-`"unknown"` status field) and coverage expansion. This spike, if anything, hardens that: the live probes in §2.3 show two filter parameters that today return confidently wrong or vacuously empty answers, and an agent surface makes both louder.

---

## What I verified vs. what I inferred

### Verified first-hand against primary sources (all fetched 2026-08-01)

- Current revision is `2026-07-28`; no newer revision; draft changelog empty — modelcontextprotocol.io versioning + draft changelog.
- Every row of the §1.2 changelog table — the official 2026-07-28 changelog, read in full.
- Every normative authorization quote in §1.3 — the authorization spec page and its security-considerations page, read in full.
- CIMD mechanics and the CIMD/pre-registration/DCR priority order — the client-registration spec page.
- The official extension inventory (auth ×2, Apps, Tasks) and the absence of any code-execution extension — extensions overview page.
- Enterprise-Managed Authorization / ID-JAG flow and its requirement for an MCP Authorization Server — the extension's own page (SEP-990).
- Deprecated-features registry contents and earliest-removal dates; elicitation's **absence** from it.
- `ToolAnnotations` field list and `CallToolResult`'s lack of a cursor — read from `schema/2026-07-28/schema.json` (181 KB) directly.
- Streamable HTTP requirements: single POST endpoint, Origin-validation MUST, `Mcp-Method`/`Mcp-Name` required, `x-mcp-header`, no resumability, `405` guidance for legacy GET/DELETE.
- Python SDK v2.0.0 release date and backward-compatibility claim; the "not covered: rate-limiting middleware / code-execution sandboxing" statement on the official what's-new page.
- Claude's 2026-07-28 post saying only "rolling out … soon", with no dates.
- Anthropic's code-execution-with-MCP post: publication date 2025-11-04, the 150,000 → 2,000 token figure, and the sandboxing caveat — quoted verbatim from the post itself.
- Cloudflare's Code Mode post: publication date 2025-09-26, authors, the V8-isolate/no-internet/RPC-bindings architecture, the **absence** of any published token or accuracy number, and the closed-beta status of the Dynamic Worker Loader at that date.
- **All Hangar Bay measurements in §2.2 and §2.3** — 500 sampled rows and the two exemplar queries, run against live production on 2026-08-01. `min_me` proved inert (15,592 with and without); `min_runs=5` proved empty (0 rows).
- Production deployment shape — `render.yaml` in this worktree.

### Inferred, estimated, or second-hand — treat accordingly

- **Token counts.** All token figures are byte-counts ÷ 4. That heuristic under-counts JSON. Directionally safe (the gap between 540 and 15,000 tokens is not a rounding question), but do not quote these as measured token counts.
- **Tool-definition budget (~2,500–4,000 tokens for seven tools).** An estimate extrapolated from the 1,482-character draft definition in the prior doc, not a measurement of a real `tools/list` response. The comparison to a 53-tool mirror at 15,000–25,000 tokens is the prior doc's figure, itself second-hand.
- **"No rate-limiting middleware in SDK v2."** Based on the release notes and the official what's-new page, which list it under "not covered". I did not read the full v2 API reference. High confidence it is not on by default; medium confidence nothing of the sort exists anywhere in the package.
- **Sandbox comparison table (§2.4).** Isolation-boundary characterisations are from general knowledge of these technologies plus a parallel research lane; I did not benchmark or price any of them. The *conclusion* (any of them is a large addition to a single-instance Render deployment) is robust to the details being imprecise; the individual rows are not authoritative.
- **Whether clients actually consume `structuredContent`.** Still the unmeasured uncertainty the prior doc flagged. The spec's own guidance ("SHOULD also return the serialized JSON in a TextContent block") is unchanged; the operational rule stands unverified by fresh evidence this session.
- **Corpus statistics** are a 500-row sample of 33,872, not a census. The 244-item / 55.7 KB maximum is a sample maximum; the true corpus maximum is at least that and probably larger.
- **Real-world code-mode server shapes.** The prior doc's claims that Massive.com (ex-Polygon.io) rebuilt to 3 tools (`search_endpoints`, `call_api`, `query_data`) and that CoinGecko went to 2 tools in code-execution mode were **not re-verified in this spike**. They do not affect the recommendation — if anything a verified "thin 3-tool passthrough" precedent is an argument to engage with, and §2.6 rejects that shape on honesty grounds independent of whether those vendors shipped it.
- **The "fitted Ishtar" relevance finding** is one query at one moment. The failure mode (bulk contracts outranking real ones on price) is structural and will reproduce, but the specific rows will not.

---

## Open questions and risks

1. **Client support is the real gating date, not the spec.** Claude's own announcement gives no timeline for 2026-07-28 support. Since SDK v2 serves every earlier revision from the same server, this is not blocking — but it means we cannot verify our server against a 2026-07-28 Claude client yet. **Do not write "Claude supports revision X" into any artifact without re-checking on the day.**
2. **Origin validation + PROXY-1 is an unresolved edge decision.** The MUST-validate-Origin requirement lands on top of a deployment where `/api/v1` is owned by the Render rewrite and FastAPI mounts bare. If MCP goes on `mcp.hangarbay.app` (which also gives a clean RFC 8707 canonical resource URI and a separate rate-limit domain), the allowed-Origin set has to be decided in both places. Worth a pitfalls entry when built.
3. **The single-instance pin.** `render.yaml` pins one instance via the `scheduler-pin` disk for APScheduler. MCP is now a stateless protocol that would happily scale horizontally, and won't be able to. Not a problem at current traffic; a known ceiling.
4. **Rate limiting remains entirely unbuilt, and the spec makes it a MUST.** The SDK will not provide it. `Mcp-Name` makes edge enforcement newly possible; whether Render's rewrite layer can act on it is unverified.
5. **`min_me`/`max_me`/`min_te`/`max_te` and `min_runs`/`max_runs` are live in production returning confidently wrong results** (verified this session: 15,592 rows for an inert ME filter). These are documented as inert in `schemas/contracts.py` and hidden from the frontend, but they are *served*. Before any MCP surface exists, decide whether they are fixed, removed, or hard-errored — an agent will find them and an agent has no `docs/pitfalls/` to read.
6. **The 55.7 KB single-row hazard needs a server-side cap**, decided before the tool surface is designed, not after a client truncates a result mid-JSON.
7. **CIMD's SSRF exposure** would be ours to handle if we ever run an AS. Noted for the day that becomes real; irrelevant to a public read-only v1.
8. **This spike did not re-verify the prior doc's non-protocol lanes** — prior-art/registry statistics, the EVE Developer License analysis, or the ESI operational-limit figures. Those remain as that document reports them, with its own flagged uncertainties.
