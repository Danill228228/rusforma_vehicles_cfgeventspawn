# Карты и координаты

## Система координат

* `x` — на восток, `z` — на север, метры от юго-западного угла карты; `y` — высота над уровнем моря.
* В `cfgeventspawns.xml` обычно только `x`, `z`, `a` (поворот в градусах; `-1` = случайный).
* Скрипт (Enforce) использует вектор `"x y z"` — **порядок другой**: `Vector(x, y, z)`, высота посередине.
* iZurvive/DayZ-карты в браузере показывают x/z (иногда как «X / Y» — второе число и есть `z`).
* Позиции и направление удобно снимать в игре админ-модами (VPPAdminTools, Community Online Tools)
  или в DayZ Editor (экспорт позиций).

## Ванильные миссии (обновление 1.30)

| Карта | Папка миссии (`template` в serverDZ.cfg) | Размер, м | Примечание |
|---|---|---|---|
| Chernarus | `dayzOffline.chernarusplus` | 15360 | базовая игра |
| Livonia | `dayzOffline.enoch` | 12800 | DLC |
| Sakhal | `dayzOffline.sakhal` | 15360 (CE-координаты до ~15000) | DLC Frostline, есть `VehicleMilitaryBoat` |
| Nasdara | `dayzOffline.nasdara` | 16384 (267 км², CE-координаты до ~15745) | DLC Badlands, вышло с 1.30 (окт. 2026), пустынная карта |

Размеры подтверждены `<world size>` в `CETool/<Карта>/<карта>.xml` и заголовком `areaflags.map` (коммит f220b29).

Сезонные миссии в официальном репо: `ChristmasOffline.*`, `halloweenOffline.*`, `valentinesOffline.*`,
`WalpurgisNightOffline.*`, `PaydayOffline.*` (+ устаревший `halloween.chernarusplus`) — оверлеи, см. `mission-files.md`.

Проверка выхода за карту: `dayz_ce.py check … --map chernarus|livonia|sakhal|nasdara`.

## Ориентиры Chernarus (точки спавна игроков из ванильного cfgplayerspawnpoints.xml)

| Место | x | z |
|---|---|---|
| WestCherno | 6063 | 1932 |
| Cherno | 5416 | 3086 |
| EastCherno | 8041 | 3332 |
| Balota | 4321 | 2399 |
| WestElektro | 8748 | 2357 |
| Pusta | 9283 | 3120 |
| EastElektro | 10577 | 2051 |
| Kamyshovo | 11831 | 3400 |
| Solnechny | 13425 | 5776 |
| Orlovets | 13230 | 6980 |
| Nizhnee | 13044 | 7886 |
| Berezino | 11076 | 8907 |
| SouthBerezino | 12641 | 9451 |
| NorthBerezino | 13161 | 10329 |
| Olsha | 13340 | 12708 |
| Svetlojarsk | 14286 | 13009 |
| Dobroye | 13294 | 15056 |

Все — побережье (юг и восток). Для глубины карты ориентируйся по iZurvive.
Найти точки событий рядом с местом: `dayz_ce.py positions cfgeventspawns.xml --near 6500 2500 800`.

## Различия ванильных миссий (1.30, коммит f220b29 от 16.10.2026)

Подсчитано по файлам официального репо. Форматы файлов — `central-economy.md` и `mission-files.md`.

| | Chernarus | Livonia | Sakhal | Nasdara |
|---|---|---|---|---|
| типов в types.xml / с nominal>0 / сумма nominal | 2382 / 1115 / 21 090 | 2391 / 1039 / 13 800 | 2404 / 1041 / 11 662 | 2411 / 1103 / 25 080 |
| событий / active=1 | 61 / 51 | 54 / 46 | 63 / 43 | 62 / 39 |
| зданий с лутом (mapgrouppos) / прототипов | 11 679 / 446 | 5 753 / 456 | 8 332 / 525 | 13 717 / 755 |
| value-флаги | Tier1–4, Unique | **нет Tier4** (Tier1–3, Unique) | Tier1–4, Unique | Tier1–4 объявлен, но в types не используется |
| доп. usage | Historical | Special, Underground | Special, Underground | Historical, **MilitaryEast, MilitaryWest** |
| `cfggameplay.json` version | 123 | 123 | 123 | 130 |
| динамический газ (`StaticContaminatedArea`) | да, 82 точки | да, 37 | нет | нет |
| дата в init.c | 20 сентября | 17 июля | 1 февраля | 30 апреля |

Глобальные настройки (`db/globals.xml`, `db/economy.xml`) у всех карт одинаковы.

### Транспорт: nominal / число точек в cfgeventspawns

| Событие | Chernarus | Livonia | Sakhal | Nasdara |
|---|---|---|---|---|
| VehicleCivilianSedan | 8 / 55 | 8 / 40 | 4 / 27 | 8 / 47 |
| VehicleSedan02 | 8 / 59 | 8 / 30 | 4 / 47 | 8 / 40 |
| VehicleHatchback02 | 8 / 56 | 8 / 39 | 4 / 60 | 8 / 52 |
| VehicleOffroadHatchback | 8 / 81 | 8 / 40 | 4 / 35 | 8 / 44 |
| VehicleOffroad02 | 3 / 21 | 3 / 21 | — | 5 / 21 |
| VehicleTruck01 | 8 / 111 | 8 / 50 | 4 / 25 | 6 / 27 |
| VehicleMotorbike | 25 / 97 | 12 / 35 | 12 / 70 | 30 / 102 |
| VehicleBoat | 17 / 72 | 5 / 17 | 14 / 63 | 5 / 0, **active=0** (лодок нет) |
| VehicleMilitaryBoat | — | — | 8 / 34 (saferadius и cleanupradius 1000) | — |

Classname в `children` (с max>0):

* **Chernarus, Livonia**: `CivilianSedan`, `CivilianSedan_Black`, `CivilianSedan_Wine`; `Sedan_02`, `Sedan_02_Grey`, `Sedan_02_Red`;
  `Hatchback_02`, `Hatchback_02_Black`, `Hatchback_02_Blue`; `OffroadHatchback`, `OffroadHatchback_Blue`, `OffroadHatchback_White`;
  `Offroad_02`; `Truck_01_Covered`, `Truck_01_Covered_Blue`, `Truck_01_Covered_Orange`; `Boat_01_Black`, `Boat_01_Blue`, `Boat_01_Orange`
  (`Boat_01_Camo` у Chernarus с max=0); `Motorbike_01_Blue`, `Motorbike_02_Red`.
* **Sakhal**: как выше, но `Hatchback_02` только обычный и `_Blue`, нет `Offroad_02`; `VehicleBoat` = `Boat_01_Blue`/`_Orange`,
  `VehicleMilitaryBoat` = `Boat_01_Black`/`Boat_01_Camo`.
* **Nasdara**: по одному цвету — `CivilianSedan`, `Hatchback_02`, `OffroadHatchback_White`, `Sedan_02_Grey`, `Truck_01_Covered`,
  новый `Offroad_02_Beige`; мотоциклы — `Motorbike_01_Blue`, `Motorbike_01_Red`, `Motorbike_01_Yellow`, `Motorbike_02_Blue`,
  `Motorbike_02_Green`, `Motorbike_02_Red`, `Motorbike_02_Yellow` (все 7 classname есть в types всех 4 карт).
* У `VehicleOffroad02` и `VehicleTruck01` на Nasdara есть `<secondary>InfectedArmy</secondary>`.
* Огрехи ванилы: `VehicleMotorbike` nominal > max на всех картах (25/12/12/30 при max 11), у Livonia child `Offroad_02` min 3 > max 2,
  у Chernarus/Livonia в cfgeventspawns пустой `VehicleTransitBus` без события (`TransitBus` в cfgignorelist).
* Мотоциклы требуют `<rootclass name="MotorbikeScript" act="car">` в cfgeconomycore.xml (есть во всех ваниллах 1.30).

### Особые события по картам

| Карта | Статика / предметы (точек) | Заражённые | Животные (cfgenvironment) |
|---|---|---|---|
| Chernarus | `StaticHeliCrash` (`Wreck_UH1Y`, 95), `StaticMilitaryConvoy` (23, группы), `StaticTrain` (21), `StaticPoliceSituation` (39), `StaticAirplaneCrate` (28, только тут), `ItemPlanks` (295); `StaticPoliceCar` (300 точек) **выключен** | `InfectedArmyDesert` (secondary у конвоя) | Deer, Cow, Goat, Sheep, RoeDeer, Wolf, WildBoar, Pig, Bear + Hen, Hare, Fox |
| Livonia | `StaticHeliCrash` (`Wreck_Mi8_Crashed`, 79), конвой (14), поезд (14), PoliceSituation (33), `ItemPlanks` (78); PoliceCar (135) выключен | `InfectedArmyConvoy` | как Chernarus |
| Sakhal | `StaticBoatFishing` (30), `StaticBoatMilitary` (35), `StaticContainerLocked` (`Land_ContainerLocked_Blue/Yellow_DE`, 114), `StaticScientist` (группа `Scientist`, 27), `StaticAmbulance` (43), `StaticPoliceCar` (71, включён), HeliCrash (31); поезд, конвой, PoliceSituation, AirplaneCrate выключены | `InfectedScientist` (`ZmbM_NBC_White`), `InfectedArmyHeavy`, `InfectedBonfire` (выкл.) | Reindeer (новое), Goat, Sheep, Wolf, Bear + Hare, Fox (Hen выкл.); `TrajectoryCraterellus` (грибы) |
| Nasdara | `ItemBricks` (`PileOfBricks`, 122; `ItemPlanks` выкл.), `StaticHeliCrash` (Mi-24 TK + Mi-8, 53), `StaticHeliCrashBig` (`StaticObj_Wreck_Chinook_DE`, 33), `StaticWaterTruck` (цистерны, 66), `StaticContainerLocked` (`Land_Mil_ContainerHabitat_Armory_Locked_Green_DE`, 28), `StaticPoliceCar` (остовы УАЗ, 69), конвой (23) | `InfectedArmyION`, `InfectedArmyConvoy` (`ZmbM_takiSoldier_*`); выкл.: ArmyHard, Firefighter, NBC, Prisoner | Dog (доберман/овчарка, `DZDogGroupBeh`), Mouflon (`Animal_OvisGmelini`), Goat и Sheep раздельно, WildBoar (Cow — пустая территория, событие выкл.) + Hen, Hare, Fox, **AmbientLizard** (`Animal_VaranusGriseus`); волков, медведей, оленей нет; `TrajectoryFig` |

### Что нового в Nasdara / 1.30 (для админа)

* Новые файлы `cfgbunkerbroadcast.json` (радиотрансляция кодов бункеров) и `cfgexternallocks.json`; в cfggameplay v130 —
  `ExternalLockData`, `SandstormData`, `bunkerBroadcastEnabled`, `lightingConfig 3`, `disablePersonalLight true`.
* Разрушаемые дома: root-класс `HouseDestructible`, в types Nasdara 43 записи `Land_House_*`/`Water_Well_N1`/`Land_IrrigationTunnel_Entrance_01`
  (nominal 0, `crafted=1`, lifetime 3888000) — нужны для сохранения состояния, не удалять **[вывод]**.
* Зоны: 6 газовых в тоннелях + 15 `OilPitArea`; 1076 подземных триггеров (тоннели, ирригация, бункеры).
* Стартовая одежда задаётся в init.c (`RemoveAllItems()` + Kameez/Shalwar/сандалии).
* Баг ванилы: зоны `InfedctedReligious` в `env/zombie_territories.xml` (31 шт.) не совпадают с событием `InfectedReligious`.
* Сезонных папок для Nasdara в репо нет.
