# Session Harness — exercise sheet

One verb per module: a short overview from the front, then you drive it.

Every exercise ends in something you can **check**, not something you should *feel*. If a
check doesn't come out the way this sheet says, that's interesting — tell your facilitator the
**exact error text**, not a paraphrase.

---

## 00 · Setup, and the contract

```bash
mkdir -p ~/harness-workshop && cd ~/harness-workshop
```

Open a session there and run `/doctor`.

- [ ] Exit code: `______`  ·  does it block a ship? `______`

**The contract every skill shares** — fill this in; it makes the next nine modules make sense:

1. ______________________ triggers it, or invoke `/verb`
2. Two files out: ______________ (the working-out) and ______________ (the answer)
3. `--quick` — chat-only, compressed, and ______________ about being so
4. ______________ labels on every claim
5. A ______________ before it finishes

> **The frame:** `/oracle` opens · `/sessionend` closes · `/fable-mode` is the posture between.

---

## 01 · `/oracle` — how a session starts

```
hey oracle
```

Answer **two** questions honestly. Skip the rest — that's allowed, and deliberate.

```bash
ls CLAUDE.md && wc -l CLAUDE.md
```

- [ ] `CLAUDE.md` now exists
- [ ] What did I just create, in my own words?

_______________________________________________

---

## 02 · `/notrest` — presence is not establishment

**Beat 1** — in the folder as it stands:

```
/notrest check
```

- [ ] Exit: `______` ← it refused. Why do you think it refused?

_______________________________________________

**Beat 2** — make it unambiguously a project, then check again:

```bash
printf '# Harness workshop scratch\n' > README.md
```
```
/notrest check
```

- [ ] Exit: `______`

> Your session has been getting harness reminders since it opened.
> **Is this project governed?** ______________

**Beat 3** — establish, then verify it yourself rather than trusting the output:

```
/notrest
```
```bash
ls COORD.md && grep -c "notrest:protocol" CLAUDE.md
```

- [ ] Exit: `______` · `COORD.md` exists · marker count `______`
- [ ] The files are there. Does that prove the session is *following* the protocol?

_______________________________________________

---

## 03 · `/fable-mode` — the posture

Run these **exactly as written, in order**. Don't skip ahead — the order is the point.

```bash
cd ~/harness-workshop
printf 'hello world\n' > notes.txt
if grep -q "$PATTERN" notes.txt; then echo "PASS"; else echo "FAIL"; fi
```
- [ ] Result: `__________`

Now replace the file's contents entirely and run the **same** check:

```bash
printf 'totally different content\n' > notes.txt
if grep -q "$PATTERN" notes.txt; then echo "PASS"; else echo "FAIL"; fi
```
- [ ] Result: `__________`
- [ ] Write what you think just happened, **before** the explanation:

_______________________________________________

```bash
PATTERN=hello
if grep -q "$PATTERN" notes.txt; then echo "PASS"; else echo "FAIL (correctly)"; fi
```
- [ ] Result: `__________`

**The loop:** ORIENT → ______ → ACT → ______ → BANK
**The word to practise saying out loud today:** ________________

---

## 04 · `/doctor` + `/eval` — the two gates

```
/doctor
```
```
/eval
```

- [ ] doctor: `______`  ·  eval: `______`
- [ ] Which of my two codes would block a ship? ______________
- [ ] Find one WARN and copy its **fix line**:

_______________________________________________

> `/doctor` checks the ____________ . `/eval` checks the ____________ .

---

## 05 · `/recap` — the trail, written and read

**Grade these three.** Which could a stranger act on? Which is the sneaky one?

**A** `- [14:22Z] [me] fixed the bug`

**B** `- [14:22Z] [me] login returns 500 on empty password -> null guard at auth.py:42 | evidence: repro curl now 401 not 500; 3 new tests pass`

**C** `- [14:22Z] [me] refactored auth for clarity -> should be much more maintainable now | evidence: looks good`

- [ ] Best `___` · worst `___` · **most dangerous** `___` — why?

_______________________________________________

**Now write one for real.** Do a small piece of work, then:

```bash
wc -l < COORD.md
```
before: `______`  → do the work, bank the line →
```bash
wc -l < COORD.md && tail -1 COORD.md
```
after: `______`

- [ ] The count went up by **exactly one**
- [ ] My line has all three parts: the ask · what landed · the evidence
- [ ] A neighbour read it and could answer: *"could you act on this if you'd never seen this project?"*

```
/recap
```
- [ ] That's what a new session gets for free.

---

## 06 · `/graph` — the live window

```
/graph river
```
```
/graph
```

- [ ] I'm looking at **my own estate** — the ledger lines I wrote in module 05, drawn as a journey.

**The four levels of "done"** — fill them in as the facilitator walks them:

present → ______________ → ______________ → ______________

---

## 07 · `/agentswarm` + `/spend` — delegate, then audit

Delegate one tiny job to a background lane — **name the model explicitly.**

```bash
ls briefs/ 2>/dev/null && tail -3 spend/ledger.md 2>/dev/null
```
```
/spend report
```

- [ ] I found the **verbatim commission** for my lane
- [ ] I found a **cost receipt**
- [ ] What does the report's exit code mean? ______________
- [ ] Any gap between the brief on disk and what I *thought* I asked for?

_______________________________________________

**The four rules:**
1. Every lane declares its ______________ explicitly. Omitting it is a ______________, not a default.
2. One ______________ lane per domain; feedback ______________ it.
3. The commission is never ______________.
4. Synthesis at fan-in is a ______________, never a ______________.

---

## 08 · Finale — `/sessionend` → `/notrest`

**The test: can a session that has never seen your work continue it?**

1. Do one more small piece of work. Leave it deliberately half-finished. Bank a line.
2. `/sessionend`
3. Open a **brand new session** in the same folder → `/notrest`
4. **Before you tell it anything**, ask:

> *What am I building here, and what was the last thing that landed?*

- [ ] It answered without my help
- [ ] Its answer matched reality: ☐ fully ☐ partly ☐ not really
- [ ] If it missed something — **which line in my trail should have carried that fact?**

_______________________________________________

**Verify as little as the evidence allows:**

| tier 0 | always | the two gates + git state vs what the packet claimed |
| tier 1 | only if a gate wasn't green | re-run the specific check the trail names |
| tier 2 | only on a contradiction | **the trail wins** — probe that one claim only |

---

## 09 · Monday

- [ ] The one project I'll try this in: _______________________________________________
- [ ] Week one, one thing only: one honest line per substantive prompt, when it lands.
- [ ] The failure that's actually costing me most right now:

_______________________________________________

**The one sentence to take home:**

> Write down what landed and how you know, the moment it lands.
