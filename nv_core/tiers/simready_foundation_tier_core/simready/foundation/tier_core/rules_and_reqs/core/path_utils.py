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
"""Shared asset-path helpers for Core capability validators."""

import glob
import io
import os
import posixpath
import re
import zipfile
from functools import lru_cache
from typing import Optional

try:
    import omni.client as omni_client
except ImportError:
    omni_client = None


UDIM_SPECIFIER = "<UDIM>"
UDIM_TILE_PATTERN = re.compile(r"^\d{4}$")


# MDL modules Kit ships and resolves from its own search paths. A reference to one of
# these may be authored by name, with no anchor: Kit ties MDL module identity to
# filesystem location, so the runtime resolves the module where it installed it. Anchoring
# such a name makes it a layer-relative path that resolves to nothing unless the asset
# packages a copy at that location.
#
# Generated from Kit 110.1.2 (Isaac Sim 6.0.1). /renderer/mdl/searchPaths in
# kit/kernel/config/kit-core.json lists the search folders; these sets hold every .mdl file
# in the material ones -- mdl/core/{Base,Ue4,Aperture,VRay,Volume,mdl} and mdl/mtlx -- plus
# UsdPreviewSurface.mdl from mdl/rtx. Two groups are left out because no asset names them as
# a material's source and their generic names would match an asset's own module: the MDL
# standard library (anno, base, debug, df, limits, math, mdl-builtin, scene, state, std, tex)
# and the renderer's other modules in mdl/rtx and mdl/rtx/iray.
#
# A module directly in a search folder resolves by its bare name and is in
# BUILTIN_MDL_MODULES; a module in a subfolder resolves by its folder-qualified name and is
# in BUILTIN_MDL_SUFFIXES. Names are lowercase because matching is case-insensitive.
# Regenerate both sets the same way when a Kit release adds modules. The Isaac asset
# transformer's fallback list (isaacsim.asset.transformer.rules.utils) is a subset of this
# and names omnipbr_base.mdl, which matches no shipped file.
BUILTIN_MDL_MODULES = frozenset(
    {
        "ad_3dsmax_maps.mdl",
        "ad_3dsmax_materials.mdl",
        "baking_annotations.mdl",
        "omniemissive.mdl",
        "omniglass.mdl",
        "omniglass_opacity.mdl",
        "omnihair.mdl",
        "omnihairpresets.mdl",
        "omnipbr.mdl",
        "omnipbr_clearcoat.mdl",
        "omnipbr_clearcoat_opacity.mdl",
        "omnipbr_opacity.mdl",
        "omnipbrbase.mdl",
        "omnisurface.mdl",
        "omnisurfaceblend.mdl",
        "omnisurfacelite.mdl",
        "omnisurfacepresets.mdl",
        "omniue4base.mdl",
        "omniue4function.mdl",
        "omniue4functionextension17.mdl",
        "omniue4subsurface.mdl",
        "omniue4translucent.mdl",
        "omnivolumedensity.mdl",
        "omnivolumenoise.mdl",
        "simpbr.mdl",
        "simpbr_model.mdl",
        "simpbr_translucent.mdl",
        "usdpreviewsurface.mdl",
        "vray_maps.mdl",
        "vray_materials.mdl",
    }
)

# Modules in a subfolder of a search folder, by the folder-qualified name Kit resolves.
BUILTIN_MDL_SUFFIXES = frozenset(
    {
        "gltf/pbr.mdl",
        "materialx/core.mdl",
        "materialx/hsv.mdl",
        "materialx/noise.mdl",
        "materialx/pbrlib.mdl",
        "materialx/pbrlib_1_10.mdl",
        "materialx/pbrlib_1_6.mdl",
        "materialx/pbrlib_1_7.mdl",
        "materialx/pbrlib_1_8.mdl",
        "materialx/pbrlib_1_9.mdl",
        "materialx/sampling.mdl",
        "materialx/stdlib.mdl",
        "materialx/stdlib_1_10.mdl",
        "materialx/stdlib_1_6.mdl",
        "materialx/stdlib_1_7.mdl",
        "materialx/stdlib_1_8.mdl",
        "materialx/stdlib_1_9.mdl",
        "nvidia/aux_definitions.mdl",
        "nvidia/axf_importer/axf_importer.mdl",
        "nvidia/core_definitions.mdl",
        "nvidia/digital_human_tech/color_correct.mdl",
        "nvidia/digital_human_tech/random_value.mdl",
        "nvidia/support_definitions.mdl",
        "omnisurface/omnihairbase.mdl",
        "omnisurface/omniimage.mdl",
        "omnisurface/omnishared.mdl",
        "omnisurface/omnisurfacebase.mdl",
        "omnisurface/omnisurfaceblendbase.mdl",
        "omnisurface/omnisurfacelitebase.mdl",
    }
)


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


def is_builtin_mdl_search_path(source_path: str) -> bool:
    """Whether an ``info:mdl:sourceAsset`` value names a shipped module by its search-path form.

    True for a bare module name in :data:`BUILTIN_MDL_MODULES` (``OmniPBR.mdl``) or a
    prefixed form in :data:`BUILTIN_MDL_SUFFIXES` (``nvidia/core_definitions.mdl``),
    compared case-insensitively. The runtime resolves either from its own MDL search path,
    so the file is never next to the asset, and a check that looks for it there reports a
    module that loads.

    Narrower than :func:`is_builtin_mdl_module`, which matches a copy at any path by its
    file name. An anchored, absolute or directory-qualified path states where the file is,
    so a missing file at that location is still a broken path.
    """
    normalized = source_path.replace("\\", "/").lower()
    return normalized in BUILTIN_MDL_MODULES or normalized in BUILTIN_MDL_SUFFIXES


def file_path(path: str) -> str:
    """Extract the directory from a file path."""
    return os.path.dirname(path)


def combine_paths(base_path: str, relative_path: str) -> str:
    """Combine local base and relative paths using normalized separators."""
    return os.path.normpath(os.path.join(base_path, relative_path)).replace("\\", "/")


def file_exists(path: str) -> bool:
    """Return whether *path* exists on a local, Nucleus, or resolver-backed store.

    Tries ``Ar.GetResolver().Resolve`` first so S3/HTTPS plugins work when
    installed, then ``omni.client.stat`` for ``omniverse://``, then ``os.path``.
    """
    if not path:
        return False
    try:
        from pxr import Ar

        if Ar.GetResolver().Resolve(path):
            return True
    except Exception:
        pass
    if "omniverse://" in path:
        if omni_client:
            result, _ = omni_client.stat(path)
            return result == omni_client.Result.OK
        return False
    return os.path.exists(path)


asset_exists = file_exists


def split_package_identifier(identifier: str) -> tuple[str, str]:
    """Return the outer package and optional inner member identifiers."""
    if not identifier:
        return "", ""
    try:
        from pxr import Ar

        if Ar.IsPackageRelativePath(identifier):
            return Ar.SplitPackageRelativePathOuter(identifier)
    except Exception:
        pass
    return identifier, ""


def package_member_identifier(package_identifier: str, member_path: str) -> str:
    """Build an OpenUSD package-relative identifier for *member_path*."""
    if not package_identifier or not member_path:
        return ""
    outer, _inner = split_package_identifier(package_identifier)
    try:
        from pxr import Ar

        return Ar.JoinPackageRelativePath(outer, member_path.replace("\\", "/"))
    except Exception:
        return f"{outer}[{member_path.replace(chr(92), '/')}]"


@lru_cache(maxsize=32)
def package_member_names(package_identifier: str) -> tuple[str, ...]:
    """Return package member names using resolver-backed package bytes."""
    outer, _inner = split_package_identifier(package_identifier)
    if not outer.lower().endswith(".usdz"):
        return ()
    raw = read_asset_bytes(outer)
    if raw is None:
        return ()
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            return tuple(archive.namelist())
    except (OSError, zipfile.BadZipFile):
        return ()


def package_root_member(package_identifier: str) -> str:
    """Return the first USD layer member, which is the USDZ root layer."""
    for member in package_member_names(package_identifier):
        if member.lower().endswith((".usd", ".usda", ".usdc")):
            return member
    return ""


def delivered_asset_identifier(layer_or_identifier) -> str:
    """Return the outer path delivered to the validator.

    Inner package layers such as ``asset.usdz[payloads/base.usdc]`` map back to
    ``asset.usdz``. This is the path naming, folder, sidecar, and thumbnail
    requirements must evaluate.
    """
    identifier = str(getattr(layer_or_identifier, "identifier", layer_or_identifier) or "")
    outer, inner = split_package_identifier(identifier)
    if not inner and hasattr(layer_or_identifier, "realPath"):
        real_path = str(getattr(layer_or_identifier, "realPath", "") or "")
        if real_path:
            outer, _inner = split_package_identifier(real_path)
    return outer.replace("\\", "/")


def anchored_asset_identifier(layer_or_identifier, authored_path: str) -> str:
    """Anchor an authored asset path to its authoring layer.

    For package layers, the result remains package-relative so the resolver can
    open the referenced member without treating it as a host filesystem path.
    """
    if not authored_path:
        return ""
    layer = layer_or_identifier if hasattr(layer_or_identifier, "identifier") else None
    identifier = getattr(layer_or_identifier, "identifier", layer_or_identifier)
    identifier = str(identifier or "")
    outer, inner = split_package_identifier(identifier)

    normalized_authored = authored_path.replace("\\", "/")
    if (
        normalized_authored.startswith("/")
        or "://" in normalized_authored
        or (len(normalized_authored) >= 2 and normalized_authored[1] == ":")
    ):
        return normalized_authored

    if outer.lower().endswith(".usdz"):
        anchor_member = inner or package_root_member(outer)
        anchor_dir = posixpath.dirname(anchor_member)
        member = posixpath.normpath(posixpath.join(anchor_dir, normalized_authored))
        if member == ".." or member.startswith("../"):
            return ""
        return package_member_identifier(outer, member)

    if layer is not None:
        try:
            from pxr import Sdf

            return Sdf.ComputeAssetPathRelativeToLayer(layer, normalized_authored)
        except Exception:
            compute = getattr(layer, "ComputeAbsolutePath", None)
            if compute is not None:
                return compute(normalized_authored)
    if "://" in identifier:
        scheme, path = identifier.split("://", 1)
        anchored = posixpath.normpath(posixpath.join(posixpath.dirname(path), normalized_authored))
        return f"{scheme}://{anchored}"
    return combine_paths(file_path(identifier), authored_path)


def sidecar_json_identifier(root_layer) -> Optional[str]:
    """Return the sibling ``<usd_stem>.json`` identifier for *root_layer*.

    Uses ``Sdf.Layer.ComputeAbsolutePath`` so URI-backed layers keep a
    resolver-legal sibling path instead of a local ``os.path.join`` result.
    """
    if root_layer is None:
        return None
    identifier = delivered_asset_identifier(root_layer)
    if not identifier:
        return None
    posix = str(identifier).replace("\\", "/")
    basename = posix.rsplit("/", 1)[-1]
    stem, _ext = os.path.splitext(basename)
    if not stem:
        return None
    parent = posix.rsplit("/", 1)[0] if "/" in posix else ""
    return f"{parent}/{stem}.json" if parent else f"{stem}.json"


def sidecar_json_identifiers(root_layer) -> tuple[str, ...]:
    """Return the external sibling sidecar when it exists."""
    candidate = sidecar_json_identifier(root_layer)
    return (candidate,) if candidate and file_exists(candidate) else ()


def thumbnail_png_identifier(root_layer) -> Optional[str]:
    """Return the SimReady thumbnail identifier ``.thumbs/256x256/<usd>.png``."""
    if root_layer is None:
        return None
    identifier = delivered_asset_identifier(root_layer)
    if not identifier:
        return None
    posix = str(identifier).replace("\\", "/")
    basename = posix.rsplit("/", 1)[-1]
    if not basename:
        return None
    parent = posix.rsplit("/", 1)[0] if "/" in posix else ""
    relative = f".thumbs/256x256/{basename}.png"
    return f"{parent}/{relative}" if parent else relative


def read_asset_bytes(path: str) -> Optional[bytes]:
    """Read *path* via the USD resolver, then local open, then ``omni.client``."""
    if not path:
        return None
    try:
        from pxr import Ar

        resolver = Ar.GetResolver()
        resolved = resolver.Resolve(path)
        if resolved:
            ar_asset = resolver.OpenAsset(resolved)
            if ar_asset is not None:
                buf = ar_asset.GetBuffer()
                return bytes(buf) if buf is not None else b""
    except Exception:
        pass
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError:
        pass
    if omni_client and "omniverse://" in path:
        result, _entry, content = omni_client.read_file(path)
        if result == omni_client.Result.OK and content is not None:
            return bytes(content)
    return None


def is_udim_asset_path(path: str) -> bool:
    """Return whether a USD asset path contains the ``<UDIM>`` token."""
    return bool(path) and UDIM_SPECIFIER in path


def resolve_udim_template_path(
    authored_path: str,
    resolved_path: str = "",
    anchor_file_path: str = "",
) -> str:
    """Resolve a UDIM template while preserving its token.

    USD may leave ``Sdf.AssetPath.resolvedPath`` empty, or return a value that
    no longer contains the token. In those cases, anchor the authored template
    to the layer that authored it.
    """
    if is_udim_asset_path(resolved_path):
        return resolved_path.replace("\\", "/")
    if not is_udim_asset_path(authored_path) or not anchor_file_path:
        return ""
    return anchored_asset_identifier(anchor_file_path, authored_path)


def _udim_tile_token(filename: str, template_basename: str) -> str:
    """Return the four-digit tile token when a filename matches a template."""
    if UDIM_SPECIFIER not in template_basename:
        return ""
    prefix, suffix = template_basename.split(UDIM_SPECIFIER, 1)
    if not filename.startswith(prefix) or not filename.endswith(suffix):
        return ""
    token = filename[len(prefix) : len(filename) - len(suffix)]
    return token if UDIM_TILE_PATTERN.fullmatch(token) else ""


def udim_tiles_exist(resolved_template_path: str) -> bool:
    """Return whether a resolved UDIM template has at least one tile."""
    if not is_udim_asset_path(resolved_template_path):
        return False

    resolved_template_path = resolved_template_path.replace("\\", "/")
    outer, inner = split_package_identifier(resolved_template_path)
    if inner:
        template_basename = posixpath.basename(inner)
        template_dir = posixpath.dirname(inner)
        return any(
            posixpath.dirname(member) == template_dir
            and _udim_tile_token(posixpath.basename(member), template_basename)
            for member in package_member_names(outer)
        )

    template_basename = os.path.basename(resolved_template_path)
    template_dir = os.path.dirname(resolved_template_path)

    if "omniverse://" in resolved_template_path:
        if not omni_client:
            return False
        result, entries = omni_client.list(template_dir)
        if result != omni_client.Result.OK:
            return False
        return any(_udim_tile_token(os.path.basename(entry.relative_path), template_basename) for entry in entries)

    glob_pattern = resolved_template_path.replace(UDIM_SPECIFIER, "*")
    return any(_udim_tile_token(os.path.basename(hit), template_basename) for hit in glob.glob(glob_pattern))


def resolve_existing_udim_template_path(
    authored_path: str,
    resolved_path: str = "",
    anchor_file_path: str = "",
) -> str:
    """Resolve a UDIM template only when at least one matching tile exists."""
    template_path = resolve_udim_template_path(
        authored_path=authored_path,
        resolved_path=resolved_path,
        anchor_file_path=anchor_file_path,
    )
    return template_path if udim_tiles_exist(template_path) else ""
