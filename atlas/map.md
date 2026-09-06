# atlas/map.md — what this estate says it is building
#
# One PART per thing worth knowing the state of. The status is NOT what you write here:
# you write the CLAIM, atlas runs the TEST, and the status is derived from the exit code.
#
#   PART: <id> — <title>
#   CLAIM: done | wip | planned | blocked      (default: wip)
#   TEST: <a shell command that could fail>    (optional — but a done with no test is
#                                               demoted to wip and reported)
#   PATH: <where the code lives>               (optional, repeatable)
#
# Every gate in gates/ACTIVE.md is picked up automatically as a part CLAIMED done.
# Directives inside a fenced code block are documentation and are never run.

PART: example — replace me with a real part
CLAIM: planned
