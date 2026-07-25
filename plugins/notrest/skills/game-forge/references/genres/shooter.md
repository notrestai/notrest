# Shooter playbook

Covers top-down twin-stick, side-scrolling shmup, and vertical space shooters. The
feel goal is a screen busy with bullets and feedback without the code turning into
spaghetti — pooling and data-driven waves are how you get there.

## Bullets: pool them

Never `new` a bullet per shot and let it fall out of the array via `filter` every
frame — the allocation/GC churn causes stutter once bullets get dense. Keep a fixed
array of bullet objects with an `active` flag; spawn by finding an inactive one,
despawn by flipping the flag. Same for enemies and particles.

```js
const bullets = Array.from({length: 256}, () => ({x:0,y:0,vx:0,vy:0,active:false}));
function fire(x,y,vx,vy){ const b=bullets.find(b=>!b.active); if(b){Object.assign(b,{x,y,vx,vy,active:true});} }
```

## Firing

- **Auto-fire** (hold to shoot, or always shooting) is more forgiving and common in
  shmups — gate it with a fire-rate cooldown timer, not per-frame.
- **Twin-stick**: aim with mouse/right-stick independent of movement. Bullet
  velocity = normalized (aim − player) × speed.
- Give bullets a lifetime or despawn off-screen so the pool doesn't fill up.

## Enemies and waves

Drive spawning from data, not hardcoded spaghetti — a timeline of `{time, type, x}`
entries, or a wave counter that spawns N of a type then escalates. Enemy *patterns*
are just movement functions: sine-weave (`x += sin(t)*amp`), dive-at-player, or
formation drift. A couple of patterns plus scaling count/speed gives lots of variety
cheaply.

## Collision

Circle-vs-circle is easiest and looks fine for bullets: overlap if distance² <
(r1+r2)². Check bullets vs enemies and enemies/enemy-bullets vs player. Give the
player a slightly *smaller* hitbox than their sprite ("forgiving hitbox") — players
perceive it as fair; a pixel-perfect hitbox feels cheap.

## Feel

Muzzle flash and a shoot sound on every shot, a burst of particles + screen shake +
a hit sound on every kill, brief hit-stop on the player taking damage, screen flash
on death. Bullet trails (draw a short line behind fast bullets) sell speed. A slow
starfield/parallax background implies motion. See `references/juice.md`. Consider a
short i-frame invulnerability blink after the player is hit so they can recover.
