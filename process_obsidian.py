#!/usr/bin/env python3
"""
Agent 知识处理器 — 将 collected.json 转为 Obsidian .md 笔记
============================================================
功能:
  1. 读取 collected.json
  2. 按类型分类生成 .md 笔记（放在 K:\agent-knowledge\）
  3. 自动建立 [[双向链接]]
  4. 生成 AI 洞察卡片
  5. 更新 Dashboard 数据

用法:
  python process_obsidian.py                           # 全量处理
  python process_obsidian.py --input collected.json    # 指定输入
  python process_obsidian.py --since 7d                # 增量更新
  python process_obsidian.py --insights-only           # 只生成洞察
"""

import json
import os
import sys
import argparse
import re
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

# ── UTF-8 on Windows ────────────────────────────────────────────
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Paths ────────────────────────────────────────────────────────
VAULT = Path("K:/agent-knowledge")
CHATS_DIR = VAULT / "10-Chats"
TASKS_DIR = VAULT / "20-Tasks"
SESSIONS_DIR = VAULT / "30-Sessions"
INSIGHTS_DIR = VAULT / "40-Insights"
DECISIONS_DIR = VAULT / "50-Decisions"
DATA_DIR = VAULT / "_data"

# ── Helpers ─────────────────────────────────────────────────────
def safe_filename(s):
    """Make a string safe for filenames."""
    return re.sub(r'[<>:"/\\|?*]', '-', s)[:100]

def date_from_ts(ts_str):
    """Extract date string from ISO timestamp."""
    try:
        return ts_str[:10]
    except:
        return datetime.now().strftime("%Y-%m-%d")

def md_link(text, target):
    """Create Obsidian [[link]]."""
    return f"[[{target}|{text}]]" if text != target else f"[[{target}]]"

def write_note(dir_path, filename, content, dry_run=False):
    """Write a .md note to the vault."""
    if dry_run:
        print(f"  [dry] Would write: {dir_path / filename}", file=sys.stderr)
        return
    dir_path.mkdir(parents=True, exist_ok=True)
    filepath = dir_path / filename
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath


# ── Processors ──────────────────────────────────────────────────
def process_chats(records, dry_run=False):
    """Generate daily chat notes."""
    print("[process] Generating chat notes...", file=sys.stderr)

    # Group by date
    by_date = defaultdict(list)
    for r in records:
        if r.get("type") in ("chat", "delegate", "review", "ask", "claim", "sync", "system"):
            ts = r.get("timestamp", "")
            ts = str(ts)
            date = date_from_ts(ts)
            if not date or date == "?":
                continue
            by_date[date].append(r)

    written = []
    for date, msgs in sorted(by_date.items()):
        lines = [
            f"---",
            f"type: daily-chat",
            f"date: {date}",
            f"message_count: {len(msgs)}",
            f"---",
            f"",
            f"# 📅 {date} · 协作日志",
            f"",
            f"> {len(msgs)} 条消息",
            f"",
            f"| 时间 | 类型 | 来自 | 去向 | 内容 |",
            f"|------|------|------|------|------|",
        ]

        for m in msgs:
            ts = m.get("timestamp", "")[11:19] if m.get("timestamp") else "??:??"
            mtype = m.get("type", "?")
            frm = m.get("from", "?")
            to = m.get("to", "?")
            content = m.get("content", "")[:80].replace("|", "\\|")

            # Build links
            task_link = ""
            if mtype == "delegate":
                task_link = " → [[20-Tasks/|任务]]"
            elif mtype == "ask":
                task_link = " → [[40-Insights/|洞察]]"
            elif mtype in ("claim", "review"):
                task_link = " → [[20-Tasks/|任务]]"

            lines.append(f"| {ts} | `{mtype}` | {frm} | {to} | {content}{task_link} |")

        lines.append("")
        lines.append(f"## 🔗 相关")
        # Link to tasks mentioned today
        for m in msgs:
            if m.get("type") == "delegate":
                content = m.get("content", "")[:50]
                tid = safe_filename(f"task-{content}")
                lines.append(f"- 📋 [[20-Tasks/{date}-{tid}|{content}]]")

        filename = f"{date}.md"
        write_note(CHATS_DIR, filename, "\n".join(lines), dry_run)
        written.append(filename)

    print(f"[process] {len(written)} chat notes written", file=sys.stderr)
    return written


def process_tasks(records, dry_run=False):
    """Generate per-task notes."""
    print("[process] Generating task notes...", file=sys.stderr)

    tasks = [r for r in records if r.get("type") == "task" or
             (r.get("id", "").startswith("T") and "title" in r)]

    # Also extract from delegate messages
    delegate_msgs = [r for r in records if r.get("type") == "delegate"]

    written = []
    seen = set()

    for t in tasks + delegate_msgs:
        tid = t.get("id", "")
        if not tid and t.get("type") == "delegate":
            tid = f"T{hash(t.get('content', '')) % 1000:03d}"

        if tid in seen:
            continue
        seen.add(tid)

        title = t.get("title") or t.get("content", "Unknown")[:100]
        status = t.get("status", "pending")
        frm = t.get("from", "?")
        assigned = t.get("assigned_to") or t.get("to", "?")
        claimed = t.get("claimed_by", "-")
        created = t.get("created_at") or t.get("timestamp", "?")
        date = date_from_ts(created)
        desc = t.get("description") or t.get("content", "")
        result = t.get("result", "-")

        lines = [
            f"---",
            f"type: task",
            f"id: \"{tid}\"",
            f"status: \"{status}\"",
            f"from: \"{frm}\"",
            f"assigned_to: \"{assigned}\"",
            f"claimed_by: \"{claimed}\"",
            f"created: \"{created}\"",
            f"---",
            f"",
            f"# 📋 {tid} · {safe_filename(title)}",
            f"",
            f"| 字段 | 值 |",
            f"|------|-----|",
            f"| 状态 | `{status}` |",
            f"| 发起 | {frm} |",
            f"| 指派 | {assigned} |",
            f"| 认领 | {claimed} |",
            f"| 创建 | {created} |",
            f"",
            f"## 描述",
            f"",
            f"{desc}",
            f"",
            f"## 结果",
            f"",
            f"{result}",
            f"",
            f"## 🔗 关联",
            f"- 📅 [[10-Chats/{date}|{date} 聊天记录]]",
            f"- 📝 [[{date}|会话日]]" if t.get("type") == "delegate" else "",
        ]

        filename = f"{tid}-{safe_filename(title)[:60]}.md"
        write_note(TASKS_DIR, filename, "\n".join(lines), dry_run)
        written.append(filename)

    print(f"[process] {len(written)} task notes written", file=sys.stderr)
    return written


def process_sessions(records, dry_run=False):
    """Generate session summaries from Claude Code transcripts."""
    print("[process] Generating session notes...", file=sys.stderr)

    sessions = [r for r in records if r.get("type") == "claude_session"]

    written = []
    for sess in sessions:
        sid = sess.get("id", "unknown")
        project = sess.get("project", "unknown")
        count = sess.get("message_count", 0)
        ts = sess.get("timestamp", "")
        date = date_from_ts(ts)

        lines = [
            f"---",
            f"type: session",
            f"id: \"{sid}\"",
            f"project: \"{project}\"",
            f"date: \"{date}\"",
            f"message_count: {count}",
            f"---",
            f"",
            f"# 📝 会话 · {date} · {project}",
            f"",
            f"| 字段 | 值 |",
            f"|------|-----|",
            f"| 项目 | [[{project}]] |",
            f"| 消息数 | {count} |",
            f"| 会话 ID | `{sid}` |",
            f"",
            f"## 🔗 关联",
            f"- 📅 [[10-Chats/{date}|{date} 聊天记录]]",
        ]

        filename = f"session-{sid[:16]}.md"
        write_note(SESSIONS_DIR, filename, "\n".join(lines), dry_run)
        written.append(filename)

    print(f"[process] {len(written)} session notes written", file=sys.stderr)
    return written


def generate_insights(records, dry_run=False):
    """Generate AI insight cards from collected data."""
    print("[process] Generating insights...", file=sys.stderr)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Insight 1: Message type distribution
    type_counts = defaultdict(int)
    for r in records:
        mtype = r.get("type", "other")
        type_counts[mtype] += 1

    if type_counts:
        lines = [
            f"---",
            f"type: insight",
            f"tags: [statistics, overview]",
            f"created: \"{now}\"",
            f"---",
            f"",
            f"# 📊 消息类型分布",
            f"",
            f"> 自动生成 · {now}",
            f"",
            f"| 类型 | 数量 |",
            f"|------|------|",
        ]
        for mtype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            lines.append(f"| `{mtype}` | {count} |")

        lines.append("")
        lines.append(f"## 🔗 关联")
        lines.append(f"- 📊 [[Dashboard|仪表盘]]")

        write_note(INSIGHTS_DIR, "insight-message-types.md", "\n".join(lines), dry_run)

    # Insight 2: Project context snapshot
    ctx_records = [r for r in records if r.get("_source") == "bridge/context.json"]
    if ctx_records:
        ctx = ctx_records[0]
        lines = [
            f"---",
            f"type: insight",
            f"tags: [project, context]",
            f"created: \"{now}\"",
            f"---",
            f"",
            f"# 🎯 项目上下文",
            f"",
            f"> 自动生成 · {now}",
            f"",
            f"| 字段 | 值 |",
            f"|------|-----|",
            f"| 项目 | {ctx.get('project', '-')} |",
            f"| 分支 | {ctx.get('branch', '-')} |",
            f"| 文件 | {', '.join(ctx.get('files', []))} |",
            f"| 最后同步 | {ctx.get('last_sync', '-')} |",
            f"",
            f"## 🔗 关联",
            f"- 📊 [[Dashboard|仪表盘]]",
        ]
        write_note(INSIGHTS_DIR, "insight-project-context.md", "\n".join(lines), dry_run)

    # Insight 3: Agent collaboration summary
    agent_msgs = defaultdict(int)
    for r in records:
        frm = r.get("from", "unknown")
        if frm not in ("bridge", "unknown", "test"):
            agent_msgs[frm] += 1

    if agent_msgs:
        lines = [
            f"---",
            f"type: insight",
            f"tags: [agents, collaboration]",
            f"created: \"{now}\"",
            f"---",
            f"",
            f"# 🤖 Agent 协作统计",
            f"",
            f"> 自动生成 · {now}",
            f"",
            f"| Agent | 消息数 |",
            f"|-------|--------|",
        ]
        for agent, count in sorted(agent_msgs.items(), key=lambda x: -x[1]):
            lines.append(f"| {agent} | {count} |")

        lines.append("")
        lines.append("## 🔗 关联")
        lines.append("- 📊 [[Dashboard|仪表盘]]")

        write_note(INSIGHTS_DIR, "insight-agent-stats.md", "\n".join(lines), dry_run)

    print(f"[process] Insights generated", file=sys.stderr)


def update_dashboard(dry_run=False):
    """Touch Dashboard.md to ensure it exists."""
    dashboard = VAULT / "Dashboard.md"
    if not dashboard.exists():
        print("[process] Dashboard.md not found, skipping update", file=sys.stderr)
    else:
        print(f"[process] Dashboard ready: {dashboard}", file=sys.stderr)


# ── Main ───────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Agent 知识处理器 — collected.json → Obsidian .md 笔记"
    )
    parser.add_argument("--input", type=str, default=str(Path("K:/my two agent/collected.json")),
                        help="Input collected.json file")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview only, don't write files")
    parser.add_argument("--insights-only", action="store_true",
                        help="Only generate insights")
    parser.add_argument("--chats-only", action="store_true",
                        help="Only process chats")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[error] Input file not found: {input_path}", file=sys.stderr)
        print(f"[error] Run collect.py first!", file=sys.stderr)
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = data.get("records", [])
    print(f"[process] Loaded {len(records)} records from {input_path}", file=sys.stderr)

    if args.dry_run:
        print("[process] DRY RUN — no files will be written\n", file=sys.stderr)

    if args.insights_only:
        generate_insights(records, args.dry_run)
    elif args.chats_only:
        process_chats(records, args.dry_run)
    else:
        process_chats(records, args.dry_run)
        process_tasks(records, args.dry_run)
        process_sessions(records, args.dry_run)
        generate_insights(records, args.dry_run)
        update_dashboard(args.dry_run)

    print(f"\n[process] ✅ Done — vault: {VAULT}", file=sys.stderr)


if __name__ == "__main__":
    main()
