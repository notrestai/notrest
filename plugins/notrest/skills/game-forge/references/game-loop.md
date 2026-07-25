# The Game Loop

The loop is the heartbeat of a game. Get it wrong and everything downstream feels
wrong — physics that speeds up on fast machines, input that misses presses,
animation that stutters. The template already implements the pattern below; this
file explains *why* so you can adapt it confidently.

## The core problem: decouple simulation from rendering

`requestAnimationFrame` fires roughly once per display refresh — but that's ~60 Hz
on most screens, 120+ Hz on some, and drops under load. If you advance physics by
"one step" per frame, the game literally runs faster on a 120 Hz monitor and slows
down during a hiccup. That's the classic bug.

The fix is a **fixed-timestep accumulator**: simulate the world in fixed slices
(e.g. 1/60 s) regardless of how often you draw, and render whenever the display is
ready. Render can interpolate between the last two physics states for smoothness.

## Canonical JS loop (in the template)

```js
const STEP = 1 / 60;          // fixed simulation slice, seconds
let last = performance.now();
let acc = 0;

function frame(now) {
  acc += Math.min((now - last) / 1000, 0.25); // clamp to avoid spiral-of-death
  last = now;
  while (acc >= STEP) {
    update(STEP);             // physics/logic advance by exactly STEP
    acc -= STEP;
  }
  render(acc / STEP);         // alpha in [0,1) for interpolation
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
```

Key details and why they matter:

- **Clamp the accumulator** (`Math.min(..., 0.25)`). If the tab is backgrounded and
  returns after 10 s, without the clamp you'd run 600 update steps in one frame and
  freeze. Clamping drops time instead — the game "loses" a moment but stays alive.
- **`while (acc >= STEP)`** can run 0, 1, or several updates per frame. That's
  correct: a slow frame catches up with multiple steps; a fast display renders the
  same state twice (interpolated). If you additionally cap the steps per frame
  (e.g. `&& steps < 5`), you must **drop the leftover accumulator when the cap is
  hit** (`acc = 0`) — otherwise the backlog carries over forever and the game runs
  in permanent slow motion after one sustained hiccup.
- **Pass `STEP` (dt) into update**, and multiply all velocities/accelerations by it.
  Never hardcode per-frame deltas. This is what makes speed identical everywhere.
- **Interpolation alpha** is optional polish: `render(alpha)` can lerp between
  previous and current position (`prev + (cur - prev) * alpha`) for buttery motion.
  Skip it for a first pass; add it if motion looks steppy.

## Input manager

Games need three questions answered every step: is a key *held*, was it *just
pressed* this step, was it *just released*. Polling raw DOM events inside update
misses fast taps. The template keeps a state table:

```js
const keys = {};        // current held state
const pressed = {};     // edge: true only on the step the key went down

addEventListener('keydown', e => {
  if (!keys[e.code]) pressed[e.code] = true;   // edge trigger
  keys[e.code] = true;
  if (JUMP_KEYS.includes(e.code)) e.preventDefault(); // stop page scroll
});
addEventListener('keyup', e => { keys[e.code] = false; });

// at the END of each update step:
function endStep() { for (const k in pressed) pressed[k] = false; }
```

Use `keys['ArrowLeft']` for continuous movement and `pressed['Space']` for a
jump/shoot that should fire once per tap. Clear `pressed` at the end of the step,
not the frame. Add pointer/touch handlers the same way for mobile support.

## State machine

Even a tiny game has menu → playing → paused → game-over. A flat `if` soup gets
unmanageable fast. Keep a single `state` string and switch update/render on it:

```js
let state = 'menu';   // 'menu' | 'play' | 'over'
function update(dt){ if (state==='play') updatePlay(dt); else updateMenu(dt); }
function render(a){ /* draw per state */ }
```

Transitions (start, die, restart) just reassign `state` and reset the relevant
variables. This keeps "press R to restart" trivial and bug-free.

## Adapting the loop

- **Turn-based / puzzle games** don't need fixed-timestep physics, but still use
  the same rAF loop for smooth animations and input; advance game logic on discrete
  player actions instead of on `dt`.
- **Idle/clicker** games can use a slower logic tick (e.g. every 100 ms) layered on
  top of the render loop for number growth.
- **Heavy particle counts**: cap the array length and reuse dead particles (object
  pooling) rather than allocating every frame — GC pauses cause stutter.
