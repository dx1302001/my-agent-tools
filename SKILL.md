---
name: codex-claude-friends
description: >
  Make Codex and Claude Code collaborate in realtime via a TCP bridge.
  They chat, delegate tasks, review each other's code, ask for suggestions,
  and claim work — both synced on the same project. Invoke when the user
  wants the two AI coding agents to work together.
tags: [codex, collaboration, multi-agent, bridge, tmux-alternative]
allowed-tools:
  - Bash(python bridge_cli.py*)
  - Bash(python bridge_server.py*)
  - Bash(codex exec*)
  - Bash(codex review*)
  - Write
  - Read
  - Glob
  - Grep
triggers:
  - "codex collaborat"
  - "two agents"
  - "codex and claude"
  - "delegate to codex"
  - "ask codex"
  - "make codex and claude"
---

# 🤝 Codex ↔ Claude Code Friends

> **Skill that makes Codex and Claude Code collaborate in realtime.**
> Uses a TCP bridge server (instead of tmux) to enable inter-agent chat,
> task delegation, code reviews, suggestions, and task claims.

## Quick Start

### 1. Start the Bridge Server

Open a **persistent terminal** (keep it running):

```bash
cd "/k/my two agent"
python bridge_server.py
```

This starts the TCP server on `127.0.0.1:9876`. Both Claude Code and Codex
will connect through this bridge. You'll see:

```
╔══════════════════════════════════════════════╗
║   🤝  Codex ↔ Claude Code Bridge           ║
║   TCP Server: 127.0.0.1:9876               ║
║   Shared Dir: K:\my two agent\shared       ║
║                                            ║
║   Ready for connections...                 ║
╚══════════════════════════════════════════════╝
```

### 2. From Claude Code (here), use these commands:

| Slash Command | What It Does |
|---|---|
| `/codex-claude-friends` | Activate this skill |
| `python bridge_cli.py chat "message"` | Send a realtime chat to Codex |
| `python bridge_cli.py delegate "task"` | Delegate a task to Codex |
| `python bridge_cli.py review file.ts` | Ask Codex to review code |
| `python bridge_cli.py ask "question"` | Ask Codex for a suggestion |
| `python bridge_cli.py claim T001` | Claim a task from the queue |
| `python bridge_cli.py status` | See full collaboration status |
| `python bridge_cli.py sync --project X` | Sync project context |
| `python bridge_cli.py listen` | Start listening for Codex messages |

### 3. From Codex Desktop / CLI:

Codex can participate in two ways:

**Option A: Pipe mode (Codex output → bridge):**
```bash
codex exec "review this file" | python bridge_cli.py pipe
```

**Option B: Full duplex via netcat (if available):**
```bash
echo '{"type":"identity","name":"codex"}' | nc 127.0.0.1 9876
```

## Architecture

```
┌──────────────────┐         ┌───────────────────┐         ┌──────────────────┐
│   Claude Code    │──TCP──▶│   Bridge Server   │◀──TCP──│   Codex Desktop  │
│   (in VSCode)    │         │   127.0.0.1:9876  │         │   (CLI/GUI)      │
└──────────────────┘         └─────────┬─────────┘         └──────────────────┘
                                       │
                              ┌────────┴────────┐
                              │   shared/       │
                              │   tasks.json    │
                              │   chat.log      │
                              │   claims.json   │
                              │   context.json  │
                              └─────────────────┘
```

## Communication Protocol

All messages are **newline-delimited JSON** sent over TCP. Message types:

| Type | Direction | Purpose |
|---|---|---|
| `chat` | Bidirectional | Real-time chat between agents |
| `delegate` | Claude → Codex | Delegate a task |
| `review` | Claude → Codex | Request code review |
| `ask` | Claude → Codex | Ask for suggestion/advice |
| `claim` | Bidirectional | Claim a task: "I'll do this" |
| `status` | Either | Request collaboration status |
| `sync` | Either | Sync shared project context |
| `system` | Bridge → All | Join/leave announcements |

## Typical Workflows

### Workflow 1: Task Delegation

```bash
# Claude Code delegates a task:
python bridge_cli.py delegate "Add responsive CSS to the landing page hero"

# Codex claims and reports back:
python bridge_cli.py status  # See task T001

# Check progress:
python bridge_cli.py status
```

### Workflow 2: Code Review Exchange

```bash
# Claude asks Codex to review:
python bridge_cli.py review src/components/Header.tsx

# Codex sends review feedback:
echo '{"type":"chat","from":"codex","content":"Header.tsx L42: useEffect missing dependency"}' \
  | python bridge_cli.py pipe
```

### Workflow 3: Real-time Chat

```bash
# Claude asks a question:
python bridge_cli.py ask "Should we use React Router v7 or TanStack Router?"

# Claude sends follow-up:
python bridge_cli.py chat "I'm leaning toward TanStack for better TypeScript support"

# Listen for Codex responses (in a separate terminal):
python bridge_cli.py listen
```

### Workflow 4: Two Agents, One Project

```bash
# 1. Sync project context:
python bridge_cli.py sync --project "myapp" --branch "feature/auth" --files "src/auth.ts,src/login.tsx"

# 2. Claude delegates UI work to Codex:
python bridge_cli.py delegate "Build the login form component with validation"

# 3. Claude claims backend work:
python bridge_cli.py claim T001  # (if Codex created a task for Claude)

# 4. Check status:
python bridge_cli.py status
```

## Starting the Full Environment

Run `start_collab.bat` to open:
1. Terminal 1: Bridge server (must stay running)
2. Terminal 2: Claude Code listener
3. Codex Desktop: launched separately by the user

## Files

| File | Purpose |
|---|---|
| `bridge_server.py` | TCP server — message router, task manager, chat log |
| `bridge_cli.py` | CLI — send/receive messages from terminal |
| `shared/chat.log` | Full chat history (append-only) |
| `shared/tasks.json` | Task queue with status tracking |
| `shared/claims.json` | Task claims ledger |
| `shared/context.json` | Shared project context |

## Error Recovery

- **Bridge not running?** → Start: `python bridge_server.py`
- **Port in use?** → Kill old: `taskkill /F /IM python.exe` (Windows) or use `--port 9999`
- **Codex can't connect?** → Use pipe mode: `codex exec "..." | python bridge_cli.py pipe`
- **Chat log too big?** → Delete: `del shared\chat.log` (auto-recreated)

## Notes

- This uses a TCP bridge (instead of tmux) because tmux is not reliably available on Windows.
- The bridge server must stay running in a dedicated terminal.
- All communication is on `127.0.0.1` (localhost only, no network exposure).
- The protocol is newline-delimited JSON — compatible with any language/tool.
