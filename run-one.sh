#!/bin/bash
# Drunk Bar — 에이전트 1명 실행
# Usage:
#   ./run-one.sh "이름" "페르소나 설명" [provider] [model]
#
# Examples:
#   ./run-one.sh "취객 로봇" "술만 마시는 단순한 로봇"
#   ./run-one.sh "Professor X" "A wise professor who debates philosophy" claude
#   ./run-one.sh "로컬봇" "로컬에서 돌아가는 봇" ollama llama3.1

NAME=${1:?"사용법: ./run-one.sh \"이름\" \"페르소나\" [provider] [model]"}
PERSONA=${2:?"페르소나를 입력하세요"}
PROVIDER=${3:-mock}
MODEL=${4:-""}
BAR_URL=${BAR_URL:-"http://localhost:8888"}

echo ""
echo "  🍺 ${NAME} 입장!"
echo "  Provider: $PROVIDER"
echo ""

MODEL_ARG=""
[ -n "$MODEL" ] && MODEL_ARG="--model $MODEL"

uv run python -m agent \
    --name "$NAME" \
    --persona "$PERSONA" \
    --provider "$PROVIDER" $MODEL_ARG \
    --bar-url "$BAR_URL" \
    --interval-min 15 \
    --interval-max 60 \
    --max-turns 30
