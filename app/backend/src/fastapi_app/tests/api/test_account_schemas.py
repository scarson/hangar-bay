# ABOUTME: Unit tests for the SavedSearchParameters validation model + saved-search request/response schemas.
# ABOUTME: Pins extra="forbid" (ME/TE + junk rejection), constraint bounds, and name trimming.
import pytest
from pydantic import ValidationError

from fastapi_app.schemas.account import (
    SavedSearchCreate,
    SavedSearchParameters,
    SavedSearchUpdate,
    WatchlistItemCreate,
    WatchlistItemUpdate,
)

# inf (1e309 overflows to inf), NaN, and a magnitude over NUMERIC(20,2) / the 1e15 cap.
NON_FINITE_OR_OVERFLOW = [1e309, float("nan"), 1e20]
PRICE_BOUNDARY = 1_000_000_000_000_000  # 1e15 — accepted (le is inclusive)


def _build_with_price(model_field, value):
    """Construct each price-bearing model with `value` on its named float field."""
    model, field = model_field
    if model is WatchlistItemCreate:
        return WatchlistItemCreate(type_id=587, **{field: value})
    return model(**{field: value})


PRICE_FIELDS = [
    (SavedSearchParameters, "min_price"),
    (SavedSearchParameters, "max_price"),
    (WatchlistItemCreate, "max_price"),
    (WatchlistItemUpdate, "max_price"),
]


def test_parameters_defaults_materialize():
    p = SavedSearchParameters()
    assert p.ships_only is True
    assert p.size == 50
    assert p.sort_by.value == "date_issued"
    assert p.sort_direction.value == "desc"
    assert p.search is None and p.region_ids is None


def test_parameters_accepts_valid_payload():
    p = SavedSearchParameters(search="frigate", max_price=5_000_000, region_ids=[10000002], is_bpc=False)
    assert p.search == "frigate"
    assert p.region_ids == [10000002]


@pytest.mark.parametrize("bad", [
    {"search": "ab"},          # min_length 3
    {"min_price": -1},         # ge 0
    {"max_price": -0.01},      # ge 0
    {"region_ids": [0]},       # positive ints only
    {"size": 0},               # ge 1
    {"size": 101},             # le 100
    {"min_me": 5},             # extra="forbid" — inert ME param rejected (FASTAPI-2)
    {"page": 2},               # extra="forbid" — page is per-view, not a saved property
    {"is_ship_contract": True},  # extra="forbid" — the blob uses ships_only, not the wire name
])
def test_parameters_reject_invalid(bad):
    with pytest.raises(ValidationError):
        SavedSearchParameters(**bad)


def test_create_trims_name_and_rejects_blank():
    c = SavedSearchCreate(name="  Cheap frigs  ", search_parameters={})
    assert c.name == "Cheap frigs"
    with pytest.raises(ValidationError):
        SavedSearchCreate(name="   ", search_parameters={})
    with pytest.raises(ValidationError):
        SavedSearchCreate(search_parameters={})  # name required


def test_update_requires_and_trims_name():
    u = SavedSearchUpdate(name="  Renamed ")
    assert u.name == "Renamed"
    with pytest.raises(ValidationError):
        SavedSearchUpdate(name="")


# ---------- price fields: reject non-finite / storage-overflow, accept the boundary ----------

@pytest.mark.parametrize("model_field", PRICE_FIELDS)
@pytest.mark.parametrize("bad", NON_FINITE_OR_OVERFLOW)
def test_price_fields_reject_non_finite_and_overflow(model_field, bad):
    with pytest.raises(ValidationError):
        _build_with_price(model_field, bad)


@pytest.mark.parametrize("model_field", PRICE_FIELDS)
def test_price_fields_accept_1e15_boundary(model_field):
    _, field = model_field
    built = _build_with_price(model_field, PRICE_BOUNDARY)
    assert getattr(built, field) == PRICE_BOUNDARY
