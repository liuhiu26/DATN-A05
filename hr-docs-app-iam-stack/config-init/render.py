"""Bước khởi tạo chạy 1 lần trước Kong và OPA (service `config-init` trong docker-compose):

1. Chờ Keycloak nạp xong realm, lấy public key RS256 của realm  ->  kong/kong.yml (consumer JWT của Kong).
2. Ghi tham số ABAC (giờ làm việc, múi giờ, dải IP nội bộ) từ .env  ->  opa/data.json (data.hrdocs.config).

Chỉ dùng thư viện chuẩn của Python. Khi Keycloak đổi key (xóa container / reset realm), chạy lại:
    docker compose up -d --force-recreate config-init kong
"""
import json
import os
import sys
import textwrap
import time
import urllib.request
from pathlib import Path
from string import Template

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
REALM = os.getenv("KEYCLOAK_REALM", "hrdocs")
ISSUER = os.getenv("KEYCLOAK_ISSUER", f"http://localhost:8080/realms/{REALM}")
OUT = Path(os.getenv("OUT_DIR", "/out"))
TEMPLATE = Path(os.getenv("KONG_TEMPLATE", "/templates/kong.template.yml"))
CIDRS = [c.strip() for c in os.getenv("INTERNAL_CIDRS", "127.0.0.1/32,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16").split(",") if c.strip()]


def realm_public_key(timeout_s: int = 300) -> str:
    url = f"{KEYCLOAK_URL}/realms/{REALM}"
    deadline = time.time() + timeout_s
    while True:
        try:
            with urllib.request.urlopen(url, timeout=5) as res:
                return json.load(res)["public_key"]
        except Exception as exc:
            if time.time() > deadline:
                sys.exit(f"Keycloak realm {url} not reachable: {exc}")
            print(f"waiting for Keycloak realm {REALM}...", flush=True)
            time.sleep(3)


def main():
    key = realm_public_key()
    pem = "-----BEGIN PUBLIC KEY-----\n" + "\n".join(textwrap.wrap(key, 64)) + "\n-----END PUBLIC KEY-----"
    kong = Template(TEMPLATE.read_text(encoding="utf-8")).safe_substitute(
        KEYCLOAK_ISSUER=ISSUER,
        KEYCLOAK_PUBLIC_KEY=textwrap.indent(pem, " " * 10),
        INTERNAL_CIDRS_YAML=json.dumps(CIDRS),
    )
    (OUT / "kong").mkdir(parents=True, exist_ok=True)
    (OUT / "kong" / "kong.yml").write_text(kong, encoding="utf-8")

    data = {
        "hrdocs": {
            "config": {
                "internal_cidrs": CIDRS,
                "work_hours": {"start": os.getenv("WORK_HOURS_START", "08:00"), "end": os.getenv("WORK_HOURS_END", "18:00")},
                "timezone": os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh"),
            }
        }
    }
    (OUT / "opa").mkdir(parents=True, exist_ok=True)
    (OUT / "opa" / "data.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"rendered kong.yml (issuer {ISSUER}) and opa/data.json (internal_cidrs={CIDRS})", flush=True)


if __name__ == "__main__":
    main()
