# `map.md` — the environment map actionplan reads

Copy this file to `map.md` in your project root and fill it in. It is the optional input
named in this skill's Inputs: every value you supply here is a value the runbook does not
have to leave as a `<PLACEHOLDER>` and does not have to ask you for.

**The one law: credentials go in by REFERENCE, never by value.** A hostname is a fact; a
password is a liability. Name *where the secret lives* — the vault item, the env var, the
key file, the person who holds it — and the runbook will emit the lookup instead of the
value. `map.md` gets read into a session, copied into a runbook, and pasted into a chat by
someone who forgot what was in it. Nothing in it should ever need rotating.

Delete rows you don't have rather than guessing. **An unknown is more useful than a wrong
answer** — an empty cell becomes a `<PLACEHOLDER>` and a question; a wrong hostname
becomes the right command on the wrong machine.

---

## Hosts

| Name (used in the runbook) | Address | OS / version | Reach it by | Sudo? |
|---|---|---|---|---|
| `<NAME>` | | | | yes / no / partial |

## Services

| Service | Runs on | Managed by | Start / stop / status |
|---|---|---|---|
| | | systemd / launchd / docker / k8s / pm2 / … | |

## Paths that matter

| What | Path | On host | Notes |
|---|---|---|---|
| app root | | | |
| config | | | |
| logs | | | |
| data / volumes | | | |
| backups | | | free space? retention? |

## Credentials — by reference only

**Never paste a value into this table.** One row per credential the work will need.

| What it opens | Where it lives (the reference) | How to fetch it at run time |
|---|---|---|
| | 1Password vault "…" item "…" / `~/.pgpass` / CI secret `…` / KMS key `…` / a named person | `op read "op://…"` / `export X=$(…)` / "ask <role>" |

## Connectivity & constraints

- **Internet:** online / restricted egress / offline / air-gapped
- **If not fully online:** what must be pre-downloaded and carried in
- **Change windows / freezes:**
- **Who must approve a production change:**

## Tooling & versions already installed

| Tool | Version | On which hosts |
|---|---|---|

## Known-unknown list

Anything you could not fill in, so the runbook flags it instead of assuming it.

- 

---

## Filled example

*(A small two-host web app. Note that no secret value appears anywhere — only the place to
get each one.)*

### Hosts

| Name (used in the runbook) | Address | OS / version | Reach it by | Sudo? |
|---|---|---|---|---|
| `<APP_HOST>` | app01.internal (10.0.3.11) | Ubuntu 22.04 LTS | `ssh deploy@app01.internal` (key `~/.ssh/id_deploy`) | yes, passwordless |
| `<DB_HOST>` | db01.internal (10.0.3.20) | managed Postgres 16 | `psql` from app01 only — no shell | no shell access |

### Services

| Service | Runs on | Managed by | Start / stop / status |
|---|---|---|---|
| myapp (web) | `<APP_HOST>` | systemd unit `myapp.service` | `sudo systemctl {start,stop,status} myapp` |
| nginx | `<APP_HOST>` | systemd unit `nginx.service` | `sudo systemctl reload nginx` |

### Paths that matter

| What | Path | On host | Notes |
|---|---|---|---|
| app root | `/srv/myapp/current` | `<APP_HOST>` | symlink to the active release |
| config | `/etc/myapp/app.env` | `<APP_HOST>` | root:myapp 0640 — holds refs, not values |
| logs | `/var/log/myapp/` | `<APP_HOST>` | journald also carries the unit |
| backups | `/var/backups/myapp/` | `<APP_HOST>` | 40 GB free, 7-day retention |

### Credentials — by reference only

| What it opens | Where it lives (the reference) | How to fetch it at run time |
|---|---|---|
| Postgres admin role `<DB_ADMIN>` | 1Password vault "Infra" → item "db01 admin" | `op read "op://Infra/db01 admin/password"` |
| deploy SSH key | `~/.ssh/id_deploy` on the operator's laptop | already loaded in the agent — `ssh-add -l` |
| app runtime secrets | `/etc/myapp/app.env` (read by systemd `EnvironmentFile=`) | never printed; the unit reads it |

### Connectivity & constraints

- **Internet:** restricted egress — app01 reaches the internal package mirror only
- **If not fully online:** any new `.deb` or wheel must be staged on the mirror first
- **Change windows / freezes:** production changes Tue–Thu 07:00–09:00 UTC
- **Who must approve a production change:** the on-call SRE (rota in the ops channel topic)

### Tooling & versions already installed

| Tool | Version | On which hosts |
|---|---|---|
| psql (client) | 16.2 | `<APP_HOST>` |
| pg_dump | 16.2 | `<APP_HOST>` |
| jq | 1.6 | `<APP_HOST>` |

### Known-unknown list

- Whether the managed Postgres allows `CREATE EXTENSION` — ask the DBA before the schema step.
- Actual free space on `/var/backups` at run time; the 40 GB figure is from last month.
