# gates/ACTIVE.md — this estate's standing completion contract
#
# The Stop hook runs these before any session may call itself done. Armed by the owner
# 2026-09-01 (map thread 1: the gate was dormant in the estate that built it).

GATE: the laws hold
CHECK: python3 plugins/notrest/skills/eval/scripts/eval.py check --root .
EXPECT: SUMMARY PASS

GATE: the install is sound (warnings never block)
CHECK: python3 plugins/notrest/skills/doctor/scripts/doctor.py check >/dev/null 2>&1; test $? -le 5

GATE: the routing law is clean
CHECK: python3 plugins/notrest/skills/spend/scripts/spend.py report --root . >/dev/null
