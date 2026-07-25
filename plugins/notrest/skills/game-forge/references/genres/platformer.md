# Platformer playbook

The whole genre lives or dies on jump feel. Players can't articulate it, but they
feel instantly when a jump is "floaty" or "sticky". Nail the feel before levels.

## Movement that feels good

- **Separate acceleration from max speed.** Don't set velocity directly from input;
  accelerate toward a target and apply friction. Snappy but not instant:
  `vx += (targetVx - vx) * accel` with a higher accel on ground than in air.
- **Asymmetric gravity.** Apply *stronger* gravity while falling than while rising
  (e.g. 1.6× on the way down). Real jumps feel bad; game jumps need a floaty rise
  and a snappy fall. This one trick fixes most "floaty" complaints.
- **Variable jump height.** If the player releases jump while still rising, cut
  upward velocity (`vy *= 0.5`). Tap = short hop, hold = full jump. Essential.

## The two forgiveness mechanics (players notice their absence)

- **Coyote time.** Let the player still jump for ~0.1 s *after* walking off a ledge.
  Track `timeSinceGrounded`; allow jump if it's under the threshold. Without this,
  players feel cheated by "I pressed jump but nothing happened".
- **Jump buffering.** If the player presses jump ~0.1 s *before* landing, queue it
  and fire on touchdown. Track `timeSinceJumpPressed`; consume on landing.

Both are a few lines each and are the difference between "controls are broken" and
"controls are tight". Always include them.

## Collision: AABB, resolve axes separately

Use axis-aligned bounding boxes against a tile grid or a list of solid rects. The
reliable approach for a beginner-safe platformer is **move-and-resolve one axis at a
time**:

1. Add `vx*dt` to x, check overlaps, push out horizontally, zero `vx` on contact.
2. Add `vy*dt` to y, check overlaps, push out vertically, zero `vy` on contact; if
   you were moving down and hit something, set `grounded = true`.

Resolving axes separately avoids the corner-snag bugs you get from resolving both at
once. For fast-moving objects that could tunnel through thin platforms, cap the step
or do a swept check, but for typical speeds axis-separated AABB is plenty.

## Camera

Lerp the camera toward the player rather than hard-locking (`cam += (target-cam)*0.1`).
Clamp to level bounds so you don't show past the edges. A small look-ahead in the
direction of movement helps players see what's coming.

## Juice that fits the genre

Dust particles on land and on direction-change, squash on landing / stretch at jump
apex, a soft screen shake on hard landings, a distinct sound for jump vs land vs
coin. Parallax background layers (move slower than foreground) add depth cheaply.
See `references/juice.md`.
