# Python / pygame specifics

Pick pygame only when the user wants Python, a desktop app, or is learning game dev
in Python (see SKILL.md "Platform selection"). All the *principles* from
`references/game-loop.md` and `references/juice.md` still apply — this file is the
Python translation and the gotchas.

## Setup and the fixed-timestep loop

```python
import sys, pygame
pygame.init()
W, H = 800, 600
screen = pygame.display.set_mode((W, H))
clock = pygame.time.Clock()
STEP = 1 / 60
acc = 0.0
running = True

while running:
    dt = min(clock.tick(120) / 1000, 0.25)   # real seconds since last frame, clamped
    acc += dt
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
    keys = pygame.key.get_pressed()           # held-state table
    while acc >= STEP:
        update(STEP, keys)                    # advance physics by fixed STEP
        acc -= STEP
    render(screen)
    pygame.display.flip()

pygame.quit()
sys.exit()
```

Same accumulator idea as JS: multiply velocities by `STEP`, clamp `dt` so a stall
doesn't spiral. `clock.tick(120)` caps the frame rate and yields CPU.

## Input

`pygame.key.get_pressed()` gives held state (good for movement). For edge-triggered
actions (jump/shoot once per press), handle `pygame.KEYDOWN` events in the event
loop and set a flag — don't infer edges from the held-state table.

## Drawing

Use `pygame.draw.rect/circle/polygon/line` for procedural shapes (mirrors the Canvas
approach — no image assets needed). Create fonts with `pygame.font.SysFont(None, 48)`
and `font.render(text, True, color)`. For a simple screen shake, offset your blit/
draw origin by a decaying random amount, exactly like the Canvas version.

## Audio without files

Don't hard-depend on `.wav`/`.ogg` files that may not exist. Synthesize short tones
at startup with numpy and `pygame.sndarray.make_sound`, and degrade gracefully to
silence if numpy is unavailable:

```python
try:
    import numpy as np
    def tone(freq=440, ms=120, vol=0.3):
        sr = 44100; n = int(sr * ms/1000)
        t = np.linspace(0, ms/1000, n, False)
        wave = (np.sign(np.sin(2*np.pi*freq*t)) * vol * 32767).astype(np.int16)
        stereo = np.column_stack([wave, wave])
        return pygame.sndarray.make_sound(stereo)
    pygame.mixer.init()
    SND_JUMP = tone(300, 120)
except Exception:
    class _Silent:            # no numpy / no audio device → no crash
        def play(self): pass
    SND_JUMP = _Silent()
```

## Verifying it runs (headless)

You can't see a window here, but you can confirm the game imports and its loop starts
without crashing by running headless with a dummy video/audio driver and a short
auto-quit. Add a tiny frame counter that calls `pygame.quit(); sys.exit()` after,
say, 120 frames when an env var like `GAMEFORGE_SMOKETEST=1` is set, then:

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy GAMEFORGE_SMOKETEST=1 python game.py
```

A clean exit means imports, init, the loop, update, and render all ran. This is the
pygame equivalent of the browser playtest — never deliver an unrun file.

## Delivery

Ship a single `game.py`. State the run command and dependency clearly for the user:
`pip install pygame` (and `numpy` for sound), then `python game.py`. Since it can't
render inline, tell them what to expect on screen and the controls.
