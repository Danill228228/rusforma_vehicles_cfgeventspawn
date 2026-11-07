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
| Sakhal | `dayzOffline.sakhal` | ≈15360 (CE-координаты до ~15000) | DLC Frostline, есть `VehicleMilitaryBoat` |
| Nasdara | `dayzOffline.nasdara` | ≈16384 (267 км², CE-координаты до ~15745) | DLC Badlands, вышло с 1.30 (окт. 2026), пустынная карта |

Сезонные миссии в официальном репо: `ChristmasOffline.*`, `halloweenOffline.*`, `valentinesOffline.*`,
`WalpurgisNightOffline.*`, `PaydayOffline.*`.

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
