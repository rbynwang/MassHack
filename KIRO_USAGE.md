# How we used Kiro

Running notes for the Hackachusetts submission write-up ("Provide a write up on
how Kiro was used"). Fill the sections at the end; append to the log as you go.

## Log

| Time (ET) | Who | Kiro feature | What and why |
| --- | --- | --- | --- |
| 10/24 ~10:00 | Robyn | Steering | Drafted `product.md`, `tech.md`, `structure.md` and a `fileMatch` steering doc (`housezero-data.md`) with Claude Code from our proposal and the dataset README, so Kiro knows the meter semantics and avoids data leakage in backtests. |
| 10/24 ~10:00 | Robyn | Hooks | Added `py-compile-on-save` (PostFileSave) and `usage-log-on-stop` (Stop) hooks. |

## Write-up sections (fill before 6 PM)

### Kiro tools used
IDE / CLI / Web / Crew: which ones, and how they differed.

### Spec-driven development
How we structured specs; how it compared to vibe coding.

### Agent hooks
Which workflows we automated, and what that changed.

### Steering docs
Strategy, and what made the biggest difference to Kiro's responses.

### MCP
Servers added, and what they let us do that was otherwise hard.

### Property-based testing
Which requirements had PBT; issues it caught that unit tests missed.

### Kiro powers
Which powers we used; any third-party tooling they brought in.

### Kiro + Claude workflow
How Claude Code (drafting specs/steering, data exploration, review) and Kiro
(executing specs, hooks, git) worked together.
