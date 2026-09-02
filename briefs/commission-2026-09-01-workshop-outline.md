# Workshop rebuild — owner's outline (2026-09-01, verbatim), banked by the Director as the commission seed

> "first thing is the plugin structure and architecture. then the tools categories and what
> each category is, then each tool with explanation, then a schematic simulation of a session
> and how its working and how we can add an ew sesion, or other tools, etc."

## Reading (Director)
Four movements, in this order:
1. **Structure & architecture** — the plugin tree (manifests, hooks, skills, scripts, ledgers,
   estate files), what runs when, where the law lives and where it is enforced.
2. **Tool categories** — the taxonomy of the 32 skills + hooks + instruments; what each
   category IS (its job in a session), before any single tool.
3. **Each tool, explained** — one entry per tool: what it does, when it fires/is invoked, its
   inputs/outputs, its script + fixture, its exit codes, one honest example.
4. **A session, schematically** — a simulated session end to end (SessionStart packet →
   prompt → router/nudges → work → lanes + receipts → gates → sessionend/auto-cushion →
   successor), then how to add a new session (role, estate, continuation) and how to add a
   new tool (skill dir, SKILL.md, script, fixture, golden surface, doctor/eval hooks).

Constraints: docs/workshop/** is on the golden release surface — a rebuild is a release-shaped
change (version-specific claims must reproduce live; eval RELEASE-SURFACE names the files).
Starts AFTER 4.6.2 is pushed. Plan lane (read-only) runs first; build lane(s) follow the
seat-builder ritual.
