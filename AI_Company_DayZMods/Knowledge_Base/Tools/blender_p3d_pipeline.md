---
title: Blender → P3D — аддон Arma 3 Object Builder
status: PARTIAL
updated: 2026-11-20
owner: modeler-3d
tags: [blender, p3d, object-builder, export, paa, 3d]
sources:
  - https://mrcmodding.gitbook.io/arma-3-object-builder (документация аддона; найдена WebSearch, из контейнера недоступна)
  - https://github.com/MrClock8163/Arma3ObjectBuilder (исходники, GPLv3)
  - https://extensions.blender.org/add-ons/arma3objectbuilder/ (каталог расширений Blender)
---
# Blender → P3D — аддон Arma 3 Object Builder

## Кратко
Arma 3 Object Builder — аддон Blender от MrClock, преемник ArmaToolbox, лицензия GPLv3. Импорт и экспорт P3D в формате MLOD: каждый LOD — отдельный объект, proxy — отдельно. Версия 2.5.x требует Blender 4.2+ и умеет импортировать PAA (DXT1/DXT5). Поддержка DayZ официально не заявлена — это гипотеза, её проверяет задача T-0033.

## Подробно (по выдержкам поиска от 2026-11-20)
- Меню: File → Import / Export → Arma 3 model (.p3d).
- Читает только небинаризованный P3D (MLOD); бинаризованный ODOL не открывается.
- В истории версий есть пометка о критической ошибке экспорта P3D в одной из версий. Перед использованием выбрать версию без неё.
- Вики BI (страница Enfusion Blender Tools для Arma Reforger) пишет, что небинаризованные P3D для Arma 3 и DayZ импортируются в Blender. Это про другой аддон, но косвенно подтверждает общий формат MLOD.

## Как проверено
В контейнере проверен только Blender 5.3 headless (smoke-тест прошёл). Аддон не устанавливался.

## Открытые вопросы (T-0033)
Установка аддона в bpy без интерфейса; экспорт MLOD, который открывает Object Builder из DayZ Tools; сохранение именованных выделений, memory-точек и свойств LOD; совместимость с Blender 5.3.
