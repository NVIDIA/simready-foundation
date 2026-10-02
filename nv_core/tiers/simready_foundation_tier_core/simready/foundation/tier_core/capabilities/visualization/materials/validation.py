# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Validation rules for Visual Materials capability.
"""

import contextlib
import logging
import math
import os
from functools import partial
from pathlib import Path
from typing import List, Optional

import simready.foundation.tier_core.requirements as cap
from pxr import Gf, Sdf, Sdr, Usd, UsdGeom, UsdShade
from usd_validation_nvidia import BaseRuleChecker, Suggestion, register_requirements

from .util.mdl_helpers import get_mdl_module_parameter_descs, is_mdl_helper_available

try:
    import omni.client
except ImportError:
    omni = None

logger = logging.getLogger(__name__)


# MDL modules Kit ships and resolves from its own search paths. A reference to one of
# these is authored as the bare module name on purpose: Kit ties MDL module identity to
# filesystem location, so a copy inside the asset is a different module, and the Isaac
# asset transformer rewrites such references to this canonical form rather than packaging
# the file. Anchoring one would make it a layer-relative path that resolves to nothing.
#
# Kept in sync with the fallback list in the asset transformer's
# ``isaacsim.asset.transformer.rules.utils``, which is the runtime that authors them.
BUILTIN_MDL_MODULES = frozenset(
    {
        "omnipbr.mdl",
        "omnipbr_base.mdl",
        "omnipbr_clearcoat.mdl",
        "omniglass.mdl",
        "omniemissive.mdl",
        "omnisurface.mdl",
        "omnisurfacebase.mdl",
        "omnisurfaceblend.mdl",
        "omnisurfacelite.mdl",
        "omnisurfacelitebase.mdl",
        "omnihair.mdl",
        "omnihairbase.mdl",
        "omnisurfacepresets.mdl",
        "usdpreviewsurface.mdl",
        "core_definitions.mdl",
    }
)

# Prefixed forms Kit also resolves, where the package directory disambiguates modules
# that share a basename.
BUILTIN_MDL_SUFFIXES = frozenset({"nvidia/core_definitions.mdl"})


def is_builtin_mdl_module(source_path: str) -> bool:
    """Whether this path names an MDL module Kit ships and resolves for itself.

    Name-based and case-insensitive, matching how Kit's own MDL search paths resolve.
    A project-local copy at an explicit path counts too: the copy cannot be relocated
    into the asset and stay the same module, so it is the same exemption.
    """
    normalized = source_path.replace("\\", "/").lower()
    if normalized.rsplit("/", 1)[-1] in BUILTIN_MDL_MODULES:
        return True
    return any(normalized.endswith(suffix) for suffix in BUILTIN_MDL_SUFFIXES)


@register_requirements(
    cap.MaterialsRequirements.VM_BIND_002,
    cap.MaterialsRequirements.VM_MAT_001,
    cap.MaterialsRequirements.VM_MDL_001,
    cap.MaterialsRequirements.VM_TEX_001,
    cap.MaterialsRequirements.VM_TEX_002,
    cap.MaterialsRequirements.VM_TEX_005,
    cap.MaterialsRequirements.VM_TEX_003,
    cap.MaterialsRequirements.VM_TEX_004,
    cap.MaterialsRequirements.VM_PBR_001,
    cap.MaterialsRequirements.VM_PBR_002,
    cap.MaterialsRequirements.VM_PBR_003,
    cap.MaterialsRequirements.VM_PS_002,
    cap.MaterialsRequirements.VM_MDL_003,
    override=True,
)
class VisualMaterialsCapabilityChecker(BaseRuleChecker):
    """Checker for Visual Materials capability requirements."""

    # The OpenPBR surface nodedef accepted as the source of outputs:mtlx:surface (VM.PBR.001).
    openpbr_surface_id = "ND_open_pbr_surface_surfaceshader"

    # Refractive-index bounds for OpenPBR IOR inputs (VM.PBR.002). 1.0 is vacuum; below it
    # is physically impossible. 3.0 admits the dielectrics a scene realistically contains,
    # including diamond at 2.42 and moissanite at 2.65. Materials whose real index is
    # higher are conductors and carry their response in base_color with base_metalness = 1,
    # so the dielectric IOR does not apply to them.
    ior_min = 1.0
    ior_max = 3.0

    # Physical ranges for OpenPBR inputs (VM.PBR.002). Intersected with the live nodedef
    # input names at check time, so a name absent from the resolved nodedef is skipped.
    openpbr_ranges = {
        "unit_float": {
            "base_weight",
            "base_metalness",
            "base_diffuse_roughness",
            "specular_weight",
            "specular_roughness",
            "specular_roughness_anisotropy",
            "transmission_weight",
            "subsurface_weight",
            "coat_weight",
            "coat_roughness",
            "coat_roughness_anisotropy",
            "coat_darkening",
            "thin_film_weight",
            "fuzz_weight",
            "fuzz_roughness",
            "geometry_opacity",
        },
        "ior_float": {
            "specular_ior",
            "coat_ior",
        },
        "non_negative_float": {
            "emission_luminance",
        },
        "unit_color3": {
            "base_color",
            "specular_color",
            "transmission_color",
            "subsurface_color",
            "coat_color",
            "fuzz_color",
            "emission_color",
        },
    }

    # Shader ids that are valid UsdShade ids but are not MaterialX nodedefs, so they do
    # not resolve through MaterialX discovery (VM.PBR.003).
    known_usd_shader_ids = {
        "UsdPreviewSurface",
        "UsdUVTexture",
        "UsdTransform2d",
        "UsdPrimvarReader_float",
        "UsdPrimvarReader_float2",
        "UsdPrimvarReader_float3",
        "UsdPrimvarReader_float4",
        "UsdPrimvarReader_int",
        "UsdPrimvarReader_string",
        "UsdPrimvarReader_normal",
        "UsdPrimvarReader_point",
        "UsdPrimvarReader_vector",
        "UsdPrimvarReader_matrix",
    }

    # Texture inputs that carry a color signal and so expect an sRGB encoding
    # (VM.TEX.002). Every other texture input on an MDL shader carries data and
    # expects a linear encoding. These are MDL and OmniPBR input names, which is why
    # the requirement is scoped to the MDL format.
    #
    # ``inputs:diffuse_texture`` was previously listed here and in a
    # ``colorspace_optional_list`` as well. The sRGB list is tested first, so the
    # optional entry was unreachable and the input was in practice always required to
    # be sRGB. That is the correct expectation for a base color texture, so the
    # unreachable list has been removed rather than the entry moved: no texture input
    # is currently exempt from a color-space expectation.
    #
    # The color textures were read off the modules shipped in sample_content rather
    # than guessed from their names. In MDL a data texture carries an ``anno::usage``
    # naming the signal -- "occlusion", "roughness", "normal", "opacity" -- and a color
    # texture carries none and sits in a color group. On that test OmniPBR contributes
    # diffuse_texture and emissive_color_texture (emissive_mask_texture is
    # anno::usage("occlusion"), so it is data and expects raw), and OmniGlass
    # contributes glass_color_texture and reflection_color_texture.
    colorspace_srgb_list = [
        "inputs:diffuse_texture",
        "inputs:emissive_color_texture",
        "inputs:glass_color_texture",
        "inputs:reflection_color_texture",
        "inputs:UV_VertexColor",
        "inputs:Set1SuperAlbedo",
        "inputs:Set2SuperAlbedo",
    ]

    # The ``colorSpace`` metadata this requirement reads is typed against the
    # ``Gf.ColorSpaceNames`` vocabulary, so that is what the expectations below are
    # written in. ``Gf.ColorSpace.IsValid`` is the membership test; constructing a
    # ``Gf.ColorSpace`` succeeds for any string and so proves nothing.
    colorspace_srgb_canonical = "srgb_rec709_scene"
    colorspace_linear_canonical = "raw"

    # Names that are not in Gf.ColorSpaceNames but unambiguously denote one of the two
    # encodings above, accepted so that content authored against the neighbouring
    # vocabularies is not reported as wrong.
    #
    # "sRGB" and "raw" are the UsdUVTexture inputs:sourceColorSpace tokens. "raw" is
    # also a Gf.ColorSpaceNames member, so it needs no alias; "sRGB" is not.
    #
    # "srgb_texture" and "none" are the MaterialX names. srgb_texture is the sRGB
    # transfer function over Rec.709 primaries, which is srgb_rec709_scene: gamma 2.4
    # with a linear bias of 0.055, distinct from g22_rec709_scene at gamma 2.2 with no
    # bias. "none" means no color transform, which is raw.
    colorspace_aliases = {
        "sRGB": colorspace_srgb_canonical,
        "srgb_texture": colorspace_srgb_canonical,
        "none": colorspace_linear_canonical,
    }

    # "auto" asks the consumer to decide the encoding from the image file. On a color
    # input it agrees with the convention and is accepted. On a data input it decodes an
    # 8-bit three- or four-channel file as sRGB, which is wrong, but leaves a
    # single-channel file alone -- so it is accepted there only when the image really is
    # single channel. Deciding that needs the file; without Pillow the check defers.
    colorspace_defer = {"auto"}

    # UsdUVTexture declares inputs:sourceColorSpace as a token with exactly these values.
    # A Gf.ColorSpaceNames name is not one of them, so it is reported on that attribute
    # even where it denotes the right encoding.
    source_color_space_values = frozenset({"raw", "sRGB", "auto"})
    single_channel_pil_modes = frozenset({"1", "L", "I", "F", "I;16", "I;16B", "I;16L"})

    # What a repair writes. The checks above read several spellings of each encoding, but
    # a repair has to settle on one, and these are the two the shipped content already
    # uses: they are the only tokens UsdUVTexture's inputs:sourceColorSpace accepts, and
    # they are how MDL content spells its colorSpace metadata. Both canonicalise to the
    # expectations above, so a texture a repair touches passes the check that asked for it.
    colorspace_repair_srgb = "sRGB"
    colorspace_repair_linear = "raw"

    # VM.TEX.004 reads MaterialX's own vocabulary literally rather than canonicalising it.
    # srgb_texture and srgb_rec709_scene denote the same encoding, but only the MaterialX
    # spelling is resolved by the MaterialX versions the target runtimes ship, so the two
    # cannot be treated as equivalent on this surface.
    openpbr_colorspace_srgb = "srgb_texture"

    # OpenUSD's name for that same encoding. Authoring intent is right and the fix is a
    # rename, so this is a warning: the decode is skipped and the texture renders
    # undecoded, but the asset is not malformed.
    openpbr_colorspace_srgb_unresolved = "srgb_rec709_scene"

    # "apply no transform", which is what a data input needs. An absent colorSpace means
    # the same thing. RTX logs an error for both spellings; the render is unaffected and
    # hdStorm accepts "none" silently, so neither is reported here.
    openpbr_colorspace_data = frozenset({"none", "raw"})

    # Texture size limit (VM.TEX.001)
    max_texture_size = 16384  # 16K pixels

    # Cache for MDL validation (VM.BIND.002)
    _cache_existing_filepaths = set()
    _cache_mdl_specs = {}

    # Said once when the nodedef-dependent checks cannot run. VM.PBR.002 compares
    # authored values against the inputs a nodedef declares and VM.PBR.003 compares
    # authored ids and types against it; with no nodedef there is nothing to compare
    # against and they report nothing, which reads exactly like a clean asset.
    # VM.PBR.001 is not in that list: it matches one literal shader id and needs no
    # nodedef, so it runs either way.
    nodedef_skip_notice = (
        "VM.PBR.002 and VM.PBR.003 did not run: no OpenPBR nodedef could be resolved in "
        "this environment, so there is nothing to check authored input names, input "
        "values and input types against. Neither Sdr (which needs USD's usdMtlx plugin) "
        "nor the MaterialX Python package could supply one. These two requirements "
        "report nothing for every asset in this run, which is not the same as passing "
        "them. Install MaterialX>=1.39 to enable them."
    )

    # Emitted once per run rather than once per prim: the condition is a property of the
    # environment, not of any asset, and CheckPrim fires for every prim on every stage.
    _nodedef_skip_reported = False

    def CheckStage(self, usdStage: Usd.Stage) -> None:
        """Reset per-stage state, and say once per run when the nodedef checks cannot run.

        ``CheckStage`` is the run-scoped hook: it fires once per asset, before any
        ``CheckPrim``. The nodedef notice is guarded by a class-level flag so a batch of
        assets is told once, since MaterialX either imports for the whole process or it
        never does. The VM.PBR.001 report set is per stage, so it is cleared here.
        """
        self._pbr_001_reported = set()
        self._vm_ps_002_reported = set()
        self._vm_mdl_003_reported = set()

        # A material library is an asset whose subject is the material: Material prims
        # and no geometry to bind them to. The surface requirements are written against
        # what a final render uses, which on such an asset is nothing, so they would
        # report nothing at all. Where the stage has no geometry a final render would
        # draw, the subject becomes the Material prims themselves.
        self._check_surfaces_without_geometry(usdStage)

        if VisualMaterialsCapabilityChecker._nodedef_skip_reported:
            return
        if self._materialx_nodedefs_available():
            return
        VisualMaterialsCapabilityChecker._nodedef_skip_reported = True

        # Two channels, because they reach different readers. The issue is the structured
        # record; the log line is what the simready-validate CLI actually prints, since it
        # reports only ERROR and FAILURE issues and would drop a warning-severity one.
        self._AddWarning(message=self.nodedef_skip_notice)
        logger.warning(self.nodedef_skip_notice)

    def _renders_any_geometry(self, stage: Usd.Stage) -> bool:
        """Whether the stage has geometry a final render would draw.

        The same subject the per-prim surface requirements use: a GPrim whose computed
        purpose is default or render. Proxy and guide geometry is excluded, so an asset
        whose only meshes are a proxy stand-in is read as having no renderable geometry.
        """
        for prim in stage.Traverse():
            if UsdGeom.Gprim(prim) and self._has_default_or_renderable_purpose(prim):
                return True
        return False

    def _check_surfaces_without_geometry(self, stage: Usd.Stage) -> None:
        """On an asset that is a material, require the surface of at least one Material.

        Two subjects, one requirement each. Where the asset has geometry a final render
        draws, every material that geometry resolves must connect the terminal -- that is
        what makes the render trustworthy, and it is checked per prim. Where the asset has
        no such geometry, there is nothing to resolve a binding from, and the same
        requirement asks instead that at least one Material prim connects it.

        The second subject is what a material library needs. Its files declare materials
        and no geometry, so a requirement written only against bound materials reports
        nothing about them, and a feature built from it states nothing a consumer can act
        on. ``VG.MESH.001`` uses the same stage-level shape to require at least one mesh.

        "At least one" rather than "every" here because an asset with no geometry has no
        way to say which of its materials a consumer will use. On an asset with geometry
        the per-prim rule is the stronger one and this branch does not run.
        """
        if self._renders_any_geometry(stage):
            return

        materials = [
            prim
            for prim in stage.Traverse()
            if prim.GetTypeName() == "Material" and not self._is_physics_only_material(prim)
        ]
        if not materials:
            return

        for terminal, requirement, description in (
            ("outputs:surface", cap.MaterialsRequirements.VM_PS_002,
             "a UsdPreviewSurface preview"),
            ("outputs:mdl:surface", cap.MaterialsRequirements.VM_MDL_003,
             "an MDL final surface"),
            ("outputs:mtlx:surface", cap.MaterialsRequirements.VM_PBR_001,
             "an OpenPBR final surface"),
        ):
            if any(
                terminal in [name for name, _ in self._connected_surface_terminals(prim)]
                for prim in materials
            ):
                continue
            self._AddFailedCheck(
                message=(
                    f"this asset declares {len(materials)} material(s) and no geometry a "
                    f"final render would draw, and none of them connects '{terminal}', so "
                    f"the asset does not provide {description}"
                ),
                at=stage.GetPseudoRoot(),
                requirement=requirement,
            )

    def CheckPrim(self, prim: Usd.Prim) -> None:
        stage = prim.GetStage()
        prim_path = prim.GetPath()

        # Check for VM.MDL.001: MDL material source asset compliance
        self.check_vm_mdl_001_material_mdl_source_asset(stage, prim_path)

        # Check for VM.MAT.001: Mesh material binding compliance
        self.check_vm_mat_001_mesh_material_binding(stage, prim_path)

        # Check for VM.BIND.002: Shader inputs validation
        self.check_vm_bind_002_shader_inputs(stage, prim_path)

        # Check for VM.TEX.001: Texture size compliance
        self.check_vm_tex_001_texture_size(stage, prim_path)

        # Check for VM.TEX.002 and VM.TEX.005: color space, MDL, by input name
        self.check_vm_tex_002_colorspace(stage, prim_path)
        self.check_vm_tex_005_colorspace(stage, prim_path)

        # Check for VM.TEX.003: Color space compliance, traced from the surface input
        self.check_vm_tex_003_traced_colorspace(stage, prim_path)

        # Check for VM.PBR.001: OpenPBR final surface
        self.check_vm_pbr_001_openpbr_surface(stage, prim_path)

        # Check for VM.PBR.002: OpenPBR parameter ranges
        self.check_vm_pbr_002_openpbr_parameter_ranges(stage, prim_path)

        # Check for VM.PBR.003: MaterialX graph structure
        self.check_vm_pbr_003_materialx_graph_structure(stage, prim_path)

        # Check for VM.PS.002: the UsdPreviewSurface preview is present
        self.check_vm_ps_002_preview_surface_present(stage, prim_path)

        # Check for VM.MDL.003: the MDL final surface is present
        self.check_vm_mdl_003_mdl_surface_present(stage, prim_path)

    # The terminal each presence requirement asks for, and how to name it.
    _presence_terminals = {
        "VM_PS_002": ("outputs:surface", "a UsdPreviewSurface preview"),
        "VM_MDL_003": ("outputs:mdl:surface", "an MDL final surface"),
    }

    def check_vm_ps_002_preview_surface_present(self, stage, prim_path: str) -> List[str]:
        """Check VM.PS.002: what a renderable GPrim renders with has a preview surface.

        ``com.nvidia.usd.VM.PS.001`` validates a UsdPreviewSurface's input types and token
        values, and it is silent on an asset that has no UsdPreviewSurface at all, because
        there is nothing for it to inspect. This asks the other half: that the surface is
        there. Without it a ``FET_006_STANDARD`` pass does not mean the asset has a
        preview surface, so a consumer searching validation metadata for assets it can
        render without MDL or MaterialX cannot use the feature to find them.

        Driven from the geometry, on the same gate VM.MAT.001 and VM.PBR.001 use, so all
        three ask about the same prims: a GPrim whose computed purpose is default or
        render. A material that nothing binds is outside the question, and a GPrim that
        resolves no material at all is VM.MAT.001's to report.
        """
        return self._check_surface_present(stage, prim_path, "VM_PS_002")

    def check_vm_mdl_003_mdl_surface_present(self, stage, prim_path: str) -> List[str]:
        """Check VM.MDL.003: what a renderable GPrim renders with has an MDL surface.

        ``VM.MDL.001`` validates an MDL shader's source asset and sub-identifier, and is
        silent on a material with no MDL shader. This asks that the surface is there, so
        that a ``FET_006_MDL`` pass means the asset has one.

        MDL does not travel outside Omniverse, so a profile requiring this is stating that
        its consumers need OmniPBR behaviour. The current profiles list FET_006_MDL as
        optional.
        """
        return self._check_surface_present(stage, prim_path, "VM_MDL_003")

    def _check_surface_present(self, stage, prim_path: str, code: str) -> List[str]:
        """Every material a renderable GPrim resolves connects ``terminal``.

        One material is commonly bound to many GPrims and the defect belongs to the
        material, so it is reported once per stage, the way VM.PBR.001 reports.
        """
        errors = []
        terminal, description = self._presence_terminals[code]

        prim = stage.GetPrimAtPath(prim_path)
        if not prim:
            return errors
        if not UsdGeom.Gprim(prim) or not self._has_default_or_renderable_purpose(prim):
            return errors

        seen_attr = "_%s_reported" % code.lower()
        reported = getattr(self, seen_attr, None)
        if reported is None:
            reported = set()
            setattr(self, seen_attr, reported)

        for material in self._bound_materials(prim):
            material_prim = material.GetPrim()
            # A friction-only material describes no appearance, so no surface is
            # required of it. The same guard VM.PBR.001 and VM.PBR.003 apply.
            if self._is_physics_only_material(material_prim):
                continue
            material_path = material_prim.GetPath()
            if material_path in reported:
                continue
            reported.add(material_path)

            connected = [name for name, _ in self._connected_surface_terminals(material_prim)]
            if terminal in connected:
                continue
            self._AddFailedCheck(
                message=(
                    f"material '{material_path}' is bound for rendering and connects no "
                    f"'{terminal}', so the asset does not have {description} on the "
                    f"geometry it renders"
                    + (f": it connects {', '.join(connected)}" if connected else "")
                ),
                at=material_prim,
                requirement=getattr(cap.MaterialsRequirements, code),
            )
            errors.append(f"No '{terminal}' on {material_path}")

        return errors

    def check_vm_mat_001_mesh_material_binding(self, stage, prim_path: str) -> List[str]:
        """Check VM.MAT.001: material binding resolves, and resolves deterministically.

        Every renderable GPrim resolves a material for the ``full`` purpose, and bindings
        are direct or inherited rather than collection-based. Binding strength overrides
        are reported as advisory.
        """
        errors = []

        prim = stage.GetPrimAtPath(prim_path)
        if not prim:
            return errors

        # The binding mechanism is checked on any prim that authors a binding, not only on
        # GPrims, since a collection binding is typically authored on an ancestor Xform.
        errors.extend(self._check_binding_mechanism(prim, prim_path))

        # Skip non-GPrims and "non-renderable" prims such as proxies
        # This also skips GeomSubsets, because they are not GPrims
        # We will inspect GeomSubsets later as we check the GPrim
        if not UsdGeom.Gprim(prim) or not self._has_default_or_renderable_purpose(prim):
            return errors

        # Get the computed material for this prim
        prim_material, _ = self._get_material(prim)

        # Check for GeomSubsets which can have their own material bindings
        mtl_binding_api = UsdShade.MaterialBindingAPI(prim)
        geom_subsets = mtl_binding_api.GetMaterialBindSubsets() or []

        if not geom_subsets:
            # No subsets, check the prim itself
            if not prim_material:
                self._AddFailedCheck(
                    message=f"GPrim '{prim_path}' does not have a material binding",
                    at=prim,
                    requirement=cap.MaterialsRequirements.VM_MAT_001,
                )
                errors.append(f"Missing material binding for GPrim: {prim_path}")
        else:
            # Has subsets, check each subset
            for geom_subset in geom_subsets:
                geomsubset_material, _ = self._get_material(geom_subset)
                if not geomsubset_material:
                    self._AddFailedCheck(
                        message=f"GeomSubset '{geom_subset.GetPath()}' does not have a material binding",
                        at=geom_subset.GetPrim(),
                        requirement=cap.MaterialsRequirements.VM_MAT_001,
                    )
                    errors.append(f"Missing material binding for GeomSubset: {geom_subset.GetPath()}")

        return errors

    def _check_binding_mechanism(self, prim: Usd.Prim, prim_path: str) -> List[str]:
        """Collection-based bindings are not permitted; strength overrides are advisory.

        Both were previously stated as a separate binding-purposes requirement. They are
        part of VM.MAT.001 because they constrain how the same binding resolves.

        Only the collection-based binding is a conformance failure and so only it is
        returned. VM.MAT.001 states the strength override as a SHOULD, so it is raised as
        a warning and kept out of the returned list, which callers read as failure.
        """
        errors = []

        for prop in prim.GetProperties():
            name = prop.GetName()
            if not name.startswith("material:binding:collection:"):
                continue
            self._AddFailedCheck(
                message=(
                    f"'{prim_path}' authors a collection-based material binding "
                    f"('{name}'); bindings must be direct or inherited"
                ),
                at=prim,
                requirement=cap.MaterialsRequirements.VM_MAT_001,
            )
            errors.append(f"Collection-based binding on {prim_path}: {name}")

        for prop in prim.GetProperties():
            name = prop.GetName()
            if not name.startswith("material:binding"):
                continue
            try:
                strength = UsdShade.MaterialBindingAPI.GetMaterialBindingStrength(prop)
            except Exception:
                continue
            if strength and strength != UsdShade.Tokens.weakerThanDescendants:
                self._AddWarning(
                    message=(
                        f"'{prim_path}' overrides binding strength on '{name}' "
                        f"(bindMaterialAs = {strength}); the default is recommended"
                    ),
                    at=prim,
                    requirement=cap.MaterialsRequirements.VM_MAT_001,
                )

        return errors

    def _has_default_or_renderable_purpose(self, prim: Usd.Prim) -> bool:
        """Returns True if the prim is Imageable with default or renderable purpose."""
        imageable = UsdGeom.Imageable(prim)
        if not imageable:
            return False
        purpose = imageable.ComputePurpose()
        return purpose in (UsdGeom.Tokens.default_, UsdGeom.Tokens.render)

    def _get_material(self, prim_or_geom_subset) -> tuple:
        """Returns the computed "full" purpose material and the relationship of the prim/geomSubset."""
        return UsdShade.MaterialBindingAPI(prim_or_geom_subset).ComputeBoundMaterial(
            materialPurpose=UsdShade.Tokens.full
        )

    # ------------------------------------------------------------------
    # OpenPBR (VM.PBR.*)
    # ------------------------------------------------------------------
    # The surface terminals a Material may carry: the universal one a preview surface
    # drives, and the two render-context ones a final surface drives.
    surface_terminals = ("outputs:surface", "outputs:mtlx:surface", "outputs:mdl:surface")

    # The two that carry a physically based final surface, per VM.PBR.001.
    # OpenPBR only. An MDL surface was accepted here while content moved across,
    # which made a FET_006_OPENPBR pass survivable with no OpenPBR in the asset --
    # so the feature could not answer "does this asset have OpenPBR", which is what
    # a library search off validation metadata needs it to answer. VM.MDL.003 is
    # the same question for MDL, and a profile that wants either lists both.
    physical_surface_terminals = ("outputs:mtlx:surface",)

    # Bounds how far a terminal is followed through nested NodeGraphs. The visited set
    # already stops a cycle; this bounds the pathologically deep case as well.
    max_nodegraph_depth = 16

    def _connected_surface_terminals(self, prim: Usd.Prim):
        """The ``(name, attribute)`` pairs for the surface terminals a Material connects."""
        connected = []
        for name in self.surface_terminals:
            attr = prim.GetAttribute(name)
            if attr and attr.IsAuthored() and attr.GetConnections():
                connected.append((name, attr))
        return connected

    def _terminal_shader(self, prim: Usd.Prim, terminal: str) -> Optional[UsdShade.Shader]:
        """Return the ``UsdShade.Shader`` driving a terminal on a Material, or None.

        A terminal may connect straight to a shader, or to an output on a
        ``UsdShade.NodeGraph`` that connects onward to one. Both are conformant
        UsdShade. Reading only the first shape skipped every material whose surface is
        wrapped in a node graph, which is a shape DCC exporters write, so the
        connection is followed to the shader at the end of it.
        """
        attr = prim.GetAttribute(terminal)
        if not attr or not attr.IsAuthored():
            return None

        stage = prim.GetStage()
        visited = set()
        pending = [(attr, 0)]
        while pending:
            current, depth = pending.pop()
            if depth > self.max_nodegraph_depth:
                continue
            for conn in current.GetConnections() or []:
                source = stage.GetPrimAtPath(conn.GetPrimPath())
                if source is None or not source.IsValid():
                    continue
                if source.IsA(UsdShade.Shader):
                    return UsdShade.Shader(source)
                # UsdShade.Material derives from NodeGraph, so this arm also covers a
                # terminal routed back through the material's own interface.
                if source.IsA(UsdShade.NodeGraph) and conn.IsPropertyPath():
                    key = str(conn)
                    if key in visited:
                        continue
                    visited.add(key)
                    inner = source.GetAttribute(conn.name)
                    if inner:
                        pending.append((inner, depth + 1))
        return None

    def _mtlx_surface_shader(self, prim: Usd.Prim) -> Optional[UsdShade.Shader]:
        """Return the shader driving ``outputs:mtlx:surface`` on a Material, or None."""
        return self._terminal_shader(prim, "outputs:mtlx:surface")

    def check_vm_pbr_001_openpbr_surface(self, stage, prim_path: str) -> List[str]:
        """Check VM.PBR.001: what a renderable GPrim renders with is physically based.

        Driven from the geometry. Every renderable GPrim resolves its binding at the
        ``full`` purpose, and the material that comes back is the one judged. Two
        classes of material therefore fall outside the requirement without needing an
        exception written for them: one that nothing binds, such as an unused entry in
        ``/Looks``, and one bound only through ``material:binding:preview``, since a
        ``full`` computation does not fall back to another purpose.

        VM.MAT.001 owns the other half of the same question -- that a renderable GPrim
        resolves a material at all -- so a GPrim with no material is reported once,
        there, and this stays silent.

        Of the material itself, two things. Presence: it connects an OpenPBR final
        surface on ``outputs:mtlx:surface``. Identity: that terminal is driven by the
        OpenPBR surface node.

        Presence is the point. A feature that a bound material satisfies without having
        the surface the feature is named for cannot answer "does this asset have
        OpenPBR", which is what a library searching validation metadata needs of it.
        ``VM.MDL.003`` asks the same of MDL, and a profile wanting either lists both.

        A Material connecting no surface terminal at all is left to VM.PBR.003, which
        reports it once. Repeating it here would report the same prim under two codes
        for one defect.

        Presence is read off the terminals the material connects rather than off the
        shader the mtlx terminal resolves to, so a broken mtlx terminal stays a single
        VM.PBR.003 dangling-connection finding rather than also being reported here as
        an absent surface.
        """
        errors = []

        prim = stage.GetPrimAtPath(prim_path)
        if not prim:
            return errors
        # The same gate VM.MAT.001 uses, so the two requirements ask about the same
        # geometry: a GPrim whose computed purpose is default or render. Proxies and
        # guides are not rendered, and a GeomSubset is not a GPrim -- it is reached
        # below, through the GPrim that owns it.
        if not UsdGeom.Gprim(prim) or not self._has_default_or_renderable_purpose(prim):
            return errors

        for material in self._bound_materials(prim):
            errors.extend(self._check_final_surface(material))

        return errors

    def _bound_materials(self, prim: Usd.Prim) -> List[UsdShade.Material]:
        """Every distinct material a renderable GPrim resolves at the ``full`` purpose.

        Its own computed material, plus one per material-bind ``GeomSubset``, since a
        mesh may render several materials across its faces and each of them is
        something the asset renders with.
        """
        materials = []
        seen = set()
        candidates = [prim]
        candidates.extend(UsdShade.MaterialBindingAPI(prim).GetMaterialBindSubsets() or [])
        for candidate in candidates:
            material, _ = self._get_material(candidate)
            if not material:
                continue
            path = material.GetPrim().GetPath()
            if path in seen:
                continue
            seen.add(path)
            materials.append(material)
        return materials

    def _check_final_surface(self, material: UsdShade.Material) -> List[str]:
        """Report a bound material that carries no physically based final surface.

        One material is commonly bound to many GPrims, and the defect belongs to the
        material rather than to any one of them, so it is reported once per stage.
        ``CheckStage`` clears the set; the lazy initialisation covers a caller that
        drives ``CheckPrim`` without it.
        """
        errors = []
        prim = material.GetPrim()

        # A friction-only material describes no appearance, so there is no final
        # surface to require of it. The same guard VM.PBR.003 applies.
        if self._is_physics_only_material(prim):
            return errors

        reported = getattr(self, "_pbr_001_reported", None)
        if reported is None:
            reported = self._pbr_001_reported = set()
        prim_path = prim.GetPath()
        if prim_path in reported:
            return errors
        reported.add(prim_path)

        connected = [name for name, _ in self._connected_surface_terminals(prim)]
        if not any(name in self.physical_surface_terminals for name in connected):
            if connected:
                self._AddFailedCheck(
                    message=(
                        f"material '{prim_path}' is bound for rendering but connects no "
                        f"OpenPBR final surface: it connects {', '.join(connected)}, and not "
                        "'outputs:mtlx:surface'"
                    ),
                    at=prim,
                    requirement=cap.MaterialsRequirements.VM_PBR_001,
                )
                errors.append(f"No physically based final surface on {prim_path}")
            return errors

        shader = self._mtlx_surface_shader(prim)
        if shader is None:
            return errors

        shader_id = shader.GetIdAttr().Get() if shader.GetIdAttr() else None
        if shader_id != self.openpbr_surface_id:
            self._AddFailedCheck(
                message=(
                    f"mtlx surface shader on '{prim_path}' is not the OpenPBR surface "
                    f"(info:id={shader_id!r}, expected {self.openpbr_surface_id!r})"
                ),
                at=shader.GetPrim(),
                requirement=cap.MaterialsRequirements.VM_PBR_001,
            )
            errors.append(f"Non-OpenPBR mtlx surface on {prim_path}: {shader_id}")

        return errors

    def check_vm_pbr_002_openpbr_parameter_ranges(self, stage, prim_path: str) -> List[str]:
        """Check VM.PBR.002: OpenPBR surface inputs are within their valid ranges.

        The value is followed to wherever the constant actually lives. Skipping every
        connected input, as this check used to, skipped essentially all of them: the
        conventional way to build one of these materials is to author the values as
        interface inputs on the Material and connect the surface shader's inputs to
        them, so the shader's own inputs carry no constant and the constants sit one
        connection away.

        An input that resolves to a shader output is computed by the graph rather than
        authored, so there is no constant to range check and it is skipped.

        The curated range map is intersected with the live nodedef input names, so a
        name that is not present in the resolved nodedef is skipped rather than reported.
        """
        errors = []

        prim = stage.GetPrimAtPath(prim_path)
        if not prim or prim.GetTypeName() != "Material":
            return errors

        shader = self._mtlx_surface_shader(prim)
        if shader is None:
            return errors
        if (shader.GetIdAttr().Get() if shader.GetIdAttr() else None) != self.openpbr_surface_id:
            return errors

        nodedef = self._nodedef(self.openpbr_surface_id)
        if nodedef is None:
            return errors
        valid_names, _ = nodedef

        unit_floats = self.openpbr_ranges["unit_float"] & valid_names
        ior_floats = self.openpbr_ranges["ior_float"] & valid_names
        non_negative_floats = self.openpbr_ranges["non_negative_float"] & valid_names
        unit_colors = self.openpbr_ranges["unit_color3"] & valid_names

        for shader_input in shader.GetInputs():
            name = shader_input.GetBaseName()
            value = self._resolved_constant(shader_input)
            if value is None:
                continue

            if name in unit_floats or name in ior_floats or name in non_negative_floats:
                components = (value,)
            elif name in unit_colors:
                components = tuple(self._as_rgb(value) or ())
            else:
                continue

            # A non-finite value is not out of range; it is not a number. VM.BIND.002
            # owns finiteness, on every numeric shader input in any format, and reports
            # it once. This requirement owns the range of a finite value, so it steps
            # over a non-finite one rather than adding a second finding that would read
            # "expected 0..1, got nan".
            if any(self._is_non_finite(component) for component in components):
                continue

            if name in unit_floats:
                number = self._as_float(value)
                if number is not None and not 0.0 <= number <= 1.0:
                    self._report_range(shader, name, f"{number} is outside [0, 1]", errors)
            elif name in ior_floats:
                number = self._as_float(value)
                if number is not None and not self.ior_min <= number <= self.ior_max:
                    self._report_range(
                        shader, name, f"{number} is outside [{self.ior_min:g}, {self.ior_max:g}]", errors
                    )
            elif name in non_negative_floats:
                number = self._as_float(value)
                if number is not None and number < 0.0:
                    self._report_range(shader, name, f"{number} is below 0", errors)
            elif name in unit_colors:
                for component in self._as_rgb(value) or ():
                    number = self._as_float(component)
                    if number is not None and not 0.0 <= number <= 1.0:
                        self._report_range(shader, name, f"component {number} is outside [0, 1]", errors)

        return errors

    @staticmethod
    def _resolved_constant_source(shader_input: UsdShade.Input):
        """``(value, source attribute)`` for the constant a shader input resolves to.

        An unconnected input carries its own value, and is its own source. A connected
        one is followed to the attributes that actually produce the value, which for the
        usual authoring shape is an interface input on the enclosing Material.

        ``GetValueProducingAttributes`` walks the whole chain, including through node
        graph interfaces, and returns what USD itself would read. Only an *input*
        attribute at the end of that chain holds an authored constant; an *output* is
        computed by a node and has none, so it yields None and the caller skips it.

        The source attribute comes back with the value so a report can name where the
        constant was authored, which for a connected input is a different prim from the
        one the finding is attached to.
        """
        if not shader_input.HasConnectedSource():
            return shader_input.Get(), shader_input.GetAttr()

        try:
            produced = shader_input.GetValueProducingAttributes()
        except Exception:
            return None, None

        for attr in produced or []:
            try:
                _, attribute_type = UsdShade.Utils.GetBaseNameAndType(attr.GetName())
            except Exception:
                continue
            if attribute_type != UsdShade.AttributeType.Input:
                continue
            value = attr.Get()
            if value is not None:
                return value, attr
        return None, None

    @classmethod
    def _resolved_constant(cls, shader_input: UsdShade.Input):
        """The constant a shader input resolves to, or None where there is not one."""
        return cls._resolved_constant_source(shader_input)[0]

    def _report_range(self, shader: UsdShade.Shader, name: str, detail: str, errors: List[str]) -> None:
        self._AddFailedCheck(
            message=f"OpenPBR input '{name}' on '{shader.GetPrim().GetPath()}': {detail}",
            at=shader.GetPrim(),
            requirement=cap.MaterialsRequirements.VM_PBR_002,
        )
        errors.append(f"Out-of-range OpenPBR input {name}: {detail}")

    @classmethod
    def _is_non_finite(cls, component) -> bool:
        """True for a NaN or an Inf. A value that is not a number at all is not one."""
        number = cls._as_number(component)
        return number is not None and not math.isfinite(number)

    def check_vm_pbr_003_materialx_graph_structure(self, stage, prim_path: str) -> List[str]:
        """Check VM.PBR.003: the material's shading network is structurally sound.

        Covers shader ids that resolve, connections whose source exists, authored input
        types that match the nodedef, and an authored, connected surface terminal.
        """
        errors = []

        prim = stage.GetPrimAtPath(prim_path)
        if not prim or prim.GetTypeName() != "Material":
            return errors
        # A material that carries only friction has no shading network by design, so the
        # surface-terminal rule below would fail a conformant asset on the prims this
        # requirement is least about. A material carrying both a physics schema and a
        # surface is a visual material and is checked in full.
        # VM.PBR.001 and VM.PBR.002 do not need this guard: both skip a material that
        # carries no mtlx surface, which a friction-only material never does.
        if self._is_physics_only_material(prim):
            return errors

        # Shader ids and input types can only be checked against nodedefs that the
        # environment can actually resolve. Where no nodedef source is available,
        # a valid id is indistinguishable from an invalid one, so those two checks are
        # skipped rather than reported. Connection and terminal checks do not need a
        # nodedef and still run.
        nodedefs_available = self._materialx_nodedefs_available()

        for descendant in Usd.PrimRange(prim):
            if not descendant.IsA(UsdShade.Shader):
                continue
            shader = UsdShade.Shader(descendant)
            id_attr = shader.GetIdAttr()
            shader_id = id_attr.Get() if id_attr else None
            node = self._nodedef(shader_id) if shader_id else None

            # An MDL shader names its implementation with info:mdl:sourceAsset and a
            # subIdentifier, so it has nothing to resolve in the MaterialX nodedef registry:
            # its info:id is either absent or an "mdl:"-prefixed token that is not a nodedef
            # name. Judging it against the registry fails every valid OmniPBR material in an
            # environment where MaterialX resolves but MDL Sdr discovery does not. These
            # shaders are covered instead by VM.MDL.001, which resolves the source asset, and
            # VM.BIND.002, which checks input types against the MDL module.
            if (
                node is None
                and nodedefs_available
                and not self._is_mdl_shader(shader)
                and shader_id not in self.known_usd_shader_ids
            ):
                self._AddFailedCheck(
                    message=f"shader info:id {shader_id!r} on '{descendant.GetPath()}' does not resolve to a nodedef",
                    at=descendant,
                    requirement=cap.MaterialsRequirements.VM_PBR_003,
                )
                errors.append(f"Unresolved shader id: {shader_id}")
                continue

            for shader_input in shader.GetInputs():
                name = shader_input.GetBaseName()
                dangling = self._dangling_target(shader_input.GetAttr(), stage)
                if dangling is not None:
                    self._AddFailedCheck(
                        message=(
                            f"input '{name}' on '{descendant.GetPath()}' has a dangling "
                            f"connection to {dangling}"
                        ),
                        at=descendant,
                        requirement=cap.MaterialsRequirements.VM_PBR_003,
                    )
                    errors.append(f"Dangling connection on {name}")

                if node is None or not nodedefs_available:
                    continue
                _, declared_types = node
                expected = declared_types.get(name)
                if expected is None:
                    continue
                actual = shader_input.GetTypeName()
                if expected and actual and expected.type != actual.type:
                    self._AddFailedCheck(
                        message=(
                            f"input '{name}' on '{descendant.GetPath()}' has type {actual}, "
                            f"nodedef declares {expected}"
                        ),
                        at=descendant,
                        requirement=cap.MaterialsRequirements.VM_PBR_003,
                    )
                    errors.append(f"Type mismatch on {name}")

        # A material must connect a surface terminal in at least one render context. Which
        # context is not this requirement's concern: a material may legitimately carry only
        # a universal UsdPreviewSurface, only an OpenPBR surface, or several at once, and
        # the render context selects between them. Whether one of them is physically based,
        # and what an mtlx one must be, are VM.PBR.001's concern, and it checks both.
        connected = self._connected_surface_terminals(prim)

        if not connected:
            self._AddFailedCheck(
                message=f"material '{prim_path}' connects no surface terminal in any render context",
                at=prim,
                requirement=cap.MaterialsRequirements.VM_PBR_003,
            )
            errors.append(f"No connected surface terminal on {prim_path}")
        else:
            for name, attr in connected:
                dangling = self._dangling_target(attr, stage)
                if dangling is not None:
                    self._AddFailedCheck(
                        message=f"'{name}' on '{prim_path}' has a dangling connection to {dangling}",
                        at=prim,
                        requirement=cap.MaterialsRequirements.VM_PBR_003,
                    )
                    errors.append(f"Dangling surface terminal '{name}' on {prim_path}")

        return errors

    @staticmethod
    def _is_physics_only_material(prim) -> bool:
        """Whether this Material carries friction and no appearance at all.

        ``PhysicsMaterialAPI`` and a visual surface are not exclusive. One
        ``UsdShade.Material`` may legitimately carry both, describing appearance
        and friction on the same prim, and a material that does is a visual
        material for this requirement's purposes. Only a material that applies the
        physics schema and authors no surface output in any render context is out
        of scope: it has no shading network, and that is correct rather than a
        defect.

        An authored surface output counts even when it is not connected, since a
        material that declares one is claiming to be visual and a broken terminal
        is exactly what this requirement is for.

        Keyed on the applied schema rather than a path convention. The sample
        assets group these under a ``PhysicsMaterials`` scope, but nothing
        requires that name and matching on it would miss any asset that organises
        its materials differently.
        """
        if "PhysicsMaterialAPI" not in prim.GetAppliedSchemas():
            return False
        for name in ("outputs:surface", "outputs:mtlx:surface", "outputs:mdl:surface"):
            attr = prim.GetAttribute(name)
            if attr and attr.IsAuthored():
                return False
        return True

    @staticmethod
    def _is_mdl_shader(shader: UsdShade.Shader) -> bool:
        """Whether this shader is implemented by an MDL source asset rather than a registry id.

        ``UsdShade`` states this on the shader itself: an implementation source of
        ``sourceAsset`` means the node is defined by the asset named in
        ``info:mdl:sourceAsset``, not by a name looked up in ``Sdr``. This is the same
        discriminator VM.MDL.001 already uses.

        The ``info:id`` cannot serve as the test. Sample content authors both shapes
        alongside a source asset: absent, and an ``mdl:``-prefixed token such as
        ``mdl:OmniPBR``. Neither is a nodedef name, and an allowlist of the tokens would
        cover only the second shape and go stale as MDL modules are added.
        """
        prim = shader.GetPrim()
        try:
            if shader.GetImplementationSourceAttr().Get() == UsdShade.Tokens.sourceAsset:
                return True
        except Exception:
            pass
        return bool(prim.GetAttribute("info:mdl:sourceAsset"))

    @staticmethod
    def _shader_registry():
        """Return the Sdr registry, or None where it cannot be constructed.

        Some USD builds raise when the shader definition resources are absent, so the
        registry is treated as unavailable rather than allowed to abort validation.
        """
        try:
            return Sdr.Registry()
        except Exception:
            return None

    # MaterialX input type strings mapped to the Sdf types Sdr reports for the same
    # nodedef. Verified elementwise against Sdr on the OpenPBR surface nodedef in an
    # environment where both sources resolve: all 41 inputs agree, none disagree.
    # "lightshader" and "material" have no Sdf equivalent and are deliberately absent;
    # an unmapped type yields None and the input's type is not judged.
    mtlx_type_to_sdf = {
        "boolean": Sdf.ValueTypeNames.Bool,
        "integer": Sdf.ValueTypeNames.Int,
        "float": Sdf.ValueTypeNames.Float,
        "string": Sdf.ValueTypeNames.String,
        "filename": Sdf.ValueTypeNames.Asset,
        "color3": Sdf.ValueTypeNames.Color3f,
        "color4": Sdf.ValueTypeNames.Color4f,
        "vector2": Sdf.ValueTypeNames.Float2,
        "vector3": Sdf.ValueTypeNames.Float3,
        "vector4": Sdf.ValueTypeNames.Float4,
        "matrix33": Sdf.ValueTypeNames.Matrix3d,
        "matrix44": Sdf.ValueTypeNames.Matrix4d,
        "surfaceshader": Sdf.ValueTypeNames.Token,
        "displacementshader": Sdf.ValueTypeNames.Token,
        "volumeshader": Sdf.ValueTypeNames.Token,
        "BSDF": Sdf.ValueTypeNames.Token,
        "EDF": Sdf.ValueTypeNames.Token,
        "VDF": Sdf.ValueTypeNames.Token,
    }

    # Minimum MaterialX the nodedef names in these requirements are written against.
    # 1.39 renamed some nodedefs -- ND_normalmap became ND_normalmap_float -- so an
    # older library would fail to resolve ids that are correct.
    mtlx_minimum_version = (1, 39)

    _mtlx_document = None
    _mtlx_document_loaded = False
    _nodedef_cache = {}

    @classmethod
    def _materialx_document(cls):
        """The MaterialX standard library, or None where MaterialX is unavailable.

        The ``MaterialX`` Python wheel ships the whole standard library, so nodedefs
        resolve from it without USD's ``usdMtlx`` plugin. That matters because the plugin
        is absent from a plain ``pip install usd-core``, which is what this repo's own
        requirements produce and what CI runs, so ``Sdr`` resolves no ``ND_*`` identifier
        there and every OpenPBR requirement silently skipped.
        """
        if cls._mtlx_document_loaded:
            return cls._mtlx_document
        cls._mtlx_document_loaded = True
        try:
            import MaterialX as mx

            version = tuple(int(p) for p in mx.getVersionString().split(".")[:2])
            if version < cls.mtlx_minimum_version:
                return cls._mtlx_document

            document = mx.createDocument()
            mx.loadLibraries(
                ["libraries"],
                mx.FileSearchPath(os.path.dirname(mx.__file__)),
                document,
            )
            cls._mtlx_document = document
        except Exception:
            cls._mtlx_document = None
        return cls._mtlx_document

    @classmethod
    def _nodedef(cls, identifier: str):
        """Resolve a shader identifier to its declared inputs.

        Returns a ``(names, types)`` pair, where ``names`` is the set of declared input
        names and ``types`` maps a name to its ``Sdf`` type, or None where the identifier
        does not resolve in this environment.

        Two sources, in order. ``Sdr`` first, so an environment carrying ``usdMtlx`` or
        MDL discovery keeps behaving exactly as it did. MaterialX second, so an
        environment without them still resolves ``ND_*`` nodedefs instead of skipping
        every check that needs one.
        """
        if identifier in cls._nodedef_cache:
            return cls._nodedef_cache[identifier]

        result = None

        registry = cls._shader_registry()
        if registry is not None:
            try:
                node = registry.GetShaderNodeByIdentifier(identifier)
            except Exception:
                node = None
            if node is not None:
                names = set(node.GetShaderInputNames())
                types = {}
                for name in names:
                    declared = cls._sdr_node_input(node, name)
                    if declared is None:
                        continue
                    types[name] = cls._sdr_property_sdf_type(declared)
                result = (names, types)

        if result is None:
            document = cls._materialx_document()
            if document is not None:
                try:
                    nodedef = document.getNodeDef(identifier)
                except Exception:
                    nodedef = None
                if nodedef is not None:
                    names = set()
                    types = {}
                    for declared in nodedef.getActiveInputs():
                        name = declared.getName()
                        names.add(name)
                        types[name] = cls.mtlx_type_to_sdf.get(declared.getType())
                    result = (names, types)

        cls._nodedef_cache[identifier] = result
        return result

    def _materialx_nodedefs_available(self) -> bool:
        """True when MaterialX nodedefs resolve in this environment.

        Probed with the OpenPBR surface id. Where neither source can resolve it, an
        unresolvable id says nothing about the asset and the id and type checks are
        skipped.
        """
        return self._nodedef(self.openpbr_surface_id) is not None

    def _dangling_target(self, attr, stage) -> Optional[str]:
        """Return an authored connection target that does not resolve, or None.

        A connection to a missing prim or output is dropped from ``GetConnectedSources()``,
        so the authored targets are read directly off the attribute.
        """
        try:
            connections = attr.GetConnections()
        except Exception:
            return None
        for conn in connections or []:
            source = stage.GetPrimAtPath(conn.GetPrimPath())
            if source is None or not source.IsValid():
                return str(conn)
            if conn.IsPropertyPath() and not source.GetAttribute(conn.name):
                return str(conn)
        return None

    @staticmethod
    def _as_number(value) -> Optional[float]:
        """Coerce to float, keeping NaN and Inf. None where the value is not a number."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_float(value) -> Optional[float]:
        """Coerce to a finite float. None for a non-number or a non-finite one.

        Callers use this for range comparisons, which a non-finite value would silently
        pass. VM.PBR.002 steps over a non-finite value before it gets here, and
        VM.BIND.002 reports it; folding it into None keeps a comparison from acting on
        one either way.
        """
        number = VisualMaterialsCapabilityChecker._as_number(value)
        return number if number is not None and math.isfinite(number) else None

    @staticmethod
    def _as_rgb(value):
        try:
            return (value[0], value[1], value[2])
        except (TypeError, IndexError, KeyError):
            return None

    def check_vm_mdl_001_material_mdl_source_asset(self, stage, prim_path: str) -> List[str]:
        """Check VM.MDL.001: MDL material source asset compliance."""
        errors = []

        prim = stage.GetPrimAtPath(prim_path)
        if not prim:
            return errors

        # Check if this is a material with MDL shader
        if prim.GetTypeName() == "Material":
            for child in prim.GetChildren():
                if child.GetTypeName() == "Shader":
                    shader = UsdShade.Shader(child)
                    implementation_source = shader.GetImplementationSourceAttr().Get()

                    if implementation_source == "sourceAsset":
                        errors.extend(self._validate_mdl_source_asset(shader))

        return errors

    def _validate_mdl_source_asset(self, shader: UsdShade.Shader) -> List[str]:
        """Validate MDL source asset attributes."""
        errors = []

        # Check for required MDL source asset attribute
        source_asset_attr = shader.GetPrim().GetAttribute("info:mdl:sourceAsset")
        if not source_asset_attr:
            errors.append("MDL shader missing required 'info:mdl:sourceAsset' attribute")
            self._AddFailedCheck(
                message="MDL shader missing required 'info:mdl:sourceAsset' attribute",
                at=shader.GetPrim(),
                requirement=cap.MaterialsRequirements.VM_MDL_001,
            )
            return errors

        source_asset = source_asset_attr.Get()
        if not source_asset:
            errors.append("MDL source asset path is empty")
            self._AddFailedCheck(
                message="MDL source asset path is empty",
                at=shader.GetPrim(),
                requirement=cap.MaterialsRequirements.VM_MDL_001,
            )
            return errors

        # Check file extension
        source_path = str(source_asset)

        # Remove leading and trailing @ symbols if present
        while source_path.startswith("@") and source_path.endswith("@"):
            source_path = source_path[1:-1]

        if not source_path.endswith(".mdl"):
            errors.append(f"MDL source asset must have .mdl extension: {source_asset}")
            self._AddFailedCheck(
                message=f"MDL source asset must have .mdl extension: {source_asset}",
                at=shader.GetPrim(),
                requirement=cap.MaterialsRequirements.VM_MDL_001,
            )

        # A path that is neither anchored nor absolute is resolved through the MDL search
        # path, so which module it names depends on how the runtime is configured.
        # Absolute paths are not reported here: they resolve deterministically, and
        # AA.001 covers them as a portability matter for every asset reference.
        builtin = is_builtin_mdl_module(source_path)
        if not builtin and not source_path.startswith(("./", "../")) and not os.path.isabs(source_path):
            message = (
                f"MDL source asset path '{source_path}' is resolved through the MDL search "
                f"path, so the module it names depends on runtime configuration. Anchor it "
                f"with './'"
            )
            errors.append(message)
            self._AddFailedCheck(
                message=message,
                at=shader.GetPrim(),
                requirement=cap.MaterialsRequirements.VM_MDL_001,
            )

        # A built-in module is not in the package and must not be, so there is no file
        # at the authored path to find and nothing for the existence check to say.
        if builtin:
            return errors

        # Check if the MDL file exists
        stage = shader.GetPrim().GetStage()
        mdl_path = source_asset.resolvedPath
        if not mdl_path and omni:
            mdl_path = omni.client.combine_urls(stage.GetRootLayer().identifier, source_asset.path)
        elif not mdl_path:
            mdl_path = source_asset.path

        mdl_path = mdl_path.replace("\\", "/")

        # Check if file exists (with caching)
        file_exists = False
        if mdl_path in self._cache_existing_filepaths:
            file_exists = True
        else:
            if omni:
                # Use omni.client for file checking
                result, _ = omni.client.stat(mdl_path)
                if result == omni.client.Result.OK:
                    file_exists = True
                    self._cache_existing_filepaths.add(mdl_path)
            else:
                # Fallback to os.path.exists for local files
                if os.path.exists(mdl_path):
                    file_exists = True
                    self._cache_existing_filepaths.add(mdl_path)

        if not file_exists:
            errors.append(f"MDL source asset file does not exist: {mdl_path}")
            self._AddFailedCheck(
                message=f"MDL source asset file does not exist: {mdl_path}",
                at=shader.GetPrim(),
                requirement=cap.MaterialsRequirements.VM_MDL_001,
            )

        return errors

    def _canonical_colorspace(self, color_space) -> Optional[str]:
        """Return the ``Gf.ColorSpaceNames`` name for an authored color space.

        None where the name states no expectation ("auto") or is not a color space
        this requirement recognises; the caller distinguishes the two.
        """
        name = str(color_space)
        if name in self.colorspace_defer:
            return None
        if name in self.colorspace_aliases:
            return self.colorspace_aliases[name]
        if Gf.ColorSpace.IsValid(name):
            return name
        return None

    @classmethod
    def _colorspace_repair_token(cls, is_color: bool) -> str:
        """The token a repair writes for a color texture or for a data one."""
        return cls.colorspace_repair_srgb if is_color else cls.colorspace_repair_linear

    def check_vm_tex_002_colorspace(self, stage, prim_path: str) -> List[str]:
        """Check VM.TEX.002, frozen at the behaviour FET_006_MDL 0.1.0 shipped with.

        Authored values only. An input that authors no color space is not examined,
        which is what this requirement did when 0.1.0 was released. VM.TEX.005 covers
        the same authored values and adds the unauthored case.
        """
        return self._check_mdl_colorspace(
            stage, prim_path, cap.MaterialsRequirements.VM_TEX_002, unauthored=False
        )

    def check_vm_tex_005_colorspace(self, stage, prim_path: str) -> List[str]:
        """Check VM.TEX.005: the current MDL color space requirement.

        The authored values VM.TEX.002 covers, plus the input that authors nothing and
        so resolves to ``auto``, which decodes an 8-bit three- or four-channel file as
        sRGB and is wrong on a data input.
        """
        return self._check_mdl_colorspace(
            stage, prim_path, cap.MaterialsRequirements.VM_TEX_005, unauthored=True
        )

    def _check_mdl_colorspace(self, stage, prim_path: str, requirement, unauthored: bool) -> List[str]:
        """Check VM.TEX.002: MDL texture inputs carry the color space their signal needs.

        Scoped to texture inputs on MDL shaders, which is the scope the requirement
        page states. The expectation is decided from the shader input's name against a
        list of MDL and OmniPBR color-texture names, so it is only meaningful for
        shaders using those names: in MDL the input name *is* the signal, and
        ``diffuse_texture`` says what ``normalmap_texture`` does not.

        UsdPreviewSurface and MaterialX are VM.TEX.003's, because their image nodes all
        read through one input called ``file`` and the name carries nothing. That is a
        different traversal rather than this one with a flag.

        Applying this to any attribute that happens to carry color-space metadata
        reported conformant data as wrong: a ``primvars:displayColor`` on a Mesh is not
        a texture input and has no business being judged against a texture input's
        expectation.
        """
        errors = []

        prim = stage.GetPrimAtPath(prim_path)
        if not prim or not prim.IsA(UsdShade.Shader):
            return errors

        # Format gate. The name-driven expectation below only describes MDL and OmniPBR
        # inputs, so a MaterialX image node or UsdUVTexture feeding a color signal
        # through inputs:file would be reported as wrong for correctly carrying sRGB.
        if not self._is_mdl_shader(UsdShade.Shader(prim)):
            return errors

        for attr in prim.GetAttributes():
            attr_name = attr.GetName()
            # Only texture inputs: an asset-valued shader input. This excludes outputs,
            # non-input metadata carriers, and any non-asset input.
            if not attr_name.startswith("inputs:"):
                continue
            if attr.GetTypeName() != Sdf.ValueTypeNames.Asset:
                continue
            if not attr.Get():
                continue

            is_color = attr_name in self.colorspace_srgb_list

            # The name says which signal the input carries, so the value a repair should
            # write is settled here, before anything is read off the attribute. The one
            # finding below that does not take it is the unrecognised-token one: there
            # the authored value states an intent nothing can read, and overwriting it
            # would be a guess rather than a repair.
            repair_token = self._colorspace_repair_token(is_color)
            suggestion = Suggestion(
                message=f"Set the 'colorSpace' metadata on '{attr_name}' to '{repair_token}'.",
                callable=partial(
                    self._repair_mdl_colorspace, attr_name=attr_name, token=repair_token
                ),
                at=[prim],
            )

            # An unauthored color space resolves to 'auto', so the two are one case.
            # 'auto' decodes a file with three or four channels, which is wrong on a
            # data input and right on a color one.
            authored = str(attr.GetColorSpace()) if attr.HasColorSpace() else None
            if authored is None or authored in self.colorspace_defer:
                if not unauthored:
                    continue
                if is_color or self._is_single_channel_asset(attr) is not False:
                    continue
                self._AddFailedCheck(
                    message=(
                        f"Attribute '{attr_name}' carries data and leaves the color space "
                        f"to '{authored or 'auto'}'. The file has three or more channels, "
                        f"so 'auto' decodes it as sRGB; declare 'raw'"
                    ),
                    at=prim,
                    requirement=requirement,
                    suggestion=suggestion,
                )
                errors.append(f"'auto' on multi-channel data texture {attr_name}")
                continue

            actual = self._canonical_colorspace(authored)
            if actual is None:
                self._AddFailedCheck(
                    message=(
                        f"Attribute '{attr_name}' has color space '{authored}', which is not a "
                        "Gf.ColorSpaceNames name or a recognised alias of one"
                    ),
                    at=prim,
                    requirement=requirement,
                )
                errors.append(f"Unrecognised color space for {attr_name}: {authored}")
                continue

            if attr_name in self.colorspace_srgb_list:
                expected = self.colorspace_srgb_canonical
            else:
                expected = self.colorspace_linear_canonical

            if actual != expected:
                self._AddFailedCheck(
                    message=(
                        f"Attribute '{attr_name}' has color space '{authored}' ({actual}), "
                        f"expected '{expected}'"
                    ),
                    at=prim,
                    requirement=requirement,
                    suggestion=suggestion,
                )
                errors.append(f"Incorrect color space for {attr_name}: {actual} (expected {expected})")

        return errors

    def _repair_mdl_colorspace(self, _: Usd.Stage, prim: Usd.Prim, attr_name: str, token: str) -> None:
        """Declare the color space VM.TEX.002 expects on one MDL texture input.

        MDL has no separate texture node, so the metadata belongs on the shader's own
        asset attribute, which is where the check read it from.
        """
        prim.GetAttribute(attr_name).SetColorSpace(token)

    # ------------------------------------------------------------------
    # Traced texture color space (VM.TEX.003)
    # ------------------------------------------------------------------
    # The surface terminals VM.TEX.003 traces from, and the surface shader each one is
    # expected to carry. MDL is absent on purpose: its texture inputs are named for the
    # signal they carry, so VM.TEX.002 reads the name and needs no traversal.
    traced_surface_terminals = ("outputs:surface", "outputs:mtlx:surface")

    # Which requirement owns each traced terminal. The traversal is shared; the
    # vocabulary, the default and the failure mode are not, so the findings are raised
    # against different requirements.
    traced_terminal_requirements = {
        "outputs:surface": "VM_TEX_003",
        "outputs:mtlx:surface": "VM_TEX_004",
    }

    # Surface inputs that carry a color signal, so a texture reaching one is expected to
    # be sRGB-encoded. Every other input on these surfaces carries data and expects raw.
    #
    # UsdPreviewSurface's are the three color3f inputs its specification declares. The
    # OpenPBR set is the ``unit_color3`` group VM.PBR.002 already curates, reused here so
    # the two requirements cannot drift on what counts as a color.
    preview_surface_color_inputs = frozenset({"diffuseColor", "emissiveColor", "specularColor"})

    # How far a texture connection is followed back from a surface input, through math
    # nodes and node graphs. The visited set stops a cycle; this bounds a deep chain.
    max_texture_trace_depth = 16

    @classmethod
    def _traced_color_inputs(cls) -> frozenset:
        """The surface input names VM.TEX.003 expects an sRGB texture on."""
        return cls.preview_surface_color_inputs | frozenset(cls.openpbr_ranges["unit_color3"])

    @staticmethod
    def _texture_file_input(shader: UsdShade.Shader):
        """The ``inputs:file`` attribute of an image-reading shader, or None.

        This is what a texture reader has in common across the formats VM.TEX.003
        covers, and it is the only thing they have in common: ``UsdUVTexture`` and every
        MaterialX ``ND_image_*`` node read through an asset-valued input called
        ``file``. Testing for the input rather than for a list of shader ids means a
        MaterialX image node of a type this file has never heard of is still traced.
        """
        attr = shader.GetPrim().GetAttribute("inputs:file")
        if attr and attr.GetTypeName() == Sdf.ValueTypeNames.Asset:
            return attr
        return None

    def _traced_texture_readers(self, shader_input) -> List[UsdShade.Shader]:
        """Every image-reading shader reachable backwards from one surface input.

        A texture rarely connects straight to the surface. It goes through a normal-map
        node, a multiply, a color correct, or a node graph's interface, and the
        expectation still belongs to whichever surface input the chain ends at. So the
        chain is walked rather than the first hop read.
        """
        attr = shader_input.GetAttr()
        if not attr:
            return []
        stage = attr.GetPrim().GetStage()
        readers = []
        found = set()
        visited = set()
        pending = [(attr, 0)]
        while pending:
            current, depth = pending.pop()
            if depth > self.max_texture_trace_depth:
                continue
            for conn in current.GetConnections() or []:
                key = str(conn)
                if key in visited:
                    continue
                visited.add(key)
                source = stage.GetPrimAtPath(conn.GetPrimPath())
                if source is None or not source.IsValid():
                    continue
                if source.IsA(UsdShade.Shader):
                    shader = UsdShade.Shader(source)
                    if self._texture_file_input(shader) is not None:
                        path = source.GetPath()
                        if path not in found:
                            found.add(path)
                            readers.append(shader)
                        continue
                    # Not an image node, so keep going back through its own inputs.
                    for upstream in shader.GetInputs():
                        pending.append((upstream.GetAttr(), depth + 1))
                    continue
                # A NodeGraph or the Material's own interface: follow the named property.
                if source.IsA(UsdShade.NodeGraph) and conn.IsPropertyPath():
                    inner = source.GetAttribute(conn.name)
                    if inner:
                        pending.append((inner, depth + 1))
        return readers

    def _authored_texture_colorspace(self, reader: UsdShade.Shader):
        """``(authored name, where)`` for a texture reader's color space, or ``(None, None)``.

        The two formats write the same fact in two places. ``UsdUVTexture`` declares an
        ``inputs:sourceColorSpace`` token; a MaterialX image node carries ``colorSpace``
        metadata on ``inputs:file``. The typed attribute is read first where both are
        present, since it is the one USD's own reader consults.

        Where ``inputs:file`` is connected the metadata is read from the attribute that
        actually supplies the path. The shipped OpenPBR content authors its image nodes
        that way -- ``inputs:file`` connects to an asset-valued interface input on the
        enclosing ``Material``, and the ``colorSpace`` sits on the interface input --
        so reading only the shader's own attribute would find nothing on any of it and
        report a clean result for a material that had never been looked at.
        """
        source_color_space = reader.GetInput("sourceColorSpace")
        if source_color_space and source_color_space.GetAttr().IsAuthored():
            value = source_color_space.Get()
            if value is not None:
                return str(value), "inputs:sourceColorSpace"

        file_attr = self._texture_file_input(reader)
        if file_attr is None:
            return None, None
        if file_attr.HasColorSpace():
            return str(file_attr.GetColorSpace()), "colorSpace metadata on inputs:file"

        file_input = UsdShade.Input(file_attr)
        if file_input and file_input.HasConnectedSource():
            try:
                produced = file_input.GetValueProducingAttributes()
            except Exception:
                produced = []
            for attr in produced or []:
                if attr.HasColorSpace():
                    return str(attr.GetColorSpace()), f"colorSpace metadata on {attr.GetName()}"
        return None, None

    def check_vm_tex_003_traced_colorspace(self, stage, prim_path: str) -> List[str]:
        """Check VM.TEX.003: texture color space on UsdPreviewSurface."""
        return self._check_traced_terminal(stage, prim_path, "VM_TEX_003")

    def check_vm_tex_004_openpbr_colorspace(self, stage, prim_path: str) -> List[str]:
        """Check VM.TEX.004: texture color space on an OpenPBR surface."""
        return self._check_traced_terminal(stage, prim_path, "VM_TEX_004")

    def _check_traced_terminal(self, stage, prim_path: str, requirement_name: str) -> List[str]:
        """Trace one surface terminal's textures and judge their color space.

        The expectation is traced rather than read off a name. In MDL an input is called
        ``diffuse_texture`` or ``normalmap_texture``, so the name says which signal it
        carries and VM.TEX.002 looks the expectation up. In MaterialX and in
        ``UsdUVTexture`` every image node reads through an input called ``file``, so the
        name says nothing; the only thing that says whether a texture is color or data
        is which surface input it ends up driving. So the walk starts at the surface and
        goes backwards.

        The two surfaces differ in what the color inputs are called (``diffuseColor``
        against ``base_color``), where the color space is written (an
        ``inputs:sourceColorSpace`` attribute against ``colorSpace`` metadata), and which
        vocabulary the value is read in. The traversal is the same, so it lives here and
        the two requirements differ only in how the value is judged.

        A texture that no surface input reaches states nothing either requirement has an
        expectation about.
        """
        errors = []

        prim = stage.GetPrimAtPath(prim_path)
        if not prim or prim.GetTypeName() != "Material":
            return errors

        color_inputs = self._traced_color_inputs()

        # (texture prim path, expected color space) -> (reader, surface, [input names]).
        # An ORM map reaches both ``roughness`` and ``metallic``, and both want the same
        # encoding, so it is one finding naming both rather than two saying the same
        # thing. A texture reaching a color input *and* a data one keys twice, which is
        # the case worth hearing about separately.
        demands = {}
        for terminal in self.traced_surface_terminals:
            if self.traced_terminal_requirements.get(terminal) != requirement_name:
                continue
            surface = self._terminal_shader(prim, terminal)
            if surface is None:
                continue
            # An MDL shader driving one of these terminals is VM.TEX.002's, by name.
            if self._is_mdl_shader(surface):
                continue

            for surface_input in surface.GetInputs():
                name = surface_input.GetBaseName()
                is_color = name in color_inputs
                expected = (
                    self.colorspace_srgb_canonical
                    if is_color
                    else self.colorspace_linear_canonical
                )
                for reader in self._traced_texture_readers(surface_input):
                    key = (reader.GetPrim().GetPath(), expected)
                    entry = demands.setdefault(key, (reader, surface, [], is_color))
                    if name not in entry[2]:
                        entry[2].append(name)

        # A texture that keys twice reaches a color input and a data one, so the two
        # demands ask for different encodings and no single value satisfies both. Those
        # findings stand as they are but carry no repair: writing what either demand
        # asks for would break the other.
        expectations = {}
        for path, expected in demands:
            expectations.setdefault(path, set()).add(expected)
        contested = {path for path, seen in expectations.items() if len(seen) > 1}

        for (path, expected), (reader, surface, names, is_color) in sorted(
            demands.items(), key=lambda item: (str(item[0][0]), item[0][1])
        ):
            if requirement_name == "VM_TEX_004":
                errors.extend(self._check_openpbr_colorspace(reader, surface, names, is_color))
            else:
                errors.extend(
                    self._check_traced_colorspace(
                        reader, surface, names, expected, is_color, path not in contested
                    )
                )

        return errors

    def _check_traced_colorspace(
        self,
        reader: UsdShade.Shader,
        surface: UsdShade.Shader,
        surface_inputs: List[str],
        expected: str,
        is_color: bool = True,
        repairable: bool = True,
    ) -> List[str]:
        """Compare one texture reader's authored color space against one expectation.

        ``repairable`` is False where a second surface input demands the other encoding
        of the same texture, which is the one case the expectation does not settle.
        """
        errors = []
        authored, where = self._authored_texture_colorspace(reader)

        # The expectation says what the texture should carry whatever it carries now, so
        # the repair is the same for every finding below but one. The exception is the
        # unrecognised-token finding: there the authored value states an intent nothing
        # can read, and it sits in colorSpace metadata that a write to
        # inputs:sourceColorSpace would shadow rather than correct.
        suggestion = None
        if repairable:
            repair_token = self._colorspace_repair_token(is_color)
            suggestion = Suggestion(
                message=f"Set 'inputs:sourceColorSpace' to '{repair_token}'.",
                callable=partial(self._repair_preview_colorspace, token=repair_token),
                at=[reader.GetPrim()],
            )

        # An unauthored color space resolves to the attribute's own default, which is
        # ``auto``, so the two are the same case.
        if authored is None or authored in self.colorspace_defer:
            if is_color or self._is_single_channel_texture(reader) is not False:
                return errors
            authored = authored or "auto"
            where = where or "unauthored, defaults to 'auto'"
            reader_path = reader.GetPrim().GetPath()
            reached = ", ".join(f"'{name}'" for name in surface_inputs)
            self._AddFailedCheck(
                message=(
                    f"Texture '{reader_path}' feeds {reached} on "
                    f"'{surface.GetPrim().GetPath()}' and leaves the color space to "
                    f"'{authored}'. The file has three or more channels, so 'auto' "
                    f"decodes it as sRGB; a data texture must declare 'raw'"
                ),
                at=reader.GetPrim(),
                requirement=cap.MaterialsRequirements.VM_TEX_003,
                suggestion=suggestion,
            )
            errors.append(f"'auto' on multi-channel data texture {reader_path}")
            return errors

        reader_path = reader.GetPrim().GetPath()
        if where == "inputs:sourceColorSpace" and authored not in self.source_color_space_values:
            self._AddFailedCheck(
                message=(
                    f"Texture '{reader_path}' declares 'inputs:sourceColorSpace = "
                    f"\"{authored}\"'. That attribute takes "
                    f"{', '.join(repr(v) for v in sorted(self.source_color_space_values))} "
                    f"and no other value"
                ),
                at=reader.GetPrim(),
                requirement=cap.MaterialsRequirements.VM_TEX_003,
                suggestion=suggestion,
            )
            errors.append(f"Illegal sourceColorSpace on {reader_path}: {authored}")
            return errors

        actual = self._canonical_colorspace(authored)
        if actual is None:
            self._AddFailedCheck(
                message=(
                    f"Texture '{reader_path}' declares color space '{authored}' ({where}), "
                    "which is not a Gf.ColorSpaceNames name or a recognised alias of one"
                ),
                at=reader.GetPrim(),
                requirement=cap.MaterialsRequirements.VM_TEX_003,
            )
            errors.append(f"Unrecognised color space for {reader_path}: {authored}")
            return errors

        if actual != expected:
            reached = ", ".join(f"'{name}'" for name in surface_inputs)
            self._AddFailedCheck(
                message=(
                    f"Texture '{reader_path}' feeds {reached} on "
                    f"'{surface.GetPrim().GetPath()}' and has color space '{authored}' "
                    f"({actual}), expected '{expected}'"
                ),
                at=reader.GetPrim(),
                requirement=cap.MaterialsRequirements.VM_TEX_003,
                suggestion=suggestion,
            )
            errors.append(
                f"Incorrect color space for {reader_path} feeding {reached}: "
                f"{actual} (expected {expected})"
            )

        return errors

    def _repair_preview_colorspace(self, _: Usd.Stage, prim: Usd.Prim, token: str) -> None:
        """Declare the color space VM.TEX.003 expects on one texture reader.

        The value follows the surface input the texture drives, which is how the check
        arrived at the expectation, so the repaired texture passes it. It is written to
        ``inputs:sourceColorSpace`` even where the reported value came from ``colorSpace``
        metadata, because the typed attribute is the one USD's own reader consults and so
        the one that decides the decode.
        """
        UsdShade.Shader(prim).CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set(token)

    def _is_single_channel_asset(self, attr):
        """True/False if the asset's channel count is known, None if it is not."""
        asset = attr.Get()
        if not asset:
            return None
        path = getattr(asset, "resolvedPath", "") or getattr(asset, "path", "")
        if not path or not os.path.exists(path):
            return None
        try:
            from PIL import Image
        except ImportError:
            return None
        try:
            with self._image_size_guard_lifted(Image), Image.open(path) as img:
                return img.mode in self.single_channel_pil_modes
        except Exception:
            return None

    def _is_single_channel_texture(self, reader: UsdShade.Shader):
        """True/False if the texture's channel count is known, None if it is not.

        ``auto`` decodes a file with three or four channels and leaves anything else
        alone, so whether it is safe on a data input depends on the file. Without Pillow
        the answer is unknown and the caller defers rather than guessing.
        """
        file_attr = self._texture_file_input(reader)
        if file_attr is None:
            return None
        asset = file_attr.Get()
        if not asset:
            return None
        path = getattr(asset, "resolvedPath", "") or getattr(asset, "path", "")
        if not path or not os.path.exists(path):
            return None
        try:
            from PIL import Image
        except ImportError:
            return None
        try:
            with self._image_size_guard_lifted(Image), Image.open(path) as img:
                return img.mode in self.single_channel_pil_modes
        except Exception:
            return None

    def _check_openpbr_colorspace(
        self, reader: UsdShade.Shader, surface: UsdShade.Shader, surface_inputs: List[str], is_color: bool
    ) -> List[str]:
        """Judge one OpenPBR texture's color space in MaterialX's own vocabulary.

        The tokens are compared literally. ``srgb_texture`` and ``srgb_rec709_scene``
        denote the same encoding, but the MaterialX versions the target runtimes ship
        resolve only the first, so treating them as equivalent would pass a texture that
        renders undecoded.
        """
        errors = []
        authored, where = self._authored_texture_colorspace(reader)
        reader_path = reader.GetPrim().GetPath()
        reached = ", ".join(f"'{name}'" for name in surface_inputs)
        surface_path = surface.GetPrim().GetPath()

        if is_color:
            if authored == self.openpbr_colorspace_srgb:
                return errors
            if authored == self.openpbr_colorspace_srgb_unresolved:
                self._AddWarning(
                    message=(
                        f"Texture '{reader_path}' feeds {reached} on '{surface_path}' and "
                        f"declares '{authored}' ({where}). That is OpenUSD's name for the "
                        f"encoding MaterialX calls '{self.openpbr_colorspace_srgb}'. The "
                        f"MaterialX versions the target runtimes ship do not resolve it, so "
                        f"the texture is consumed undecoded; author "
                        f"'{self.openpbr_colorspace_srgb}'"
                    ),
                    at=reader.GetPrim(),
                )
                errors.append(f"Unresolved sRGB spelling on {reader_path}: {authored}")
                return errors
            declared = f"'{authored}' ({where})" if authored is not None else "no color space"
            self._AddFailedCheck(
                message=(
                    f"Texture '{reader_path}' feeds {reached} on '{surface_path}' and has "
                    f"{declared}, expected '{self.openpbr_colorspace_srgb}'. Without it the "
                    f"texture is consumed undecoded"
                ),
                at=reader.GetPrim(),
                requirement=cap.MaterialsRequirements.VM_TEX_004,
            )
            errors.append(f"Incorrect color space for {reader_path} feeding {reached}")
            return errors

        # Data input: no transform is what is wanted, so an absent color space and the
        # two tokens that state it explicitly all pass.
        if authored is None or authored in self.openpbr_colorspace_data:
            return errors
        self._AddFailedCheck(
            message=(
                f"Texture '{reader_path}' feeds {reached} on '{surface_path}' and declares "
                f"'{authored}' ({where}). Those inputs carry data, which must not be "
                f"decoded; declare 'none' or no color space at all"
            ),
            at=reader.GetPrim(),
            requirement=cap.MaterialsRequirements.VM_TEX_004,
        )
        errors.append(f"Color space on data texture {reader_path}: {authored}")
        return errors

    @staticmethod
    def _sdr_node_for_shader(shader_prim: UsdShade.Shader):
        """Resolve a non-MDL shader to its Sdr node, or None.

        This branch receives shaders selected for *not* being MDL, so asking for the
        "mdl" source type could only ever return None and the check never ran on any
        shader it was given.

        There is no single correct source type to ask for instead. A shader whose
        implementation source is "id" -- which is every non-MDL shader in the sample
        content: UsdPreviewSurface, UsdUVTexture, UsdPrimvarReader_*, UsdTransform2d --
        declares no source types at all, since source types describe sourceAsset and
        sourceCode implementations. Its definition is found by resolving info:id in the
        registry, which is source-type agnostic.

        So: use whatever source types the shader actually declares, and fall back to
        resolving info:id by identifier for the "id" implementations that declare none.
        """
        try:
            for source_type in shader_prim.GetSourceTypes() or []:
                node = shader_prim.GetShaderNodeForSourceType(source_type)
                if node:
                    return node
        except Exception:
            pass

        try:
            id_attr = shader_prim.GetIdAttr()
            shader_id = id_attr.Get() if id_attr else None
            if not shader_id:
                return None
            registry = VisualMaterialsCapabilityChecker._shader_registry()
            if registry is None:
                return None
            return registry.GetShaderNodeByIdentifier(shader_id)
        except Exception:
            return None

    def _shader_definition(self, shader_prim: UsdShade.Shader):
        """Return ``(names, types)`` for a non-MDL shader's definition, or None.

        Sdr first, so an environment carrying ``usdMtlx`` or MDL discovery keeps
        behaving exactly as it did, including the source-type lookup that resolves a
        shader declaring one.

        Where Sdr cannot supply the node, the MaterialX standard library is asked
        instead, through the same ``_nodedef`` the VM.PBR.* requirements use. Sdr
        resolves no ``ND_*`` identifier under a plain ``pip install usd-core``, which
        carries no ``usdMtlx`` plugin and is what this repository's own requirements
        produce, so without this second source the type and NaN/Inf checks below ran
        on no MaterialX shader at all in the environment CI uses.
        """
        node = self._sdr_node_for_shader(shader_prim)
        if node is not None:
            names = set(node.GetShaderInputNames())
            types = {}
            for name in names:
                declared = self._sdr_node_input(node, name)
                if declared is None:
                    continue
                types[name] = self._sdr_property_sdf_type(declared)
            return (names, types)

        id_attr = shader_prim.GetIdAttr()
        shader_id = id_attr.Get() if id_attr else None
        if not shader_id:
            return None
        return self._nodedef(shader_id)

    def _validate_sdr_shader_inputs(self, prim: Usd.Prim, shader_prim: UsdShade.Shader) -> List[str]:
        """Validate non-MDL shader inputs against their declared definition.

        Args:
            prim: The shader prim being validated
            shader_prim: The UsdShade.Shader wrapper

        Returns:
            List of error messages
        """
        errors = []

        try:
            definition = self._shader_definition(shader_prim)

            if definition is None:
                # The definition is unavailable in this environment, so an input type
                # cannot be judged. Skip rather than report what cannot be trusted.
                return errors

            _, declared_types = definition

            # Validate shader inputs against the declaration
            for usdshade_input in shader_prim.GetInputs():
                name = usdshade_input.GetBaseName()

                # None both for an input the definition does not declare and for one
                # whose declared type has no Sdf equivalent. Neither can be judged.
                property_type = declared_types.get(name)
                input_type = usdshade_input.GetTypeName()

                if property_type is None or not input_type:
                    continue

                # Compared on the underlying type rather than the value type name, so
                # that a role difference such as color3f against float3 is not reported
                # as a mismatch. This is the same comparison VM.PBR.003 makes.
                if property_type.type != input_type.type:
                    error_msg = (
                        f"Type mismatch for: {usdshade_input.GetFullName()}"
                        f"\texpected: {property_type}\tactual: {input_type}"
                    )
                    self._AddFailedCheck(
                        message=error_msg,
                        at=prim,
                        requirement=cap.MaterialsRequirements.VM_BIND_002,
                    )
                    errors.append(error_msg)

                self._report_non_finite_input(prim, usdshade_input, errors)

        except Exception:
            # Silently skip if SDR validation fails
            pass

        return errors

    @staticmethod
    def _sdr_node_input(sdr_shader_node, name):
        """Return an Sdr node's named input, across USD's two API shapes.

        USD 25.08 renamed ``GetInput`` to ``GetShaderInput`` on the shader node. The
        surrounding ``except Exception`` would otherwise turn the AttributeError into a
        silent pass, which is indistinguishable from a shader with nothing wrong.
        """
        for accessor in ("GetShaderInput", "GetInput"):
            method = getattr(sdr_shader_node, accessor, None)
            if callable(method):
                return method(name)
        return None

    @staticmethod
    def _sdr_property_sdf_type(sdr_shader_property):
        """Return the Sdf type an Sdr property declares, across USD's two API shapes."""
        try:
            indicator = sdr_shader_property.GetTypeAsSdfType()
        except Exception:
            return None
        getter = getattr(indicator, "GetSdfType", None)
        if callable(getter):
            return getter()
        try:
            return indicator[1] or indicator[0]
        except Exception:
            return None

    @staticmethod
    def _float_components(value) -> List[float]:
        """Every floating-point scalar inside a shader input's value, in order.

        A shader input is not always a scalar float. The OpenPBR surface alone declares
        its four geometry inputs as ``float3`` and two of its scatter controls as
        ``color3f``, and a NaN in a normal reaches render output exactly as a NaN in a
        scalar does. Vectors, colors, matrices and arrays are therefore flattened to
        the numbers they hold rather than skipped for not being scalar floats.

        Integers are passed over, since an integer cannot carry NaN or Inf. That covers
        booleans too, ``bool`` being a subclass of ``int`` in Python. Strings, tokens
        and asset paths yield nothing.
        """
        numbers: List[float] = []

        def walk(item, depth: int = 0) -> None:
            # A shader input's value is at most an array of matrices; the bound stops
            # a self-referential iterable from recursing without end.
            if depth > 4:
                return
            if isinstance(item, int):
                return
            if isinstance(item, float):
                numbers.append(item)
                return
            if isinstance(item, (str, bytes)):
                return
            try:
                iterator = iter(item)
            except TypeError:
                # Not a container: take it as a number if it converts, and otherwise
                # leave it alone. Asset paths and tokens land here and convert to
                # neither, which is what should happen to them.
                try:
                    numbers.append(float(item))
                except (TypeError, ValueError):
                    pass
                return
            for sub in iterator:
                walk(sub, depth + 1)

        walk(value)
        return numbers

    def _report_non_finite_input(self, prim: Usd.Prim, shader_input, errors: List[str]) -> None:
        """Report NaN or Inf on a shader input, whatever numeric shape it carries.

        Previously this lived only in the MDL branch, and there only after the MDL
        module had been parsed, so it required Kit's MDL helpers and never ran outside
        Kit. Whether an authored float is finite is a property of the value, not of the
        material format or of the runtime that happens to be loaded, so it belongs on
        every shader input this requirement inspects. It is kept for MDL as well, so no
        coverage is lost where the helpers are present.

        It also used to admit only inputs typed exactly ``float``, which left the
        vector and color inputs unchecked -- on the OpenPBR surface, the four geometry
        directions and the two scatter controls, every one of them an input VM.PBR.002
        excludes from range checking and hands to this requirement instead. The type
        was an accident of where the check started rather than a statement about which
        values matter, so the value is now flattened to its components and each one
        tested.

        The value is read through ``_resolved_constant_source`` rather than off the
        input directly, so a constant reached through a connection is checked too.
        Reading the input alone missed every material built the conventional way: the
        values are authored as interface inputs on the ``Material`` and the shader's
        inputs connect to them, so the shader input holds no constant of its own. That
        is the shape VM.PBR.002 describes as usual, and it is the shape the check could
        not see.
        """
        value, source = self._resolved_constant_source(shader_input)
        if value is None:
            return

        own_attr = shader_input.GetAttr()
        authored_elsewhere = source is not None and source.GetPath() != own_attr.GetPath()

        components = self._float_components(value)
        multiple = len(components) > 1
        for index, number in enumerate(components):
            if math.isfinite(number):
                continue
            where = f" in component {index}" if multiple else ""
            origin = f", authored on '{source.GetPath()}'" if authored_elsewhere else ""
            message = (
                f"Shader input '{own_attr.GetName()}' contains "
                f"invalid float value (NaN or Inf){where}{origin}"
            )
            self._AddFailedCheck(
                message=message,
                at=prim,
                requirement=cap.MaterialsRequirements.VM_BIND_002,
            )
            errors.append(message)

    def _validate_mdl_shader_inputs(
        self, prim: Usd.Prim, shader_prim: UsdShade.Shader, stage: Usd.Stage, prim_path: str
    ) -> List[str]:
        """Validate MDL shader inputs against MDL specification.

        Args:
            prim: The shader prim being validated
            shader_prim: The UsdShade.Shader wrapper
            stage: The USD stage
            prim_path: Path to the shader prim

        Returns:
            List of error messages
        """
        errors = []

        mdl_path_attr = prim.GetAttribute("info:mdl:sourceAsset")

        # Check if this is an MDL shader
        if not mdl_path_attr:
            errors.append(f"Shader input 'info:mdl:sourceAsset' does not exist for {prim_path} {prim.GetTypeName()}")
            self._AddFailedCheck(
                message=f"Shader input 'info:mdl:sourceAsset' does not exist for {prim_path} {prim.GetTypeName()}",
                at=prim,
                requirement=cap.MaterialsRequirements.VM_BIND_002,
            )
            return errors

        mdl_asset = mdl_path_attr.Get()
        if not mdl_asset:
            errors.append(f"Shader input 'info:mdl:sourceAsset' has no value for {prim_path} {prim.GetTypeName()}")
            self._AddFailedCheck(
                message=f"Shader input 'info:mdl:sourceAsset' has no value for {prim_path} {prim.GetTypeName()}",
                at=prim,
                requirement=cap.MaterialsRequirements.VM_BIND_002,
            )
            return errors

        # Resolve MDL path
        mdl_path = mdl_asset.resolvedPath
        if not mdl_path and omni:
            mdl_path = omni.client.combine_urls(stage.GetRootLayer().identifier, mdl_asset.path)
        elif not mdl_path:
            mdl_path = mdl_asset.path

        mdl_path = mdl_path.replace("\\", "/")

        # Check if file exists (with caching). Only a path actually shown to exist may
        # enter the cache. It is the "known to exist" set that VM.MDL.001 reads, and
        # this branch used to add the path whether or not anything had confirmed it:
        # without Kit the `omni and ...` guard is false, so every MDL path was recorded
        # as existing. VM.MDL.001 then found it cached and reported nothing, so a
        # missing .mdl was reported for at most the first asset in a run and silently
        # passed on every later one carrying the same path. That is the environment CI
        # uses, and the class-level cache made it persist across assets.
        if mdl_path not in self._cache_existing_filepaths:
            if omni:
                if omni.client.stat(mdl_path)[0] != omni.client.Result.OK:
                    # File doesn't exist, skip validation
                    return errors
                self._cache_existing_filepaths.add(mdl_path)
            elif os.path.exists(mdl_path):
                self._cache_existing_filepaths.add(mdl_path)

        # Get material subidentifier
        mdl_material_attr = prim.GetAttribute("info:mdl:sourceAsset:subIdentifier")
        mdl_material = mdl_material_attr.Get() if mdl_material_attr else None

        if not mdl_material:
            return errors

        # Finiteness does not depend on the MDL module, so it is checked before the
        # early return below. Otherwise it would run only where Kit's MDL helpers are
        # present, which is the reason it never ran in CI or in a plain pip install.
        for shader_input in shader_prim.GetInputs():
            self._report_non_finite_input(prim, shader_input, errors)

        # Validate shader inputs against MDL specification
        if not is_mdl_helper_available():
            # MDL helpers not available, skip the shader input type checks.
            return errors

        try:
            mdl_key = f"{mdl_path}||||{mdl_material}"
            if mdl_key not in self._cache_mdl_specs:
                self._cache_mdl_specs[mdl_key] = get_mdl_module_parameter_descs(mdl_path, mdl_material)

            input_manifest = self._cache_mdl_specs[mdl_key]

            if input_manifest:
                for shader_input in shader_prim.GetInputs():
                    input_name = shader_input.GetBaseName()
                    expected_type = input_manifest.get(input_name)

                    if not expected_type:
                        continue

                    actual_type = shader_input.GetTypeName()
                    if expected_type != actual_type:
                        self._AddFailedCheck(
                            message=f"Shader input '{shader_input.GetAttr().GetName()}' has type '{actual_type}', expected '{expected_type}'",
                            at=prim,
                            requirement=cap.MaterialsRequirements.VM_BIND_002,
                        )
                        errors.append(f"Type mismatch for {input_name}: {actual_type} vs {expected_type}")
            else:
                self._AddFailedCheck(
                    message=f"Cannot validate shader inputs: invalid material shader '{mdl_material}' in '{mdl_path}'",
                    at=prim,
                    requirement=cap.MaterialsRequirements.VM_BIND_002,
                )
                errors.append(f"Invalid material shader: {mdl_material}")

        except ImportError:
            # MDL helpers not available, skip this check
            pass

        return errors

    def check_vm_bind_002_shader_inputs(self, stage, prim_path: str) -> List[str]:
        """Check VM.BIND.002: Shader inputs validation."""
        errors = []

        prim = stage.GetPrimAtPath(prim_path)
        if not prim or prim.GetTypeName() != "Shader":
            # prim is not a shader, skip validation
            return errors

        shader_prim = UsdShade.Shader(prim)
        if not shader_prim:
            errors.append(f"No shader schema for {prim_path} {prim.GetTypeName()}")
            self._AddFailedCheck(
                message=f"No shader schema for {prim_path} {prim.GetTypeName()}",
                at=prim,
                requirement=cap.MaterialsRequirements.VM_BIND_002,
            )
            return errors

        id_attr = prim.GetAttribute("info:id")
        mdl_path_attr = prim.GetAttribute("info:mdl:sourceAsset")

        if id_attr and not mdl_path_attr:
            # Handle non-MDL shaders (built-in shaders, node graphs, etc.)
            errors.extend(self._validate_sdr_shader_inputs(prim, shader_prim))
        else:
            # Handle MDL shaders
            errors.extend(self._validate_mdl_shader_inputs(prim, shader_prim, stage, prim_path))

        return errors

    @staticmethod
    @contextlib.contextmanager
    def _image_size_guard_lifted(image_module):
        """Let Pillow report the size of an image it would otherwise refuse to open.

        Pillow raises ``DecompressionBombError`` from ``Image.open`` once the declared
        pixel count passes twice ``MAX_IMAGE_PIXELS``, which defaults to 89,478,485. The
        surrounding ``except Exception`` turned that into a silent skip, so every texture
        above roughly 13,376 square went unreported -- including a 16384x16384 one, which
        is exactly the size this requirement permits, and a 32768x32768 one, which is the
        case the rule exists for. Only the dimensions are read here and no pixel data is
        decoded, so the guard has nothing to protect against.
        """
        previous = image_module.MAX_IMAGE_PIXELS
        image_module.MAX_IMAGE_PIXELS = None
        try:
            yield
        finally:
            image_module.MAX_IMAGE_PIXELS = previous

    def check_vm_tex_001_texture_size(self, stage, prim_path: str) -> List[str]:
        """Check VM.TEX.001: Texture size compliance."""
        errors = []

        prim = stage.GetPrimAtPath(prim_path)
        if not prim:
            return errors

        # Check all attributes for texture asset references
        for attr in prim.GetAttributes():
            # Check if attribute is an asset type
            if attr.GetTypeName() == Sdf.ValueTypeNames.Asset:
                asset_value = attr.Get()
                if not asset_value:
                    continue

                asset_path = asset_value.resolvedPath
                if not asset_path and omni:
                    asset_path = omni.client.combine_urls(stage.GetRootLayer().identifier, asset_value.path)
                elif not asset_path:
                    asset_path = asset_value.path

                # Check if this is an image file
                image_extensions = [".png", ".jpg", ".jpeg", ".exr", ".hdr", ".tga", ".bmp", ".tif", ".tiff"]
                if any(asset_path.lower().endswith(ext) for ext in image_extensions):
                    # Validate texture size
                    try:
                        # Try to get image dimensions using PIL if available
                        from PIL import Image

                        if os.path.exists(asset_path):
                            with self._image_size_guard_lifted(Image), Image.open(asset_path) as img:
                                width, height = img.size
                                if width > self.max_texture_size or height > self.max_texture_size:
                                    self._AddFailedCheck(
                                        message=f"Texture '{asset_path}' dimensions ({width}x{height}) exceed maximum size of {self.max_texture_size} pixels on either axis",
                                        at=prim,
                                        requirement=cap.MaterialsRequirements.VM_TEX_001,
                                    )
                                    errors.append(f"Texture too large: {asset_path} ({width}x{height})")
                    except ImportError:
                        # PIL not available, skip size check
                        pass
                    except Exception:
                        # Unable to read image, skip
                        pass

        return errors
