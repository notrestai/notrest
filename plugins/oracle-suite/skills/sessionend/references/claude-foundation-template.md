# CLAUDE.md — [your name / handle]

<!-- =====================================================================
  WHAT THIS FILE IS
  Your invariant layer — the stable, foundational context that is true
  across ALL your projects. As CLAUDE.md it is auto-read by Claude Code
  at the repo root, so it loads itself (no pasting). Read-only during
  work; updated rarely.

  WHY IT EXISTS AS ONE FILE
  Protocol (how you work) and Map (the infrastructure you work on) are
  both stable across projects in your case. Combining them into one
  foundation file:
    - stops the shared parts from being re-stated per project
    - makes cross-project overlaps visible (one source of truth for
      machines, paths, tooling, conventions you use everywhere)
    - keeps the foundational layer small and loadable

  WHAT THIS FILE IS NOT
    - Not project status     → that's the Handoff / state file
    - Not project goals/plan → that's the Agenda / Step-by-step
    - Not workflow process   → that's a separate protocol (e.g. PEP,
                               research pipeline)
    - Not anything volatile  → if it changes mid-session, it doesn't
                               belong here
  ===================================================================== -->

> **THE EARN-ITS-LINE TEST — applied to every line in this file:**
> *"If the next chat lacked this line, would I have to re-explain it,
> would the chat get it wrong, or would it burn tokens rediscovering it?"*
> If no — cut the line. A foundation works by being small and solid,
> not comprehensive.

Last updated: YYYY-MM-DD

---

## PART 1 — PROTOCOL  (how you work — invariant)

<!-- The behavioral layer. Stable across projects: this is how YOU work,
     not how a project works. Use the trigger/action format — a rule
     without a trigger cannot fire.
     Keep this section to ~5-8 rules total. The discipline is the point. -->

### Operating principles  (override defaults)

1. **[Principle]** — [one line: what it means in practice]
2. **[Principle]** — [...]
3. **[Principle]** — [...]

### Hard rules

**1. [Rule name].**
   *Trigger:* [observable condition]
   *Action:* [what to do]
   *Exception:* [delete this line if none]

**2. [Rule name].**
   *Trigger:* [...]
   *Action:* [...]

### Certainty labels

Every factual claim ends with: `[confidence · source — what would invalidate it]`
- confidence: high / med / low
- source: cited / recall / inferred / unverified / disputed

---

## PART 2 — TOOLING DEFAULTS  (what you reach for, by default)

<!-- The toolchain you assume across projects. Project-specific
     deviations live in that project's section below, not here. -->

- **Languages I default to:** [...]
- **Editor / shell:** [...]
- **Git workflow:** [...]
- **Tools I assume are installed:** [...]
- **Offload model policy (HARD RULE, owner-set 2026-07-15):** Fable never rides in a
  subagent; every job a Fable session offloads runs on **opus** (`model: "opus"` on
  every Agent/Workflow call — no sonnet, no haiku, never inherited fable). Delegate
  via agentswarm (seat-agnostic; the seat keeps decompose/judge/apply/gate); receipts via /spend;
  never `/model`-switch the seat mid-session (cache burn — delegate instead).
- **[Anything else stable across your work]**

---

## PART 3 — CROSS-PROJECT CONVENTIONS  (rules that hold everywhere)

<!-- Things that are true regardless of which project. Naming patterns,
     inviolable rules, how you do certain things universally. -->

- **[Convention]** — [what it means]
- **[Inviolable rule]** — [e.g. "no cloud inference, all local"]
- **[Convention]**

---

## PART 4 — SHARED INFRASTRUCTURE  (the Map across all projects)

<!-- The machines, paths, and services you use across multiple projects.
     If something is only used in one project, it does NOT go here —
     it goes in that project's section below.

     A useful pattern: if you find yourself wanting to write the same
     thing in two project sections, it belongs HERE instead. The
     structure teaches you what's actually shared. -->

### Machines

| Name | Address | Role |
|---|---|---|
| [name] | [IP / host] | [what it's used for, across projects] |

### Standard paths

| What | Where |
|---|---|
| [thing] | [path] |

### Shared services

| Service | Location | Notes |
|---|---|---|
| [service] | [where it runs] | [...] |

---

## PART 5 — PROJECTS  (per-project sections — only what's unique)

<!-- DISCIPLINE — the part that keeps this file from rotting:

     - Each project section has a HARD LINE BUDGET of ~15-20 lines.
       Going over means content belongs in that project's own Handoff
       or in Shared Infrastructure above, not here.
     - This section holds what is UNIQUE to the project — anything
       shared promotes UP to Part 4.
     - Add a project only when it is actively in use. Archive
       inactive projects (move them out of the file entirely, or
       collapse to a one-line "see [other file]").
     - Each project section follows the same shape, so a fresh chat
       can find what it needs in a known place. -->

### Project: [name]

- **Purpose (one line):** [...]
- **Status:** active / paused / archived
- **Project-unique machines/paths:** [only what isn't in Part 4]
- **Project-unique conventions:** [only what isn't in Part 3]
- **Pointer to project docs:** [Agenda, Handoff, etc. — names, not content]

### Project: [name]

- **Purpose (one line):** [...]
- **Status:** [...]
- **Project-unique machines/paths:** [...]
- **Project-unique conventions:** [...]
- **Pointer to project docs:** [...]

<!-- Add new project sections only when the project is active. -->

---

## MAINTENANCE  (the part that keeps this file honest)

<!-- A foundation file rots if it only grows. These rules are the
     mechanism that prevents it. -->

**When to add a line:** when something is stably true across projects (or
across multiple sessions of one project) AND would otherwise be re-stated
or re-discovered. Not because "it might be useful."

**When to remove a line:** if a line has not been needed in [N] sessions,
or the AI handles it correctly without being told, cut it. Pruning is
first-class, not cleanup.

**When to promote up:** if you write the same line in two project sections,
move it to Shared Infrastructure (Part 4) or Cross-Project Conventions
(Part 3). Repetition across projects is the signal that something is
actually shared.

**When to archive a project:** if a project is no longer active, move its
section out of this file (to its own doc or a separate archive). Inactive
projects loaded into every chat are pure context cost.

**Staleness check:** the "Last updated" date at the top. If it is months
old, the per-project sections are almost certainly wrong somewhere —
reconcile against reality before relying on this file.
