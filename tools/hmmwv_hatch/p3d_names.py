#!/usr/bin/env python3
"""
p3d_names.py: offline name scanner for DayZ P3D models (binarized ODOL or MLOD).

Purpose: find out whether the vanilla M1025 model (Offroad_02.p3d) has a separate
bone, named selection or model.cfg animation for the roof hatch, without editing
or de-binarizing the model.

A binarized ODOL stores the names of bones, selections, proxies and model.cfg
animation sources as null-terminated ASCII strings. The script pulls them out and:
  * checks which of the KNOWN AnimationSources from config.cpp (DoorsDriver, ...)
    are present in the model (this validates the method: if the doors are found,
    the extraction works);
  * flags names that look like a hatch / turret / roof;
  * prints model.cfg-like names that config.cpp does NOT define as AnimationSources
    (an unused animation, if the model has one, will be among them).

Usage:
    python p3d_names.py P:\\DZ\\vehicles\\wheeled\\Offroad_02\\Offroad_02.p3d
    python p3d_names.py Offroad_02.p3d --all            # all strings
    python p3d_names.py Offroad_02.p3d --json out.json  # save the result

Where to get the file (the original PBO is never modified):
  * DayZ Tools -> Workdrive / "Extract Game Data" -> P:\\DZ\\vehicles\\wheeled\\Offroad_02\\
  * or unpack <DayZ>\\Addons\\vehicles_wheeled.pbo (DayZ Tools BankRev / any PBO tool)
    into a separate folder.

The script only reads the file. It modifies nothing and does not de-binarize the model.
"""

import argparse
import json
import re
import struct
import sys

# AnimationSources that the vanilla config.cpp defines for Offroad_02
# (own ones plus those inherited from CarScript).
KNOWN_CONFIG_SOURCES = [
    "DoorsDriver", "DoorsCoDriver", "DoorsCargo1", "DoorsCargo2",
    "DoorsHood", "DoorsTrunk",
    "HideDestroyed_1_1", "HideDestroyed_1_2", "HideDestroyed_2_1", "HideDestroyed_2_2",
    "AnimHitWheel_1_1", "AnimHitWheel_1_2", "AnimHitWheel_2_1", "AnimHitWheel_2_2",
    "HitDoorsHood", "HitDoorsTrunk", "HitDoorsDrivers", "HitDoorsCoDrivers", "HitDoorsCargo",
    "damper_1_1", "damper_2_1", "damper_1_2", "damper_2_2",
]

# Keywords for a hatch / turret / roof (EN + CZ, since BI often uses Czech names).
HATCH_KEYWORDS = [
    "hatch", "poklop", "turret", "vez", "kopul", "lid", "roof", "strech",
    "gunner", "commander", "cupola", "kruh", "krytk", "otoc", "mg_",
]

STRING_RE = re.compile(rb"[\x20-\x7e]{3,}(?=\x00)")


def read_header(data):
    magic = data[:4].decode("ascii", "replace")
    version = struct.unpack("<I", data[4:8])[0] if len(data) >= 8 else None
    return magic, version


def extract_strings(data, min_len):
    seen = {}
    for m in STRING_RE.finditer(data):
        s = m.group().decode("ascii")
        if len(s) < min_len:
            continue
        if s not in seen:
            seen[s] = m.start()
    return seen  # name -> offset of first occurrence


def looks_like_identifier(s):
    # Names of bones/selections/sources: no spaces, a "reasonable" length.
    return 2 < len(s) <= 64 and " " not in s and re.fullmatch(r"[A-Za-z0-9_\\.:\-]+", s) is not None


def main():
    ap = argparse.ArgumentParser(description="DayZ P3D name scanner (search for the hatch on Offroad_02)")
    ap.add_argument("p3d", help="path to a .p3d file")
    ap.add_argument("--min-len", type=int, default=3)
    ap.add_argument("--all", action="store_true", help="print all extracted strings")
    ap.add_argument("--json", metavar="FILE", help="save the result as JSON")
    args = ap.parse_args()

    with open(args.p3d, "rb") as f:
        data = f.read()

    magic, version = read_header(data)
    print(f"file:     {args.p3d}")
    print(f"size:     {len(data)} bytes")
    print(f"format:   {magic} (version {version})")
    if magic not in ("ODOL", "MLOD"):
        print("WARNING: unexpected signature; the file may not be a P3D or may be packed.")

    strings = extract_strings(data, args.min_len)
    idents = {s: o for s, o in strings.items() if looks_like_identifier(s)}
    lower_map = {s.lower(): s for s in idents}

    print(f"strings:  {len(strings)} unique, of which {len(idents)} look like names\n")

    # 1. Validate the method on known door sources.
    print("== 1. AnimationSources from config.cpp found in the model ==")
    found_known, missing_known = [], []
    for src in KNOWN_CONFIG_SOURCES:
        hit = lower_map.get(src.lower())
        (found_known if hit else missing_known).append(src)
    print("  found:     " + (", ".join(found_known) or "-"))
    print("  not found: " + (", ".join(missing_known) or "-"))
    if not found_known:
        print("  !! None of the door sources was found. The names may be stored compressed;")
        print("     in that case use the in-game diagnostic (diag_offroad02_console.c).")
    print()

    # 2. Hatch / turret / roof candidates.
    print("== 2. Hatch / turret / roof candidates ==")
    hatch_hits = []
    for s, off in sorted(idents.items(), key=lambda kv: kv[1]):
        sl = s.lower()
        if any(k in sl for k in HATCH_KEYWORDS):
            hatch_hits.append((s, off))
            print(f"  0x{off:08X}  {s}")
    if not hatch_hits:
        print("  - (no names matching the keywords)")
    print()

    # 3. Door-like/animated names that config.cpp does not define.
    print("== 3. Door/animation-like names that config.cpp does not define ==")
    known_lower = {k.lower() for k in KNOWN_CONFIG_SOURCES}
    anim_like = []
    for s, off in sorted(idents.items(), key=lambda kv: kv[1]):
        sl = s.lower()
        if sl in known_lower:
            continue
        if sl.startswith(("doors", "door_", "hide", "hit", "damper", "anim", "axis_", "osa_")) \
                or any(k in sl for k in HATCH_KEYWORDS):
            anim_like.append((s, off))
            print(f"  0x{off:08X}  {s}")
    if not anim_like:
        print("  - none")
    print()

    # 4. Proxies (crew seats etc.).
    print("== 4. Proxies / crew positions ==")
    proxies = [(s, o) for s, o in sorted(strings.items(), key=lambda kv: kv[1])
               if "proxy" in s.lower() or s.lower().startswith(("crew", "pos_", "seat_"))]
    for s, off in proxies:
        print(f"  0x{off:08X}  {s}")
    if not proxies:
        print("  - none")
    print()

    if args.all:
        print("== All strings ==")
        for s, off in sorted(strings.items(), key=lambda kv: kv[1]):
            print(f"  0x{off:08X}  {s}")

    verdict = (
        "HATCH CANDIDATES FOUND: verify them in-game (diag_offroad02_console.c)"
        if hatch_hits else
        "NO hatch names found: the hatch is most likely static geometry (option B)"
    )
    if not found_known:
        verdict = "INCONCLUSIVE: the method did not find even the door sources"
    print("VERDICT: " + verdict)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({
                "file": args.p3d, "format": magic, "version": version,
                "known_sources_found": found_known, "known_sources_missing": missing_known,
                "hatch_candidates": [s for s, _ in hatch_hits],
                "unconfigured_anim_like": [s for s, _ in anim_like],
                "proxies": [s for s, _ in proxies],
                "verdict": verdict,
            }, f, ensure_ascii=False, indent=2)
        print(f"JSON saved: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
