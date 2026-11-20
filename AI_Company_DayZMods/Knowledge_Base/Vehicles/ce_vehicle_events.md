---
title: Спавн техники в Central Economy — cfgeventspawns.xml и events.xml
status: VERIFIED
updated: 2026-11-20
owner: research-lead
game_version: официальный репозиторий CE, коммит 7bfc95c от 2026-11-18
tags: [ce, central-economy, vehicles, cfgeventspawns, events, xml]
sources:
  - https://github.com/BohemiaInteractive/DayZ-Central-Economy (dayzOffline.chernarusplus/cfgeventspawns.xml и db/events.xml)
  - experiment:2026-11-20 разбор XML официальной Черноруссии скриптом Python (xml.etree.ElementTree)
  - https://community.bistudio.com/wiki/DayZ:Central_Economy_mission_files_modding (найдена WebSearch; полный текст из контейнера недоступен)
---
# Спавн техники в Central Economy

## Кратко
Техника спавнится событиями CE. `db/events.xml` описывает событие: сколько машин, какие классы, время жизни. `cfgeventspawns.xml` задаёт фиксированные точки `<pos x z a>`, где событие может появиться. Связь — по одинаковому имени события.

## Подробно
Официальный формат cfgeventspawns.xml:
```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<eventposdef>
	<event name="VehicleCivilianSedan">
		<pos x="12071.933594" z="9129.989258" a="317.953339" />
	</event>
</eventposdef>
```
- Атрибуты `pos` в официальных файлах только `x`, `z` (координаты карты) и `a` (угол поворота). Высота не задаётся.
- Официальная Черноруссия: 35 событий, из них 9 событий техники; у них 552 точки, уникальных 498. 54 точки используются сразу несколькими событиями — BI сама допускает общие точки.
  По событиям: VehicleCivilianSedan 55, VehicleSedan02 59, VehicleHatchback02 56, VehicleOffroadHatchback 81, VehicleOffroad02 21, VehicleMotorbike 97, VehicleTruck01 111, VehicleBoat 72, VehicleTransitBus 0.

Событие в events.xml (VehicleCivilianSedan, официальная Черноруссия):
```xml
<event name="VehicleCivilianSedan">
    <nominal>8</nominal> <min>5</min> <max>11</max>
    <lifetime>300</lifetime> <restock>0</restock>
    <saferadius>500</saferadius> <distanceradius>500</distanceradius> <cleanupradius>200</cleanupradius>
    <flags deletable="0" init_random="0" remove_damaged="1" />
    <position>fixed</position> <limit>mixed</limit> <active>1</active>
    <children>
        <child lootmax="0" lootmin="0" max="5" min="3" type="CivilianSedan" />
        <child lootmax="0" lootmin="0" max="5" min="3" type="CivilianSedan_Black" />
        <child lootmax="0" lootmin="0" max="5" min="3" type="CivilianSedan_Wine" />
    </children>
</event>
```
- `position` = `fixed` — событие берёт точки из cfgeventspawns.xml.
- Точный смысл nominal, min, max, радиусов и флагов — по вики BI, которая пока недоступна (открытые вопросы).

## Применение к активу заказчика
Файл `rusforma_vehicles_cfgeventspawn` в корне репозитория — содержимое cfgeventspawns.xml для техники пака CrSk и общего события `VehicleSpawnPoints`: 42 события, 144 точки, из них только 21 уникальная. Проверка QA — `QA/Bugs/BUGS.md`, `QA/Reports/`.

## Как проверено
Официальные файлы прочитаны из клона репозитория и разобраны парсером. Цифры по Черноруссии получены скриптом.

## Ограничения и открытые вопросы
- Значение saferadius, distanceradius, cleanupradius, restock и флагов, а также поведение CE при нехватке свободных точек — прочитать на вики BI (T-0016) или проверить на сервере.
- Что делает сервер при некорректном XML (игнорирует весь файл или его часть) — проверить на сервере заказчика.
