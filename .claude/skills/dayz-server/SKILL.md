---
name: dayz-server
description: Настройка и отладка серверов DayZ — Central Economy (types.xml, events.xml, cfgeventspawns.xml, cfgspawnabletypes.xml, cfgeconomycore.xml, globals.xml, cfggameplay.json, init.c, serverDZ.cfg), спавн ванильного и модового транспорта (RUSForma_vehicles), координаты карт Chernarus/Livonia/Sakhal/Nasdara, моды, ключи, логи, вайпы. Use for any DayZ server/mission file task, vehicle or loot spawn problem, or edits to this repository's cfgeventspawn file.
when_to_use: Триггеры — DayZ, дейзи, спавн машин, машины не спавнятся или пропадают, types.xml, events.xml, cfgeventspawns, добавить машину или мод на сервер, RUSForma, Central Economy, лут, вайп.
argument-hint: "[задача или путь к файлу/миссии]"
---

# DayZ server / Central Economy

## Сначала

1. Проверь, что уже известно: `CLAUDE.md` репозитория и (если ты субагент `dayz-expert`) свою память.
2. Определи файлы по корневому тегу, а не по имени — в этом репо файл без расширения:
   `rusforma_vehicles_cfgeventspawn` = фрагмент `cfgeventspawns.xml` (`<eventposdef>`) для Chernarus.
3. Прогони проверку **до** правок, чтобы видеть исходные ошибки:

```bash
python3 -I ${CLAUDE_SKILL_DIR}/scripts/dayz_ce.py check <файл|папка миссии> --map chernarus
```

## Скрипт `${CLAUDE_SKILL_DIR}/scripts/dayz_ce.py` (только stdlib)

| Команда | Что делает |
|---|---|
| `check PATH… [--map M] [--radius 5] [-q]` | XML-валидность с номером строки (и точное место незакрытого `<event>`), дубли, точки вне карты, общие точки у разных событий, nominal vs число точек, `child type` есть в types, машины без spawnabletypes, файлы из `<ce folder>`. Папка миссии читается целиком. Exit 1 при ERROR |
| `positions FILE [--event RE] [--near X Z R] [--csv]` | таблица точек (с номерами строк) |
| `gen-events FILE --prefix P [--strip-prefix P] [--class EV=A,B] [--nominal N] [--wrap]` | блоки events.xml из событий cfgeventspawns |
| `gen-types CLASS… [--wrap]` | записи types.xml для машин |
| `gen-spawnable CLASS… [--full] [--wrap]` | cfgspawnabletypes с деталями (RUSForma — по `references/rusforma_attachments.tsv`) |
| `suggest NAME… [--list types.xml]` | правильный classname: `Kuban_G1` → `KubanG1` |

Ванильные миссии всех четырёх карт проходят `check` с 0 ERROR — ERROR в чужом файле означает реальную проблему.

## Справочники (читай нужный, не всё подряд)

| Файл | Когда |
|---|---|
| `references/central-economy.md` | формат и поля любого файла миссии, `<ce folder>`, globals, economy |
| `references/vehicles.md` | добавить машину, точки спавна, вайп машин, «не спавнятся/пропадают» |
| `references/rusforma.md` | мод RUSForma_vehicles, имена деталей, разбор файла этого репо и таблица исправлений classname |
| `references/rusforma_classnames.txt` / `rusforma_attachments.tsv` | 255 classname мода и их стандартные детали (данные 2024 г.) |
| `references/maps.md` | система координат, размеры карт, ориентиры Chernarus |
| `references/server-setup.md` | serverDZ.cfg, параметры запуска, моды и ключи, логи, init.c, рестарты |

Нужен ванильный файл целиком — официальный репо: `git clone --depth 1 https://github.com/BohemiaInteractive/DayZ-Central-Economy`
(в scratchpad, не в проект).

## Правила, которые чаще всего ломают сервер

1. Один незакрытый тег → CE не читает файл корректно. Всегда `check` после правки.
2. Машина = 4 звена: types + events (`child type`) + cfgeventspawns (`<pos>`) + spawnabletypes. Нет любого — нет машины или она без колёс.
3. Имена событий совпадают во всех файлах до символа; у транспорта префикс `Vehicle`.
4. `child type` — реальный classname мода (регистр и `_` важны). Проверяй `suggest`.
5. `cfgeventspawns.xml` нельзя вынести в `<ce folder>` — модовые точки дописываются в основной файл. types/events/spawnabletypes — можно и нужно выносить.
6. Точек ≫ nominal (ванилла 55–111 точек на nominal 8); разные события не должны сидеть на одних точках.
7. Машины персистентны (`storage_1/data/vehicles.bin`) — после смены точек/событий может понадобиться вайп машин.
8. Не трогай `areaflags.map` руками, не правь ванильные файлы без бэкапа, не меняй координаты «на глаз».

## Порядок работы

1. Прочитать файлы и выполнить `check` → записать исходное состояние.
2. Править точечно (Edit), сохраняя стиль файла (табы/пробелы, комментарии).
3. `check` ещё раз → 0 ERROR; объяснить оставшиеся WARN.
4. В ответе: что изменено (файл:строка), что сделать на сервере (куда положить файл, `<ce>` блок,
   рестарт, нужен ли вайп `vehicles.bin`), что не проверено (например, наличие класса в текущей версии мода).
