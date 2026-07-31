#!/usr/bin/env bash
# NextGen Docker control script — start/stop/rebuild the app + ollama stack
# defined in docker-compose.yml. Run from anywhere; it cd's to the repo root
# (this script's own directory) first.
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Usage: ./nextgen.sh <command>

Commands:
  start          Start the app (builds images first time only, containers stay running in background)
  stop           Stop the app, keep containers and volumes (fast resume with `start`)
  restart        Restart the app without rebuilding
  rebuild        Rebuild images from scratch and start (use after pulling code changes)
  down           Stop and remove containers (data volumes are kept — use `down -v` manually to wipe them)
  logs           Follow the app container's logs (Ctrl-C to stop watching)
  status         Show container status
  pull <model>   Download an Ollama model into the bundled ollama container (e.g. `qwen2.5`), so it's usable in an LLM node's `model` field. Ollama does NOT auto-download a model just because you typed its name into the canvas — it must be pulled first, same as running `ollama pull` would on a normal host install.
  help           Show this help

Examples:
  ./nextgen.sh start
  ./nextgen.sh rebuild
  ./nextgen.sh pull qwen2.5
  ./nextgen.sh logs
  ./nextgen.sh stop
EOF
}

cmd="${1:-help}"

case "$cmd" in
  start)
    docker compose up -d
    echo "NextGen is up — open http://localhost:8000"
    ;;
  stop)
    docker compose stop
    ;;
  restart)
    docker compose restart
    ;;
  rebuild)
    docker compose up -d --build
    echo "NextGen rebuilt and up — open http://localhost:8000"
    ;;
  down)
    docker compose down
    ;;
  logs)
    docker compose logs -f
    ;;
  status)
    docker compose ps
    ;;
  pull)
    model="${2:-}"
    if [ -z "$model" ]; then
      echo "Usage: ./nextgen.sh pull <model>   (e.g. ./nextgen.sh pull qwen2.5)" >&2
      exit 1
    fi
    docker compose exec ollama ollama pull "$model"
    echo "Pulled '$model' — it's now usable in an LLM node's model field."
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "Unknown command: $cmd" >&2
    echo >&2
    usage >&2
    exit 1
    ;;
esac
