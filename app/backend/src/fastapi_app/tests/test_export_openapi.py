import json
import subprocess
import sys
from pathlib import Path

BACKEND_SRC = Path(__file__).resolve().parents[2]  # .../app/backend/src
SCRIPT = BACKEND_SRC / "export_openapi.py"


def test_export_openapi_writes_usable_schema(tmp_path):
    out = tmp_path / "openapi.json"

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(out)],
        capture_output=True, text=True, cwd=str(BACKEND_SRC),
    )

    assert result.returncode == 0, result.stderr
    schema = json.loads(out.read_text())
    assert "/contracts/" in schema["paths"]
    assert "/contracts/{contract_id}" in schema["paths"]

    list_op = schema["paths"]["/contracts/"]["get"]
    # Regression guard on Task 1: a requestBody here means the ID-list
    # filters regressed to GET-body binding (pitfall FASTAPI-1).
    assert "requestBody" not in list_op
    param_names = {p["name"] for p in list_op["parameters"]}
    assert {"region_ids", "system_ids", "station_ids", "type_ids"} <= param_names
    # The list envelope the TS client is generated from. It carries the page fields
    # plus unknown_system_excluded, the figure that makes the partial reach of
    # system_ids readable instead of silent; segment_counts, the per-type counts the
    # segment controls are labelled from; and coverage, the regions the corpus
    # actually holds, which is what stops the client embedding a region literal.
    envelope = schema["components"]["schemas"]["ContractListResponse"]
    assert {
        "total", "page", "size", "items", "unknown_system_excluded", "segment_counts",
        "coverage",
    } <= set(envelope["properties"])
    assert {"ingested_region_ids", "as_of"} <= set(
        schema["components"]["schemas"]["CoverageInfo"]["properties"]
    )

    # The row/detail split the generated TS client binds to. A row carries no item
    # array — `items` on the envelope is the page — and everything a client would
    # have derived by walking those items is a field on the row instead.
    row = schema["components"]["schemas"]["ContractListItemSchema"]
    assert "items" not in row["properties"]
    assert {
        "buyout", "days_to_complete", "reward_per_volume", "end_location_name",
        "last_seen_at", "is_blueprint_copy_contract", "primary_label",
        "composition", "blueprint_summary",
    } <= set(row["properties"])

    detail_op = schema["paths"]["/contracts/{contract_id}"]["get"]
    detail_ref = detail_op["responses"]["200"]["content"]["application/json"]["schema"]
    assert detail_ref["$ref"].endswith("/ContractDetailSchema")
    assert "items" in schema["components"]["schemas"]["ContractDetailSchema"]["properties"]
