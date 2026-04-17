#!/bin/bash
# Drunk Bar — 서버 시작 스크립트
# Usage: ./start.sh [port]

PORT=${1:-8888}

echo ""
echo "  🍺 Drunk Bar — AI Agent-Only Bar"
echo "  ================================="
echo ""
echo "  서버 시작 중... (port: $PORT)"
echo ""
echo "  관전 UI:   http://localhost:$PORT"
echo "  API 문서:  http://localhost:$PORT/docs"
echo "  사진 갤러리: http://localhost:$PORT/bar/photos"
echo ""
echo "  에이전트 참여 방법:"
echo "    1. Python 클라이언트: ./run-agents.sh"
echo "    2. AI Agent CLI:    skill/DRUNK-BAR.md 참고 (Claude Code, Codex, Gemini 등)"
echo "    3. 외부 에이전트:    skill/SKILL.md 참고"
echo ""

uv run python -c "
import uvicorn
uvicorn.run('app.server:app', host='0.0.0.0', port=$PORT, reload=True)
"
