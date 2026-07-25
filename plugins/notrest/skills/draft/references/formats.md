# draft — format skeletons

Five formats. Each is a skeleton with named slots and a **hard length budget**.

The budget is a limit, not a target. Over budget is a defect. The fix is always **cut content**
— never shrink a hedge, never drop a caveat to make room. If the material genuinely will not
fit, say so and recommend the next format up rather than overrunning silently.

State the chosen format and its budget in the background file, and report actual-vs-budget when
you hand over.

| Format | File suffix | Budget | Best when |
|---|---|---|---|
| Email | `.email.md` | **200 words** body (subject ≤ 10 words) | One named recipient or a small list; needs a subject and an ask |
| Exec memo | `.memo.md` | **500 words** | A decision-maker who needs the reasoning, not just the call |
| Slack / chat update | `.slack.md` | **120 words**, ≤ 5 lines before any list | A channel skims it on a phone |
| One-pager | `.onepager.md` | **700 words**, one printed page | Someone outside the room needs the whole picture standalone |
| Status update | `.status.md` | **300 words** | A recurring cadence where last time is the baseline |

---

## 1 — Email · `{slug}.email.md` · 200 words

The subject line **is part of the deliverable**. Write it into the file.

```
To:      [RECIPIENT: ___]
Subject: <≤ 10 words — the thing, not the topic>

<Opener — 1 line. Why they're getting this, now.>

<Body — 2 to 4 short paragraphs. Facts with their hedges intact.>

<The ask — its own line, imperative, with a date if there is one.>

<Sign-off>
```

- **Subject:** name the substance, not the category. "Migration slips to Nov 14" beats
  "Migration update". Never put an [estimate] number in a subject unhedged — the subject is the
  most-quoted line in the message and the least likely to carry a caveat with it.
- **Opener:** one line. Do not restate the subject.
- **The ask goes on its own line.** Buried in a paragraph, it does not exist.
- Unknown recipient stays as `[RECIPIENT: ___]`. Never guess an address or a name.

---

## 2 — Exec memo · `{slug}.memo.md` · 500 words

For a reader who will act on it and may be asked to defend it.

```
# <Title — the decision or finding, stated>

**Bottom line:** <1–2 sentences. The call, up front.>

## What we found
<3–6 sentences. Facts with labels honored — "we estimate", "unconfirmed but".>

## Why it matters
<2–4 sentences. Consequence for this reader specifically.>

## What we recommend
<The recommendation. One paragraph or a short list.>

## What we don't know
<Every [unverified] and load-bearing [estimate], stated plainly.>

## Ask
<What this reader decides or approves, and by when.>
```

- **Bottom line first.** An exec memo that makes the reader work for the conclusion has failed
  before the honesty rules are even in play.
- **"What we don't know" is not optional.** It is where the [unverified] material lives with its
  hedge instead of being quietly dropped. If you dropped an [unverified] claim rather than
  hedging it, that is a `[framing]` line in the background file.

---

## 3 — Slack / chat update · `{slug}.slack.md` · 120 words

Read on a phone, in a scroll. The channel line is part of the deliverable.

```
#<channel or [CHANNEL: ___]>

<Lead line — the news, in one sentence. Bold the subject if it helps scanning.>

<1–3 short lines of detail, or a 2–4 bullet list.>

<Ask or "no action needed" — explicit either way.>
```

- **Five lines max before any list.** Longer belongs in a memo with a link.
- **"No action needed" is a real ask** and should be written when true — it stops the thread.
- Hedges survive compression: "~2 weeks (estimate)" is fine, "2 weeks" is not, when the source
  says [estimate].
- No @-mentions of people the source didn't name.

---

## 4 — One-pager · `{slug}.onepager.md` · 700 words

Standalone. Assume the reader has no context and will not ask a follow-up.

```
# <Title>

**In one line:** <the whole thing, compressed>

## Context
<Why this exists. 2–4 sentences.>

## The situation / the finding
<The substance. Facts with labels honored.>

## Options or approach
<What was considered, what was chosen.>

## Risks and unknowns
<[unverified] and [estimate] material, plainly stated.>

## Next steps
<Who does what, by when. Named or [OWNER: ___].>
```

- Because it stands alone, **every claim needs its hedge carried locally** — there is no
  surrounding conversation to supply the caveat.
- Fits on one printed page. If it does not, cut the Context section first.

---

## 5 — Status update · `{slug}.status.md` · 300 words

For a recurring cadence. The baseline is what you said last time.

```
# <Project> — status, <date>

**Status:** <on track / at risk / blocked / done> — <one clause of why>

## Since last update
<What changed. Facts only.>

## Now
<What is in flight.>

## Next
<What happens before the next update, with dates.>

## Blocked / needs a decision
<Explicit. "Nothing" is a valid and useful answer.>
```

- **The status word is a claim** and follows the honesty rules like any other. "On track" when
  the source says [estimate] on the date means the update says *"on track — completion date is
  an estimate"*. A status word is the single most-forwarded token in the message; it may not
  outrun its label.
- **"Since last update" is a diff, not a summary.** If nothing changed, say nothing changed.
- If a prior update exists in `draft/`, read it so the baseline is real rather than assumed.
