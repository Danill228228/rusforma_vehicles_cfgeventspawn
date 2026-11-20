#!/usr/bin/env bash
# Тест видеоконвейера: 3-секундный вертикальный ролик 1080x1920 (Shorts/TikTok) с титром и звуком.
# Использование: bash AI_Company_DayZMods/Media/Finished/_pipeline_test/build.sh [выходной.mp4]
set -euo pipefail
OUT="${1:-/tmp/dzm_short_test.mp4}"
ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i "color=c=0x2b2f2a:s=1080x1920:d=3,format=yuv420p" \
  -f lavfi -i "sine=frequency=220:duration=3" \
  -vf "drawtext=text='DZM TEST':fontcolor=white:fontsize=96:x=(w-text_w)/2:y=(h-text_h)/2" \
  -r 30 -c:v libx264 -preset veryfast -crf 20 -c:a aac -b:a 192k -shortest "$OUT"
ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate -show_entries format=duration -of compact "$OUT"
