import json
import os
import sys
import requests


def main():
    backend = os.getenv("BACKEND_URL", "http://localhost:5000").rstrip("/")
    token = os.getenv("TOKEN", "").strip()
    if not token:
        print("TOKEN env var is required.")
        return 2

    headers = {"Authorization": f"Bearer {token}"}

    def call(method, path, payload=None):
        url = backend + path
        resp = requests.request(method, url, headers=headers, json=payload, timeout=10)
        print(f"{method} {path} -> {resp.status_code}")
        try:
            data = resp.json()
        except Exception:
            print(resp.text[:400])
            return None
        print(json.dumps(data, indent=2)[:800])
        return data

    auth = call("GET", "/api/auth/check")
    if not auth or not auth.get("ok"):
        print("Auth check failed.")
        return 1

    settings = call("GET", "/api/me/settings")
    if not settings or not settings.get("ok"):
        print("Settings fetch failed.")
        return 1

    scheme_id = os.getenv("SCHEME_ID", "").strip() or settings.get("settings", {}).get("default_scheme_id", "")
    if not scheme_id:
        print("No scheme_id available (set SCHEME_ID env or set default_scheme_id).")
        return 1

    context = settings.get("settings", {}).get("default_context") or {"type": "ASM"}

    preview = call("POST", "/api/numbering/preview", {"scheme_id": scheme_id, "context": context})
    if not preview or not preview.get("ok"):
        print("Preview failed.")
        return 1

    allocate = call("POST", "/api/numbering/allocate", {
        "scheme_id": scheme_id,
        "context": context,
        "create_part_if_missing": False,
        "requested_revision_action": "new_part",
    })
    if not allocate or not allocate.get("ok"):
        print("Allocate failed.")
        return 1

    print("Smoke test completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
