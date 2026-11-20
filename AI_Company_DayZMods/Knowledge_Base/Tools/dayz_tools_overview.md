---
title: DayZ Tools — состав и назначение (требует проверки)
status: HYPOTHESIS
updated: 2026-11-20
owner: research-lead
tags: [dayz-tools, workbench, object-builder, addon-builder, binarize, signing]
sources: []
---
# DayZ Tools — состав и назначение

## Кратко
DayZ Tools ставится через Steam и работает только в Windows. Ниже — рабочие знания команды без подтверждения первоисточником. Использовать как ориентир; проверка по вики BI — задача T-0016.

## Состав (гипотеза)
| Инструмент | Назначение |
|---|---|
| Workbench | среда Enforce Script: редактор, отладка, браузер ресурсов, редакторы layout и анимаций |
| Object Builder | редактор P3D: LOD, геометрии, выделения, memory-точки, материалы |
| Terrain Builder | создание карт |
| Addon Builder | упаковка папки в PBO с бинаризацией и подписью |
| Binarize | бинаризация: config.cpp → config.bin, P3D MLOD → ODOL, обработка текстур |
| TexView 2, ImageToPAA | просмотр и конвертация текстур в .paa |
| DSUtils (DSCreateKey, DSSignFile, DSCheckSignatures) | ключи .bikey/.biprivatekey и подписи .bisign |
| Publisher | публикация мода в Steam Workshop |
| Извлечение игровых данных и P-диск | распаковка данных игры, в том числе ванильных скриптов, на P:\ |

## Что проверить
Актуальный состав, имена и параметры командной строки Addon Builder, DSSignFile и Binarize — для автоматизации сборки на ПК заказчика.
