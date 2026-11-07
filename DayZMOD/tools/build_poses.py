"""Builds the seated firing animations from the game's own files.

Usage: python build_poses.py <anm folder> <workspace folder> <DayZPlayerCfgBase.c> <mod folder>
  anm folder:       Addons/anims_anm_player.pbo unpacked with tools/unpbo.py (.anm)
  workspace folder: Addons/anims_workspaces.pbo unpacked, its player/player_main (.asi, .aw)
  DayZPlayerCfgBase.c: from dta/scripts.pbo, the list of weapons and their animation sets

A pose takes the pelvis and legs from the passenger seat and the upper body from the crouched stance
with that kind of weapon, so the arms, the grip and the breathing stay original. The player's capsule
cannot enter the car, so the body is moved inside by the animation itself. Everything else that moves
the pelvis or the feet (the aiming table, turning on the spot, standing up, falling) is replaced to keep
it there.

Two clips move the player between the seat and the window:
  out: the one-frame fall that takes the player out of the seat plays the seat-to-window clip instead
       (Falls.Erc.FallForward and FallBack); CrewFire.c lands him when it is over (LEAN_OUT_TIME).
  in:  every car's get-in clip (Vehicle.<car>.<seat>GetIn) is replaced by a window-to-seat clip that
       keeps the game's length and events, so the game's own get-in brings the player back.
In vehicle clips the EntityPosition bone is the player's place in the car; the clips move it between
the seat and the capsule outside the door while the body stays where it is seen.
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

LEAN_DEGREES = 30      # the lower back leans towards the window
LEAN_SHIFT = 0.15      # the pelvis slides along the seat towards the door
CHEST_LEVEL = 0.35     # part of the lean the upper back takes back: the chest goes out, the shoulders stay level
HEAD_KEEP = 0.5        # part of what is left that the neck takes back, so the head stays nearly level

# Seat to window. The game blends from the seat into the fall in VEHICLE_BLEND seconds (BlendFn S), while
# the capsule is already outside the door, so for that moment the clip pulls the pelvis further in.
VEHICLE_BLEND = 0.25
BLEND_BOOST = 2.0
LEAN_OUT_START = 0.12  # seconds into the fall
LEAN_OUT_END = 0.75    # same as CrewFire.LEAN_OUT_TIME: the script lands the player then
FALL_SECONDS = 3.0     # the clip holds the window pose this long, so a late landing never sees it loop
# Window to seat: the motion takes this long, the rest of the game's get-in clip holds the seat.
LEAN_IN_SECONDS = 0.8
PELVIS_ARC = 0.04      # the pelvis lifts off the seat a little while it slides
KEY_STEP = 2           # a key every other frame is smooth enough and halves the files

# When each part of the body moves, as a share of the transition: (start, end).
OUT_TIMING = {"spine": (0.0, 0.7), "pelvis": (0.05, 0.7), "legs": (0.0, 0.6), "arms": (0.2, 0.95), "head": (0.3, 1.0)}
IN_TIMING = {"arms": (0.0, 0.6), "head": (0.0, 0.65), "spine": (0.15, 0.85), "pelvis": (0.2, 0.9), "legs": (0.3, 1.0)}
SPECIAL = {"Scene_Root", "EntityPosition", "Collision"}

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


def sample_t(track, frame):
    """Translation of a sparse track at a frame."""
    keys = sorted(track)
    if frame <= keys[0]:
        return track[keys[0]]
    if frame >= keys[-1]:
        return track[keys[-1]]
    for a, b in zip(keys, keys[1:]):
        if a <= frame <= b:
            u = (frame - a) / (b - a)
            return tuple(track[a][i] * (1 - u) + track[b][i] * u for i in range(3))
    return track[keys[-1]]


def pose_at(anim, frame):
    """{bone: (translation or None, rotation or None)} of an animation at a frame."""
    return {name: (sample_t(bone.t, frame) if bone.t else None, sample(bone.r, frame) if bone.r else None)
            for name, bone in anim.bones.items()}


def slerp(p, q, u):
    dot = sum(i * j for i, j in zip(p, q))
    if dot < 0:
        q = tuple(-c for c in q)
        dot = -dot
    if dot > 0.9995:
        r = [p[i] + (q[i] - p[i]) * u for i in range(4)]
    else:
        theta = math.acos(dot)
        a = math.sin((1 - u) * theta) / math.sin(theta)
        b = math.sin(u * theta) / math.sin(theta)
        r = [a * p[i] + b * q[i] for i in range(4)]
    n = math.sqrt(sum(c * c for c in r))
    return tuple(c / n for c in r)


def lerp(a, b, u):
    return tuple(a[i] + (b[i] - a[i]) * u for i in range(3))


def smoothstep(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def ease(u, window):
    """0..1 over the window (start, end) of a 0..1 time, smooth at both ends."""
    start, end = window
    if u <= start:
        return 0.0
    if u >= end:
        return 1.0
    x = (u - start) / (end - start)
    return x * x * x * (x * (6 * x - 15) + 10)


def part(name):
    """Which schedule of OUT_TIMING / IN_TIMING a bone follows."""
    if name == "Pelvis":
        return "pelvis"
    if name in LOWER:
        return "legs"
    if name.startswith(("Neck", "Head")) or any(k in name for k in ("Eye", "Jaw", "Brow", "Lip", "Cheek", "Tongue")):
        return "head"
    if any(k in name for k in ("Shoulder", "Arm", "Hand", "Finger", "Clavicle", "Weapon")):
        return "arms"
    return "spine"


def blend(start, end, u, timing):
    """The pose a share u of the way from start to end, each part of the body on its own schedule.
    Returns the pose and how far the pelvis has got."""
    out = {}
    for name in set(start) | set(end):
        if name in SPECIAL:
            continue
        ta, ra = start.get(name) or end[name]
        tb, rb = end.get(name) or start[name]
        e = ease(u, timing[part(name)])
        t = lerp(ta, tb, e) if ta and tb else (ta or tb)
        r = slerp(ra, rb, e) if ra and rb else (ra or rb)
        out[name] = (t, r)
    return out, ease(u, timing["pelvis"])


def key_frames(count, dense_until=0):
    """Every frame up to dense_until, then every KEY_STEP-th, and always the last one."""
    frames = list(range(0, min(count, dense_until + 1)))
    frames += [f for f in range(0, count, KEY_STEP) if f > dense_until]
    if frames[-1] != count - 1:
        frames.append(count - 1)
    return frames


def put_key(anim, name, frame, t, r):
    bone = anim.bones.get(name)
    if bone is None:
        bone = anim.bones[name] = anm.Bone(name)
    if t is not None:
        bone.t[frame] = t
    if r is not None:
        bone.r[frame] = r


def squeeze(anim):
    """A track that never moves keeps one key."""
    for bone in anim.bones.values():
        for track in (bone.t, bone.r):
            if len(track) > 1:
                values = list(track.values())
                if all(max(abs(x - y) for x, y in zip(v, values[0])) < 1e-5 for v in values):
                    k = min(track)
                    v = track[k]
                    track.clear()
                    track[k] = v
    return anim


def lean_out_fall(seat, window, side, template):
    """Seat to window, played as the fall that takes the player out of the seat.

    The capsule is outside the door from the first frame, so the body is drawn back by the capsule offset.
    For the first VEHICLE_BLEND seconds the game still mixes in the car's seat pose, which it now draws from
    the capsule, i.e. outside: the pelvis is pulled further in for that time so that the mix stays inside."""
    fps = template.fps
    count = int(round(FALL_SECONDS * fps)) + 1
    out = anm.Anim(fps, count)
    out.events = template.events
    offset = (-CAPSULE_SIDE * side, CAPSULE_DOWN, 0.0)

    start = {name: value for name, value in seat.items() if name not in SPECIAL}
    t, r = start["Pelvis"]
    start["Pelvis"] = (tuple(t[i] + offset[i] for i in range(3)), r)

    begin = LEAN_OUT_START * fps
    end = LEAN_OUT_END * fps
    for f in key_frames(count, int(math.ceil(VEHICLE_BLEND * fps))):
        u = min(1.0, max(0.0, (f - begin) / (end - begin)))
        pose, moved = blend(start, window, u, OUT_TIMING)
        t, r = pose["Pelvis"]
        lift = PELVIS_ARC * math.sin(math.pi * moved)
        car_share = 1 - smoothstep(f / fps / VEHICLE_BLEND)
        boost = BLEND_BOOST if car_share >= 1 else min(BLEND_BOOST, car_share / (1 - car_share))
        pose["Pelvis"] = ((t[0] + boost * offset[0], t[1] + lift + boost * offset[1], t[2] + boost * offset[2]), r)
        for name, (t, r) in pose.items():
            put_key(out, name, f, t, r)
    # The root stays as in the stance poses: nothing to move, the capsule is pinned by the script.
    for name in SPECIAL:
        if name in window:
            put_key(out, name, 0, *window[name])
    return squeeze(out)


def lean_in_getin(windows, template):
    """Window to seat, in place of a car's get-in clip: same length and events, so the game's get-in still ends
    as it should. EntityPosition goes from the capsule outside the door to the seat with the pelvis, so the
    body is seen moving only as the pose says. None for a seat in the middle of the car."""
    count = template.frames
    seat = pose_at(template, count - 1)
    if "EntityPosition" not in seat or not seat["EntityPosition"][0]:
        return None
    ep_seat, ep_rot = seat["EntityPosition"]
    if abs(ep_seat[0]) < 0.1:
        return None
    side = 1 if ep_seat[0] > 0 else -1
    ep_window = (ep_seat[0] + CAPSULE_SIDE * side, ep_seat[1] - CAPSULE_DOWN, ep_seat[2])
    window = windows[side]

    out = anm.Anim(template.fps, count)
    out.events = template.events
    for name in ("Scene_Root", "Collision"):
        if name in template.bones:
            source = template.bones[name]
            bone = anm.Bone(name, source.additive)
            bone.t = dict(source.t)
            bone.r = dict(source.r)
            out.bones[name] = bone

    last = max(1.0, min(count - 1, LEAN_IN_SECONDS * template.fps))
    for f in key_frames(count):
        u = min(1.0, f / last)
        pose, moved = blend(window, seat, u, IN_TIMING)
        t, r = pose["Pelvis"]
        pose["Pelvis"] = ((t[0], t[1] + PELVIS_ARC * math.sin(math.pi * moved), t[2]), r)
        for name, (t, r) in pose.items():
            put_key(out, name, f, t, r)
        put_key(out, "EntityPosition", f, lerp(ep_window, ep_seat, moved), ep_rot)
    return squeeze(out)


def seated_pose(upper_path, seat_path, side):
    """Seat legs + stance upper body, leaning out towards the door. Facing the car's forward direction.
    The lower back leans, the upper back takes part of it back (CHEST_LEVEL) so the weapon is held level,
    and the neck straightens the head."""
    upper = anm.read(upper_path)
    seat = anm.read(seat_path)
    out = anm.Anim(upper.fps, upper.frames)

    seat_pelvis_r = first(seat.bones["Pelvis"].r)
    seat_pelvis_t = first(seat.bones["Pelvis"].t)
    lean = qaxis((0, 0, 1), -LEAN_DEGREES * side)
    counter = qaxis((0, 0, 1), LEAN_DEGREES * CHEST_LEVEL * side)
    neck_back = qaxis((0, 0, 1), LEAN_DEGREES * (1 - CHEST_LEVEL) * HEAD_KEEP * side)

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
    # Rotations here are in the player's space: parent * child. The lean turns the whole chain from Spine up;
    # a turn about the same axis given to Spine2 in that space becomes inv(parent) * turn * parent * local.
    pelvis = upper.bones["Pelvis"].r
    spine = upper.bones["Spine"].r
    keep = qinv(seat_pelvis_r)
    out.bones["Spine"].r = {}
    out.bones["Spine2"].r = {}
    out.bones["Neck"].r = {}
    for f in range(upper.frames):
        stance_spine = qmul(sample(pelvis, f), sample(spine, f))
        out.bones["Spine"].r[f] = qmul(keep, qmul(lean, stance_spine))

        below = qmul(stance_spine, sample(upper.bones["Spine1"].r, f))
        spine2 = sample(upper.bones["Spine2"].r, f)
        out.bones["Spine2"].r[f] = qmul(qinv(below), qmul(counter, qmul(below, spine2)))

        chest = qmul(qmul(below, spine2), sample(upper.bones["Spine3"].r, f))
        leaned = qmul(counter, qmul(lean, chest))
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

    def names(self):
        return set(self.own) | set(self.base)


STANCES = ("Erc", "ErcRas", "Cro", "CroRas")


def hold_lines(sets):
    """Every on-the-spot line of the standing and crouched stances and the stance changes (Go*) between them.
    The script keeps the player crouched, but the game passes through the others for a few frames, and a
    standing pose would be drawn at the capsule, outside the door."""
    lines = ["Locomotion.%s.%s" % (column, anim) for column in STANCES for anim in ["Idle", "IdleExhausted"] + TURNS]
    lines += sorted(n for n in sets.names() if re.match(r"Locomotion\.(%s)\.Go\w+$" % "|".join(STANCES), n))
    return [line for line in lines if sets.get(line)]


def getin_lines(sets):
    """The cars' get-in clips of every seat but the driver's."""
    found = []
    for name in sorted(sets.names()):
        m = re.match(r"Vehicle\.(\w+)\.(\w+)$", name)
        if not m or not sets.get(name):
            continue
        car, anim = m.group(1).lower(), m.group(2).lower()
        if "getin" in anim and not anim.startswith("driver") and "jump" not in anim and not car.startswith(("boat", "jawa")):
            found.append(name)
    return found


def build_kind(kind, side_name, source, workspace, target):
    """Writes the animations of one weapon kind and door. Returns ({pose name: file}, window pose)."""
    side = 1 if side_name == "r" else -1
    sets = Sets(kind, workspace)
    seat_path = os.path.join(source, SEATS[side_name])
    src = lambda name: os.path.join(source, sets.get(name))
    lines = {}

    def put(name, anim, line):
        anm.write(anim, os.path.join(target, name))
        lines[line] = name

    low = seated_pose(src("Locomotion.Cro.Idle"), seat_path, side)
    low_name = "%s_%s_low.anm" % (kind, side_name)
    anm.write(low, os.path.join(target, low_name))

    raised, ras_name = low, low_name
    if sets.get("Locomotion.CroRas.Idle"):
        raised = seated_pose(src("Locomotion.CroRas.Idle"), seat_path, side)
        ras_name = "%s_%s_ras.anm" % (kind, side_name)
        anm.write(raised, os.path.join(target, ras_name))

    for line in hold_lines(sets):
        column, anim_name = line.split(".")[1:]
        pose, pose_name = (raised, ras_name) if column.endswith("Ras") else (low, low_name)
        if anim_name in ("Idle", "IdleExhausted"):
            lines[line] = pose_name
        else:
            put("%s_%s_%s_%s.anm" % (kind, side_name, column.lower(), anim_name.lower()), still(pose, src(line)), line)

    seat = pose_at(anm.read(seat_path), 0)
    window = pose_at(low, 0)
    for fall in FALLS:
        line = "Falls.Erc." + fall
        if fall.startswith("Fall"):
            clip = lean_out_fall(seat, window, side, anm.read(src(line)))
        else:
            clip = still(low, src(line))
        put("%s_%s_%s.anm" % (kind, side_name, fall.lower()), clip, line)

    # The overlays do not depend on the door.
    crouched = src("Locomotion.CroRas.Idle") if sets.get("Locomotion.CroRas.Idle") else src("Locomotion.Cro.Idle")
    standing = src("Locomotion.ErcRas.Idle") if sets.get("Locomotion.ErcRas.Idle") else crouched
    overlays = (("Locomotion.CroRas.Aim", "aim", crouched), ("Locomotion.CroRas.Look", "look_ras", crouched),
                ("Locomotion.Cro.Look", "look_low", crouched), ("Locomotion.ErcRas.Aim", "aim_erc", standing),
                ("Locomotion.ErcRas.Look", "look_erc_ras", standing), ("Locomotion.Erc.Look", "look_erc_low", standing))
    for line, name, stance in overlays:
        if sets.get(line):
            file_name = "%s_%s.anm" % (kind, name)
            anm.write(seated_overlay(src(line), stance), os.path.join(target, file_name))
            lines[line] = file_name
    return lines, window


def build_getins(kind, source, workspace, target, windows):
    """Window-to-seat clips for one weapon kind, the same for both doors' sets. Returns {pose name: file}."""
    sets = Sets(kind, workspace)
    lines = {}
    for line in getin_lines(sets):
        clip = lean_in_getin(windows, anm.read(os.path.join(source, sets.get(line))))
        if not clip:
            continue
        name = "%s_in_%s.anm" % (kind, line[len("Vehicle."):].replace(".", "_").lower())
        anm.write(clip, os.path.join(target, name))
        lines[line] = name
        ep = clip.bones["EntityPosition"].t
        print("  %-48s %3d frames %2d fps  seat %s" % (line, clip.frames, clip.fps,
                                                       tuple(round(c, 2) for c in ep[max(ep)])))
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
        built = {side: build_kind(kind, side, source, workspace, target) for side in "rl"}
        print(kind, "get-in clips:")
        getins = build_getins(kind, source, workspace, target, {1: built["r"][1], -1: built["l"][1]})
        if not getins:
            print("  none found: the way back into the seat keeps the game's own get-in")
        for side in "rl":
            lines = dict(built[side][0])
            lines.update(getins)
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
