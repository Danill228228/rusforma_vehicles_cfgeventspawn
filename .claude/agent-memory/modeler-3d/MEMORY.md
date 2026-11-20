# Память агента modeler-3d

- 2026-11-20: Blender 5.3 headless работает (smoke-тест: 3 LOD 588/108/12 треугольников, UV, FBX/OBJ/GLB/.blend). Установка ~1 ГБ, 1–3 минуты: setup_blender.sh.
- Экспорт P3D через аддон Arma 3 Object Builder (GPLv3) — гипотеза для DayZ, задача T-0033.
- 2026-11-20 (T-0054): атлас RF_Humvee без padding и с одинаковой плотностью 127 px/м: первые правки: dilate, UV LOD3, _smdi по зонам. Фары: carscript.c регистрирует селекции 0…8 с материалами *MatOn/Off; без выделений light_* в LOD0 свечения не будет (проверять в игре).
- Скрипты в DayZ-Script-Diff лежат в scripts/4_world/entities/vehicles/carscript.c (лицензия DPL: только изучать).
