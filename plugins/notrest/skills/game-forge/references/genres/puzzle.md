# Puzzle playbook

Covers match-3, tile-swap, sliding, block-drop (tetris-like), and grid logic games.
These are usually turn/action-based rather than physics-based, so the loop is used
for *animation and input*, while game state advances on discrete moves.

## Model the grid as data, render from it

Keep the board as a 2-D array of cell values (or `null`/`0` for empty). All rules —
matching, clearing, gravity, win-check — operate on this array. Rendering just draws
the array. This separation keeps the logic testable and the bugs shallow.

```js
const W=8, H=8;
const grid = Array.from({length:H}, () => Array(W).fill(0));
const at = (x,y) => (x>=0&&x<W&&y>=0&&y<H) ? grid[y][x] : null;
```

## Core operations

- **Match detection**: scan rows and columns for runs of ≥3 equal non-empty cells;
  collect their coordinates into a set to clear. For flood-based games (same-color
  blobs), use BFS/DFS from a cell.
- **Clear + gravity + refill**: null out matched cells, then for each column let
  cells fall into the gaps (iterate from bottom up), then fill the top with new
  values. Loop match→clear→gravity until no new matches (cascades).
- **Swap validity** (match-3): only allow a swap if it produces a match; otherwise
  animate a swap-and-swap-back so the player sees it was rejected.
- **Win/lose**: board cleared, target score, no legal moves left, or (tetris-like) a
  piece locks above the top row.

## Timing model

Advance logic on player action (a click, a key, a swap), not on `dt`. Use `dt` only
to animate the *transition* — tiles sliding into place, cleared tiles shrinking out,
new tiles dropping in. A short animation lock (ignore input while animating) prevents
the player from desyncing the board mid-cascade.

## Undo

Puzzle players expect undo. It's trivial if state is data: push a deep copy of the
grid (and score) onto a stack before each move; pop to undo. Cheap and much-loved.

## Feel

Satisfying puzzles lean on *escalating* feedback: a pop sound and particle burst per
cleared tile, rising pitch through a cascade combo, a "+N" float, a screen shake on
a big clear, a gentle idle bob on swappable tiles. Snappy but eased tile movement
(ease-out) is most of the tactile satisfaction. See `references/juice.md`.
