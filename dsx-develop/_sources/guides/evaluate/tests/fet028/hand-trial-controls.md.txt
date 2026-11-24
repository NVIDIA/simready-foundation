# Configured hand trials (FET028)

The cube and sphere procedures accept optional `hand_trial_controls` for
independently driven hands. They are explicit trial configuration, not an
automatic tuning system or asset repair. `{}` preserves automatic mapping and
the existing simultaneous close. Published feature identities, default object
sizes/payload fractions and grasp verdict thresholds are unchanged.

Use the supported plan-editing/configuration API with a fresh output directory
and `--no-stamp` for diagnostic comparisons. Do not hand-edit saved results or
replace the official test with a copied runner. Read the loaded provider's
configuration and joint inventory before using an override.

## Controls

| Key | Meaning and validation |
| --- | --- |
| `joints` | At most 64 named independent angular joints. Each record supplies either `hold_rad`, or both `open_rad` and `closed_rad`. Targets are finite radians and must remain within the resolved joint limits. A complete signed pair can decrease or increase; equal targets mean held, not closing. |
| `close_delay_steps` | Named closing-joint delays, integer step calls from 0 to 10,000. Each delayed ramp must finish inside the configured `close_steps`; the test never silently enlarges that budget. |
| `approach_pitch_deg` | Finite 0–90 degrees downward from horizontal: 0 is world +X, 90 is world −Z. The target grip direction is world −Y. Omission retains the existing hand approach; physical-root pivot handling remains in force. |
| `grasp_center_base_m` | Three finite metre coordinates in the physical gripper-base rotational frame. Approach prediction uses the resolved pre-rebuild USD frame, stage scale and physical-root pivot; does not rewrite the authored grasp-site marker or establish a live tensor orientation. |
| `object_offset_world_xy_m` | Two finite metre offsets in world X/Y from the planned object center. Omission means no offset. |
| `descent_reference` | `fingertips` by default, or `grasp_center`. Center-based descent requires an explicit `grasp_center_base_m` and retains the existing object-motion stop/backoff proxy. |

Joint names are resolved after carrier insertion/remapping. Carrier coordinates,
mimic followers, passive/loop-owned joints and ambiguous identities are not
independent controls. Explicit `_rad` targets require a uniquely resolved
angular joint; unqualified prismatic coordinates cannot be declared radians.
Every required finger branch must retain at least one closing target. A held
opposition joint cannot satisfy engagement or stall by itself.

Procedure 1.4.9 keeps independent mimic chains within the existing hand path.
Free and mimic fingers can coexist, with finite signed/asymmetric gearing.
Every raw active selected coupling must resolve safely before either jaw or
hand mapping; unresolved references, cycles, duplicate ownership, invalid
coefficients and missing/ambiguous tips are execution limitations. Each physical
branch supplies one distinct distal tip, including follower/passive geometry,
and each independent leader is probed against that tip. Followers never enter
`finger_chains`, sparse `{idx, open, closed, name}` specs or eligible overrides,
even if native DOFs and authored drives expose them. Name capture/remapping
keeps this leader identity across carrier insertion and reordered native DOFs.
A wholly held branch still fails the existing per-branch closure requirement.
The limits, measured polarity, restoration and required-state guards remain
in force.

Parallel/centric candidate bodies and their passive/fixed descendants use the
selected physical root and non-closure graph, independent of authored body0/body1
order. A floating container requires complete qualified cooked-parent metadata;
missing or ambiguous root evidence is a setup limitation. Excluded closure
edges do not become parent edges, and follower/passive geometry does not acquire
command ownership. Bounded schema-light helper compatibility retains its
conventional endpoint fallback without qualifying native topology. The official
caller uses the loaded asset boundary; arbitrary descendant search hints are
not qualified by this procedure. Live aperture/polarity probing and all existing
grasp criteria still apply. Source-host stepped adapters establish routing and
restoration only, not native hand acceptance.

Unknown keys, partial/conflicting records, nonfinite values, out-of-limit
targets and invalid schedules are configuration/setup errors, not asset FAIL.
Overrides do not bypass required live readback, safe probing or restoration.
Nonempty controls require integral `close_steps` from 1 to 10,000 and integral
`close_ramp_steps` from 1 through that budget; Boolean/fractional/string budgets
are rejected. Original array readbacks must use integer/unsigned/float dtypes,
not Boolean, complex or object arrays. Held joints remain required readable
coordinates even though they do not contribute to closure engagement/stall.
Required selected grasp/rail coordinates also reject malformed original numeric
types and magnitudes above `sqrt(float32.max)` (approximately 1.845e19 native
units), before capture. This conservative representational safety envelope is
not a mechanical stop, permitted tracking-error threshold, or qualification of
a native unit scale. Unrelated unavailable coordinates remain optional; ordinary
overshoot is still evaluated by the existing grasp criteria.
Configured centers/offsets and resolved stage/world placement are also checked
after coordinate conversion against that envelope before fixture/object
authoring. Finite metre inputs alone do not guarantee a usable resolved position;
the stage length scale must be a finite positive numeric scalar.
For a delayed close, the joint holds its measured starting coordinate until
its own ramp begins; early stall completion is blocked until all scheduled
ramps finish. Delays count step calls, not video frames or exact solver time.

For example, after checking the actual joint names/limits, a **configured** hand
trial might use the following shape (the names and numbers are illustrative,
not universally valid targets or a built-in Ability Hand preset):

```json
{
  "hand_trial_controls": {
    "joints": {
      "opposition_joint": {"hold_rad": -1.0},
      "finger_joint": {"open_rad": 0.0, "closed_rad": 0.5}
    },
    "close_delay_steps": {"finger_joint": 100},
    "approach_pitch_deg": 15.0,
    "grasp_center_base_m": [0.01, 0.02, 0.10],
    "object_offset_world_xy_m": [0.005, 0.0],
    "descent_reference": "grasp_center"
  }
}
```

Existing `object_size_fraction` and `tested_mass_kg_override` remain the size
and direct-mass controls. Do not change canonical `gripper_maxOpening` (or its
legacy `custom:maxOpening` alias), rated payload,
self-collision, solver settings or drive gains merely to reproduce a green
trial. A larger-than-authored-opening object needs separately explained
geometry/metadata evidence, not a silent change to qualification defaults.

## Effective results and coverage

`gripper_trial_controls` records the resolved object dimensions/mass, joint
identity/units, held/closing role, signed targets, delays, approach/placement and
consumed procedure settings. Later trials use `_trial_002`, etc. Missing fields
remain unknown and omission counts survive reporting. The HTML report presents
**Recorded grasp trial controls** below the video; the registration description
states defaults. A record made during setup is not proof that motion executed:
check the outcome and completed phase metrics.
Grasp, joint and force histories retain separate shape/trial identity. The first
history names are preserved; later trials receive a suffix so repeated shapes
cannot overwrite or lose earlier motion. `trial_index` is zero-based and
`trial_number` is one-based, matching the human-readable report headings.

Keep cube and sphere outcomes, same-revision static validation and selected
contract dependencies separate. A configured cube PASS does not establish a
default-size PASS, sphere behavior, a hardware payload rating, or full contract
qualification. Results rendered by a newer reporter still belong to the
provider/test/engine versions that actually ran.

## Optional native contacts

`diagnostic_native_contact_pairs` defaults to `false` and accepts only an explicit
JSON Boolean (`true` or `false`). Strings such as `"false"`, numbers, null and
containers are configuration errors before trial/observer mutation, not
truthy native opt-ins. A compatible PhysX Engine
Kit observes the explicit synthetic rigid body against discovered hand bodies.
Only that test object receives temporary contact-report opinions in an owned
anonymous session sublayer; source-asset bodies and unrelated scene content are
not edited. The collector is closed on success, failure and cancellation.
Ordinary unavailable APIs/readbacks or truncated observations warn without
changing grasp criteria. Failed required cleanup is a runtime-health problem,
not an asset grasp failure; a contaminated stage must not be reused.
Required cleanup failure retires the Kit process, including on cancellation.
Restart Kit before another run; reopening the interactive window does not reset
that retirement flag.

Required support, carrier and spawned physical-object cleanup is attempted
independently even after a stop request. The object's captured USD edit target
owns its removal; an unrelated layer is not deleted to make cleanup appear
successful. If carrier restoration cannot confirm its stop/topology barrier,
the physical object is preserved for required scene teardown and worker
retirement; no additional object topology edit bypasses that barrier.
Failed native cleanup is an execution/health error, not an asset
grasp FAIL or optional media warning. Compatible EngineKit adapters latch
worker retirement for these failures. Cleanup preserves the first trial or
required-cleanup cause, including cancellation, keyboard interruption and
system exit; optional evidence/video/log sink errors cannot replace it.
Secondary diagnostic notes are best-effort too: missing/raising `add_note`,
message formatting or note delivery cannot mask the first required cause,
including SDK exceptions without Python's note API.
With no earlier cause, a new stop request propagates after required cleanup.

`native_contact_diagnostics` contains bounded phase/pair summaries, ordered
actor/collider identities, counters, availability, cleanup status and nullable
Kit timeline times. Header/point inspections are capped per callback; retained
phase/pair summaries are capped over the trial. Individual points and friction
anchors are not retained. Units remain `unknown_native` until the exact native
API/backend conversion is qualified; metre stage scale alone is insufficient.

Peak single-point impulse is not force, actuator effort or total pair impulse.
Positive-separation/zero-impulse events do not prove force-bearing contact.
Missing readings remain null, and partial summaries do not establish continuous
contact or precise video synchronization. No new physics steps, captures,
commands, material tuning or verdict thresholds are introduced for collection.

## Verification

Cover held opposition plus sibling flexion, reversed closing polarity, delays,
foreign/follower/carrier rejection, valid fixed-joint roots, rotated/scaled
attachments, required-state-before-capture guards and exact cleanup. Preserve
parallel-jaw/centric behavior and no-hook/no-capture compatibility. Qualify new
builds with real static validation and both supported shapes in Isaac/PhysX,
including default and explicitly configured trials. Host-only tests and archived
Ability Hand results do not establish native qualification of this version.
