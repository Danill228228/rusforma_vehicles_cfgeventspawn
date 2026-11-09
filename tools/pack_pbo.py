#!/usr/bin/env python3
"""
pack_pbo.py — простой упаковщик PBO (без сжатия и без подписи) для тестовых модов DayZ.

Нужен, чтобы собрать тестовый мод без DayZ Tools. Для DayZDiag (офлайн или локальный
сервер с verifySignatures = 0) подписи не требуются. Для боевого сервера мод нужно
собирать и подписывать штатно через DayZ Tools (Addon Builder + DS Utils).

Запуск:
    python tools/pack_pbo.py prototype/HatchP0 prototype/@HatchP0/addons/HatchP0.pbo --prefix HatchP0
    python tools/pack_pbo.py --list prototype/@HatchP0/addons/HatchP0.pbo   # проверить содержимое

Формат: заголовок «Vers» с расширением prefix, записи файлов, пустая завершающая запись,
данные файлов, затем байт 0x00 и SHA1 всего предыдущего содержимого.
"""

import argparse
import hashlib
import os
import struct
import sys

VERS = 0x56657273  # 'Vers'
SKIP_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}


def collect_files(src_dir):
    entries = []
    for root, dirs, files in os.walk(src_dir):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(files):
            if name.startswith(".") or name in SKIP_NAMES:
                continue
            full = os.path.join(root, name)
            rel = os.path.relpath(full, src_dir).replace("/", "\\")
            with open(full, "rb") as f:
                data = f.read()
            entries.append((rel, data))
    return entries


def pack(src_dir, out_path, prefix):
    entries = collect_files(src_dir)
    if not any(rel.lower() == "config.cpp" for rel, _ in entries):
        raise SystemExit(f"ошибка: в {src_dir} нет config.cpp")

    header = bytearray()
    # Первая запись: пустое имя, тип 'Vers', затем расширения заголовка (key\0value\0 ... \0)
    header += b"\x00" + struct.pack("<5I", VERS, 0, 0, 0, 0)
    header += b"prefix\x00" + prefix.encode("ascii") + b"\x00"
    header += b"product\x00dayz\x00"
    header += b"\x00"

    for rel, data in entries:
        header += rel.encode("ascii") + b"\x00"
        # тип 0 (без сжатия), originalSize 0, reserved 0, timestamp 0 (воспроизводимая сборка), dataSize
        header += struct.pack("<5I", 0, 0, 0, 0, len(data))

    # Завершающая пустая запись
    header += b"\x00" + struct.pack("<5I", 0, 0, 0, 0, 0)

    body = bytes(header) + b"".join(data for _, data in entries)
    digest = hashlib.sha1(body).digest()

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(body + b"\x00" + digest)

    print(f"собрано: {out_path} ({len(entries)} файлов, prefix={prefix})")
    for rel, data in entries:
        print(f"  {rel}  {len(data)} байт")


def read_asciiz(buf, pos):
    end = buf.index(b"\x00", pos)
    return buf[pos:end].decode("ascii"), end + 1


def list_pbo(path):
    with open(path, "rb") as f:
        buf = f.read()

    pos = 0
    ext = {}
    files = []
    first = True
    while True:
        name, pos = read_asciiz(buf, pos)
        mime, orig, _res, _ts, size = struct.unpack_from("<5I", buf, pos)
        pos += 20
        if first and name == "" and mime == VERS:
            first = False
            while True:
                key, pos = read_asciiz(buf, pos)
                if key == "":
                    break
                val, pos = read_asciiz(buf, pos)
                ext[key] = val
            continue
        first = False
        if name == "":
            break
        files.append((name, mime, size))

    data_start = pos
    total = sum(size for _, _, size in files)
    body_end = data_start + total
    ok_sha = buf[body_end:body_end + 1] == b"\x00" and \
        hashlib.sha1(buf[:body_end]).digest() == buf[body_end + 1:body_end + 21]

    print(f"файл:     {path}")
    print(f"заголовок: {ext}")
    for name, mime, size in files:
        print(f"  {name}  {size} байт  (тип {mime})")
    print(f"SHA1:     {'OK' if ok_sha else 'НЕ СОВПАДАЕТ'}")
    return 0 if ok_sha else 1


def main():
    ap = argparse.ArgumentParser(description="Упаковщик PBO для тестовых модов DayZ")
    ap.add_argument("src", help="папка мода (с config.cpp) или .pbo при --list")
    ap.add_argument("out", nargs="?", help="путь к создаваемому .pbo")
    ap.add_argument("--prefix", help="prefix PBO (обычно имя папки мода)")
    ap.add_argument("--list", action="store_true", help="показать содержимое .pbo и проверить SHA1")
    args = ap.parse_args()

    if args.list:
        return list_pbo(args.src)

    if not args.out:
        ap.error("укажите путь к .pbo")
    prefix = args.prefix or os.path.basename(os.path.normpath(args.src))
    pack(args.src, args.out, prefix)
    return 0


if __name__ == "__main__":
    sys.exit(main())
