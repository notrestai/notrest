---
name: game-forge
description: >-
  Build a complete, polished, playable game from a short request — on the fly.
  Use this skill whenever the user wants to make, build, generate, prototype, or
  "vibe-code" a game of any kind: an arcade game, platformer, shooter, puzzle,
  tower defense, snake/breakout/tetris-style classic, an idle/clicker, a roguelike,
  a physics toy, a "game like X but Y", a browser game, or a Python/pygame game.
  Trigger even when the user is casual ("make me something fun to play", "build a
  little game about a cat dodging rain") or doesn't say the word "game" explicitly
  but clearly wants something interactive and playable. Do NOT trigger for game
  *reviews*, buying advice, lore/story questions, or non-interactive animations.
  This skill encodes what separates a real game from a throwaway demo — a correct
  game loop, responsive input, game feel/juice, self-contained assets, and an
  automated playtest — so every generation clears a quality bar instead of being
  hit-or-miss.
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
this skill always **runs the game before handing it over** and fixes what it finds.

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
   you have not run.

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
