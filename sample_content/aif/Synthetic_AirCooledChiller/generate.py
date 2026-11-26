# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Build the fictional air-cooled chiller from its CSV contract and source.json.

Requires OpenUSD Python. The source ratings are invented examples, not OEM data.
Rendering is separate: usdrecord --camera /Presentation/Camera --imageWidth 1600
sample_content/aif/Synthetic_AirCooledChiller/preview.usda preview.png
"""
import argparse
import csv
import json
import math
import subprocess
from pathlib import Path

from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux, UsdPhysics, UsdShade, Vt

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CSV = REPO / "standards/equipment-classes/aif-v0.3/air-cooled-chiller.csv"
NAME = "Synthetic_AirCooledChiller"
TYPES = {
    "float": Sdf.ValueTypeNames.Float, "int": Sdf.ValueTypeNames.Int,
    "bool": Sdf.ValueTypeNames.Bool, "string": Sdf.ValueTypeNames.String,
    "token": Sdf.ValueTypeNames.Token,
    "float_array": Sdf.ValueTypeNames.FloatArray,
    "int_array": Sdf.ValueTypeNames.IntArray,
    "token_array": Sdf.ValueTypeNames.TokenArray,
}


def source_data():
    return json.loads((HERE / "source.json").read_text())


def contract_rows():
    with CSV.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def new_stage(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    stage = Usd.Stage.CreateNew(str(path))
    root = UsdGeom.Xform.Define(stage, "/world").GetPrim()
    stage.SetDefaultPrim(root)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdPhysics.SetStageKilogramsPerUnit(stage, 1.0)
    return stage


class Geometry:
    """Closed mesh solids; mass is the sum of solid volumes times densities."""

    def __init__(self, stage, source):
        self.stage = stage
        self.source = source
        self.mass = 0.0
        self.materials = {}
        UsdGeom.Scope.Define(stage, "/world/Geometry")
        for name, item in source["materials"].items():
            material = UsdShade.Material.Define(stage, "/world/Looks/" + name)
            shader = UsdShade.Shader.Define(stage, material.GetPath().AppendChild("Surface"))
            shader.CreateIdAttr("UsdPreviewSurface")
            shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*item["color"]))
            shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(item["roughness"])
            shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(item["metallic"])
            material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
            self.materials[name] = material

    def mesh(self, name, points, faces, material, volume):
        mesh = UsdGeom.Mesh.Define(self.stage, "/world/Geometry/" + name)
        points = [Gf.Vec3f(*point) for point in points]
        mesh.CreatePointsAttr(points)
        mesh.CreateFaceVertexCountsAttr([len(face) for face in faces])
        mesh.CreateFaceVertexIndicesAttr([i for face in faces for i in face])
        mesh.CreateSubdivisionSchemeAttr("none")
        mesh.CreateOrientationAttr("rightHanded")
        normals = []
        for face in faces:
            normal = Gf.Cross(points[face[1]] - points[face[0]], points[face[2]] - points[face[0]]).GetNormalized()
            normals.extend([normal] * len(face))
        mesh.CreateNormalsAttr(normals)
        mesh.SetNormalsInterpolation(UsdGeom.Tokens.faceVarying)
        mesh.CreateExtentAttr(UsdGeom.PointBased(mesh).ComputeExtent(points))
        mesh.CreateDisplayColorAttr([Gf.Vec3f(*self.source["materials"][material]["color"])])
        UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(self.materials[material])
        mass = volume * self.source["materials"][material]["density_kg_m3"]
        mesh.GetPrim().SetCustomDataByKey("synthetic:solidVolume_m3", float(volume))
        mesh.GetPrim().SetCustomDataByKey("synthetic:mass_kg", float(mass))
        self.mass += mass

    def box(self, name, center, size, material="paintedSteel", rotation=0.0):
        x, y, z = (v / 2 for v in size)
        points = [(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),
                  (-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
        angle = math.radians(rotation)
        points = [(a*math.cos(angle)-b*math.sin(angle)+center[0],
                   a*math.sin(angle)+b*math.cos(angle)+center[1],c+center[2]) for a,b,c in points]
        faces = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
        self.mesh(name, points, faces, material, math.prod(size))

    def tube(self, name, center, outer, inner, length, material="aluminum", axis="Z", segments=32):
        points = []
        for radius, z in ((outer,-length/2),(outer,length/2),(inner,-length/2),(inner,length/2)):
            for i in range(segments):
                angle = 2*math.pi*i/segments
                a,b,c = radius*math.cos(angle),radius*math.sin(angle),z
                if axis == "X":
                    a,b,c = c,a,b
                elif axis == "Y":
                    a,b,c = a,c,-b
                points.append((a+center[0],b+center[1],c+center[2]))
        faces = []
        for i in range(segments):
            j=(i+1)%segments
            faces.extend([(i,j,segments+j,segments+i),
                          (2*segments+j,2*segments+i,3*segments+i,3*segments+j),
                          (j,i,2*segments+i,2*segments+j),
                          (segments+i,segments+j,3*segments+j,3*segments+i)])
        # Polygonal cross-section, rather than the ideal circle, matches authored geometry.
        area = segments*math.sin(2*math.pi/segments)*(outer*outer-inner*inner)/2
        self.mesh(name, points, faces, material, area*length)

    def aperture_plate(self, name, center, size, radius, material="enclosureSteel", axis="Z"):
        """Closed rectangular plate with a real circular opening, not a painted disk."""
        half_x,half_y,thickness=size[0]/2,size[1]/2,size[2]
        angles={2*math.pi*i/64 for i in range(64)}
        angles.update(math.atan2(y,x) % (2*math.pi) for x in (-half_x,half_x) for y in (-half_y,half_y))
        angles=sorted(angles)
        count=len(angles)
        points=[]
        for outer,z in ((True,-thickness/2),(True,thickness/2),(False,-thickness/2),(False,thickness/2)):
            for angle in angles:
                cosine,sine=math.cos(angle),math.sin(angle)
                distance=min(half_x/max(abs(cosine),1e-12),half_y/max(abs(sine),1e-12)) if outer else radius
                x,y=distance*cosine,distance*sine
                a,b,c=(z,x,y) if axis == "X" else (x,y,z)
                points.append((a+center[0],b+center[1],c+center[2]))
        faces=[]
        for i in range(count):
            j=(i+1)%count
            faces.extend([(i,j,count+j,count+i),
                          (2*count+j,2*count+i,3*count+i,3*count+j),
                          (j,i,2*count+i,2*count+j),
                          (count+i,count+j,3*count+j,3*count+i)])
        hole_area=sum(radius*radius*math.sin(angles[(i+1)%count]-angle)/2 for i,angle in enumerate(angles))
        self.mesh(name,points,faces,material,(size[0]*size[1]-hole_area)*thickness)


def geometry_layer(path, source):
    stage = new_stage(path)
    g = Geometry(stage, source)
    for side in (-1,1):
        tag = 'L' if side<0 else 'R'
        for z in (.003,.147):
            g.box(f"SkidRail_{tag}_Flange_{int(z*1000)}", (0,side*.72,z), (4.8,.13,.006))
        for y in (-.062,.062):
            g.box(f"SkidRail_{tag}_Web_{'L' if y<0 else 'R'}", (0,side*.72+y,.075), (4.8,.006,.138))
    for x in (-2.2,0,2.2):
        tag = str(x).replace('-','N').replace('.','_')
        g.box(f"Crossmember_{tag}_Web", (x,0,.19), (.006,1.65,.08))
        for z in (.153,.227):
            g.box(f"Crossmember_{tag}_Flange_{int(z*1000)}", (x,0,z), (.10,1.65,.006))
    # Closed service panels, dense condenser banks and a continuous pierced deck
    # make the simplified unit a coherent packaged outdoor chiller.
    fan_centers = source["geometry"]["fan_centers_x_m"]
    for side in (-1,1):
        tag = "L" if side < 0 else "R"
        g.box(f"CabinetSide_{tag}", (-2.0445,side*.93,1.11625), (.559,.004,1.7725), "enclosureSteel")
        g.box(f"CabinetEnd_{tag}", (-2.322 if side<0 else -1.767,0,1.11625), (.004,1.86,1.7725), "enclosureSteel")
        g.box(f"CabinetCap_{tag}", (-2.0445,0,.232 if side<0 else 2.0005), (.559,1.86,.004), "enclosureSteel")
    g.box("CabinetDoor", (-2.0445,-.938,1.11625), (.50,.003,1.64), "enclosureSteel")
    g.box("CabinetHandle", (-1.88,-.956,1.03), (.018,.025,.24), "blackSteel")
    g.box("SyntheticNameplate", (-2.0445,-.948,1.70), (.30,.012,.11), "blue")
    g.box("ServicePanel_Floor", (.295,0,.232), (4.12,1.86,.004), "enclosureSteel")
    for side in (-1,1):
        side_tag="L" if side<0 else "R"
        for bay,x in enumerate(fan_centers,1):
            g.box(f"ServicePanel_{side_tag}_{bay}", (x,side*.932,.513), (1.01,.004,.546), "enclosureSteel")
            g.box(f"ServicePanel_{side_tag}_{bay}_Handle", (x+.34,side*.951,.53), (.018,.025,.12), "blackSteel")
            g.box(f"CondenserCore_{side_tag}_{bay}", (x,side*.81,1.365), (1.00,.24,1.13), "condenserCore")
            for edge in (-1,1):
                g.box(f"CoilFrame_{side_tag}_{bay}_Vertical_{'L' if edge<0 else 'R'}", (x+edge*.495,side*.932,1.365), (.025,.025,1.15), "blackSteel")
                g.box(f"CoilFrame_{side_tag}_{bay}_Horizontal_{'L' if edge<0 else 'R'}", (x,side*.932,1.365+edge*.565), (1.015,.025,.025), "blackSteel")
            for fin in range(42):
                g.box(f"CoilFin_{side_tag}_{bay}_{fin:02}", (x-.48+fin*.96/41,side*.938,1.365), (.004,.012,1.075), "coilFin")
        g.box(f"FanDeck_SideRim_{side_tag}", (.295,side*.93,1.9705), (4.12,.045,.051), "enclosureSteel")
        for end,x in enumerate((-1.765,2.355),1):
            g.box(f"CornerPost_{side_tag}_{end}", (x,side*.925,1.113), (.035,.035,1.766), "enclosureSteel")
    # The right-hand access panel has real clearance openings around the pipes.
    g.box("ServicePanel_End_Upper", (2.355,0,1.3625), (.004,1.86,1.185), "enclosureSteel")
    g.box("ServicePanel_End_Lower", (2.355,0,.39), (.004,1.86,.32), "enclosureSteel")
    for tag,y,width in (("L",-.77,.32),("Middle",0,.78),("R",.77,.32)):
        g.box("ServicePanel_End_Bridge_"+tag, (2.355,y,.66), (.004,width,.22), "enclosureSteel")
    for index,y in enumerate((-.5,.5),1):
        g.aperture_plate(f"ServicePanel_End_PipeOpening_{index}",(2.355,y,.66),(.22,.22,.004),.06,axis="X")
    for index,x in enumerate(fan_centers,1):
        g.aperture_plate(f"FanDeck_{index}",(x,0,1.999),(1.03,1.86,.006),.465)
        g.tube(f"Fan_{index}_Shroud", (x,0,2.08), .48,.475,.16,"blackSteel")
        g.tube(f"Fan_{index}_Motor", (x,0,2.06), .075,.001,.12,"blackSteel")
        for support in (0,90):
            g.box(f"Fan_{index}_MotorBridge_{support}",(x,0,2.025),(.94,.025,.018),"blackSteel",support)
        for blade in range(6):
            angle=blade*60
            a=math.radians(angle)
            g.box(f"Fan_{index}_Blade_{blade+1}",(x+.245*math.cos(a),.245*math.sin(a),2.08),(.32,.105,.014),"fanBlade",angle+18)
        for guard in range(3):
            g.tube(f"Fan_{index}_Guard_{guard+1}", (x,0,2.177), .16+.12*guard,.155+.12*guard,.006,"blackSteel")
        for cross in (0,90):
            g.box(f"Fan_{index}_GuardCross_{cross}",(x,0,2.177),(.92,.008,.008),"blackSteel",cross)
        for support in range(4):
            a=math.radians(support*90)
            g.box(f"Fan_{index}_GuardPost_{support}",(x+.46*math.cos(a),.46*math.sin(a),2.166),(.008,.008,.022),"blackSteel")
    for index,x in enumerate((-.7,.7),1):
        g.tube(f"Compressor_{index}_Shell", (x,0,.69), .18,.176,.7,"blackSteel")
        for z in (.34,1.04):
            g.tube(f"Compressor_{index}_Cap_{int(z*100)}", (x,0,z), .18,.001,.012,"blackSteel")
        g.box(f"Compressor_{index}_Foot",(x,0,.324),(.42,.42,.008),"blackSteel")
    g.tube("EvaporatorShell", (1.55,0,.55), .21,.19,1.1,"aluminum",axis="X")
    # Separate inlet and outlet branches connect each visible pipe to a
    # different point on the evaporator barrel rather than short-circuiting it.
    g.tube("Header_Supply_Y", (2.04,-.25,.66), .05715,.05,.5,"copper",axis="Y")
    g.tube("Header_Supply_X", (2.07,-.5,.66), .05715,.05,.06,"copper",axis="X")
    g.tube("Header_Return_Y", (1.06,.25,.66), .05715,.05,.5,"copper",axis="Y")
    g.tube("Header_Return_X", (1.58,.5,.66), .05715,.05,1.04,"copper",axis="X")
    for name,y in (("EvaporatorSupply",-.5),("EvaporatorReturn",.5)):
        g.tube(name+"Pipe", (2.35,y,.66), .05715,.05,.5,"copper",axis="X")
        g.tube(name+"Flange", (2.59,y,.66), .10,.05,.025,"blue",axis="X")
    g.box("ElectricalInletPlate",(-2.324,-.35,.7),(.012,.16,.20),"blackSteel")
    UsdPhysics.MassAPI.Apply(stage.GetDefaultPrim()).CreateMassAttr(g.mass)
    stage.GetRootLayer().Save()
    bounds = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_]).ComputeWorldBound(stage.GetDefaultPrim()).ComputeAlignedRange()
    return g.mass, bounds.GetSize()


def properties_layer(path, source, mass, size):
    rows = contract_rows()
    attributes = source["attributes"]
    names = {row["USD Attribute Namespace"] for row in rows}
    unknown = set(attributes) - names
    if unknown:
        raise ValueError(f"Unknown chiller attributes: {sorted(unknown)}")
    required = {
        row["USD Attribute Namespace"] for row in rows
        if row["Needed (Required / Optional)"].startswith("Required")
        or row["USD Attribute Namespace"].startswith("aif:spec:performanceMap")
    }
    missing = required - set(attributes)
    if missing:
        raise ValueError(f"Missing required chiller attributes: {sorted(missing)}")
    if attributes["aif:spec:performanceModelType"] != "TABULAR":
        raise ValueError("AirCooledChiller requires performanceModelType = TABULAR")
    stage = new_stage(path)
    root = stage.GetDefaultPrim()
    for row in rows:
        name = row["USD Attribute Namespace"]
        if name not in attributes:
            continue
        attr = root.CreateAttribute(name, TYPES[row["Attribute Type"]], custom=True)
        attr.Set(attributes[name])
        attr.SetCustomDataByKey("units", row["SI Unit Values"])
        attr.SetDocumentation(row["Description"])
        if row["Options"] != "Not required":
            attr.SetMetadata("allowedTokens", Vt.TokenArray(row["Options"].split(" | ")))
    common = {
        "manufacturer": ("string","NVIDIA synthetic example; no OEM"),
        "modelNumber": ("string","SYN-ACC-100"),
        "weight": ("float",mass), "height": ("float",size[2]*1000),
        "width": ("float",size[0]*1000), "depth": ("float",size[1]*1000),
        "installationClearance": ("float",1000.0), "accessibilityRequirement": ("float",800.0),
        "assetVersion": ("string","1.0.0"), "assetClass": ("string","AirCooledChiller"),
        "simreadyVersion": ("string","0.3.0"), "sceneOptimizerVersion": ("string","not used; procedural synthetic geometry"),
        "assetValidatorVersion": ("string","simready-validate 2026.10.0"),
        "assetDescription": ("string",source["description"]),
        "connectsToModelDocumentation": ("string","../README.md"),
        "assetCreationDate": ("string",source["date"]),
    }
    for name,(type_name,value) in common.items():
        root.CreateAttribute("aif:core:"+name,TYPES[type_name],custom=True).Set(value)
    stage.GetRootLayer().Save()


def port_frame(stage, name, position, normal):
    frame = UsdGeom.Xform.Define(stage, "/world/ConnectionPoints/"+name)
    frame.CreatePurposeAttr("guide")
    z = Gf.Vec3d(*normal).GetNormalized()
    vertical = Gf.Vec3d(0,0,1) if abs(z[2]) < .9 else Gf.Vec3d(0,1,0)
    x = Gf.Cross(vertical,z).GetNormalized()
    y = Gf.Cross(z,x).GetNormalized()
    transform = Gf.Matrix4d(1)
    for i,axis in enumerate((x,y,z)):
        transform.SetRow(i,Gf.Vec4d(*axis,0))
    transform.SetRow(3,Gf.Vec4d(*position,1))
    frame.AddTransformOp().Set(transform)
    return frame.GetPrim()


def connection_layer(path, source):
    stage = new_stage(path)
    UsdGeom.Scope.Define(stage,"/world/ConnectionPoints")
    for name,port in source["ports"].items():
        prim = port_frame(stage,name,port["position"],port["normal"])
        for name,(type_name,value) in port["properties"].items():
            prim.CreateAttribute("simready:connectionPoint:"+name,TYPES[type_name],custom=True).Set(value)
    stage.GetRootLayer().Save()


def entry_layer(path, source, mass, size):
    stage = new_stage(path)
    stage.GetRootLayer().subLayerPaths = [f"./layers/{NAME}_Geometry.usda",f"./layers/{NAME}_Properties.usda",f"./layers/{NAME}_ConnectionPoints.usda"]
    stage.GetRootLayer().customLayerData = {"SimReady_Metadata": {
        "author":"nvidia", "asset_name":NAME, "asset_type":"equipment",
        "asset_license":"CC-BY 4.0", "category":"AirCooledChiller",
        "source_file":"../source.json", "usd_date_generated":source["date"],
        "qcode":source["qcode"], "rigid_body_count":0,
        "asset_extents":Gf.Vec3f(*size), "mass":float(mass),
        "synthetic":True,
    }}
    stage.GetRootLayer().Save()


def presentation(path):
    if path.exists():
        path.unlink()
    stage=Usd.Stage.CreateNew(str(path))
    root=UsdGeom.Xform.Define(stage,"/Presentation").GetPrim()
    stage.SetDefaultPrim(root)
    UsdGeom.SetStageUpAxis(stage,"Z")
    UsdGeom.SetStageMetersPerUnit(stage,1)
    asset=UsdGeom.Xform.Define(stage,"/Presentation/Chiller").GetPrim()
    asset.GetReferences().AddReference(f"./asset/{NAME}.usda")
    camera=UsdGeom.Camera.Define(stage,"/Presentation/Camera")
    view=Gf.Matrix4d().SetLookAt(Gf.Vec3d(6.8,-9.4,6.2),Gf.Vec3d(.1,0,1.1),Gf.Vec3d(0,0,1))
    camera.AddTransformOp().Set(view.GetInverse())
    camera.CreateFocalLengthAttr(65)
    camera.CreateHorizontalApertureAttr(36)
    camera.CreateVerticalApertureAttr(24)
    dome=UsdLux.DomeLight.Define(stage,"/Presentation/Dome")
    dome.CreateIntensityAttr(.7)
    dome.CreateColorAttr(Gf.Vec3f(.8,.88,1))
    key=UsdLux.DistantLight.Define(stage,"/Presentation/Key")
    key.CreateIntensityAttr(2.5)
    key.CreateAngleAttr(1)
    key.AddRotateXYZOp().Set(Gf.Vec3f(-35,-25,-35))
    ground=UsdGeom.Mesh.Define(stage,"/Presentation/Ground")
    ground.CreatePointsAttr([(-100,-100,-.005),(100,-100,-.005),(100,100,-.005),(-100,100,-.005)])
    ground.CreateFaceVertexCountsAttr([4])
    ground.CreateFaceVertexIndicesAttr([0,1,2,3])
    ground.CreateSubdivisionSchemeAttr("none")
    ground.CreateDisplayColorAttr([Gf.Vec3f(.16,.18,.21)])
    material=UsdShade.Material.Define(stage,"/Presentation/GroundMaterial")
    shader=UsdShade.Shader.Define(stage,"/Presentation/GroundMaterial/Surface")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor",Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(.16,.18,.21))
    shader.CreateInput("roughness",Sdf.ValueTypeNames.Float).Set(.95)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(),"surface")
    UsdShade.MaterialBindingAPI.Apply(ground.GetPrim()).Bind(material)
    stage.GetRootLayer().Save()


def generate(destination=HERE):
    source=source_data()
    asset=destination/"asset"
    layers=asset/"layers"
    mass,size=geometry_layer(layers/f"{NAME}_Geometry.usda",source)
    properties_layer(layers/f"{NAME}_Properties.usda",source,mass,size)
    connection_layer(layers/f"{NAME}_ConnectionPoints.usda",source)
    entry_layer(asset/f"{NAME}.usda",source,mass,size)
    presentation(destination/"preview.usda")
    print(f"Generated {NAME}: {len(source['attributes'])} chiller attributes, mass {mass:.3f} kg, extent {tuple(size)} m")


def render(destination=HERE, renderer=None):
    """Render the composed presentation USD and create the publishing thumbnail."""
    from PIL import Image, ImageOps

    destination = Path(destination)
    output = destination / "preview.png"
    command = ["usdrecord", "--camera", "/Presentation/Camera", "--imageWidth", "1600"]
    if renderer:
        command.extend(["--renderer", renderer])
    subprocess.run(command + [str(destination / "preview.usda"), str(output)], check=True)
    with Image.open(output).convert("RGBA") as rendered:
        background = Image.new("RGBA", rendered.size, "white")
        background.alpha_composite(rendered)
        preview = background.convert("RGB")
        preview.save(output)
        thumbnail = Image.new("RGB", (256, 256), "white")
        scaled = ImageOps.contain(preview, (256, 256), Image.Resampling.LANCZOS)
        thumbnail.paste(scaled, ((256-scaled.width)//2, (256-scaled.height)//2))
        target = destination / "asset/.thumbs/256x256" / f"{NAME}.usda.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        thumbnail.save(target)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=HERE)
    parser.add_argument("--render", action="store_true", help="Render the USD preview and publishing thumbnail")
    parser.add_argument("--renderer", help="Hydra renderer exposed by usdrecord on this host")
    args = parser.parse_args()
    generate(args.output)
    if args.render:
        render(args.output, args.renderer)
