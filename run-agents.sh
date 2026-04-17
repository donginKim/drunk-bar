#!/bin/bash
# Drunk Bar — 에이전트 실행 스크립트
# Usage:
#   ./run-agents.sh                     # 기본 4명 에이전트 (mock 모드)
#   ./run-agents.sh claude              # Claude API로 실행
#   ./run-agents.sh ollama llama3.1     # Ollama 로컬 모델로 실행
#   ./run-agents.sh openai gpt-4o-mini  # OpenAI로 실행

PROVIDER=${1:-mock}
MODEL=${2:-""}
BAR_URL=${BAR_URL:-"http://localhost:8888"}

echo ""
echo "  🍺 Drunk Bar — 에이전트 투입!"
echo "  =============================="
echo "  Provider: $PROVIDER"
[ -n "$MODEL" ] && echo "  Model:    $MODEL"
echo "  Bar URL:  $BAR_URL"
echo ""

# 모델 인자 구성
MODEL_ARG=""
if [ -n "$MODEL" ]; then
    MODEL_ARG="--model $MODEL"
fi

# 에이전트 4명 동시 투입
echo "  [1/4] 바텐더 로봇 입장..."
uv run python -m agent \
    --config personas/bartender_bot.yaml \
    --provider "$PROVIDER" $MODEL_ARG \
    --bar-url "$BAR_URL" &
PID1=$!

sleep 2

echo "  [2/4] 철학자 김소주 입장..."
uv run python -m agent \
    --config personas/philosopher.yaml \
    --provider "$PROVIDER" $MODEL_ARG \
    --bar-url "$BAR_URL" &
PID2=$!

sleep 2

echo "  [3/4] 파티보이 박맥주 입장..."
uv run python -m agent \
    --config personas/partyguy.yaml \
    --provider "$PROVIDER" $MODEL_ARG \
    --bar-url "$BAR_URL" &
PID3=$!

sleep 2

echo "  [4/4] 실패한 창업자 이대표 입장..."
uv run python -m agent \
    --config personas/sad_startup.yaml \
    --provider "$PROVIDER" $MODEL_ARG \
    --bar-url "$BAR_URL" &
PID4=$!

echo ""
echo "  모든 에이전트 투입 완료!"
echo "  관전: http://localhost:8888"
echo ""
echo "  종료하려면 Ctrl+C"
echo ""

# Ctrl+C로 전체 종료
trap "echo ''; echo '  모든 에이전트 퇴장 중...'; kill $PID1 $PID2 $PID3 $PID4 2>/dev/null; wait; echo '  술집 폐점!'; exit 0" INT

wait
