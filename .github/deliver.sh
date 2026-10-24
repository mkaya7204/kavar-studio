#!/usr/bin/env bash
# D-49 (10-24): when an archive can't be uploaded as an artifact (storage quota: run 40057675759 lost the day),
# it goes to a release of this run instead (tag out-<run id>; release files don't count toward the artifact
# quota). `daily.py fetch` looks there when the artifact is missing. Usage: deliver.sh <file.tgz>...
set -e
TAG="out-$GITHUB_RUN_ID"
gh release view "$TAG" >/dev/null 2>&1 ||
  gh release create "$TAG" --target "$GITHUB_SHA" --prerelease --title "$TAG" \
    --notes "Cloud output of run $GITHUB_RUN_ID (artifact upload failed); daily.py fetch reads it."
gh release upload "$TAG" "$@" --clobber
echo "delivered as release $TAG: $*"
