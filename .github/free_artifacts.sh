#!/usr/bin/env bash
# D-49 (10-24): GitHub's artifact storage was full and run 40057675759 lost a whole day (3 ready posts, one
# voiced Reel): retention-days only applies to new uploads, the old archives stayed. Every uploading workflow
# runs this first: archives older than KEEP_HOURS and fallback releases (deliver.sh) older than 3 days go.
# Needs GH_TOKEN and `permissions: actions: write` (+ contents: write for the releases). Never fails the run.
KEEP_HOURS=${KEEP_HOURS:-48}  # dry runs keep an approved silent Reel 2 days for voice.yml (D-46)
CUTOFF=$(date -u -d "-${KEEP_HOURS} hours" +%Y-%m-%dT%H:%M:%SZ)
gh api --paginate "repos/$GITHUB_REPOSITORY/actions/artifacts?per_page=100" \
  --jq ".artifacts[] | select(.created_at < \"$CUTOFF\") | .id" 2>/dev/null |
while read -r id; do
  gh api -X DELETE "repos/$GITHUB_REPOSITORY/actions/artifacts/$id" >/dev/null 2>&1 && echo "deleted artifact $id"
done
OLD=$(date -u -d "-3 days" +%Y-%m-%dT%H:%M:%SZ)
gh release list --limit 100 --json tagName,createdAt \
  --jq ".[] | select((.tagName | startswith(\"out-\")) and .createdAt < \"$OLD\") | .tagName" 2>/dev/null |
while read -r tag; do
  gh release delete "$tag" --yes --cleanup-tag >/dev/null 2>&1 && echo "deleted release $tag"
done
gh api "repos/$GITHUB_REPOSITORY/actions/artifacts?per_page=100" \
  --jq '"artifacts kept: \(.total_count), \(((([.artifacts[].size_in_bytes] | add) // 0) / 1048576) | floor) MB"' || true
exit 0
