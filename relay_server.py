"""AgentPet Relay Server
Listens for HTTP events from the Linux Hermes monitor and forwards to AgentPet's HTTP API.
"""
import http.server
import json
import urllib.request
import sys
import time

AGENTPET_API = "http://127.0.0.1:47628/event"
PORT = 7890

_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        event = body.get("event", "working")
        agent = body.get("agent", "hermes")
        session = body.get("session", "hermes:remote")
        project = body.get("project", "hermes")
        message = body.get("message", "")
        tool = body.get("tool", "")
        file = body.get("file", "")
        desc = body.get("desc", "")

        payload = {
            "agent": agent,
            "event": event,
            "session": session,
            "project": project,
            "ts": int(time.time() * 1000),
        }
        if message:
            payload["message"] = message
        if tool:
            payload["tool"] = tool
        if file:
            payload["file"] = file
        if desc:
            payload["desc"] = desc

        try:
            data = json.dumps(payload).encode()
            req = urllib.request.Request(AGENTPET_API, data=data, headers={"Content-Type": "application/json"}, method="POST")
            resp = _opener.open(req, timeout=5)
            result = resp.read().decode()
            print(f"  -> {event}: {result} | msg={message[:50] if message else '-'} tool={tool or '-'}")
        except Exception as e:
            print(f"  [WARN] AgentPet API unreachable: {e}", file=sys.stderr)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True}).encode())

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "running"}).encode())

    def log_message(self, fmt, *args):
        print(f"[{self.address_string()}] {fmt % args}")

if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"AgentPet relay listening on port {PORT} -> {AGENTPET_API}")
    server.serve_forever()
