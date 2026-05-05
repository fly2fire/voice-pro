# Skills for AI agents

This directory ships [agent skills](https://docs.claude.com/en/docs/claude-code/skills) — short markdown files that AI agents (Claude Code, Cursor, etc.) auto-activate when the user describes a relevant task. They turn the CLIs and workflows in this repo into something an AI agent can use without being told *how*.

## Available skills

| Skill | Triggers when the user says... | Wraps |
|---|---|---|
| [`yt-dub`](yt-dub/SKILL.md) | "翻译这个 YouTube 视频", "给这个视频配中文", "dub a YouTube video", "translate and voice-over a video" | `tools/yt-dub` CLI |

## How to install

Skills live in `~/.claude/skills/<name>/SKILL.md` (user-wide) or `<project>/.claude/skills/<name>/SKILL.md` (per-project). Pick whichever scope you want:

```bash
# Install yt-dub system-wide for all your Claude Code sessions
mkdir -p ~/.claude/skills
cp -r skills/yt-dub ~/.claude/skills/
```

Or symlink so the repo's copy stays the source of truth:

```bash
ln -s "$(pwd)/skills/yt-dub" ~/.claude/skills/yt-dub
```

After install, restart your Claude Code session. The skill registers automatically and Claude will reach for it whenever you describe a matching task.

## Editing / writing your own

Each skill is one folder with a single `SKILL.md`:

```
skills/<name>/SKILL.md
```

The file starts with YAML frontmatter — the `description` field is what the agent reads to decide whether to activate the skill, so include explicit trigger phrases (in the user's natural language, both English and the languages they speak).

```markdown
---
name: yt-dub
description: ... Use when the user wants to "翻译这个 YouTube 视频" ...
---

# yt-dub: ...

(detailed reference for the agent)
```

The body of the markdown is what the agent reads after activation — write it as a concise reference manual covering: prerequisites, common command patterns, performance notes, and troubleshooting.
