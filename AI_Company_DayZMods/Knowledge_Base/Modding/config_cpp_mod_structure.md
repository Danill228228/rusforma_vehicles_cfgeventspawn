---
title: config.cpp мода — CfgPatches и CfgMods по официальным образцам BI
status: VERIFIED
updated: 2026-11-20
owner: research-lead
game_version: образцы BI от 2023-05-22; актуальность для текущей версии перепроверить по вики (T-0016)
tags: [config, cfgpatches, cfgmods, script-modules, mod-structure]
sources:
  - https://github.com/BohemiaInteractive/DayZ-Samples (Test_SmartCar, Test_ScriptCmdSwim, Test_Inputs — config.cpp; коммит da5e543)
  - https://community.bistudio.com/wiki/DayZ:Modding_Basics (выдержка WebSearch 2026-11-20 — CfgMods, defs, worldScriptModule; PlayerBase объявлен в 4_World)
---
# config.cpp мода — CfgPatches и CfgMods

## Кратко
Каждый аддон (PBO) содержит `config.cpp`. `CfgPatches` регистрирует аддон и его зависимости (`requiredAddons`). `CfgMods` подключает скрипты к модулям движка через `class defs`. Путь в `files[]` — это путь внутри игровой файловой системы (префикс PBO плюс папка), а не путь на диске.

## Подробно
Эталон из официального образца Test_SmartCar:
```cpp
class CfgPatches
{
	class smpl_test_smartcar
	{
		units[] = {};
		weapons[] = {};
		requiredVersion = 0.1;
		requiredAddons[] = {"DZ_Data"};
	};
};

class CfgMods
{
	class smpl_test_scriptsmartccar
	{
		type = "mod";
		class defs
		{
			class worldScriptModule
			{
				value = "";
				files[] = {"samples/test_smartcar/scripts/4_world"};
			};
		}
	};
};
```
- Один мод может подключать несколько модулей. В образце Test_Inputs: `gameScriptModule` → `samples/test_inputs/scripts/gameModule`, `worldScriptModule` → `samples/test_inputs/scripts/worldModule`. Там же `inputs = "samples\test_inputs\my_new_inputs.xml";` — собственные привязки ввода.
- Модуль определяет класс в `defs`, а не имя папки: в образцах встречаются и `scripts/4_world`, и `scripts/worldModule`.
- Во всех 16 официальных config.cpp встречаются только `gameScriptModule` (1 раз) и `worldScriptModule` (6 раз). Имена `engineScriptModule`, `gameLibScriptModule`, `missionScriptModule` и их соответствие слоям 1_Core, 2_GameLib, 5_Mission в образцах не встречаются. Это знание из сторонней DayZ Modding Wiki (уровень PARTIAL), подтверждение — задача T-0019.
- Ванильный класс модифицируют в модуле, где он объявлен. Вики BI: PlayerBase — 4_World. Образец переопределяет `CarScript` через `modded class CarScript` в worldScriptModule.
- В образцах BI после `class defs {…}` стоит `}` без `;`, и это работает. Линтер компании (T-0021) не должен считать это ошибкой. Стандарт для нашего кода — `};`.
- В образцах `author`, `name`, `url` в CfgPatches — заглушки («yourname», «addonname»): это метаданные, не влияющие на загрузку (гипотеза).

## Как проверено
Прочитаны все 16 config.cpp репозитория DayZ-Samples (поиск классов модулей и полей). Выдержка вики BI получена через WebSearch: полная страница из контейнера недоступна.

## Ограничения и открытые вопросы
- Поля `dir`, `name`, `dependencies[]`, `picture`, `action` в CfgMods образцы не используют. Назначение и обязательность проверить (T-0019, T-0038).
- Лицензия образцов ADPL-SA: атрибуция, только некоммерческое использование, share-alike, только Arma и DayZ. Изучать можно; переносить код образцов в коммерческие моды нельзя.
