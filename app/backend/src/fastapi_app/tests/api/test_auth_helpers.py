# ABOUTME: Unit coverage for the return-path next validator and the query-merge builder.
# ABOUTME: Pure-function tests — no app or fixtures; redirect targets can never leave FRONTEND_ORIGIN.
import pytest

from fastapi_app.api.auth import build_redirect, validate_next


@pytest.mark.parametrize("bad", ["//evil.com", "/\\evil.com", "https://evil.com", "javascript:alert(1)", "", None, "garbage"])
def test_validate_next_rejects_dangerous_values(bad):
    assert validate_next(bad) == "/"


@pytest.mark.parametrize("ok", ["/", "/contracts", "/contracts?type=bpc&page=2"])
def test_validate_next_accepts_safe_paths(ok):
    assert validate_next(ok) == ok


def test_build_redirect_merges_query_without_double_question_mark():
    out = build_redirect("https://localhost:5173", "/contracts?type=bpc&page=2", flag="denied")
    assert out == "https://localhost:5173/contracts?type=bpc&page=2&sso=denied"


def test_build_redirect_adds_first_query_param():
    out = build_redirect("https://localhost:5173", "/contracts", flag="error")
    assert out == "https://localhost:5173/contracts?sso=error"


def test_build_redirect_success_has_no_flag():
    out = build_redirect("https://localhost:5173", "/contracts?page=2", flag=None)
    assert out == "https://localhost:5173/contracts?page=2"


def test_build_redirect_cannot_yield_protocol_relative_location():
    # next was already validated to "/", so the Location stays under FRONTEND_ORIGIN.
    out = build_redirect("https://localhost:5173", validate_next("//evil.com"), flag="error")
    assert out == "https://localhost:5173/?sso=error"


def test_build_redirect_strips_existing_sso_param_before_appending_its_own():
    # Finding 8d: a retry landing back on e.g. /contracts?sso=error must not
    # accumulate a second sso param — URLSearchParams.get('sso') on the frontend
    # reads only the FIRST value, so a stale one would silently win over the
    # freshly-appended one.
    out = build_redirect("https://localhost:5173", "/contracts?sso=error", flag="denied")
    assert out == "https://localhost:5173/contracts?sso=denied"


def test_build_redirect_strips_existing_sso_param_with_no_new_flag():
    out = build_redirect("https://localhost:5173", "/contracts?sso=error", flag=None)
    assert out == "https://localhost:5173/contracts"


def test_build_redirect_strips_existing_sso_param_among_other_params():
    out = build_redirect("https://localhost:5173", "/contracts?sso=error&type=bpc", flag="denied")
    assert out == "https://localhost:5173/contracts?type=bpc&sso=denied"
