"""
GAME FORGE ENGINE TEMPLATE (pygame, single file)
A runnable starter that wires up what every game needs:
  - fixed-timestep loop (frame-rate independent physics)
  - input: held-state for movement + KEYDOWN edges for one-shot actions
  - state machine (menu / play / over)
  - procedural sound via numpy (degrades to silence if numpy is absent)
  - particles + screen shake (juice)
The demo is a minimal "dodge the falling blocks". Replace the marked GAME LOGIC
sections with your game; keep the loop, input, audio, and juice scaffolding.

Run:   pip install pygame numpy   &&   python engine.py
Smoke test (headless, auto-quits, no window/audio device needed):
       SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy GAMEFORGE_SMOKETEST=1 python engine.py
"""
import os, sys, math, random, pygame

pygame.init()
W, H = 480, 640
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Game")
clock = pygame.time.Clock()
font_big = pygame.font.SysFont(None, 56)
font_mid = pygame.font.SysFont(None, 28)
font_sml = pygame.font.SysFont(None, 22)
SMOKETEST = os.environ.get("GAMEFORGE_SMOKETEST") == "1"

# ---------- AUDIO (procedural; silent fallback) ----------
class _Silent:
    def play(self): pass
def make_tone(freq=440, ms=120, vol=0.3):
    try:
        import numpy as np
        pygame.mixer.init()
        sr = 44100; n = int(sr * ms / 1000)
        t = np.linspace(0, ms / 1000, n, False)
        wave = (np.sign(np.sin(2 * np.pi * freq * t)) * vol * 32767).astype("int16")
        stereo = np.column_stack([wave, wave])
        return pygame.sndarray.make_sound(stereo)
    except Exception:
        return _Silent()
SND_SCORE = make_tone(760, 60, 0.2)
SND_HIT   = make_tone(140, 220, 0.3)
SND_START = make_tone(520, 110, 0.25)

# ---------- JUICE ----------
particles = []  # each: [x,y,vx,vy,life,max,color,size]
def spawn_particles(x, y, color, n=16, spd=220):
    for _ in range(n):
        a = random.random() * math.tau; s = spd * (0.3 + random.random())
        life = 0.4 + random.random() * 0.4
        particles.append([x, y, math.cos(a) * s, math.sin(a) * s, life, life, color, 2 + random.random() * 3])
shake = 0.0

# ---------- STATE ----------
state = "menu"           # 'menu' | 'play' | 'over'
score = 0; best = 0
player = {}; blocks = []; spawn_timer = 0.0
def reset():
    global player, blocks, spawn_timer, score
    player = {"x": W / 2, "y": H - 70, "w": 44, "h": 16, "vx": 0.0}
    blocks = []; spawn_timer = 0.0; score = 0

# ---------- UPDATE ----------
def update(dt, keys, just_pressed):
    global state, score, best, spawn_timer, shake
    for p in particles:
        p[0] += p[2] * dt; p[1] += p[3] * dt; p[3] += 400 * dt; p[4] -= dt
    particles[:] = [p for p in particles if p[4] > 0]
    shake *= math.pow(0.001, dt)

    if state in ("menu", "over"):
        if pygame.K_SPACE in just_pressed:
            reset(); state = "play"; SND_START.play()
        return

    # --- GAME LOGIC update (replace for your game) ---
    accel = 1400.0; want = 0
    if keys[pygame.K_LEFT]:  want -= 1
    if keys[pygame.K_RIGHT]: want += 1
    player["vx"] += want * accel * dt
    player["vx"] *= math.pow(0.0005, dt)
    player["x"] += player["vx"] * dt
    player["x"] = max(player["w"] / 2, min(W - player["w"] / 2, player["x"]))

    spawn_timer -= dt
    rate = max(0.35, 0.9 - score * 0.01)
    if spawn_timer <= 0:
        spawn_timer = rate
        blocks.append({"x": 20 + random.random() * (W - 40), "y": -20,
                       "w": 24, "h": 24, "v": 120 + score * 4 + random.random() * 60})
    for b in blocks[:]:
        b["y"] += b["v"] * dt
        if abs(b["x"] - player["x"]) < (b["w"] / 2 + player["w"] / 2 - 4) and \
           abs(b["y"] - player["y"]) < (b["h"] / 2 + player["h"] / 2 - 2):
            spawn_particles(player["x"], player["y"], (255, 84, 112), 26, 300)
            shake = 16; SND_HIT.play(); best = max(best, score); state = "over"; return
        if b["y"] > H + 30:
            blocks.remove(b); score += 1; SND_SCORE.play()
            if score % 10 == 0: shake = 7

# ---------- RENDER ----------
def draw_text(surf, font, txt, color, cx, cy):
    img = font.render(txt, True, color); r = img.get_rect(center=(cx, cy)); surf.blit(img, r)
def render():
    screen.fill((18, 22, 42))
    ox = random.uniform(-1, 1) * shake; oy = random.uniform(-1, 1) * shake
    # NOTE: pygame ignores the alpha channel in draw colors on a plain surface —
    # use a pre-dimmed solid color for subtle background lines, not (r,g,b,alpha).
    for x in range(0, W, 32): pygame.draw.line(screen, (28, 33, 58), (x + ox, 0), (x + ox, H))
    if state in ("play", "over"):
        for b in blocks:
            pygame.draw.rect(screen, (255, 194, 60),
                             (b["x"] - b["w"] / 2 + ox, b["y"] - b["h"] / 2 + oy, b["w"], b["h"]), border_radius=5)
        pygame.draw.rect(screen, (77, 225, 193),
                         (player["x"] - player["w"] / 2 + ox, player["y"] - player["h"] / 2 + oy,
                          player["w"], player["h"]), border_radius=6)
    for p in particles:
        alpha = max(0, p[4] / p[5])
        c = (int(p[6][0]), int(p[6][1]), int(p[6][2]))
        pygame.draw.circle(screen, c, (int(p[0] + ox), int(p[1] + oy)), max(1, int(p[7] * alpha)))
    if state == "play":
        draw_text(screen, font_mid, f"Score {score}", (255, 255, 255), 60, 24)
    if state == "menu":
        draw_text(screen, font_big, "DODGER", (255, 255, 255), W // 2, H // 2 - 30)
        draw_text(screen, font_sml, "Move with LEFT / RIGHT. Dodge the blocks.", (159, 179, 209), W // 2, H // 2 + 8)
        draw_text(screen, font_sml, "Press Space to start", (77, 225, 193), W // 2, H // 2 + 40)
    if state == "over":
        draw_text(screen, font_big, "GAME OVER", (255, 255, 255), W // 2, H // 2 - 30)
        draw_text(screen, font_sml, f"Score {score}    Best {best}", (159, 179, 209), W // 2, H // 2 + 8)
        draw_text(screen, font_sml, "Press Space to retry", (77, 225, 193), W // 2, H // 2 + 40)
    pygame.display.flip()

# ---------- FIXED-TIMESTEP LOOP ----------
STEP = 1 / 60; acc = 0.0; running = True; frames = 0
reset(); state = "menu"
while running:
    dt = min(clock.tick(120) / 1000, 0.25); acc += dt
    just_pressed = set()
    for e in pygame.event.get():
        if e.type == pygame.QUIT: running = False
        elif e.type == pygame.KEYDOWN: just_pressed.add(e.key)
    # Smoke test: keep injecting SPACE while on menu/over screens (not a single
    # exact frame — a one-frame press can be dropped if no fixed-timestep sub-step
    # happens to run that frame, leaving the test stuck on the menu).
    if SMOKETEST and frames >= 8 and state in ("menu", "over"):
        just_pressed.add(pygame.K_SPACE)
    keys = pygame.key.get_pressed()
    while acc >= STEP:
        update(STEP, keys, just_pressed); just_pressed = set(); acc -= STEP
    render()
    frames += 1
    if SMOKETEST and frames > 120:  # ran menu+play without crashing → exit clean
        print("SMOKETEST OK: loop, update, render ran for", frames, "frames"); running = False
pygame.quit(); sys.exit()
