#!/usr/bin/env python3
"""Hermes Activity Monitor for AgentPet
Polls Hermes state.db and sends rich events to the Windows AgentPet relay.
"""
import sqlite3
import time
import sys
import json
import urllib.request
import argparse
import os

for var in ("ALL_PROXY", "all_proxy", "http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "SOCKS_PROXY", "socks_proxy", "no_proxy", "NO_PROXY"):
    os.environ.pop(var, None)

_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

STATE_DB = os.path.expanduser("~/.hermes/state.db")
DEFAULT_RELAY = "http://192.168.2.100:7890"

def send_event(relay_url, payload):
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(relay_url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        _opener.open(req, timeout=5)
    except Exception as e:
        print(f"  [WARN] Relay unreachable: {e}", file=sys.stderr)

def get_state(db_path):
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, role, content, tool_calls, tool_name, finish_reason, active, session_id, timestamp
            FROM messages ORDER BY id DESC LIMIT 1
        """)
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return {
            "id": row[0], "role": row[1], "content": row[2] or "",
            "tool_calls": row[3], "tool_name": row[4],
            "finish_reason": row[5], "active": row[6],
            "session_id": row[7], "timestamp": row[8],
        }
    except Exception as e:
        print(f"  [WARN] DB read error: {e}", file=sys.stderr)
        return None

def main():
    parser = argparse.ArgumentParser(description="Hermes activity monitor for AgentPet")
    parser.add_argument("--relay", default=DEFAULT_RELAY, help="AgentPet relay URL")
    parser.add_argument("--interval", type=int, default=3, help="Poll interval in seconds")
    parser.add_argument("--idle-timeout", type=int, default=15, help="Seconds of no activity before done")
    args = parser.parse_args()

    print(f"Hermes Pet Monitor starting...")
    print(f"  DB: {STATE_DB}")
    print(f"  Relay: {args.relay}")
    print(f"  Interval: {args.interval}s, Idle timeout: {args.idle_timeout}s")

    last_state = get_state(STATE_DB)
    if last_state is None:
        print("ERROR: Cannot read state.db")
        sys.exit(1)

    last_msg_id = last_state["id"]
    pet_state = "idle"
    last_activity_time = time.time()

    print(f"  Starting from message ID: {last_msg_id}")
    print("Monitoring... (Ctrl+C to stop)")

    while True:
        try:
            time.sleep(args.interval)

            current = get_state(STATE_DB)
            if current is None:
                continue

            now = time.time()
            msg_changed = current["id"] != last_msg_id

            if msg_changed:
                last_msg_id = current["id"]
                last_activity_time = now

            # Determine what AgentPet event to send
            if current["role"] == "user" and msg_changed:
                # New user message — Hermes is about to work
                if pet_state != "working":
                    pet_state = "working"
                    send_event(args.relay, {
                        "agent": "hermes",
                        "event": "working",
                        "session": f"hermes:{current['session_id']}",
                        "project": "hermes",
                        "message": current["content"][:100] if current["content"] else "Processing...",
                    })
                    print(f"  -> working (user msg #{current['id']}: {current['content'][:60]})")

            elif current["role"] == "assistant" and current["active"] and not current["finish_reason"]:
                # Assistant message still generating — check for tool calls
                tool_info = ""
                if current["tool_calls"]:
                    try:
                        tc = json.loads(current["tool_calls"])
                        if isinstance(tc, list) and len(tc) > 0:
                            tool_name = tc[0].get("function", {}).get("name", "")
                            tool_info = f" [tool: {tool_name}]"
                    except (json.JSONDecodeError, IndexError):
                        pass

                if pet_state != "working":
                    pet_state = "working"
                    send_event(args.relay, {
                        "agent": "hermes",
                        "event": "working",
                        "session": f"hermes:{current['session_id']}",
                        "project": "hermes",
                        "message": f"Thinking{tool_info}",
                    })
                    print(f"  -> working (assistant #{current['id']}{tool_info})")

            elif current["role"] == "assistant" and current["finish_reason"] == "stop" and msg_changed:
                # Assistant finished — will wait for next user message
                if pet_state != "done":
                    pet_state = "waiting"
                    preview = (current["content"][:80] + "...") if len(current["content"]) > 80 else current["content"]
                    send_event(args.relay, {
                        "agent": "hermes",
                        "event": "waiting",
                        "session": f"hermes:{current['session_id']}",
                        "project": "hermes",
                        "message": preview if preview else "Awaiting input",
                    })
                    print(f"  -> waiting (assistant #{current['id']} done)")
                    last_activity_time = now

            # Idle timeout — send done
            if pet_state == "waiting" and (now - last_activity_time) > args.idle_timeout:
                pet_state = "idle"
                send_event(args.relay, {
                    "agent": "hermes",
                    "event": "done",
                    "session": f"hermes:{current['session_id']}",
                    "project": "hermes",
                })
                print(f"  -> done (idle {args.idle_timeout}s)")

        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print(f"  [ERROR] {e}", file=sys.stderr)
            time.sleep(args.interval)

if __name__ == "__main__":
    main()
