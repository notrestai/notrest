#!/usr/bin/env node
/*
 * playtest.mjs — automated smoke test for a Game Forge HTML game.
 *
 * Loads the game in headless Chromium, FAILS on any console error / page error,
 * simulates input, and writes a screenshot so you can visually confirm it renders
 * (not a blank screen). This is what makes "on the fly" reliable: never hand the
 * user a game you haven't actually run.
 *
 * Usage:
 *   node playtest.mjs <path-to-game.html> [screenshotPath] [--keys Space,ArrowLeft]
 *
 * Exit code 0 = passed; non-zero = something is broken (read the printed errors).
 *
 * Requires Playwright. In this environment Chromium is preinstalled at
 * /opt/pw-browsers — the script points at it and does NOT download anything.
 */
import { pathToFileURL } from 'url';
import { existsSync } from 'fs';
import path from 'path';
import { createRequire } from 'module';
import { execSync } from 'child_process';

// Resolve playwright wherever it lives: local node_modules first, then the
// global npm root. A hard `import ... from 'playwright'` fails whenever the
// script runs outside a directory with playwright installed — this doesn't.
const require = createRequire(import.meta.url);
let chromium;
try {
  ({ chromium } = require('playwright'));
} catch {
  try {
    const globalRoot = execSync('npm root -g', { encoding: 'utf8' }).trim();
    ({ chromium } = require(path.join(globalRoot, 'playwright')));
  } catch {
    console.error('ERROR: playwright not found. Install it with: npm install -g playwright');
    process.exit(2);
  }
}

const args = process.argv.slice(2);
const gamePath = args[0];
if (!gamePath || !existsSync(gamePath)) {
  console.error('ERROR: pass a path to an existing .html game file.');
  process.exit(2);
}
const shot = args[1] && !args[1].startsWith('--') ? args[1]
  : gamePath.replace(/\.html?$/i, '') + '.playtest.png';
const keysArg = (args.find(a => a.startsWith('--keys=')) || '').split('=')[1]
  || (args.includes('--keys') ? args[args.indexOf('--keys') + 1] : 'Space');
const keys = keysArg.split(',').map(s => s.trim()).filter(Boolean);

const exe = '/opt/pw-browsers/chromium';
const launchOpts = existsSync(exe) ? { executablePath: exe } : {};

const errors = [];
const browser = await chromium.launch(launchOpts);
const page = await browser.newPage({ viewport: { width: 520, height: 700 } });
page.on('console', m => { if (m.type() === 'error') errors.push('console.error: ' + m.text()); });
page.on('pageerror', e => errors.push('pageerror: ' + (e && e.message || e)));

try {
  await page.goto(pathToFileURL(path.resolve(gamePath)).href, { waitUntil: 'load' });
  await page.waitForTimeout(500);            // let the loop spin up

  // focus the canvas and drive some input
  const canvas = await page.$('canvas');
  if (canvas) await canvas.click({ position: { x: 60, y: 60 } }).catch(() => {});
  for (const k of keys) { await page.keyboard.press(k).catch(() => {}); await page.waitForTimeout(120); }
  // hold a couple of keys briefly to exercise movement
  await page.keyboard.down('ArrowLeft').catch(() => {}); await page.waitForTimeout(300);
  await page.keyboard.up('ArrowLeft').catch(() => {});
  await page.waitForTimeout(1200);           // let the game run a bit

  // if the template's debug hook is present, report state
  const gs = await page.evaluate(() => (window.__game && window.__game.get) ? window.__game.get() : null);

  // detect an all-black / blank canvas (common failure: nothing drew)
  const blank = await page.evaluate(() => {
    const c = document.querySelector('canvas'); if (!c) return 'no-canvas';
    const g = c.getContext('2d'); const d = g.getImageData(0, 0, c.width, c.height).data;
    let nonBg = 0; for (let i = 0; i < d.length; i += 4 * 97) { if (d[i] > 30 || d[i+1] > 30 || d[i+2] > 60) nonBg++; }
    return nonBg < 3 ? 'blank-canvas' : null;
  });

  await page.screenshot({ path: shot });

  if (blank) errors.push('render: ' + blank + ' (canvas appears empty — nothing is drawing)');

  if (errors.length) {
    console.error('PLAYTEST FAILED:\n - ' + errors.join('\n - '));
    console.error('screenshot: ' + shot);
    await browser.close(); process.exit(1);
  }
  console.log('PLAYTEST OK');
  if (gs) console.log('game state:', JSON.stringify(gs));
  console.log('screenshot:', shot);
  await browser.close();
  process.exit(0);
} catch (e) {
  console.error('PLAYTEST ERROR:', e && e.message || e);
  await browser.close(); process.exit(3);
}
