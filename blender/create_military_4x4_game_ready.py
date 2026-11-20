import bpy
import math
import os
from mathutils import Vector

# DayZ-style military 4x4 (procedural blockout)
# Blender 3.6+ / 4.x: Scripting -> Open -> this file -> Run Script.
# Creates the model and saves Military_4x4_GameReady.blend
# (next to this .py, or next to the open .blend, or in the home folder).

# ---------- reset ----------
if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
    for block in list(coll):
        if block.users == 0:
            coll.remove(block)


def mat(name, color, metallic=0.0, roughness=0.65):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    bs = m.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value = (*color, 1)
    bs.inputs["Metallic"].default_value = metallic
    bs.inputs["Roughness"].default_value = roughness
    return m


# Subtle procedural woodland camouflage for painted panels
camo = mat("Paint | Woodland camouflage", (0.16, 0.20, 0.12), 0.28, 0.78)
nt = camo.node_tree
bs = nt.nodes.get("Principled BSDF")
tex = nt.nodes.new("ShaderNodeTexNoise")
tex.inputs["Scale"].default_value = 3.2
tex.inputs["Detail"].default_value = 2.0
ramp = nt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements.remove(ramp.color_ramp.elements[1])
colors = [
    (0.0, (0.055, 0.070, 0.045, 1)),
    (0.34, (0.13, 0.17, 0.095, 1)),
    (0.63, (0.29, 0.30, 0.19, 1)),
    (0.84, (0.075, 0.085, 0.065, 1)),
]
for i, (pos, col) in enumerate(colors):
    e = ramp.color_ramp.elements[0] if i == 0 else ramp.color_ramp.elements.new(pos)
    e.position = pos
    e.color = col
nt.links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
nt.links.new(ramp.outputs["Color"], bs.inputs["Base Color"])

rubber = mat("Rubber | tire", (0.018, 0.021, 0.022), 0.0, 0.92)
glass = mat("Glass | dark tinted", (0.018, 0.035, 0.043), 0.25, 0.22)
metal = mat("Metal | dark olive steel", (0.075, 0.085, 0.071), 0.72, 0.48)
black = mat("Grille and trim", (0.012, 0.016, 0.015), 0.35, 0.72)
lamp = mat("Headlamp glass", (0.72, 0.68, 0.49), 0.12, 0.22)
red = mat("Tail lamp red", (0.38, 0.018, 0.012), 0.1, 0.28)
orange = mat("Indicator amber", (0.8, 0.22, 0.025), 0.05, 0.3)
seatmat = mat("Interior upholstery", (0.095, 0.105, 0.078), 0.0, 0.9)


def cube(name, loc, scale, material, bevel=0.04, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.object
    o.name = name
    o.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        o.data.materials.append(material)
    if bevel:
        mod = o.modifiers.new("Small game-ready edge bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        o.modifiers.new("Weighted corner normals", "WEIGHTED_NORMAL")
    return o


def cyl(name, loc, radius, depth, material, rot=(0, 0, 0), vertices=16):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth,
                                        location=loc, rotation=rot)
    o = bpy.context.object
    o.name = name
    if material:
        o.data.materials.append(material)
    bevel = o.modifiers.new("Edge bevel", "BEVEL")
    bevel.width = 0.025
    bevel.segments = 2
    o.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    return o


def uv_sphere(name, loc, scale, material):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = scale
    if material:
        o.data.materials.append(material)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return o


def beam(name, a, b, radius, material, vertices=8):
    mid = (Vector(a) + Vector(b)) / 2
    vec = Vector(b) - Vector(a)
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=vec.length, location=mid)
    o = bpy.context.object
    o.name = name
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = vec.to_track_quat('Z', 'Y')
    if material:
        o.data.materials.append(material)
    return o


# Vehicle coordinate convention: front = -X, rear = +X, left/right = +/-Y
# Chassis, underbody and armor tub
cube("Main chassis", (0, 0, 0.93), (4.55, 1.78, 0.34), black, 0.08)
cube("Lower armored body", (0, 0, 1.30), (4.45, 2.02, 0.82), camo, 0.16)
cube("Front hood", (-1.47, 0, 1.78), (1.55, 2.00, 0.20), camo, 0.10)
cube("Rear body deck", (1.62, 0, 1.72), (1.18, 2.00, 0.22), camo, 0.08)

# Cabin roof and pillars
cube("Cabin roof", (0.34, 0, 2.78), (2.72, 2.03, 0.20), camo, 0.12)
for y in (-0.91, 0.91):
    for x in (-0.91, 1.43):
        beam("Cabin structural pillar", (x, y, 1.76), (x + 0.02, y, 2.72), 0.075, metal)
    beam("Front windshield frame", (-0.96, y, 2.62), (-0.79, y, 1.99), 0.055, metal)
    beam("Rear cabin frame", (1.43, y, 2.66), (1.45, y, 1.90), 0.065, metal)

# Front and rear windshields, side windows
cube("Front windshield", (-0.84, 0, 2.34), (0.045, 1.70, 0.66), glass, 0.025, (0, 0.18, 0))
cube("Rear window", (1.43, 0, 2.34), (0.045, 1.56, 0.60), glass, 0.025)
for y in (-1.025, 1.025):
    cube("Front side window", (-0.30, y, 2.35), (0.94, 0.035, 0.62), glass, 0.025)
    cube("Rear side window", (0.92, y, 2.35), (0.78, 0.035, 0.62), glass, 0.025)
    # Door separation and handles
    for x in (-0.77, 0.43, 1.37):
        cube("Door seam", (x, y * 1.006, 1.48), (0.018, 0.018, 0.64), black, 0.004)
    cube("Door handle", (0.20, y * 1.035, 1.73), (0.20, 0.045, 0.045), metal, 0.015)
    cube("Side mirror arm", (-0.91, y * 1.12, 2.10), (0.28, 0.055, 0.045), metal, 0.015)
    cube("Side mirror", (-1.02, y * 1.18, 2.16), (0.18, 0.11, 0.24), black, 0.035)

# Hood details
for y in (-0.55, -0.28, 0, 0.28, 0.55):
    cube("Hood ventilation slot", (-1.50, y, 1.892), (0.78, 0.035, 0.012), black, 0.006)
for y in (-0.73, 0.73):
    cube("Hood latch", (-0.85, y, 1.90), (0.10, 0.055, 0.035), metal, 0.01)

# Front grille, headlights and heavy brush guard
cube("Front grille backing", (-2.245, 0, 1.49), (0.08, 0.82, 0.53), black, 0.025)
for y in [i * 0.105 for i in range(-3, 4)]:
    cube("Vertical grille slat", (-2.30, y, 1.49), (0.035, 0.045, 0.43), metal, 0.012)
for y in (-0.78, 0.78):
    cyl("Round headlight housing", (-2.30, y, 1.57), 0.19, 0.09, black, (0, math.pi / 2, 0))
    cyl("Headlight lens", (-2.355, y, 1.57), 0.145, 0.025, lamp, (0, math.pi / 2, 0))
    uv_sphere("Front indicator", (-2.34, y, 1.28), (0.045, 0.07, 0.07), orange)
cube("Front bumper", (-2.39, 0, 1.05), (0.22, 2.18, 0.20), metal, 0.055)
# Wraparound brush guard rails
for y in (-1.00, 1.00):
    beam("Brush guard upright", (-2.49, y, 0.98), (-2.49, y, 1.90), 0.045, metal)
    beam("Brush guard side wing", (-2.49, y, 1.88), (-2.20, y, 1.94), 0.045, metal)
beam("Brush guard upper rail", (-2.50, -1.00, 1.91), (-2.50, 1.00, 1.91), 0.045, metal)
beam("Brush guard lower rail", (-2.50, -1.00, 1.05), (-2.50, 1.00, 1.05), 0.045, metal)
for y in (-0.72, 0.72):
    beam("Brush guard diagonal", (-2.50, y, 1.08), (-2.50, y, 1.86), 0.025, black)

# Rear tailgate, bumper, lights and tow hooks
cube("Rear tailgate panel", (2.255, 0, 1.52), (0.10, 1.35, 0.54), camo, 0.05)
for y in (-0.73, 0.73):
    cube("Rear lamp housing", (2.32, y, 1.50), (0.12, 0.22, 0.40), black, 0.025)
    cube("Rear red lamp", (2.39, y, 1.60), (0.035, 0.13, 0.13), red, 0.018)
    cube("Rear amber lamp", (2.39, y, 1.40), (0.035, 0.13, 0.10), orange, 0.018)
cube("Rear bumper", (2.42, 0, 1.00), (0.20, 1.95, 0.18), metal, 0.04)
for y in (-0.58, 0.58):
    beam("Rear tow hook", (2.49, y, 0.96), (2.53, y, 0.72), 0.035, metal)
    beam("Rear tow hook return", (2.53, y, 0.72), (2.35, y, 0.72), 0.035, metal)

# Wheels: torus tire with chunky tread blocks and simple steel hubs
WHEEL_Z = 0.76
TREAD_R = 0.53
for x in (-1.48, 1.48):
    for y in (-1.10, 1.10):
        # Torus lies in XY; rotate to make axle run along Y
        bpy.ops.mesh.primitive_torus_add(major_radius=0.39, minor_radius=0.17,
                                         major_segments=20, minor_segments=8,
                                         location=(x, y, WHEEL_Z), rotation=(math.pi / 2, 0, 0))
        tire = bpy.context.object
        tire.name = "All-terrain tire"
        tire.data.materials.append(rubber)
        # hub and wheel face
        cyl("Wheel rim", (x, y * 1.025, WHEEL_Z), 0.285, 0.13, metal, (math.pi / 2, 0, 0), 20)
        cyl("Wheel hub", (x, y * 1.09, WHEEL_Z), 0.105, 0.15, black, (math.pi / 2, 0, 0), 16)
        for i in range(8):
            a = 2 * math.pi * i / 8
            cyl("Wheel lug", (x + 0.19 * math.cos(a), y * 1.09, WHEEL_Z + 0.19 * math.sin(a)),
                0.025, 0.04, black, (math.pi / 2, 0, 0), 8)
        # tread lugs around tire circumference, alternating across tire width
        for i in range(18):
            a = 2 * math.pi * i / 18
            for side in (-1, 1):
                xx = x + TREAD_R * math.cos(a)
                zz = WHEEL_Z + TREAD_R * math.sin(a)
                # rotate about Y so the block's thin side faces outward (radially)
                cube("Tire tread block", (xx, y + side * 0.095, zz), (0.18, 0.14, 0.075),
                     rubber, 0.018, (0, math.pi / 2 - a, 0))

# Wheel arches / fender lips
for x in (-1.48, 1.48):
    for y in (-1.035, 1.035):
        cube("Wheel fender top", (x, y, 1.43), (1.18, 0.18, 0.13), camo, 0.05)
        cube("Fender front edge", (x - 0.53, y, 1.30), (0.12, 0.18, 0.35), camo, 0.04)
        cube("Fender rear edge", (x + 0.53, y, 1.30), (0.12, 0.18, 0.35), camo, 0.04)

# Basic visible cabin interior
cube("Dashboard", (-0.58, 0, 1.98), (0.30, 1.60, 0.18), black, 0.04)
for y in (-0.48, 0.48):
    cube("Front seat cushion", (-0.05, y, 1.62), (0.58, 0.62, 0.16), seatmat, 0.07)
    cube("Front seat back", (0.22, y, 1.96), (0.16, 0.62, 0.62), seatmat, 0.07, (0, -0.08, 0))
cube("Steering wheel column", (-0.45, -0.48, 1.88), (0.30, 0.08, 0.08), metal, 0.02)
bpy.ops.mesh.primitive_torus_add(major_radius=0.17, minor_radius=0.025, major_segments=16, minor_segments=6,
                                 location=(-0.32, -0.48, 1.98), rotation=(0, math.pi / 2, 0))
bpy.context.object.name = "Steering wheel"
bpy.context.object.data.materials.append(black)

# Underbody axles and suspension hints
for x in (-1.48, 1.48):
    beam("Axle", (x, -1.0, 0.72), (x, 1.0, 0.72), 0.075, black)
    for y in (-0.83, 0.83):
        beam("Shock absorber", (x, y, 0.62), (x + 0.16, y, 1.12), 0.045, metal)

# A simple roof hatch outline (closed)
cube("Roof hatch panel", (0.42, 0, 2.895), (0.92, 0.86, 0.035), metal, 0.025)
for y in (-0.47, 0.47):
    cube("Roof hatch rim", (0.42, y, 2.91), (1.02, 0.035, 0.06), black, 0.012)

# Object organization: everything under one empty
root = bpy.data.objects.new("MILITARY_4X4_GAME_READY", None)
bpy.context.collection.objects.link(root)
for obj in list(bpy.context.scene.objects):
    if obj != root and obj.parent is None:
        obj.parent = root
bpy.ops.object.select_all(action='DESELECT')
root.select_set(True)
bpy.context.view_layer.objects.active = root

# Units and render preview
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
for engine in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):  # 4.2-4.x use _NEXT; 3.6 and 5.x use plain
    try:
        scene.render.engine = engine
        break
    except TypeError:
        pass
scene.render.resolution_x = 1200
scene.render.resolution_y = 800
scene.render.resolution_percentage = 100
if scene.world is None:
    scene.world = bpy.data.worlds.new("World")
scene.world.color = (0.08, 0.08, 0.08)

# Camera at front-left elevated angle
bpy.ops.object.camera_add(location=(-7.4, -8.2, 5.1))
cam = bpy.context.object
cam.name = "Preview Camera"
target = Vector((0, 0, 1.35))
cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam.data.lens = 52
scene.camera = cam
bpy.ops.object.light_add(type='AREA', location=(-4, -4, 7))
key = bpy.context.object
key.data.energy = 1600
key.data.shape = 'DISK'
key.data.size = 6
bpy.ops.object.light_add(type='AREA', location=(3, 4, 5))
fill = bpy.context.object
fill.data.energy = 1100
fill.data.size = 5

# Ground plane for preview: top surface touches the bottom of the tread blocks
ground_z = WHEEL_Z - TREAD_R - 0.075 / 2
groundmat = mat("Preview ground", (0.045, 0.055, 0.04), 0, 0.95)
cube("Preview ground", (0, 0, ground_z - 0.05), (200, 200, 0.1), groundmat, 0)


# ---------- save ----------
def output_dir():
    if bpy.data.filepath:
        return os.path.dirname(bpy.data.filepath)
    space = getattr(bpy.context, "space_data", None)
    text = getattr(space, "text", None)
    if text and text.filepath:
        return os.path.dirname(bpy.path.abspath(text.filepath))
    return os.path.expanduser("~")


output = os.path.join(output_dir(), "Military_4x4_GameReady.blend")
bpy.ops.wm.save_as_mainfile(filepath=output)
print("Saved:", output)
