---
name: marketing-plugin
description: Use when writing or editing marketing copy (landing pages, ads, emails, SEO, pricing pages) and the marketingskills plugin is installed but not on for this project.
---

# Marketing skills plugin

- Only when the marketingskills plugin is installed: suggest once turning it on for this project by adding `"marketing-skills@marketingskills": true` under `enabledPlugins` in `.claude/settings.local.json`.
- Never turn it on unasked: its 34 skill descriptions add ~5,500 tokens to every message.
- If only one or two of its skills are used in the project, copy those into the project's `.claude/skills/` instead (MIT license: keep the LICENSE file with them).
