# Module 02 — `/notrest` — presence is not establishment

**15 minutes.** The module that carries the workshop's central idea.

---

## The failure it prevents

A developer ran an entire working session in a project folder believing the harness
governed it. It did not.

The plugin was installed, so every session got the *nudges* — the discipline reminders, the
identity line, all of it, unconditionally. But the parts that actually write things were
gated behind a condition the folder didn't meet. So the session received every reminder and
produced **no ledger, no index, no trail.**

Nothing errored. Nothing logged. The session simply had no memory of itself, and it looked
exactly like one that did.

## Overview — what the verb is

`/notrest` has **two modes**, and it picks between them by looking at the folder:

| the folder is… | what the verb does |
|---|---|
| not yet governed | **establishes** it — writes the two surfaces that make a project governed |
| already governed | **continues the build** — reads the trail and picks up where the last session left off |

Today they'll use the first mode. Module 08 uses the second, and that's the finale.

**Establishment is two files, and both are checkable:**

- `COORD.md` — the ledger, with the header every reader parses
- `CLAUDE.md` — a marker-delimited, versioned protocol block

**Its exit codes are the whole interface:**

| code | meaning |
|---|---|
| `0` | established |
| `5` | partially — a surface missing, or a block at an older version |
| `6` | not established |
| `2` | **refused root** — it will not scatter files somewhere dangerous |

## Test drive (10 min) — three beats

### Beat 1: the refusal

In the bare scratch folder:

```
/notrest check
```

**Expect exit 2 — refused.** No project marker, so it declines to write anything and names
what it looked for.

This surprises people. Ask: *why would a tool refuse the thing you just asked it to do?*

Because **the estate never scatters.** A tool that helpfully creates files wherever it's
pointed will eventually create them somewhere terrible. Some refusals are absolute and no
flag overrides them — your home directory, the filesystem root, and `Desktop` / `Documents`
/ `Downloads` by exact path.

Worth one sentence: `~/Desktop` is refused, but `~/Desktop/my-project` is an ordinary
project. The refusal targets the specific dangerous locations, not a whole tree.

### Beat 2: not established

Give it a marker so it reads as a real project — module 01 may already have done this with
`CLAUDE.md`, in which case say so and skip the `printf`:

```bash
printf '# Harness workshop scratch\n' > README.md
```

```
/notrest check
```

**Expect exit 6.** Now the question that makes the module land — and *pause* on it:

> Your session has been getting harness reminders since it opened. **Is this project
> governed?**

No. **The nudges a session sees are not an estate.** That gap — between a session that
feels governed and a project that is — is the failure this module exists for, and they're
now looking at it with an exit code attached.

### Beat 3: establish

```
/notrest
```

**Expect exit 0.** Verify it themselves rather than trusting the output:

```bash
ls COORD.md && grep -c "notrest:protocol" CLAUDE.md
```

Two facts worth pointing at while the files are open:

**It only owns its own block.** Everything in `CLAUDE.md` outside the markers is the
project's own text and survives byte for byte. If the markers are ambiguous — a stray
opener, two blocks — it writes *nothing* and reports the line numbers. A tool that guesses
which markers it owns eventually eats the file.

**Writing the files is not the end.** They're inert. The session that establishes must then
*operate* under the protocol, from that turn on. The script writes; the binding is the
session's own act. Nothing enforces this, which is exactly why it gets said out loud.

## What just happened

Run `check` once more and look past the exit code at the informational lines — a count of
ledger lines, the age of the newest. Then:

> Your project is established. **Does that prove the session is following the protocol?**

No. It proves the files exist. Adherence is a judgment about behaviour: the files are
`[cited]`, following is `[unverified]` until there's a trail to point at.

This is why the exit code deliberately does **not** move based on how busy the ledger looks.
A code that swung on activity would make "am I compliant?" unfalsifiable.

## Facilitator notes

- **Do not rush beat 2.** The pause between "I'm getting reminders" and "this project has
  no trail" is where the idea lands. Let it be slightly uncomfortable.
- Someone will ask whether the beat-1 refusal can be overridden. Be precise: the *marker*
  requirement is soft — resolve it by making the folder a real project. The
  home/root/Desktop refusals are absolute.
- **The `--root` trap — expect this one.** Passing an explicit root deliberately bypasses the
  soft marker gate, so a helpful attendee who "fixes" beat 1 with `--root` will establish
  successfully and skip the entire lesson. That's correct behaviour (the refusal message
  literally suggests it, for the case where it really *is* the project root), but it defeats
  the beat. Tell them to `cd` in and run the verb against the current directory — which is how
  they'd use it for real anyway. The absolute refusals still hold even with `--root`.
  *Verified live: bare folder → exit 2 · add a `README.md` → exit 6 · establish → exit 0.*
- If someone runs it inside a git repo subdirectory they'll get a refusal naming the repo's
  top level instead. Correct behaviour: an estate below the toplevel would be written by
  nobody and read by nobody.

## Fallback

Run the three beats on the projector and have attendees call out the expected exit code
before you press enter. The codes are the content; the typing isn't.
