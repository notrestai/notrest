#!/bin/bash
# notrest tombstone SessionStart hook — the "where it went" notice, and nothing else.
# From v4.8.0 the notrest harness is part of Atlas: the repository is private and an
# install needs both repository access and an owner-issued access key. This stub exists
# ONLY so machines holding the last open release are told where the harness went instead
# of being stranded on a marketplace that no longer answers them. It says nothing about
# the copy they already have — that copy was released under MIT and stays theirs.
# One line, no state, no side effects, never fails a session.
echo '[notrest-free] The notrest harness is part of Atlas from v4.8.0 — the repo is private and an install needs repo access plus an owner-issued access key at ~/.notrest/access-key. Ask for access at https://do.not.rest. The v4.7.1 copy you have was released under the MIT License and remains yours under it.'
exit 0
