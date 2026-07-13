# ABOUTME: Schema-level guard that /me and the SSO routes are mounted bare with the right shape (TEST-1).
# ABOUTME: PROXY-1 sentinel: no /api/v1 prefix may ever appear in the backend-owned OpenAPI paths.
from fastapi_app.main import app


def test_me_and_sso_routes_mounted_bare():
    schema = app.openapi()
    assert "/me" in schema["paths"]
    assert "/auth/sso/login" in schema["paths"]
    assert "/auth/sso/callback" in schema["paths"]
    assert "/auth/sso/logout" in schema["paths"]
    # PROXY-1: never an /api/v1 prefix on the backend
    assert not any(p.startswith("/api/v1") for p in schema["paths"])


def test_me_response_schema_shape():
    schema = app.openapi()
    ref = schema["paths"]["/me"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    name = ref.rsplit("/", 1)[-1]
    props = schema["components"]["schemas"][name]["properties"]
    assert set(props) == {"character_id", "character_name"}
    assert props["character_id"]["type"] == "integer"
    assert props["character_name"]["type"] == "string"
