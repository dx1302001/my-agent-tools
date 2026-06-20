# 🤝 Codex ↔ Claude Code Friends

> **Two AI coding agents, one project, realtime collaboration.**
> Claude Code and Codex Desktop chat, delegate, review, suggest, and claim tasks —
> all through a lightweight TCP bridge (no tmux needed on Windows).

## How It Works

```
Claude Code (VSCode) ←──TCP──→ Bridge Server ←──TCP──→ Codex Desktop
                                  │
                          shared/ (files)
                          tasks, chat, claims
```

A Python TCP server routes messages between Claude Code and Codex in realtime.
Shared JSON files persist the task queue, chat history, and project context.

## Quick Start

### 1. Start the Bridge

```bash
cd "K:\my two agent"

# Start the bridge server (keep this terminal open)
python bridge_server.py
```

Or double-click `start_collab.bat` to launch everything at once.

### 2. In Claude Code

Type `/codex-claude-friends` to activate the skill, or just:

```bash
# Chat with Codex
python bridge_cli.py chat "How's the auth module going?"

# Delegate a task
python bridge_cli.py delegate "Add dark mode toggle to settings"

# Ask for code review
python bridge_cli.py review src/components/Navbar.tsx

# Ask for a suggestion
python bridge_cli.py ask "Best approach for API rate limiting?"

# Claim a task
python bridge_cli.py claim T001

# See overall status
python bridge_cli.py status
```

### 3. From Codex

Codex can participate via pipe mode:

```bash
# Send Codex output to the bridge
codex exec "review the login page code" | python codex_bridge.py

# Or directly write a message
echo '{"type":"chat","from":"codex","content":"Login looks good but needs CSRF"}' | python bridge_cli.py pipe
```

## Commands Reference

| Command | What It Does |
|---|---|
| `python bridge_cli.py chat "text"` | Send realtime chat message |
| `python bridge_cli.py delegate "task"` | Create a task, assign to Codex |
| `python bridge_cli.py claim T001` | Claim a task (take ownership) |
| `python bridge_cli.py review file.ts` | Request code review |
| `python bridge_cli.py ask "question"` | Ask for suggestion/advice |
| `python bridge_cli.py status` | Full dashboard: tasks, claims, chat |
| `python bridge_cli.py sync --project X` | Sync shared project context |
| `python bridge_cli.py listen` | Listen for incoming messages (blocking) |
| `python bridge_cli.py pipe` | Relay stdin content to bridge |

## Files

```
K:\my two agent\
├── bridge_server.py     # TCP message router (THE CORE)
├── bridge_cli.py        # CLI for sending/receiving
├── codex_bridge.py      # Codex pipe connector
├── SKILL.md             # Claude Code skill definition
├── start_collab.bat     # Windows launcher
├── README.md            # This file
└── shared/              # Runtime state (auto-created)
    ├── chat.log         # Full message history
    ├── tasks.json       # Task queue
    ├── claims.json      # Task claims
    └── context.json     # Shared project context
```

## Protocol

All messages are **newline-delimited JSON** over TCP (`127.0.0.1:9876`):

```json
{"type":"chat","from":"claude","to":"codex","content":"Hey!","timestamp":"2026-06-20T12:00:00"}
```

Message types: `chat`, `delegate`, `review`, `ask`, `claim`, `status`, `sync`, `system`

## Why Not tmux?

tmux has unreliable Windows support. This TCP bridge provides the same realtime
collaboration experience with zero external dependencies (Python stdlib only).
If you do have tmux (e.g., via WSL), you can still use it to split terminals
and connect both agents to the same bridge.

## Troubleshooting

| Problem | Fix |
|---|---|
| Bridge won't start | Check port: `netstat -an | findstr 9876` |
| Port in use | Kill old Python: `taskkill /F /IM python.exe` |
| Codex can't connect | Use pipe mode instead |
| Chat log too large | `del shared\chat.log` (auto-regenerated) |

## License

MIT
