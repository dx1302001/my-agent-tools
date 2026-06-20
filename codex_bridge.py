#!/usr/bin/env python3
"""
Codex Bridge Connector
======================
Drop-in script that Codex can use to send its responses to the bridge.
Usage:
    codex exec "your prompt" | python codex_bridge.py

Or the user can pipe Codex output manually:
    codex exec "review src/login.ts" > codex_output.txt
    python bridge_cli.py pipe < codex_output.txt

This script wraps codex exec and pipes output into the bridge automatically.
"""

import sys
import os
import json
import subprocess
import tempfile
from datetime import datetime

BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 9876

# If stdin has content (piped), relay it to bridge
def relay_stdin():
    content = sys.stdin.read()
    if not content.strip():
        return

    # Try to send via socket
    import socket
    msg = {
        "type": "chat",
        "from": "codex",
        "to": "claude",
        "content": content.strip()[:4000],  # Truncate very long outputs
        "timestamp": datetime.now().isoformat()
    }
    data = (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((BRIDGE_HOST, BRIDGE_PORT))
        identity = json.dumps({"type": "identity", "name": "codex"}, ensure_ascii=False) + "\n"
        sock.sendall(identity.encode("utf-8"))
        sock.sendall(data)
        buf = sock.recv(4096)
        if buf:
            resp = json.loads(buf.strip().decode("utf-8"))
            print(f"[bridge] {resp.get('status', 'unknown')}", file=sys.stderr)
        sock.close()
    except Exception as e:
        print(f"[bridge] Connection failed: {e}", file=sys.stderr)
        print(f"[bridge] Output saved to shared/ directory", file=sys.stderr)
        # Fallback: save to shared dir
        shared_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shared")
        os.makedirs(shared_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(shared_dir, f"codex_output_{ts}.txt")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content.strip())
        print(f"[bridge] → {output_file}", file=sys.stderr)

if __name__ == "__main__":
    relay_stdin()
