# rusforma_vehicles_cfgeventspawn

Точки спавна модовых машин **RUSForma_vehicles** для сервера **DayZ** (карта Chernarus).

* `rusforma_vehicles_cfgeventspawn` — файл без расширения, по содержимому это фрагмент `cfgeventspawns.xml`
  (`<eventposdef>`). На сервере его события вставляются в основной `mpmissions/<миссия>/cfgeventspawns.xml`.

## DayZ-задачи

* Субагент **`dayz-expert`** (`.claude/agents/dayz-expert.md`) — делегируй ему любую работу с файлами DayZ.
  У него постоянная память проекта: `.claude/agent-memory/dayz-expert/MEMORY.md`.
* Скилл **`/dayz-server`** (`.claude/skills/dayz-server/`) — справочники по Central Economy, транспорту,
  RUSForma, картам и настройке сервера + скрипт проверки/генерации XML.

Проверка файла после любой правки:

```bash
python3 -I .claude/skills/dayz-server/scripts/dayz_ce.py check rusforma_vehicles_cfgeventspawn --map chernarus
```

Известная проблема (на 2026-11-07): не закрыт `<event name="VehicleSpawnPoints">` — нужен `</event>` после строки 45.
