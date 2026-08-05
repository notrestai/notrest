# Module 06 — `/graph` — the live window over the estate

**15 minutes.** The most visual module in the day, and the cheapest — it costs zero model
tokens.

---

## The failure it prevents

You cannot see the shape of what you're working in. Which files reference which. Which are
orphans nobody links to. Which have gone stale. And — once you have a trail — what the
project's actual journey looked like, including the backtracks you'd rather forget.

There's a second failure here, subtler and more interesting, and it's the module's payload:
**a view that exists but is never on screen is not a view.**

## Overview — what the verb is

`/graph` is a set of script-built views. A python-stdlib scanner walks the repo and renders
self-contained HTML. No model involved, so it's effectively free and instant.

| view | what it shows |
|---|---|
| **file graph** | every file and the references between them — wikilinks, markdown links, imports, sourced scripts. Obsidian, for a codebase |
| **river** | the ledger and findings drawn as a journey toward the goal — side channels, backtrack loops, milestone flags |
| **domains** | partitions a file set into non-overlapping lanes for delegation (module 07's input) |
| **links · orphans · stale** | text queries over the last scan |

And the **cockpit** — the live window that serves those views on `127.0.0.1`, one at a time,
each owning the screen.

```bash
cockpit.py status     # 0 running · 5 down · 6 not opted in
cockpit.py serve      # bring it up
```

## Test drive (9 min)

The satisfying part: by now their scratch project has a real trail, so the river draws
**their own session.**

```
/graph river
```

Then open the cockpit and look at it live:

```
/graph
```

**Success condition: they are looking at their own estate on screen** — the ledger lines
they wrote in module 05, drawn as a journey.

**Optional, 2 min:** point the scanner at a real project they actually work in and look at
the file graph. Flag honestly that this **writes a `graph/` output directory** into that
project — harmless, but theirs to clean up or gitignore. Don't skip that sentence; surprising
someone with files in their own repo is a bad first impression for a tool about trust.

## What just happened

This module's payload is a trilogy of laws, each earned by a real defect, each one a version
of the workshop's central idea. Walk them in order — the escalation is the lesson:

**1 · Presence is not display.** The cockpit existed and worked, and nobody ever looked at
it. The owner's field note was blunt: *the graphs should be on display, showing the work as
it happens.* A window nobody opens is not a window. The fix wasn't a better renderer — it
was making the estate *tell* each session the window exists, and open it.

**2 · Rendered is not readable.** Then it was on screen — and unreadable. Too much on one
canvas, labels colliding, legends eating the viewport. The gate law was amended to say so:
**a correct render nobody can read fails this gate.**

**3 · Readable is not navigable.** Then it was readable, and you still couldn't explore it —
no panning, no zoom, clicks doing nothing. The root cause is the best debugging story in the
repo: an invisible empty-state overlay was sitting on top of the canvas **swallowing every
pointer event.** The handlers were correct the whole time. They were starving.

Say the sequence out loud, because it's the whole workshop in miniature:

> **present → displayed → readable → navigable.** Each one felt like done. None of the
> first three were.

That is *presence is not establishment*, four levels deep, in one feature.

## Facilitator notes

- **This is the module people photograph.** Leave a beat after the river renders. Let them
  look at their own trail.
- The pointer-event story lands well with anyone who has debugged a UI. Ask before you
  reveal the cause: *the click handlers were correct — so what was wrong?* Someone always
  gets it, and they enjoy getting it.
- Zero model tokens is worth stating plainly. In a room comparing tools on cost, an
  instrument that's free to run every single session is a genuinely different category from
  one that isn't.
- Don't let this become a graph-layout discussion. Fifteen minutes.

## Fallback

If the cockpit won't serve — a busy port is the usual reason — the views still render to
standalone HTML files they can open directly in a browser. If the scan fails entirely, show
yours on the projector; the trilogy of laws is the content, and it survives without their
own render.
