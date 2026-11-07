# RUSForma_vehicles + файл этого репозитория

## Мод

* Steam Workshop: **RUSForma_vehicles** (ID 2536888090, по данным поиска). В 2024 часть исторической
  техники вынесена в отдельный мод **RUSForma_vehicles_historical**; тогда же добавлены VW Golf и трактор УМЗ.
  Автор пишет, что мод работает на Chernarus, Livonia и Sakhal.
* Нет класса в RUSForma_vehicles → ищи в RUSForma_vehicles_historical (военная/историческая техника).
* Серверные файлы от сообщества: `github.com/omniomi/dayz-rusforma_vehicles-files` (окт. 2024):
  `vehicletypes.xml`, `parttypes.xml`, `partvarianttypes.xml` (детали в мире не спавнятся: nominal 0),
  маркет-файлы DayZ Expansion (`_RusFormaVehicles.json`, `_RusFormaParts.json` и др.).
  Из них сделаны `rusforma_classnames.txt` (255 машин и вариантов) и `rusforma_attachments.tsv`
  (стандартные детали каждой машины) в этой папке.
* Номерные знаки: `number_gos_706`, `number_euro_1735`, `number_gos_MILICIA`, `number_gos_ARMY`,
  `number_gos_6832`, `number_gos_ARIADA`, `number_gos_Black_Squad`, `number_gos_POLIS`,
  `number_gos_nasha_rasha`, `RF_Number_Arctic_Long`, `RF_Number_Arctic_Short`.
* В обсуждениях мода есть жалобы, что машины пропадают после рестарта/без причины — при отладке
  проверять lifetime в types.xml, `economy.xml`, конфликты с другими модами (см. vehicles.md).

## Как называются детали

`<Класс>_wheel`, `<Класс>_WheelDouble` (сдвоенные задние у грузовиков/автобусов),
`<Класс>_doors_driver`, `_doors_codriver`, `_doors_cargo1…5`, `_doors_hood`, `_doors_trunk`,
`<Класс>_tent` (тент кузова), `UAZ_3163_migalki` (мигалки). Общие ванильные: `HeadlightH7`,
`CarRadiator`, `CarBattery` (легковые) или `TruckBattery` (грузовые/военные), `SparkPlug`.
Шаблон spawnabletypes: `dayz_ce.py gen-spawnable <Класс>`.

## Регистр и подчёркивания в classname

Пиши classname **ровно как в моде**. Разница в подчёркивании гарантированно ломает спавн;
на совпадение «без учёта регистра» не полагайся. Проверка: `dayz_ce.py suggest <имя> …`.

## Файл `rusforma_vehicles_cfgeventspawn` (корень репо)

Это фрагмент `cfgeventspawns.xml` (корень `<eventposdef>`, без расширения) для **Chernarus**:
координаты совпадают с ванильными точками Chernarus (например 6497/3667 ≈ ванильная точка VehicleCivilianSedan).
Его содержимое переносится в основной `cfgeventspawns.xml` миссии (CE не умеет брать этот файл через `<ce>`).

Состав (на 2026-11-07):

* `VehicleSpawnPoints` (строки 3–45) — 21 точка, в комментариях подписаны машины.
  **CE не связывает точку с машиной из комментария**; событие сработает, только если в events.xml
  есть `<event name="VehicleSpawnPoints">` со своими `children`.
* 42 события `VehicleCrSk_<Модель>` по 3 точки. Все используют те же 21 точку циклом по 7 тройкам —
  каждую точку делят 6–7 событий.
* 7 из 21 точки совпадают (±10 м) с ванильными точками Chernarus: #3 и #5 — VehicleCivilianSedan/
  VehicleHatchback02, #7, #11, #13 — VehicleSedan02, #14 — StaticPoliceCar, #19 — StaticContaminatedArea.

Найденные проблемы:

1. **ERROR: не закрыт `<event name="VehicleSpawnPoints">`** — нет `</event>` перед комментарием
   `<!-- LUAZ_969 -->` (строка 46). XML невалиден → CE выдаст ошибку парсинга в RPT и не прочитает
   cfgeventspawns.xml корректно (под угрозой и ванильные точки, если фрагмент вставлен в общий файл).
   Исправление — вставить `    </event>` после строки 45.
2. По 3 точки на событие и общие точки у 6–7 событий → nominal ≤ 3, события конкурируют за места,
   весь модовый транспорт стоит в одних и тех же 21 местах.
3. Имена событий ≠ classname. Это нормально (имя события любое, но с префиксом `Vehicle`),
   однако в events.xml `child type` должен быть настоящим classname:

| Событие | Правильный classname |
|---|---|
| VehicleCrSk_Kuban_G1 | `KubanG1`, `KubanG1_green` |
| VehicleCrSk_GAZ_21_Volga | `GAZ21_Volga` (+ `_black`, `_green`) |
| VehicleCrSk_Gaz_53_RF | `Gaz_53RF`, `Gaz_53RF_petrol_truck` |
| VehicleCrSk_Moskvich_407 | `moskvich_407` (+ `_grey`, `_double_blue`, `_double_red`) |
| VehicleCrSk_Opel_Blitz | `opel_blitz`, `opel_blitz_grey` |
| VehicleCrSk_M4_Tractor | `m4_tractor` (+ `_usa`, `_winter`) |
| VehicleCrSk_Artillery_Tractor | `artillery_tractor` (+ `_camo`, `_kung`, `_kung_camo`) |
| VehicleCrSk_LUAZ_969 | `LUAZ_969`? — нет в списке 2024 года, проверить в моде |
| комментарий «M3A1_Scout_Ca» | `M3A1_Scout_Car` |
| комментарий «GAZ_51» | `gaz_51` |
| комментарий «UAZ_27722» | базового нет, только варианты: `UAZ_27722_blue`, `_brown`, `_red`, `_yellow`, `_mchs`, `_ambulancia`, `_ambulancia2` |

Остальные модели из событий (URAL_375_1964, UAZ_469_Hunter, kraz_255B, VBL, KAVZ685_RF, ij_2715_RF,
LIAZ_677RF, vaz_2106_RF, VAZ_2109_RF, UAZ_3172, azlk_400, BRDM2_RF, UAZ_33094, GAZ_13_Chaika, ZAZ_968,
ZIL_130, ZIL_130_ac40, GAZ_12, kamaz_4310RUS, T_34_76, VAZ_21099R, F1_Pickup, ZAZ_965, VAZ_2104RF,
GAZ_69_rus, IJ_2140_SL, ZIL133_double, UAZ_469_army, Gaz_233002_Tiger, AZLK_2141RF, VAZ_2105_RUS,
UAZ_Patrot_Pikap, ZIL_157_rus) совпадают с classname 1-в-1.

Быстрая проверка: `python3 -I .claude/skills/dayz-server/scripts/dayz_ce.py check rusforma_vehicles_cfgeventspawn --map chernarus`.
