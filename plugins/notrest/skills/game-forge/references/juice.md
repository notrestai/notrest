# Juice: the polish that makes games feel good

"Juice" is the maximal output for minimal input — the pile of small feedback
effects that make an action feel *satisfying*. The same jump with screen shake,
a squash on landing, a dust puff, and a soft thud feels ten times better than a
rectangle teleporting upward in silence. This is the highest-leverage work in the
whole build and the thing a naive generation always skips. Budget real time for it.

Work through this checklist. You don't need all of it in every game, but a game
with *none* of it feels dead. Aim for feedback on every meaningful action.

## The checklist

**Sound on everything.** Every action the player takes and every reaction the world
gives should make a noise — jump, land, shoot, hit, pickup, score, die, menu-move.
Silence reads as "broken". Use procedural WebAudio (`references/audio.md`); it's
cheap and needs no files. This is #1 for a reason.

**Screen shake.** On impacts, explosions, deaths, big hits. Implement as a decaying
offset applied to the whole canvas transform:
```js
let shake = 0;                       // set shake = 8 on a big hit
// in render, before drawing the world:
const sx = (Math.random()*2-1)*shake, sy = (Math.random()*2-1)*shake;
ctx.save(); ctx.translate(sx, sy);
// ...draw world...
ctx.restore();
shake *= 0.9;                        // decay each frame
```
Keep it subtle — a few pixels. Too much is nauseating.

**Hit-stop (freeze frames).** On a heavy hit, pause the simulation for 2–4 frames.
The tiny stutter makes impacts feel weighty. Implement with a `hitStop` counter that,
while > 0, skips `update` but still renders.

**Particles.** Bursts of small shapes on impacts, jumps (dust), pickups (sparkle),
death (debris). A simple pooled system: each particle has position, velocity, life,
color, size; spawn 8–20 on an event, fade and shrink over life. Cheap and hugely
effective. Pool them (reuse dead ones) to avoid GC stutter.

**Tweening / easing.** Nothing good moves linearly. Menus slide in, pickups pop
(scale 0→1.2→1), the score counts up instead of snapping. Ease-out for things
arriving, ease-in for things leaving. `easeOutBack` gives a satisfying overshoot:
```js
const easeOutBack = t => 1 + 2.7*Math.pow(t-1,3) + 1.7*Math.pow(t-1,2);
```

**Squash & stretch.** Deform on acceleration: a character stretches vertically while
rising, squashes on landing; a ball flattens on impact. Scale x and y inversely so
volume looks preserved. Sells weight and life more than any sprite detail.

**Anticipation & follow-through.** A tiny wind-up before a big action and a settle
after. Even 3–4 frames reads as intentional and alive.

**Juicy numbers & feedback.** Floating "+100" text that rises and fades on score.
Flash the screen white for 1 frame on a big event. Flash a hit enemy white. Combo
counters that scale up with each hit.

**Camera feel.** Don't hard-lock the camera to the player — lerp toward the target
(`cam += (target - cam) * 0.1`) for a smooth trailing follow. Optionally lead in the
direction of motion. Add a slight zoom punch on big moments.

**Juicy start & death.** Enemies/blocks pop in with a scale tween rather than
appearing instantly. On death, explode the player into particles rather than just
switching states. First impressions and last impressions carry a lot of the feel.

**Color & contrast.** A tight, high-contrast palette (dark background, a few vivid
accent colors) looks far more intentional than many muddy colors. Add a subtle
background — a gradient, parallax dots/stars, a grid — so the play space isn't a
flat void. Round line caps and a slight glow (`shadowBlur`) make shapes feel modern.

## The rule of thumb

For each thing that happens in your game, ask: *does the player see, hear, and feel
it?* Sight (particle/flash/animation), sound (a blip), feel (shake/hit-stop). If an
important event hits zero of those three, add at least one. That single habit is
most of what "game feel" is.
