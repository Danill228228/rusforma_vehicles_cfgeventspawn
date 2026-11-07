# Сервер DayZ: структура, запуск, моды, логи

## Папка сервера

```
DayZServer/
├── DayZServer_x64.exe        # Windows (Linux: DayZServer)
├── serverDZ.cfg              # основной конфиг
├── keys/                     # *.bikey — ключи модов (иначе кик при verifySignatures)
├── @CF/, @RUSForma_vehicles/ # моды (копии из steamapps/workshop/content/221100/<id>)
├── mpmissions/dayzOffline.chernarusplus/   # миссия (см. central-economy.md)
└── profiles/                 # логи и настройки модов (задаётся -profiles=)
```

## serverDZ.cfg — ключевые параметры

```cpp
hostname = "My Server";
password = "";
passwordAdmin = "";
maxPlayers = 60;
verifySignatures = 2;          // проверка подписей модов
forceSameBuild = 1;
disableVoN = 0;
disable3rdPerson = 0;
disableCrosshair = 0;
serverTime = "SystemTime";
serverTimeAcceleration = 1;
serverNightTimeAcceleration = 1;
serverTimePersistent = 0;
guaranteedUpdates = 1;
loginQueueConcurrentPlayers = 5;
loginQueueMaxPlayers = 500;
instanceId = 1;                // => mpmissions/<миссия>/storage_1/
storageAutoFix = 1;
enableCfgGameplayFile = 1;     // читать cfggameplay.json миссии

class Missions
{
    class DayZ
    {
        template = "dayzOffline.chernarusplus";   // папка в mpmissions/
    };
};
```

Список не полный — сверяйся с конфигом, который лежит у пользователя; не добавляй параметры «на всякий случай».

## Запуск

```bat
DayZServer_x64.exe -config=serverDZ.cfg -port=2302 -profiles=profiles ^
  "-mod=@CF;@RUSForma_vehicles" "-serverMod=@MyServerSideMod" -dologs -adminlog -netlog -freezecheck
```

* `-mod=` — моды, которые качают и клиенты; `-serverMod=` — только серверные.
* Порядок в `-mod` = порядок загрузки: зависимости (например `@CF`) раньше модов, которые их требуют.
  Зависимости конкретного мода — на его странице в Workshop.
* Каждый клиентский мод: скопировать его `keys/*.bikey` в `keys/` сервера.
* Linux: имена папок модов лучше в нижнем регистре и без пробелов (файловая система регистрозависима).

## Логи (`profiles/`)

| Файл | Что там |
|---|---|
| `DayZServer_x64_<дата>.RPT` | главный лог: загрузка модов, ошибки парсинга XML CE (с номером строки), сообщения CE |
| `script_<дата>.log` | ошибки скриптов (Enforce) модов и init.c |
| `DayZServer_x64.ADM` | админ-лог: подключения, убийства, чат (с `-adminlog`) |
| `crash_*.log`, `*.mdmp` | падения |

Подробные логи CE: `log_ce_*` в `cfgeconomycore.xml` (`log_ce_vehicle`, `log_ce_lootspawn`, `log_ce_statistics` …).
Ищи в RPT по имени файла/класса: `grep -n "cfgeventspawns\|events.xml\|types.xml" *.RPT`.

## init.c

* `CreateHive()` + `ce.InitOffline()` — запуск CE (не трогать).
* Блок даты: ванилла сбрасывает дату к 20 сентября, если вышла из окна.
* `class CustomMission: MissionServer` — `StartingEquipSetup` (стартовые вещи), `CreateCharacter`.
* `CreateCustomMission(string path)` в конце возвращает `new CustomMission()`.
* Моды (Expansion, трейдеры) часто требуют свои вставки в init.c — смотреть их документацию.

## Рестарты и вайпы

* Сообщения/авто-выключение: `db/messages.xml` (`<deadline>` минут, `<shutdown>1`) — сервер выключается,
  перезапуск делает внешний скрипт/хостинг.
* Вайп машин: остановить сервер → удалить `storage_1/data/vehicles.bin` (бэкап!).
* Полный вайп мира: удалить `storage_1/` целиком (игроки тоже сотрутся — `players.db`).
* После правки types.xml/events.xml вайп обычно не нужен: изменения применяются при старте.
