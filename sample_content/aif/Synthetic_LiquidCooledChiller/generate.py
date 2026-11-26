# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Build the fictional liquid-cooled chiller from its CSV contract and source.json.

Requires OpenUSD Python. The source ratings are invented examples, not OEM data.
Rendering is separate: usdrecord --camera /Presentation/Camera --imageWidth 1600
sample_content/aif/Synthetic_LiquidCooledChiller/preview.usda preview.png
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
CSV = REPO / "standards/equipment-classes/aif-v0.3/liquid-cooled-chiller.csv"
NAME = "Synthetic_LiquidCooledChiller"
TYPES = {
    "float": Sdf.ValueTypeNames.Float, "int": Sdf.ValueTypeNames.Int,
    "bool": Sdf.ValueTypeNames.Bool, "string": Sdf.ValueTypeNames.String,
    "token": Sdf.ValueTypeNames.Token, "float3": Sdf.ValueTypeNames.Float3,
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

    def waterbox_cover(self, name, center, head_radius, bore_radius, offset, side, material):
        """One half of a circular access cover, with its own open nozzle bore."""
        # Trace the perimeter of the semicircle from the nozzle center. This
        # gives the annular mesh matching inner/outer vertices on every ray.
        corners = [math.atan2(z, -side * offset) % math.tau for z in (-head_radius, head_radius)]
        angles = sorted({math.tau * i / 64 for i in range(64)} | set(corners))
        outer, hole = [], []
        for a in angles:
            dy, dz = math.cos(a), math.sin(a)
            proj = side * offset * dy
            distance = -proj + math.sqrt(proj * proj + head_radius**2 - offset**2)
            if side * dy < -1e-10:
                distance = min(distance, -side * offset / dy)
            outer.append((side * offset + distance * dy, distance * dz))
            hole.append((side * offset + bore_radius * dy, bore_radius * dz))
        self.ring_profile(name, center, outer, hole, .025, material)

    def ring_profile(self, name, center, outside, inside, thickness, material):
        n = len(outside)
        points = [(center[0]+dx, center[1]+y, center[2]+z)
                  for outline, dx in ((outside, -thickness/2), (outside, thickness/2),
                                      (inside, -thickness/2), (inside, thickness/2))
                  for y,z in outline]
        faces = []
        for i in range(n):
            j = (i+1) % n
            faces.extend([(i,j,n+j,n+i), (2*n+j,2*n+i,3*n+i,3*n+j),
                          (j,i,2*n+i,2*n+j), (n+i,n+j,3*n+j,3*n+i)])
        def area(poly):
            return sum(y*poly[(i+1)%n][1] - z*poly[(i+1)%n][0]
                       for i,(y,z) in enumerate(poly)) / 2
        self.mesh(name, points, faces, material, (area(outside)-area(inside))*thickness)

    def mating_flange(self, name, position, bore_radius, neck_radius, thickness, material):
        """Single closed annulus with open bolt holes around an open fluid bore."""
        x, cy, cz = position
        bolt_count, outer_radius = 8, neck_radius + .049
        pitch_radius, hole_radius = neck_radius + .025, .0095
        half_sector = math.pi / bolt_count
        points, faces, by_position = [], [], {}
        face_area = 0

        def vertex(axial, y, z):
            key = (axial, round(y, 9), round(z, 9))
            if key not in by_position:
                by_position[key] = len(points)
                points.append((x+axial, cy+y, cz+z))
            return by_position[key]

        # Each sector has one bolt hole. Trace its outer perimeter, project
        # that perimeter onto the hole, then join neighboring sectors using
        # shared vertices on their radial edges. Only exposed surfaces close.
        for sector in range(bolt_count):
            axis = sector * math.tau / bolt_count
            hy, hz = pitch_radius*math.cos(axis), pitch_radius*math.sin(axis)
            boundary = []
            for edge in range(4):
                for k in range(12):
                    f = k / 12
                    if edge == 0:
                        radius, angle = outer_radius, axis + (2*f-1)*half_sector
                    elif edge == 1:
                        radius, angle = (1-f)*outer_radius+f*bore_radius, axis+half_sector
                    elif edge == 2:
                        radius, angle = bore_radius, axis + (1-2*f)*half_sector
                    else:
                        radius, angle = (1-f)*bore_radius+f*outer_radius, axis-half_sector
                    boundary.append((radius*math.cos(angle), radius*math.sin(angle)))
            hole = []
            for y,z in boundary:
                factor = hole_radius / math.hypot(y-hy, z-hz)
                hole.append((hy+(y-hy)*factor, hz+(z-hz)*factor))
            for i,(y,z) in enumerate(boundary):
                j = (i+1) % len(boundary)
                yj,zj = boundary[j]
                yi,zi = hole[i]
                yk,zk = hole[j]
                face_area += (y*zj-z*yj - yi*zk+zi*yk)/2
                outside = [vertex(d, y, z) for d in (-thickness, 0)]
                outer_next = [vertex(d, yj, zj) for d in (-thickness, 0)]
                inner = [vertex(d, yi, zi) for d in (-thickness, 0)]
                inner_next = [vertex(d, yk, zk) for d in (-thickness, 0)]
                faces.append((outside[1], outer_next[1], inner_next[1], inner[1]))
                faces.append((inner[0], inner_next[0], outer_next[0], outside[0]))
                faces.append((inner[0], inner[1], inner_next[1], inner_next[0]))
                if i//12 in (0, 2):
                    faces.append((outside[0], outer_next[0], outer_next[1], outside[1]))
        self.mesh(name, points, faces, material, face_area * thickness)

    def rounded_pipe(self, name, centerline, outer, inner, material, segments=16):
        """Sweep an open-bore tube along a non-branching, coplanar centerline."""
        path = [Gf.Vec3d(*p) for p in centerline]
        binormal = Gf.Cross(path[1]-path[0], path[-1]-path[-2]).GetNormalized()
        points = []
        for radius in (outer, inner):
            for i, center in enumerate(path):
                tangent = (path[min(i+1,len(path)-1)]-path[max(0,i-1)]).GetNormalized()
                normal = Gf.Cross(binormal, tangent).GetNormalized()
                for k in range(segments):
                    a = math.tau * k / segments
                    points.append(center + radius*(normal*math.cos(a)+binormal*math.sin(a)))
        rows = len(path)
        outer_count = rows * segments
        faces = []
        for k in range(segments):
            k2 = (k+1) % segments
            for i in range(rows-1):
                v, w = i*segments+k, i*segments+k2
                faces.append((v,w,w+segments,v+segments))
                faces.append((outer_count+v+segments,outer_count+w+segments,outer_count+w,outer_count+v))
            a, b = (rows-1)*segments+k, (rows-1)*segments+k2
            faces.extend([(k2,k,outer_count+k,outer_count+k2),(a,b,outer_count+b,outer_count+a)])
        volume = sum(Gf.Dot(points[f[0]], Gf.Cross(points[f[i]], points[f[i+1]]))
                     for f in faces for i in range(1, len(f)-1)) / 6
        self.mesh(name, points, faces, material, abs(volume))


def skid_and_supports(g, shell_z, shell_radius):
    for tag, y in (("L", -.78), ("R", .78)):
        for z in (.006, .174):
            g.box(f"SkidRail_{tag}_Flange_{int(z*1000)}", (0,y,z), (3.6,.16,.012))
        g.box("SkidRail_"+tag+"_Web", (0,y,.09), (3.6,.012,.156))
    for i,x in enumerate((-1.40,-.95,.90,1.40)):
        g.box(f"Crossmember_{i}", (x,0,.215), (.16,1.72,.07))
    for label,y in (("Evaporator",-.5),("Condenser",.5)):
        for i,x in enumerate((-.95,.90)):
            g.box(f"{label}SaddleFoot_{i}", (x,y,.265), (.28,.48,.03))
            # A continuous formed steel strap cradles the lower face of each shell.
            r = shell_radius + (.022 if label == "Evaporator" else 0)
            for side in (-1,1):
                ztop = shell_z - r*math.sqrt(1-(.18/r)**2)
                g.box(f"{label}SaddleWeb_{i}_{'L' if side < 0 else 'R'}",
                      (x,y+side*.18,(.28+ztop)/2), (.19,.022,ztop-.28))
            g.tube(f"{label}SaddleBand_{i}",(x,y,shell_z),r+.007,r,.10,"paintedSteel",axis="X",segments=64)


def exchanger(g, source, circuit, y):
    dimensions = source["geometry"]
    length = dimensions["shell_length_m"]
    radius = dimensions["shell_outside_radius_m"]
    z = dimensions["shell_center_height_m"]
    outside = dimensions[circuit.lower()+"_pipe_outside_diameter_m"]/2
    inside = dimensions[circuit.lower()+"_pipe_inside_diameter_m"]/2
    material = "shellPaint"
    g.tube(circuit+"Shell",(0,y,z),radius,radius-.010,length,material,axis="X",segments=64)
    if circuit == "Evaporator":
        g.tube("EvaporatorInsulatingJacket",(0,y,z),radius+.022,radius,length-.10,"insulation",axis="X",segments=64)
        for i,x in enumerate((-1.23,-.62,0,.62,1.23)):
            g.tube(f"JacketRetainingBand_{i}",(x,y,z),radius+.024,radius+.022,.016,"aluminum",axis="X",segments=64)
    for side in (-1,1):
        tag = "Rear" if side < 0 else "Front"
        x = side*(length/2+.018)
        g.tube(circuit+tag+"TubeSheet",(x,y,z),radius+.042,radius-.010,.036,material,axis="X",segments=64)
        for i in range(14):
            a = math.tau*i/14
            g.tube(f"{circuit}{tag}TubeSheetStud_{i}",(x-side*.026,y+(radius+.024)*math.cos(a),z+(radius+.024)*math.sin(a)),
                   .014,.001,.018,"aluminum",axis="X",segments=6)
    head_end = 1.636
    sheet_end = length/2 + .036
    chamber_end = head_end - .0125
    g.tube(circuit+"Waterbox",((sheet_end+chamber_end)/2,y,z),radius+.007,radius-.010,
           chamber_end-sheet_end,material,axis="X",segments=64)
    # Bolt-on front flange and divided cover leave both CP faces open.
    g.tube(circuit+"CoverRim",(head_end-.02,y,z),radius+.042,radius+.007,.04,material,axis="X",segments=64)
    for role in ("Supply", "Return"):
        port = source["ports"][circuit+role]
        end, nozzle_y, nozzle_z = port["position"]
        g.waterbox_cover(circuit+role+"Cover",(head_end,y,z),radius+.035,inside,abs(nozzle_y-y),
                         -1 if nozzle_y < y else 1,material)
        # Two shoulders on a cast nozzle; gasket and sealing rim remain distinct.
        start = head_end+.0125
        g.tube(circuit+role+"NozzleCollar",(start+.025,nozzle_y,nozzle_z),outside+.025,inside,.05,material,axis="X")
        flange_len = .032
        pipe_end = end-flange_len
        g.tube(circuit+role+"Pipe",((start+.05+pipe_end)/2,nozzle_y,nozzle_z),outside,inside,
               pipe_end-start-.05,material,axis="X")
        g.mating_flange(circuit+role+"Flange",(end,nozzle_y,nozzle_z),inside,outside,flange_len,material)
        # Split cover hardware is part of the asset; field mating faces remain free.
        for bolt in range(7):
            a = (bolt+.5)*math.pi/7 + (math.pi/2 if nozzle_y < y else -math.pi/2)
            g.tube(f"{circuit}{role}CoverBolt_{bolt}",(head_end+.022,y+(radius+.015)*math.cos(a),z+(radius+.015)*math.sin(a)),
                   .017,.001,.019,"aluminum",axis="X",segments=6)
    g.tube(circuit+"RearCover",(-sheet_end-.030,y,z),radius+.011,.001,.06,material,axis="X",segments=64)


def compressor(g, idx, x, z):
    label = f"Compressor_{idx}"
    # Stepped cast compressor and motor barrels share one horizontal shaft axis.
    g.box(label+"_Mount",(x,0,z-.235),(.79,.43,.055),"paintedSteel")
    for i, dx in enumerate((-.25,.25)):
        g.box(f"{label}_CrossBridge_{i}", (x+dx,0,1.12), (.085,1.10,.045),"paintedSteel")
    for direction in (-1,1):
        g.box(label+("_LeftWeb" if direction < 0 else "_RightWeb"),(x,direction*.16,z-.342),
              (.66,.029,.159),"paintedSteel")
    for part, dx, r, width in (("Shell",.125,.205,.44),("Motor",-.253,.16,.30),
                                ("BearingCover",.377,.145,.065),("MotorTail",-.431,.131,.052)):
        g.tube(label+"_"+part,(x+dx,0,z),r,r-.017,width,"paintedSteel",axis="X",segments=48)
    for dx,r in ((.408,.145),(-.460,.131)):
        g.tube(label+("_HeadPlate" if dx>0 else "_TailPlate"),(x+dx,0,z),r,.001,.012,"paintedSteel",axis="X")
    for i,dx in enumerate((-.407,-.31,-.22,-.13,-.083,.25,.344)):
        r = .17 if dx < -.095 else .215
        g.tube(f"{label}_CastingCollar_{i}",(x+dx,0,z),r,r-.015,.021,"shellPaint",axis="X")
    # Deep longitudinal fins along the electric motor, visible around its full circumference.
    for i in range(12):
        a=math.tau*i/12
        g.tube(f"{label}_MotorRib_{i}",(x-.25,.16*math.cos(a),z+.16*math.sin(a)),.011,.001,
               .275,"paintedSteel",axis="X",segments=6)
    g.box(label+"_TerminalEnclosure",(x-.24,-.03,z+.19),(.195,.16,.077),"enclosureSteel")
    for y, prefix, outer, material, dx in ((-.50,"Suction",.067,"insulation",.05),(.50,"Discharge",.043,"copper",.205)):
        # A formed elbow rises off each horizontal exchanger and enters its compressor laterally.
        side = 1 if y < 0 else -1
        bend=.095
        pipe_z = z+.032
        path=[(x+dx,y,.78+.31),(x+dx,y,pipe_z-bend)]
        for step in range(1,9):
            a=math.pi*step/16
            path.append((x+dx,y+side*bend*(1-math.cos(a)),pipe_z-bend+bend*math.sin(a)))
        path.append((x+dx,side*-.177,pipe_z))
        g.rounded_pipe(label+"_"+prefix+"Line",path,outer,outer-.008,material)
        g.tube(label+"_"+prefix+"Root",(x+dx,y,1.10),outer+.024,outer-.008,.040,"shellPaint")
    # A service valve on the discharge branch sits above the condenser nozzle.
    g.tube(label+"_ServiceValve",(x+.205,.50,1.19),.065,.035,.055,"aluminum")
    g.tube(label+"_ValveStem",(x+.205,.585,1.19),.016,.001,.09,"aluminum",axis="Y")
    g.tube(label+"_ValveWheel",(x+.205,.638,1.19),.058,.047,.016,"blackSteel",axis="Y")
    g.box(label+"_ValveSpoke",(x+.205,.638,1.19),(.104,.012,.010),"blackSteel")


def cabinet(g, source):
    # Sheet metal enclosure, formed doors, electrical hardware and a blank HMI.
    for side,tag in ((-1,"L"),(1,"R")):
        g.box("CabinetSide_"+tag,(-1.48,side*.28,1.06),(.52,.008,1.56),"enclosureSteel")
        g.box("CabinetEnd_"+tag,(-1.48+side*.26,0,1.06),(.008,.56,1.56),"enclosureSteel")
        g.box("CabinetCap_"+tag,(-1.48,0,1.06+side*.78),(.52,.56,.008),"enclosureSteel")
    g.box("CabinetDoor",(-1.48,-.289,1.06),(.49,.01,1.49),"shellPaint")
    g.box("CabinetHMISurround",(-1.48,-.309,1.55),(.245,.032,.16),"blackSteel")
    g.box("CabinetHMIGlass",(-1.48,-.332,1.55),(.203,.012,.113),"display")
    g.box("CabinetHandle",(-1.29,-.313,1.02),(.019,.027,.19),"blackSteel")
    for i in range(6):
        g.box(f"CabinetVentLouver_{i}",(-1.48,-.308,.50+i*.029),(.29,.022,.01),"paintedSteel")
    for i,z in enumerate((.435,.98,1.68)):
        g.box(f"CabinetHinge_{i}",(-1.718,-.300,z),(.022,.025,.064),"aluminum")
    # Reference the actual electrical frame for the outer face of the gland plate.
    x,y,z = source["ports"]["ElectricalInlet"]["position"]
    g.box("ElectricalInletPlate",(x+.006,y,z),(.012,.16,.20),"blackSteel")


def geometry_layer(path, source):
    stage = new_stage(path)
    g = Geometry(stage, source)
    dims = source["geometry"]
    skid_and_supports(g, dims["shell_center_height_m"], dims["shell_outside_radius_m"])
    exchanger(g,source,"Evaporator",-.5)
    exchanger(g,source,"Condenser",.5)
    for i,x in enumerate((-.68,.46),1):
        compressor(g,i,x,1.505)
    cabinet(g,source)
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
        raise ValueError("LiquidCooledChiller requires performanceModelType = TABULAR")
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
        "manufacturer": ("string","Synthetic"),
        "modelNumber": ("string",source["model_number"]),
        "weight": ("float",mass), "height": ("float",size[2]*1000),
        "width": ("float",size[0]*1000), "depth": ("float",size[1]*1000),
        "installationClearance": ("float",1000.0), "accessibilityRequirement": ("float",800.0),
        "assetVersion": ("string","1.1.0"), "assetClass": ("string","LiquidCooledChiller"),
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
        "asset_license":"CC-BY 4.0", "category":"LiquidCooledChiller",
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
    view=Gf.Matrix4d().SetLookAt(Gf.Vec3d(6.65,-8.65,4.7),Gf.Vec3d(.15,0,.85),Gf.Vec3d(0,0,1))
    camera.AddTransformOp().Set(view.GetInverse())
    camera.CreateFocalLengthAttr(65)
    camera.CreateHorizontalApertureAttr(36)
    camera.CreateVerticalApertureAttr(24)
    dome=UsdLux.DomeLight.Define(stage,"/Presentation/Dome")
    dome.CreateIntensityAttr(1.0)
    dome.CreateColorAttr(Gf.Vec3f(.8,.88,1))
    key=UsdLux.DistantLight.Define(stage,"/Presentation/Key")
    key.CreateIntensityAttr(3.5)
    key.CreateAngleAttr(1)
    key.AddRotateXYZOp().Set(Gf.Vec3f(-45,30,15))
    ground=UsdGeom.Mesh.Define(stage,"/Presentation/Ground")
    ground.CreatePointsAttr([(-100,-100,-.005),(100,-100,-.005),(100,100,-.005),(-100,100,-.005)])
    ground.CreateFaceVertexCountsAttr([4])
    ground.CreateFaceVertexIndicesAttr([0,1,2,3])
    ground.CreateSubdivisionSchemeAttr("none")
    ground.CreateDisplayColorAttr([Gf.Vec3f(.46,.48,.51)])
    material=UsdShade.Material.Define(stage,"/Presentation/GroundMaterial")
    shader=UsdShade.Shader.Define(stage,"/Presentation/GroundMaterial/Surface")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor",Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(.46,.48,.51))
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
