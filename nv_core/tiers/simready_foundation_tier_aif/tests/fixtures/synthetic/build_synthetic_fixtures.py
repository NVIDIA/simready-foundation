# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Generate the synthetic AIF fixtures from the class configs and value sources.

Everything the validators read is metadata and connection point structure, so
this writes an asset per equipment class: the aif:core:* and
aif:spec:* values lifted from a source, the connection points as complete CP2 coordinate frames, and the root-layer SimReady_Metadata that SR.001 reads.

A source is either a fixture asset under tests/fixtures/ (read with USD) or a
JSON file under synthetic/sources/ mapping attribute name to [type, value].
The JSON sources carry invented, vendor-neutral values: the CRAH values are
Beau Perschall's fictional "Generic Cooling Systems" CRAH from
aif-pipeline-samples, and the UPS values were authored for this fixture. No
value in either file comes from a vendor product. CRAH and UPS geometry is
remodeled from in-house exemplars; see sources/README.md for provenance and
regeneration. The other fixtures retain their minimal mesh bodies.

The required attribute set comes from config/aif-equipment-<class>.json, the
same file the validator reads, so a generated fixture cannot drift from AM.007.

Usage:
    python build_synthetic_fixtures.py <simready_foundations-worktree> [--write]
"""
import json
import importlib.util
from pathlib import Path
import os
import sys

TIER = "nv_core/tiers/simready_foundation_tier_aif"
PKG = f"{TIER}/simready/foundation/tier_aif"
FIXTURES = f"{TIER}/tests/fixtures"
OUT = f"{FIXTURES}/synthetic"      # test fixtures, covered by the repo licence
SAMPLES = "sample_content/aif"     # published samples, CC-BY 4.0

# Every asset this script writes is content NVIDIA authored for this
# repository, so both destinations carry the same licence. The string matches
# the rest of sample_content, and the Isaac asset library states CC-BY 4.0 the
# same way on its own converted assets.
LICENSES = {SAMPLES: "CC-BY 4.0", OUT: "CC-BY 4.0"}

# One synthetic asset per equipment class. The third column names the source
# to lift values from, relative to tests/fixtures/: a fixture asset, or a JSON
# value file under synthetic/sources/. The asset name states the equipment
# class, never a vendor product.
ASSETS = [
    ("cdu", "Synthetic_CDU", f"{SAMPLES}/Generic_CDU/asset/Generic_CDU.usda", OUT),
    ("crah", "Synthetic_CRAH", f"{FIXTURES}/synthetic/sources/generic_crah.json", SAMPLES),
    ("ups", "Synthetic_UPS", f"{FIXTURES}/synthetic/sources/generic_ups.json", SAMPLES),
    ("compute-rack", "Synthetic_ComputeRack", f"{SAMPLES}/gb300/asset/gb300.usda", OUT),
]



def load_classes(root):
    out = {}
    for name in sorted(os.listdir(os.path.join(root, PKG, "config"))):
        if not name.startswith("aif-equipment-"):
            continue
        doc = json.load(open(os.path.join(root, PKG, "config", name)))
        out[doc["class"]] = doc
    return out


def lift_values(root, rel):
    """Read every aif:core:* and aif:spec:* value off the source.

    A .json source is a dict of attribute name -> [usd type name, value]; the
    value of a vector type is a list of components. Anything else is opened as
    a USD stage and traversed.
    """
    path = os.path.join(root, rel)
    if rel.endswith(".json"):
        return {name: (type_name, value)
                for name, (type_name, value) in json.load(open(path)).items()
                if name.startswith("aif:core:") or name.startswith("aif:spec:")}
    from pxr import Usd
    stage = Usd.Stage.Open(path)
    out = {}
    for prim in stage.Traverse():
        for attr in prim.GetAttributes():
            n = attr.GetName()
            if n.startswith("aif:core:") or n.startswith("aif:spec:"):
                v = attr.Get()
                if v is not None:
                    out[n] = (attr.GetTypeName(), v)
    return out


_STRINGY = ("string", "token", "asset")
_INTEGRAL = ("int", "uint", "int64", "uint64", "uchar")


def _quote(value) -> str:
    """Quote a USD string or token, escaping what the text format reserves."""
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return '"%s"' % text.replace("\n", "\\n")


def _scalar(type_name: str, value) -> str:
    """Format one value. The declared type decides, not the Python type."""
    base = type_name[:-2] if type_name.endswith("[]") else type_name
    if base in _STRINGY:
        return _quote(value)
    if base == "bool":
        return "1" if value else "0"
    if base in _INTEGRAL:
        return "%d" % int(value)
    try:
        # repr round-trips a float exactly; "%g" keeps six significant digits,
        # so a value like 113557.90625 came back as 113558.
        return repr(float(value))
    except (TypeError, ValueError):
        # A compound: Gf.Vec3f, Gf.Matrix4d, anything iterable of numbers.
        return "(%s)" % ", ".join(_scalar(base, component) for component in value)


def usda_value(type_name, value):
    """Return (declared type, value literal) for one attribute.

    The type is emitted as the source declares it. Mapping a small allowlist and
    falling back to `string` silently retyped every USD type outside that list:
    `vector3f` became a quoted string in three committed fixtures, and so would
    `point3f`, `normal3f`, `color3f` and `double3`.
    """
    t = str(type_name)
    if t.endswith("[]"):
        return t, "[%s]" % ", ".join(_scalar(t, item) for item in value)
    return t, _scalar(t, value)


# Wikidata entity per equipment class, resolved rather than searched for. SR.001
# checks only that a qcode matches ^Q[0-9]+$, so a wrong entity passes silently.
QCODE = {"cdu": "Q189124", "crah": "Q2479079", "ups": "Q207696",
         "compute-rack": "Q431000"}

GENERATED = "2026-09-14"


def root_layer_text(asset_name, sublayers, category, qcode, extents, mass,
                    asset_license="CC-BY 4.0"):
    """Build a root layer carrying the metadata SR.001 reads.

    SR.001 wants five entries at the top of customLayerData -- the
    SimReady_Metadata dictionary and four fields beside it -- and eleven inside
    the dictionary. The four that appear twice are mirrored here rather than
    left to drift.
    """
    layers = "\n".join('        @%s@,' % path for path in sublayers).rstrip(",")
    return '''#usda 1.0
(
    defaultPrim = "%s"
    metersPerUnit = 1
    upAxis = "Z"
    subLayers = [
%s
    ]
    customLayerData = {
        string asset_name = "%s"
        string asset_type = "equipment"
        string source_file = "%s.usda"
        string usd_date_generated = "%s"

        dictionary SimReady_Metadata = {
            string author = "nvidia"
            string asset_name = "%s"
            string asset_type = "equipment"
            string asset_license = "%s"
            string category = "%s"
            string source_file = "%s.usda"
            string usd_date_generated = "%s"
            string qcode = "%s"
            int rigid_body_count = 0
            float3 asset_extents = (%s)
            float mass = %s
        }
    }
)

def Xform "%s"
{
    # A body. VG.MESH.001 asks a SimReady asset to contain at least one mesh,
    # and a connection point is an Xform under v0.2.0, so a fixture whose only
    # content is connection points has no geometry at all.
    def Mesh "Body"
    {
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
        point3f[] points = [(-0.5, -0.5, 0), (0.5, -0.5, 0), (0.5, 0.5, 0), (-0.5, 0.5, 0)]
        float3[] extent = [(-0.5, -0.5, 0), (0.5, 0.5, 0)]
    }
}
''' % (asset_name, layers, asset_name, asset_name, GENERATED,
       asset_name, asset_license, category, asset_name, GENERATED, qcode,
       ", ".join(repr(float(e)) for e in extents), repr(float(mass)),
       asset_name)


def emit(root, cls, asset_name, source_rel, dest, classes, write):
    doc = classes[cls]
    vals = lift_values(root, source_rel) if source_rel else {}
    required = sorted(doc["attributes"])

    missing = [a for a in required if a not in vals]
    extra_core = sorted(k for k in vals if k.startswith("aif:core:"))

    prop_lines = []
    for attr in extra_core + required:
        if attr in vals:
            t, v = usda_value(*vals[attr])
        else:
            t, v = "float", "0"
        prop_lines.append("    custom %s %s = %s" % (t, attr, v))

    props = '#usda 1.0\n(\n    defaultPrim = "%s"\n)\n\nover "%s"\n{\n%s\n}\n' % (
        asset_name, asset_name, "\n".join(prop_lines))

    # Share the canonical CP2 source with the two NVIDIA equipment fixtures.
    builder_path = Path(__file__).resolve().parent.parent / "connection_points" / "build_connection_points.py"
    spec = importlib.util.spec_from_file_location("fixture_connection_points", builder_path)
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    conn = builder.layer_text(asset_name)

    dims = vals.get("aif:core:overallGeometryDimensions", (None, (1000.0, 1000.0, 2000.0)))[1]
    root_layer = root_layer_text(
        asset_name,
        sublayers=[f"./layers/{asset_name}_Properties.usda",
                   f"./layers/{asset_name}_ConnectionPoints.usd"],
        # category is aif:core:assetClass, the value the vendor assets carry.
        # displayName is prose for a reader and groups the fixture tree wrong.
        category=str(vals["aif:core:assetClass"][1]),
        qcode=QCODE[cls],
        extents=[float(d) / 1000.0 for d in dims],
        mass=float(vals.get("aif:core:weight", (None, 1000.0))[1]),
        asset_license=LICENSES[dest],
    )

    if cls in ("crah", "ups"):
        # The committed geometry layer is rebuilt separately from the in-house
        # exemplars; ordinary metadata regeneration needs no external assets.
        root_layer = root_layer.replace(
            "    subLayers = [",
            '    subLayers = [\n        @./layers/%s_Geometry.usda@,' % asset_name,
        )
        root_layer = root_layer[:root_layer.index('\ndef Xform')] + '\ndef Xform "%s"\n{\n}\n' % asset_name

    files = {
        f"asset/{asset_name}.usda": root_layer,
        f"asset/layers/{asset_name}_Properties.usda": props,
        f"asset/layers/{asset_name}_ConnectionPoints.usd": conn,
    }
    if write:
        for name, text in files.items():
            path = os.path.join(root, dest, asset_name, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w").write(text)
    return len(required), len(missing), missing, sum(len(t) for t in files.values())


def main(root, write):
    classes = load_classes(root)
    print("%-14s %-14s %-9s %-9s %s" % ("class", "asset", "required", "missing", "bytes"))
    for cls, asset_name, source_rel, dest in ASSETS:
        n, nm, missing, size = emit(root, cls, asset_name, source_rel, dest, classes, write)
        print("  %-12s %-14s %-9d %-9d %d %s" % (cls, asset_name, n, nm, size,
              ("<- " + ", ".join(x.split(":")[-1] for x in missing[:4])) if missing else ""))
    print()
    print("%-12s %-28s %-9s %s" % ("cp2 domain", "asset", "props", "unvalued"))
    for domain, name, n, nm, missing in emit_cp2(root, write):
        print("  %-10s %-28s %-9d %d %s" % (domain, name, n, nm, missing or ""))
    print("\n%s" % ("written to " + os.path.join(root, OUT) if write else "dry run, nothing written"))




# --------------------------------------------------------------------------
# CP 2.0 positives, one per connection point domain. These are the companions
# to the cp2_fail_* negatives in tests/fixtures/variants/, and they replace the
# single thermal-only positive that used to sit beside them.
# The property list is parsed from the CP.011 and CP.012 requirement documents,
# so a generated fixture cannot drift from the specification.

CP2_VALUES = {
    "thermal": {"portDiameter": "0.05", "matingDepth": "0.02", "designFlowRate": "12.5",
                "maxFlowRate": "15.0", "designTemperature": "18.0", "maxTemperature": "25.0",
                "operatingPressure": "400000", "maxPressure": "1000000",
                "fluidType": "water", "flangeRating": "ANSI_150", "flangeSize": "NPS4"},
    "electrical": {"matingDepth": "0.0", "nominalVoltage": "480.0", "maxCurrent": "1458.0",
                   "phases": "3", "frequency": "60.0", "connectorType": "hardwired",
                   "ratedPower": "1200000.0", "breakerRating": "2000.0", "powerFactor": "0.99"},
    "network": {"portWidth": "0.022", "portHeight": "0.009", "matingDepth": "0.015",
                "portType": "OSFP", "protocol": "Ethernet", "dataRate": "800GbE",
                "medium": "fiber", "fabricRole": "compute",
                "supportedLineRates": '["800GbE", "400GbE"]',
                "supportedConfigurations": '["1x800G", "2x400G"]',
                "allowedTransceivers": '["DR4", "FR4"]', "hotPlugCapable": "1"},
    "airflow": {"interfaceWidth": "0.6", "interfaceHeight": "2.0", "freeAreaRatio": "0.7",
                "designAirflowRate": "1.07", "maxAirflowRate": "1.28",
                "designTemperature": "24.0", "maxTemperature": "45.0",
                "staticPressure": "50.0", "filterType": "none"},
}
CP2_BASE = {"thermal": ("supply", "FWS", "flanged"), "electrical": ("input", "power", "hardwired"),
            "network": ("bidirectional", "high_speed_data", "OSFP"),
            "airflow": ("input", "equipment_cooling", "open_vent")}
CP2_TYPES = {"phases": "int", "hotPlugCapable": "bool"}


def cp2_usda_type(domain, prop, value):
    if prop in CP2_TYPES:
        return CP2_TYPES[prop]
    if value.startswith("["):
        return "token[]"
    try:
        float(value)
        return "float"
    except ValueError:
        return "token"


def emit_cp2(root, write):
    import re
    reqs = os.path.join(root, PKG, "capabilities/aif/connection_points/requirements")

    def table(text, marker):
        body = text.split(marker, 1)[1]
        out = []
        for line in body.splitlines():
            line = line.strip()
            if not line.startswith("|"):
                if out:
                    break
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) < 3 or cells[0].startswith("---") or cells[0] == "Property":
                continue
            out.append(cells[0].strip("`").split(":")[-1])
        return out

    dom_doc = open(os.path.join(reqs, "connection-point-domain-namespace.md")).read()
    markers = {"thermal": "### Thermal domain", "electrical": "### Electrical domain",
               "network": "### Network domain", "airflow": "### Airflow domain"}

    rows = []
    for domain, marker in markers.items():
        props = table(dom_doc, marker)
        missing = [p for p in props if p not in CP2_VALUES[domain]]
        direction, system, disconnect = CP2_BASE[domain]
        lines = [
            '            uniform token purpose = "guide"',
            '            token simready:connectionPoint:domain = "%s"' % domain,
            '            token simready:connectionPoint:direction = "%s"' % direction,
            '            token simready:connectionPoint:system = "%s"' % system,
            '            token simready:connectionPoint:disconnectType = "%s"' % disconnect,
            '            float simready:connectionPoint:serviceClearance = 0.6',
            '',
        ]
        for prop in props:
            v = CP2_VALUES[domain].get(prop, "0")
            t = cp2_usda_type(domain, prop, v)
            rendered = v if (t in ("float", "int", "bool") or v.startswith("[")) else '"%s"' % v
            lines.append('            %s simready:connectionPoint:%s:%s = %s'
                         % (t, domain, prop, rendered))
        name = "Synthetic_CP2_%s" % domain.capitalize()
        conn = ('#usda 1.0\n(\n    defaultPrim = "%s"\n)\n\ndef Xform "%s"\n{\n'
                '    def Scope "ConnectionPoints"\n    {\n        def Xform "acme_%s_main"\n        {\n%s\n        }\n    }\n}\n'
                % (name, name, domain, "\n".join(lines)))
        # The same root layer the class fixtures get. Without it these four fail
        # SR.001, which no test asserts, so the only place it showed was a
        # profile run.
        rootl = root_layer_text(
            name,
            sublayers=["./layers/%s_ConnectionPoints.usd" % name],
            category="Connection Point",
            qcode="Q189124",
            extents=[0.1, 0.1, 0.1],
            mass=1.0,
        )
        if write:
            for rel, text in (("asset/%s.usda" % name, rootl),
                              ("asset/layers/%s_ConnectionPoints.usd" % name, conn)):
                path = os.path.join(root, OUT, name, rel)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                open(path, "w").write(text)
        rows.append((domain, name, len(props), len(missing), missing))
    return rows


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".", "--write" in sys.argv)
