#!/bin/bash
# oracle-suite tombstone SessionStart hook — the migration notice, and nothing else.
# The plugin `oracle-suite` was renamed to `notrest`. This stub exists ONLY so machines
# that already installed oracle-suite are told where the harness went instead of being
# stranded on a dead id. One line, no state, no side effects, never fails a session.
echo '[oracle-suite] This plugin was renamed to "notrest". Install the harness with: claude plugin install notrest@notrest — then uninstall oracle-suite.'
exit 0
