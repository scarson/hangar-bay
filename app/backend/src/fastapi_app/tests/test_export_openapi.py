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
    assert "PaginatedResponse_ContractSchema_" in schema["components"]["schemas"]
