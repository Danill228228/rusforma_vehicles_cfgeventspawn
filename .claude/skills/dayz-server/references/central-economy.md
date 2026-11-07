# Central Economy (CE) — справочник по файлам миссии

Источник истины: официальный репозиторий Bohemia
`github.com/BohemiaInteractive/DayZ-Central-Economy` (папки `dayzOffline.chernarusplus`,
`dayzOffline.enoch`, `dayzOffline.sakhal`, `dayzOffline.nasdara` + сезонные миссии).
Сверено с его состоянием на октябрь 2026 (обновление 1.30, `cfggameplay.json` version 130 у Nasdara, 123 у остальных).
Если нужен «как в ванилле» — клонируй его (`git clone --depth 1 …`) и смотри там.

## Дерево миссии

```
mpmissions/dayzOffline.chernarusplus/
├── init.c                     # скрипт миссии: InitOffline() CE, дата, стартовый лут игрока
├── cfgeconomycore.xml         # root-классы CE, логирование, ПОДКЛЮЧЕНИЕ СВОИХ ПАПОК <ce folder>
├── cfgeventspawns.xml         # координаты событий (машины, вертолёты, статика)  <eventposdef>
├── cfgeventgroups.xml         # группы объектов для событий (поезда и т.п.)       <eventgroupdef>
├── cfgspawnabletypes.xml      # что спавнится ВНУТРИ/НА предмете (детали машин, лут в рюкзаках)
├── cfgrandompresets.xml       # именованные наборы для cargo/attachments
├── cfglimitsdefinition.xml    # допустимые category/usage/value/tag
├── cfglimitsdefinitionuser.xml# пользовательские комбинации usage/value
├── cfgplayerspawnpoints.xml   # точки спавна игроков (fresh / hop / travel)
├── cfgenvironment.xml         # подключение env/*_territories.xml (животные, зомби)
├── cfgignorelist.xml          # типы, которые CE игнорирует
├── cfgweather.xml             # погода (enable="0" по умолчанию = не используется)
├── cfgEffectArea.json         # заражённые зоны (газ)
├── cfgundergroundtriggers.json# подземелья (темнота/звук)
├── cfggameplay.json           # геймплей; читается только если enableCfgGameplayFile = 1 в serverDZ.cfg
├── areaflags.map              # бинарная карта usage/value (тиры) — редактируется CE Tool
├── mapgroupproto.xml          # точки лута внутри моделей зданий
├── mapgrouppos.xml            # позиции зданий на карте
├── mapgroupcluster*.xml       # кластеры (деревья/кусты и пр. для Trajectory-событий)
├── mapclusterproto.xml, mapgroupdirt.xml
├── env/                       # *_territories.xml — зоны животных и заражённых
├── db/
│   ├── types.xml              # ВСЕ спавнящиеся типы: количество, время жизни, где спавнить
│   ├── events.xml             # события: машины, животные, заражённые, статика
│   ├── globals.xml            # глобальные переменные CE
│   ├── economy.xml            # какие подсистемы инициализировать/сохранять
│   └── messages.xml           # сообщения сервера (рестарт и т.п.)
└── storage_1/                 # ПЕРСИСТЕНТНОСТЬ (создаётся сервером; 1 = instanceId)
```

Имена файлов на Linux-сервере регистрозависимы (`cfgEffectArea.json` в Chernarus, `cfgeffectarea.json` в Sakhal/Nasdara).

## Как связаны файлы (главное)

```
types.xml ──────── «этот класс существует для CE» + сколько/где/сколько живёт
   ▲
events.xml ─────── <event name="X"> … <child type="Класс"/>  (кого спавнит событие)
   ▲ name
cfgeventspawns.xml <event name="X"> <pos x z a/> …  (где, если position=fixed)
   ▼
cfgspawnabletypes.xml <type name="Класс"> детали/груз/повреждения при спавне
cfgeconomycore.xml  <ce folder> — откуда ещё брать types/events/spawnabletypes
```

## cfgeconomycore.xml

```xml
<economycore>
  <classes>
    <rootclass name="CarScript" act="car" reportMemoryLOD="no" />   <!-- машины -->
    <rootclass name="BoatScript" act="car" reportMemoryLOD="no" />  <!-- лодки -->
    ...
  </classes>
  <defaults>
    <default name="log_ce_vehicle" value="false"/>   <!-- true = лог спавна машин в RPT -->
    <default name="log_ce_lootspawn" value="false"/>
    <default name="save_events_startup" value="true"/>
    <default name="save_types_startup" value="true"/>
    ...
  </defaults>
  <!-- свои файлы: папка относительно корня миссии -->
  <ce folder="custom_rusforma">
    <file name="rf_types.xml" type="types" />
    <file name="rf_spawnabletypes.xml" type="spawnabletypes" />
    <file name="rf_events.xml" type="events" />
  </ce>
</economycore>
```

* Корень такого файла — тот же, что у оригинала (`<types>`, `<events>`, `<spawnabletypes>`).
* Типы для `<ce>`: `types`, `spawnabletypes`, `events`, а также `globals`, `economy`, `messages`, `randompresets` (последние — реже).
* **`cfgeventspawns.xml` так вынести нельзя** (известное ограничение, feedback.bistudio.com T161291):
  точки модовых машин дописывают прямо в основной `cfgeventspawns.xml`.
* Если моду нужен собственный root-класс (не наследуется от `CarScript`) — добавить `<rootclass … act="car">`.

## cfgeventspawns.xml (`<eventposdef>`)

```xml
<eventposdef>
  <event name="VehicleCivilianSedan">
    <pos x="12071.933594" z="9129.989258" a="317.953339" />
  </event>
  <event name="StaticHeliCrash">
    <zone smin="1" smax="3" dmin="3" dmax="5" r="45" />   <!-- заражённые вокруг события -->
    <pos x="558.859619" z="12918.953125" a="-1" />          <!-- a=-1: случайный поворот -->
  </event>
  <event name="StaticSantaCrash">
    <pos x="2593.47" z="5094.11" a="0" y="201.66"/>          <!-- y: высота (редко нужна) -->
  </event>
  <event name="VehicleTransitBus" />                           <!-- пустое = нет точек -->
</eventposdef>
```

* `x` — восток, `z` — север (метры от юго-западного угла), `y` — высота (обычно не указывают:
  объект ставится на поверхность), `a` — поворот в градусах (в ванилле встречаются и значения > 360,
  они просто «прокручиваются»).
* `group="Имя"` у `<pos>` — ссылка на группу из `cfgeventgroups.xml`.
* Имя события должно точно совпадать с `events.xml` (регистр важен). Точки без события в `events.xml` просто игнорируются.

## events.xml (`<events>`)

Ванильное событие машины (Chernarus):

```xml
<event name="VehicleCivilianSedan">
    <nominal>8</nominal>          <!-- сколько экземпляров держать на карте -->
    <min>5</min>
    <max>11</max>
    <lifetime>300</lifetime>      <!-- сек -->
    <restock>0</restock>          <!-- задержка перед респавном, сек -->
    <saferadius>500</saferadius>  <!-- не спавнить ближе к игрокам -->
    <distanceradius>500</distanceradius> <!-- мин. расстояние между экземплярами этого события -->
    <cleanupradius>200</cleanupradius>   <!-- не чистить, пока игрок ближе -->
    <flags deletable="0" init_random="0" remove_damaged="1"/> <!-- remove_damaged: убирать разбитые (ruined) -->
    <position>fixed</position>    <!-- fixed = точки из cfgeventspawns; player = вокруг игроков -->
    <limit>mixed</limit>          <!-- child | parent | mixed | custom -->
    <active>1</active>
    <children>
        <child lootmax="0" lootmin="0" max="5" min="3" type="CivilianSedan"/>
        <child lootmax="0" lootmin="0" max="5" min="3" type="CivilianSedan_Black"/>
        <child lootmax="0" lootmin="0" max="0" min="0" type="Boat_01_Camo"/> <!-- max=0: не спавнить -->
    </children>
</event>
```

* Префикс имени задаёт категорию: `Vehicle*`, `Static*`, `Item*`, `Infected*`, `Animal*`, `Ambient*`,
  `Trajectory*`, `Loot`. Все ванильные события его соблюдают — для машин держи `Vehicle…`.
* `Animal*`/`Ambient*` берут места из `env/*_territories.xml`, `Infected*` — `position=player`
  + `zombie_territories.xml`; им точки в `cfgeventspawns.xml` не нужны.
* Ванильные пропорции для машин: nominal 8 / min 5 / max 11 при 55–111 точках на событие.
  **Точек должно быть заметно больше nominal**, иначе машины «залипают» на одних местах.

## types.xml (`<types>`)

```xml
<type name="AKM">
    <nominal>3</nominal>      <!-- целевое количество на карте -->
    <lifetime>7200</lifetime> <!-- сколько живёт брошенный/лежащий предмет, сек -->
    <restock>3600</restock>   <!-- пауза перед респавном, сек -->
    <min>2</min>              <!-- порог, ниже которого CE начинает спавнить -->
    <quantmin>30</quantmin>   <!-- % заполненности (магазины, бутылки); -1 = не применяется -->
    <quantmax>80</quantmax>
    <cost>100</cost>          <!-- приоритет -->
    <flags count_in_cargo="0" count_in_hoarder="0" count_in_map="1" count_in_player="0" crafted="0" deloot="0"/>
    <category name="weapons"/>
    <usage name="Military"/> <!-- где: см. cfglimitsdefinition.xml -->
    <value name="Tier4"/>    <!-- тир зоны (areaflags.map) -->
    <!-- <tag name="shelves"/> -->
</type>
```

* `deloot="1"` — только в динамических событиях (вертолёты, конвои).
* `crafted="1"` — не спавнится, только крафт.
* Машины: `nominal 0`, `min 0` — их количество задаёт `events.xml`, не `types.xml`.
  Ванилла: `CivilianSedan` lifetime 3, restock 1800, cost 100, без category/usage/value.
  Сборки модов часто ставят lifetime 3888000 (45 дней) — обе схемы работают.
* Дубликат `<type name>` в разных файлах — частая причина «настройки не применяются». Ищи `grep -rn 'name="Класс"'`.

## cfgspawnabletypes.xml (`<spawnabletypes>`)

```xml
<type name="CivilianSedan">
    <attachments chance="1.00">               <!-- блок: шанс, что блок вообще сработает -->
        <item name="CivSedanWheel" chance="0.80" />   <!-- шанс конкретного предмета -->
    </attachments>
    <attachments chance="1.00"><item name="CarBattery" chance="0.60" /></attachments>
    <cargo preset="mixArmy" />                 <!-- набор из cfgrandompresets.xml -->
    <damage min="0.0" max="0.3" />             <!-- повреждение при спавне -->
</type>
<type name="Barrel_Blue"><hoarder /></type>    <!-- контейнер-схрон -->
```

Ванильные шансы деталей седана: колёса 0.80 (запаска 0.40), радиатор/АКБ/свеча 0.60,
фары 0.40, двери 0.30, капот/багажник 0.20. **Без записи машина появится без колёс и деталей.**

## cfgrandompresets.xml

```xml
<randompresets>
  <cargo chance="0.15" name="foodHermit">
    <item name="TunaCan" chance="0.11" />
  </cargo>
  <attachments chance="1.0" name="...">...</attachments>
</randompresets>
```

## cfglimitsdefinition.xml / cfglimitsdefinitionuser.xml

Списки допустимых `category` (tools, containers, clothes, lootdispatch, food, weapons, books, explosives),
`tag` (floor, shelves, ground), `usage` (Military, Police, Medic, Firefighter, Industrial, Farm, Coast,
Town, Village, Hunting, Office, School, Prison, Lunapark, SeasonalEvent, ContaminatedArea, Historical),
`value` (Tier1–Tier4, Unique). В `…user.xml` — комбинации, например `<user name="TownVillage">`.
Значение, которого нет в списке, CE не примет.

## db/globals.xml (выдержка из ваниллы)

| var | значение | смысл |
|---|---|---|
| AnimalMaxCount | 200 | лимит животных |
| ZombieMaxCount | 1000 | лимит заражённых |
| CleanupLifetimeDeadPlayer | 3600 | сек до удаления трупа игрока |
| CleanupLifetimeRuined | 330 | сек до удаления разрушенных объектов |
| CleanupLifetimeDefault | 45 | |
| InitialSpawn | 100 | % лута при первом старте |
| RestartSpawn | 0 | |
| SpawnInitial | 1200 | |
| RespawnAttempt / RespawnLimit / RespawnTypes | 2 / 20 / 12 | скорость респавна лута |
| LootDamageMin / LootDamageMax | 0.0 / 0.82 | повреждение лута |
| FlagRefreshFrequency / FlagRefreshMaxDuration | 432000 / 3456000 | флаги баз |
| TimeLogin / TimeLogout / TimeHopping / TimePenalty | 15 / 15 / 60 / 20 | |
| IdleModeCountdown / IdleModeStartup | 60 / 1 | |
| ZoneSpawnDist | 300 | |
| FoodDecay | 1 | |

`type="0"` — целое, `type="1"` — дробное.

## db/economy.xml

```xml
<economy>
    <dynamic init="1" load="1" respawn="1" save="1"/>
    <animals init="1" load="0" respawn="1" save="0"/>
    <zombies init="1" load="0" respawn="1" save="0"/>
    <vehicles init="1" load="1" respawn="1" save="1"/>  <!-- машины сохраняются между рестартами -->
    <randoms init="0" load="0" respawn="1" save="0"/>
    <custom init="0" load="0" respawn="0" save="0"/>
    <building init="1" load="1" respawn="0" save="1"/>
    <player init="1" load="1" respawn="1" save="1"/>
</economy>
```

## Прочее

* `cfgeventgroups.xml` — `<group name="Train_Abandoned_Cherno"><child type="…" x z a y deloot lootmin lootmax/></group>`;
  в `cfgeventspawns.xml` ссылка `<pos … group="Train_Abandoned_Cherno"/>`. Координаты child — смещения.
* `cfgplayerspawnpoints.xml` — секции `<fresh>`, `<hop>`, `<travel>`; `spawn_params`, `generator_params`,
  `group_params`, `generator_posbubbles` с `<group name="WestCherno"><pos x z/></group>`.
* `cfgenvironment.xml` — `<territories><file path="env/wolf_territories.xml"/>…` + описание видов.
* `cfgignorelist.xml` — `<ignore><type name="Bandage"></type>…`.
* `cfgweather.xml` — `<weather reset="0" enable="0">` (`enable="1"` чтобы файл работал).
* `db/messages.xml` — `<message><deadline>600</deadline><shutdown>1</shutdown><text>#name will shutdown in #tmin minutes.</text></message>`.
* `cfggameplay.json` — стамина, строительство, `WorldsData.objectSpawnersArr` (JSON-файлы со статикой),
  `playerRestrictedAreaFiles` (Sakhal: `pra/warheadstorage.json`). Нужен `enableCfgGameplayFile = 1;` в serverDZ.cfg.
* `areaflags.map` — правится только CE Tool (`CETool/` в официальном репо), не руками.
