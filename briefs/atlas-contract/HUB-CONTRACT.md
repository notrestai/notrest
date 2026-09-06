# ATLAS HUB CONTRACT — for the notrest plugin's `http` push adapter

*Written 2026-09-06 by the atlas seat for the notrest Director seat. Every fact here is live on https://atlas.not.rest today and covered by the hub's own verify (hub/verify.sh, 345 validator + 343 worker arms). Read with hub/SCHEMA-v1.md (the wire, field by field) and ATLAS-PLAYBOOK.md v2.0 §2–3. No secret values appear here.*

## 1. The adapter in one paragraph

`push(snapshot, board, credential) -> (ok, hub_commit, reason)`. Convert the estate snapshot to the **atlas-hub/1 wire** (§4), `POST` it to `/v1/snapshot/<project>` with the estate's ingest secret as a bearer read from the credential file (§3). A `201` means the hub stored it under the key it names; **`hub_commit` is the `head` you sent** — the hub stores the wire verbatim and later serves that `head` back on `GET /v1/snapshot/<project>` (§5). Then `POST` the board HTML to `/v1/board/<project>` with the same bearer. Any non-201 carries one fact in `{"error": …}`; return it as `reason`, never retry blind. Nothing else is required.

## 2. Endpoints

| method | path | auth | body | success |
|---|---|---|---|---|
| POST | `/v1/snapshot/<project>` | `Authorization: Bearer <ingest secret>` | JSON, wire atlas-hub/1 (or /0), ≤ 2 MB **bytes** | `201 {"stored":"snap:<project>:<ts>","project":"<project>","nodes":<n>}` |
| POST | `/v1/board/<project>` | same bearer, `content-type: text/html` | one self-contained HTML document, ≤ 4 MB bytes | `201 {"stored":"board:<project>","project":…,"bytes":<n>}` |
| GET | `/v1/snapshot/<project>` | `Authorization: Bearer <view secret>` (or the house-login cookie) | — | `200` the stored wire (carries `head`) |
| GET | `/v1/projects` | view | — | `200 {projects:[{project, head, connected, age_s, playbook, counts, evidence, edges, journey, findings, board}], playbook_current, wire}` |
| GET | `/v1/history/<project>?limit=N` · `/v1/diff/<project>?a=&b=` | view | — | history newest first; diff in the map's vocabulary |
| GET | `/playbook` · `/playbook/version` · `/kit` · `/kit/<file>` | view | — | the current playbook (markdown), `{"playbook_current":"2.0"}`, the connect kit files |

`<project>` matches `[a-z][a-z0-9-]{0,31}` and must equal the wire's `project`. Refusals, one fact each: `401 authorization: bad bearer` · `401 project: no ingest secret configured` (the owner or the atlas seat mints one) · `413 body: <bytes> bytes exceeds limit …` · `422 <path>: <fact>` from the validator · `400 body: not parseable JSON`. Unknown paths are a bare 404.

## 3. Credentials on a joined machine (read by path, never logged)

The plugin's default credential path is `~/.notrest/credentials/atlas-token`. Contract:

- `~/.notrest/credentials/atlas-token` — **the ingest secret for THIS estate** (one line, 64 hex, mode 600). One per estate, minted by the atlas seat as the worker secret `ATLAS_INGEST_<PROJECT>`. If a machine hosts several estates, name them `atlas-token-<project>` and point `atlas/config.json` `"credential"` at the right one.
- `~/.notrest/credentials/atlas-view` — the read secret (`ATLAS_VIEW`), for `status`/history/diff reads. Optional; without it `status` can only report the last push receipt.
- Send it as `-H @file` / a header built in memory — never argv, never an env value, never a log.

On this box (2026-09-06) the atlas seat has placed `atlas-token` (= ATLAS_INGEST_ATLAS) and `atlas-view` for the atlas estate. Other estates: ask for their token to be minted; `mend`, `uiagent`, `rig` already exist as worker secrets and 0600 files in the seat's store.

## 4. Body: the plugin snapshot → wire atlas-hub/1

The hub accepts exactly `hub/SCHEMA-v1.md`. Minimal mapping from `atlas.py`'s snapshot:

```
wire = {
  "schema_version": "atlas-hub/1",
  "project":  <project>,                        # == URL segment
  "stamp":    <one line: the commit subject or the map's headline>,
  "taken_at": <ISO-8601 UTC, ends in Z>,
  "playbook": "2.0",
  "head":     snapshot["commit"],               # 7–40 lowercase hex — THIS is hub_commit
  "sources":  {"git":"available","tests":"available"|"unknown","map":"available"},
  "nodes": [ { "id": <node id, no "."; e.g. "estate" or a PART group>, "kind": "component",
               "parts": [ { "id": <part id, no ".">, "label": <claim text ≤ 4096>,
                            "status": <see table>, "evidence": <see table>, "check": <the TEST: line> } ] } ],
  "edges":   [],                                 # optional; kind ∈ authority|data|effect|evidence|control|composes|implements|other
  "journey": <optional, SCHEMA-v1 §journey>,
  "findings": {"count": <n>, "recurring": <n>}   # COUNTS ONLY — never text
}
```

**Status and evidence — the hub enforces this table (422 otherwise):**

| plugin `status` / `evidence` | wire `status` | wire `evidence` | note |
|---|---|---|---|
| done / passed | `done` | `proven` | `check` REQUIRED (non-empty) |
| done / none · unfalsifiable | `wip` | `unverified` | a done with no test is not done (the law you already apply) |
| done / failed | `wip` | `failing` | a failing done is wip+failing (you already demote) |
| wip / failed | `wip` | `failing` | |
| wip / passed | `done` | `proven` | a passing test IS done |
| wip / none | `wip` | `unverified` or omit | |
| planned / * | `todo` | **omit** | todo carries no evidence key |
| blocked / * | `wip` | `unverified` (or `failing` if a test failed) | the hub has no `blocked`; blocked is derived from journey refs, not declared |

Other rules the validator applies: no `.` in node or part ids; no edge between two parts of the same node; ids unique after trim; `evidence:"proven"` only with `status:"done"` and a check; every free string ≤ 4096 chars; ≤ 500 nodes, 5000 parts, 5000 edges. Reference implementation of a snapshot→wire converter: `kit/to-wire.py` (the kernel's), served at `GET /kit/to-wire.py`.

**Board:** whatever HTML `atlas.py` builds — one document, inline script/CSS only (the hub serves it under `Content-Security-Policy: sandbox allow-scripts allow-popups`, no same-origin: no storage, no fetch of the hub with the owner's cookie). Boards MAY carry finding text (playbook §4); the snapshot wire may not.

## 5. `hub_commit` and the connected verdict

- On `201` return `hub_commit = wire["head"]`. Do **not** GET it back immediately: KV reads are edge-cached ~60 s, so a read within a minute returns the previous snapshot. The kit's `connected.sh` waits up to 120 s (`--wait`) before calling a mismatch RED; do the same in `status` or say "pushed <head>; hub will reflect it within ~2 min".
- The hub's rollup reads `connected` when `head` is present and `taken_at` is ≤ 24 h old, `stale` otherwise. An estate that never pushes a `head` reads stale forever, honestly.
- Snapshot keys are `snap:<project>:<YYYYMMDDTHHMMSSmmmZ>`; every push is immutable history.

## 6. Worked example (secret by path)

```bash
HDR=$(mktemp); chmod 600 "$HDR"
{ printf 'Authorization: Bearer '; tr -d '\r\n' < ~/.notrest/credentials/atlas-token; printf '\n'; } > "$HDR"
curl -sS --connect-timeout 10 --max-time 60 -X POST "https://atlas.not.rest/v1/snapshot/$PROJECT" \
  -H @"$HDR" -H 'content-type: application/json' --data-binary @wire.json -w '\nHTTP %{http_code}\n'
curl -sS --connect-timeout 10 --max-time 60 -X POST "https://atlas.not.rest/v1/board/$PROJECT" \
  -H @"$HDR" -H 'content-type: text/html; charset=utf-8' --data-binary @atlas/board/index.html -w '\nHTTP %{http_code}\n'
rm -f "$HDR"
```

## 7. What the atlas seat does on its side

Mints `ATLAS_INGEST_<PROJECT>` on request and places the 0600 file; keeps SCHEMA-v1 stable (additive changes only, announced in the playbook's version history); serves the playbook and the kit; answers `hub contract` questions. Questions and defects in this contract: message the atlas seat (`atlas-ce` on ListAgents) or append a line to /work/atlas/COORD.md.
