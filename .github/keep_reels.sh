#!/usr/bin/env bash
# D-80 / COMMITMENTS #27 (user 11-15 "Evet"): an approved Reel that is not posted must never vanish. Run archives
# expire in 2-3 days (11-14: the reserve's Skillbox and ElevenLabs Reels could no longer be voiced, #20), so every
# Reel of the run that voice.yml could voice later (its <reel>/_voice kit) is copied, without its videos, to the
# release "kept-reels", which never expires. voice.yml reads it there when the run's archive is gone.
# Usage: keep_reels.sh <reel folder>...
set -e
TAG="kept-reels"
gh release view "$TAG" >/dev/null 2>&1 ||
  gh release create "$TAG" --target "$GITHUB_SHA" --prerelease --title "$TAG" \
    --notes "Approved Reels' silent parts (<reel>/_voice and their files), kept for good so voice.yml can voice them any day (D-80)."
for d in "$@"; do
  [ -f "$d/_voice/capture.json" ] || continue
  name=$(basename "$d")
  tar -czf "keep-$name.tgz" --exclude='*.mp4' "$d"
  gh release upload "$TAG" "keep-$name.tgz" --clobber
  echo "kept for good: $name (release $TAG)"
done
