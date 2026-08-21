---
name: draft
description: "The suite's outbound verb — turns a dossier, decision, or recap into the thing you actually send (email · memo · slack update · one-pager), every factual sentence traced to its source line, honesty label kept. Use on /draft, \"write the email\", \"draft the memo\", \"turn this into an update\", \"make this sendable\", \"write it up for {audience}\"; --quick for chat-only. A draft is never sent — sending is the owner's act. Not for legal or regulatory notices, nor before the decision exists."
---

# draft — the dossier, turned into the thing you send

Every other skill in this suite ends at *"you now know / you have decided / you have a plan."*
That is one step short of the work. The plan still has to reach a person: the investor who
needs the number, the team that needs the call, the customer who needs the date.

**draft is that step.** It takes a source you already trust and produces a sendable artifact —
and it is the one skill in the suite where the pressure runs the wrong way. Research pressure
pushes toward *more hedging*. Writing pressure pushes toward *less*: the sentence reads better
without "we estimate", the number lands harder without "unverified", the paragraph is cleaner
without the caveat. **That is the exact moment this skill exists to survive.**

The whole skill rests on one distinction: **[fact] vs [framing].**

- A **fact** is a claim about the world. It must trace to the source. It keeps its label.
- A **framing** choice is a decision about presentation — what to lead with, what to cut, what
  tone, what order. It is legitimate, it is yours, and it gets **written down as a choice**.

Facts get a source-map. Framing gets a list. Nothing gets invented.

**Router shape:** `outbound`

## When to run

- You have a suite dossier (research / decision / market / factcheck / recap / plan) and now
  someone else needs to read it.
- You have a decision and need to announce it.
- Someone asks for "the update" and you have the material but not the message.
- You want the *same* conclusions written for a different audience — the board, not the team.

## When NOT to run

- **Legal or regulatory notices** — breach notifications, disclosures, cease-and-desist,
  regulatory filings, anything with a statutory recipient or deadline. Route to the legal
  domain packs. This skill has no legal review step and must not pretend to one.
- **The decision isn't made yet.** If the source is options-and-tradeoffs rather than a call,
  run **decider** first. Drafting an announcement of an undecided thing manufactures a
  decision, which is the worst possible failure mode for a skill that writes in your voice.
- **You have no source.** If the "source" is only what you remember, say so out loud before
  writing — see *Unlabeled and unsourced material* below. draft does not fill gaps.
- **Quick one-liners.** "Reply yes to Ana" needs no ritual. Just write it.

## Inputs

Three, and the second is the one people forget.

**1 — The source (required).** Any of:
- **the findings store** — `archive/findings.jsonl`, where decider / factcheck / researcher now
  leave their **records**. This is the default source, and step 1 below starts there,
- a path to a suite dossier (`research/…`, `decision/…`, `market-research/…`, `factcheck/…`,
  `recap/…`, `action-plan/…`) — the legacy estate, still fully supported,
- a decision or recap written elsewhere,
- pasted conclusions.

Read it. All of it. The source is the only place facts may come from.

**2 — The audience (required — ask if not given).** Three questions, and you may not skip them:
- **Who reads this?** Name them or name the role. "The team" is not an audience; "the four
  engineers on the migration" is.
- **What do they already know?** Everything they know is context you can compress. Everything
  they don't is context you must include or the message fails.
- **What do they do with it?** Decide, act, acknowledge, or nothing. This determines the ask,
  and the ask determines the whole shape.

If the user gave you a format but no audience, ask for the audience. It is cheaper than a
rewrite and it is the input that actually changes the output.

**3 — The format.** One of the five in `references/formats.md` — email, exec memo, slack/chat
update, one-pager, status update. Each is a skeleton with named slots and a **hard length
budget**. If the user didn't name one, infer from the audience and *say which you picked*.

## Quick mode (`--quick`)

If the invocation includes `--quick` (or "quick", "just draft it", "no files"):
- **No files.** Chat only.
- **Labels stated inline** in the draft itself — `[estimate]`, `[unverified]` visible in the
  text, because there is no background file to carry them.
- Still read the source. Still refuse to invent. The shortcut is the paperwork, never the law.
- End with: *"Quick draft — labels are inline and this is honestly rougher; run without
  `--quick` for the source-map, the framing list, and a clean sendable version."*

## Workflow

### 1 — Read the source and extract the claims, with labels

**Start at the store.** decider and factcheck do not leave a dossier to open — they leave
**records**. So the source inventory begins with a query, not a file hunt:

```bash
IDX="${CLAUDE_PLUGIN_ROOT}/skills/archivist/scripts/index.py"
python3 "$IDX" track --json --status live --kind decision --root .   # the calls
python3 "$IDX" track --json --status live --kind result   --root .   # what they concluded
```

`--kind` takes **one** kind per call — it is an enum, not a list — so that is **two calls**,
not `--kind decision,result`. Union the two `records` arrays; that is the inventory. Add
`--kind finding` when the draft needs the underlying evidence too, and `--session <s>` to scope
it to one session's work. Each record hands you the claim (`statement`), its honesty labels
(`evidence[].label`), the sources behind it (`evidence[].ref`), and its `id` — which is what
the source-map cites.

Three store rules that bind the draft:

- **`--status live` is not optional.** It filters on the *effective* status, so a superseded or
  refuted record never reaches the page. Drafting from a record the store has already retired
  is how a retracted finding gets mailed to a board.
- **A record whose `rests_on_refuted` is non-empty may not be stated as fact.** The record is
  live, but a finding it links was refuted (`"rests_on_refuted": ["F-3"]`). Cut the claim, or
  write it with the loss named — and put that in the framing list, never silently.
- **`[model-opinion]` evidence is a judgment, never a source.** Attribute it as an opinion or
  cut it; it may not be written as a fact about the world.

The store is a finding aid, never a source: cite the record's evidence `ref`, and carry the
record id so a reader can walk back to it. If there is no store in this repo, fall back to the
dossier path or the pasted material — everything below is identical either way.

Go through the source and pull out every claim the draft might use. For each one record:

| Claim (as the source states it) | Label | Where in the source |
|---|---|---|

"Where in the source" is the record id (`F-12`) for a store record, and `path#heading` for a
file — never "the dossier".

Labels come from the source, not from you. The suite's labels are load-bearing:

- **[cited]** — backed by a real named source in the dossier. May be stated as fact.
- **[recall]** — from the model's or the owner's memory, unverified. Hedge it or cut it.
- **[estimate]** — a number or judgment that was derived, not measured. **Must stay hedged.**
- **[unverified]** — checked and not confirmed, or never checked. **Cut it, or carry the hedge.**

**Unlabeled and unsourced material.** If the source has no labels (a pasted email thread, raw
notes, a doc from outside the suite), you do not get to promote it. Treat the whole source as
**[recall]-grade**, write that fact into the background file's source inventory as a line the
owner can see — *"source carries no honesty labels; all claims treated as [recall] and hedged
accordingly"* — and hedge accordingly in the prose. An unlabeled source is a weaker source, and
the draft should read like it.

### 2 — Write the audience brief (three lines)

In the background file, three lines only:
- **Reader:** who, and their relationship to this.
- **Knows already:** what you can assume.
- **Should do:** the single action. If there are two, pick one and note the other as dropped.

### 3 — Pick the skeleton and fill it inside the budget

Open `references/formats.md`, take the skeleton, fill every slot. The budget is a **hard**
limit, not a target — being over budget is a defect, and the fix is cutting content, never
shrinking the caveats. If the material genuinely does not fit, say so and recommend a longer
format rather than silently overrunning.

### 4 — Build the source-map and the framing list

Both go in the background file. The source-map is the proof:

| Draft sentence (first ~8 words) | Source (`F-<n>` or path) | Label | Treatment |
|---|---|---|---|
| "We are moving the read path to Redis…" | `F-12` (decision) — "Pick Redis; the hinge is whether eviction is CI-verified." | [cited] · ev: `https://redis.io/docs/…` | stated as fact |
| "Migration should land around mid-Q4…" | `F-9` (result) — "~6 engineer-weeks on current staffing." | [estimate] | hedged ("we estimate") |
| "Support is 24/7 on Enterprise…" | `understanding/vendor-slaDossier.md#SLA` | [unverified] | dropped |

**Every factual sentence in the deliverable appears in this table.** If a sentence is in the
draft and not in the map, it came from nowhere — delete it or find its source. "Treatment"
records what you did to the label: *stated as fact* (only [cited]), *hedged*, *dropped*,
*attributed*.

**The source column is a pointer someone can follow**: a record id (`F-12`) or a path with a
heading, never "the dossier" or "the decision". A record id is the stronger citation — it
carries its evidence refs and its effective status with it, so a reader can check both the
claim and whether the store still stands behind it. A store-sourced row keeps the evidence
`ref` beside the label, because the record is the finding aid and the `ref` is the source.

The framing list is the honest half of the same page — one line per choice:

> `[framing]` chose *X* over *Y* because *<audience reason>*

Real examples of what belongs there: leading with the cost instead of the timeline; putting the
risk in paragraph three instead of the subject; cutting two of five findings; a warm opener for
a tense recipient; naming a person or not naming them.

### 5 — Self-check (below), then hand it over

## Honesty rules

These are the skill. Everything above is procedure; this is the contract.

1. **Every factual sentence traces to the source.** The background file carries labels inline;
   the deliverable carries clean prose plus the honest hedges. The source-map is what connects
   them, and it is not optional.
2. **Persuasion may never upgrade a label.** This is the core law and it is violated
   *gradually*, by good writing:
   - **[estimate] stays hedged.** "We estimate ~$40k" — never "$40k". "Roughly", "we estimate",
     "on our numbers" survive into the final prose. A hedge deleted for rhythm is a lie added
     for rhythm.
   - **[unverified] either drops or appears with its hedge** — "we have not confirmed this, but
     …" — **never as fact**, and never as an unattributed implication.
   - **[recall] gets attributed or hedged.** "From the notes", "as I remember it".
   - **[cited] may be stated flatly.** That is what the citation bought.
3. **Numbers are never invented.** Not rounded into precision, not "approximately"-ed into a
   figure the source doesn't contain, not summed across claims the source didn't sum. If the
   draft needs a number the source lacks, leave `[NUMBER NEEDED: what]` in the text and flag it
   at the top of the background file.
4. **Quotes are never manufactured.** No plausible paraphrase in quotation marks. No
   reconstructed "as Jamie said". If it isn't verbatim in the source, it isn't in quotes.
5. **Recipients are never guessed.** No invented names, emails, titles, or channels. Unknown
   recipient = `[RECIPIENT: ___]` in the header. Guessing who receives a message is how a draft
   becomes an incident.
6. **Framing is disclosed, not hidden.** Every framing choice appears in the list. A choice you
   would not want to write down is a choice you should not make.
7. **A draft is never sent.** See below.

## A draft is never sent

**This skill writes. It does not send.** No email client, no Slack post, no publish, no push —
not with an MCP available, not when asked, not when the message is trivial. Sending is the
owner's act, in the owner's client, under the owner's name.

And the harness law behind it: **a draft is never evidence that a message was sent.** A file
at `draft/customer-update.email.md` proves text exists — nothing more. Never report a draft as
a sent message, never log it as a delivery, and when a later session finds a draft in the repo,
that file means *written*, never *delivered*.

Finish by telling the owner where the file is and that they send it.

## Outputs

Two files (or chat only under `--quick`):

- **`draft/{slug}background.md`** — the working file: source inventory (the `track` queries
  actually run and the record ids they returned, or the dossier paths read, with the
  no-labels disclosure if it applies), the claims table with labels, the three-line audience
  brief, the chosen format + budget, the **framing decisions** list, and the **source-map**
  table at the bottom. Labels appear inline here.
- **`draft/{slug}.{format}.md`** — the sendable. Clean prose, no label brackets, hedges intact.
  For `email` and `slack`, the **subject line / channel + opener is part of the deliverable**,
  written into the file. Unknown recipients stay as `[RECIPIENT: ___]` placeholders.

`{slug}` is a short kebab-case name for the message (`q3-board-update`, `migration-delay`).
`{format}` is one of `email`, `memo`, `slack`, `onepager`, `status`.

## Self-check

Run all five before handing over. Any failure is fixed, not noted.

1. **No unlabeled fact crossed over.** Every factual sentence in the deliverable appears in the
   source-map with a source line. Zero exceptions — walk the draft sentence by sentence. A
   store-sourced sentence names its record id; no sentence rests on a record the store no
   longer calls live, or on one flagged `RESTS-ON-REFUTED` without the loss named in the text.
2. **No label was upgraded.** Each [estimate] in the map is hedged in the prose. Each
   [unverified] is dropped or hedged. Each [recall] is attributed or hedged. Re-read the
   deliverable *alone*, as the recipient — would you believe anything more firmly than the
   source supports? If yes, that sentence is the bug.
3. **Length is within budget.** Count it against `references/formats.md`. Over budget = cut
   content, never cut caveats.
4. **The one thing the reader should do is unmissable.** Say the ask out loud to yourself; find
   it in the draft. If it is buried in paragraph four or implied, it is not there.
5. **Nothing was invented.** No number, quote, name, date, or recipient that isn't in the
   source. Any `[NUMBER NEEDED: …]` or `[RECIPIENT: ___]` placeholders are listed at the top of
   the background file so the owner sees them before sending.

## Finishing up

Report, in this order:
- both file paths (or "chat only" for `--quick`),
- the format and the length actually used vs the budget,
- the framing choices, in one line each,
- any placeholders the owner must fill,
- and the last line, every time: **the draft is written; sending is yours.**

### Chains

- **archivist → draft** — the inventory is a query, not a file hunt: `index.py track --json
  --status live --kind decision` then `--kind result` (one kind per call). The source-map cites
  `F-<n>` ids, so a reader walks from a sentence in the email back to the record, its evidence
  refs, and whether the store still calls it live.
- **decider → draft** — make the call, then announce it. The canonical pair.
- **researcher / marketresearcher / factcheck → draft** — findings → the update that carries
  them, labels intact.
- **recap → draft** — the trail becomes the status update or the stakeholder memo.
- **stepbystep / actionplan → draft** — the plan becomes the kickoff message.
- **draft → critic** — for a high-stakes send, red-team the draft before the owner sends it.
- **draft → owner sends** — the chain always ends here, outside the tool.
- **sessionend** notes the drafts produced (path + format + sent-status *unsent*), so the next
  session knows a message exists and was never delivered.
