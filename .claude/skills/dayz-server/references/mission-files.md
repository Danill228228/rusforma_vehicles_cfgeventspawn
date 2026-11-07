# Остальные файлы миссии (1.30): формат, ключи, особенности

Дополняет `central-economy.md` (types/events/cfgeventspawns/spawnabletypes/globals/economy там).
Источник: официальный репо `BohemiaInteractive/DayZ-Central-Economy`, коммит `f220b29` (16.10.2026, обновление 1.30),
4 основные миссии + 14 сезонных папок + `CETool/`. Всё ниже прочитано в этих файлах, кроме пометок:
**[вывод]** — выведено из данных/имён ключей; **[не сверено]** — по памяти о вики BI, страница из сессии недоступна.

## Какие файлы есть у какой карты

| Файл | Chernarus | Livonia (enoch) | Sakhal | Nasdara |
|---|---|---|---|---|
| `cfggameplay.json` version | 123 | 123 | 123 | **130** |
| `cfgEffectArea.json` | `cfgEffectArea.json` | `cfgEffectArea.json` | `cfgeffectarea.json` | `cfgeffectarea.json` |
| `cfgIgnoreList.xml` | `cfgIgnoreList.xml` | `cfgignorelist.xml` | `cfgignorelist.xml` | `cfgignorelist.xml` |
| `cfgundergroundtriggers.json` | пустой | 8 триггеров | 30 | 1076 |
| `db/messages.xml` | есть | есть | **нет** | есть |
| только у карты | — | `mapgroupcluster05.xml` (пустой) | `build.xml`, `config.cpp`, `pra/warheadstorage.json` | `cfgbunkerbroadcast.json`, `cfgexternallocks.json` |

Имена различаются регистром — на Linux важно. `db/globals.xml` и `db/economy.xml` **побайтно одинаковы** у всех 4 карт.

## cfgeconomycore.xml — что добавилось к 1.30

Во всех 4 миссиях root-классы: `DefaultWeapon`, `DefaultMagazine`, `Inventory_Base`, `HouseNoDestruct`,
`SurvivorBase`/`DZ_LightAI` (`act="character"`), `CarScript`, `BoatScript`, **`MotorbikeScript`** (`act="car"`),
**`HouseDestructible`**. Если сервер обновлялся со старым `cfgeconomycore.xml` без `MotorbikeScript` —
мотоциклы, скорее всего, не будут спавниться **[вывод]**. Defaults: `dyn_radius 30`, `dyn_smin 0`, `dyn_smax 0`,
`dyn_dmin 1`, `dyn_dmax 5` (значения по умолчанию для `<zone>` **[вывод]**), `log_ce_*` (+ `log_ce_animal` у Livonia/Nasdara),
`log_storageinfo`, `log_hivewarning`, `log_missionfilewarning`.

## cfggameplay.json

Читается только при `enableCfgGameplayFile = 1;` в serverDZ.cfg. Ключ `version` — версия формата; у 3 карт
в 1.30 лежит 123 и работает **[вывод]**. Значения ниже — ванилла Chernarus (отличия карт — в конце).

| Секция | Ключи (ванильное значение) |
|---|---|
| `GeneralData` | `disableBaseDamage` false, `disableContainerDamage` false, `disableRespawnDialog` false, `disableRespawnInUnconsciousness` false |
| `PlayerData` | `disablePersonalLight` false (Nasdara: **true**) |
| `PlayerData.StaminaData` | `sprintStaminaModifierErc` 1.0, `sprintStaminaModifierCro` 1.0, `staminaWeightLimitThreshold` 6000.0 (г), `staminaMax` 100.0, `staminaKgToStaminaPercentPenalty` 1.75, `staminaMinCap` 5.0, `sprintSwimmingStaminaModifier`, `sprintLadderStaminaModifier`, `meleeStaminaModifier`, `obstacleTraversalStaminaModifier`, `holdBreathStaminaModifier` (все 1.0) |
| `PlayerData.ShockHandlingData` | `shockRefillSpeedConscious` 5.0, `shockRefillSpeedUnconscious` 1.0, `allowRefillSpeedModifier` true |
| `PlayerData.MovementData` | `timeToStrafeJog` 0.1, `rotationSpeedJog` 0.15, `timeToSprint` 0.45, `timeToStrafeSprint` 0.3, `rotationSpeedSprint` 0.15, `allowStaminaAffectInertia` true |
| `PlayerData.DrowningData` | `staminaDepletionSpeed`, `healthDepletionSpeed`, `shockDepletionSpeed` (10.0) |
| `PlayerData.WeaponObstructionData` | `staticMode` 1, `dynamicMode` 1 (0 = выкл. **[не сверено]**) |
| `WorldsData` | `lightingConfig` (0/2/3 по картам), `objectSpawnersArr` [] (список JSON-файлов со статикой), `environmentMinTemps`/`environmentMaxTemps` (12 чисел — °C по месяцам янв…дек), `wetnessWeightModifiers` [1.0, 1.0, 1.33, 1.66, 2.0] (множитель веса по степени намокания **[вывод]**) |
| `WorldsData` (не везде) | `playerRestrictedAreaFiles` (Sakhal: `["pra/warheadstorage.json"]`), `bunkerBroadcastEnabled` (Nasdara: true) |
| `BaseBuildingData.HologramData` | `disableIsCollidingBBoxCheck`, `disableIsCollidingPlayerCheck`, `disableIsClippingRoofCheck`, `disableIsBaseViableCheck`, `disableIsCollidingGPlotCheck`, `disableIsCollidingAngleCheck`, `disableIsPlacementPermittedCheck`, `disableHeightPlacementCheck`, `disableIsUnderwaterCheck`, `disableIsInTerrainCheck` (все false); холод — см. ниже; `disallowedTypesInUnderground` ["FenceKit","TerritoryFlagKit","WatchtowerKit"] |
| `BaseBuildingData.ConstructionData` | `disablePerformRoofCheck`, `disableIsCollidingCheck`, `disableDistanceCheck`, `disableItemFalling`, `disableDropAttachmentsOnFall`, `disableRefundMaterialsOnFall` (все false) |
| `UIData` | `use3DMap` false |
| `UIData.HitIndicationData` | `hitDirectionOverrideEnabled` false, `hitDirectionBehaviour` 1, `hitDirectionStyle` 0, `hitDirectionIndicatorColorStr` "0xffbb0a1e" (ARGB), `hitDirectionMaxDuration` 2.0, `hitDirectionBreakPointRelative` 0.2, `hitDirectionScatter` 10.0, `hitIndicationPostProcessEnabled` true |
| `MapData` | `ignoreMapOwnership` false (карта без предмета-карты), `ignoreNavItemsOwnership` false (без компаса/GPS), `displayPlayerPosition` false, `displayNavInfo` true |
| `VehicleData` | `boatDecayMultiplier` 1, `canDetachAttachedCarWheels`, `canDamageAttachedCarWheels`, `canDetachAttachedBikeWheels`, `canDamageAttachedBikeWheels` (true) |
| `ExternalLockData` (только v130) | `protectionCountStageOne` 3, `protectionCountStageTwo` 1, `protectionTime` 30, `protectionResetTime` 3600 |
| `SandstormData` (только v130) | `sandstormFrequency` 1.0 |

**Отличия карт** (сверено diff по всем ключам):

| | Chernarus | Livonia | Sakhal | Nasdara |
|---|---|---|---|---|
| `lightingConfig` | 0 | 0 | 2 | 3 |
| холод в HologramData | `disableColdAreaBuildingCheck: true` | то же | `disableColdAreaPlacementCheck: false` | `disableColdAreaPlacementCheck: true` |
| мин/макс °C (янв / июль) | −3…3 / 18…26 | −7…−2.5 / 20.4…25 | −6.5…−3 / 9…16 | 3.4…17.4 / 14.4…38.4 |
| прочее | — | — | `playerRestrictedAreaFiles` | `disablePersonalLight: true`, `bunkerBroadcastEnabled`, `ExternalLockData`, `SandstormData` |

* `disableColdAreaBuildingCheck` (Chernarus/Livonia) и `disableColdAreaPlacementCheck` (Sakhal/Nasdara) — разные имена
  одного по смыслу ключа; актуальное, вероятно, `…PlacementCheck` (в двух новейших файлах) **[вывод]**.
  На Sakhal `false` = проверка включена, в холодных зонах ставить/строить нельзя **[вывод]**.
* Не переносите `lightingConfig`, температуры и `playerRestrictedAreaFiles` между картами — это настройки конкретного мира.
* Формат файлов `objectSpawnersArr`: `{"Objects":[{"name":"Класс","pos":[x,y,z],"ypr":[0,0,0],"scale":1,…}]}` **[не сверено]**;
  в ванилле массив пуст у всех карт.

## Player Restricted Area (Sakhal, `pra/warheadstorage.json`)

```json
{ "areaName": "RestrictedAreaWarheadStorage",
  "PRABoxes": [ [ [27, 5.2, 11], [108, 0, 0], [2570, 15.22, 5963.8] ] ],
  "safePositions3D": [ [2575.12, 15.25, 5954.31], … ] }
```

Бокс = `[размер x,y,z]`, `[поворот]`, `[центр x,y,z]` **[вывод]**; `safePositions3D` — куда переносить игрока,
оказавшегося в зоне (при входе на сервер) **[вывод]**. Подключается через `WorldsData.playerRestrictedAreaFiles`.

## cfgEffectArea.json (зоны эффектов)

```json
{ "Areas": [ { "AreaName": "Ship-Bow", "Type": "ContaminatedArea_Static", "TriggerType": "ContaminatedTrigger",
    "Data": { "Pos": [13917, 0, 11178], "Radius": 75, "PosHeight": 20, "NegHeight": 3,
              "InnerPartDist": 80, "OuterOffset": 30, "ParticleName": "graphics/particles/contaminated_area_gas_bigass" },
    "PlayerData": { "AroundPartName": "…gas_around", "TinyPartName": "…gas_around_tiny",
                    "PPERequesterType": "PPERequester_ContaminatedAreaTint" } } ],
  "SafePositions": [ [434, 13624], … ] }
```

* `Pos` — x, y, z (y = 0 → по земле **[вывод]**), `Radius`, `PosHeight`/`NegHeight` — высота цилиндра вверх/вниз.
* `SafePositions` — `[x, z]`, куда переносит игрока, зашедшего на сервер внутри зоны **[не сверено]**.
* Динамический газ — это **не** этот файл, а событие `StaticContaminatedArea` (child `ContaminatedArea_Dynamic`,
  `limit=parent`) + точки в cfgeventspawns: есть на Chernarus (82 точки) и Livonia (37), нет на Sakhal и Nasdara.

| Карта | Зоны (Type → TriggerType) | SafePositions |
|---|---|---|
| Chernarus | 9 × `ContaminatedArea_Static` (корабль, Павлово) | 55 |
| Livonia | 8 × `ContaminatedArea_Static` (Radunin, аэродром Lukow) | 27 |
| Sakhal | 5 `GeyserArea`→`GeyserTrigger` (+`EffectInterval` 7200, `EffectDuration` 180), 41 `HotSpringArea`→`HotSpringTrigger`, 4 `VolcanicArea`→`VolcanicTrigger`; без `PlayerData`, без `SafePositions` | — |
| Nasdara | 6 `ContaminatedArea_Static` (`Tunnel1…6`), 15 `OilPitArea`→`OilPitTrigger` (радиус 2 м) | 0 |
| сезонные halloween* | + `SpookyArea23`→`SpookyTrigger23` (`InnerRingCount`, `OuterRingToggle`, `OuterPartDist`, `VerticalLayers`, `VerticalOffset`, частицы `spooky_mist`) | |

## cfgundergroundtriggers.json (подземелья: темнота и звук)

```json
{ "Triggers": [ { "Position": [735.0, 533.7, 1229.1], "Orientation": [0,0,0], "Size": [15, 5.6, 10.8],
    "EyeAccommodation": 0, "InterpolationSpeed": 1, "AmbientSoundSet": "Underground_SoundSet",
    "Breadcrumbs": [ { "Position": [741.29, 531.52, 1227.55], "EyeAccommodation": 1, "UseRaycast": 0, "Radius": -1 }, … ] } ] }
```

* Триггер — повёрнутый бокс (`Position` центр, `Size`). `EyeAccommodation` 1 = как снаружи, 0 = полная темнота
  (у входа крошки 1 → 0.7 → 0.4 → 0.2 → 0 вглубь) **[вывод]**. `Breadcrumbs` — точки плавного перехода внутри триггера.
* Новые поля (Sakhal/Nasdara): `AmbientSoundType` (`caveBig`, `caveSmall`), `UseLinePointFade`, `Comment`,
  `LightLerp` у крошки, `CustomSpawn: true` + `ParentNetworkId` (триггер привязан к объекту — бункер Warhead Storage),
  `ExternalValueController: {"Type": "DoorState", "Params": ["maindoor2_outer"]}` — темнота зависит от состояния двери.
* Звуки Nasdara: `ambient_Bunker_loop_SoundSet`, `ambient_Irrigation_Tunnel_loop_SoundSet`, `ambient_Traffic_tunnels_loop_SoundSet` и др.
* Связь со строительством: `disallowedTypesInUnderground` в cfggameplay запрещает эти киты внутри подземных триггеров **[вывод]**.

## cfgplayerspawnpoints.xml

Три секции одинакового формата: `<fresh>` — новые персонажи, `<hop>` — «server hoppers» (сменили сервер),
`<travel>` — «travellers» (формулировки из комментариев Nasdara). В каждой:

| Блок | Параметры (fresh Chernarus) | Смысл (из официальных комментариев в Nasdara/Sakhal) |
|---|---|---|
| `spawn_params` | `min/max_dist_infected` 30/70 (вес 2×), `min/max_dist_player` 65/150 (вес 3×), `min/max_dist_static` 0/2 (вес 1×); Sakhal/Nasdara ещё `min/max_dist_trigger` 50/100 (вес 6×) | Оценка точки в рантайме: ближе min — штраф (−1), между min и max — лучше всего, дальше max — 0 |
| `generator_params` | `grid_density` 4, `grid_width`/`grid_height` 200 (1–4096 м), `min/max_dist_static` 0/2, `min/max_steepness` −45/45; Nasdara: `allow_in_water` false | Вокруг каждой `<pos>` строится прямоугольник и сетка кандидатов (density 0 = только центр). Точки в объектах/воде отбрасываются |
| `group_params` | `enablegroups` true, `groups_as_regular` true, `lifetime` 120 (с, −1 выкл.), `counter` 2 (входов, −1 выкл.) | Активна одна группа; меняется по истечении lifetime или counter. Проверка только при логине игрока |
| `generator_posbubbles` | `<group name="WestCherno"><pos x z/>…</group>`; у группы можно задать `lifetime=""`/`counter=""` | Центры сеток |

| Карта | fresh: групп / точек | hop и travel | Особенности |
|---|---|---|---|
| Chernarus | 11 / 49, группы вкл. (lifetime 120, counter 2) | 10 групп / 50, группы выкл., player 25–70 м, сетка 150 | в группе `WestCherno` есть точка x=13552 z=5955 (у Солнечного) |
| Livonia | 12 / 63 | 6 / 44 | как Chernarus |
| Sakhal | 1 группа `Zones` / 39, группы выкл. (lifetime 360), density 6 | 1 группа / 39 (часть точек другие), все `*_dist_*` = 0, lifetime −1 | |
| Nasdara | 1 группа `AllSpawnpoints lifetime="0"` / 20 (север карты) | идентичны fresh | подробные комментарии ко всем параметрам — образец |

## cfgenvironment.xml + env/*_territories.xml

```xml
<env><territories>
  <file path="env/wolf_territories.xml" />                          <!-- загрузить файл зон -->
  <territory type="Herd" name="Wolf" behavior="DZWolfGroupBeh">     <!-- стадо -->
    <file usable="wolf_territories" />                              <!-- имя файла без .xml -->
  </territory>
  <territory type="Ambient" name="AmbientHen" behavior="DZAmbientLifeGroupBeh">
    <file usable="hen_territories" />
    <agent type="Female" chance="3"><spawn configName="Animal_GallusGallusDomesticusF_White" chance="20" /></agent>
    <item name="globalCountMax" val="50" />  <!-- также zoneCountMin/Max, playerSpawnRadiusNear/Far, zoneTouchDisableEditPeriodSec -->
  </territory>
</territories></env>
```

Файл территорий: `<territory-type><territory color="…"><zone name="Rest" smin dmin smax dmax x z r/>…`.
Пустой файл = `<territory-type/>` (Nasdara: `cattle_`, `sheep_goat_territories.xml`).

**Связь с events.xml** (во всех картах соблюдается) **[вывод]**:
* `Herd` с `name="Wolf"` ↔ событие `AnimalWolf` (`Animal` + name); `Ambient` `AmbientHen` ↔ событие `AmbientHen`.
  Точек в cfgeventspawns им не нужно (там лишь пустые `<event name="AnimalWolf" />`), места — из территорий.
* Заражённые: `zombie_territories.xml`, **имя зоны = имя события** (`InfectedVillage`, `InfectedArmy`…),
  `dmin`/`dmax` — сколько заражённых держать в зоне, `r` — радиус; события `Infected*` с `position=player`.
  `territory ZombieTest` в cfgenvironment — заглушка (`herdsCount 0`).
* Зоны животных: `Graze`/`Rest`/`Water` (травоядные), `HuntingGround`/`Rest`/`Water` (волки), `Zone_fox`/`Zone_Hare`/`Zone_hen`.
* **Баг ванилы Nasdara**: 31 зона `InfedctedReligious` (опечатка) — событие `InfectedReligious` (active=1) зон не имеет,
  религиозные заражённые на Nasdara, вероятно, не появляются. Исправление — переименовать зоны.
* Мелочи: Chernarus подключает `hare_territories.xml` дважды и не подключает `domestic_animals_territories.xml`;
  в `env/` Nasdara лежат неиспользуемые `wolf_`, `bear_`, `pig_`, `red_deer_`, `roe_deer_`, `wildboar_`.

## Карта лута: mapgroup*/mapcluster*

| Файл | Корень | Формат | Назначение |
|---|---|---|---|
| `mapgroupproto.xml` | `<prototype>` | `<defaults>` (`group lootmax 6`, `container lootmax 4`, `keepInvalidPoints`, `clusterMatrix de="TrajectoryX" width height`); `<group name="Land_Shed_M1" lootmax="2">` → `<usage>`/`<value>`, `<container name="lootFloor" lootmax><category/><tag/><point pos="x y z" range height flags/></container>`, `<dispatch dechance><proxy type="HatchbackWheel" pos rpy/></dispatch>` | точки лута **внутри модели** здания (локальные координаты); `dispatch/proxy` — детали в остовах машин |
| `mapgrouppos.xml` | `<map>` | `<group name="Land_…" pos="x y z" rpy="…" a="угол"/>` | все здания с лутом на карте (Chernarus 11 679, Livonia 5 753, Sakhal 8 332, Nasdara 13 717) |
| `mapgroupcluster*.xml` | `<map>` | `<group name="PearTree3" pos a/>`, по 50 000 на файл | деревья/кусты/камни для событий `Trajectory*` (сбор фруктов, грибов, камней) |
| `mapclusterproto.xml` | `<prototype><clusters>` | `<export name shape="dz\…\x.p3d"/>`; `<cluster name="CaninaBush1" lootmax maxinstances><de name="TrajectoryCanina"/><container><point/></container></cluster>` | что и где спавнится на объектах кластеров |
| `mapgroupdirt.xml` | `<map>` | пустой во всех картах | — |

Эти файлы **генерируются** из моделей и карты (руками правят только `lootmax`/категории в proto). Модовые здания
без записи в `mapgroupproto.xml` лута не дают. В proto можно указать `usage`/`value`, которые для этого здания
перекрывают раскраску areaflags **[вывод]**.

## cfgeventgroups.xml, `<secondary>`, `<zone>`

```xml
<eventgroupdef>
  <group name="Train_Abandoned_Cherno">
    <child type="StaticObj_Wreck_Train_742_Red_DE" deloot="0" lootmax="3" lootmin="1" x="0" z="0" a="78.123" y="1.9"/>
  </group>
  <group name="Scientist">  <!-- Sakhal -->
    <child type="StaticObj_FrozenScientist_DE" spawnsecondary="false" x="0.0" z="0.0" a="0"/>
  </group>
</eventgroupdef>
```

* `x/z/a/y` у child — смещение от `<pos … group="Имя">` в cfgeventspawns. Атрибуты: `type`, `deloot`, `lootmin`, `lootmax`,
  `spawnsecondary` (Nasdara/Sakhal, всегда `false`). Событие при этом с пустыми `<children/>`.
* Группы: Chernarus 83 (`Train_*`, `Traffic_*`, конвои, полиция), Livonia 61, Sakhal 1 (`Scientist`, 27 точек), Nasdara 26 (`Abad`, `Tunnel`, `Palace`…).
* `<secondary>InfectedArmy</secondary>` в events.xml — какое событие заражённых спавнить вокруг (HeliCrash→InfectedArmy,
  PoliceCar→InfectedPoliceHard, Train→InfectedIndustrial, SantaCrash→InfectedSanta, MilitaryConvoy→InfectedArmyDesert/Convoy).
  Количество/радиус — `<zone smin smax dmin dmax r/>` у события в cfgeventspawns **[вывод]**.
  На Nasdara `<secondary>` есть даже у `VehicleOffroad02`, `VehicleTruck01`, `AnimalGoat`, `ItemBricks`, но `<zone>` у них нет.
* `position`: `fixed` (452 в репо), `player` (350), `uniform` (13 — только `StaticChristmasTree`).
  `limit`: `child`, `custom` (заражённые), `mixed` (машины, предметы), `parent` (`StaticContaminatedArea`, `AmbientTest`).

## cfgignorelist.xml

`<ignore><type name="Bandage"></type>…</ignore>` — типы, которые CE не учитывает/удаляет при загрузке **[вывод]**.
Одинаков у Chernarus/Livonia/Sakhal (24 типа: `Bandage`, маски Payday, `TransitBus`, `Wreck_Mi8`, `Spear`, `EasterEgg`,
`Mag_STANAGCoupled_30Rnd`, ракетница и сигнальные ракеты…). Nasdara — без `Flaregun`/`Ammo_Flare*` (19).

## cfgweather.xml

`<weather reset="0" enable="0">` у всех карт — **файл выключен**, погода из мира. `reset` = не грузить погоду из storage.
Секции `overcast`, `fog`, `rain`, `windMagnitude`, `windDirection`, `snowfall`: `<current actual time duration/>`,
`<limits min max/>`, `<timelimits min max/>` (сек), `<changelimits min max/>`; у `rain`/`snowfall` ещё
`<thresholds min max end/>` (при какой облачности возможны осадки). `<storm density threshold timeout/>` — молнии.

| | Chernarus | Livonia | Sakhal | Nasdara |
|---|---|---|---|---|
| fog limits | 0.02–0.08 | 0.02–0.13 | 0–0 | = Livonia |
| rain | 0–1, threshold 0.6 | то же | **всегда 0** | = Livonia |
| snowfall | всегда 0 | всегда 0 | 0–1, threshold 0.3 | 0 |
| storm threshold/timeout | 0.9 / 45 | 0.7 / 20 | 0.98 / 45 | 0.7 / 20 |

Nasdara побайтно = Livonia (копия), песчаная буря задаётся `SandstormData` в cfggameplay. Чтобы файл работал — `enable="1"`.

## db/messages.xml

Во всех ваниллах только закомментированные примеры (у Sakhal файла нет). Теги `<message>`:
`<deadline>` (мин. до выключения, обратный отсчёт), `<shutdown>1` (выключить по deadline), `<repeat>` (каждые N мин.),
`<delay>` (через N мин.), `<onconnect>1` (при подключении игрока), `<text>` с `#name` (имя сервера) и `#tmin` (минут осталось).

```xml
<message><deadline>600</deadline><shutdown>1</shutdown><text>#name will shutdown in #tmin minutes.</text></message>
<message><delay>2</delay><onconnect>1</onconnect><text>Welcome to my server #name</text></message>
```

## init.c (ванилла 1.30)

`main()`: `CreateHive()` → `ce.InitOffline()`, затем сброс даты: если текущая дата не в окне
[reset_day месяца reset_month … reset_day следующего месяца] — ставится reset-дата (время суток сохраняется).
`CustomMission : MissionServer`: `SetRandomHealth` (0.45–0.65), `CreateCharacter`, `StartingEquipSetup`, `CreateCustomMission()`.

| Карта | Дата сброса | Стартовые вещи (поверх одежды из выбора персонажа) |
|---|---|---|
| Chernarus | 20 сентября | `BandageDressing` (слот 2), случайный `Chemlight_*` (слот 1), `Apple`/`Pear`/`Plum` (слот 3) |
| Livonia | 17 июля | бинт + химсвет, без фрукта |
| Sakhal | 1 февраля | бинт, химсвет, `SteakKnife` (0.15–0.35), здоровье одежды 0.25–0.65; вода 750, энергия 1000, иммунитет к гриппу 900 с |
| Nasdara | 30 апреля | `RemoveAllItems()`, затем случайные `KameezShirt_*`, `*ShalwarPants_*`, `*Sandal*Shoes_*`, химсвет, `SodaCan_*`, `Figs`, бинт; вода 1000, энергия 800 |

Сезонные init.c = базовые, кроме: Payday/valentines Livonia — 10 августа; Walpurgis Sakhal — 15 февраля;
halloween Chernarus/Livonia — `OnClientReadyEvent` + `ActivateModifier(eModifiers.MDF_FLIES)` (мухи над игроком).

## Только Nasdara: cfgbunkerbroadcast.json, cfgexternallocks.json

```json
{ "bunkerSettings":   { "numberOfActive": 3, "lockCodeLength": 4, "lockCodeMode": 0 },
  "schedulerSettings":{ "batchLifetimeLength": 720, "reportInterval": 10,
                        "periods": [ { "startTime": "1745", "endTime": "0600" } ] },
  "playbackSettings": { "dotDuration": 0.5, "dashDuration": 1.5, "symbolGapDuration": 0.4, "wordGapDuration": 2.2,
                        "pauseBetweenBunkers": 6.0, "messageRepetitions": 1, "bunkerRepetitions": 0 },
  "proxies": [ { "position": [7216.415, 185.244, 5706.955] }, … ] }
```

Радиотрансляция азбукой Морзе кодов замков бункеров **[вывод]**: 23 `proxies` совпадают с позициями
`Land_Bunker_Shelter_*`/`Land_Bunker_Basement_*` из mapgrouppos; активны 3 бункера, код из 4 символов,
вещание с 17:45 до 06:00 (игровое время **[вывод]**). В types есть `MorsecodeLeaflet_*`, `PersonalRadio`, `BaseRadio`.
Включается `WorldsData.bunkerBroadcastEnabled`.

`cfgexternallocks.json`: `{"locksSettings": {"protectionCountStageOne": 3, "protectionCountStageTwo": 1,
"protectionTime": 30, "protectionResetTime": 3600}}` — те же 4 значения, что `ExternalLockData` в cfggameplay
(защита внешних замков от перебора **[вывод]**; какой файл главнее — не выяснено).

## Только Sakhal: build.xml, config.cpp, pra/

* `build.xml` — Ant-проект внутренней сборки BI (`worlds_sakhal_ce.pbo`), `config.cpp` — `CfgPatches DZ_Worlds_Sakhal_CE`.
  Служебные файлы упаковки, серверу не нужны **[вывод]**; лишними в миссии не мешают.
* `pra/warheadstorage.json` — см. «Player Restricted Area».

## Сезонные миссии

| Папка | Файлы |
|---|---|
| `ChristmasOffline.ChernarusPlus` / `.Enoch` | `cfgrandompresets.xml`, `db/events.xml`, `db/types.xml`, `init.c` |
| `ChristmasOffline.sakhal` | то же + `cfgeventspawns.xml`, `mapgroupproto.xml` |
| `PaydayOffline.*`, `valentinesOffline.*` | `db/types.xml`, `init.c` |
| `WalpurgisNightOffline.ChernarusPlus` / `.Enoch` | `cfgspawnabletypes.xml`, `db/events.xml`, `db/types.xml`, `init.c`, `mapgroupproto.xml` |
| `WalpurgisNightOffline.Sakhal` | то же + `cfgeventspawns.xml` |
| `halloweenOffline.chernarusplus` / `.enoch` | `cfgeffectarea.json` (Spooky-зоны), `cfgspawnabletypes.xml`, `db/events.xml`, `db/types.xml`, `env/zombie_territories.xml`, `init.c` |
| `halloweenOffline.sakhal` | `areaflags.map` (= базовому), `cfgspawnabletypes.xml`, `db/events.xml`, `db/types.xml`, `env/zombie_territories.xml`, `init.c` |
| `halloween.chernarusplus` | **устаревший** пакет: свой `areaflags.map` старого формата (16 бит usage, 50 МБ), `cfgLimitsDefinition.xml`, `cfgRandomPresets.xml`, `db/economy.xml`, `db/globals.xml`, `env/wolf_`, `zombie_territories.xml` (зоны `InfectedPumpkin`, `InfectedWitch`) |

Это **оверлей**: папка содержит только изменённые файлы; остальное берётся из `dayzOffline.<карта>`.
Что меняют: включают события (`StaticChristmasTree`, `StaticSantaCrash`, `InfectedSanta`, `StaticBonfire`, `InfectedBonfire`,
`InfectedSpooky`), поднимают nominal сезонных предметов (Christmas Chernarus — 39 типов: `GiftBox_*`, `SantasHat`, `Candycane_*`,
`XmasBaseballBat`…; Halloween — `WitchHat`, `Cauldron`, `Broom_Birch`; Valentines — `Ammo_CupidsBolt`; Payday — `PaydayMask_*`).

**Важно: сезонные файлы — старые снимки (до 1.29/1.30).** В их types.xml 1 786–1 955 типов против ~2 390 в базовых,
нет мотоциклов (`Motorbike_*`), собак, `MotorbikeScript`-контента и др. (~440–640 типов); в events.xml нет `VehicleMotorbike`;
в сезонных `cfgeventspawns.xml` Sakhal нет точек `VehicleMotorbike` (у Walpurgis ещё и `StaticAmbulance`, `StaticBoat*`, `StaticHeliCrash`).
Поэтому **не копируйте сезонные файлы поверх миссии 1.30 целиком** — точечно перенесите: `active=1` нужных событий
и nominal/min сезонных предметов (или их `<type>` через `<ce folder>`, убрав дубли из основного types.xml).
`halloween.chernarusplus` с его `areaflags.map` на 1.30 не использовать.

Порядок, если всё же разворачивать целиком: скопировать `dayzOffline.<карта>` в новую папку → поверх положить файлы
сезонной → `template` в serverDZ.cfg → `check` → сравнить types/events с базой (потерянные типы вернуть).

## CETool и areaflags.map

`CETool/<Карта>/` — **проект** для DayZ CE Tool (сама программа — в DayZ Tools в Steam, в репо её нет):

| Файл | Что это |
|---|---|
| `<карта>.xml` (`<zg-config>`) | проект: `<world size>` (Chernarus 15360, Livonia 12800, Sakhal 15360, **Nasdara 16384**), `<layer size="4096"/>`, список `usages`/`values`, слои `<layer usage_flags value_flags color name/>`, `<territory-type-list>` — все зоны животных/заражённых (источник `env/*_territories.xml`) |
| `map.png` | подложка (2048² RGB; Livonia 4096² RGBA) |
| `layers/*.tga` | маски 4096×4096 (8 бит, RLE): `usgFlg_Paint-<Usage>`, `usgFlg_Def-<Usage>`, `valueFlg_Tier1…4/Unique`, вода (`water-fresh`, `water-sea`), у Livonia `spawning-*`, у Sakhal `tex_sakhal_ice_*`, `tex_sakhal_snow` |

* Бит usage = `1 << индекс` в списке `usageflags` из `cfglimitsdefinition.xml` (Military 1, Police 2, Medic 4, Firefighter 8,
  Industrial 16, Farm 32, Coast 64, Town 128, Village 256, Hunting 512, Office 1024, School 2048, Prison 4096, далее по карте;
  Nasdara: MilitaryEast 131072, MilitaryWest 262144). Value: Tier1 1, Tier2 2, Tier3 4, Tier4 8, Unique 16.
  Значит **порядок usage/value в cfglimitsdefinition.xml нельзя менять** — только дописывать в конец **[вывод, совпадает на 4 картах]**.
* `areaflags.map`: заголовок 24 байта (`4096, 4096, world, world, 32, 0` как uint32), далее растр 4096×4096:
  4 байта usage + value-биты (Livonia без Tier4 → 4.5 байта/ячейку, 75.5 МБ; остальные 5 байт, 83.9 МБ) **[вывод]**.
  Ячейка ≈ 3.75 м на Chernarus. Правится только CE Tool: открыть проект → рисовать слои → экспорт `areaflags.map`
  (и territories) → положить в миссию → рестарт. Руками/скриптом не редактировать.

## Проверка официальных миссий скриптом `check` (16.10.2026)

| Миссия | ERROR | WARN | Что за WARN |
|---|---|---|---|
| chernarusplus | 0 | 58 | 48 дублей точек `ItemPlanks`, 8 — `StaticAirplaneCrate`, дубль `HuntingVest` в spawnabletypes, точки `VehicleTransitBus` без события |
| enoch | 0 | 6 | child `Offroad_02` min 3 > max 2, дубли `R12`/`PM73Rak`/`ZmbM_usSoldier_Heavy_Woodland` в spawnabletypes, `VehicleTransitBus`, дубль точки `StaticSantaCrash` |
| sakhal | 0 | 2 | дубли `ZmbM_Mummy`, `ScientificBriefcase` в spawnabletypes |
| nasdara | 0 | 0 | — (баг `InfedctedReligious` скрипт не ловит: env/ не проверяется) |
| сезонные (14) | 0, кроме 2 | 0–2 | `halloweenOffline.enoch` и `WalpurgisNightOffline.Enoch`: **ERROR** — `cfgspawnabletypes.xml` стр. 1268/1295, комментарий `<!-- ----MUMMY---- -->` содержит `--` (запрещено в XML); 20 WARN «машина не описана в spawnabletypes» — следствие той же ошибки |

* Все WARN выше — реальные мелкие огрехи ванилы (дубли, опечатки), не ложные срабатывания. Как к ошибке в комментарии
  относится парсер DayZ — не проверено; перед использованием замените на `<!-- MUMMY -->`.
* INFO «нет ни одной `<pos>` (событие с position=fixed не заспавнится)» для `Animal*`, `Ambient*`, `Infected*`, `Trajectory*`,
  `Loot` — **ложная тревога**: им точки не нужны (территории, `position=player`, кластеры). Для `Vehicle*`/`Static*` — реальная проблема.
* INFO «min > nominal» (172–462 шт.) у типов с nominal 0 — норма ванилы. INFO «nominal > max» у `VehicleMotorbike` всех карт — тоже ванилла.
* Сезонная папка проверяется сама по себе (без базовой) — отсутствие файлов не ошибка.
