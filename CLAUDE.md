# MassHack — guidance for Claude Code

This project is built for Hackachusetts 2026, where the rules require the
project to be built **with Kiro**. Claude Code works alongside Kiro and follows
the same steering docs, which are the single source of truth:

@.kiro/steering/product.md
@.kiro/steering/tech.md
@.kiro/steering/structure.md
@.kiro/steering/housezero-data.md

## How Claude and Kiro split the work
- **Claude drafts, Kiro executes.** For any feature larger than a quick fix,
  write a spec in `.kiro/specs/<feature>/` as `requirements.md` (user stories +
  EARS acceptance criteria), `design.md` and `tasks.md` (small numbered
  checkbox tasks). Kiro then implements it task by task.
- **Kiro owns git.** Don't commit or push from Claude unless asked; commits and
  pushes go through Kiro so the work is visible in Kiro.
- Updating steering, hooks (`.kiro/hooks/*.json`, schema `"version": "v1"`) or
  MCP config (`.kiro/settings/mcp.json`) counts as Kiro usage too. Keep them current
  when conventions change.
- **Log it.** After anything notable (a new spec, hook, steering change, MCP
  server, property-based test), add a line to `KIRO_USAGE.md`. It becomes the
  submission write-up.
- Never add `.kiro/` to `.gitignore`. That disqualifies the submission.
