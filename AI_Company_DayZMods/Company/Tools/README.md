# Инструменты компании

| Файл | Назначение | Запуск |
|---|---|---|
| `company.py` | CLI `./dzm`: задачи, проекты, ошибки, ростер, найм, база знаний, учёт токенов, отчёты, проверка целостности | `./dzm -h` |
| `setup_blender.sh` | ставит Blender 5.3 как Python-модуль (bpy) и печатает путь к python | `PY=$(bash AI_Company_DayZMods/Company/Tools/setup_blender.sh)` |
| `blender_smoke_test.py` | проверка 3D-конвейера: 3 LOD, UV, материал, экспорт FBX/OBJ/GLB, .blend | `$PY AI_Company_DayZMods/Company/Tools/blender_smoke_test.py /tmp/out` |

## Частые команды
```bash
./dzm status                                   # начало сессии
./dzm inbox research-lead                      # задачи и сообщения сотрудника
./dzm task add --title "..." --assignee lead-engineer --type dev --priority P1 --project PRJ-0002 --deps T-0018 --budget 80000
./dzm task status T-0018 IN_PROGRESS --by research-lead
./dzm task update T-0018 --result "..." --files "AI_Company_DayZMods/Knowledge_Base/..." --by research-lead
./dzm task status T-0018 REVIEW --by research-lead
./dzm task review T-0018 --by qa-lead --verdict PASS --report "..." --complete
./dzm task comment T-0018 --by qa-lead --to research-lead --text "..."
./dzm bug add --title "..." --severity S2 --repro "..." --cause "..." --location "файл:строка" --fix "..." --by qa-lead
./dzm kb search "netsync rpc"
./dzm run log --agent qa-lead --tokens 41000 --task T-0018
./dzm report ceo --save                         # Reports/Weekly/CEO_REPORT_<дата>.md
./dzm validate                                  # целостность всех данных
python3 -m unittest discover -s AI_Company_DayZMods/QA/Tests -v
```

Данные: `Company/Tasks/tasks.json`, `Company/Tasks/runs.jsonl`, `Company/HR/roster.json`, `QA/Bugs/bugs.json`. Витрины `BOARD.md`, `ROSTER.md`, `BUGS.md`, `Knowledge_Base/INDEX.md` генерируются автоматически — вручную их не правят.
