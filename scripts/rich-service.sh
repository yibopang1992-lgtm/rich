#!/usr/bin/env bash
set -euo pipefail

APP_NAME="rich-ashare-agent"
APP_MODULE="ashare_agent.apps.api.main:app"
HOST="${RICH_HOST:-0.0.0.0}"
PORT="${RICH_PORT:-8000}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
RUN_DIR="${ROOT_DIR}/.run"
LOG_DIR="${ROOT_DIR}/logs"
PID_FILE="${RUN_DIR}/${APP_NAME}.pid"
LOG_FILE="${LOG_DIR}/${APP_NAME}.log"
ENV_FILE="${ROOT_DIR}/.env"

mkdir -p "${RUN_DIR}" "${LOG_DIR}"

load_env() {
  if [[ -f "${ENV_FILE}" ]]; then
    local line key value
    while IFS= read -r line || [[ -n "${line}" ]]; do
      [[ -z "${line}" || "${line}" =~ ^[[:space:]]*# ]] && continue
      line="${line#export }"
      [[ "${line}" == *"="* ]] || continue
      key="${line%%=*}"
      value="${line#*=}"
      key="${key#"${key%%[![:space:]]*}"}"
      key="${key%"${key##*[![:space:]]}"}"
      [[ "${key}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
      if [[ "${value}" =~ ^\".*\"$ || "${value}" =~ ^\'.*\'$ ]]; then
        value="${value:1:${#value}-2}"
      fi
      export "${key}=${value}"
    done < "${ENV_FILE}"
  fi
}

python_bin() {
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
  elif command -v python >/dev/null 2>&1; then
    command -v python
  else
    echo "python3 or python is required" >&2
    exit 1
  fi
}

is_running() {
  [[ -f "${PID_FILE}" ]] || return 1
  local pid
  pid="$(cat "${PID_FILE}")"
  [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1
}

ensure_venv() {
  if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    "$(python_bin)" -m venv "${VENV_DIR}"
  fi

  PIP_USER=false "${VENV_DIR}/bin/python" -m pip install --upgrade pip setuptools wheel
  PIP_USER=false "${VENV_DIR}/bin/python" -m pip install -e ".[dev]"
}

start() {
  load_env
  if is_running; then
    echo "${APP_NAME} is already running: pid $(cat "${PID_FILE}")"
    return 0
  fi

  ensure_venv
  echo "Starting ${APP_NAME} on ${HOST}:${PORT}"
  cd "${ROOT_DIR}"
  nohup "${VENV_DIR}/bin/python" -m uvicorn "${APP_MODULE}" \
    --host "${HOST}" \
    --port "${PORT}" \
    >"${LOG_FILE}" 2>&1 &
  echo "$!" > "${PID_FILE}"
  sleep 1

  if is_running; then
    echo "${APP_NAME} started: pid $(cat "${PID_FILE}")"
    echo "Log: ${LOG_FILE}"
  else
    echo "${APP_NAME} failed to start. Last log lines:" >&2
    tail -n 80 "${LOG_FILE}" >&2 || true
    exit 1
  fi
}

stop() {
  if ! is_running; then
    echo "${APP_NAME} is not running"
    rm -f "${PID_FILE}"
    return 0
  fi

  local pid
  pid="$(cat "${PID_FILE}")"
  echo "Stopping ${APP_NAME}: pid ${pid}"
  kill "${pid}"

  for _ in {1..20}; do
    if ! kill -0 "${pid}" >/dev/null 2>&1; then
      rm -f "${PID_FILE}"
      echo "${APP_NAME} stopped"
      return 0
    fi
    sleep 0.5
  done

  echo "Force stopping ${APP_NAME}: pid ${pid}"
  kill -9 "${pid}" >/dev/null 2>&1 || true
  rm -f "${PID_FILE}"
}

status() {
  if is_running; then
    echo "${APP_NAME} is running: pid $(cat "${PID_FILE}")"
    echo "Health URL: http://${HOST}:${PORT}/health"
  else
    echo "${APP_NAME} is not running"
    return 1
  fi
}

logs() {
  touch "${LOG_FILE}"
  tail -n "${LINES:-120}" -f "${LOG_FILE}"
}

sync_data() {
  load_env
  ensure_venv
  cd "${ROOT_DIR}"
  "${VENV_DIR}/bin/python" -m ashare_agent.scripts.sync_market_data "${@:2}"
}

backfill_data() {
  load_env
  ensure_venv
  cd "${ROOT_DIR}"
  "${VENV_DIR}/bin/python" -m ashare_agent.scripts.backfill_recent_data "${@:2}"
}

case "${1:-start}" in
  start)
    start
    ;;
  stop)
    stop
    ;;
  restart)
    stop
    start
    ;;
  status)
    status
    ;;
  logs)
    logs
    ;;
  sync)
    sync_data "$@"
    ;;
  backfill)
    backfill_data "$@"
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|logs|sync|backfill}" >&2
    exit 2
    ;;
esac
