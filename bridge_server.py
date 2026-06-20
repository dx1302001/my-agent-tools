#!/usr/bin/env python3
"""
Codex ↔ Claude Code Collaboration Bridge Server
================================================
TCP-based realtime message router + file-based persistent state.
Replaces tmux for agent-to-agent collaboration on Windows.

Architecture:
    Claude Code ──TCP──▶ Bridge Server ◀──TCP── Codex CLI
                            │
                     shared/ (files)
                       tasks.json
                       chat.log
                       context.json

Usage:
    python bridge_server.py              # Start server (default port 9876)
    python bridge_server.py --port 9999  # Custom port
"""

import socket
import threading
import json
import os
import sys
import time
import argparse
from datetime import datetime

# Force UTF-8 on Windows (avoids GBK encoding errors with special chars)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Configuration ──────────────────────────────────────────────
DEFAULT_PORT = 9876
SHARED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shared")
CHAT_LOG = os.path.join(SHARED_DIR, "chat.log")
TASKS_FILE = os.path.join(SHARED_DIR, "tasks.json")
CONTEXT_FILE = os.path.join(SHARED_DIR, "context.json")
CLAIMS_FILE = os.path.join(SHARED_DIR, "claims.json")

# Ensure shared directory exists
os.makedirs(SHARED_DIR, exist_ok=True)

# ── File Initialization ────────────────────────────────────────
def init_files():
    """Initialize shared state files if they don't exist."""
    if not os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)
    if not os.path.exists(CONTEXT_FILE):
        with open(CONTEXT_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "project": "",
                "branch": "",
                "files": [],
                "last_sync": None
            }, f, indent=2)
    if not os.path.exists(CLAIMS_FILE):
        with open(CLAIMS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=2)
    if not os.path.exists(CHAT_LOG):
        with open(CHAT_LOG, "w", encoding="utf-8") as f:
            f.write("")

# ── Message Protocol ───────────────────────────────────────────
# Each message is a JSON line (newline-delimited JSON):
# {
#   "type": "chat" | "delegate" | "review" | "ask" | "claim" | "status" | "sync" | "system",
#   "from": "claude" | "codex",
#   "to": "claude" | "codex" | "all",
#   "content": "...",
#   "task_id": "..." (optional),
#   "timestamp": "ISO8601"
# }

def make_message(msg_type, sender, content, **extra):
    """Create a standard protocol message."""
    return json.dumps({
        "type": msg_type,
        "from": sender,
        "to": extra.pop("to", "all"),
        "content": content,
        "timestamp": datetime.now().isoformat(),
        **extra
    }, ensure_ascii=False)

def append_chat(msg):
    """Append a message to the chat log."""
    with open(CHAT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(msg, ensure_ascii=False) + "\n")

def get_tasks():
    """Read the task list."""
    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_tasks(tasks):
    """Write the task list."""
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)

def get_claims():
    with open(CLAIMS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_claims(claims):
    with open(CLAIMS_FILE, "w", encoding="utf-8") as f:
        json.dump(claims, f, indent=2, ensure_ascii=False)

def get_context():
    with open(CONTEXT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_context(ctx):
    with open(CONTEXT_FILE, "w", encoding="utf-8") as f:
        json.dump(ctx, f, indent=2, ensure_ascii=False)

# ── Request Handlers ───────────────────────────────────────────
def handle_message(msg_dict, sender_name):
    """Process an incoming message based on type, return response."""
    msg_type = msg_dict.get("type", "chat")
    content = msg_dict.get("content", "")

    if msg_type == "chat":
        append_chat(msg_dict)
        return {"status": "ok", "action": "broadcast", "message": msg_dict}

    elif msg_type == "delegate":
        tasks = get_tasks()
        task_id = f"T{len(tasks)+1:03d}"
        task = {
            "id": task_id,
            "title": content[:200],
            "description": content,
            "from": sender_name,
            "assigned_to": msg_dict.get("to", "all"),
            "status": "pending",
            "created_at": msg_dict["timestamp"],
            "claimed_by": None,
            "completed_at": None,
            "result": None
        }
        tasks.append(task)
        save_tasks(tasks)
        append_chat(msg_dict)
        return {"status": "ok", "action": "task_created", "task": task}

    elif msg_type == "review":
        append_chat(msg_dict)
        return {
            "status": "ok",
            "action": "review_requested",
            "message": f"[REVIEW] {sender_name} requests review of: {content[:100]}"
        }

    elif msg_type == "ask":
        append_chat(msg_dict)
        return {"status": "ok", "action": "question_asked", "message": msg_dict}

    elif msg_type == "claim":
        task_id = content.strip()
        tasks = get_tasks()
        claims = get_claims()
        for t in tasks:
            if t["id"] == task_id:
                t["status"] = "in_progress"
                t["claimed_by"] = sender_name
                claims[task_id] = {
                    "claimed_by": sender_name,
                    "claimed_at": msg_dict["timestamp"]
                }
                save_tasks(tasks)
                save_claims(claims)
                append_chat(msg_dict)
                return {"status": "ok", "action": "claimed", "task": t}
        return {"status": "error", "message": f"Task {task_id} not found"}

    elif msg_type == "status":
        tasks = get_tasks()
        claims = get_claims()
        ctx = get_context()
        # Read last N chat lines
        chat_lines = []
        if os.path.exists(CHAT_LOG):
            with open(CHAT_LOG, "r", encoding="utf-8") as f:
                chat_lines = f.readlines()[-20:]  # last 20 messages
        return {
            "status": "ok",
            "action": "status_report",
            "tasks": tasks,
            "claims": claims,
            "context": ctx,
            "recent_chat": [line.strip() for line in chat_lines if line.strip()]
        }

    elif msg_type == "sync":
        ctx = get_context()
        if content:
            try:
                update = json.loads(content)
                ctx.update(update)
                ctx["last_sync"] = msg_dict["timestamp"]
                save_context(ctx)
            except json.JSONDecodeError:
                pass
        append_chat(msg_dict)
        return {"status": "ok", "action": "synced", "context": ctx}

    elif msg_type == "system":
        append_chat(msg_dict)
        return {"status": "ok", "action": "system_msg", "message": msg_dict}

    else:
        append_chat(msg_dict)
        return {"status": "ok", "action": "echo", "message": msg_dict}

# ── TCP Server ──────────────────────────────────────────────────
clients = {}  # {socket: name}

def broadcast(message_dict):
    """Send a message dict to all connected clients."""
    dead = []
    data = (json.dumps(message_dict, ensure_ascii=False) + "\n").encode("utf-8")
    for sock, name in clients.items():
        try:
            sock.sendall(data)
        except (BrokenPipeError, ConnectionResetError, OSError):
            dead.append(sock)
    for sock in dead:
        del clients[sock]

def broadcast_json_str(json_str):
    """Broadcast a raw JSON string to all connected clients (for passthrough)."""
    dead = []
    data = (json_str.strip() + "\n").encode("utf-8")
    for sock, name in clients.items():
        try:
            sock.sendall(data)
        except (BrokenPipeError, ConnectionResetError, OSError):
            dead.append(sock)
    for sock in dead:
        del clients[sock]

def handle_client(sock, addr):
    """Handle a single client connection."""
    buf = b""
    sender_name = f"agent@{addr[1]}"
    identity_received = False

    try:
        sock.settimeout(10)
        initial_data = sock.recv(4096)
        buf = initial_data
        sock.settimeout(None)

        # Process any complete messages in the initial buffer
        # The FIRST line might be an identity announcement
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            line_str = line.decode("utf-8").strip()
            if not line_str:
                continue

            if not identity_received:
                identity_received = True
                try:
                    identity = json.loads(line_str)
                    if identity.get("type") == "identity":
                        sender_name = identity.get("name", sender_name)
                        continue  # Don't process identity as a regular message
                except json.JSONDecodeError:
                    pass  # Not an identity, process as regular message below

            # Process non-identity message
            try:
                msg = json.loads(line_str)
                msg["from"] = sender_name
                response = handle_message(msg, sender_name)
                broadcast(msg)
                resp_data = (json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8")
                sock.sendall(resp_data)
            except json.JSONDecodeError:
                err_resp = {"status": "error", "message": "Invalid JSON"}
                sock.sendall((json.dumps(err_resp) + "\n").encode("utf-8"))

    except socket.timeout:
        pass

    clients[sock] = sender_name
    print(f"[+] {sender_name} connected from {addr}")

    # Announce arrival
    join_msg = make_message("system", "bridge", f"{sender_name} joined the session", to="all")
    broadcast(join_msg)

    try:
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buf += chunk

            # Process complete messages (newline-delimited JSON)
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line_str = line.decode("utf-8").strip()
                if not line_str:
                    continue

                try:
                    msg = json.loads(line_str)
                    msg["from"] = sender_name  # enforce sender identity
                    response = handle_message(msg, sender_name)

                    # Broadcast to all other clients
                    broadcast(msg)

                    # Send response back to sender
                    resp_data = (json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8")
                    sock.sendall(resp_data)

                except json.JSONDecodeError:
                    err_resp = {"status": "error", "message": "Invalid JSON"}
                    sock.sendall((json.dumps(err_resp) + "\n").encode("utf-8"))

    except (ConnectionResetError, BrokenPipeError, OSError):
        pass
    finally:
        print(f"[-] {sender_name} disconnected")
        del clients[sock]
        leave_msg = make_message("system", "bridge", f"{sender_name} left the session", to="all")
        broadcast(leave_msg)
        try:
            sock.close()
        except Exception:
            pass

# ── CLI (stdin bridge mode) ────────────────────────────────────
def stdin_bridge():
    """
    Bridge mode: reads messages from stdin (for Codex to pipe into).
    This allows Codex to participate without a TCP client.
    """
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            msg.setdefault("from", "codex")
            msg.setdefault("timestamp", datetime.now().isoformat())
            response = handle_message(msg, "codex")
            print(json.dumps(response, ensure_ascii=False))
        except json.JSONDecodeError:
            # Treat as plain chat message
            msg = make_message("chat", "codex", line)
            handle_message(msg, "codex")
            print(json.dumps({"status": "ok"}, ensure_ascii=False))

# ── Main ───────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Codex ↔ Claude Code Collaboration Bridge"
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"TCP port (default: {DEFAULT_PORT})")
    parser.add_argument("--stdin", action="store_true",
                        help="Run in stdin bridge mode (for piping from Codex)")
    args = parser.parse_args()

    init_files()

    if args.stdin:
        print("[bridge] Stdin bridge mode — ready for messages", file=sys.stderr)
        stdin_bridge()
        return

    # TCP Server mode
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", args.port))
    server.listen(5)

    print(f"""
╔══════════════════════════════════════════════╗
║   🤝  Codex ↔ Claude Code Bridge           ║
║   TCP Server: 127.0.0.1:{args.port:<5}            ║
║   Shared Dir: {SHARED_DIR[:35]:<35} ║
║                                            ║
║   Ready for connections...                 ║
╚══════════════════════════════════════════════╝
""")
    print(f"[bridge] Chat log: {CHAT_LOG}")
    print(f"[bridge] Tasks:    {TASKS_FILE}")
    print(f"[bridge] Claims:   {CLAIMS_FILE}")
    print(f"[bridge] Context:  {CONTEXT_FILE}")
    print("[bridge] Waiting for connections...\n")

    try:
        while True:
            sock, addr = server.accept()
            t = threading.Thread(target=handle_client, args=(sock, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("\n[bridge] Shutting down...")
    finally:
        server.close()

if __name__ == "__main__":
    main()
