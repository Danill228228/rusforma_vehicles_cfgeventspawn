# Происхождение материалов мода RF_Humvee

Область: `RF_Humvee_Mod/src/`, `RF_Humvee_Mod/@RF_Humvee/`, а также `RF_Humvee_Mod/tools/`, `RF_Humvee_Mod/server/`, `RF_Humvee/` (исходники модели). Шаблон: `AI_Company_DayZMods/Development/PROVENANCE_TEMPLATE.md`. Мод коммерческий, закрытый (правило 8 CLAUDE.md).

Основание фактов: `git log/show origin/ccr-1682cad6-sct7q3` (все коммиты после 898eee7 подписаны автором «Claude») и отчёт QA `QA/Reports/QA-T-0045-RF_Humvee-2026-11-20.md`. Что не установлено, так и помечено.

## Текущее дерево

Автор всех материалов ниже: собственная разработка сессии Claude в ветке `ccr-1682cad6-sct7q3` (AI Company DayZMods), если не указано иное. Лицензия «собственная» означает: права принадлежат владельцу проекта, внешней лицензии нет; юридическую оценку авторства ИИ-кода компания не давала (не установлено).

| Материал | Автор и источник | Лицензия | В коммерческом закрытом моде | Подтверждение |
|---|---|---|---|---|
| `src/RF_Humvee/config.cpp`, `src/RF_Humvee_Hatch/config.cpp` | собственная разработка; наследуют ванильный `Offroad_02` (ссылка, не копия) | собственная | да | git log; grep QA: чужих файлов нет |
| `src/RF_Humvee/scripts/4_World/RF_Humvee/RF_Humvee.c` | собственная разработка (`extends Offroad_02`) | собственная | да | git log |
| `src/RF_Humvee_Hatch/scripts/4_World/RF_Humvee_Hatch/RF_HumveeHatch.c`, `ActionRFHatch.c` | собственная разработка | собственная | да | git log; содержание правит lead-engineer, провенанс не меняется |
| `src/RF_Humvee/data/rf_humvee.p3d` | генерируется `tools/build_mod.py` из `RF_Humvee/source/m1025.py` (модель собрана из примитивов; размеры сняты в игре с ванильного M1025 лучами и через API машины, ванильные модели не копировались) | собственная | да | docstring m1025.py и build_mod.py; в P3D есть прокси на ванильные колёса, см. раздел ссылок |
| `src/RF_Humvee/data/rf_humvee_woodland_co.paa`, `rf_humvee_desert_co.paa`, `rf_humvee_body_nohq.paa`, `rf_humvee_body_smdi.paa` | процедурно сгенерированы `tools/texture_atlas.py`, `tools/build_mod.py`, записаны `tools/paa.py`; палитра подобрана «по ванильному M1025» (цвета, не пиксели) | собственная | да | docstring texture_atlas.py. Не установлено: не использовались ли ванильные текстуры как исходные пиксели; по описанию кода — нет |
| `src/RF_Humvee/data/rf_humvee_body.rvmat` | генерируется `build_mod.py` (`write_rvmat`), собственные карты и параметры | собственная | да | заголовок файла; одна ссылка на ванильную `env_land_optic_co.paa` (ниже) |
| `src/RF_Humvee/data/model.cfg` | собственная разработка (генерируется или пишется `build_mod.py`; точно не проверено) | собственная | да | git log |
| `@RF_Humvee/mod.cpp` | собственная разработка | собственная | да | git log |
| `@RF_Humvee/Addons/RF_Humvee.pbo`, `RF_Humvee_Hatch.pbo` | артефакты сборки `tools/pbo.py` + `build_mod.py` из файлов выше, без бинаризации и подписи. Текущий RF_Humvee.pbo собран в bce8988; пересборка после правок — отдельная задача T-0052 | собственная | да, только текущие; PBO из старых коммитов нельзя (см. «История») | git log -- pbo |
| `tools/build_mod.py`, `p3d_mlod.py`, `paa.py`, `pbo.py`, `texture_atlas.py` | собственная разработка, написаны в сессии (Python, numpy) | собственная | да | git log; внешних лицензий в файлах нет |
| `RF_Humvee/source/m1025.py`, `generate_humvee.py`, `preview_template.html` | собственная разработка (генератор модели из примитивов, «без чужих ассетов» по docstring) | собственная | да | docstring |
| `RF_Humvee/model/*` (humvee.obj, .gltf, .mtl, camo png, memory_points.json), `RF_Humvee/preview/humvee_preview.html` | вывод `generate_humvee.py`; это ранний вариант модели (коммит 59b93a6), не вход текущей сборки | собственная | да | git log |
| `server/*.xml`, `server/init_c_test_spawn.c`, `README.md` | собственная разработка; форматы XML сверены с эталонными файлами (QA-T-0045) | собственная | да | QA-T-0045 стадии 1-3 |
| `tools/__pycache__/` | кэш Python, не материал мода (в .gitignore) | нет | не включать в сборку | .gitignore |

## Ссылки на ресурсы BI (не копии)

Мод не содержит файлов игры. Он ссылается на ванильные ресурсы, которые есть у каждого игрока с DayZ:
- Наследование `class RF_Humvee: Offroad_02` (config.cpp, строка 41) и `extends Offroad_02` в RF_Humvee.c; слоты и предметы `Offroad_02_Wheel_*`, `Offroad_02_Door_*`, `Offroad_02_Hood`, `Offroad_02_Trunk`. Двигатель, коробка, подвеска, звуки и места экипажа берутся из ванильного класса.
- Прокси колёс `\DZ\vehicles\wheeled\proxies\...` в P3D (`build_mod.py`, add_proxy).
- Текстура `dz\data\data\env_land_optic_co.paa` в `rf_humvee_body.rvmat` (строка 84) и в `build_mod.py`.
- Ванильная текстура и материалы крыши M1025 по docstring `build_mod.py` подключаются ссылками.

Ограничения BI на коммерческое использование и работу с ресурсами игры: `AI_Company_DayZMods/Knowledge_Base/Research/commercial_use_rules.md` (EULA DayZ и Tools EULA). Продажа и платная передача — только после письменного разрешения BI.

## История

- Модель «Low Poly Humvee FREE» (автор MadTrollStudio, лицензия CC-BY-4.0, источник: Sketchfab по README.md:96) была в репозитории вместе с `license.txt`, `scene.gltf`, `scene.bin`, `lowpoly_humvee.py` и `CREDITS.txt`. По `git ls-tree` она присутствует в коммитах ecbcb60 и bb1eccc (в 786d095, ec8cad2 и позже — уже нет) и удалена в 26c4dbd. Формулировка «786d095…ecbcb60» в задаче неточна по порядку коммитов: 786d095 идёт после 26c4dbd, на проверку ls-tree чужих файлов в нём нет.
- Старые сборки (PBO) из ecbcb60 и bb1eccc содержат эту модель. Распространять их без атрибуции (автор, источник, лицензия CC-BY-4.0, указание изменений) нельзя.
- Текущая версия (начиная с 26c4dbd, модель собственная с ec8cad2) геометрии MadTrollStudio не содержит: grep по `*.py/*.c/*.cpp` пуст (QA-T-0045, стадия 4); упоминание осталось только в `README.md` (строка 96) как справка об истории. Атрибуция для текущей версии не требуется; это решение фиксируется здесь. Остаётся рекомендация держать старые коммиты вне передаваемых заказчику сборок.
- Не установлено: оригинальная страница Sketchfab и текст лицензии в этой сессии не проверялись (по коммитам и отчёту QA).
