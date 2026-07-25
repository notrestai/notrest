#!/bin/bash
# render-check.sh — prove an HTML file actually serves, then hand the seat a URL.
#
# Opening a file:// path in the browser pane silently breaks fetches, module
# scripts and relative assets; this serves the file's own directory over
# 127.0.0.1 on a private port, curls it to prove HTTP 200, and prints the exact
# URL to open. The server is LEFT RUNNING (that is the point) — close it with
# --close <port>. Nothing is ever left orphaned on a failure path: the trap kills
# the child unless the 200 was proved.
#
#   render-check.sh <html-file> [port]    serve + prove + print URL (leaves it up)
#   render-check.sh --once <html-file> [port]   same, PID line labeled explicitly
#   render-check.sh --close <port>        kill the server on that port
#
# exit: 0 ok · 2 usage · 3 no free port in range · 4 served but not HTTP 200
set -uo pipefail

LO=8790
HI=8799

usage() {
  printf '%s\n' \
    "usage: render-check.sh <html-file> [port]" \
    "       render-check.sh --once <html-file> [port]" \
    "       render-check.sh --close <port>" \
    "port range: ${LO}-${HI} · exit 0 ok / 2 usage / 3 no free port / 4 not 200" >&2
}

# ── free port: bind-test each candidate (no SO_REUSEADDR — a listening socket
# must fail the bind, which is exactly the signal we want).
pick_port() {
  python3 - "$LO" "$HI" <<'PY'
import socket, sys
lo, hi = int(sys.argv[1]), int(sys.argv[2])
for p in range(lo, hi + 1):
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", p))
        print(p)
        sys.exit(0)
    except OSError:
        pass
    finally:
        try:
            s.close()
        except Exception:
            pass
sys.exit(3)
PY
}

close_port() {
  local port="$1" pids=""
  case "$port" in
    ''|*[!0-9]*) usage; exit 2 ;;
  esac
  pids="$(lsof -ti "tcp:${port}" -sTCP:LISTEN 2>/dev/null || true)"
  if [ -z "$pids" ]; then
    echo "render-check: nothing listening on ${port}"
    exit 0
  fi
  # shellcheck disable=SC2086
  kill $pids 2>/dev/null || true
  sleep 0.3
  # shellcheck disable=SC2086
  kill -9 $pids 2>/dev/null || true
  echo "render-check: closed ${port} (pids: $(echo $pids | tr '\n' ' '))"
  exit 0
}

MODE="serve"
case "${1:-}" in
  --close) shift; close_port "${1:-}" ;;
  --once)  MODE="once"; shift ;;
  -h|--help) usage; exit 2 ;;
  '') usage; exit 2 ;;
esac

FILE="${1:-}"
[ -z "$FILE" ] && { usage; exit 2; }
[ -f "$FILE" ] || { echo "render-check: no such file: $FILE" >&2; usage; exit 2; }

DIR="$(cd "$(dirname "$FILE")" && pwd)" || { echo "render-check: unreadable dir" >&2; exit 2; }
BASE="$(basename "$FILE")"

PORT="${2:-}"
if [ -n "$PORT" ]; then
  case "$PORT" in ''|*[!0-9]*) usage; exit 2 ;; esac
else
  PORT="$(pick_port)" || { echo "render-check: no free port in ${LO}-${HI}" >&2; exit 3; }
  [ -z "$PORT" ] && { echo "render-check: no free port in ${LO}-${HI}" >&2; exit 3; }
fi

python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$DIR" >/dev/null 2>&1 &
SRV=$!
# every abnormal exit from here on reaps the child — no orphans, ever.
trap 'kill "$SRV" 2>/dev/null; wait "$SRV" 2>/dev/null; exit' INT TERM
trap 'kill "$SRV" 2>/dev/null; wait "$SRV" 2>/dev/null' EXIT

URL="http://127.0.0.1:${PORT}/${BASE}"
CODE=""
for _ in $(seq 1 40); do
  kill -0 "$SRV" 2>/dev/null || break
  CODE="$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "$URL" 2>/dev/null || true)"
  [ "$CODE" = "200" ] && break
  sleep 0.25
done

if [ "$CODE" != "200" ]; then
  echo "render-check: FAIL — ${URL} returned '${CODE:-no-response}' (server killed)" >&2
  exit 4
fi

trap - EXIT INT TERM   # proved: hand the live server to the seat
echo "render-check: HTTP 200"
echo "URL:  $URL"
echo "PORT: $PORT"
echo "PID:  $SRV"
[ "$MODE" = "once" ] && echo "MODE: once (left running — reap with: render-check.sh --close $PORT)"
echo "close: render-check.sh --close $PORT"
exit 0
