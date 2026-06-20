@echo off
chcp 65001 >nul
cd /d "K:\my two agent"

echo.
echo ╔══════════════════════════════════════════════╗
echo ║   🤝  Codex ↔ Claude Code Collaboration    ║
echo ╚══════════════════════════════════════════════╝
echo.
echo Starting bridge server...

start "🤝 Bridge Server" cmd /k "cd /d K:\my two agent && python bridge_server.py"

timeout /t 2 >nul

echo.
echo Bridge server started on 127.0.0.1:9876
echo.
echo ────────────────────────────────────────────
echo.
echo Next steps:
echo   1. Keep this bridge terminal running
echo   2. Open Codex Desktop and start working
echo   3. In Claude Code, type /codex-claude-friends
echo   4. Use python bridge_cli.py to communicate
echo.
echo Quick commands:
echo   python bridge_cli.py chat "Hello Codex!"
echo   python bridge_cli.py delegate "Task description"
echo   python bridge_cli.py status
echo.
echo ────────────────────────────────────────────
echo.
echo Opening listener in new terminal...

start "👂 Claude Listener" cmd /k "cd /d K:\my two agent && python bridge_cli.py listen"

echo.
echo Codex Pipe Mode (use in Codex terminal):
echo   codex exec "your prompt" ^| python bridge_cli.py pipe
echo.
echo ✅ Collaboration environment ready!
echo.
pause
