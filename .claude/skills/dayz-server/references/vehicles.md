# Транспорт в DayZ: спавн, моды, отладка

## Цепочка спавна машины (все 4 звена обязательны)

| # | Файл | Что нужно | Если нет |
|---|---|---|---|
| 1 | `db/types.xml` (или `<ce>`-файл с `type="types"`) | `<type name="Класс">` (nominal 0, min 0) | CE не знает класс → не спавнит |
| 2 | `db/events.xml` (или `<ce>` `type="events"`) | `<event name="VehicleX">` с `<child type="Класс">`, `position=fixed`, `active=1` | нечего спавнить |
| 3 | `cfgeventspawns.xml` (только основной файл!) | `<event name="VehicleX">` с `<pos x z a/>` | нет мест → не спавнит |
| 4 | `cfgspawnabletypes.xml` (или `<ce>` `type="spawnabletypes"`) | `<type name="Класс">` с колёсами/деталями | машина без колёс/АКБ/дверей |

Плюс: мод подключён на сервере (`-mod=@…`), его `.bikey` лежит в `keys/`, класс машины
наследуется от `CarScript` (или добавлен свой `<rootclass act="car">` в `cfgeconomycore.xml`).

## Добавить модовую машину — пошагово

Скрипт: `.claude/skills/dayz-server/scripts/dayz_ce.py` (из корня репозитория: `python3 -I <скрипт> <команда> …`).

1. Узнать точный classname: types.xml в папке мода / config.cpp / `references/rusforma_classnames.txt`.
   Проверить: `python3 -I .claude/skills/dayz-server/scripts/dayz_ce.py suggest Kuban_G1` → `KubanG1`.
2. types: `dayz_ce.py gen-types KubanG1 KubanG1_green --wrap > rf_types.xml` (или дописать в db/types.xml).
3. spawnabletypes: `dayz_ce.py gen-spawnable KubanG1 --wrap > rf_spawnabletypes.xml` (`--full` = все детали 100%).
4. Точки: дописать `<event name="VehicleKubanG1">` с 10+ `<pos>` в основной `cfgeventspawns.xml`.
5. events: `dayz_ce.py gen-events cfgeventspawns.xml --prefix VehicleKubanG1 --class VehicleKubanG1=KubanG1,KubanG1_green --nominal 2 --wrap > rf_events.xml`.
6. Подключить файлы через `<ce folder="…">` в `cfgeconomycore.xml` (см. central-economy.md).
7. `dayz_ce.py check <папка миссии> --map chernarus` → 0 ERROR.
8. Остановить сервер → при необходимости вайп машин (ниже) → запуск → проверить RPT.

## Правила для точек (`<pos>`)

* Ровное открытое место у дороги/парковки; не в зданиях, не на склонах, не под деревьями/мостами.
* `a` — поворот в градусах. Бери координаты и угол in-game (админ-тулы показывают позицию и направление)
  или с iZurvive (только x/z; угол подбирать по дороге).
* Количество точек ≫ nominal (ванилла: 55–111 точек на nominal 8). Минимум — вдвое больше nominal.
* Точки разных событий лучше не совмещать: занятое место недоступно другим событиям,
  а при 1-в-1 совпадении все машины скапливаются в одних и тех же местах. Ванилла делит максимум 2 события на точку.
* `distanceradius` (500 м в ванилле) — экземпляры одного события не встанут ближе этого друг к другу.
  Если все точки события в одном городе, больше одной машины там не появится.
* Для крупной техники (грузовики, БТР, автобусы) места нужно больше — коллизия при спавне ломает/подбрасывает машину.

## Персистентность и вайп машин

* `db/economy.xml`: `<vehicles init="1" load="1" respawn="1" save="1"/>` — машины сохраняются между рестартами.
* Хранилище: `mpmissions/<миссия>/storage_<instanceId>/data/` (instanceId из serverDZ.cfg, обычно 1):
  `vehicles.bin` (машины), `events.bin`, `types.bin`, `building.bin`, `dynamic_*.bin`; `players.db` — игроки.
* Изменили точки/события, а машины «старые» → сервер стоит, удалить `storage_1/data/vehicles.bin`
  (и при смене событий — `events.bin`). Сделай бэкап. Полный вайп = удалить `storage_1` целиком.
* Машины, заспавненные/купленные через трейдер (Expansion Market и т.п.), живут по правилам мода трейдера.

## Отладка «машины не спавнятся / пропадают»

1. XML валиден? `dayz_ce.py check …`. Одна ошибка (незакрытый `<event>`) → CE не прочитает весь файл.
2. Включить логи: в `cfgeconomycore.xml` `<default name="log_ce_vehicle" value="true"/>`,
   смотреть `profiles/*.RPT` (строки CE/vehicle, ошибки парсинга с номером строки).
3. Имя события совпадает во всех файлах (регистр!) и начинается с `Vehicle`.
4. `child type` = реальный classname (регистр, подчёркивания: `GAZ21_Volga`, а не `GAZ_21_Volga`).
5. `active=1`, `nominal>0`, у `child` `max>0`.
6. Точек достаточно, они не внутри объектов и не заняты другими событиями.
7. Мод реально загружен (в RPT есть его PBO, нет ошибок подписи), ключ в `keys/`.
8. Пропадают после рестарта → проверить `economy.xml` (`save="1"`), lifetime в types.xml (слишком маленький
   + `remove_damaged`), не удаляется ли `vehicles.bin` скриптом рестарта, не конфликтуют ли моды
   (в обсуждениях RUSForma есть жалобы на исчезновение машин — проверять lifetime и конфликты).
9. Машина появилась и взорвалась/улетела → точка в коллизии (дом, забор, другая машина), неверная высота `y`.

## Ванильные события транспорта (1.30)

| Карта | События |
|---|---|
| Chernarus | VehicleBoat, VehicleCivilianSedan, VehicleHatchback02, VehicleMotorbike, VehicleOffroad02, VehicleOffroadHatchback, VehicleSedan02, VehicleTruck01 (+ пустой VehicleTransitBus в cfgeventspawns) |
| Livonia (enoch) | то же |
| Sakhal | VehicleBoat, VehicleCivilianSedan, VehicleHatchback02, VehicleMilitaryBoat, VehicleMotorbike, VehicleOffroadHatchback, VehicleSedan02, VehicleTruck01 |
| Nasdara | как Chernarus, но `VehicleBoat` active=0 и без точек (лодок нет); VehicleMotorbike nominal 30, 7 цветов мотоциклов, `Offroad_02_Beige` |

Nominal, число точек и classname по картам — `maps.md`, раздел «Различия ванильных миссий».

Ванильные классы: `CivilianSedan(_Black/_Wine)`, `Sedan_02*`, `Hatchback_02*`, `OffroadHatchback*`,
`Offroad_02`, `Truck_01_Covered*`, `Boat_01_*`, мотоцикл — смотри `children` в ванильном events.xml.
