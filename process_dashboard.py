#!/usr/bin/env python3
"""
Agent 仪表盘生成器 — 生成独立 dashboard.html
============================================
功能:
  1. 读取 collected.json
  2. 生成单文件 HTML 仪表盘（浏览器直接打开）
  3. 包含：消息时间线、任务状态、Agent 统计、搜索过滤

用法:
  python process_dashboard.py                          # 生成 dashboard.html
  python process_dashboard.py --input collected.json   # 指定输入
  python process_dashboard.py --output myboard.html    # 指定输出
"""

import json
import sys
import argparse
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# ── UTF-8 on Windows ────────────────────────────────────────────
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_INPUT = Path("K:/my two agent/collected.json")
DEFAULT_OUTPUT = Path("K:/my two agent/dashboard.html")


def build_html(records):
    """Generate the full dashboard HTML."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── Data crunching ──────────────────────────────────────
    # Message types
    type_counts = defaultdict(int)
    agent_counts = defaultdict(int)
    messages_by_date = defaultdict(int)
    tasks = []

    for r in records:
        mtype = r.get("type", "other")
        type_counts[mtype] += 1

        frm = r.get("from", "?")
        if frm not in ("bridge", "test", "unknown"):
            agent_counts[frm] += 1

        ts = r.get("timestamp") or r.get("created_at") or r.get("claimed_at") or r.get("last_sync") or ""
        ts = str(ts)
        if ts and ts != "None":
            messages_by_date[ts[:10]] += 1

        # Collect tasks
        if mtype == "delegate" or (r.get("id", "").startswith("T")):
            tasks.append({
                "id": r.get("id", "?"),
                "title": r.get("title") or r.get("content", "?")[:80],
                "status": r.get("status", "pending"),
                "from": frm,
                "assigned": r.get("assigned_to") or r.get("to", "?"),
                "claimed": r.get("claimed_by", "-"),
                "created": ts
            })

    total = len(records)

    # ── Data as JSON for JS ──────────────────────────────────
    data_json = json.dumps({
        "total": total,
        "type_counts": dict(type_counts),
        "agent_counts": dict(agent_counts),
        "messages_by_date": dict(sorted(messages_by_date.items())),
        "tasks": tasks,
        "generated_at": now
    }, ensure_ascii=False, indent=2)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🤝 Agent 协作仪表盘</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: system-ui, -apple-system, sans-serif; background:#0f172a; color:#e2e8f0; min-height:100vh; }}
.header {{ background:linear-gradient(135deg,#6366f1,#8b5cf6); padding:32px; text-align:center; }}
.header h1 {{ font-size:2em; margin-bottom:8px; }}
.header p {{ opacity:0.8; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:20px; padding:24px; max-width:1400px; margin:0 auto; }}
.card {{ background:#1e293b; border-radius:12px; padding:24px; border:1px solid #334155; }}
.card h3 {{ font-size:0.9em; color:#94a3b8; margin-bottom:12px; text-transform:uppercase; letter-spacing:1px; }}
.stat {{ font-size:2.5em; font-weight:bold; }}
.stat.green {{ color:#34d399; }}
.stat.blue {{ color:#60a5fa; }}
.stat.purple {{ color:#a78bfa; }}
.stat.yellow {{ color:#fbbf24; }}
.stat.red {{ color:#f87171; }}
.timeline {{ grid-column:1/-1; }}
.timeline-chart {{ display:flex; align-items:flex-end; gap:2px; height:150px; padding-top:16px; }}
.bar {{ flex:1; background:#6366f1; border-radius:2px 2px 0 0; min-width:6px; position:relative; transition:background .2s; }}
.bar:hover {{ background:#818cf8; }}
.bar-label {{ font-size:0.6em; text-align:center; color:#94a3b8; margin-top:4px; }}
table {{ width:100%; border-collapse:collapse; font-size:0.85em; }}
th {{ text-align:left; color:#94a3b8; padding:8px; border-bottom:1px solid #334155; }}
td {{ padding:8px; border-bottom:1px solid #1e293b; }}
tr:hover td {{ background:#334155; }}
.tag {{ display:inline-block; padding:2px 8px; border-radius:4px; font-size:0.75em; font-weight:600; }}
.tag.chat {{ background:#6366f1; }}
.tag.delegate {{ background:#f59e0b; }}
.tag.ask {{ background:#10b981; }}
.tag.review {{ background:#06b6d4; }}
.tag.claim {{ background:#8b5cf6; }}
.tag.system {{ background:#64748b; }}
.tag.pending {{ background:#f59e0b22; color:#fbbf24; border:1px solid #f59e0b; }}
.tag.in_progress {{ background:#3b82f622; color:#60a5fa; border:1px solid #3b82f6; }}
.tag.done {{ background:#10b98122; color:#34d399; border:1px solid #10b981; }}
.filter-bar {{ padding:24px; max-width:1400px; margin:0 auto; display:flex; gap:8px; flex-wrap:wrap; }}
.filter-bar button {{ padding:8px 16px; border:1px solid #334155; background:#1e293b; color:#e2e8f0; border-radius:8px; cursor:pointer; font-size:0.85em; transition:all .2s; }}
.filter-bar button:hover,.filter-bar button.active {{ background:#6366f1; border-color:#6366f1; }}
.search {{ padding:8px 16px; border:1px solid #334155; background:#1e293b; color:#e2e8f0; border-radius:8px; font-size:0.85em; flex:1; min-width:200px; }}
.footer {{ text-align:center; padding:32px; color:#64748b; font-size:0.8em; }}
</style>
</head>
<body>

<div class="header">
  <h1>🤝 Agent 协作仪表盘</h1>
  <p>Codex ↔ Claude Code · {now}</p>
</div>

<div class="filter-bar">
  <input class="search" id="search" placeholder="🔍 搜索消息内容..." oninput="filter()">
  <button class="active" onclick="filter('all')" id="btn-all">全部</button>
  <button onclick="filter('chat')" id="btn-chat">💬 聊天</button>
  <button onclick="filter('delegate')" id="btn-delegate">📋 委派</button>
  <button onclick="filter('ask')" id="btn-ask">💡 提问</button>
  <button onclick="filter('review')" id="btn-review">🔍 审查</button>
  <button onclick="filter('claim')" id="btn-claim">✅ 认领</button>
  <button onclick="filter('system')" id="btn-system">⚙ 系统</button>
</div>

<div class="grid" id="dashboard">
  <!-- Stats cards will be rendered by JS -->
</div>

<div class="footer">
  Generated by process_dashboard.py · Agent 聊天收集系统
</div>

<script>
const DATA = {data_json};

function render() {{
  const d = DATA;
  const html = `
  <div class="card"><h3>📨 总消息数</h3><div class="stat blue">${{d.total.toLocaleString()}}</div></div>
  <div class="card"><h3>📋 任务</h3><div class="stat yellow">${{d.tasks.length}}</div></div>
  <div class="card"><h3>🤖 Agent 数</h3><div class="stat purple">${{Object.keys(d.agent_counts).length}}</div></div>
  <div class="card"><h3>💬 聊天消息</h3><div class="stat green">${{d.type_counts.chat || 0}}</div></div>

  <div class="card timeline">
    <h3>📈 消息时间线</h3>
    <div class="timeline-chart">
      ${{Object.entries(d.messages_by_date).map(([date, count]) => {{
        const h = Math.max(4, count * 10);
        return `<div style="height:${{h}}px" class="bar" title="${{date}}: ${{count}} 条"><div class="bar-label">${{date.slice(5)}}</div></div>`;
      }}).join('')}}
    </div>
  </div>

  <div class="card" style="grid-column:1/-1;">
    <h3>📋 任务列表</h3>
    <table>
      <tr><th>ID</th><th>标题</th><th>状态</th><th>发起</th><th>指派</th><th>认领</th></tr>
      ${{d.tasks.length > 0 ? d.tasks.map(t => `
        <tr>
          <td><code>${{t.id}}</code></td>
          <td>${{t.title}}</td>
          <td><span class="tag ${{t.status}}">${{t.status}}</span></td>
          <td>${{t.from}}</td>
          <td>${{t.assigned}}</td>
          <td>${{t.claimed || '-'}}</td>
        </tr>
      `).join('') : '<tr><td colspan="6" style="color:#64748b">暂无任务</td></tr>'}}
    </table>
  </div>

  <div class="card" style="grid-column:1/-1;">
    <h3>🤖 Agent 活跃度</h3>
    <table>
      <tr><th>Agent</th><th>消息数</th><th>占比</th></tr>
      ${{Object.entries(d.agent_counts).sort((a,b) => b[1]-a[1]).map(([agent, count]) => `
        <tr><td>${{agent}}</td><td>${{count}}</td><td>${{Math.round(count/d.total*100)}}%</td></tr>
      `).join('')}}
    </table>
  </div>
  `;

  document.getElementById('dashboard').innerHTML = html;
}}

let currentFilter = 'all';
function filter(type) {{
  currentFilter = type || currentFilter;
  document.querySelectorAll('.filter-bar button').forEach(b => b.classList.remove('active'));
  const id = type === 'all' ? 'btn-all' : 'btn-' + type;
  document.getElementById(id)?.classList.add('active');
  // Re-render with filter
  render();
}}

render();
</script>

</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(
        description="Agent 仪表盘生成器 — collected.json → dashboard.html"
    )
    parser.add_argument("--input", type=str, default=str(DEFAULT_INPUT),
                        help="Input collected.json file")
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT),
                        help="Output HTML file path")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[error] Input not found: {input_path}", file=sys.stderr)
        print(f"[error] Run collect.py first!", file=sys.stderr)
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = data.get("records", [])
    print(f"[dashboard] Loaded {len(records)} records", file=sys.stderr)

    html = build_html(records)

    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n[dashboard] ✅ {output_path}", file=sys.stderr)
    print(f"[dashboard] Open in browser: file:///{output_path}", file=sys.stderr)
    print(output_path)


if __name__ == "__main__":
    main()
