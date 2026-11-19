# Claude Code Notes — Newton Tier

Tier-local skills live under the tier's package skill tree:

```text
simready/foundation/tier_newton/skills/<skill-name>/SKILL.md
```

Compatibility links (for standalone, tier-rooted agent discovery):

```text
.claude/skills  -> ../simready/foundation/tier_newton/skills
.codex/skills   -> ../simready/foundation/tier_newton/skills
.agents/skills  -> ../simready/foundation/tier_newton/skills
```

These conform skills repair assets to this tier's Newton features
(`simready-foundation-conform-fet-*-newton`). Edit skills in the
`simready/foundation/tier_newton/skills` source of truth, including bundled
`references/`, `assets/`, `evals/`, and `assets/openai.yaml` metadata.

Read `AGENTS.md` in this directory for durable tier context (what the tier owns,
its independence from the Core tier, and how to validate).
