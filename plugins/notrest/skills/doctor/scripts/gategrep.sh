#!/bin/bash
# gategrep.sh — count a phrase in a file the way a READER sees it, not the way
# grep sees it. Markdown wraps: a phrase that lives on one visual line is split
# across two source lines, so line-oriented grep reports a false zero and a gate
# "fails" on text that is present. This normalizes first — every run of
# whitespace (newlines included) collapses to a single space — then counts
# case-sensitive, non-overlapping occurrences.
#
#   gategrep.sh <file> <phrase> [expected-count]
#
# prints: N (expected M) PASS|FAIL     — M is "≥1" when no count is given
# exit:   0 match · 1 mismatch · 2 usage
set -uo pipefail

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
  printf '%s\n' \
    "usage: gategrep.sh <file> <phrase> [expected-count]" \
    "exit: 0 match / 1 mismatch / 2 usage" >&2
  exit 2
fi

FILE="$1"
PHRASE="$2"
EXPECTED="${3:-}"

[ -f "$FILE" ] || { echo "gategrep: no such file: $FILE" >&2; exit 2; }
[ -n "$PHRASE" ] || { echo "gategrep: empty phrase" >&2; exit 2; }
if [ -n "$EXPECTED" ]; then
  case "$EXPECTED" in ''|*[!0-9]*) echo "gategrep: expected-count must be a non-negative integer" >&2; exit 2 ;; esac
fi

python3 - "$FILE" "$PHRASE" "$EXPECTED" <<'PY'
import re, sys

path, phrase, expected = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
except Exception as e:
    print(f"gategrep: unreadable file: {e}", file=sys.stderr)
    sys.exit(2)

norm = re.sub(r"\s+", " ", text)
# the needle is normalized identically, so a multi-line phrase argument works too
needle = re.sub(r"\s+", " ", phrase).strip()
if not needle:
    print("gategrep: empty phrase after normalization", file=sys.stderr)
    sys.exit(2)

n = norm.count(needle)          # case-sensitive, non-overlapping
if expected == "":
    ok = n >= 1
    shown = "≥1"
else:
    ok = n == int(expected)
    shown = expected
print(f"{n} (expected {shown}) {'PASS' if ok else 'FAIL'}")
sys.exit(0 if ok else 1)
PY
