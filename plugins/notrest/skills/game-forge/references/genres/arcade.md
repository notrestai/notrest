# Arcade playbook

Single-screen classics and endless score-chasers: snake, breakout/pong, asteroids,
flappy-style dodgers, endless runners, dodge-the-falling-things. These are the best
"on the fly" games — small, self-contained, instantly fun when the core verb is
tuned. Ship fast, then juice.

## Shared skeleton

- **One screen, no camera** (mostly). The whole play field is visible; state is a
  handful of entities.
- **Score + high score.** Score is the point. Show it big. Track a session high
  score (in memory) and celebrate beating it — it's the core loop of "one more try".
- **Lives or one-hit death.** Decide up front. One-hit + instant restart (press to
  retry) suits score-chasers; a few lives suits breakout/asteroids.
- **Difficulty ramp.** The engine of replayability. Increase speed / spawn rate /
  reduce gaps as score or time climbs. A game that never gets harder gets boring in
  20 seconds. Ramp gradually and keep it going.
- **Instant restart.** On death, "press Space to play again" that resets in one
  keystroke. Friction here kills the "one more try" loop.

## Per-classic notes

- **Snake:** grid-based; move on a timer (not per-frame); grow on food; die on self/
  wall. Speed up slightly as it grows. Watch the classic bug: check self-collision
  against the body *before* moving the tail.
- **Breakout/Pong:** ball as circle, paddle/bricks as AABB; reflect velocity on hit;
  vary bounce angle by where the ball hits the paddle (edges = sharper) so the player
  has control. Juice brick breaks hard — particles, shake, rising combo pitch.
- **Asteroids:** thrust + rotation with inertia (velocity persists), screen-wrap at
  edges, split asteroids into smaller ones on hit. Momentum feel is the whole game.
- **Flappy/dodger:** simple gravity + flap impulse, procedurally spawned obstacles
  with a gap, score per obstacle passed. Tune gravity/impulse/gap until it's hard
  but fair — that tuning *is* the game.
- **Endless runner:** auto-scroll world, jump/duck input, spawn obstacles on a timer
  with a guaranteed-clearable spacing, speed ramp over distance.

## Feel

Arcade games live on juice because they're mechanically simple — the polish is the
product. Screen shake on death/impact, particles on every score event, a punchy
sound per action, a floating score popup, a color-flash on milestones, and a snappy
death animation. A subtle animated background (scrolling stars, gradient shift) lifts
the whole thing. See `references/juice.md`.
