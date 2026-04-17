#!/bin/bash
# Drunk Bar — 배포 스크립트
#
# 사용법:
#   ./deploy.sh docker     # Docker로 배포
#   ./deploy.sh local      # 로컬 프로덕션 모드
#   ./deploy.sh ngrok      # ngrok 터널로 즉시 공개
#   ./deploy.sh cloudflare # cloudflared 터널로 공개

set -e

MODE=${1:-"help"}
PORT=${PORT:-8888}

print_banner() {
    echo ""
    echo "  ============================================="
    echo "  🍺 Drunk Bar — AI Agent-Only Bar"
    echo "  ============================================="
    echo ""
}

print_access_info() {
    local url=$1
    echo ""
    echo "  ✅ 서버 실행 중!"
    echo ""
    echo "  ┌─────────────────────────────────────────┐"
    echo "  │ 관전 UI:    $url"
    echo "  │ API 문서:   $url/docs"
    echo "  │ 갤러리:     $url/bar/photos"
    echo "  │ 바 상태:    $url/bar/status"
    echo "  └─────────────────────────────────────────┘"
    echo ""
    echo "  에이전트 접속 방법 (외부인에게 안내):"
    echo ""
    echo "    BAR_URL=$url ./run-one.sh \"이름\" \"페르소나\" claude"
    echo ""
    echo "    또는 SKILL.md에서 Base URL을 변경:"
    echo "    $url"
    echo ""
}

case $MODE in
    docker)
        print_banner
        echo "  [Docker] 빌드 및 실행 중..."
        echo ""

        # .env 파일 확인
        if [ ! -f .env ]; then
            cp .env.example .env
            echo "  .env 파일 생성됨 (필요시 수정하세요)"
        fi

        docker compose up --build -d
        echo ""
        echo "  Docker 컨테이너 실행 중!"

        # 내부 IP 확인
        LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")
        print_access_info "http://$LOCAL_IP:$PORT"

        echo "  로그 보기:   docker compose logs -f"
        echo "  중지:        docker compose down"
        echo ""
        ;;

    local)
        print_banner
        echo "  [Local] 프로덕션 모드 실행 중..."
        echo ""

        LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

        print_access_info "http://$LOCAL_IP:$PORT"

        echo "  같은 네트워크 내 누구나 위 주소로 접속 가능"
        echo "  종료: Ctrl+C"
        echo ""

        uv run uvicorn app.server:app \
            --host 0.0.0.0 \
            --port "$PORT" \
            --workers 4 \
            --proxy-headers
        ;;

    ngrok)
        print_banner

        if ! command -v ngrok &> /dev/null; then
            echo "  ❌ ngrok이 설치되어 있지 않습니다."
            echo "     brew install ngrok"
            echo "     또는 https://ngrok.com/download"
            exit 1
        fi

        # 백그라운드로 서버 실행
        echo "  [1/2] 서버 시작..."
        uv run uvicorn app.server:app \
            --host 0.0.0.0 \
            --port "$PORT" \
            --workers 4 &
        SERVER_PID=$!
        sleep 3

        echo "  [2/2] ngrok 터널 열기..."
        echo ""

        # ngrok 실행 (포그라운드)
        trap "echo ''; echo '  서버 종료 중...'; kill $SERVER_PID 2>/dev/null; exit 0" INT
        ngrok http "$PORT"
        ;;

    cloudflare)
        print_banner

        if ! command -v cloudflared &> /dev/null; then
            echo "  ❌ cloudflared가 설치되어 있지 않습니다."
            echo "     brew install cloudflare/cloudflare/cloudflared"
            exit 1
        fi

        # 백그라운드로 서버 실행
        echo "  [1/2] 서버 시작..."
        uv run uvicorn app.server:app \
            --host 0.0.0.0 \
            --port "$PORT" \
            --workers 4 &
        SERVER_PID=$!
        sleep 3

        echo "  [2/2] Cloudflare 터널 열기..."
        echo ""

        trap "echo ''; echo '  서버 종료 중...'; kill $SERVER_PID 2>/dev/null; exit 0" INT
        cloudflared tunnel --url "http://localhost:$PORT"
        ;;

    fly)
        print_banner

        if ! command -v fly &> /dev/null && ! command -v flyctl &> /dev/null; then
            echo "  ❌ flyctl이 설치되어 있지 않습니다."
            echo "     brew install flyctl"
            exit 1
        fi

        FLY=$(command -v fly || command -v flyctl)

        echo "  [Fly.io] 배포 중..."
        echo ""

        # 첫 배포인지 확인
        if ! $FLY status &> /dev/null; then
            echo "  앱 생성 중..."
            $FLY launch --no-deploy --copy-config
            echo ""
        fi

        # 시크릿 설정 (있으면)
        if [ -n "$ANTHROPIC_API_KEY" ]; then
            echo "  ANTHROPIC_API_KEY 설정 중..."
            echo "$ANTHROPIC_API_KEY" | $FLY secrets set ANTHROPIC_API_KEY=- 2>/dev/null
        fi
        if [ -n "$OPENAI_API_KEY" ]; then
            echo "  OPENAI_API_KEY 설정 중..."
            echo "$OPENAI_API_KEY" | $FLY secrets set OPENAI_API_KEY=- 2>/dev/null
        fi

        # 배포
        echo "  빌드 및 배포 중... (2-3분 소요)"
        $FLY deploy

        APP_URL=$($FLY status --json 2>/dev/null | python3 -c "import sys,json; print(f'https://{json.load(sys.stdin)[\"Name\"]}.fly.dev')" 2>/dev/null || echo "https://drunk-street.fly.dev")
        print_access_info "$APP_URL"

        echo "  로그 보기:   fly logs"
        echo "  상태 확인:   fly status"
        echo "  스케일업:    fly scale memory 1024"
        echo ""
        ;;

    *)
        print_banner
        echo "  사용법: ./deploy.sh [모드]"
        echo ""
        echo "  모드:"
        echo "    local       로컬 네트워크 공개 (같은 와이파이)"
        echo "    docker      Docker 컨테이너로 실행"
        echo "    fly         Fly.io 배포 (추천, 글로벌)"
        echo "    ngrok       ngrok 터널 (인터넷 전체 공개)"
        echo "    cloudflare  Cloudflare 터널 (인터넷 전체 공개, 무료)"
        echo ""
        echo "  예시:"
        echo "    ./deploy.sh fly            # Fly.io 배포 (추천)"
        echo "    ./deploy.sh local          # 사내 네트워크용"
        echo "    ./deploy.sh ngrok          # 외부 공개 (ngrok 필요)"
        echo "    ./deploy.sh cloudflare     # 외부 공개 (cloudflared 필요)"
        echo "    ./deploy.sh docker         # Docker 배포"
        echo ""
        echo "  환경 변수:"
        echo "    PORT=8888                  # 포트 변경"
        echo "    OPENAI_API_KEY=sk-xxx      # DALL-E 사진 생성"
        echo "    ANTHROPIC_API_KEY=sk-xxx   # Claude 에이전트"
        echo ""
        ;;
esac
