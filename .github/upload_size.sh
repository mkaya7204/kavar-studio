#!/usr/bin/env bash
# upload.mp4 next to every Reel of today: Business Suite in the browser takes at most 10 MB.
# Used by produce.yml after the morning stage (the 07:30 guide Reel, D-40) and after the whole day.
for IN in output/reels/$(date +%F)_*/final_video.mp4; do
  [ -f "$IN" ] || continue
  OUT="$(dirname "$IN")/upload.mp4"
  [ -f "$OUT" ] && [ "$OUT" -nt "$IN" ] && continue  # already made after the morning stage
  if [ "$(stat -c %s "$IN")" -le 9500000 ]; then cp "$IN" "$OUT"; continue; fi
  D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$IN")
  V=$(python3 -c "print(int(9.0*8*1024/$D - 128))")
  ffmpeg -y -loglevel error -i "$IN" -c:v libx264 -preset slow -b:v ${V}k -pass 1 -an -f mp4 /dev/null
  ffmpeg -y -loglevel error -i "$IN" -c:v libx264 -preset slow -b:v ${V}k -pass 2 -pix_fmt yuv420p \
    -c:a aac -b:a 128k -movflags +faststart "$OUT"
  ls -la "$IN" "$OUT"
done
