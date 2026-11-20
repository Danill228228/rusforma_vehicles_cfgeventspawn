---
title: Управление машиной из скрипта — официальный образец Test_SmartCar
status: PARTIAL
updated: 2026-11-20
owner: research-lead
game_version: образец BI от 2023-05-22; API мог измениться, сверить с ванильными скриптами (T-0026)
tags: [vehicles, carscript, enforce-script, input, modded-class]
sources:
  - https://github.com/BohemiaInteractive/DayZ-Samples (Test_SmartCar/scripts/4_world/CarScript.c, 229 строк)
---
# Управление машиной из скрипта — образец Test_SmartCar

## Кратко
Образец показывает, как управлять машиной без водителя: `modded class CarScript` переопределяет `OnInput(float dt)` и сам задаёт газ, тормоз, руль и передачи. Логика работает только на сервере.

## Подробно
- Точка входа — `override void OnInput(float dt)`. Ранний выход: `if (!GetGame().IsServer() || CrewMember(DayZPlayerConstants.VEHICLESEAT_DRIVER)) return;` — только сервер и только без водителя.
- Чтение состояния: `EngineGetRPM()`, `EngineGetRPMIdle()`, `EngineGetRPMMin()`, `EngineGetRPMRedline()`, `EngineIsOn()`, `GetGear()`, `GetGearsCount()`, `GearboxGetType()`, `GearboxGetMode()`, `GetSpeedometer()`.
- Управление: `EngineStart()`, `EngineStop()`, `SetThrust(throttle, 0.0, 0.0)`, `SetBrake(value, 0, false)`, `SetHandbrake(value)`, `SetSteering(value, false)`, `ShiftUp()`, `ShiftDown()`, `ShiftTo(gear)`, `SetClutchState(false)`, `SetBrakesActivateWithoutDriver(false)`.
- Физическое тело остаётся активным благодаря `dBodyActive(this, ActiveState.ACTIVE);`.

## Как проверено
Прочитан исходник официального образца (один источник). Компиляция в текущей версии игры не проверялась.

## Ограничения и открытые вопросы
- Смысл второго и третьего аргументов `SetThrust` и `SetBrake` — по ванильным Car/CarScript (T-0026).
- Лицензия ADPL-SA: изучать можно, копировать в коммерческие моды нельзя.
