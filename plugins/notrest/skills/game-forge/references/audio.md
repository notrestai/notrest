# Procedural audio with WebAudio (no sound files)

Sound is the cheapest, highest-impact juice — and the most common failure mode is
depending on `.mp3`/`.wav` files that don't exist or won't load. Generate every
sound at runtime with the WebAudio API instead. Zero assets, always works, stays in
the single HTML file.

## Setup and the browser autoplay gotcha

Browsers suspend audio until a user gesture. Create the context lazily/resume it on
the first input, or sounds silently fail:

```js
let actx;
function audio() {
  if (!actx) actx = new (window.AudioContext || window.webkitAudioContext)();
  if (actx.state === 'suspended') actx.resume();
  return actx;
}
// call audio() inside your first keydown/pointerdown handler, then freely after.
```

## A tiny synth: one function covers most game sounds

Most retro game sounds are a short oscillator tone with a fast volume envelope and
sometimes a pitch sweep. This one helper gets you jumps, shoots, blips, and coins:

```js
function beep({freq=440, freq2=freq, type='square', dur=0.12, vol=0.2}) {
  const a = audio(), t = a.currentTime;
  const osc = a.createOscillator(), g = a.createGain();
  osc.type = type;                          // 'square'=retro, 'sine'=soft, 'sawtooth'=harsh, 'triangle'=mellow
  osc.frequency.setValueAtTime(freq, t);
  osc.frequency.exponentialRampToValueAtTime(Math.max(1, freq2), t + dur); // pitch sweep
  g.gain.setValueAtTime(vol, t);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);   // fast decay = punchy
  osc.connect(g).connect(a.destination);
  osc.start(t); osc.stop(t + dur);
}
```

Recipes:
- **Jump:** `beep({freq:300, freq2:600, type:'square', dur:0.12})` — rising sweep.
- **Shoot:** `beep({freq:800, freq2:200, type:'sawtooth', dur:0.1})` — falling zap.
- **Coin/pickup:** two quick ascending blips (`523` then `784` a moment later).
- **Hit/hurt:** `beep({freq:160, freq2:60, type:'square', dur:0.2, vol:0.3})`.
- **Menu move:** `beep({freq:440, dur:0.05, vol:0.1})` — very short tick.

## Noise for explosions/whooshes

Tonal oscillators can't make explosions or footsteps — those need noise. Generate a
short white-noise buffer and filter it:

```js
function noise({dur=0.3, vol=0.3, cutoff=1000} = {}) {
  const a = audio(), n = Math.floor(a.sampleRate * dur);
  const buf = a.createBuffer(1, n, a.sampleRate);
  const d = buf.getChannelData(0);
  for (let i=0;i<n;i++) d[i] = Math.random()*2-1;
  const src = a.createBufferSource(); src.buffer = buf;
  const lp = a.createBiquadFilter(); lp.type='lowpass'; lp.frequency.value=cutoff;
  const g = a.createGain();
  g.gain.setValueAtTime(vol, a.currentTime);
  g.gain.exponentialRampToValueAtTime(0.0001, a.currentTime + dur);
  src.connect(lp).connect(g).connect(a.destination);
  src.start();
}
// explosion: noise({dur:0.4, vol:0.4, cutoff:800})
```

## Simple background music (optional)

A short arpeggio looped on a timer gives ambient energy without a music file: hold
an array of note frequencies and `beep` the next one every ~200 ms with a mellow
`triangle` wave at low volume. Keep it quiet and let the player mute it (M key) —
always offer a mute, since audio is the first thing some players want off.

## pygame audio

pygame can synthesize similarly via `numpy` + `pygame.sndarray`, but it's more
involved. For pygame games, prefer generating a couple of short tones at startup
with numpy, or gracefully degrade to silence if numpy isn't available — never hard-
depend on external sound files there either. See `references/pygame.md`.
