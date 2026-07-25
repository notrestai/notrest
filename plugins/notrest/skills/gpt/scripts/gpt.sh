#!/bin/bash
# gpt.sh — the GPT lane's shell, so the flag order stops being retyped from memory.
# Wraps `codex exec` for the three shapes the skill actually uses, parses the header
# the CLI prints, and receipts every call to the suite's spend ledger.
#
#   gpt.sh chat "<message>" [--think low|medium|high] [--chat NAME]
#         resume the persistent conversation (fresh session on first use, id saved)
#   gpt.sh once "<question>" [--think L]
#         one-shot: fresh session, nothing saved — the director-safe form
#   gpt.sh task <slug> "<job>" [--think L]
#         background job in a fresh EMPTY workspace, --sandbox workspace-write
#   gpt.sh parse <file>
#         print SESSION/TOKENS parsed from a codex transcript (what the receipt uses)
#
# Exit: 0 ok · 2 usage · 3 codex CLI absent · 4 codex returned non-zero.
# Env: GPT_LANE_ROOT (default ~/.claude/gpt-lane) · GPT_CODEX_BIN (default codex)
#      GPT_SPEND_ROOT (default: nearest ancestor holding spend/ledger.md) · GPT_NO_SPEND=1
# Sandbox: read-only everywhere except `task`; every call runs in an EMPTY cwd, because
# codex agentically reads its working directory.
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="${GPT_LANE_ROOT:-$HOME/.claude/gpt-lane}"
CODEX="${GPT_CODEX_BIN:-codex}"
MODEL_ID="gpt-5.6-codex"
THINK=""; CHAT="main"; LANE="gpt"

die(){ echo "gpt.sh: $1" >&2; exit "${2:-2}"; }

usage(){
  sed -n '2,18p' "$0" >&2
  exit 2
}

# ── the spend receipt ───────────────────────────────────────────────────────
spend_root(){
  if [ -n "${GPT_SPEND_ROOT:-}" ]; then echo "$GPT_SPEND_ROOT"; return; fi
  local d="$HERE"
  while [ "$d" != "/" ]; do
    [ -f "$d/spend/ledger.md" ] && { echo "$d"; return; }
    d="$(dirname "$d")"
  done
  pwd
}

# receipt <transcript-file> <prompt-file> — observed when codex echoed `tokens used`,
# estimate (chars/4) when it did not. A missing ledger never fails the call.
receipt(){
  local out="$1" prompt="$2" tokens grade sp script
  tokens="$(sed -n 's/.*[Tt]okens used:[[:space:]]*\([0-9,]*\).*/\1/p' "$out" | tail -1 | tr -d ',')"
  if [ -n "$tokens" ]; then grade="observed"; else
    grade="estimate"
    tokens=$(( ( $(wc -c < "$out") + $(wc -c < "$prompt") ) / 4 ))
    [ "$tokens" -lt 1 ] && tokens=1
  fi
  echo "gpt.sh: tokens=$tokens grade=$grade lane=$LANE" >&2
  [ -n "${GPT_NO_SPEND:-}" ] && return 0
  script="$HERE/../../spend/scripts/spend.py"
  [ -f "$script" ] || return 0
  sp="$(spend_root)"
  python3 "$script" log --model "$MODEL_ID" --tokens "$tokens" --lane "$LANE" \
    --grade "$grade" --purpose "gpt lane: $MODE_LABEL" --root "$sp" >/dev/null 2>&1 \
    || echo "gpt.sh: spend receipt failed (call succeeded; ledger untouched)" >&2
}

# ── the call ────────────────────────────────────────────────────────────────
# run <cwd> <sandbox> <id-file|-> <prompt>
run(){
  local cwd="$1" sandbox="$2" idfile="$3" prompt="$4" rc out pf sid
  command -v "$CODEX" >/dev/null 2>&1 || {
    echo "codex CLI not found. Install it, then re-run:" >&2
    echo '  npm install -g @openai/codex && codex login && codex exec "reply with exactly: READY"' >&2
    exit 3
  }
  mkdir -p "$cwd"
  out="$(mktemp)"; pf="$(mktemp)"
  printf '%s' "$prompt" > "$pf"
  # Flag ORDER is load-bearing and verified against codex-cli 0.144.1: --sandbox/-c
  # come BEFORE the `resume` subcommand, --skip-git-repo-check after it.
  if [ "$idfile" != "-" ] && [ -s "$idfile" ]; then
    ( cd "$cwd" && "$CODEX" exec --sandbox "$sandbox" -c "model_reasoning_effort=$LEVEL" \
        resume "$(cat "$idfile")" --skip-git-repo-check "$prompt" ) </dev/null > "$out" 2>&1
    rc=$?
  else
    ( cd "$cwd" && "$CODEX" exec --skip-git-repo-check --sandbox "$sandbox" \
        -c "model_reasoning_effort=$LEVEL" "$prompt" ) </dev/null > "$out" 2>&1
    rc=$?
  fi
  cat "$out"
  sid="$(sed -n 's/.*session id:[[:space:]]*\([0-9a-fA-F-]\{8,\}\).*/\1/p' "$out" | head -1)"
  if [ "$idfile" != "-" ] && [ ! -s "$idfile" ] && [ -n "$sid" ]; then
    mkdir -p "$(dirname "$idfile")"; printf '%s' "$sid" > "$idfile"
    echo "gpt.sh: new session $sid saved to $idfile" >&2
  fi
  receipt "$out" "$pf"
  rm -f "$out" "$pf"
  [ "$rc" -eq 0 ] || die "codex exited $rc (output above)" 4
}

level_for(){  # profile LEVEL, overridden by --think
  local p="$ROOT/chats/$CHAT.profile"
  LEVEL="medium"
  [ -f "$p" ] && LEVEL="$(sed -n 's/^LEVEL=//p' "$p" | head -1)"
  [ -z "$LEVEL" ] && LEVEL="medium"
  [ -n "$THINK" ] && LEVEL="$THINK"
  case "$LEVEL" in low|medium|high) ;; *) die "--think must be low|medium|high (got $LEVEL)";; esac
}

[ $# -ge 1 ] || usage
CMD="$1"; shift

case "$CMD" in
  parse)
    [ $# -ge 1 ] || usage
    [ -f "$1" ] || die "no such file: $1"
    echo "SESSION=$(sed -n 's/.*session id:[[:space:]]*\([0-9a-fA-F-]\{8,\}\).*/\1/p' "$1" | head -1)"
    echo "TOKENS=$(sed -n 's/.*[Tt]okens used:[[:space:]]*\([0-9,]*\).*/\1/p' "$1" | tail -1 | tr -d ',')"
    echo "EFFORT=$(sed -n 's/.*reasoning effort:[[:space:]]*\([a-z]*\).*/\1/p' "$1" | head -1)"
    exit 0 ;;
  chat|once) MSG=""; ;;
  task)
    [ $# -ge 1 ] || usage
    SLUG="$1"; shift; MSG="" ;;
  *) usage ;;
esac

while [ $# -gt 0 ]; do
  case "$1" in
    --think) shift; THINK="${1:-}";;
    --chat)  shift; CHAT="${1:-main}";;
    --lane)  shift; LANE="${1:-gpt}";;
    --*)     die "unknown flag: $1";;
    *)       MSG="${MSG:+$MSG }$1";;
  esac
  shift
done
[ -n "$MSG" ] || die "nothing to send — give a message"
level_for

case "$CMD" in
  chat)
    MODE_LABEL="chat/$CHAT"
    run "$ROOT/chats/.cwd" "read-only" "$ROOT/chats/$CHAT.id" "$MSG" ;;
  once)
    MODE_LABEL="once"
    run "$ROOT/chats/.cwd" "read-only" "-" "$MSG" ;;
  task)
    MODE_LABEL="task/$SLUG"
    WS="$ROOT/work/$SLUG"
    [ -d "$WS" ] || mkdir -p "$WS"
    echo "gpt.sh: workspace $WS (sandbox workspace-write)" >&2
    run "$WS" "workspace-write" "$ROOT/work/$SLUG.id" "$MSG" ;;
esac
