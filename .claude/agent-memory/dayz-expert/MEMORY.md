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
* Ванильные миссии 4 карт проходят `dayz_ce.py check` с 0 ERROR (проверено на официальном репо, окт. 2026).

## Открытые вопросы

* Есть ли у пользователя events.xml для `VehicleCrSk_*` и `VehicleSpawnPoints`, и какие там `child type`.
* Какая версия RUSForma_vehicles стоит и подключён ли RUSForma_vehicles_historical.
