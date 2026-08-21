# Codex runtime contract

Not Rest is one harness with two runtime adapters. The estate and the skill methods are
shared; lifecycle wiring and orchestration tools are not.

## Runtime map

| Concern | Codex adapter | Claude adapter |
|---|---|---|
| Project foundation | `AGENTS.md` | `CLAUDE.md` |
| Session identity | `CODEX_THREAD_ID` when available | Claude session id when available |
| Delegation model | explicit `gpt-5.6-sol` | explicit `opus` |
| Fresh worker context | `spawn_agent` with `fork_turns: "none"` or a bounded recent-turn fork | non-fork Agent/Task lane |
| Cross-task wire | Codex task/thread tools when exposed and authorized | Claude session tools when exposed |
| Lifecycle hooks | unavailable; discipline is carried by `AGENTS.md`, the selected skill, and explicit instruments | `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `SubagentStop` hooks |
| Health proof | Codex manifest + installation + estate checks | Claude manifest + hooks + installation + estate checks |

Never translate a missing Codex hook into a claim that the law was automatically enforced.
On Codex, the law is **instruction-enforced and post-checked** unless a future Codex hook
surface is shipped and proved.

## Path resolution

Codex does not promise `CLAUDE_PLUGIN_ROOT`. When a skill cites `<plugin-root>`, resolve it
from the selected `SKILL.md`: the plugin root is two directories above `skills/<skill>/`.
Use the resulting absolute path in tool calls. Never execute a literal placeholder.

Claude may continue to use `CLAUDE_PLUGIN_ROOT`. `NOTREST_PLUGIN_ROOT`, when explicitly
provided by an operator, wins on either runtime.

## Delegation law

Delegation is used only when the user asks for it or the active host policy permits it.
Every lane carries the runtime's explicit frontier worker model:

- Codex: `model: "gpt-5.6-sol"`; a model override must use `fork_turns: "none"` or a
  bounded recent-turn fork, never a full-history inherited fork.
- Claude: `model: "opus"`; never `subagent_type: "fork"`.

No model name silently substitutes for the other. Receipts record the model that actually
ran, not the one the commission intended.

## Capability boundaries

- `notrest`, `doctor`, `eval`, `graph`, `recap`, `archivist`, `spend`, research/planning,
  drafting, and file-based continuity are native on both adapters.
- `agentswarm`, `director`, `mentor`, and `refuter` map to Codex collaboration agents only
  when delegation is authorized. The seat retains decomposition, judgment, application,
  and gates.
- `beam` remote-Agent isolation and Claude hook automation are Claude-only in v4.3.0.
  Codex may bank a checkpoint but must label remote respawn unavailable rather than fake it.
- `gpt` is a cross-vendor lane when invoked from Claude. In Codex it is redundant with the
  current seat unless the user explicitly asks for a separate Codex task or comparison.
- Live predecessor contact is opportunistic. If task/thread tools are absent or the user
  has not authorized creating a task, continue from `START-HERE.md`, `HANDOFF.md`, `STATE.md`,
  and the COORD trail without blocking.

## Native package boundary

The Codex manifest is `.codex-plugin/plugin.json`. It intentionally does **not** declare
Claude `hooks/`; Codex rejects that manifest field and does not execute those lifecycle
events. The repo-local Codex catalog is `.agents/plugins/marketplace.json`.

After installing or updating the local plugin, start a new Codex task so skill discovery
uses the new package.
