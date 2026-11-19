# Claude Code Notes — Core Tier

Tier-local skills live under the tier's package skill tree:

```text
simready/foundation/tier_core/skills/<skill-name>/SKILL.md
```

Compatibility links (for standalone, tier-rooted agent discovery):

```text
.claude/skills  -> ../simready/foundation/tier_core/skills
.codex/skills   -> ../simready/foundation/tier_core/skills
.agents/skills  -> ../simready/foundation/tier_core/skills
```

These are the `simready-foundation-conform-fet-*` conform skills for the
Standard/PhysX/MuJoCo/Isaac features this tier owns. Foundation-authoring skills
(`add/update-*`, `validate-foundation-change`, `create-package`) live at the
repository root, not here. Newton conform skills live in the
`simready-foundation-tier-newton` package.

Edit skills in the `simready/foundation/tier_core/skills` source of truth,
including bundled `references/`, `assets/`, `evals/`, and `assets/openai.yaml`
metadata. Read `AGENTS.md` in this directory for durable tier context.
