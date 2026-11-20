#!/usr/bin/env bash
# Ставит Blender как Python-модуль (bpy) для headless-работы 3D-отдела.
# Идемпотентно: повторный запуск только печатает путь к python.
# Использование: bash AI_Company_DayZMods/Company/Tools/setup_blender.sh   →  печатает путь к python с bpy
set -euo pipefail
BPY_VERSION="${DZM_BPY_VERSION:-5.3.0}"
VENV="${DZM_BLENDER_VENV:-$HOME/.cache/dzm/blender-venv}"
if [ ! -x "$VENV/bin/python" ] || ! "$VENV/bin/python" -c "import bpy" >/dev/null 2>&1; then
  echo "Установка bpy==$BPY_VERSION в $VENV (около 1 ГБ, 1–3 минуты)…" >&2
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q --disable-pip-version-check "bpy==$BPY_VERSION" >&2
fi
"$VENV/bin/python" -c "import bpy, sys; print('bpy', bpy.app.version_string, file=sys.stderr)"
echo "$VENV/bin/python"
