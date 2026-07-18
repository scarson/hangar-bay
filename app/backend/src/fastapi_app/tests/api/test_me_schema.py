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


def test_login_and_callback_declare_302_not_200():
    # Finding 10: login/callback always redirect — they never return 200
    # application/json — so the generated OpenAPI schema (and the typed
    # frontend client built from it) must declare 302, not the FastAPI
    # default of 200, or callers mis-type the response shape.
    schema = app.openapi()
    login_responses = schema["paths"]["/auth/sso/login"]["get"]["responses"]
    callback_responses = schema["paths"]["/auth/sso/callback"]["get"]["responses"]
    assert "302" in login_responses and "200" not in login_responses
    assert "302" in callback_responses and "200" not in callback_responses


def test_me_response_schema_shape():
    schema = app.openapi()
    ref = schema["paths"]["/me"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    name = ref.rsplit("/", 1)[-1]
    props = schema["components"]["schemas"][name]["properties"]
    assert set(props) == {"character_id", "character_name"}
    assert props["character_id"]["type"] == "integer"
    assert props["character_name"]["type"] == "string"
