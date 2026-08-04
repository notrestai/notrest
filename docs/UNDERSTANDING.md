# Understanding what we built

*Written 2026-07-28 for the owner. Plain language, complete, honest about what is
finished and what is not. If a sentence here disagrees with the code, the code wins and
this document is wrong — say so and it gets fixed.*

---

## 1. The problem this whole thing solves

An AI session has three flaws that have nothing to do with how smart the model is:

1. **It forgets.** Every session starts blank. Yesterday's decisions, the reason you
   rejected an approach, the thing that broke last time — gone.
2. **It claims.** "Done!" is cheap to say and expensive to check. Without a discipline,
   you get confident sentences and no evidence.
3. **Its work evaporates.** Helpers finish, their windows close, and what they found
   disappears with them.

Everything below is machinery for those three problems. Not smarter answers — *reliable*
ones, that survive the session that produced them.

---

## 2. The two things we built (keep these separate)

| | **notrest** | **rig.rest** |
|---|---|---|
| What it is | A Claude Code **plugin** — the engine | A **product** — a portal plus an app |
| Who uses it | You, on this machine, today | Other people, once you deploy it |
| Where it lives | `~/Desktop/oracle-suite-plugin` | `~/Desktop/rig.rest` |
| Status | Shipped, v3.16.0, running live | Built, gated, **not deployed** |

The plugin is the **engine**. The product is the **car built around it**. They are
deliberately separate repos with separate records — one is a tool you use, the other is a
business you might run.

---

## 3. The engine (notrest) — what each part does and why

### The estate — how it remembers

Plain files in your project folder. That folder *is* the memory; there is no database.

- **`COORD.md`** — one honest line per prompt: what was asked, what landed, the evidence.
  *Why:* so a session that dies mid-thought leaves a trail the next one can read.
- **`COORD-AGENTS.md`** — a receipt for every helper agent that finishes, written
  automatically. *Why:* helpers used to vanish with their findings.
- **`briefs/`** — the **exact prompt** given to every helper, banked automatically.
  *Why:* you asked to see what we ask our agents. Now it is on disk, not in a transcript.
- **`spend/ledger.md`** — what each helper cost and which model ran it. *Why:* the rule
  "only Opus does delegated work" becomes checkable instead of a promise.
- **`archive/findings.jsonl`** — the knowledge store. Each record is one finding: what was
  asked, what was found, the evidence with its source, and how it relates to the goal.
  A validator rejects malformed records at the door. *Why:* so knowledge outlives the
  session and can be searched instead of re-derived.

### The library — how knowledge crosses projects

Every project keeps its own store; a registry federates them. `library find <anything>`
searches **all** your projects in seconds at zero model cost, and one project's record can
cite another's. *Why:* the most expensive thing an AI does is re-learn what it already
knew somewhere else.

### The instruments — how it checks itself

- **`doctor`** (11 checks) — is the installation real? Right versions, hooks present,
  nothing shadowing the runtime, token budget respected.
- **`eval`** (12 checks) — are the laws still obeyed? Every rule we wrote must leave a
  visible fingerprint in the shipped files.
- **`pulse`** — one command that runs everything and writes one honest line. Scheduled
  daily; also runs at session start and session end.
- **`spend`** — proves model routing; exits angry if a rule was broken.

*Why:* a harness that can't audit itself is a story. These run in seconds and cost zero
model tokens.

### The pictures — how you see it

- **the river** — the session drawn as a river: the main channel toward the goal, side
  routes that merged back or dead-ended, loop arrows where we backtracked, **red rocks
  where something got refuted**, a flag for every ship.
- **the journey** — every skill, what phrase triggers it, and what it hands off to.
- **the graph** — the file map of the project.
- **the cockpit** — three views, one at a time, each owning the screen: river, file graph, coord. Opt a project in once (`serve --always`) and every session start surfaces it: probe, start if down, open it. Every view opens STAGED — the important thing first, the rest one click away — because a correct render nobody can read is a failed render.

*Why:* they are drawn **by scripts, not by the model** — a law we wrote deliberately. A
picture of a whole working day costs zero tokens.

### The gates — the rules with teeth

- A **push gate** physically blocks `git push` when the instruments are red.
- A **shadow guard** blocks the install flow that kept silently replacing the live plugin.
- A **router** reads each prompt and names the right specialist for the shape of work.

*Why:* rules that depend on remembering get forgotten. These don't ask.

### The 31 skills — the specialists

Research, decide, fact-check, red-team, plan, turn plans into commands, draft what you
send, watch facts for drift, recap the story, compile repeated work into scripts, run
multi-model rooms, beam work to the cloud, and the meta ones — `notrest` (establish the harness
in a project), `oracle` (start a session), `sessionend` (close one), `mentor` (teach
another session), `fable-mode` (the discipline).

---

## 4. The product (rig.rest) — what each part does and why

### The shape

A **portal** on Cloudflare serves the interface. The **agent** runs on the user's own
machine, against **one folder they choose**, using **their own model keys**. A **tunnel**
connects the two — outbound only, so nothing on their machine is ever publicly exposed.

*Why this shape:* their files never reach us. That is the product's whole promise, and it
also means no model costs and no data liability for you.

### The parts

- **The three-panel shell** — left: the tools; middle: the work (a live session, like the
  one you are in); right: the river and graph, always on, redrawing as work lands.
- **The session runner** — runs the model loop **inside the harness**, which is why we can
  count tokens and enforce your spend ceiling.
- **The connector** — official APIs, the user's own key. Nothing is proxied through us,
  and **no field anywhere can accept a key** (a lane attacked its own route with seven
  key-shaped fields to prove it).
- **Onboarding** — sign in, install the agent, grant one folder, connect models, and the
  first river draws itself.
- **Departure** — close the lid and the work banks losslessly; it resumes where it
  stopped. The promise is worded exactly: *"Closing the lid stops the work. Nothing is
  lost. It resumes where it stopped."*
- **Purge** — clears online traces and hands back a **receipt** of what was cleared.
- **On-device evidence** — lists every path written and every host contacted, so the
  privacy claim is demonstrable rather than asserted.
- **Entitlement and revocation** — sign-in issues a short-lived token (24h). Revoking a
  user drops their tunnel **at the edge**, without needing the agent's cooperation.

### The honest limits, stated on purpose

- **Revocation does not reach into a machine we don't own.** Someone determined can patch
  a local check. We disable the portal, the tunnel and the interface immediately, and the
  agent at its next check-in. We never touch their files.
- **Unreachable is not revoked.** If our portal is down, the agent says *unreachable* and
  keeps working until its token expires. It never tells a user they were revoked when we
  simply couldn't answer.
- **Prompts do go to the model vendor.** Results and the estate do not. "Nothing persists
  on our side" is the claim; "nothing touches the cloud" would be a lie.
- **A spend ceiling can be overshot by up to one turn**, because neither stop is a
  pre-spend bound.

---

## 5. How we got here — the build, in order

1. **Verified the handoff.** Re-ran every instrument before trusting a document.
2. **Cut the fat.** Per-session overhead measured and reduced ~29%.
3. **Found a real bug.** A duplicated line in the plugin manifest was registering every
   hook twice — the cause of a week of doubled messages and duplicate receipts.
4. **Moved to live-git.** The plugin now loads straight from the working tree; no frozen
   copies. (The `/plugin` panel can't show that kind of install — which is why notrest
   kept looking "missing" and got reinstalled, shadowing itself four times.)
5. **Gave routing teeth**, then **catalogued everything** — every skill, what it does, its
   biggest gap.
6. **Built the findings store and the river.** Knowledge became records; records became a
   picture.
7. **Closed eighteen gaps in one batch** — six parallel workers, one gate.
8. **Added the hard gate, the heartbeat, and beam**; proved `watch` live on real URLs.
9. **Federated the library** across projects; added concepts and convergence.
10. **Made commissions visible** — every agent's prompt banked automatically.
11. **Built the cockpit**, then **`mentor`** — turning the way we worked into a skill.
12. **Built rig.rest**: spec, SDK spike, shell, connector, cross-model resume **proven**,
    departure, purge, on-device evidence, portal, entitlement, tunnel pairing, install.

Fifteen-plus engine releases; one full product batch; every ship gated on instruments that
run in seconds.

---

## 6. Where it stands

**Done and running:** the engine (v3.22.0, 31 skills), all instruments green, the cockpit,
the estate, the library.

**Built and gated, not live:** rig.rest v0.1 — ~1,536 fixture assertions across six
suites, all model-free and network-free.

**Waiting on you, each blocking only itself:**

1. **An OpenAI key** — turns the connector from *unvalidated* into proven.
2. **A sending domain** (Workers Paid) — so a stranger can receive a sign-in code.
3. **A git remote** on the rig repo — so the installer can be a one-liner.
4. **The first named tunnel** registered on your Cloudflare account — the instant kill
   switch needs it, and no automated worker may create it.
5. **The deploy**, when you want it:
   `npx wrangler pages deploy portal/public --project-name rig-portal --branch main`
   (9 files, 93,496 bytes, each with its sha256 recorded; nothing outside `public/` can
   be published.)

---

## 7. How to move forward

**To try it locally today:** run the shell, open the cockpit, start a session in a project
folder, and watch the river draw itself.

**To get a second user:** the four items above, in that order. Deploy last, because until
the tunnel exists the kill switch is not real, and until the sender exists a stranger
cannot sign in.

**To keep it honest as it grows:** the laws are already mechanical. `doctor` and `eval`
run before every push; the gate blocks the push if either is red; the pulse runs daily;
every helper's prompt is banked; every claim in the estate carries a label. You do not
have to remember any of it — that was the point.
