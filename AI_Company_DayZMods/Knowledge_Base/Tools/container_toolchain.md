---
title: Что работает в облачном контейнере компании
status: VERIFIED
updated: 2026-11-20
owner: research-lead
tags: [environment, tools, network, blender, ffmpeg, limits]
sources:
  - experiment:2026-11-20 проверка команд (python3, ffmpeg -encoders/-filters, convert, import bpy)
  - experiment:2026-11-20 curl и WebFetch к хостам источников, git clone официальных репозиториев BI
  - experiment:2026-11-20 blender_smoke_test.py (3 LOD, UV, экспорт FBX/OBJ/GLB/.blend — OK) и тестовый ролик ffmpeg 1080x1920
---
# Что работает в облачном контейнере компании

## Кратко
Linux, 4 ядра, 15 ГБ ОЗУ, Python 3.13. Работают: скрипты и конфиги, 3D в Blender headless, монтаж в ffmpeg, исследования через поиск и git. Не работают: DayZ Tools и запуск игры (это Windows и ПК заказчика). Контейнер одноразовый — всё ценное хранится в git.

## Инструменты
| Инструмент | Статус | Примечание |
|---|---|---|
| Python 3.13, git, Node 22 | есть | Pillow 12, numpy 2, PyYAML |
| ffmpeg / ffprobe 6.1.1 | есть | libx264, AAC, drawtext, loudnorm, ass/subtitles; вертикальное видео 1080×1920 собрано и проверено |
| ImageMagick (convert) | есть | генерация и обработка текстур |
| Blender 5.3 (bpy) | по требованию | `Company/Tools/setup_blender.sh`: около 1 ГБ, установка 1–3 минуты; моделирование и экспорт работают |
| DayZ Tools (Workbench, Object Builder, Addon Builder, Binarize, TexView 2, ImageToPAA, DSUtils) | нет | Windows и Steam — только на ПК заказчика |
| Клиент и сервер DayZ | нет | Linux-сервер DayZ потребовал бы SteamCMD, аккаунт с игрой и доступ к Steam — не настроено |
| 7z, wine, steamcmd, упаковщики PBO | нет | упаковщик PBO — задача T-0017 |

## Сеть (политика окружения «limited»)
| Хост или сервис | Статус |
|---|---|
| WebSearch | работает: выдержки и ссылки |
| git clone публичных репозиториев GitHub | работает |
| raw.githubusercontent.com, code.claude.com | работают |
| pypi.org, registry.npmjs.org | работают |
| github.com (веб-страницы) | 400/403 — только git |
| community.bistudio.com, feedback.bistudio.com, forums.bohemia.net, forums.dayz.com, dayz.com, www.bohemia.net, steamcommunity.com, store.steampowered.com, steamdb.info, www.reddit.com, discord.com, www.youtube.com, dayz.fandom.com, stardz-team.github.io, mrcmodding.gitbook.io, extensions.blender.org, download.blender.org | заблокированы прокси; WebFetch тоже не проходит |

## Как проверено
Команды выполнены 2026-11-20 в сессии запуска компании. Результаты зафиксированы в задачах T-0010 и T-0013 и в QA-отчёте.

## Ограничения
Список хостов меняет только заказчик (настройки окружения). После изменения таблицу нужно перепроверить (T-0016).
