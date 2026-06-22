#!/usr/bin/env python3
"""
Agent 聊天收集器 — 扫描全部数据源，聚合成统一 JSON
=====================================================
数据源:
  1. Bridge shared/  (chat.log, tasks.json, claims.json, context.json)
  2. Claude Code ~/.claude/projects/**/*.jsonl (会话记录)
  3. Claude Code ~/.claude/history.jsonl (命令历史)

用法:
  python collect.py                        # 全量收集
  python collect.py --since 7d             # 最近 7 天
  python collect.py --output mydata.json   # 指定输出文件
  python collect.py --bridge-only          # 只收桥接数据
"""

import json
import os
import sys
import glob
import argparse
import re
from datetime import datetime, timedelta
from pathlib import Path

# ── UTF-8 on Windows ────────────────────────────────────────────
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Paths ────────────────────────────────────────────────────────
HOME = Path.home()
BRIDGE_DIR = Path("K:/my two agent/shared")
CLAUDE_PROJECTS = HOME / ".claude/projects"
CLAUDE_HISTORY = HOME / ".claude/history.jsonl"
DEFAULT_OUTPUT = Path("K:/my two agent/collected.json")


def parse_since(since_str):
    """Parse '7d', '24h', '2w' into a datetime."""
    if not since_str:
        return None
    match = re.match(r'(\d+)\s*(d|h|w|m)', since_str.lower())
    if not match:
        print(f"[warn] Cannot parse --since '{since_str}', using all data", file=sys.stderr)
        return None
    num = int(match.group(1))
    unit = match.group(2)
    if unit == 'h':
        return datetime.now() - timedelta(hours=num)
    elif unit == 'd':
        return datetime.now() - timedelta(days=num)
    elif unit == 'w':
        return datetime.now() - timedelta(weeks=num)
    elif unit == 'm':
        return datetime.now() - timedelta(days=num * 30)
    return None


def in_range(ts_str, since):
    """Check if a timestamp string is within the since range."""
    if since is None:
        return True
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00").replace("+00:00", ""))
        return ts.replace(tzinfo=None) >= since
    except (ValueError, TypeError):
        return True  # keep if we can't parse


# ── Source 1: Bridge Data ──────────────────────────────────────
def collect_bridge(since=None):
    """Collect all data from the bridge shared/ directory."""
    records = []
    print(f"[collect] Scanning bridge: {BRIDGE_DIR}", file=sys.stderr)

    # chat.log
    chat_log = BRIDGE_DIR / "chat.log"
    if chat_log.exists():
        with open(chat_log, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    ts = msg.get("timestamp", "")
                    if in_range(ts, since):
                        msg["_source"] = "bridge/chat.log"
                        records.append(msg)
                except json.JSONDecodeError:
                    continue

    # tasks.json
    tasks_file = BRIDGE_DIR / "tasks.json"
    if tasks_file.exists():
        with open(tasks_file, "r", encoding="utf-8") as f:
            tasks = json.load(f)
            for t in tasks:
                ts = t.get("created_at", "")
                if in_range(ts, since):
                    t["_source"] = "bridge/tasks.json"
                    records.append(t)

    # claims.json
    claims_file = BRIDGE_DIR / "claims.json"
    if claims_file.exists():
        with open(claims_file, "r", encoding="utf-8") as f:
            claims = json.load(f)
            for task_id, claim in claims.items():
                ts = claim.get("claimed_at", "")
                if in_range(ts, since):
                    claim["_source"] = "bridge/claims.json"
                    claim["task_id"] = task_id
                    records.append(claim)

    # context.json
    context_file = BRIDGE_DIR / "context.json"
    if context_file.exists():
        with open(context_file, "r", encoding="utf-8") as f:
            ctx = json.load(f)
            ts = ctx.get("last_sync", "")
            if in_range(ts, since):
                ctx["_source"] = "bridge/context.json"
                records.append(ctx)

    print(f"[collect] Bridge: {len(records)} records", file=sys.stderr)
    return records


# ── Source 2: Claude Code Sessions ─────────────────────────────
def collect_claude_sessions(since=None):
    """Collect Claude Code session transcripts."""
    records = []
    if not CLAUDE_PROJECTS.exists():
        print(f"[collect] No Claude projects dir: {CLAUDE_PROJECTS}", file=sys.stderr)
        return records

    jsonl_files = glob.glob(str(CLAUDE_PROJECTS / "**/*.jsonl"), recursive=True)
    print(f"[collect] Found {len(jsonl_files)} Claude session files", file=sys.stderr)

    for fpath in jsonl_files:
        # Skip subagent internal transcripts (handled separately)
        if "subagents" in fpath:
            continue
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                session_messages = []
                session_id = Path(fpath).stem
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        ts = event.get("timestamp", "")
                        if in_range(ts, since):
                            event["_source"] = f"claude/sessions/{Path(fpath).parent.name}/{Path(fpath).name}"
                            event["_session_id"] = session_id
                            session_messages.append(event)
                    except json.JSONDecodeError:
                        continue

                if session_messages:
                    # Add session wrapper
                    records.append({
                        "type": "claude_session",
                        "id": session_id,
                        "project": Path(fpath).parent.name,
                        "file": fpath,
                        "message_count": len(session_messages),
                        "_source": "claude/sessions"
                    })
                    records.extend(session_messages)
        except Exception as e:
            print(f"[warn] Failed to read {fpath}: {e}", file=sys.stderr)

    print(f"[collect] Claude sessions: {len(records)} records", file=sys.stderr)
    return records


# ── Source 3: Claude History ───────────────────────────────────
def collect_claude_history(since=None):
    """Collect Claude Code command history."""
    records = []
    if not CLAUDE_HISTORY.exists():
        print(f"[collect] No history file: {CLAUDE_HISTORY}", file=sys.stderr)
        return records

    with open(CLAUDE_HISTORY, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                ts = entry.get("timestamp", "")
                if in_range(ts, since):
                    entry["_source"] = "claude/history.jsonl"
                    records.append(entry)
            except json.JSONDecodeError:
                continue

    print(f"[collect] Claude history: {len(records)} entries", file=sys.stderr)
    return records


# ── Aggregate ──────────────────────────────────────────────────
def collect_all(since=None, bridge_only=False):
    """Collect from all sources and return unified list."""
    all_records = []

    # Bridge always included
    all_records.extend(collect_bridge(since))

    if not bridge_only:
        all_records.extend(collect_claude_sessions(since))
        all_records.extend(collect_claude_history(since))

    # Sort by timestamp if available
    def sort_key(r):
        ts = r.get("timestamp") or r.get("created_at") or r.get("last_sync") or r.get("claimed_at") or ""
        return str(ts)

    all_records.sort(key=sort_key, reverse=True)

    return all_records


# ── Main ───────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Agent 聊天收集器 — 聚合全部协作数据"
    )
    parser.add_argument("--since", type=str, default=None,
                        help="Time range filter, e.g. '7d', '24h', '2w'")
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT),
                        help=f"Output JSON file (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--bridge-only", action="store_true",
                        help="Only collect bridge data (skip Claude sessions)")
    parser.add_argument("--compact", action="store_true",
                        help="Output compact JSON (no indentation)")
    args = parser.parse_args()

    since = parse_since(args.since)
    if since:
        print(f"[collect] Filter: since {since.isoformat()}", file=sys.stderr)

    records = collect_all(since=since, bridge_only=args.bridge_only)

    # Write output
    output_path = Path(args.output)
    indent = None if args.compact else 2
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "collected_at": datetime.now().isoformat(),
            "total_records": len(records),
            "since": since.isoformat() if since else None,
            "records": records
        }, f, indent=indent, ensure_ascii=False)

    print(f"\n[collect] ✅ {len(records)} records → {output_path}", file=sys.stderr)
    print(output_path)  # stdout for piping


if __name__ == "__main__":
    main()
