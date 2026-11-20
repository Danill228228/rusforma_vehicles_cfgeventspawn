# Доказательства проверок конвейеров — 2026-11-20

_Сессия запуска компании. Команды выполнены в облачном контейнере; вывод приведён без правок (сокращены только служебные строки). Дополняет QA-PRJ-0001-2026-11-20.md, где эти шаги отмечены NOT RUN (не перезапускались аудитором)._

## 1. Blender 5.3 headless (3D-отдел)
```
$ PY=$(bash AI_Company_DayZMods/Company/Tools/setup_blender.sh)      # bpy 5.3.0
$ $PY AI_Company_DayZMods/Company/Tools/blender_smoke_test.py <scratch>/blender_test
{ "blender": "5.3.0",
  "lods": { "crate_lod0": {"verts": 296, "tris": 588, "uv_layers": 1},
            "crate_lod1": {"verts": 56,  "tris": 108, "uv_layers": 1},
            "crate_lod2": {"verts": 8,   "tris": 12,  "uv_layers": 1} },
  "files": { "fbx": {"ok": true, "bytes": 28012}, "obj": {"ok": true, "bytes": 34320},
             "glb": {"ok": true, "bytes": 22996}, "blend": {"ok": true, "bytes": 99949} },
  "lod_order_ok": true, "ok": true }
exit=0
```

## 2. ffmpeg и ImageMagick (медиаотдел)
```
$ ffmpeg -version            → ffmpeg version 6.1.1-3ubuntu5
$ ffmpeg -encoders | grep    → libx264, aac
$ ffmpeg -filters  | grep    → drawtext (libfreetype), loudnorm (EBU R128), ass (libass)
$ bash AI_Company_DayZMods/Media/Finished/_pipeline_test/build.sh <scratch>/short_test.mp4
$ ffprobe ... short_test.mp4
stream|codec_name=h264|width=1080|height=1920|r_frame_rate=25/1
stream|codec_name=aac
format|duration=3.000000
$ convert -size 512x512 xc:'#4a4f3a' ... crate_co.png → PNG 512x512 8-bit sRGB
```
Замечание: lavfi по умолчанию даёт 25 fps — в build.sh задано `-r 30` явно (стандарт Shorts).

## 3. Агенты компании
```
$ claude plugin validate .claude/agents          → √ Validation passed
# В текущей сессии (папки .claude не было на старте): Agent(subagent_type="qa-lead") →
#   "Agent type 'qa-lead' not found"
$ claude -p "Назови ... имена кастомных субагентов ..." --model haiku --max-turns 1
config-build-engineer, hr-director, lead-engineer, media-director, modeler-3d, project-planner, qa-lead, research-lead, screenwriter, video-editor
$ claude -p "<делегируй аудит агенту qa-lead>" --model haiku --permission-mode auto --output-format json
is_error=False, turns=2, duration_ms=97474, total_cost_usd=0.2350
  claude-haiku-5-5 (оркестратор CEO): out 2992, cache_creation 24011, cache_read 77948, $0.0071
  claude-sonnet-5-5 (qa-lead):        out 10016, cache_creation 37021, cache_read 351652, $0.2279
```
Вывод: в новой сессии агенты загружаются нативно; в сессии, где их создали, работает запуск через отдельный процесс `claude -p`.
