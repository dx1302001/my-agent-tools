#!/usr/bin/env python3
"""
Codex ↔ Claude Code Bridge CLI
===============================
Command-line interface for the collaboration bridge.
Send messages, delegate tasks, claim work, request reviews.

Usage:
    # Chat
    python bridge_cli.py chat "Hey Codex, how's the login page coming along?"

    # Delegate a task
    python bridge_cli.py delegate "Fix the CSS alignment bug in header"

    # Claim a task
    python bridge_cli.py claim T001

    # Request a code review
    python bridge_cli.py review src/login.ts

    # Ask for a suggestion
    python bridge_cli.py ask "What's the best way to handle nested routing?"

    # Get status overview
    python bridge_cli.py status

    # Sync project context
    python bridge_cli.py sync --project "myapp" --branch "feature/auth"

    # Start listening for incoming messages (blocks)
    python bridge_cli.py listen

    # Pipe Codex output into the bridge
    codex exec "something" | python bridge_cli.py pipe
"""

import socket
import json
import sys
import os
import argparse
import time
from datetime import datetime

# Force UTF-8 on Windows (avoids GBK encoding errors with special chars)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Defaults ────────────────────────────────────────────────────
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9876

# ── Core Send ────────────────────────────────────────────────────
def send_message(msg_dict, host=DEFAULT_HOST, port=DEFAULT_PORT):
    """Send a JSON message to the bridge server and return the response."""
    data = (json.dumps(msg_dict, ensure_ascii=False) + "\n").encode("utf-8")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((host, port))

        # Send identity first
        identity = json.dumps({"type": "identity", "name": "claude"}, ensure_ascii=False) + "\n"
        sock.sendall(identity.encode("utf-8"))

        # Send the actual message
        sock.sendall(data)

        # Read all responses (server broadcasts first, then replies)
        # We need the LAST message which is the actual response with "status" key
        buf = b""
        sock.settimeout(1)
        try:
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
        except socket.timeout:
            pass  # No more data

        sock.close()

        # Parse all messages, return the response (one with "status" key)
        lines = buf.decode("utf-8", errors="replace").strip().split("\n")
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                msg = json.loads(line)
                if "status" in msg:
                    return msg
            except json.JSONDecodeError:
                continue

        # Fallback: return last valid JSON message
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue

        return {"status": "ok"}
    except ConnectionRefusedError:
        return {"status": "error", "message": "Bridge server not running. Start: python bridge_server.py"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def make_msg(msg_type, content, **extra):
    return {
        "type": msg_type,
        "from": "claude",
        "to": extra.pop("to", "codex"),
        "content": content,
        "timestamp": datetime.now().isoformat(),
        **extra
    }

# ── Commands ────────────────────────────────────────────────────
def cmd_chat(args):
    """Send a chat message to Codex."""
    msg = make_msg("chat", args.message)
    resp = send_message(msg)
    if resp.get("status") == "ok":
        print(f"💬 [You → Codex] {args.message}")
    else:
        print(f"❌ Error: {resp.get('message', 'Unknown error')}")

def cmd_delegate(args):
    """Delegate a task to Codex."""
    msg = make_msg("delegate", args.task)
    resp = send_message(msg)
    if resp.get("status") == "ok" and "task" in resp:
        t = resp["task"]
        print(f"📋 Task Created: {t['id']} — \"{t['title']}\"")
        print(f"   Assigned to: {t['assigned_to']}")
        print(f"   Status: {t['status']}")
    else:
        print(f"❌ Error: {resp.get('message', 'Unknown error')}")

def cmd_review(args):
    """Request a code review from Codex."""
    file_or_code = args.target
    if os.path.isfile(file_or_code):
        with open(file_or_code, "r", encoding="utf-8") as f:
            content = f.read()
        msg = make_msg("review", content, file=os.path.abspath(file_or_code))
    else:
        msg = make_msg("review", file_or_code)
    resp = send_message(msg)
    if resp.get("status") == "ok":
        print(f"🔍 Review Requested: {file_or_code}")
        print(f"   Waiting for Codex response...")
    else:
        print(f"❌ Error: {resp.get('message', 'Unknown error')}")

def cmd_ask(args):
    """Ask Codex for a suggestion."""
    msg = make_msg("ask", args.question)
    resp = send_message(msg)
    if resp.get("status") == "ok":
        print(f"💡 Question sent to Codex: {args.question}")
    else:
        print(f"❌ Error: {resp.get('message', 'Unknown error')}")

def cmd_claim(args):
    """Claim a task."""
    msg = make_msg("claim", args.task_id)
    resp = send_message(msg)
    if resp.get("status") == "ok" and "task" in resp:
        t = resp["task"]
        print(f"✅ Claimed: {t['id']} — \"{t['title']}\"")
        print(f"   Now assigned to: claude")
    else:
        print(f"❌ Error: {resp.get('message', 'Unknown error')}")

def cmd_status(args):
    """Show collaboration status."""
    msg = make_msg("status", "")
    resp = send_message(msg)
    if resp.get("status") != "ok":
        print(f"❌ Error: {resp.get('message', 'Unknown error')}")
        return

    print("╔══════════════════════════════════════════╗")
    print("║   🤝  Codex ↔ Claude Code Status        ║")
    print("╚══════════════════════════════════════════╝")

    # Context
    ctx = resp.get("context", {})
    if ctx.get("project"):
        print(f"\n📁 Project: {ctx['project']}")
        print(f"   Branch:  {ctx.get('branch', 'N/A')}")
        print(f"   Files:   {len(ctx.get('files', []))} tracked")

    # Tasks
    tasks = resp.get("tasks", [])
    print(f"\n📋 Tasks ({len(tasks)}):")
    for t in tasks:
        status_icon = {"pending": "⏳", "in_progress": "🔄", "completed": "✅", "cancelled": "❌"}.get(t["status"], "❓")
        claimed = f" [{t['claimed_by']}]" if t.get("claimed_by") else ""
        print(f"   {status_icon} {t['id']}{claimed} — {t['title'][:60]}")

    # Claims
    claims = resp.get("claims", {})
    if claims:
        print(f"\n🔒 Claims: {len(claims)} active")

    # Recent chat
    chat = resp.get("recent_chat", [])
    if chat:
        print(f"\n💬 Recent Chat (last {len(chat)}):")
        for line in chat[-5:]:
            try:
                m = json.loads(line) if isinstance(line, str) else line
                sender = m.get("from", "unknown")
                ctype = m.get("type", "")
                content = m.get("content", "")
                if ctype == "chat":
                    print(f"   [{sender}] {content[:80]}")
                elif ctype == "delegate":
                    print(f"   [{sender}] 📋 Delegated: {content[:80]}")
                elif ctype == "review":
                    print(f"   [{sender}] 🔍 Review request")
                elif ctype == "claim":
                    print(f"   [{sender}] ✅ Claimed: {content[:80]}")
            except Exception:
                print(f"   {line[:80]}")

    print()

def cmd_sync(args):
    """Sync project context."""
    update = {}
    if args.project:
        update["project"] = args.project
    if args.branch:
        update["branch"] = args.branch
    if args.files:
        update["files"] = args.files.split(",")

    msg = make_msg("sync", json.dumps(update))
    resp = send_message(msg)
    if resp.get("status") == "ok":
        print(f"🔄 Context synced")
        ctx = resp.get("context", {})
        print(f"   Project: {ctx.get('project', 'N/A')}")
        print(f"   Branch:  {ctx.get('branch', 'N/A')}")
        print(f"   Files:   {ctx.get('files', [])}")
    else:
        print(f"❌ Error: {resp.get('message', 'Unknown error')}")

def cmd_listen(args):
    """Listen for incoming messages (blocking)."""
    print("👂 Listening for messages from Codex...\n")

    def receive_loop():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        try:
            sock.connect((DEFAULT_HOST, DEFAULT_PORT))
            identity = json.dumps({"type": "identity", "name": "claude-listener"}, ensure_ascii=False) + "\n"
            sock.sendall(identity.encode("utf-8"))

            buf = b""
            while True:
                try:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        line_str = line.decode("utf-8").strip()
                        if not line_str:
                            continue
                        try:
                            msg = json.loads(line_str)
                            display_message(msg)
                        except json.JSONDecodeError:
                            print(f"[raw] {line_str}")
                except socket.timeout:
                    continue
        except ConnectionRefusedError:
            print("❌ Bridge server not running. Start: python bridge_server.py")
        except KeyboardInterrupt:
            print("\n👋 Stopped listening.")
        finally:
            sock.close()

    receive_loop()

def display_message(msg):
    """Pretty-print an incoming message."""
    msg_type = msg.get("type", "")
    sender = msg.get("from", "?")
    content = msg.get("content", "")
    ts = msg.get("timestamp", "")[:19]

    icons = {
        "chat": "💬", "delegate": "📋", "review": "🔍",
        "ask": "💡", "claim": "✅", "system": "🔔"
    }
    icon = icons.get(msg_type, "📨")

    if msg_type == "system":
        print(f"  {icon} [{ts}] {content}")
    elif msg_type == "chat":
        print(f"  {icon} [{sender}] [{ts}] {content}")
    elif msg_type == "delegate":
        print(f"  {icon} [{sender}] Delegated Task: {content[:100]}")
        if "task_id" in msg:
            print(f"     Task ID: {msg['task_id']}")
    elif msg_type == "review":
        print(f"  {icon} [{sender}] Review Request: {content[:100]}")
    elif msg_type == "claim":
        print(f"  {icon} [{sender}] Claimed: {content[:100]}")
    elif msg_type == "ask":
        print(f"  {icon} [{sender}] Question: {content[:100]}")
    else:
        print(f"  {icon} [{sender}] {content[:100]}")

def cmd_pipe(args):
    """Pipe mode: read messages from stdin and relay to bridge."""
    msg = make_msg("chat", "")
    # Read all stdin
    content = sys.stdin.read()
    if content.strip():
        msg["content"] = content.strip()
        resp = send_message(msg)
        if resp.get("status") == "ok":
            print(f"💬 [piped to bridge] {content[:80]}...")
        else:
            print(f"❌ Error: {resp.get('message', 'Unknown error')}")

# ── Main ────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Codex ↔ Claude Code Bridge CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python bridge_cli.py chat "How's it going?"
  python bridge_cli.py delegate "Fix login page bug"
  python bridge_cli.py claim T001
  python bridge_cli.py review src/app.ts
  python bridge_cli.py ask "Best ORM for PostgreSQL?"
  python bridge_cli.py status
  python bridge_cli.py listen
        """
    )
    sub = parser.add_subparsers(dest="command", help="Command")

    # chat
    p_chat = sub.add_parser("chat", help="Send a chat message to Codex")
    p_chat.add_argument("message", help="Message text")

    # delegate
    p_del = sub.add_parser("delegate", help="Delegate a task to Codex")
    p_del.add_argument("task", help="Task description")

    # claim
    p_claim = sub.add_parser("claim", help="Claim a task")
    p_claim.add_argument("task_id", help="Task ID (e.g., T001)")

    # review
    p_rev = sub.add_parser("review", help="Request a code review")
    p_rev.add_argument("target", help="File path or code snippet to review")

    # ask
    p_ask = sub.add_parser("ask", help="Ask Codex for a suggestion")
    p_ask.add_argument("question", help="Your question")

    # status
    sub.add_parser("status", help="Show collaboration status")

    # sync
    p_sync = sub.add_parser("sync", help="Sync project context")
    p_sync.add_argument("--project", help="Project name")
    p_sync.add_argument("--branch", help="Git branch")
    p_sync.add_argument("--files", help="Comma-separated file list")

    # listen
    sub.add_parser("listen", help="Start listening for messages (blocks)")

    # pipe
    sub.add_parser("pipe", help="Read stdin and relay to bridge")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    commands = {
        "chat": cmd_chat,
        "delegate": cmd_delegate,
        "claim": cmd_claim,
        "review": cmd_review,
        "ask": cmd_ask,
        "status": cmd_status,
        "sync": cmd_sync,
        "listen": cmd_listen,
        "pipe": cmd_pipe,
    }

    commands[args.command](args)

if __name__ == "__main__":
    main()
