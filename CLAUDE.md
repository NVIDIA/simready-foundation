# Claude Code Notes

Repo-local skills live under the agent-agnostic skill tree:

```text
skills/<skill-name>/SKILL.md
```

Compatibility links:

```text
.claude/skills -> ../skills
.codex/skills -> ../skills
.agents/skills -> ../skills
```

When updating a SimReady skill, edit the `skills` source of truth, including
bundled `references/`, `assets/`, `evals/`, and `assets/openai.yaml`
metadata. Helper scripts used by skills live under `assets/scripts/` in this
repository.

Use the same repo-level agent guidance as Codex in `AGENTS.md`.
