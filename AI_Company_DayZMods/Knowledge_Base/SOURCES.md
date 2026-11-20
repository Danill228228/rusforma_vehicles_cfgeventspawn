# Реестр исследовательских источников

_Владелец: research-lead · доступ проверен из контейнера 2026-11-20 (curl, WebFetch, git clone), повторно — после открытия хостов заказчиком · правила: `Company/Rules/RESEARCH_PROTOCOL.md`_

Обозначения доступа: ✅ работает · 🛡 прокси пропускает, но сайт закрыт защитой Cloudflare от ботов (обходить не будем — D-015) · 🔎 только выдержки через WebSearch · ⛔ заблокировано сетевой политикой окружения.

## Официальные (надёжность: высокая)
| Источник | Адрес | Доступ | Что берём |
|---|---|---|---|
| BI Community Wiki — DayZ | https://community.bistudio.com/wiki/Category:DayZ | 🛡 🔎 | моддинг, CE, инструменты. Известные страницы: `DayZ:Modding_Basics`, `DayZ:Central_Economy_mission_files_modding`, `DayZ:Central_Economy_setup_for_custom_terrains`, `DayZ:Configuring_2D_Map` |
| DayZ-Samples (BI, GitHub) | https://github.com/BohemiaInteractive/DayZ-Samples | ✅ git clone (коммит da5e543 от 2023-05-22) | 13 учебных модов: config.cpp, скрипты, здания, техника (Test_SmartCar), ввод. Лицензия ADPL-SA |
| DayZ-Central-Economy (BI, GitHub) | https://github.com/BohemiaInteractive/DayZ-Central-Economy | ✅ git clone (коммит 7bfc95c от 2026-11-18) | эталонные XML CE: chernarusplus, enoch, sakhal, nasdara, сезонные миссии, CETool |
| DayZ-Script-Diff (BI, GitHub) — ванильные скрипты игры | https://github.com/BohemiaInteractive/DayZ-Script-Diff | ✅ git clone (коммит 78be1c4 от 2026-11-03: Build 1.30.164289, Scripts Rev. 127855) | полный исходник ванильных скриптов 1_core…5_mission — главный источник по API движка. Лицензия — DayZ Public License (DPL: Attribution, Noncommercial, DayZ Only), указана в README.md репозитория (отдельного файла LICENSE нет): только изучение, без копирования в моды и без коммерческого использования. Найден lead-engineer 2026-11-20 (WebSearch его не находил) |
| BI Feedback Tracker | https://feedback.bistudio.com/ | 🛡 | известные баги и ограничения движка |
| Форумы Bohemia | https://forums.bohemia.net/ | 🛡 | ответы разработчиков, история инструментов |
| Форумы DayZ | https://forums.dayz.com/ | 🛡 | моддинг, серверы |
| Сайт DayZ | https://dayz.com/ | 🛡 | заметки к обновлениям, статус-репорты |
| Сайт Bohemia | https://www.bohemia.net/ | ✅ | лицензии (ADPL-SA и др.), правила монетизации |
| Правила BI для коммерческой модели | https://www.bistudio.com/community/game-content-usage-rules · https://www.bistudio.com/monetization · https://community.bistudio.com/wiki/Intellectual_Property · https://data.bistudio.com/dayz/Public_PC_DayZ_Server_Hosting_Rules_V11.pdf | ✅ прочитаны 2026-11-20: /en/monetization, /en/monetization/dayz, /en/licenses/dayz-end-user-license, /en/licenses/bohemia-interactives-tools-end-user-license, PDF V11 (www.bistudio.com перенаправляет на www.bohemia.net; Game Content Usage Rules прочитаны; вики-страница IP — 🛡) | продажа модов, монетизация серверов, использование игрового контента (T-0041) |

## Сообщество (надёжность: средняя или низкая — нужны подтверждения)
| Источник | Адрес | Доступ | Что берём |
|---|---|---|---|
| Steam Workshop DayZ | https://steamcommunity.com/app/221100/workshop/ | ✅ | обзор существующих модов, совместимость |
| DayZ Modding Wiki (StarDZ-Team, неофициальная) | https://stardz-team.github.io/DayZ-Modding-Wiki/ | ✅ | заявляет разбор 2 800+ ванильных файлов и 15 образцов BI; есть русская версия (`/ru/`). Перепроверять по официальным источникам |
| Публичные моды на GitHub | `git clone --depth 1 https://github.com/<owner>/<repo>` | ✅ для публичных | исходники модов — только с учётом лицензии |
| Arma 3 Object Builder (аддон Blender) | https://github.com/MrClock8163/Arma3ObjectBuilder · документация https://mrcmodding.gitbook.io/arma-3-object-builder | git clone не проверялся · документация ✅ | экспорт P3D из Blender (GPLv3) |
| Blender Extensions | https://extensions.blender.org/ | ✅ (точный адрес страницы аддона уточнить: прежний вернул 404) | аддоны Blender |
| Reddit, Discord, YouTube | reddit.com, discord.com, youtube.com | ⛔ | обсуждения и туториалы (низкая надёжность) |
| DayZ Fandom Wiki | https://dayz.fandom.com/ | ⛔ | геймплей, не моддинг |

## Инструменты доступа
| Инструмент | Статус | Когда применять |
|---|---|---|
| WebSearch | ✅ | поиск страниц и коротких выдержек; полный текст страниц не даёт |
| WebFetch и curl | ✅ только для разрешённых хостов | чтение страниц (сейчас: raw.githubusercontent.com, code.claude.com) |
| git clone публичных репозиториев GitHub | ✅ | официальные репозитории BI и открытые моды. Клонировать в `/home/user/<owner>/<repo>`, не в наш репозиторий |
| raw.githubusercontent.com | ✅ | отдельные файлы публичных репозиториев |
| PyPI, npm | ✅ | библиотеки и инструменты (bpy 5.3.0 установлен и работает) |
| Браузер с графическим интерфейсом | нет в облаке | возможен через приложение Claude на ПК заказчика (подключение компьютера) |

## Статус доступа (после открытия хостов заказчиком, 2026-11-20)
Заказчик одобрил 12 хостов (T-0013). Работают: www.bohemia.net (и www.bistudio.com через перенаправление), data.bistudio.com, steamcommunity.com, stardz-team.github.io, mrcmodding.gitbook.io, extensions.blender.org. Вики BI, трекер, форумы BI и DayZ, dayz.com требуют проверку браузером (Cloudflare) — обходить её не будем (D-015). Замена: выдержки WebSearch, браузер заказчика через приложение Claude на ПК, страницы, сохранённые заказчиком в `Knowledge_Base/Research/inbox/`. Reddit, Discord, YouTube и Fandom не открывались — по запросу.
