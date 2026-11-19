# Contributing

Contributions to SimReady Foundation start with a GitHub issue so a maintainer
can agree on the scope, coordinate a working branch, and identify the contributor
responsible for the work. Public working branches support drafting and validating
specifications; acceptance into main or a release follows maintainer review.
Contributor branches have no guaranteed hosted CI. Run the relevant local checks
and preserve the evidence for review.

## Signing off your work

We require that all contributors "sign-off" on their commits. This certifies
that the contribution is your original work, or you have rights to submit it
under the same license, or a compatible license. Any contribution which
contains commits that are not signed off will not be accepted.

To sign off on a commit, use the `--signoff` (or `-s`) option when committing
your changes:

```bash
git commit -s -m "Add cool feature."
```

This appends the following to your commit message:

```text
Signed-off-by: Your Name <your@email.com>
```

Full text of the [Developer Certificate of Origin (DCO)](https://developercertificate.org/):

```text
Developer Certificate of Origin
Version 1.1

Copyright (C) 2004, 2006 The Linux Foundation and its contributors.

Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.


Developer's Certificate of Origin 1.1

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```

## Branch access

[NVIDIA/simready-foundation](https://github.com/NVIDIA/simready-foundation) is
public, but public access does not grant permission to create or push branches
in that repository. GitHub requires **write access** to create an upstream branch;
read and triage access are insufficient. Repository rules can further restrict
branch creation and pushes. See GitHub's
[branch documentation](https://docs.github.com/en/pull-requests/how-tos/commit-changes/managing-branches-within-your-repository)
and [repository roles](https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories/managing-repository-roles/repository-roles-for-an-organization).

You can create a local branch without upstream write access. Publishing it to
the upstream repository requires permission. If you already have write access,
coordinate your branch and scope in the issue before starting work.

## Request a branch and work ownership

If you do not have write access, [open a GitHub issue](https://github.com/NVIDIA/simready-foundation/issues/new)
requesting a contribution branch and naming yourself as the proposed work owner.
Use this format:

```text
Title: Contribution branch request: <short description>

GitHub username: @<username>
Proposed change: <what you want to contribute and why>
Affected files or contracts: <paths, requirement IDs, feature/profile versions>
Proposed branch name: <username>/<short-description>
Validation plan: <how you will demonstrate that the change works>
Access needed: Please create the branch and arrange access for me to push to it.
Work owner: @<username>
```

The maintainer coordinating your request will review the scope, create the
agreed branch from the appropriate base, and record you as its work owner in
the issue. They will arrange any required repository access with an administrator
and confirm the branch name, target branch for review, and how you should push.
Accept any collaborator invitation before pushing.

GitHub does not have a separate branch-owner permission. Ownership here means
responsibility for the contribution, recorded in the issue; assigning an issue
or creating a branch does not grant write access. Write access is a repository
role, and any restriction to a particular branch must be configured separately
through repository rules. If upstream access cannot be granted, the maintainer
will coordinate a fork-based pull request with you instead.

Wait for the maintainer's confirmation before relying on upstream access.

## Set up and make the change

Follow the [README setup instructions](README.md#getting-the-repository),
including Git LFS and Python 3.12. Once the maintainer confirms your upstream
branch, check it out (replace the example with the agreed name):

```bash
git fetch origin
git switch --track origin/your-username/short-description
```

Ensure `origin` points to the repository containing your agreed working branch.
Keep the change focused on the issue's scope. Read [AGENTS.md](AGENTS.md) for
project conventions and the [guide index](nv_core/sr_specs/docs/guides/guides.md)
for the relevant workflow.

### Choose the workflow for your contribution

Follow the [External Contribution Workflow](nv_core/sr_specs/docs/guides/external_contribution_workflow.md)
for the full branch, tier, contract, sample, evaluation, and review sequence.

For domain- or organization-specific content, start with
[how to define your tier](nv_core/sr_specs/docs/guides/foundation_pypi.md#creating-your-own-tier).
The guide covers package metadata, discovery entry points, validators, and
content layout. Read the [tier overview](nv_core/sr_specs/docs/guides/tiers.md)
to decide where your contribution belongs: a downstream tier can extend Core
without changing the upstream contracts.

| Contribution | Workflow |
| --- | --- |
| Define and distribute a tier | [Creating Your Own Tier](nv_core/sr_specs/docs/guides/foundation_pypi.md#creating-your-own-tier) |
| Propose specification content and understand review gates | [SimReady Acceptance Workflow](nv_core/sr_specs/docs/guides/acceptance_workflow.md) |
| Add a requirement, validator, and feature together | [Adding a New Feature](nv_core/sr_specs/docs/guides/features_expansion_workflow.md) |
| Define or version features and runtime variants | [Features Documentation Guide](nv_core/sr_specs/docs/guides/features/features.md) |
| Define or version profiles | [Profiles Documentation Guide](nv_core/sr_specs/docs/guides/profiles/profiles.md) |
| Validate profiles and manage multiple profiles | [Profiles Validation Workflow](nv_core/sr_specs/docs/guides/profiles_validation_workflow.md) |
| Convert assets between feature contracts | [Feature Adapters Documentation Guide](nv_core/sr_specs/docs/guides/feature_adapters/feature_adapters.md) |
| Prove static asset conformance | [SimReady Validation Workflow](nv_core/sr_specs/docs/guides/validate_workflow.md) |
| Add or run behavioral tests and preserve evidence | [SimReady Evaluate](nv_core/sr_specs/docs/guides/evaluate/evaluate.md) |
| Package assets | [SimReady Packaging Workflow](nv_core/sr_specs/docs/guides/packaging_workflow.md) |
| Add semantic-label vocabularies | [Adding a Custom Taxonomy](nv_core/sr_specs/docs/guides/adding_a_custom_taxonomy.md) |
| Choose attribute prefixes and rule namespaces | [Naming Conventions](nv_core/sr_specs/docs/guides/naming_conventions.md) |

For Foundation changes:

- Keep requirement docs, validators, feature JSON manifests, profile TOMLs,
  authoring docs, and shared indexes consistent.
- Preserve published capability, feature, and profile versions. Add a new
  contract version when behavior changes, and retain the previous version. Use
  dotted Foundations 2 IDs for capabilities and features.
- Edit profiles in their owning tier's `profiles/` directory; TOML files are
  the machine-readable source of truth.
- Edit agent skills under `skills/`; the agent-specific skill directories are
  compatibility links. Use the applicable skill's `SKILL.md` for its workflow.
- Use native OpenUSD schemas and composition patterns for USD work. Repair
  staged asset copies and derive physical values from the actual asset.
- Preserve license notices and document the source and license of new sample
  content. Follow the repository's Git LFS tracking rules for assets.
- Edit source files rather than generated documentation build output.

## Validate and submit for review

Run the checks relevant to your change and include the commands, results, and
any remaining validation gaps in your pull request. For documentation changes,
check links and formatting and build the docs when the change affects rendered
spec pages. For validators and adapters, demonstrate the expected behavior with
appropriate passing and failing cases.

Asset validation, runtime evaluation, and packaging use the external
`simready-validate`, `simready-evaluate`, and `simready-package` libraries. Follow
their bundled skills when available and the repository's
[validation](nv_core/sr_specs/docs/guides/validate_workflow.md) and
[evaluation](nv_core/sr_specs/docs/guides/evaluate/evaluate.md) guides. Ensure
validation uses the Foundation content version containing your change, and
preserve the resulting reports.

Push to your agreed branch and record the commit and evidence in the issue.
Open a pull request when the maintainer confirms the review route and target
branch. Include:

- A link to the coordinating issue.
- DCO sign-offs on every commit, as described in [Signing off your work](#signing-off-your-work).
- The problem, resulting behavior, and affected requirement or contract versions.
- Validation evidence and any limitations or manual checks.

Use a draft pull request while work is in progress. Before accepting an outside
contribution, the maintainer verifies the commit sign-offs and completes
NVIDIA's IP review. The maintainer reviews the change and coordinates its merge.

