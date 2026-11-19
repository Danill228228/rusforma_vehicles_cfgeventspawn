# @RF_Humvee — отдельный мод DayZ

Бронированный HMMWV с люком стрелка на крыше.

Модель кузова и дверей основана на «Low Poly Humvee FREE» от MadTrollStudio, лицензия CC-BY-4.0.
Колёса — ванильные колёса M1025 из игры (модель берётся из файлов DayZ, в мод не копируется).
При распространении мода указывайте автора, текст атрибуции лежит в `@RF_Humvee/CREDITS.txt`:

> This work is based on "Low Poly Humvee FREE" (https://sketchfab.com/3d-models/low-poly-humvee-free-c0e2ddcc4ccf4d49a9303303a6307bcf) by MadTrollStudio (https://sketchfab.com/madtrollstudio) licensed under CC-BY-4.0 (http://creativecommons.org/licenses/by/4.0/)

Люк, открывающиеся капот и багажник, стёкла, камуфляж, коллизия, LOD, анимации и скрипты написаны для мода (`RF_Humvee/source/lowpoly_humvee.py`).

Мод состоит из двух аддонов, чтобы проверять по шагам:

| PBO | Что делает |
|---|---|
| `RF_Humvee.pbo` | **шаг 1, машина в игре**: модель, колёса, 4 места, двигатель и физика (наследуются от Ada 4x4), повреждения, капот (двигатель доступен, когда он открыт) и багажник (груз — когда открыт), 2 окраски (`RF_Humvee`, `RF_Humvee_Desert`), колесо `RF_HumveeWheel`. Анимация люка уже в `model.cfg` |
| `RF_Humvee_Hatch.pbo` | **шаг 2, люк**: действия «Открыть люк» / «Закрыть люк» из салона и снаружи (с крыши), положение сохраняется после рестарта |

## Структура

```
RF_Humvee_Mod/
  @RF_Humvee/              ← готовый мод: копировать в папку DayZ и DayZServer
    mod.cpp
    Addons/RF_Humvee.pbo
    Addons/RF_Humvee_Hatch.pbo
  src/RF_Humvee/           ← исходники аддона (для Addon Builder / P:\)
    config.cpp
    data/rf_humvee.p3d          машина (MLOD, открывается в Object Builder)
    data/proxy/wheel_X_Y.p3d    прокси колёс
    data/model.cfg              колёса, амортизаторы, руль, двери, капот, багажник, люк
    data/rf_humvee_*_co.paa     камуфляж (DXT1)
    scripts/4_World/RF_Humvee/RF_Humvee.c
  src/RF_Humvee_Hatch/     ← исходники аддона люка
  server/                  ← спавн: init.c (тест), cfgeventspawns/events/types
  tools/build_mod.py       ← пересобрать всё: python3 RF_Humvee_Mod/tools/build_mod.py
```

## Шаг 1: машина в игре

1. Скопируйте папку `@RF_Humvee` в каталог **DayZ** (клиент) и в каталог **DayZServer**.
2. В `serverDZ.cfg` на время теста поставьте `verifySignatures = 0;` (PBO не подписаны).
3. Запуск сервера: `DayZServer_x64.exe -config=serverDZ.cfg -mod=@RF_Humvee -dologs -adminlog -scriptDebug=true`
4. Запуск клиента с тем же `-mod=@RF_Humvee` (в лаунчере: Моды → «Добавить локальный мод»).
5. Чтобы машина появилась сразу рядом с вами, вставьте функцию из `server/init_c_test_spawn.c` в
   `mpmissions/dayzOffline.chernarusplus/init.c` (в `class CustomMission`) и вызовите её в начале
   `StartingEquipSetup`. Создайте нового персонажа: собранная заправленная машина появится в 7 м перед ним.
   Есть админ-тулза (VPP, COT)? Тогда достаточно заспавнить `RF_Humvee` и прикрепить 4× `RF_HumveeWheel`,
   `CarBattery`, `CarRadiator`, `SparkPlug`.

Что проверить: машина видна, стоит на колёсах, двери, капот и багажник открываются снаружи, на 4 места можно сесть через открытую дверь, двигатель заводится, машина едет и рулит.

## Шаг 2: люк

Сначала добейтесь, чтобы шаг 1 работал. В `@RF_Humvee/Addons` должны лежать оба PBO (если люк пока
не нужен, уберите `RF_Humvee_Hatch.pbo`). Сядьте в машину: в меню действий появится «Открыть люк».
Снаружи действие доступно, если встать на крышу и смотреть на крышку.

## Если что-то не так, пришлите мне логи

Файлы `*.RPT` и `script_*.log` из `%LocalAppData%\DayZ` (клиент) и из папки профиля сервера. По ним я исправлю мод.

Возможные проблемы:

| Симптом | Причина | Что делать |
|---|---|---|
| Машина невидима или «Cannot load model» | игра не приняла небинаризованный P3D | собрать через **DayZ Tools → Addon Builder** (см. ниже) |
| Колёса висят, крутятся не туда или слишком медленно | масштаб источников анимации в `model.cfg` | пришлите видео или скрин, поправлю `wheel*`/`damper_*` |
| Крышка люка уходит внутрь салона | знак угла | в `data/model.cfg` у `hatch_roof` поменять `angle1 = 1.9198622` на `-1.9198622` |
| Игра пишет ошибку скрипта при запуске | несовпадение API версии игры | пришлите `script_*.log` |

## Сборка через DayZ Tools (бинаризация, подпись)

1. DayZ Tools → **Work Drive** → смонтировать `P:`; скопировать `src/RF_Humvee` и `src/RF_Humvee_Hatch` в `P:\`.
2. **Addon Builder**: Source `P:\RF_Humvee`, Destination `@RF_Humvee\Addons`, включить *Binarize*,
   *Sign* (ключ создаётся в DS Utils). Повторить для `RF_Humvee_Hatch`.
3. Ключ `.bikey` положить в `DayZServer\keys`, и тогда можно вернуть `verifySignatures = 2`.

## Спавн на сервере постоянно

`server/cfgeventspawns_snippet.xml`, `events_snippet.xml`, `types_snippet.xml`: событие `VehicleRF_Humvee`.
Тестовый спавн в `init.c` после проверки уберите.
