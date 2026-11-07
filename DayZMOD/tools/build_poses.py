"""Builds the seated firing animations from the game's own files.

Usage: python build_poses.py <anm folder> <workspace folder> <DayZPlayerCfgBase.c> <mod folder>
  anm folder:       Addons/anims_anm_player.pbo unpacked with tools/unpbo.py (.anm)
  workspace folder: Addons/anims_workspaces.pbo unpacked, its player/player_main (.asi, .aw)
  DayZPlayerCfgBase.c: from dta/scripts.pbo, the list of weapons and their animation sets

A pose takes the pelvis and legs from the passenger seat and the upper body from the crouched stance
with that kind of weapon, so the arms, the grip and the breathing stay original. The player's capsule
cannot enter the car, so the body is moved inside by the animation itself. Everything else that moves
the pelvis or the feet (the aiming table, turning on the spot, falling) is replaced to keep it there.
"""
import hashlib
import math
import os
import re
import sys

import anm

# Where the capsule stands relative to the seat, in car axes. Same numbers as in CrewFire.c.
CAPSULE_SIDE = 0.9
CAPSULE_DOWN = 0.12

SEATS = {
    "r": "vehicles/CivilianSedan/p_CivilianSedan_codriver_idle.anm",
    "l": "vehicles/CivilianSedan/p_CivilianSedan_passenger_idle.anm",
}

LEAN_DEGREES = 22      # the chest leans towards the window
LEAN_SHIFT = 0.12      # the pelvis slides along the seat towards the door
HEAD_KEEP = 0.45       # part of the lean the neck takes back, so the head stays nearly level

LOWER = {
    "Pelvis", "LeftHipExtra", "RightHipExtra",
    "LeftUpLeg", "LeftUpLegRoll", "LeftKneeExtra", "LeftLeg", "LeftLegRoll", "LeftFoot", "LeftToeBase",
    "RightUpLeg", "RightUpLegRoll", "RightKneeExtra", "RightLeg", "RightLegRoll", "RightFoot", "RightToeBase",
}
SPINE = ["Spine", "Spine1", "Spine2", "Spine3"]

TURNS = ["Turn0", "TurnL90", "TurnL180", "TurnR90", "TurnR180"]
FALLS = ["FallForward", "FallBack", "LandLight", "LandMedium", "LandHeavy", "LandBack"]
KINDS = {"rfl": "player_main_rifle.asi", "pst": "player_main_pistol.asi", "emp": "player_main.asi"}
ANIM_ROOT = "DZ/anims/anm/player/"
TEMPLATE = "{F0C651DE8E24A5DE}DZ/anims/workspaces/player/player_main/player_main.ast"


def qmul(a, b):
    x1, y1, z1, w1 = a
    x2, y2, z2, w2 = b
    return (w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2)


def qinv(q):
    return (-q[0], -q[1], -q[2], q[3])


def qaxis(axis, degrees):
    half = math.radians(degrees) / 2
    s = math.sin(half)
    return (axis[0] * s, axis[1] * s, axis[2] * s, math.cos(half))


def sample(track, frame):
    """Rotation of a sparse track at a frame."""
    keys = sorted(track)
    if frame <= keys[0]:
        return track[keys[0]]
    if frame >= keys[-1]:
        return track[keys[-1]]
    for a, b in zip(keys, keys[1:]):
        if a <= frame <= b:
            u = (frame - a) / (b - a)
            p, q = track[a], track[b]
            sign = -1.0 if sum(i * j for i, j in zip(p, q)) < 0 else 1.0
            r = [p[i] * (1 - u) + q[i] * sign * u for i in range(4)]
            n = math.sqrt(sum(c * c for c in r))
            return tuple(c / n for c in r)
    return track[keys[-1]]


def first(track):
    return track[min(track)]


def seated_pose(upper_path, seat_path, side):
    """Seat legs + stance upper body, leaning towards the door. Facing the car's forward direction."""
    upper = anm.read(upper_path)
    seat = anm.read(seat_path)
    out = anm.Anim(upper.fps, upper.frames)

    seat_pelvis_r = first(seat.bones["Pelvis"].r)
    seat_pelvis_t = first(seat.bones["Pelvis"].t)
    lean = qaxis((0, 0, 1), -LEAN_DEGREES * side)
    neck_back = qaxis((0, 0, 1), LEAN_DEGREES * HEAD_KEEP * side)

    for name, source in upper.bones.items():
        bone = anm.Bone(name)
        if name == "Pelvis":
            bone.t[0] = (seat_pelvis_t[0] + (LEAN_SHIFT - CAPSULE_SIDE) * side, seat_pelvis_t[1] + CAPSULE_DOWN, seat_pelvis_t[2])
            bone.r[0] = seat_pelvis_r
        elif name in LOWER:
            seat_bone = seat.bones[name]
            if seat_bone.t:
                bone.t[0] = first(seat_bone.t)
            bone.r[0] = first(seat_bone.r)
        else:
            bone.t = dict(source.t)
            bone.r = dict(source.r)
        out.bones[name] = bone

    # The chest keeps the orientation it has in the stance, whatever the seated pelvis does, plus the lean.
    pelvis = upper.bones["Pelvis"].r
    spine = upper.bones["Spine"].r
    keep = qinv(seat_pelvis_r)
    out.bones["Spine"].r = {}
    out.bones["Neck"].r = {}
    for f in range(upper.frames):
        stance_spine = qmul(sample(pelvis, f), sample(spine, f))
        out.bones["Spine"].r[f] = qmul(keep, qmul(lean, stance_spine))

        chest = stance_spine
        for name in SPINE[1:]:
            chest = qmul(chest, sample(upper.bones[name].r, f))
        leaned = qmul(lean, chest)
        out.bones["Neck"].r[f] = qmul(qinv(leaned), qmul(neck_back, qmul(leaned, sample(upper.bones["Neck"].r, f))))
    return out


def seated_overlay(aim_path, stance_path):
    """The game's aiming and looking tables turn the pelvis too. Here the pelvis and legs stay in the seat
    and their share of the turn goes to the spine."""
    aim = anm.read(aim_path)
    stance_spine = first(anm.read(stance_path).bones["Spine"].r)

    out = anm.Anim(aim.fps, aim.frames)
    for name, source in aim.bones.items():
        if name in LOWER:
            continue
        bone = anm.Bone(name, 1)
        bone.t = dict(source.t)
        bone.r = dict(source.r)
        out.bones[name] = bone

    if "Pelvis" not in aim.bones or "Spine" not in aim.bones:
        return out
    pelvis = aim.bones["Pelvis"].r
    spine = aim.bones["Spine"].r
    out.bones["Spine"].r = {}
    for f in range(aim.frames):
        # An additive key turns a bone around its own axes: final = base * key.
        moved = qmul(qinv(stance_spine), qmul(sample(pelvis, f), stance_spine))
        out.bones["Spine"].r[f] = qmul(moved, sample(spine, f))
    return out


def still(pose, template_path):
    """Same pose with the length and the step marks of a game file: nothing moves, the root does not rotate."""
    template = anm.read(template_path)
    out = anm.Anim(template.fps, template.frames)
    out.events = template.events
    for name, source in pose.bones.items():
        bone = anm.Bone(name)
        if source.t:
            bone.t[0] = first(source.t)
        if source.r:
            bone.r[0] = first(source.r)
        out.bones[name] = bone
    return out


def guid(text):
    return "{%s}" % hashlib.sha1(text.encode()).hexdigest()[:16].upper()


def asi_lines(path):
    text = open(path, encoding="utf-8", errors="replace").read()
    found = re.findall(r'AnimSetInstanceSource_Line "([^"]+)" \{\s*Resource "\{[0-9A-F]+\}([^"]+)"', text)
    return dict(found)


class Sets:
    """Resolves a pose name through the kind's animation set and its parent."""

    def __init__(self, kind, workspace):
        self.own = asi_lines(os.path.join(workspace, KINDS[kind]))
        self.base = asi_lines(os.path.join(workspace, "player_main.asi"))

    def get(self, name):
        path = self.own.get(name) or self.base.get(name)
        return path[len(ANIM_ROOT):] if path and path.startswith(ANIM_ROOT) else None


def build_kind(kind, side_name, source, workspace, target):
    """Writes the animations of one weapon kind and door. Returns {pose name: file}."""
    side = 1 if side_name == "r" else -1
    sets = Sets(kind, workspace)
    seat = os.path.join(source, SEATS[side_name])
    src = lambda name: os.path.join(source, sets.get(name))
    lines = {}

    def put(name, anim, line):
        anm.write(anim, os.path.join(target, name))
        lines[line] = name

    low = seated_pose(src("Locomotion.Cro.Idle"), seat, side)
    low_name = "%s_%s_low.anm" % (kind, side_name)
    put(low_name, low, "Locomotion.Cro.Idle")
    lines["Locomotion.Cro.IdleExhausted"] = low_name

    raised = low
    if sets.get("Locomotion.CroRas.Idle"):
        raised = seated_pose(src("Locomotion.CroRas.Idle"), seat, side)
        ras_name = "%s_%s_ras.anm" % (kind, side_name)
        put(ras_name, raised, "Locomotion.CroRas.Idle")
        lines["Locomotion.CroRas.IdleExhausted"] = ras_name

    for turn in TURNS:
        for column, pose in (("Cro", low), ("CroRas", raised)):
            line = "Locomotion.%s.%s" % (column, turn)
            if sets.get(line):
                put("%s_%s_%s_%s.anm" % (kind, side_name, column.lower(), turn.lower()), still(pose, src(line)), line)

    for fall in FALLS:
        line = "Falls.Erc." + fall
        put("%s_%s_%s.anm" % (kind, side_name, fall.lower()), still(low, src(line)), line)

    # The overlays do not depend on the door.
    stance = src("Locomotion.CroRas.Idle") if sets.get("Locomotion.CroRas.Idle") else src("Locomotion.Cro.Idle")
    for line, name in (("Locomotion.CroRas.Aim", "aim"), ("Locomotion.CroRas.Look", "look_ras"), ("Locomotion.Cro.Look", "look_low")):
        if sets.get(line):
            file_name = "%s_%s.anm" % (kind, name)
            anm.write(seated_overlay(src(line), stance), os.path.join(target, file_name))
            lines[line] = file_name
    return lines


def write_asi(path, parent, lines):
    body = ["AnimSetInstanceSource {", ' Template "%s"' % TEMPLATE, " ParentTemplates {", '  "%s"' % parent, " }", " Lines {"]
    for line in sorted(lines):
        resource = "CrewFire/anims/" + lines[line]
        body += ['  AnimSetInstanceSource_Line "%s" {' % line, '   Resource "%s%s"' % (guid(resource), resource), "  }"]
    body += [" }", "}", ""]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(body))


def weapons(cfg_path):
    """(class, set file, kind, grip pose, weapon states) of every firearm the game registers, in its order."""
    text = open(cfg_path, encoding="utf-8", errors="replace").read()
    pattern = (r'AddItemInHandsProfileIK\("(\w+)",\s*"dz/anims/workspaces/player/player_main/weapons/(player_main_\w+)\.asi",'
               r'\s*(\w+),\s*"([^"]*)"(?:,\s*"([^"]*)")?')
    kinds = {"fireArmsItemBehaviour": "rfl", "pistolItemBehaviour": "pst"}
    return [(c, f, kinds[b], ik, states) for c, f, b, ik, states in re.findall(pattern, text) if b in kinds]


def parent_guids(workspace):
    text = open(os.path.join(workspace, "player_main.aw"), encoding="utf-8", errors="replace").read()
    found = re.findall(r'"\{([0-9A-F]+)\}(DZ/[^"]+\.asi)"', text)
    return {p.rsplit("/", 1)[1].lower(): "{%s}%s" % (g, p) for g, p in found}


def write_script(path, rows):
    out = ["// Generated by tools/build_poses.py, do not edit.", "class CrewFireProfiles", "{",
           "	//! The animation set for what the player holds.", "	static string SetOf(EntityAI item)", "	{",
           "		if (!item)", '			return "emp";']
    for row in rows:
        out += ['		if (item.IsKindOf("%s"))' % row[0], '			return "%s";' % row[1]]
    out += ["		if (item.IsInherited(Pistol_Base))", '			return "pst";', "		if (item.IsInherited(Weapon_Base))",
            '			return "rfl";', '		return "emp";', "	}", "",
            "	protected static void Add(DayZPlayerType type, string name, HumanItemBehaviorCfg behaviour, string ik, string states)",
            "	{", '		type.AddItemInHandsProfileIK("CrewFire_" + name + "_r", CrewFire.SetPath(name, 1), behaviour, ik, states);',
            '		type.AddItemInHandsProfileIK("CrewFire_" + name + "_l", CrewFire.SetPath(name, -1), behaviour, ik, states);',
            "	}", "",
            "	//! Sets must be registered to be loaded. The grip and the weapon states have to be the real ones:",
            "	//! firing with a set registered without them crashes the engine. The item names are never used.",
            "	static void Register(DayZPlayerType type)", "	{",
            "		DayzPlayerItemBehaviorCfg firearm = new DayzPlayerItemBehaviorCfg;", "		firearm.SetFirearms();",
            "		DayzPlayerItemBehaviorCfg pistol = new DayzPlayerItemBehaviorCfg;", "		pistol.SetPistols();",
            "		DayzPlayerItemBehaviorCfg empty = new DayzPlayerItemBehaviorCfg;", "		empty.SetEmptyHanded();",
            '		Add(type, "emp", empty, "", "");']
    behaviours = {"rfl": "firearm", "pst": "pistol"}
    done = set()
    # Weapons from other mods get the generic sets, with the grip of a common weapon of that kind.
    generic = {"rfl": "m4a1", "pst": "fnp45"}
    for cls, name, kind, ik, states in rows:
        if name == generic[kind]:
            out.append('		Add(type, "%s", %s, "%s", "%s");' % (kind, behaviours[kind], ik, states))
        if name not in done:
            done.add(name)
            out.append('		Add(type, "%s", %s, "%s", "%s");' % (name, behaviours[kind], ik, states))
    out += ["	}", "}", ""]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out))


def main(source, workspace, cfg, mod):
    target = os.path.join(mod, "anims")
    os.makedirs(target, exist_ok=True)
    parents = parent_guids(workspace)
    firearms = weapons(cfg)
    rows = []
    for kind in KINDS:
        for side in "rl":
            lines = build_kind(kind, side, source, workspace, target)
            write_asi(os.path.join(target, "i_%s_%s.asi" % (kind, side)), parents[KINDS[kind]], lines)
            for cls, set_file, weapon_kind, ik, states in firearms:
                if weapon_kind == kind:
                    name = set_file[len("player_main_"):].lower()
                    write_asi(os.path.join(target, "i_%s_%s.asi" % (name, side)), parents[(set_file + ".asi").lower()], lines)
                    if (cls, name, kind, ik, states) not in rows:
                        rows.append((cls, name, kind, ik, states))
    write_script(os.path.join(mod, "scripts", "4_World", "CrewFireProfiles.c"), rows)
    print(len(os.listdir(target)), "files,", len(rows), "firearms")


if __name__ == "__main__":
    main(*sys.argv[1:5])
