#!/usr/bin/env python3
"""Upload the Engram MCP worker bundle via Cloudflare v4 API with full bindings.

Bindings: D1(DB) R2(CONTENT) Vectorize(VECTORIZE) AI(AI) service(SELF)
          Durable Object DRAINER/DrainerDO. Vars: APP_URL.
"""
import json
import sys
import urllib.parse
import urllib.request
import uuid

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
import dynamic_credentials as dc

BASE = "https://api.cloudflare.com/client/v4"
ALLOWED = ["api.cloudflare.com"]
ACCOUNT = "f6283a853b7a54eae1f8810779bbe93b"
NAME = "engram-mcp-server"
D1_ID = "e364e375-99cb-4e2d-9385-fdc403302bcd"


def api(method, path, body=None):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    dc.add_surrogate_to_request(req, "custom.cloudflare", entry_name="access_token",
                                allowed_hosts=ALLOWED)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return dc.read_json_response(resp)


def main():
    script_path = sys.argv[1] if len(sys.argv) > 1 else "dist/index.js"
    with open(script_path, "r", encoding="utf-8") as f:
        script = f.read()

    metadata = {
        "main_module": "index.js",
        "compatibility_date": "2024-12-01",
        "compatibility_flags": ["nodejs_compat"],
        "bindings": [
            {"type": "plain_text", "name": "APP_URL",
             "text": "https://engram-mcp-server.me3442.workers.dev"},
            {"type": "d1", "name": "DB", "id": D1_ID},
            {"type": "r2_bucket", "name": "CONTENT", "bucket_name": "engram-content"},
            {"type": "vectorize", "name": "VECTORIZE", "index_name": "engram-vectors"},
            {"type": "ai", "name": "AI"},
            {"type": "service", "name": "SELF", "service": NAME},
            {"type": "durable_object_namespace", "name": "DRAINER",
             "class_name": "DrainerDO"},
        ],
    }

    boundary = "----engram" + uuid.uuid4().hex
    body = b""
    body += f"--{boundary}\r\n".encode()
    body += b'Content-Disposition: form-data; name="metadata"\r\n'
    body += b"Content-Type: application/json\r\n\r\n"
    body += json.dumps(metadata).encode() + b"\r\n"
    body += f"--{boundary}\r\n".encode()
    body += b'Content-Disposition: form-data; name="index.js"; filename="index.js"\r\n'
    body += b"Content-Type: application/javascript+module\r\n\r\n"
    body += script.encode() + b"\r\n"
    body += f"--{boundary}--\r\n".encode()

    url = (f"{BASE}/accounts/{ACCOUNT}/workers/scripts/"
           f"{urllib.parse.quote(NAME, safe='')}")
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="PUT",
    )
    dc.add_surrogate_to_request(req, "custom.cloudflare", entry_name="access_token",
                                allowed_hosts=ALLOWED)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = dc.read_json_response(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        print(f"deploy failed {exc.code}: {body[:2000]}")
        raise SystemExit(1)
    if not payload.get("success"):
        raise SystemExit(f"deploy failed: {json.dumps(payload.get('errors'))[:1500]}")
    print("upload ok:", payload["result"].get("modified_on"))

    # enable workers.dev
    r = api("POST", f"/accounts/{ACCOUNT}/workers/scripts/{NAME}/subdomain",
            {"enabled": True})
    print("subdomain:", r.get("success"))

    # crons
    r = api("PUT", f"/accounts/{ACCOUNT}/workers/scripts/{NAME}/schedules",
            {"schedules": [{"cron": c} for c in
                            ["*/10 * * * *", "0 3 * * *", "0 13 * * *"]]})
    print("schedules:", r.get("success"))


if __name__ == "__main__":
    main()
