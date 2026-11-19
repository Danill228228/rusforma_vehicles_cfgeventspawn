# RF_Humvee — HMMWV с открываемым люком

Армейский внедорожник в стиле HMMWV M1114 (бронированная крыша и двери с X-рёбрами, кенгурятник, жалюзи на капоте,
лесной камуфляж) с круглым люком стрелка на крыше, который открывается и закрывается.

**Модель в моде.** Мод `RF_Humvee_Mod` построен на ванильном M1025 (Offroad_02) из игры; от этой папки в нём
остались только помощники геометрии `generate_humvee.py`, из которых `RF_Humvee_Mod/tools/build_mod.py` собирает
люк. Файлы `model/` и `preview/` ниже — прежняя модель из примитивов.

## Состав

| Путь | Что это |
|---|---|
| `model/humvee.gltf` | 3D-модель glTF 2.0: ноды `body`, `interior`, `wheel_1_1…wheel_2_2`, `hatch_roof_pivot → hatch_roof` |
| `model/humvee.obj` + `.mtl` | та же модель в OBJ, объекты названы как селекции DayZ, плюс ребро `hatch_roof_axis` |
| `model/humvee_camo_woodland.png` | бесшовная текстура лесного камуфляжа (для DayZ сконвертировать в `rf_humvee_woodland_co.paa` через TexView 2) |
| `model/memory_points.json` | координаты memory-точек (ось люка, центры колёс) |
| `preview/humvee_preview.html` | интерактивный 3D-просмотр (открыть в браузере): люк, окраска, камеры |
| `source/generate_humvee.py` | генератор прежней модели (`python3 source/generate_humvee.py`, нужен только numpy) |
| `../RF_Humvee_Mod/` | **готовый мод DayZ** (`@RF_Humvee`): ванильный M1025 с люком — см. его README |

## Как устроен люк

* В модели крышка — отдельная селекция **`hatch_roof`**, ось шарнира — две точки **`hatch_roof_axis`**
  в LOD Memory (x = ±0.25, y = 2.032, z = −1.005).
* `config.cpp` → `AnimationSources/HatchRoof` (`source = "user"`, 1.2 с).
* `model.cfg` → `Animations/hatch_roof`, `type = "rotation"`, `angle1 = -1.9199` (−110°).
* Скрипт: `RF_Humvee.RF_SetHatchOpen(bool)` вызывает `SetAnimationPhase("HatchRoof", 0/1)` на сервере;
  состояние сохраняется в базе (`OnStoreSave/OnStoreLoad`).
* Действия:
  * из салона: «Открыть люк» / «Закрыть люк» доступны с любого места;
  * снаружи: когда игрок смотрит на крышку (компонент `hatch_roof` в View/Fire Geometry).

## Сборка P3D (что осталось сделать руками)

DayZ не читает glTF/OBJ напрямую, модель нужно перевести в P3D:

1. **Blender**: File → Import → glTF (`humvee.gltf`) или Wavefront OBJ (`humvee.obj`, Forward = Z, Up = Y).
2. Экспорт в P3D аддоном *Arma Toolbox* для Blender или через FBX → Object Builder (DayZ Tools).
3. В Object Builder:
   * **LOD 0 (Resolution)**: всё, кроме колёс; селекции `camo` (кузов) и `hatch_roof` (крышка);
   * **Geometry / View Geometry / Fire Geometry**: выпуклые компоненты, крышка люка — отдельным компонентом
     с селекцией `hatch_roof`, масса в Geometry около 2500 кг;
   * **Memory**: `hatch_roof_axis` (2 точки) плюс стандартные точки машины (места экипажа, `pos_driver`,
     `pos_codriver`, оси колёс, `wheel_X_Y_damper_land` и т.д.), удобнее всего скопировать из DayZ-Samples (Test_Vehicle).
   * Колесо (`wheel_1_1`) — отдельный файл `data/rf_humvee_wheel.p3d`.
4. Положите `rf_humvee.p3d`, `rf_humvee_wheel.p3d`, `model.cfg` и текстуры (`rf_humvee_olive_co.paa`,
   `rf_humvee_desert_co.paa`) в `RF_Humvee/data/`.
5. Допишите в `data/model.cfg` кости и анимации колёс, амортизаторов и руля из ванильного Ada 4x4
   (`OffroadHatchback`), от которого наследуется физика.
6. Соберите PBO через Addon Builder (`RF_Humvee` → `@RF_Humvee/Addons/RF_Humvee.pbo`).
7. Добавьте записи из `server/` в миссию сервера.

> Конфиг и скрипты — рабочая заготовка, их нужно проверить в игре после сборки P3D:
> без настоящей модели их нельзя запустить.
