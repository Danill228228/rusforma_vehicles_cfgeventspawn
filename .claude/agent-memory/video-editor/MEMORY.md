# Память агента video-editor

- 2026-11-20: проверенная команда-образец: ffmpeg -f lavfi -i color=…:s=1080x1920 … -vf drawtext=… -c:v libx264 -crf 20 -c:a aac -b:a 192k — работает. Для 9:16 задавать -r 30 явно (lavfi по умолчанию 25 fps).
