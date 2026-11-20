---
title: Форматы PAA и суффиксы текстур (_co, _nohq, _smdi)
status: PARTIAL
updated: 2026-11-20
owner: modeler-3d
tags: [texture, paa, vehicle]
sources:
  - https://community.bistudio.com/wiki/PAA
  - https://community.bistudio.com/wiki/TexConvert.cfg
  - https://community.bistudio.com/wiki/Arma:_Texture_Naming_Rules
  - https://armaio.readthedocs.io/stable/paa/format/
---

# Форматы PAA и суффиксы текстур (_co, _nohq, _smdi)

## Кратко

## Подробно

## Как проверено

## Ограничения и открытые вопросы


## Подтверждено (VERIFIED по выдержкам WebSearch; сами страницы BI из контейнера недоступны)
- TexConvert поддерживает ARGB4444, ARGB8888, AI88, DXT1-DXT5, P8; формат выбирается по суффиксу имени (TexConvert.cfg).
- Коды типа в PAA: 0xFF01 = DXT1, 0x4444 = ARGB4444, 0x8888 = ARGB8888 (armaio). Мипы: таблица до 16 смещений, у блока 24-битный размер.
- Суффиксы (Texture Naming Rules): _CO цвет sRGB; _CA цвет с альфой; _NOHQ карта нормалей high quality; _SMDI оптимизированная карта блика. Нормали бывают DXT1 или swizzled DXT5 (HQ Normal Maps / BI).
- Максимум TexConvert по умолчанию 4096; больше Arma не загрузит.
- Вики DayZ Modding Wiki (stardz-team) трактует _nohq/_smdi иначе, чем BI: не использовать как источник.

## Гипотезы (нужен эксперимент на ПК заказчика)
- Точная раскладка каналов swizzled-DXT5 для _nohq и формат по умолчанию для _smdi в TexConvert.cfg не подтверждены. Поэтому _nohq/_smdi оставлены DXT1 (RGB), 3-компонентная нормаль разрешена. Эксперимент: прогнать через ImageToPAA/TexView эталонный _nohq и сравнить тип/каналы с нашим.
- Флаг LZO (старший бит ширины мипа, LZO1X) не подтверждён; писать без проверки на ПК нельзя. Следующий шаг: LZO через DayZ Tools ImageToPAA на ПК или эксперимент с python-lzo.
- Разумное разрешение техники: 2048 для одного атласа на машину (консервативно; ванильная техника использует 2048-4096, не проверено). 4096 дал ~11 МБ на карту.
