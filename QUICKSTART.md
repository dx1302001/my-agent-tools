# 🤝 Codex ↔ Claude 协作桥 · 速查卡

> **一句话**：启动桥接 → Claude 发命令 → Codex 响应 → 两边一起干活

---

## 🚀 启动（每次用之前做一次）

```bash
# 1. 开一个新终端，启动桥接服务器（保持开着别关）
python "K:\my two agent\bridge_server.py"

# 看到这个就说明好了 ↓
# ╔══════════════════════════════════════════════╗
# ║   🤝  Codex ↔ Claude Code Bridge           ║
# ║   TCP Server: 127.0.0.1:9876               ║
```

---

## 📋 全部命令（7个）

| # | 命令 | 干什么用 | 例子 |
|---|------|---------|------|
| 1 | `chat` | 跟 Codex 聊天 | `python "K:\my two agent\bridge_cli.py" chat "Hey 开始干活吧"` |
| 2 | `delegate` | 派任务给 Codex | `python "K:\my two agent\bridge_cli.py" delegate "给设置页加暗黑模式开关"` |
| 3 | `ask` | 问 Codex 建议 | `python "K:\my two agent\bridge_cli.py" ask "这个用 React Server Components 还是客户端组件？"` |
| 4 | `review` | 让 Codex 审查代码 | `python "K:\my two agent\bridge_cli.py" review src/components/Navbar.tsx` |
| 5 | `claim` | 认领一个任务 | `python "K:\my two agent\bridge_cli.py" claim T001` |
| 6 | `status` | 看全局状态 | `python "K:\my two agent\bridge_cli.py" status` |
| 7 | `sync` | 同步项目上下文 | `python "K:\my two agent\bridge_cli.py" sync --project "项目名" --branch "分支"` |

---

## ⚡ 常用别名（粘到 .bashrc 里）

```bash
# 加到 ~/.bashrc 或每次手动 source
alias cc-chat='python "K:\my two agent\bridge_cli.py" chat'
alias cc-delegate='python "K:\my two agent\bridge_cli.py" delegate'
alias cc-ask='python "K:\my two agent\bridge_cli.py" ask'
alias cc-review='python "K:\my two agent\bridge_cli.py" review'
alias cc-claim='python "K:\my two agent\bridge_cli.py" claim'
alias cc-status='python "K:\my two agent\bridge_cli.py" status'
alias cc-sync='python "K:\my two agent\bridge_cli.py" sync'
```

设置后直接用：`cc-chat "hello"` / `cc-status` / `cc-delegate "修bug"`

---

## 🔁 典型工作流

```
1. cc-sync --project "myapp"          ← 告诉 Codex 我们在做什么项目
2. cc-delegate "修登录页的 token 刷新逻辑"  ← 派活
3. cc-status                          ← 看看任务列表
4. cc-claim T001                      ← Codex 认领了，我也认领一个
5. cc-ask "这个用 jwt 还是 session？"    ← 边干活边讨论
6. cc-review src/login.tsx             ← 互相审查代码
7. cc-status                          ← 再看看进展
```

---

## 🗂️ 共享文件（在 shared\ 目录下）

| 文件 | 内容 |
|------|------|
| `shared/tasks.json` | 所有任务及状态 |
| `shared/chat.log` | 完整聊天记录 |
| `shared/claims.json` | 谁认领了什么 |
| `shared/context.json` | 项目上下文（项目名/分支/文件列表） |

---

## 🔧 故障排查

| 问题 | 解决 |
|------|------|
| `Connection refused` | 桥接服务器没启动，先跑 `bridge_server.py` |
| `Address already in use` | 上次的服务器还在跑，用 `taskkill /F /IM python.exe` 杀掉 |
| 中文乱码 | 已经修好了（UTF-8），如果还乱码检查终端编码 |

---

## 📦 文件清单

```
K:\my two agent\
├── bridge_server.py    ← 核心：TCP 桥接服务器
├── bridge_cli.py       ← 命令行工具（你用这个）
├── codex_bridge.py     ← Codex 端连接器
├── start_collab.bat    ← 双击一键启动
├── SKILL.md            ← Claude Code 技能定义
├── QUICKSTART.md       ← 你正在看的这个文件
├── collect.py          ← 收集器：扫全部数据源 → JSON
├── process_obsidian.py ← 生成 Obsidian 知识库
├── process_dashboard.py← 生成 dashboard.html
└── shared/             ← 运行时数据（自动创建）
```

---

## 📊 知识收集系统（新！）

### 一键收数据 → Obsidian → 可视化

```bash
# 1. 收集全部协作数据（桥接 + Claude 会话 + Codex 输出）
python "K:\my two agent\collect.py"

# 2. 生成 Obsidian 笔记库（.md + [[双向链接]] + 洞察）
python "K:\my two agent\process_obsidian.py"

# 3. 生成网页仪表盘
python "K:\my two agent\process_dashboard.py"

# 浏览器打开
start K:\my two agent\dashboard.html
```

### 用 Obsidian 打开知识库

1. 打开 Obsidian → **Open folder as vault**
2. 选 `K:\agent-knowledge\` → 确认
3. 图谱视图看全局关联

### 实时同步

桥接服务器启动后**自动**把每条消息写入 Obsidian vault，不需要手动跑。

### 常用筛选

```bash
python collect.py --since 7d             # 最近 7 天
python collect.py --bridge-only          # 只要桥接数据
python process_obsidian.py --insights-only  # 只生成洞察
```

### 产出位置

| 产物 | 位置 |
|------|------|
| Obsidian 笔记库 | `K:\agent-knowledge\` |
| 网页仪表盘 | `K:\my two agent\dashboard.html` |
| 收集数据 | `K:\my two agent\collected.json` |

---

> **记住三步**：**启动服务器** → **用 bridge_cli.py 发命令** → **看 status 了解全局**
>
> **知识三步**：**collect.py** → **process_obsidian.py** → **dashboard.html**
