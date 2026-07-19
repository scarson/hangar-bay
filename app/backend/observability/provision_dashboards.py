# ABOUTME: Provisions the committed dashboards under observability/dashboards/ to the
# ABOUTME: Grafana Cloud stack via POST /api/dashboards/db (service-account token auth).
import json
import sys
from pathlib import Path

import httpx
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]  # app/backend
DASHBOARD_DIR = Path(__file__).resolve().parent / "dashboards"


class ProvisionSettings(BaseSettings):
    """Stack URL + service-account token, from docker/grafana-cloud-provisioning.env or the environment."""

    GRAFANA_STACK_URL: str
    GRAFANA_SA_TOKEN: SecretStr

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / "docker" / "grafana-cloud-provisioning.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def main() -> int:
    settings = ProvisionSettings()
    dashboards = sorted(DASHBOARD_DIR.glob("*.json"))
    if not dashboards:
        print(f"no dashboard JSON found in {DASHBOARD_DIR}", file=sys.stderr)
        return 1

    base_url = settings.GRAFANA_STACK_URL.rstrip("/")
    failures = 0
    for path in dashboards:
        # One bad dashboard or a transient network error must not abort the
        # rest of the batch — report it, count it, keep provisioning.
        try:
            payload = {
                "dashboard": json.loads(path.read_text(encoding="utf-8")),
                "overwrite": True,
                "message": f"provisioned from repo ({path.name})",
            }
            response = httpx.post(
                f"{base_url}/api/dashboards/db",
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.GRAFANA_SA_TOKEN.get_secret_value()}"
                },
                timeout=30.0,
            )
        except (json.JSONDecodeError, OSError, httpx.HTTPError) as exc:
            failures += 1
            print(f"{path.name}: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        if response.status_code == 200:
            try:
                body = response.json()
            except json.JSONDecodeError:
                body = {}
            print(
                f"{path.name}: {body.get('status', 'ok')} -> {base_url}{body.get('url', '')}"
            )
        else:
            failures += 1
            print(
                f"{path.name}: HTTP {response.status_code}: {response.text[:300]}",
                file=sys.stderr,
            )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
