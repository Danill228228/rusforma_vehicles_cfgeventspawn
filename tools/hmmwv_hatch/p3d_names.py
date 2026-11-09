#!/usr/bin/env python3
"""
p3d_names.py — офлайн-сканер имён в моделях DayZ P3D (бинаризованный ODOL или MLOD).

Назначение: выяснить, есть ли у ванильной модели M1025 (Offroad_02.p3d) отдельная
кость, named selection или анимация model.cfg для верхнего люка. Модель при этом
не редактируется и не дебинаризуется.

Бинаризованный ODOL хранит имена костей, selection, прокси и источников анимаций
model.cfg как ASCII-строки, завершённые нулём. Скрипт извлекает их и:
  * проверяет, какие ИЗВЕСТНЫЕ AnimationSources из config.cpp (DoorsDriver, ...)
    присутствуют в модели. Это проверка метода: если двери найдены, извлечение работает;
  * отмечает имена, похожие на люк, башню или крышу;
  * выводит похожие на анимации имена, которых НЕТ в AnimationSources конфига
    (неиспользуемая анимация, если она есть в модели, окажется среди них).

Запуск:
    python p3d_names.py P:\\DZ\\vehicles\\wheeled\\Offroad_02\\Offroad_02.p3d
    python p3d_names.py Offroad_02.p3d --all            # все строки
    python p3d_names.py Offroad_02.p3d --json out.json  # сохранить результат

Где взять файл (оригинальный PBO не изменяется):
  * DayZ Tools -> Workdrive / «Extract Game Data» -> P:\\DZ\\vehicles\\wheeled\\Offroad_02\\
  * или распаковать <DayZ>\\Addons\\vehicles_wheeled.pbo (DayZ Tools BankRev или любой
    PBO-инструмент) в отдельную папку.

Скрипт только читает файл. Он ничего не изменяет и не дебинаризует модель.
"""

import argparse
import json
import re
import struct
import sys

# AnimationSources, которые ванильный config.cpp задаёт для Offroad_02
# (собственные и унаследованные от CarScript).
KNOWN_CONFIG_SOURCES = [
    "DoorsDriver", "DoorsCoDriver", "DoorsCargo1", "DoorsCargo2",
    "DoorsHood", "DoorsTrunk",
    "HideDestroyed_1_1", "HideDestroyed_1_2", "HideDestroyed_2_1", "HideDestroyed_2_2",
    "AnimHitWheel_1_1", "AnimHitWheel_1_2", "AnimHitWheel_2_1", "AnimHitWheel_2_2",
    "HitDoorsHood", "HitDoorsTrunk", "HitDoorsDrivers", "HitDoorsCoDrivers", "HitDoorsCargo",
    "damper_1_1", "damper_2_1", "damper_1_2", "damper_2_2",
]

# Ключевые слова для люка, башни, крыши (англ. и чешск.: в BI часто используют чешские имена).
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
    return seen  # имя -> смещение первого вхождения


def looks_like_identifier(s):
    # Имена костей, selection и источников: без пробелов, разумной длины.
    return 2 < len(s) <= 64 and " " not in s and re.fullmatch(r"[A-Za-z0-9_\\.:\-]+", s) is not None


def main():
    # На Windows при перенаправлении вывода в файл кодировка может не поддерживать кириллицу.
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass

    ap = argparse.ArgumentParser(description="Сканер имён DayZ P3D (поиск люка у Offroad_02)")
    ap.add_argument("p3d", help="путь к файлу .p3d")
    ap.add_argument("--min-len", type=int, default=3, help="минимальная длина строки")
    ap.add_argument("--all", action="store_true", help="вывести все извлечённые строки")
    ap.add_argument("--json", metavar="FILE", help="сохранить результат в JSON")
    args = ap.parse_args()

    with open(args.p3d, "rb") as f:
        data = f.read()

    magic, version = read_header(data)
    print(f"файл:     {args.p3d}")
    print(f"размер:   {len(data)} байт")
    print(f"формат:   {magic} (версия {version})")
    if magic not in ("ODOL", "MLOD"):
        print("ВНИМАНИЕ: неожиданная сигнатура; возможно, это не P3D или файл упакован.")

    strings = extract_strings(data, args.min_len)
    idents = {s: o for s, o in strings.items() if looks_like_identifier(s)}
    lower_map = {s.lower(): s for s in idents}

    print(f"строк:    {len(strings)} уникальных, из них {len(idents)} похожи на имена\n")

    # 1. Проверка метода на известных источниках дверей.
    print("== 1. AnimationSources из config.cpp, найденные в модели ==")
    found_known, missing_known = [], []
    for src in KNOWN_CONFIG_SOURCES:
        hit = lower_map.get(src.lower())
        (found_known if hit else missing_known).append(src)
    print("  найдены:    " + (", ".join(found_known) or "-"))
    print("  не найдены: " + (", ".join(missing_known) or "-"))
    if not found_known:
        print("  !! Не найден ни один источник дверей. Возможно, имена хранятся в сжатом виде;")
        print("     в этом случае используйте внутриигровую диагностику (diag_offroad02_console.c).")
    print()

    # 2. Кандидаты на люк, башню, крышу.
    print("== 2. Кандидаты на люк / башню / крышу ==")
    hatch_hits = []
    for s, off in sorted(idents.items(), key=lambda kv: kv[1]):
        sl = s.lower()
        if any(k in sl for k in HATCH_KEYWORDS):
            hatch_hits.append((s, off))
            print(f"  0x{off:08X}  {s}")
    if not hatch_hits:
        print("  - (нет имён, совпадающих с ключевыми словами)")
    print()

    # 3. Похожие на двери и анимации имена, которых нет в config.cpp.
    print("== 3. Имена, похожие на двери и анимации, которых нет в config.cpp ==")
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
        print("  - нет")
    print()

    # 4. Прокси (места экипажа и т. п.).
    print("== 4. Прокси / позиции экипажа ==")
    proxies = [(s, o) for s, o in sorted(strings.items(), key=lambda kv: kv[1])
               if "proxy" in s.lower() or s.lower().startswith(("crew", "pos_", "seat_"))]
    for s, off in proxies:
        print(f"  0x{off:08X}  {s}")
    if not proxies:
        print("  - нет")
    print()

    if args.all:
        print("== Все строки ==")
        for s, off in sorted(strings.items(), key=lambda kv: kv[1]):
            print(f"  0x{off:08X}  {s}")

    verdict = (
        "НАЙДЕНЫ КАНДИДАТЫ НА ЛЮК: проверьте их в игре (diag_offroad02_console.c)"
        if hatch_hits else
        "Имён люка НЕ найдено: скорее всего, люк — статичная геометрия (вариант B)"
    )
    if not found_known:
        verdict = "НЕОПРЕДЕЛЁННО: метод не нашёл даже источники дверей"
    print("ВЫВОД: " + verdict)

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
        print(f"JSON сохранён: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
