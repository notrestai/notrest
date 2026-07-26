---
name: game-forge
description: "Build a complete, playable game from a short request — real game loop, game feel, self-contained assets, automated playtest. Use on \"/game-forge\" or any ask to make, build, generate, prototype, or vibe-code a game: arcade, platformer, shooter, puzzle, tower defense, snake/breakout/tetris, idle/clicker, roguelike, \"a game like X but Y\", browser or pygame. Fires on casual asks (\"something fun to play\"). NOT for game reviews, buying advice, lore, or non-interactive animations."
---

# Game Forge

Anyone can ask a model for "a game" and get *some* HTML back. The gap between that
and something people actually enjoy playing is almost entirely craft the request
never mentions: a frame-rate-independent loop, input that feels tight, collision
that isn't janky, and the layer of polish ("juice") that makes actions feel good.
This skill's job is to make that craft the default, every time, without the user
having to ask for it.

The other half of "on the fly" is *reliability*: a generated game that throws a
console error on load is worse than useless because the user can't debug it. So
this skill always **runs the game before handing it over** and fixes what it finds
— and when the playtest comes back green, that green is banked as a record in the
archivist store, with the screenshot and the invocation as its evidence. "I ran it"
is a claim; a `kind=result` record carrying the exit-0 command is a receipt.

**Router shape:** none (invoked by name)

## The workflow

Follow this order. The sequence is the quality — skipping the early steps to
start coding is the most common way games come out mediocre.

1. **Lock the concept in one sentence.** Before any code, be able to state: the
   *core verb* (what the player physically does moment to moment — jump? aim and
   shoot? swap tiles?), the *goal/win-or-score condition*, and the *fail state*.
   If the user was vague ("make something fun"), pick a strong, well-scoped idea
   and say what you chose in one line — don't stall an unattended session waiting
   for input. A tight small game beats an ambitious broken one.

2. **Choose the platform.** Default to **browser (HTML5 Canvas)** — it runs
   instantly, renders inline as an artifact, needs no install, and can be
   playtested automatically here. Choose **Python/pygame** only if the user asks
   for it or wants a desktop app. See "Platform selection" below. Then read the
   matching engine reference before writing the loop.

3. **Start from the engine template, not a blank file.** Copy the relevant
   template (`assets/engine.html` or `assets/engine.py`) and build on its loop,
   input handling, and state machine. These solve the boring-but-critical parts
   correctly so you spend effort on the game, not on rediscovering a fixed-timestep
   loop. Read `references/game-loop.md` if you need to understand or adapt it.

4. **Make the core verb feel good *first*.** Implement only the central mechanic
   and tune it until it's satisfying on its own — movement acceleration, jump
   arc, aim responsiveness — before adding enemies, levels, scoring, or menus.
   If the core verb isn't fun with a bare rectangle on screen, more content won't
   save it.

5. **Layer in juice deliberately.** Work through `references/juice.md`. This is
   the single biggest quality lever and the thing models most reliably skip:
   screen shake, hit-stop, particles, easing/tweening, squash-and-stretch, and a
   sound on *every* meaningful action. Add procedural audio (`references/audio.md`)
   so there are zero missing-asset failures.

6. **Playtest it — actually run it.** For browser games, run
   `scripts/playtest.mjs` (headless Chromium — preinstalled on claude.ai, local Chromium/Playwright elsewhere). It loads the game,
   fails on any console/page error, simulates input, and screenshots the result.
   Read the screenshot and fix anything broken or blank. For pygame, build in the
   `GAMEFORGE_SMOKETEST` auto-quit hook (see `references/pygame.md` — the template
   already has it) and run headless with `SDL_VIDEODRIVER=dummy` to confirm the
   loop, update, and render all execute without crashing. Do not deliver a game
   you have not run. **When the playtest exits 0, write the record** (see "The
   receipt" below) — never before, and never on a run you patched afterwards
   without re-running.

7. **Deliver as one self-contained file.** Browser games ship as a single `.html`
   with all CSS/JS inline and no external CDNs or asset URLs — this is what makes
   them always run and render inline. Send it via the harness's file-send (`SendUserFile` on claude.ai) or save it into the
   project; a browser game the user will replay is also a good candidate to persist as an artifact.

## Platform selection

Choose per-game rather than assuming:

**Browser / HTML5 Canvas** (default) — pick this for almost everything: arcade,
action, puzzle, platformer, shooter, clicker, physics toys. Advantages that matter
for "on the fly": instant run anywhere, inline artifact preview, self-contained
single file, automatic playtesting here. Read `references/game-loop.md` and use
`assets/engine.html`.

**Python / pygame** — pick this only when the user explicitly wants Python, a
desktop app, or is learning game dev in Python. It can't render inline and is
harder to auto-playtest, and the user needs a Python env with pygame. Read
`references/pygame.md` and use `assets/engine.py`.

If the user names neither and the game is browser-suitable, go browser and say so
briefly.

## Genre playbooks

Each genre has recurring mechanics, collision needs, and camera behavior worth
getting right. When the concept matches one, read the matching file before
implementing — it saves you from re-deriving, e.g., swept collision for a
platformer or wave spawning for a shooter:

- `references/genres/platformer.md` — gravity, jump feel (coyote time, jump
  buffering, variable height), AABB swept collision, camera follow.
- `references/genres/shooter.md` — top-down/side shmup, bullet pools, wave
  spawning, enemy patterns, twin-stick vs auto-fire.
- `references/genres/puzzle.md` — grid state, match/clear logic, gravity/refill,
  turn vs real-time, undo.
- `references/genres/arcade.md` — single-screen classics (snake, breakout,
  asteroids, dodger, endless runner): scoring, difficulty ramp, lives.

If the requested game doesn't fit a playbook, that's fine — the engine template,
game-loop, juice, and audio references are genre-agnostic and enough to build from.

## Quick reference map

- **How the loop works / how to adapt it:** `references/game-loop.md`
- **Making it feel good (do this, don't skip):** `references/juice.md`
- **Sound with no asset files:** `references/audio.md`
- **Python specifics:** `references/pygame.md`
- **Genre mechanics:** `references/genres/*.md`
- **Starter code:** `assets/engine.html`, `assets/engine.py`
- **Verify it runs:** `scripts/playtest.mjs`

## The receipt — one record when the playtest goes green

A green playtest is the only evidence this skill produces, so it gets written down.
After `playtest.mjs` (or the pygame smoketest) **exits 0**, append one `kind=result`
record to the archivist store (`archive/findings.jsonl`, append-only, validated at
the door):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/archivist/scripts/index.py" add --root . --json '{
  "session":"game-forge-2026-07-25",
  "skill":"game-forge",
  "kind":"result",
  "ask":"make a little game about a cat dodging rain",
  "statement":"Shipped rain-dodger.html — single-file HTML5 canvas: fixed-timestep loop, pointer + keyboard input, WebAudio blip per dodge, screen shake and particles on a hit. Playtest exited 0 with no console or page errors, and the screenshot shows the cat, four raindrops mid-fall and a live score — not a blank canvas. Untested: mobile Safari, which the headless run does not cover.",
  "evidence":[{"type":"command","ref":"node scripts/playtest.mjs rain-dodger.html --keys Space,ArrowLeft","label":"cited"},
              {"type":"path","ref":"rain-dodger.playtest.png","label":"cited"},
              {"type":"path","ref":"rain-dodger.html","label":"cited"}],
  "relation":"toward",
  "links":[]}'
```

(Loose install: `../archivist/scripts/index.py` relative to this skill folder.) The
rules that matter here:

- **The command and the screenshot are both evidence.** `type=command` is the
  invocation that exited 0; `type=path` is the screenshot you actually looked at.
  A record without the screenshot is "it ran"; with it, it's "it rendered".
- **Say what you did not test.** Mobile browsers, gamepads, long sessions — the
  headless playtest covers none of them. That belongs in the statement, not in the
  user's first bug report.
- **A failed playtest is not a record — it's a fix.** Only exit 0 earns the write;
  if you patched the game after the green run, re-run it and record the new one.
- `add` prints the assigned `F-<n>` and **exits 2 naming the rule** on rejection —
  an empty evidence list, or a `[cited]` url that isn't a URL, does not enter the
  store. Fix the record, re-run; never hand-append to the JSONL.

## Anti-patterns to avoid

- **A `setInterval`/naive-`requestAnimationFrame` loop where physics scales with
  frame rate.** The game runs at different speeds on different machines. The
  template's fixed-timestep loop exists to prevent exactly this — use it.
- **Reading input inside update by polling one-shot events.** Track held-key
  *state* and edge-trigger presses (see the template's input manager) so movement
  is smooth and jumps are reliable.
- **Shipping without sound or feedback.** Silent, static hits feel dead. Even a
  single WebAudio blip per action transforms the feel; it's cheap, do it.
- **External assets / CDNs.** A missing sprite or a blocked CDN turns the whole
  game into a blank screen with no recourse for the user. Generate visuals with
  Canvas/SVG shapes and audio with WebAudio; keep everything in one file.
- **`localStorage` / `sessionStorage`.** Browser storage APIs are unavailable in
  the claude.ai artifact sandbox and throw, taking the game down with them. Keep
  high scores and settings in plain JS variables — a session best is still
  satisfying, and the game keeps working everywhere.
- **Keyboard-only input.** A good chunk of players open the game on a phone. The
  template wires pointer/touch alongside keys — keep both paths when you replace
  its game logic.
- **Delivering unrun code.** Always playtest. "It looks right" is not "it runs".
