# dayz-expert — память проекта

Обновлено: 2026-11-07. Подробности — в `.claude/skills/dayz-server/references/`.

## Проект

* Репо `danill228228/rusforma_vehicles_cfgeventspawn`. Пользователь пишет по-русски.
* Единственный рабочий файл: `rusforma_vehicles_cfgeventspawn` (без расширения) — фрагмент
  `cfgeventspawns.xml` (`<eventposdef>`) с точками модовых машин RUSForma для **Chernarus**.
  Разбор и таблица classname: `references/rusforma.md`.
* Серверных файлов пользователя (types/events/serverDZ.cfg) в репо нет — спрашивай или проси приложить.

## Состояние файла на 2026-11-07 (не исправлено — пользователь не просил)

* ERROR: не закрыт `<event name="VehicleSpawnPoints">` (стр. 3; нужен `</event>` после стр. 45).
* 42 события `VehicleCrSk_*` × 3 точки, все на тех же 21 точке (каждую делят 6–7 событий).
* 7 из 21 точки совпадают с ванильными точками Chernarus (седаны, StaticPoliceCar, StaticContaminatedArea).
* Имена с неверным classname: Kuban_G1→KubanG1, GAZ_21_Volga→GAZ21_Volga, Gaz_53_RF→Gaz_53RF,
  Moskvich_407→moskvich_407, Opel_Blitz→opel_blitz, M4_Tractor→m4_tractor,
  Artillery_Tractor→artillery_tractor; LUAZ_969 нет в списке 2024 г.

## Проверенные факты

* DayZ 1.30 (окт. 2026): новая карта Nasdara (`dayzOffline.nasdara`, DLC Badlands).
* `cfgeventspawns.xml` нельзя подключить через `<ce folder>`; types/events/spawnabletypes — можно.
* Ванильные миссии 4 карт проходят `dayz_ce.py check` с 0 ERROR (повторно 2026-11-07: WARN 58/6/2/0 —
  Chernarus/Livonia/Sakhal/Nasdara, все реальные мелкие огрехи ванилы).

## Изучено: официальный репо DayZ-Central-Economy (2026-11-07)

* Коммит `f220b29` (16.10.2026, 1.30), shallow-клон в scratchpad сессии (не в проекте). Разобраны все 4 миссии,
  14 сезонных папок, CETool. Итог — `references/mission-files.md` (форматы прочих файлов) и раздел
  «Различия ванильных миссий» в `references/maps.md`.
* Важное: root-класс `MotorbikeScript` нужен мотоциклам; сезонные папки — старые оверлеи (нет мотоциклов и ~450 типов
  1.29/1.30), целиком поверх 1.30 не копировать; порядок usage в cfglimitsdefinition = биты areaflags.map (не менять).
* Баги ванилы: Nasdara `InfedctedReligious` (31 зона) ≠ событие `InfectedReligious`; `halloweenOffline.enoch` и
  `WalpurgisNightOffline.Enoch` cfgspawnabletypes — `--` в комментарии (невалидный XML, check = ERROR).
* Вики BI (community.bistudio.com) из сессии не резолвится — смысл части ключей cfggameplay помечен [не сверено].
* Ложная тревога скрипта: INFO «нет ни одной <pos>» для Animal*/Ambient*/Infected*/Trajectory*/Loot.

## Открытые вопросы

* Есть ли у пользователя events.xml для `VehicleCrSk_*` и `VehicleSpawnPoints`, и какие там `child type`.
* Какая версия RUSForma_vehicles стоит и подключён ли RUSForma_vehicles_historical.
