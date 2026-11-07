#!/usr/bin/env python3
"""DayZ Central Economy helper: validate and generate CE XML files.

Stdlib only. Run with `python3 -I dayz_ce.py <command> ...`.

Commands
  check PATH [PATH ...]   Validate files and/or a mission folder
                          (cfgeventspawns.xml, events.xml, types.xml,
                          cfgspawnabletypes.xml, cfgeconomycore.xml + <ce> folders).
  positions FILE          List spawn positions of a cfgeventspawns-style file.
  gen-events FILE         Print events.xml blocks for events found in a
                          cfgeventspawns-style file.
  gen-types CLASS ...     Print types.xml entries for vehicle classnames.
  gen-spawnable CLASS ... Print cfgspawnabletypes.xml entries (parts) for vehicles.
  suggest NAME ...        Find the real classname (case/underscore typos).

Files are recognised by their root tag, so files without extension work too.
Exit code: 1 if any ERROR was reported by `check`, else 0.
"""
import argparse
import os
import re
import sys
import xml.parsers.expat
from collections import defaultdict

# Approximate terrain sizes in metres (x/z range 0..size).
MAP_SIZES = {
    "chernarus": 15360, "chernarusplus": 15360,
    "livonia": 12800, "enoch": 12800,
    "sakhal": 15360,
    "nasdara": 16384,   # 1.30 Badlands map; estimate (~267 km2, CE coords up to ~15745)
}

ROOT_KINDS = {
    "eventposdef": "spawns",        # cfgeventspawns.xml
    "events": "events",             # db/events.xml (+ custom event files)
    "types": "types",               # db/types.xml (+ custom types files)
    "spawnabletypes": "spawnable",  # cfgspawnabletypes.xml
    "economycore": "core",          # cfgeconomycore.xml
    "randompresets": "presets",     # cfgrandompresets.xml
    "eventgroupdef": "groups",      # cfgeventgroups.xml
    "lists": "limits",              # cfglimitsdefinition.xml
    "user_lists": "userlimits",     # cfglimitsdefinitionuser.xml
    "variables": "globals",         # db/globals.xml
    "economy": "economy",           # db/economy.xml
}

# ---------------------------------------------------------------- reporting

class Report:
    def __init__(self):
        self.items = []

    def add(self, level, where, msg):
        self.items.append((level, where, msg))

    def error(self, where, msg):
        self.add("ERROR", where, msg)

    def warn(self, where, msg):
        self.add("WARN", where, msg)

    def info(self, where, msg):
        self.add("INFO", where, msg)

    def print(self, quiet_info=False):
        order = {"ERROR": 0, "WARN": 1, "INFO": 2}
        for level, where, msg in sorted(self.items, key=lambda i: order[i[0]]):
            if quiet_info and level == "INFO":
                continue
            print(f"{level:5} {where}: {msg}")
        counts = defaultdict(int)
        for level, _, _ in self.items:
            counts[level] += 1
        print(f"\nИтого: {counts['ERROR']} ERROR, {counts['WARN']} WARN, {counts['INFO']} INFO")
        return counts["ERROR"]

# ---------------------------------------------------------------- parsing

class Node:
    __slots__ = ("tag", "attrib", "children", "line", "text")

    def __init__(self, tag, attrib, line):
        self.tag, self.attrib, self.line = tag, attrib, line
        self.children, self.text = [], ""

    def find_all(self, tag):
        return [c for c in self.children if c.tag == tag]

    def child_text(self, tag, default=None):
        for c in self.children:
            if c.tag == tag:
                return c.text.strip()
        return default


def parse_xml(path):
    """Return (root Node | None, error string | None). Keeps line numbers."""
    with open(path, "rb") as fh:
        data = fh.read()
    parser = xml.parsers.expat.ParserCreate()
    stack, holder = [], {}

    def start(tag, attrs):
        node = Node(tag, attrs, parser.CurrentLineNumber)
        if stack:
            stack[-1].children.append(node)
        else:
            holder["root"] = node
        stack.append(node)

    def end(_tag):
        stack.pop()

    def chars(text):
        if stack:
            stack[-1].text += text

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = chars
    try:
        parser.Parse(data, True)
    except xml.parsers.expat.ExpatError as exc:
        return None, f"строка {exc.lineno}, столбец {exc.offset + 1}: {xml.parsers.expat.ErrorString(exc.code)}"
    return holder.get("root"), None


COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
ROOT_RE = re.compile(r"<([A-Za-z_][\w.-]*)")
EVENT_OPEN_RE = re.compile(r"<event\b([^>]*?)(/?)>")
EVENT_CLOSE_RE = re.compile(r"</event\s*>")
POS_RE = re.compile(r"<pos\b([^>]*?)/?>")
ZONE_RE = re.compile(r"<zone\b([^>]*?)/?>")
ATTR_RE = re.compile(r'([\w:-]+)\s*=\s*"([^"]*)"')


def strip_comments(text):
    # keep newlines so line numbers stay correct
    return COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def sniff_root(path):
    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        text = strip_comments(fh.read())
    text = re.sub(r"<\?.*?\?>", "", text, flags=re.S)
    m = ROOT_RE.search(text)
    return m.group(1) if m else None


def lenient_spawns(path, report=None):
    """Regex parse of cfgeventspawns-style text. Works on broken XML too.

    Returns ordered dict name -> {"line", "pos": [ {x,z,a,y,group,line} ], "zone"}.
    """
    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        text = strip_comments(fh.read())
    events, open_stack = {}, []
    order, reported_unclosed = [], set()
    for lineno, line in enumerate(text.splitlines(), 1):
        for token in re.finditer(r"<event\b[^>]*?/?>|</event\s*>|<pos\b[^>]*?/?>|<zone\b[^>]*?/?>", line):
            tok = token.group(0)
            if tok.startswith("</event"):
                if open_stack:
                    open_stack.pop()
                elif report:
                    report.error(f"{path}:{lineno}", "лишний </event> без открывающего тега")
                continue
            attrs = dict(ATTR_RE.findall(tok))
            if tok.startswith("<event"):
                name = attrs.get("name", f"<без имени:{lineno}>")
                if open_stack and report and open_stack[-1] not in reported_unclosed:
                    parent = open_stack[-1]
                    reported_unclosed.add(parent)
                    report.error(
                        f"{path}:{events[parent]['line']}",
                        f"<event name=\"{parent}\"> не закрыт: внутри него на строке {lineno} начинается "
                        f"<event name=\"{name}\">. Добавь </event> перед строкой {lineno}.")
                if name in events:
                    if report:
                        report.error(f"{path}:{lineno}",
                                     f"событие \"{name}\" объявлено повторно (первое — строка {events[name]['line']})")
                else:
                    events[name] = {"line": lineno, "pos": [], "zone": None}
                    order.append(name)
                if not tok.endswith("/>"):
                    open_stack.append(name)
            elif tok.startswith("<zone"):
                if open_stack:
                    events[open_stack[-1]]["zone"] = attrs
            else:  # <pos>
                if not open_stack:
                    if report:
                        report.error(f"{path}:{lineno}", "<pos> вне <event>")
                    continue
                attrs["line"] = lineno
                events[open_stack[-1]]["pos"].append(attrs)
    for name in open_stack:
        if report and name not in reported_unclosed:
            report.error(f"{path}:{events[name]['line']}", f"<event name=\"{name}\"> не закрыт до конца файла")
    return {n: events[n] for n in order}

# ---------------------------------------------------------------- loading

class Mission:
    def __init__(self):
        self.files = defaultdict(list)   # kind -> [path]


def find_ci(folder, *parts):
    """Case-insensitive path lookup (Linux servers are case-sensitive)."""
    cur = folder
    for part in parts:
        try:
            entries = os.listdir(cur)
        except OSError:
            return None
        match = next((e for e in entries if e.lower() == part.lower()), None)
        if match is None:
            return None
        cur = os.path.join(cur, match)
    return cur


def collect(paths, report):
    mission = Mission()
    for path in paths:
        if os.path.isdir(path):
            for parts in (("cfgeventspawns.xml",), ("db", "events.xml"), ("db", "types.xml"),
                          ("cfgspawnabletypes.xml",), ("cfgeconomycore.xml",), ("cfgrandompresets.xml",),
                          ("cfgeventgroups.xml",), ("cfglimitsdefinition.xml",), ("db", "globals.xml"),
                          ("db", "economy.xml")):
                found = find_ci(path, *parts)
                if found:
                    add_file(mission, found, report)
            core = find_ci(path, "cfgeconomycore.xml")
            if core:
                add_ce_folders(mission, path, core, report)
        elif os.path.isfile(path):
            add_file(mission, path, report)
        else:
            report.error(path, "путь не найден")
    return mission


def add_file(mission, path, report):
    root = sniff_root(path)
    kind = ROOT_KINDS.get(root or "")
    if not kind:
        report.warn(path, f"неизвестный корневой тег <{root}> — файл пропущен")
        return
    if path not in mission.files[kind]:
        mission.files[kind].append(path)


def add_ce_folders(mission, mission_dir, core_path, report):
    root, err = parse_xml(core_path)
    if err:
        report.error(core_path, f"XML не парсится: {err}")
        return
    for ce in root.find_all("ce"):
        folder = ce.attrib.get("folder", "")
        for f in ce.find_all("file"):
            name, ftype = f.attrib.get("name", ""), f.attrib.get("type", "")
            full = find_ci(mission_dir, *re.split(r"[\\/]", folder), name) if folder else find_ci(mission_dir, name)
            where = f"{core_path}:{f.line}"
            if not full:
                report.error(where, f"<ce folder=\"{folder}\"> ссылается на несуществующий файл \"{name}\"")
                continue
            if ftype not in ("types", "spawnabletypes", "events", "globals", "economy", "messages", "randompresets"):
                report.warn(where, f"необычный type=\"{ftype}\" для {name}")
            add_file(mission, full, report)

# ---------------------------------------------------------------- checks

def as_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def check_spawns(mission, report, map_size, radius, shared_warn=3):
    spawns = {}
    for path in mission.files["spawns"]:
        root, err = parse_xml(path)
        if err:
            report.error(path, f"XML не парсится ({err}). CE выдаст ошибку парсинга и не прочитает файл корректно. Детали ниже.")
        events = lenient_spawns(path, report if err else None)
        if not err:
            # duplicates are not XML errors, detect them on the clean parse too
            seen = {}
            for ev in root.find_all("event"):
                name = ev.attrib.get("name")
                if name in seen:
                    report.error(f"{path}:{ev.line}", f"событие \"{name}\" объявлено повторно (первое — строка {seen[name]})")
                seen.setdefault(name, ev.line)
        for name, ev in events.items():
            where = f"{path}:{ev['line']}"
            if name in spawns:
                report.error(where, f"событие \"{name}\" уже есть в {spawns[name]['file']}")
            ev["file"] = path
            spawns[name] = ev
            if not ev["pos"]:
                report.info(where, f"\"{name}\": нет ни одной <pos> (событие с position=fixed не заспавнится)")
            for p in ev["pos"]:
                pw = f"{path}:{p['line']}"
                x, z, a = p.get("x"), p.get("z"), p.get("a")
                try:
                    fx, fz = float(x), float(z)
                except (TypeError, ValueError):
                    report.error(pw, f"\"{name}\": у <pos> нет корректных x/z")
                    continue
                if fx < 0 or fz < 0 or (map_size and (fx > map_size or fz > map_size)):
                    lim = f"0..{map_size}" if map_size else ">= 0"
                    report.error(pw, f"\"{name}\": координата вне карты (x={x}, z={z}, ожидается {lim})")
                if a is not None:
                    # vanilla uses values > 360 too (they wrap); -1 = random heading
                    try:
                        float(a)
                    except ValueError:
                        report.error(pw, f"\"{name}\": a=\"{a}\" не число")
        if radius > 0:
            check_overlaps(path, events, report, radius, shared_warn)
    return spawns


def check_overlaps(path, events, report, radius, shared_warn=3):
    cell = max(radius, 1.0)
    grid = defaultdict(list)
    pts = []
    for name, ev in events.items():
        for p in ev["pos"]:
            try:
                x, z = float(p["x"]), float(p["z"])
            except (KeyError, ValueError):
                continue
            pts.append((x, z, name, p["line"]))
    for i, (x, z, _, _) in enumerate(pts):
        grid[(int(x // cell), int(z // cell))].append(i)
    parent = list(range(len(pts)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, (x, z, _, _) in enumerate(pts):
        gx, gz = int(x // cell), int(z // cell)
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                for j in grid.get((gx + dx, gz + dz), ()):
                    if j > i and (pts[j][0] - x) ** 2 + (pts[j][1] - z) ** 2 <= radius * radius:
                        parent[find(j)] = find(i)
    clusters = defaultdict(list)
    for i in range(len(pts)):
        clusters[find(i)].append(pts[i])
    shared = [c for c in clusters.values() if len(c) > 1]
    if not shared:
        return
    multi_event = 0
    for c in sorted(shared, key=lambda c: c[0][3]):
        names = sorted({p[2] for p in c})
        x, z = c[0][0], c[0][1]
        if len(names) > 1:
            multi_event += 1
            shown = ", ".join(names[:6]) + (f" и ещё {len(names) - 6}" if len(names) > 6 else "")
            msg = (f"точка x={x:.1f} z={z:.1f} (±{radius:g} м) общая для {len(names)} событий: {shown}")
            # vanilla shares some points between 2 events; many events on one point is a smell
            if len(names) >= shared_warn:
                report.warn(f"{path}:{c[0][3]}", msg + ". События конкурируют за одно место: пока оно занято, "
                            "остальные там не появятся, весь транспорт скучивается в одних и тех же точках.")
            else:
                report.info(f"{path}:{c[0][3]}", msg)
        else:
            report.warn(f"{path}:{c[0][3]}", f"\"{names[0]}\": дублирующаяся точка x={x:.1f} z={z:.1f} ({len(c)} раза)")
    if multi_event:
        report.info(path, f"{multi_event} точек разделяются между разными событиями (радиус {radius:g} м)")


def load_named(mission, kind, item_tag, report, label):
    """Parse all files of `kind`; return name -> (path, Node)."""
    result = {}
    for path in mission.files[kind]:
        root, err = parse_xml(path)
        if err:
            report.error(path, f"XML не парсится ({err}). CE не прочитает {label} корректно.")
            continue
        for node in root.find_all(item_tag):
            name = node.attrib.get("name")
            if not name:
                report.error(f"{path}:{node.line}", f"<{item_tag}> без name")
                continue
            key = name.lower()
            if key in result:
                prev = result[key]
                report.warn(f"{path}:{node.line}",
                            f"\"{name}\" уже объявлен в {prev[0]}:{prev[1].line} — останется одно определение, проверь какое")
            result[key] = (path, node)
    return result


def check_events(mission, report, spawns):
    events = load_named(mission, "events", "event", report, "события")
    spawn_lc = {k.lower(): v for k, v in spawns.items()}
    for key, (path, ev) in sorted(events.items()):
        name = ev.attrib["name"]
        where = f"{path}:{ev.line}"
        nominal, emin, emax = (as_int(ev.child_text(t)) for t in ("nominal", "min", "max"))
        for tag, val in (("nominal", nominal), ("min", emin), ("max", emax)):
            if val is None:
                report.error(where, f"\"{name}\": нет/некорректный <{tag}>")
        is_vehicle = name.lower().startswith("vehicle")
        # max=0 is common in vanilla (no cap) and non-vehicle events use their own semantics
        if is_vehicle and None not in (emin, emax) and emax > 0 and emin > emax:
            report.error(where, f"\"{name}\": min ({emin}) > max ({emax})")
        if is_vehicle and None not in (nominal, emax) and emax > 0 and nominal > emax:
            report.info(where, f"\"{name}\": nominal ({nominal}) > max ({emax})")
        active = ev.child_text("active", "1")
        if active == "0":
            report.info(where, f"\"{name}\": active=0 — событие выключено")
        position = (ev.child_text("position") or "").lower()
        children = []
        for ch in ev.find_all("children"):
            children += ch.find_all("child")
        if is_vehicle and not children:
            report.error(where, f"\"{name}\": у события транспорта нет <children>")
        for c in children:
            cw = f"{path}:{c.line}"
            if not c.attrib.get("type"):
                report.error(cw, f"\"{name}\": <child> без type")
            cmin, cmax = as_int(c.attrib.get("min")), as_int(c.attrib.get("max"))
            if is_vehicle and None not in (cmin, cmax) and cmax > 0 and cmin > cmax:
                report.warn(cw, f"\"{name}\": child {c.attrib.get('type')} min ({cmin}) > max ({cmax})")
        if position == "fixed" and mission.files["spawns"] and active != "0":
            sp = spawn_lc.get(key)
            if sp is None:
                msg = f"\"{name}\": position=fixed, но в cfgeventspawns нет <event name=\"{name}\"> — не заспавнится"
                if is_vehicle:
                    report.error(where, msg)
                elif name.lower().startswith("static"):
                    report.warn(where, msg)
                # Animal*/Ambient* use env/*_territories.xml, not cfgeventspawns
            elif is_vehicle and nominal is not None:
                count = len(sp["pos"])
                if count < nominal:
                    report.warn(where, f"\"{name}\": nominal={nominal}, а точек всего {count} — больше {count} не появится")
                elif count < nominal * 2:
                    report.info(where, f"\"{name}\": точек {count} при nominal={nominal}; в ванилле точек в 5–7 раз больше nominal")
    for key, sp in spawns.items():
        if mission.files["events"] and key.lower() not in events:
            report.warn(f"{sp['file']}:{sp['line']}",
                        f"точки события \"{key}\" не используются: в events.xml (и <ce> файлах) нет такого события")
    return events


def check_types(mission, report, events):
    types = load_named(mission, "types", "type", report, "types")
    for key, (path, t) in types.items():
        where = f"{path}:{t.line}"
        nominal, tmin = as_int(t.child_text("nominal")), as_int(t.child_text("min"))
        if None not in (nominal, tmin) and tmin > nominal:
            report.info(where, f"\"{t.attrib['name']}\": min ({tmin}) > nominal ({nominal})")
        if t.child_text("lifetime") is None:
            report.warn(where, f"\"{t.attrib['name']}\": нет <lifetime>")
    if mission.files["types"]:
        for _, (path, ev) in events.items():
            if not ev.attrib["name"].lower().startswith("vehicle"):
                continue  # static wrecks/props are often not in types.xml by design
            for ch in ev.find_all("children"):
                for c in ch.find_all("child"):
                    ctype = c.attrib.get("type", "")
                    if ctype and ctype.lower() not in types:
                        report.error(f"{path}:{c.line}",
                                     f"событие \"{ev.attrib['name']}\": child type=\"{ctype}\" нет в types.xml — CE его не заспавнит")
    return types


def check_spawnable(mission, report, types, events):
    spawnable = load_named(mission, "spawnable", "type", report, "spawnabletypes")
    if types:
        for key, (path, t) in spawnable.items():
            if key not in types:
                report.info(f"{path}:{t.line}", f"\"{t.attrib['name']}\" есть в spawnabletypes, но нет в types")
    vehicle_children = set()
    for _, (_, ev) in events.items():
        if ev.attrib["name"].lower().startswith("vehicle"):
            for ch in ev.find_all("children"):
                vehicle_children |= {c.attrib.get("type", "").lower() for c in ch.find_all("child")}
    if mission.files["spawnable"]:
        for ctype in sorted(vehicle_children - set(spawnable)):
            if ctype:
                report.warn("cfgspawnabletypes", f"машина \"{ctype}\" не описана в spawnabletypes — может появиться без колёс/деталей")


def cmd_check(args):
    report = Report()
    map_size = MAP_SIZES.get(args.map.lower()) if args.map else None
    if args.map and map_size is None:
        try:
            map_size = float(args.map)
        except ValueError:
            sys.exit(f"неизвестная карта {args.map}; варианты: {', '.join(MAP_SIZES)} или число")
    mission = collect(args.paths, report)
    for kind, files in sorted(mission.files.items()):
        for f in files:
            report.info(f, f"распознан как {kind}")
    for kind in ("core", "presets", "groups", "limits", "userlimits", "globals", "economy"):
        for path in mission.files[kind]:
            _, err = parse_xml(path)
            if err:
                report.error(path, f"XML не парсится: {err}")
    spawns = check_spawns(mission, report, map_size, args.radius, args.shared_warn)
    events = check_events(mission, report, spawns)
    types = check_types(mission, report, events)
    check_spawnable(mission, report, types, events)
    errors = report.print(quiet_info=args.quiet)
    return 1 if errors else 0

# ---------------------------------------------------------------- positions

def cmd_positions(args):
    events = lenient_spawns(args.file)
    rows = []
    for name, ev in events.items():
        if args.event and not re.search(args.event, name, re.I):
            continue
        for i, p in enumerate(ev["pos"], 1):
            try:
                x, z = float(p["x"]), float(p["z"])
            except (KeyError, ValueError):
                continue
            if args.near:
                nx, nz, r = args.near
                if (x - nx) ** 2 + (z - nz) ** 2 > r * r:
                    continue
            rows.append((name, i, x, z, p.get("a", ""), p.get("y", ""), p["line"]))
    if args.csv:
        print("event,index,x,z,a,y,line")
        for r in rows:
            print(",".join(str(v) for v in r))
    else:
        for name, i, x, z, a, y, line in rows:
            extra = f" y={y}" if y else ""
            print(f"{name:40} #{i:<3} x={x:10.2f} z={z:10.2f} a={a}{extra}  (строка {line})")
        print(f"\nВсего: {len(rows)} точек")
    return 0

# ---------------------------------------------------------------- generators

def cmd_gen_events(args):
    events = lenient_spawns(args.file)
    class_map = {}
    for item in args.cls or []:
        ev, _, classes = item.partition("=")
        class_map[ev] = [c for c in classes.split(",") if c]
    out = []
    for name, ev in events.items():
        if args.prefix and not name.startswith(args.prefix):
            continue
        count = len(ev["pos"])
        if count == 0:
            continue
        children = class_map.get(name)
        if not children:
            base = name[len(args.strip_prefix):] if args.strip_prefix and name.startswith(args.strip_prefix) else name
            children = [base]
        nominal = min(args.nominal, count)
        out.append(f"    <event name=\"{name}\">")
        out.append(f"        <nominal>{nominal}</nominal>")
        out.append(f"        <min>{nominal}</min>")
        out.append(f"        <max>{nominal}</max>")
        out.append("        <lifetime>300</lifetime>")
        out.append("        <restock>0</restock>")
        out.append("        <saferadius>500</saferadius>")
        out.append(f"        <distanceradius>{args.distanceradius}</distanceradius>")
        out.append("        <cleanupradius>200</cleanupradius>")
        out.append("        <flags deletable=\"0\" init_random=\"0\" remove_damaged=\"1\"/>")
        out.append("        <position>fixed</position>")
        out.append("        <limit>mixed</limit>")
        out.append("        <active>1</active>")
        out.append("        <children>")
        for c in children:
            out.append(f"            <child lootmax=\"0\" lootmin=\"0\" max=\"{nominal}\" min=\"0\" type=\"{c}\"/>")
        out.append("        </children>")
        out.append(f"    </event> <!-- точек в cfgeventspawns: {count} -->")
    if args.wrap:
        print('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<events>')
    print("\n".join(out))
    if args.wrap:
        print("</events>")
    print("<!-- ПРОВЕРЬ: type= должен совпадать с classname из мода (регистр и подчёркивания!) -->", file=sys.stderr)
    return 0


def cmd_gen_types(args):
    if args.wrap:
        print('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<types>')
    for c in args.classes:
        print(f"    <type name=\"{c}\">")
        print("        <nominal>0</nominal>")
        print(f"        <lifetime>{args.lifetime}</lifetime>")
        print(f"        <restock>{args.restock}</restock>")
        print("        <min>0</min>")
        print("        <quantmin>-1</quantmin>")
        print("        <quantmax>-1</quantmax>")
        print("        <cost>100</cost>")
        print("        <flags count_in_cargo=\"0\" count_in_hoarder=\"0\" count_in_map=\"1\" count_in_player=\"0\" crafted=\"0\" deloot=\"0\"/>")
        print("    </type>")
    if args.wrap:
        print("</types>")
    return 0


REF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references")
DEFAULT_CLASSLIST = os.path.join(REF_DIR, "rusforma_classnames.txt")
DEFAULT_ATTACHMENTS = os.path.join(REF_DIR, "rusforma_attachments.tsv")


def norm(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def read_list(path):
    with open(path, encoding="utf-8") as fh:
        return [l.strip() for l in fh if l.strip() and not l.startswith("#")]


def cmd_suggest(args):
    """Find the closest real classname (fixes Kuban_G1 -> KubanG1 style mistakes)."""
    import difflib
    known = []
    for path in args.list or [DEFAULT_CLASSLIST]:
        if sniff_root(path) == "types":
            root, err = parse_xml(path)
            if err:
                sys.exit(f"{path}: {err}")
            known += [t.attrib["name"] for t in root.find_all("type") if "name" in t.attrib]
        else:
            known += [l.split("\t")[0] for l in read_list(path)]
    by_norm = defaultdict(list)
    for k in known:
        by_norm[norm(k)].append(k)
    status = 0
    for name in args.names:
        if name in known:
            print(f"OK      {name}")
            continue
        exact = by_norm.get(norm(name))
        if exact:
            print(f"FIX     {name} -> {', '.join(sorted(set(exact)))}  (отличие в регистре/подчёркиваниях)")
            continue
        close = difflib.get_close_matches(norm(name), list(by_norm), n=5, cutoff=0.6)
        if close:
            cands = sorted({c for n in close for c in by_norm[n]})
            print(f"MAYBE   {name} -> {', '.join(cands)}")
        else:
            print(f"UNKNOWN {name}  (нет в списке — проверь config.cpp/types.xml мода)")
            status = 1
    return status


def part_chance(item, full):
    if full:
        return 1.0
    low = item.lower()
    if "wheel" in low:
        return 0.8
    if low in ("carradiator", "carbattery", "truckbattery", "sparkplug", "glowplug"):
        return 0.6
    if low.startswith("headlight"):
        return 0.4
    if "_doors_hood" in low or "_doors_trunk" in low or low.endswith("hood") or low.endswith("trunk"):
        return 0.2
    if "_doors_" in low or "door" in low:
        return 0.3
    return 1.0  # tents, beacons and other cosmetic parts


def cmd_gen_spawnable(args):
    table = {}
    for line in read_list(args.attachments):
        cls, _, parts = line.partition("\t")
        table[cls.lower()] = [p for p in parts.split(",") if p]
    if args.wrap:
        print('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<spawnabletypes>')
    missing = []
    for cls in args.classes:
        parts = table.get(cls.lower())
        if parts is None:
            missing.append(cls)
            continue
        print(f"    <type name=\"{cls}\">")
        for item in parts:
            print("        <attachments chance=\"1.00\">")
            print(f"            <item name=\"{item}\" chance=\"{part_chance(item, args.full):.2f}\" />")
            print("        </attachments>")
        print("    </type>")
    if args.wrap:
        print("</spawnabletypes>")
    if missing:
        print(f"<!-- нет в {os.path.basename(args.attachments)}: {', '.join(missing)} -->", file=sys.stderr)
        return 1
    return 0

# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description="DayZ Central Economy helper")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="проверить файлы и/или папку миссии")
    c.add_argument("paths", nargs="+")
    c.add_argument("--map", help="chernarus|livonia|sakhal|nasdara или размер в метрах — проверка границ")
    c.add_argument("--radius", type=float, default=5.0, help="радиус совпадения точек, м (0 = не проверять)")
    c.add_argument("--shared-warn", type=int, default=3,
                   help="WARN, если точку делят столько событий или больше (default 3; ванилла делит по 2)")
    c.add_argument("-q", "--quiet", action="store_true", help="не показывать INFO")
    c.set_defaults(func=cmd_check)

    p = sub.add_parser("positions", help="вывести точки спавна")
    p.add_argument("file")
    p.add_argument("--event", help="regex по имени события")
    p.add_argument("--near", nargs=3, type=float, metavar=("X", "Z", "R"), help="только точки в радиусе R от X,Z")
    p.add_argument("--csv", action="store_true")
    p.set_defaults(func=cmd_positions)

    g = sub.add_parser("gen-events", help="сгенерировать блоки events.xml по cfgeventspawns")
    g.add_argument("file")
    g.add_argument("--prefix", default="Vehicle", help="брать только события с этим префиксом (default: Vehicle)")
    g.add_argument("--strip-prefix", default="", help="classname = имя события без этого префикса")
    g.add_argument("--class", dest="cls", action="append", metavar="EVENT=Class1,Class2",
                   help="явные classname для события (можно несколько раз)")
    g.add_argument("--nominal", type=int, default=1)
    g.add_argument("--distanceradius", type=int, default=500)
    g.add_argument("--wrap", action="store_true", help="обернуть в <events>…</events>")
    g.set_defaults(func=cmd_gen_events)

    t = sub.add_parser("gen-types", help="сгенерировать types.xml записи для машин")
    t.add_argument("classes", nargs="+")
    t.add_argument("--lifetime", type=int, default=3888000)
    t.add_argument("--restock", type=int, default=0)
    t.add_argument("--wrap", action="store_true", help="обернуть в <types>…</types>")
    t.set_defaults(func=cmd_gen_types)

    s = sub.add_parser("suggest", help="найти правильный classname (по списку мода или types.xml)")
    s.add_argument("names", nargs="+")
    s.add_argument("--list", action="append",
                   help="файл со списком classname (txt/tsv) или types.xml; default: references/rusforma_classnames.txt")
    s.set_defaults(func=cmd_suggest)

    sp = sub.add_parser("gen-spawnable", help="сгенерировать cfgspawnabletypes для машин RUSForma")
    sp.add_argument("classes", nargs="+")
    sp.add_argument("--attachments", default=DEFAULT_ATTACHMENTS, help="TSV: classname<TAB>детали через запятую")
    sp.add_argument("--full", action="store_true", help="все детали с шансом 1.0 (машина целиком)")
    sp.add_argument("--wrap", action="store_true", help="обернуть в <spawnabletypes>…</spawnabletypes>")
    sp.set_defaults(func=cmd_gen_spawnable)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
