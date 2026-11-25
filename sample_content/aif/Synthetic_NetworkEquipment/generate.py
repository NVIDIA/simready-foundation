# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Generate a fictional network switch; all engineering inputs are synthetic.

Requires OpenUSD Python. --render additionally requires usdrecord and Pillow.
The authored CSV governs equipment attribute identities and types.
"""
import argparse
import csv
import json
import math
from pathlib import Path
import subprocess

from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux, UsdPhysics, UsdShade, Vt

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
NAME = "Synthetic_NetworkEquipment"
CSV = REPO / "standards/equipment-classes/aif-v0.3/network-equipment.csv"
TYPES = {"float": Sdf.ValueTypeNames.Float, "float3": Sdf.ValueTypeNames.Float3,
         "int": Sdf.ValueTypeNames.Int, "string": Sdf.ValueTypeNames.String,
         "token": Sdf.ValueTypeNames.Token, "token[]": Sdf.ValueTypeNames.TokenArray,
         "bool": Sdf.ValueTypeNames.Bool}


def new_stage(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    stage = Usd.Stage.CreateNew(str(path))
    root = UsdGeom.Xform.Define(stage, "/world").GetPrim()
    stage.SetDefaultPrim(root)
    UsdGeom.SetStageUpAxis(stage, "Z")
    UsdGeom.SetStageMetersPerUnit(stage, 1)
    UsdPhysics.SetStageKilogramsPerUnit(stage, 1)
    return stage


class Geometry:
    """Closed mesh boxes with derived mass from stated synthetic densities."""

    def __init__(self, stage, source):
        self.stage, self.source, self.mass = stage, source, 0.0
        self.materials = {}
        UsdGeom.Scope.Define(stage, "/world/Geometry")
        for name, data in source["materials"].items():
            mat = UsdShade.Material.Define(stage, "/world/Looks/" + name)
            shader = UsdShade.Shader.Define(stage, str(mat.GetPath()) + "/Surface")
            shader.CreateIdAttr("UsdPreviewSurface")
            shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*data["color"]))
            shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(data["roughness"])
            shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(data["metallic"])
            mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
            self.materials[name] = mat

    def box(self, name, center, size, material="Aluminum"):
        x, y, z = (v / 2 for v in size)
        points = [(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),
                  (-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
        points = [Gf.Vec3f(*(v + c for v, c in zip(p, center, strict=True))) for p in points]
        faces = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
        mesh = UsdGeom.Mesh.Define(self.stage, "/world/Geometry/" + name)
        mesh.CreatePointsAttr(points)
        mesh.CreateFaceVertexCountsAttr([4] * 6)
        mesh.CreateFaceVertexIndicesAttr([i for face in faces for i in face])
        mesh.CreateExtentAttr(UsdGeom.PointBased(mesh).ComputeExtent(points))
        mesh.CreateSubdivisionSchemeAttr("none")
        mesh.CreateOrientationAttr("rightHanded")
        normals = []
        for face in faces:
            normal = Gf.Cross(points[face[1]] - points[face[0]], points[face[2]] - points[face[0]]).GetNormalized()
            normals.extend([normal] * 4)
        mesh.CreateNormalsAttr(normals)
        mesh.SetNormalsInterpolation("faceVarying")
        mesh.CreateDisplayColorAttr([Gf.Vec3f(*self.source["materials"][material]["color"])])
        UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(self.materials[material])
        volume = math.prod(size)
        mass = volume * self.source["materials"][material]["density_kg_m3"]
        mesh.GetPrim().SetCustomDataByKey("synthetic:solidVolume_m3", volume)
        mesh.GetPrim().SetCustomDataByKey("synthetic:mass_kg", mass)
        self.mass += mass


def geometry_layer(path, source):
    stage = new_stage(path)
    g = Geometry(stage, source)
    h, w, d = .04445, .44, .4
    # Hollow shell: the front opening is assembled from rails and webs.
    g.box("Bottom", (0,0,.00075), (w,d,.0015))
    # The inset synthetic plaque replaces a patch of the top sheet.
    for label, center, size in (
        ("TopRear",(0,.03125,h-.00075),(w,.3375,.0015)),
        ("TopFront",(0,-.19125,h-.00075),(w,.0175,.0015)),
        ("TopLeft",(-.21,-.16,h-.00075),(.02,.045,.0015)),
        ("TopRight",(.085,-.16,h-.00075),(.27,.045,.0015)),
    ):
        g.box(label,center,size)
    for label, x in (("Left",-.21925),("Right",.21925)):
        g.box(label, (x,0,h/2), (.0015,d,h-.003))
    g.box("Rear", (0,.19925,h/2), (.437,.0015,h-.003), "DarkMetal")
    for label, z in (("FrontLowerRail",.007), ("FrontUpperRail",h-.007)):
        g.box(label,(0,-.19925,z),(.437,.0015,.011),"DarkMetal")
    for label, x in (("LeftEar",-.23065),("RightEar",.23065)):
        g.box(label,(x,-.198,h/2),(.0213,.004,h),"Aluminum")
    p = source["ports"]
    for i in range(p["count"]):
        x, y, z = p["first_x_m"] + i*p["spacing_m"], p["front_y_m"], p["height_z_m"]
        tag = f"Port{i+1:02}"
        # The visible opening and connection frame share the exact source dimensions.
        for side, sign in (("Lower",-1),("Upper",1)):
            g.box(tag+side,(x,y+.0075,z+sign*(p["opening_height_m"]+.001)/2),
                  (p["opening_width_m"]+.002,.015,.001),"Connector")
        for side, sign in (("Left",-1),("Right",1)):
            g.box(tag+side,(x+sign*(p["opening_width_m"]+.001)/2,y+.0075,z),
                  (.001,.015,p["opening_height_m"]),"Connector")
        g.box(tag+"Back",(x,y+.0155,z),(p["opening_width_m"],.001,p["opening_height_m"]),"DarkMetal")
        g.box(tag+"LED",(x+.014,y+.0005,z+.007),(.002,.001,.002),"LED")
        if i < p["count"]-1:
            g.box(tag+"Web",(x+.02,y+.00075,z),(.016,.0015,.01645),"DarkMetal")
    g.box("FrontLeftWeb",(-.195,y+.00075,z),(.047,.0015,.01645),"DarkMetal")
    g.box("FrontRightWeb",(.155,y+.00075,z),(.046,.0015,.01645),"DarkMetal")
    # Management jack is an integral copper connector, not a pluggable optic.
    for label, cx, cz, sx, sz in (("Lower",.19,z-.0065,.016,.001),
                                ("Upper",.19,z+.0065,.016,.001),
                                ("Left",.1825,z,.001,.012),
                                ("Right",.1975,z,.001,.012)):
        g.box("Management"+label,(cx,-.1925,cz),(sx,.015,sz),"Connector")
    g.box("ManagementBack",(.19,-.1845,z),(.014,.001,.012),"DarkMetal")
    g.box("FrontRightEnd",(.209,y+.00075,z),(.019,.0015,.01645),"DarkMetal")
    g.box("MainBoard",(0,.02,.005),(.39,.32,.002),"Board")
    g.box("ProcessorHeatsink",(0,.02,.017),(.08,.08,.02),"Aluminum")
    g.box("SyntheticNameplate",(-.125,-.16,h-.00075),(.15,.045,.0015),"SyntheticPlate")
    # A slotted rear grille is simplified by disconnected bars.
    for i in range(20):
        g.box(f"RearVent{i:02}",(-.19+i*.02,.1975,.024),(.01,.001,.022),"Connector")
    UsdPhysics.MassAPI.Apply(stage.GetDefaultPrim()).CreateMassAttr(g.mass)
    stage.GetRootLayer().Save()
    size = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default"]).ComputeWorldBound(stage.GetDefaultPrim()).ComputeAlignedRange().GetSize()
    return g.mass, size


def property_layer(path, source, mass, size):
    stage = new_stage(path)
    root = stage.GetDefaultPrim()
    values = dict(source["attributes"], **{"aif:core:weight": mass})
    with CSV.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    names = {r["USD Attribute Namespace"] for r in rows if r["USD Attribute Namespace"].startswith("aif:")}
    if names != set(values):
        raise ValueError(f"CSV/source attribute mismatch: missing={names-set(values)}, extra={set(values)-names}")
    for row in rows:
        name = row["USD Attribute Namespace"]
        if name not in values:
            continue
        attr = root.CreateAttribute(name, TYPES[row["Attribute Type"].lower()], custom=True)
        attr.Set(values[name])
        attr.SetCustomDataByKey("units", row["SI Unit Values"])
        attr.SetDocumentation(row["Description"])
        if row["Options"] != "Not required":
            attr.SetMetadata("allowedTokens", Vt.TokenArray(row["Options"].split(" | ")))
    extras = {"assetClass":("string","network-equipment"), "simreadyVersion":("string","0.3.0"),
              "assetDescription":("string",source["description"]),
              "sceneOptimizerVersion":("string","not used; procedural synthetic geometry"),
              "assetValidatorVersion":("string","simready-validate; see validation.json"),
              "assetCreationDate":("string",source["date"]),
              "connectsToModelDocumentation":("string","../README.md")}
    for name, (type_name,value) in extras.items():
        root.CreateAttribute("aif:core:"+name,TYPES[type_name],custom=True).Set(value)
    stage.GetRootLayer().Save()


def connection_layer(path, source):
    stage = new_stage(path)
    UsdGeom.Scope.Define(stage, "/world/ConnectionPoints")
    p = source["ports"]
    for i in range(p["count"]+1):
        management = i == p["count"]
        name = "management_01" if management else f"ethernet_{i+1:02}"
        port = UsdGeom.Xform.Define(stage,"/world/ConnectionPoints/"+name)
        port.CreatePurposeAttr("guide")
        port.AddTranslateOp().Set(Gf.Vec3d(.19 if management else p["first_x_m"]+i*p["spacing_m"],p["front_y_m"],p["height_z_m"]))
        # Local +Z points outward from the front (-Y), local +Y is equipment +Z.
        port.AddRotateXOp().Set(90)
        values = {"domain":("token","network"),"direction":("token","bidirectional"),
                  "system":("token","mgmt" if management else "high_speed_data"),
                  "disconnectType":("token","RJ45" if management else "OSFP"),
                  "serviceClearance":("float",.6),
                  "network:portWidth":("float",.014 if management else p["opening_width_m"]),
                  "network:portHeight":("float",.012 if management else p["opening_height_m"]),
                  "network:matingDepth":("float",p["mating_depth_m"]),
                  "network:portType":("token","RJ45" if management else "OSFP"),
                  "network:protocol":("token","Ethernet"),
                  "network:dataRate":("token","100Mbps" if management else "800GbE"),
                  "network:medium":("token","copper" if management else "fiber"),
                  "network:fabricRole":("token","mgmt" if management else "compute"),
                  "network:supportedLineRates":("token[]",["100Mbps"] if management else ["800GbE","400GbE"]),
                  "network:supportedConfigurations":("token[]",["1x100M"] if management else ["1x800G","2x400G"]),
                  "network:allowedTransceivers":("token[]",[] if management else ["DR4","FR4"]),
                  "network:hotPlugCapable":("bool",True)}
        for name,(type_name,value) in values.items():
            port.GetPrim().CreateAttribute("simready:connectionPoint:"+name,TYPES[type_name],custom=True).Set(value)
    stage.GetRootLayer().Save()


def entry_layer(path, source, mass, size):
    stage = new_stage(path)
    stage.GetRootLayer().subLayerPaths = [f"./layers/{NAME}_{part}.usda" for part in ("Geometry","Properties","ConnectionPoints")]
    metadata = {"author":"nvidia", "asset_name":NAME,"asset_type":"equipment",
                "asset_license":"CC-BY 4.0","category":"network-equipment",
                "source_file":"../source.json","usd_date_generated":source["date"],
                "qcode":source["qcode"],"rigid_body_count":0,
                "asset_extents":Gf.Vec3f(*size),"mass":float(mass),"synthetic":True}
    stage.GetRootLayer().customLayerData = {"SimReady_Metadata":metadata,
        **{key:metadata[key] for key in ("asset_name","asset_type","source_file","usd_date_generated")}}
    stage.GetRootLayer().Save()


def presentation(path):
    path.unlink(missing_ok=True)
    stage = Usd.Stage.CreateNew(str(path))
    root = UsdGeom.Xform.Define(stage,"/Presentation").GetPrim()
    stage.SetDefaultPrim(root)
    UsdGeom.SetStageUpAxis(stage,"Z")
    UsdGeom.SetStageMetersPerUnit(stage,1)
    UsdGeom.Xform.Define(stage,"/Presentation/Switch").GetPrim().GetReferences().AddReference(f"./asset/{NAME}.usda")
    camera = UsdGeom.Camera.Define(stage,"/Presentation/Camera")
    view = Gf.Matrix4d().SetLookAt(Gf.Vec3d(.62,-.96,.58),Gf.Vec3d(0,-.015,.01),Gf.Vec3d(0,0,1))
    camera.AddTransformOp().Set(view.GetInverse())
    camera.CreateFocalLengthAttr(65)
    camera.CreateHorizontalApertureAttr(36)
    camera.CreateVerticalApertureAttr(20.25)
    dome = UsdLux.DomeLight.Define(stage,"/Presentation/Dome")
    dome.CreateIntensityAttr(.8)
    key = UsdLux.DistantLight.Define(stage,"/Presentation/Key")
    key.CreateIntensityAttr(2.5)
    key.AddRotateXYZOp().Set(Gf.Vec3f(-35,-25,-35))
    fill = UsdLux.DistantLight.Define(stage,"/Presentation/Fill")
    fill.CreateIntensityAttr(1.5)
    fill.AddRotateXYZOp().Set(Gf.Vec3f(65,0,10))
    stage.GetRootLayer().Save()


def generate(destination=HERE):
    destination = Path(destination)
    source = json.loads((HERE/"source.json").read_text())
    asset = destination/"asset"
    layers = asset/"layers"
    mass,size = geometry_layer(layers/f"{NAME}_Geometry.usda",source)
    property_layer(layers/f"{NAME}_Properties.usda",source,mass,size)
    connection_layer(layers/f"{NAME}_ConnectionPoints.usda",source)
    entry_layer(asset/f"{NAME}.usda",source,mass,size)
    presentation(destination/"preview.usda")
    print(f"Generated {NAME}: mass={mass:.6f} kg, extent={tuple(size)} m")


def render(destination=HERE, renderer=None):
    from PIL import Image, ImageOps
    destination = Path(destination)
    command = ["usdrecord","--camera","/Presentation/Camera","--imageWidth","1600"]
    if renderer:
        command += ["--renderer",renderer]
    subprocess.run(command+[str(destination/"preview.usda"),str(destination/"preview.png")],check=True)
    with Image.open(destination/"preview.png").convert("RGBA") as rendered:
        background = Image.new("RGBA",rendered.size,"white")
        background.alpha_composite(rendered)
        preview = background.convert("RGB")
        preview.save(destination/"preview.png")
        thumbnail = Image.new("RGB",(256,256),"white")
        scaled = ImageOps.contain(preview,(256,256),Image.Resampling.LANCZOS)
        thumbnail.paste(scaled,((256-scaled.width)//2,(256-scaled.height)//2))
        target = destination/"asset/.thumbs/256x256"/f"{NAME}.usda.png"
        target.parent.mkdir(parents=True,exist_ok=True)
        thumbnail.save(target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=HERE)
    parser.add_argument("--render",action="store_true")
    parser.add_argument("--renderer",help="Hydra renderer advertised by usdrecord")
    args = parser.parse_args()
    generate(args.output)
    if args.render:
        render(args.output,args.renderer)
