#!/usr/bin/env node
// server.mjs — Atlas read-only MCP v0.1. © 2026 Not Rest Inc. Part of Atlas; licensed with the notrest plugin. Authored by the Atlas seat (atlas-ce), 2026-09-06.
// atlas MCP server — read-only agent surface over the atlas hub.  v0.1
//
// WHY THIS EXISTS
//   A fresh session should be able to ask one question and receive a BOUNDED view of a
//   project instead of reading a hundred files.  The north star is time-to-context.
//
// LAWS IN FORCE (they shape the code below, not just the prose)
//   read-only            — every route this server speaks is a GET.  There is no write
//                          path, no token that could authorize one, and no tool that
//                          takes a mutation argument.
//   never owns authority — atlas reports what estates pushed.  It never decides, approves,
//                          or ranks work as "should do next".
//   secrets by path      — the view bearer is read from a FILE whose PATH comes from the
//                          environment (ATLAS_VIEW_FILE).  The value is never an argv,
//                          never an env value, never logged, never returned to a client.
//   finding text stays   — the hub carries finding COUNTS only, so no finding body can
//     in the estate       reach this process.  atlas_findings says so out loud rather than
//                          leaving the caller to assume the text is missing by accident.
//   derived never        — every number here is either the hub's own, or derived by the
//     invented            same rule the hub uses (hub/validate.mjs rollup()).  A field the
//                          snapshot does not carry is reported as "unknown", never guessed.
//
// TRANSPORT: newline-delimited JSON-RPC 2.0 over stdio (one compact JSON object per line,
// "\n" terminated).  This is the framing MCP stdio clients (Claude Code, Codex) use.
// Content-Length framing is NOT implemented.  stdout carries protocol bytes and nothing
// else; every diagnostic goes to stderr.
//
// Node >= 22, ESM, ZERO dependencies.
//
// FLAGS
//   --selftest   run every tool against the in-process FIXTURE hub and print a verdict.
//                Never touches the network.
// ENV
//   ATLAS_HUB_BASE   default https://atlas.not.rest
//   ATLAS_VIEW_FILE  default /home/dev/.atlas-hub-secrets/view   (a PATH, never a value)
//   ATLAS_MCP_FIXTURE=1  serve from the in-process fixture hub instead of the network

import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, "..");

const SERVER_NAME = "atlas";
const SERVER_VERSION = "0.1";
const DEFAULT_PROTOCOL = "2025-06-18";

const HUB_BASE = (process.env.ATLAS_HUB_BASE || "https://atlas.not.rest").replace(/\/+$/, "");
const VIEW_FILE = process.env.ATLAS_VIEW_FILE || "/home/dev/.atlas-hub-secrets/view";
const FIXTURE = process.env.ATLAS_MCP_FIXTURE === "1" || process.argv.includes("--selftest");

// Bounds.  Every tool is capped so no answer can grow with the estate.
const CAP = {
  projects: 64,      // rollup rows
  level1: 48,        // nodes returned by atlas_project
  subtree: 80,       // nodes returned by atlas_subtree
  parts: 40,         // parts shown for one node
  edges: 60,         // edges returned anywhere
  steps: 40,         // journey steps
  centrality: 25,    // blocker centrality rows
  searchProjects: 12,
  searchHits: 40,
  historyDefault: 10,
  historyMax: 50,
  contextBytes: 3900, // atlas_relevant_context hard budget (~4 KB)
};

// ---------------------------------------------------------------------------
// secret handling — by PATH, cached, never printed
// ---------------------------------------------------------------------------
const FIXTURE_TOKEN = "fixture-view-token-never-real";
let viewCache;   // { token } on success, { err } on failure — the token is never logged.

function viewSecret() {
  if (FIXTURE) return { token: FIXTURE_TOKEN };
  if (viewCache) return viewCache;
  try {
    const raw = readFileSync(VIEW_FILE, "utf8").trim();
    if (!raw) viewCache = { err: `view secret: the file at ATLAS_VIEW_FILE (${VIEW_FILE}) is empty` };
    else viewCache = { token: raw };
  } catch {
    viewCache = { err: `view secret: cannot read the file at ATLAS_VIEW_FILE (${VIEW_FILE})` };
  }
  return viewCache;
}

// Defence in depth: nothing this process writes may carry the bearer, even by accident.
function redact(s) {
  const v = viewCache && viewCache.token;
  let out = String(s);
  if (v && v.length > 3) out = out.split(v).join("[redacted]");
  return out;
}
const logErr = (msg) => { try { process.stderr.write(redact(msg) + "\n"); } catch {} };

// ---------------------------------------------------------------------------
// hub access — GET only, one fact per error, never throws to the client
// ---------------------------------------------------------------------------
// Returns { ok:true, data } or { ok:false, error:"<one fact>", status:<code> }.
async function hubGet(path, { text = false } = {}) {
  const sec = viewSecret();
  if (sec.err) return { ok: false, error: sec.err, status: 401 };
  if (FIXTURE) return fixtureGet(path, { text });
  let res;
  try {
    res = await fetch(HUB_BASE + path, {
      method: "GET",   // read-only: this is the only verb in the file
      headers: { authorization: `Bearer ${sec.token}`, accept: text ? "text/*" : "application/json" },
    });
  } catch (e) {
    return { ok: false, error: `hub unreachable at ${HUB_BASE}: ${String(e && e.message || e)}`, status: 0 };
  }
  const body = await res.text().catch(() => "");
  if (!res.ok) {
    let fact = "";
    try { fact = JSON.parse(body).error || ""; } catch {}
    if (res.status === 401) {
      // Say the secret is missing/invalid — never any part of its value.
      return { ok: false, status: 401,
        error: `view secret: the hub refused it (401). Check the file at ATLAS_VIEW_FILE (${VIEW_FILE}); its contents are never printed.` };
    }
    return { ok: false, status: res.status, error: fact || `hub returned HTTP ${res.status}` };
  }
  if (text) return { ok: true, data: body };
  try { return { ok: true, data: JSON.parse(body) }; }
  catch { return { ok: false, error: "hub returned a body that is not JSON", status: 502 }; }
}

// ---------------------------------------------------------------------------
// FIXTURE HUB — in-process, no network, used by --selftest and ATLAS_MCP_FIXTURE=1
// ---------------------------------------------------------------------------
// Serves hub/fixtures/kernel-wire1.json as project "kernel" plus one small synthetic
// project ("demo") so cross-project tools have more than one row to work with.  The
// rollup is SYNTHESIZED with the same rule the hub uses (hub/validate.mjs rollup() +
// connectedOf()), so fixture numbers and live numbers cannot mean different things.
let fixtureWires;
function fixtureProjects() {
  if (fixtureWires) return fixtureWires;
  let kernel = null;
  try { kernel = JSON.parse(readFileSync(join(REPO, "hub", "fixtures", "kernel-wire1.json"), "utf8")); }
  catch { kernel = null; }
  const now = new Date().toISOString();
  const demo = {
    schema_version: "atlas-hub/1", project: "demo", stamp: "fixture", taken_at: now,
    playbook: "1.1", head: "demo000000000000000000000000000000000000",
    sources: { snapshot: "available", git: "available", tests: "unknown" },
    nodes: [
      { id: "demo", kind: "product", title: "Demo Product", parts: [] },
      { id: "api", kind: "component", parent: "demo", title: "Auth API", parts: [
        { id: "login", label: "password login", status: "done", evidence: "proven", check: "tests/auth.test.mjs" },
        { id: "token", label: "session token rotation", status: "wip", evidence: "unverified" } ] },
      { id: "store", kind: "component", parent: "demo", title: "Token Store", parts: [
        { id: "kv", label: "kv persistence for tokens", status: "todo", evidence: "unverified" } ] },
    ],
    edges: [{ from: "api.token", to: "store.kv", kind: "data", relation: "token → store" }],
    journey: { name: "SHIP AUTH", objective: "A user logs in and the session token rotates.",
      steps: [ { step_id: "login", label: "user logs in", order: 0, refs: ["api.login"] },
               { step_id: "rotate", label: "token rotates and persists", order: 1, refs: ["api.token", "store.kv"] } ] },
    findings: { count: 3, recurring: 1 },
    links: [],
  };
  fixtureWires = new Map();
  if (kernel) fixtureWires.set("kernel", kernel);
  fixtureWires.set("demo", demo);
  return fixtureWires;
}

function fixtureGet(path, { text }) {
  const [p, qs] = path.split("?");
  const q = new URLSearchParams(qs || "");
  const wires = fixtureProjects();
  const nf = { ok: false, status: 404, error: "not found" };

  if (p === "/v1/projects") {
    const now = Date.now();
    const projects = [...wires.entries()].map(([project, snap]) => ({
      project, stamp: snap.stamp, taken_at: snap.taken_at,
      playbook: typeof snap.playbook === "string" ? snap.playbook : null,
      links: snap.links || [], board: project === "kernel",
      ...connectedOf(snap, now), ...rollupOf(snap),
    })).sort((a, b) => a.project.localeCompare(b.project));
    return { ok: true, data: { projects, wire: "atlas-hub/1", playbook_current: "1.1" } };
  }
  let m = /^\/v1\/snapshot\/([^/]+)$/.exec(p);
  if (m) {
    const snap = wires.get(m[1]);
    return snap ? { ok: true, data: snap } : { ok: false, status: 404, error: "project: no snapshot stored" };
  }
  // history + diff exist for "kernel" only, so BOTH branches are exercised: the compaction
  // path, and the "hub has no history route yet" path (any 404).
  m = /^\/v1\/history\/([^/]+)$/.exec(p);
  if (m) {
    if (m[1] !== "kernel") return nf;
    const snap = wires.get("kernel");
    if (!snap) return { ok: false, status: 404, error: "project: no snapshot stored" };   // fixture wire absent: refuse, never throw
    const limit = Math.min(Number(q.get("limit")) || CAP.historyDefault, CAP.historyMax);
    // shapes mirror the live hub as observed on 2026-09-05: ts is the stamp STRING the key
    // is built from, not an epoch number.
    const all = ["20260905T141346Z", "20260905T072714Z", "20260904T221501Z"].map((ts) => ({
      key: `snap:kernel:${ts}`, ts,
      taken_at: snap.taken_at, stamp: snap.stamp, head: snap.head,
      schema_version: snap.schema_version, playbook: snap.playbook,
    }));
    return { ok: true, data: { project: "kernel", snapshots: all.slice(0, limit), truncated: all.length > limit } };
  }
  m = /^\/v1\/diff\/([^/]+)$/.exec(p);
  if (m) {
    if (m[1] !== "kernel") return nf;
    if (!wires.get("kernel")) return { ok: false, status: 404, error: "project: no snapshot stored" };
    return { ok: true, data: {
      project: "kernel",
      // the live hub answers with snapshot OBJECTS here, not bare keys
      a: { key: q.get("a") || "snap:kernel:20260905T072714Z", ts: "20260905T072714Z", taken_at: "2026-09-05T07:27:14Z", head: null },
      b: { key: q.get("b") || "snap:kernel:20260905T141346Z", ts: "20260905T141346Z", taken_at: "2026-09-05T14:13:46Z", head: "6bc0e83a71fc8e6a4ed2c573e5b7f6cab8e82af6" },
      nodes: { added: ["wasmtime"], removed: [] },
      parts: { added: ["edge.session"], removed: [],
               status_changed: [{ id: "edge.principal", from: "wip", to: "done" }],
               evidence_changed: [{ id: "edge.invoke", from: "unverified", to: "proven" }] },
      edges: { added: [{ from: "edge.principal", to: "gate.intent" }], removed: [] },
      journey: { steps_changed: [{ step_id: "interpret", from: false, to: true }] },
      findings: { count: { from: 151, to: 154 }, recurring: { from: 6, to: 7 } },
      playbook: { from: "1.1", to: "1.1" },
      summary: { changed: 6 },
    } };
  }
  if (p === "/playbook") {
    let md = "";
    try { md = readFileSync(join(REPO, "ATLAS-PLAYBOOK.md"), "utf8"); }
    catch { md = "# ATLAS PLAYBOOK\n(fixture: the playbook file was not readable)\n"; }
    return { ok: true, data: text ? md : md };
  }
  if (p === "/playbook/version") return { ok: true, data: { playbook_current: "1.1" } };
  if (p === "/kit") {
    let files = [];
    try { files = readdirSync(join(REPO, "kit")).sort(); } catch {}
    return { ok: true, data: { files } };
  }
  return nf;
}

// ---------------------------------------------------------------------------
// derivations — each mirrors the hub's own rule (hub/validate.mjs rollup(), worker.js
// connectedOf()).  Nothing here invents a fact the snapshot does not carry.
// ---------------------------------------------------------------------------
const CONNECTED_MAX_AGE_S = 26 * 3600;   // hub/worker.js
const EVIDENCE = ["proven", "unverified", "stale", "failing"];

function connectedOf(snap, now) {
  const head = (typeof snap.head === "string" && snap.head.length > 0) ? snap.head : null;
  const t = Date.parse(snap.taken_at);
  const age_s = Number.isFinite(t) ? Math.floor((now - t) / 1000) : -1;   // -1 = unknown
  const connected = (head !== null && Number.isFinite(t) && age_s <= CONNECTED_MAX_AGE_S)
    ? "connected" : "stale";
  return { connected, head, age_s };
}

function partIndex(snap) {
  const byRef = new Map();      // "<node>.<part>" -> { node, part }
  for (const n of snap.nodes || []) for (const p of n.parts || []) byRef.set(`${n.id}.${p.id}`, { node: n, part: p });
  return byRef;
}

function rollupOf(snap) {
  const counts = { todo: 0, wip: 0, done: 0 };
  const evidence = { proven: 0, unverified: 0, stale: 0, failing: 0 };
  const status = new Map();
  for (const n of snap.nodes || []) for (const p of n.parts || []) {
    if (counts[p.status] !== undefined) counts[p.status]++;
    status.set(`${n.id}.${p.id}`, p.status);
    evidence[EVIDENCE.includes(p.evidence) ? p.evidence : "unverified"]++;   // absence is never proof
  }
  const journey = deriveJourney(snap, status);
  const extra = {};
  if (snap.schema_version === "atlas-hub/1") { extra.evidence = evidence; extra.edges = Array.isArray(snap.edges) ? snap.edges.length : 0; }
  return { counts, total: counts.todo + counts.wip + counts.done, journey,
           findings: snap.findings || null, ...extra };
}

// The hub's rule, exactly: a step is done when it has KNOWN refs and every one of them is
// done.  An unresolvable ref is never evidence — it is counted as unresolved.
function deriveJourney(snap, statusMap) {
  if (!snap.journey || !Array.isArray(snap.journey.steps)) return null;
  const status = statusMap || (() => {
    const m = new Map();
    for (const n of snap.nodes || []) for (const p of n.parts || []) m.set(`${n.id}.${p.id}`, p.status);
    return m;
  })();
  const steps = snap.journey.steps.map((s) => {
    const refs = Array.isArray(s.refs) ? s.refs : [];
    const known = refs.filter((r) => status.has(r));
    const done = known.length > 0 && known.every((r) => status.get(r) === "done");
    return { step_id: s.step_id, label: s.label || s.step_id, order: s.order ?? 0,
             refs, done, unresolved: refs.length - known.length, blocked: known.length > 0 && !done };
  });
  return { name: snap.journey.name, objective: snap.journey.objective || "", steps,
           done: steps.filter((s) => s.done).length, total: steps.length,
           blockers: steps.filter((s) => s.blocked).map((s) => s.step_id) };
}

const age = (s) => {
  if (typeof s !== "number" || s < 0) return "unknown";
  if (s < 90) return `${s}s`;
  if (s < 5400) return `${Math.round(s / 60)}m`;
  if (s < 172800) return `${Math.round(s / 3600)}h`;
  return `${Math.round(s / 86400)}d`;
};
const shortHead = (h) => (typeof h === "string" && h.length >= 7 ? h.slice(0, 12) : "unknown");
const nodeMap = (snap) => new Map((snap.nodes || []).map((n) => [n.id, n]));
const childrenOf = (snap) => {
  const kids = new Map();
  for (const n of snap.nodes || []) if (n.parent) { if (!kids.has(n.parent)) kids.set(n.parent, []); kids.get(n.parent).push(n); }
  return kids;
};
function partSummary(n) {
  const c = { todo: 0, wip: 0, done: 0 };
  const e = { proven: 0, unverified: 0, stale: 0, failing: 0 };
  for (const p of n.parts || []) {
    if (c[p.status] !== undefined) c[p.status]++;
    e[EVIDENCE.includes(p.evidence) ? p.evidence : "unverified"]++;
  }
  return { parts: (n.parts || []).length, status: c, evidence: e };
}
// An edge touches a node when either end is the node, one of its parts, or a descendant.
function edgesTouching(snap, ids) {
  const set = new Set(ids);
  const hit = (ref) => {
    if (typeof ref !== "string") return false;
    if (set.has(ref)) return true;
    const dot = ref.lastIndexOf(".");
    return dot > 0 && set.has(ref.slice(0, dot));
  };
  return (snap.edges || []).filter((e) => hit(e.from) || hit(e.to));
}

// ---------------------------------------------------------------------------
// tokenised matching for relevant_context / search — plain string work, no model
// ---------------------------------------------------------------------------
const STOP = new Set(["the", "and", "for", "with", "that", "this", "into", "from", "are", "was",
  "you", "your", "our", "its", "how", "what", "why", "when", "who", "can", "should", "would",
  "have", "has", "had", "not", "but", "all", "any", "get", "got", "add", "use", "using", "make",
  "need", "want", "work", "working", "some", "just", "now", "new", "over", "about", "here"]);
const tokens = (s) => [...new Set(String(s || "").toLowerCase().split(/[^a-z0-9]+/)
  .filter((t) => t.length >= 3 && !STOP.has(t)))].slice(0, 24);

// ---------------------------------------------------------------------------
// snapshot fetch + argument checks
// ---------------------------------------------------------------------------
const PROJECT_RE = /^[a-z][a-z0-9-]{0,31}$/;
function needProject(args) {
  const p = args && args.project;
  if (typeof p !== "string" || !p) return { error: "project: required (a string)", status: 400 };
  if (!PROJECT_RE.test(p)) return { error: "project: must match [a-z][a-z0-9-]{0,31}", status: 400 };
  return null;
}
async function snapshot(project) {
  const r = await hubGet(`/v1/snapshot/${encodeURIComponent(project)}`);
  if (!r.ok) return { error: r.error, status: r.status };
  const s = r.data;
  if (!s || !Array.isArray(s.nodes)) return { error: "hub returned a snapshot with no nodes[]", status: 502 };
  return { snap: s };
}

// ---------------------------------------------------------------------------
// TOOLS — every one read-only, every one bounded
// ---------------------------------------------------------------------------
const FINDINGS_NOTE =
  "Finding TEXT never leaves the estate: the hub carries counts only, so this server has no bodies to show. Read the finding bodies in the estate's own findings store.";

const TOOLS = [
{
  name: "atlas_projects",
  description: "The rollup: one line per project — connected state, age, playbook, part counts, journey done/total, blockers, findings count. Start here.",
  inputSchema: { type: "object", properties: {}, additionalProperties: false },
  async run() {
    const r = await hubGet("/v1/projects");
    if (!r.ok) return { error: r.error, status: r.status };
    const d = r.data || {};
    const rows = (d.projects || []).slice(0, CAP.projects).map((p) => {
      if (p.error) return { project: p.project, error: p.error };
      const j = p.journey;
      return {
        project: p.project,
        connected: p.connected || "unknown",
        age: age(p.age_s),
        head: shortHead(p.head),
        playbook: p.playbook === null || p.playbook === undefined ? "undeclared" : p.playbook,
        board: p.board === true,
        counts: p.counts || "unknown",
        total: typeof p.total === "number" ? p.total : "unknown",
        evidence: p.evidence || "unknown",
        journey: j ? { name: j.name, done: j.done, total: j.total, blockers: (j.blockers || []).length } : "unknown",
        findings: p.findings ? { count: p.findings.count, recurring: p.findings.recurring } : "unknown",
      };
    });
    return { projects: rows, count: rows.length, truncated: (d.projects || []).length > rows.length,
             wire: d.wire || "unknown", playbook_current: d.playbook_current || "unknown",
             findings_note: FINDINGS_NOTE };
  },
},
{
  name: "atlas_project",
  description: "One project's top-level summary plus its level-0 and level-1 nodes (kind, title, part counts, evidence counts). No parts — use atlas_subtree for those.",
  inputSchema: { type: "object", properties: { project: { type: "string", description: "project name as it appears in atlas_projects" } }, required: ["project"], additionalProperties: false },
  async run(args) {
    const bad = needProject(args); if (bad) return bad;
    const got = await snapshot(args.project); if (got.error) return got;
    const snap = got.snap;
    const ids = nodeMap(snap); const kids = childrenOf(snap);
    const roots = (snap.nodes || []).filter((n) => !n.parent || !ids.has(n.parent));
    const level = [];
    for (const r of roots) {
      level.push({ level: 0, id: r.id, kind: r.kind || "unknown", title: r.title || r.id,
                   children: (kids.get(r.id) || []).length, ...partSummary(r), source: r.source ? (r.source.state || "unknown") : "none" });
      for (const c of kids.get(r.id) || [])
        level.push({ level: 1, id: c.id, parent: r.id, kind: c.kind || "unknown", title: c.title || c.id,
                     children: (kids.get(c.id) || []).length, ...partSummary(c), source: c.source ? (c.source.state || "unknown") : "none" });
    }
    const roll = rollupOf(snap);
    const conn = connectedOf(snap, Date.now());
    return {
      project: snap.project || args.project,
      wire: snap.schema_version || "unknown",
      taken_at: snap.taken_at || "unknown", age: age(conn.age_s), connected: conn.connected,
      head: shortHead(conn.head), stamp: snap.stamp || "unknown",
      playbook: typeof snap.playbook === "string" ? snap.playbook : "undeclared",
      sources: snap.sources || "unknown",
      counts: roll.counts, total: roll.total, evidence: roll.evidence || "unknown",
      edges: Array.isArray(snap.edges) ? snap.edges.length : 0,
      nodes_total: (snap.nodes || []).length,
      journey: roll.journey ? { name: roll.journey.name, objective: roll.journey.objective,
                                done: roll.journey.done, total: roll.journey.total,
                                blockers: roll.journey.blockers } : "unknown",
      findings: snap.findings ? { count: snap.findings.count, recurring: snap.findings.recurring } : "unknown",
      findings_note: FINDINGS_NOTE,
      nodes: level.slice(0, CAP.level1),
      truncated: level.length > CAP.level1,
      next: "atlas_subtree(project, node_id, depth) for parts and children",
    };
  },
},
{
  name: "atlas_subtree",
  description: "One node with its parts (status + evidence + bound check), its children down to `depth`, and the edges touching that subtree.",
  inputSchema: { type: "object", properties: {
      project: { type: "string" }, node_id: { type: "string", description: "node id from atlas_project or atlas_search" },
      depth: { type: "integer", minimum: 0, maximum: 5, description: "levels of children to include (default 1)" } },
    required: ["project", "node_id"], additionalProperties: false },
  async run(args) {
    const bad = needProject(args); if (bad) return bad;
    if (typeof args.node_id !== "string" || !args.node_id) return { error: "node_id: required (a string)", status: 400 };
    const got = await snapshot(args.project); if (got.error) return got;
    const snap = got.snap;
    const ids = nodeMap(snap);
    const root = ids.get(args.node_id);
    if (!root) return { error: `node_id: no node "${args.node_id}" in this project`, status: 404 };
    const depth = Math.max(0, Math.min(5, Number.isInteger(args.depth) ? args.depth : 1));
    const kids = childrenOf(snap);
    const shape = (n, lvl) => ({
      level: lvl, id: n.id, kind: n.kind || "unknown", title: n.title || n.id,
      ...(n.parent ? { parent: n.parent } : {}),
      ...(n.milestone ? { milestone: n.milestone } : {}),
      parts: (n.parts || []).slice(0, CAP.parts).map((p) => ({
        ref: `${n.id}.${p.id}`, label: p.label || p.id, status: p.status || "unknown",
        evidence: EVIDENCE.includes(p.evidence) ? p.evidence : "unverified",
        check: p.check || "none" })),
      parts_truncated: (n.parts || []).length > CAP.parts,
      source: n.source || "none",
      children: (kids.get(n.id) || []).length,
    });
    const out = [shape(root, 0)];
    let frontier = [root];
    for (let d = 1; d <= depth && out.length < CAP.subtree; d++) {
      const next = [];
      for (const parent of frontier) for (const c of kids.get(parent.id) || []) {
        if (out.length >= CAP.subtree) break;
        out.push(shape(c, d)); next.push(c);
      }
      frontier = next;
    }
    const inSubtree = out.map((n) => n.id);
    const edges = edgesTouching(snap, inSubtree).slice(0, CAP.edges)
      .map((e) => ({ from: e.from, to: e.to, kind: e.kind || "unknown", relation: e.relation || "" }));
    return { project: snap.project || args.project, node: args.node_id, depth,
             nodes: out, truncated: out.length >= CAP.subtree, edges,
             edges_truncated: edgesTouching(snap, inSubtree).length > edges.length };
  },
},
{
  name: "atlas_objective",
  description: "The project's journey: name, objective, and every step with done/blocked/unresolved and the part refs it depends on.",
  inputSchema: { type: "object", properties: { project: { type: "string" } }, required: ["project"], additionalProperties: false },
  async run(args) {
    const bad = needProject(args); if (bad) return bad;
    const got = await snapshot(args.project); if (got.error) return got;
    const snap = got.snap;
    const j = deriveJourney(snap);
    if (!j) return { project: snap.project || args.project, journey: "unknown",
                     reason: "this snapshot carries no journey" };
    return {
      project: snap.project || args.project, name: j.name || "unknown", objective: j.objective || "unknown",
      done: j.done, total: j.total, blockers: j.blockers,
      steps: j.steps.slice(0, CAP.steps).sort((a, b) => a.order - b.order).map((s) => ({
        step_id: s.step_id, order: s.order, label: s.label,
        state: s.done ? "done" : (s.blocked ? "blocked" : "not-started"),
        refs: s.refs, unresolved_refs: s.unresolved })),
      truncated: j.steps.length > CAP.steps,
      derivation: "a step is done when it has known refs and every one is done; an unresolvable ref is never counted as done (hub rule)",
    };
  },
},
{
  name: "atlas_blockers",
  description: "The blocked journey steps, the unfinished parts under each with status/evidence, and blocker centrality: how many steps each unfinished part blocks, most first.",
  inputSchema: { type: "object", properties: { project: { type: "string" } }, required: ["project"], additionalProperties: false },
  async run(args) {
    const bad = needProject(args); if (bad) return bad;
    const got = await snapshot(args.project); if (got.error) return got;
    const snap = got.snap;
    const j = deriveJourney(snap);
    if (!j) return { project: snap.project || args.project, blocked: [], centrality: [],
                     reason: "this snapshot carries no journey" };
    const idx = partIndex(snap);
    const detail = (ref) => {
      const hit = idx.get(ref);
      if (!hit) return { ref, status: "unknown", note: "this ref resolves to no part in the snapshot" };
      return { ref, label: hit.part.label || hit.part.id, node: hit.node.id,
               status: hit.part.status || "unknown",
               evidence: EVIDENCE.includes(hit.part.evidence) ? hit.part.evidence : "unverified",
               check: hit.part.check || "none" };
    };
    const blocked = j.steps.filter((s) => s.blocked).sort((a, b) => a.order - b.order).slice(0, CAP.steps)
      .map((s) => {
        const unfinished = s.refs.filter((r) => idx.has(r) && idx.get(r).part.status !== "done");
        const unknown = s.refs.filter((r) => !idx.has(r));
        return { step_id: s.step_id, order: s.order, label: s.label,
                 unresolved_parts: unfinished.map(detail), unknown_refs: unknown };
      });
    // centrality: an unfinished part's weight is the number of NOT-DONE steps it appears in.
    const counter = new Map();
    for (const s of j.steps) { if (s.done) continue;
      for (const r of s.refs) { if (idx.has(r) && idx.get(r).part.status === "done") continue;
        counter.set(r, (counter.get(r) || 0) + 1); } }
    const centrality = [...counter.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .slice(0, CAP.centrality).map(([ref, blocks]) => ({ ...detail(ref), blocks }));
    return { project: snap.project || args.project, journey: j.name || "unknown",
             done: j.done, total: j.total, blocked_count: j.blockers.length,
             blocked, centrality,
             note: "atlas reports what blocks what. It does not decide what to work on." };
  },
},
{
  name: "atlas_findings",
  description: "Finding counts for a project (total and recurring). Counts only — finding text never leaves the estate.",
  inputSchema: { type: "object", properties: { project: { type: "string" } }, required: ["project"], additionalProperties: false },
  async run(args) {
    const bad = needProject(args); if (bad) return bad;
    const got = await snapshot(args.project); if (got.error) return got;
    const f = got.snap.findings;
    return { project: got.snap.project || args.project,
             count: f && typeof f.count === "number" ? f.count : "unknown",
             recurring: f && typeof f.recurring === "number" ? f.recurring : "unknown",
             note: FINDINGS_NOTE };
  },
},
{
  name: "atlas_history",
  description: "Recent stored snapshots for a project (newest first): timestamp, stamp, head, wire, playbook.",
  inputSchema: { type: "object", properties: { project: { type: "string" },
      limit: { type: "integer", minimum: 1, maximum: 50, description: "default 10" } },
    required: ["project"], additionalProperties: false },
  async run(args) {
    const bad = needProject(args); if (bad) return bad;
    const limit = Math.max(1, Math.min(CAP.historyMax, Number.isInteger(args.limit) ? args.limit : CAP.historyDefault));
    const r = await hubGet(`/v1/history/${encodeURIComponent(args.project)}?limit=${limit}`);
    if (!r.ok) {
      if (r.status === 404) return { available: false, reason: "hub has no history route yet", project: args.project };
      return { error: r.error, status: r.status };
    }
    const d = r.data || {};
    const snaps = (d.snapshots || []).slice(0, limit).map((s) => ({
      key: s.key, ts: s.ts, taken_at: s.taken_at, stamp: s.stamp,
      head: shortHead(s.head), wire: s.schema_version || "unknown",
      playbook: s.playbook === null || s.playbook === undefined ? "undeclared" : s.playbook }));
    return { available: true, project: d.project || args.project, count: snaps.length,
             snapshots: snaps, truncated: d.truncated === true || (d.snapshots || []).length > snaps.length };
  },
},
{
  name: "atlas_diff",
  description: "What changed between two stored snapshots: nodes and parts added/removed, statuses and evidence moved, edges, journey steps, finding counts. Omit a and b for the two most recent.",
  inputSchema: { type: "object", properties: { project: { type: "string" },
      a: { type: "string", description: "older snapshot key from atlas_history" },
      b: { type: "string", description: "newer snapshot key from atlas_history" } },
    required: ["project"], additionalProperties: false },
  async run(args) {
    const bad = needProject(args); if (bad) return bad;
    const q = [];
    if (typeof args.a === "string" && args.a) q.push("a=" + encodeURIComponent(args.a));
    if (typeof args.b === "string" && args.b) q.push("b=" + encodeURIComponent(args.b));
    const r = await hubGet(`/v1/diff/${encodeURIComponent(args.project)}${q.length ? "?" + q.join("&") : ""}`);
    if (!r.ok) {
      if (r.status === 404) return { available: false, reason: "hub has no diff route yet", project: args.project };
      return { error: r.error, status: r.status };
    }
    return { available: true, ...compactDiff(r.data, args.project) };
  },
},
{
  name: "atlas_relevant_context",
  description: "The projection: give it the task you are about to do and it returns a bounded (~4 KB) slice of the project — the nodes that match, their parts, the edges among them, the journey steps that depend on them, the blockers among them, and recent changes touching them. Says what it matched on.",
  inputSchema: { type: "object", properties: { project: { type: "string" },
      task: { type: "string", description: "what you are about to work on, in your own words" } },
    required: ["project", "task"], additionalProperties: false },
  async run(args) {
    const bad = needProject(args); if (bad) return bad;
    if (typeof args.task !== "string" || !args.task.trim()) return { error: "task: required (a string describing the work)", status: 400 };
    const got = await snapshot(args.project); if (got.error) return got;
    // recent changes are a real fact when the hub has the route, and honestly absent when
    // it does not — never a guess.
    const d = await hubGet(`/v1/diff/${encodeURIComponent(args.project)}`);
    const diff = d.ok ? d.data : { unavailable: d.status === 404 ? "hub has no diff route yet" : d.error };
    return relevantContext(got.snap, args.project, args.task, diff);
  },
},
{
  name: "atlas_search",
  description: "Search every connected project for nodes and parts whose id, title or label matches the query. Returns project, node, part, status and evidence.",
  inputSchema: { type: "object", properties: { query: { type: "string" } }, required: ["query"], additionalProperties: false },
  async run(args) {
    if (typeof args.query !== "string" || !args.query.trim()) return { error: "query: required (a string)", status: 400 };
    const toks = tokens(args.query);
    if (!toks.length) return { query: args.query, matched_on: [], results: [], count: 0,
                               note: "no searchable words in the query (words under 3 letters are skipped)" };
    const r = await hubGet("/v1/projects");
    if (!r.ok) return { error: r.error, status: r.status };
    const names = (r.data.projects || []).map((p) => p.project).filter(Boolean).slice(0, CAP.searchProjects);
    const results = []; const failed = []; const matched = new Set();
    for (const project of names) {
      if (results.length >= CAP.searchHits) break;
      const got = await snapshot(project);
      if (got.error) { failed.push({ project, error: got.error }); continue; }
      for (const n of got.snap.nodes || []) {
        const nHay = `${n.id} ${n.title || ""}`.toLowerCase();
        const nHits = toks.filter((t) => nHay.includes(t));
        if (nHits.length && results.length < CAP.searchHits) {
          nHits.forEach((t) => matched.add(t));
          results.push({ project, node: n.id, kind: n.kind || "unknown", title: n.title || n.id,
                         parts: (n.parts || []).length, on: nHits });
        }
        for (const p of n.parts || []) {
          if (results.length >= CAP.searchHits) break;
          const pHay = `${p.id} ${p.label || ""}`.toLowerCase();
          const pHits = toks.filter((t) => pHay.includes(t));
          if (!pHits.length) continue;
          pHits.forEach((t) => matched.add(t));
          results.push({ project, node: n.id, part: `${n.id}.${p.id}`, label: p.label || p.id,
                         status: p.status || "unknown",
                         evidence: EVIDENCE.includes(p.evidence) ? p.evidence : "unverified", on: pHits });
        }
      }
    }
    return { query: args.query, matched_on: [...matched], searched_projects: names,
             count: results.length, results, truncated: results.length >= CAP.searchHits,
             ...(failed.length ? { unreadable: failed } : {}) };
  },
},
{
  name: "atlas_playbook",
  description: "The current atlas playbook (markdown) as the hub serves it, plus the version every estate should declare.",
  inputSchema: { type: "object", properties: {}, additionalProperties: false },
  async run() {
    const md = await hubGet("/playbook", { text: true });
    if (!md.ok) return { error: md.error, status: md.status };
    const ver = await hubGet("/v1/projects");
    return { playbook_current: ver.ok ? (ver.data.playbook_current || "unknown") : "unknown",
             bytes: md.data.length, playbook: md.data };
  },
},
];

function compactDiff(d, project) {
  d = d || {};
  let capped = false;
  const cap = (a, n = 20) => {
    if (!Array.isArray(a)) return [];
    if (a.length > n) capped = true;
    return a.slice(0, n);
  };
  // the hub may name a side by key or by the whole snapshot row — one readable line either way
  const side = (x) => {
    if (typeof x === "string") return x;
    if (x && typeof x === "object") return `${x.key || x.ts || "unknown"}${x.taken_at ? ` @ ${x.taken_at}` : ""}`;
    return "unknown";
  };
  const n = d.nodes || {}, p = d.parts || {}, e = d.edges || {};
  const out = {
    project: d.project || project, a: side(d.a), b: side(d.b),
    summary: d.summary && typeof d.summary.changed === "number" ? d.summary.changed : "unknown",
    nodes: { added: cap(n.added), removed: cap(n.removed) },
    parts: { added: cap(p.added), removed: cap(p.removed),
             status_changed: cap(p.status_changed), evidence_changed: cap(p.evidence_changed) },
    edges: { added: cap(e.added, 12).map((x) => (x && x.from ? `${x.from} → ${x.to}` : x)),
             removed: cap(e.removed, 12).map((x) => (x && x.from ? `${x.from} → ${x.to}` : x)) },
    journey: { steps_changed: cap((d.journey || {}).steps_changed) },
    findings: d.findings || "unknown",
    playbook: d.playbook || "unknown",
  };
  out.truncated = capped;   // a capped list is said out loud, never silently short
  return out;
}

// ---------------------------------------------------------------------------
// the projection — bounded, explains its own matching, never invents relevance
// ---------------------------------------------------------------------------
// The diff lines that touch the selected nodes/parts — pass-through of the hub's diff,
// filtered, never re-derived here.
function recentLines(diff, ids, refs) {
  if (!diff || diff.unavailable) return [];
  const ownerOf = (r) => { const d = String(r).lastIndexOf("."); return d > 0 ? String(r).slice(0, d) : String(r); };
  const near = (r) => typeof r === "string" && (refs.has(r) || ids.has(r) || ids.has(ownerOf(r)));
  const out = [];
  const p = diff.parts || {}, n = diff.nodes || {};
  for (const x of p.status_changed || []) if (near(x && x.id)) out.push(`status ${x.id}: ${x.from} → ${x.to}`);
  for (const x of p.evidence_changed || []) if (near(x && x.id)) out.push(`evidence ${x.id}: ${x.from} → ${x.to}`);
  for (const x of p.added || []) if (near(x)) out.push(`part added ${x}`);
  for (const x of p.removed || []) if (near(x)) out.push(`part removed ${x}`);
  for (const x of n.added || []) if (near(x)) out.push(`node added ${x}`);
  for (const x of n.removed || []) if (near(x)) out.push(`node removed ${x}`);
  return out;
}

function relevantContext(snap, project, task, diff) {
  const toks = tokens(task);
  const idx = partIndex(snap);
  const j = deriveJourney(snap);
  const scored = [];
  const matched = new Set();
  for (const n of snap.nodes || []) {
    let score = 0; const why = new Set(); const partHits = [];
    for (const t of toks) {
      if (String(n.id).toLowerCase().includes(t)) { score += 3; why.add(`id:${t}`); matched.add(t); }
      if (String(n.title || "").toLowerCase().includes(t)) { score += 2; why.add(`title:${t}`); matched.add(t); }
    }
    for (const p of n.parts || []) {
      let ps = 0;
      for (const t of toks) if (`${p.id} ${p.label || ""}`.toLowerCase().includes(t)) { ps += 1; why.add(`part:${t}`); matched.add(t); }
      if (ps) { score += ps; partHits.push(p); }
    }
    if (score > 0) scored.push({ node: n, score, why: [...why], partHits });
  }
  // edges pull their endpoints in: a relation that matches the task makes both ends relevant
  const edgeHits = [];
  for (const e of snap.edges || []) {
    const hay = `${e.relation || ""} ${e.kind || ""}`.toLowerCase();
    const on = toks.filter((t) => hay.includes(t));
    if (on.length) { on.forEach((t) => matched.add(t)); edgeHits.push(e); }
  }
  const owner = (ref) => { const dot = String(ref).lastIndexOf("."); return dot > 0 ? String(ref).slice(0, dot) : String(ref); };
  const have = new Set(scored.map((s) => s.node.id));
  for (const e of edgeHits) for (const ref of [e.from, e.to]) {
    const id = have.has(ref) ? null : owner(ref);
    const n = (snap.nodes || []).find((x) => x.id === id || x.id === ref);
    if (n && !have.has(n.id)) { have.add(n.id); scored.push({ node: n, score: 1, why: ["edge-relation"], partHits: [] }); }
  }
  scored.sort((a, b) => b.score - a.score || String(a.node.id).localeCompare(String(b.node.id)));

  const build = (nodeLimit, partLimit) => {
    const picked = scored.slice(0, nodeLimit);
    const ids = new Set(picked.map((s) => s.node.id));
    const refs = new Set();
    const nodes = picked.map((s) => {
      const parts = (s.partHits.length ? s.partHits : (s.node.parts || [])).slice(0, partLimit);
      parts.forEach((p) => refs.add(`${s.node.id}.${p.id}`));
      return { id: s.node.id, kind: s.node.kind || "unknown", title: s.node.title || s.node.id,
               matched_on: s.why,
               parts: parts.map((p) => ({ ref: `${s.node.id}.${p.id}`, label: p.label || p.id,
                 status: p.status || "unknown",
                 evidence: EVIDENCE.includes(p.evidence) ? p.evidence : "unverified",
                 ...(p.check ? { check: p.check } : {}) })) };
    });
    const near = (r) => ids.has(r) || ids.has(owner(r));
    const edges = (snap.edges || []).filter((e) => near(e.from) && near(e.to)).slice(0, 12)
      .map((e) => `${e.from} -[${e.kind || "?"}]-> ${e.to}${e.relation ? ` (${e.relation})` : ""}`);
    const steps = j ? j.steps.filter((s) => s.refs.some((r) => refs.has(r) || ids.has(owner(r))))
      .sort((a, b) => a.order - b.order).slice(0, 8)
      .map((s) => ({ step_id: s.step_id, label: s.label, state: s.done ? "done" : (s.blocked ? "blocked" : "not-started"),
                     refs: s.refs.filter((r) => refs.has(r)) })) : [];
    const blockers = [];
    for (const n of nodes) for (const p of n.parts)
      if (p.status !== "done" && steps.some((s) => s.state === "blocked" && s.refs.includes(p.ref)))
        blockers.push({ ref: p.ref, status: p.status, evidence: p.evidence });
    return { nodes, edges, steps, blockers: blockers.slice(0, 8), ids,
             recent: recentLines(diff, ids, refs).slice(0, 6) };
  };

  // shrink until the whole answer fits the budget — the cap is enforced, not hoped for
  let nodeLimit = 12, partLimit = 6, body = build(nodeLimit, partLimit), out, size;
  const conn = connectedOf(snap, Date.now());
  const assemble = (b, trunc) => ({
    project: snap.project || project, task,
    matched_on: toks.length ? [...matched] : [],
    matching: "tokenised substring match against node ids, node titles, part labels and edge relations. No model, no ranking of what you should do.",
    snapshot: { taken_at: snap.taken_at || "unknown", age: age(conn.age_s), connected: conn.connected, head: shortHead(conn.head) },
    objective: j ? { name: j.name, objective: (j.objective || "").slice(0, 220), done: j.done, total: j.total } : "unknown",
    nodes: b.nodes, edges: b.edges, journey_steps: b.steps, blockers: b.blockers,
    recent_changes: (diff && diff.unavailable) ? `unknown — ${diff.unavailable}`
      : (b.recent && b.recent.length ? b.recent : "none touching these nodes in the latest diff"),
    findings_note: FINDINGS_NOTE,
    truncated: trunc,
    bounded: `<= ${CAP.contextBytes} bytes`,
  });
  out = assemble(body, false); size = JSON.stringify(out).length;
  let truncated = false;
  while (size > CAP.contextBytes && (nodeLimit > 1 || partLimit > 1)) {
    truncated = true;
    if (partLimit > 2) partLimit--; else if (nodeLimit > 1) nodeLimit--; else partLimit = 1;
    body = build(nodeLimit, partLimit);
    out = assemble(body, truncated); size = JSON.stringify(out).length;
  }
  if (size > CAP.contextBytes) {   // last resort: keep the frame, drop the payload
    out = assemble({ nodes: body.nodes.slice(0, 1).map((n) => ({ ...n, parts: n.parts.slice(0, 1) })),
                     edges: [], steps: [], blockers: [] }, true);
  }
  if (!scored.length) out.note = "nothing in this project's ids, titles, labels or relations matched those words — the projection is empty rather than guessed";
  return out;
}

// ---------------------------------------------------------------------------
// JSON-RPC 2.0 over newline-delimited stdio
// ---------------------------------------------------------------------------
const byName = new Map(TOOLS.map((t) => [t.name, t]));
const send = (msg) => { try { process.stdout.write(JSON.stringify(msg) + "\n"); } catch {} };
const rpcError = (id, code, message) => send({ jsonrpc: "2.0", id, error: { code, message: redact(message) } });

async function handle(msg) {
  const { id, method, params } = msg || {};
  const isNotification = id === undefined || id === null;

  if (method === "initialize") {
    const asked = params && typeof params.protocolVersion === "string" ? params.protocolVersion : DEFAULT_PROTOCOL;
    return send({ jsonrpc: "2.0", id, result: {
      protocolVersion: asked,                       // echo what the client asked for
      capabilities: { tools: {} },
      serverInfo: { name: SERVER_NAME, version: SERVER_VERSION },
      instructions: "Read-only map of every connected project. Start with atlas_projects, then atlas_relevant_context(project, task) for a bounded slice before you read any files. Finding text never leaves its estate; this server carries counts only.",
    } });
  }
  if (method === "notifications/initialized" || (typeof method === "string" && method.startsWith("notifications/"))) return;
  if (method === "ping") return isNotification ? undefined : send({ jsonrpc: "2.0", id, result: {} });
  if (method === "tools/list") {
    return send({ jsonrpc: "2.0", id, result: {
      tools: TOOLS.map((t) => ({ name: t.name, description: t.description, inputSchema: t.inputSchema })) } });
  }
  if (method === "tools/call") {
    const name = params && params.name;
    const tool = byName.get(name);
    if (!tool) return rpcError(id, -32602, `unknown tool: ${String(name)}`);
    const args = (params && params.arguments) || {};
    let result;
    try { result = await tool.run(args); }
    catch (e) { result = { error: `tool ${name} failed: ${String(e && e.message || e)}`, status: 500 }; }
    return send({ jsonrpc: "2.0", id, result: {
      content: [{ type: "text", text: redact(JSON.stringify(result)) }],
      isError: !!(result && result.error) } });
  }
  if (isNotification) return;
  return rpcError(id, -32601, `unknown method: ${String(method)}`);
}

function serve() {
  let buf = "";
  // A client that closes stdin (a one-shot `echo ... | node server.mjs`, or a shutting-down
  // host) must still receive answers already in flight: exit when stdin ends AND no handler
  // is still awaiting the hub, never in the middle of a fetch.
  let pending = 0, ended = false;
  const maybeExit = () => { if (ended && pending === 0) process.exit(0); };
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (chunk) => {
    buf += chunk;
    let nl;
    while ((nl = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, nl).trim();
      buf = buf.slice(nl + 1);
      if (!line) continue;
      let msg;
      try { msg = JSON.parse(line); }
      catch { rpcError(null, -32700, "parse error: each line must be one JSON-RPC object"); continue; }
      pending++;
      Promise.resolve(handle(msg))
        .catch((e) => logErr(`handler error: ${String(e && e.message || e)}`))
        .finally(() => { pending--; maybeExit(); });
    }
  });
  process.stdin.on("end", () => { ended = true; maybeExit(); });
  process.on("uncaughtException", (e) => logErr(`uncaught: ${String(e && e.message || e)}`));
}

// ---------------------------------------------------------------------------
// --selftest — every tool against the fixture hub, no network
// ---------------------------------------------------------------------------
async function selftest() {
  let pass = 0, fail = 0;
  const check = (ok, what) => { if (ok) { pass++; } else { fail++; process.stdout.write(`FAIL ${what}\n`); } };
  const calls = [
    ["atlas_projects", {}], ["atlas_project", { project: "kernel" }],
    ["atlas_subtree", { project: "kernel", node_id: "edge", depth: 1 }],
    ["atlas_objective", { project: "kernel" }], ["atlas_blockers", { project: "kernel" }],
    ["atlas_findings", { project: "kernel" }], ["atlas_history", { project: "kernel" }],
    ["atlas_diff", { project: "kernel" }],
    ["atlas_relevant_context", { project: "kernel", task: "the edge session and principal invocation" }],
    ["atlas_search", { query: "token" }], ["atlas_playbook", {}],
  ];
  for (const [name, args] of calls) {
    const t = byName.get(name);
    const r = await t.run(args);
    const s = JSON.stringify(r);
    check(!!r && !r.error, `${name} returned without error (${r && r.error ? r.error : "ok"})`);
    check(!s.includes(FIXTURE_TOKEN), `${name} leaks no bearer`);
    if (name === "atlas_relevant_context") check(s.length <= CAP.contextBytes, `${name} within ${CAP.contextBytes} bytes (was ${s.length})`);
    process.stdout.write(`  ${name}: ${s.length} bytes\n`);
  }
  process.stdout.write(`selftest: ${pass} passed, ${fail} failed\n`);
  process.exit(fail ? 1 : 0);
}

if (process.argv.includes("--selftest")) selftest();
else serve();
