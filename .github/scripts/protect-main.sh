#!/usr/bin/env bash
# Require one approving review before anything merges into the default branch.
#
# Creates (or updates, by name) a repository ruleset through the GitHub API:
#   * a pull request is required, with at least one approving review; a new
#     push dismisses earlier approvals;
#   * no force pushes and no deletion of the branch;
#   * repository admins (the owner) may bypass the review, only by merging a
#     pull request, never by pushing directly.
# Rulesets on a private repository need GitHub Pro (or Team); on the free plan
# the API answers 403 and this script says so.
#
# Usage: .github/scripts/protect-main.sh [--dry-run] [OWNER/REPO]
set -euo pipefail

dry_run=0
if [ "${1:-}" = "--dry-run" ]; then dry_run=1; shift; fi
repo="${1:-$(gh repo view --json nameWithOwner --jq .nameWithOwner)}"
name="main: one approving review"

body=$(cat <<'JSON'
{
  "name": "main: one approving review",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "bypass_actors": [
    { "actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "pull_request" }
  ],
  "rules": [
    { "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 1,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false } },
    { "type": "non_fast_forward" },
    { "type": "deletion" }
  ]
}
JSON
)

if [ "$dry_run" = 1 ]; then
  echo "would apply to $repo:"
  echo "$body"
  exit 0
fi

fail() {
  case "$1" in
    *"Upgrade to GitHub Pro"*)
      echo "GitHub refused: rulesets on a private repository need GitHub Pro or Team." >&2
      echo "Upgrade the account (or make $repo public), then run this script again." >&2 ;;
    *) echo "$1" >&2 ;;
  esac
  exit 1
}

if ! existing=$(gh api "repos/$repo/rulesets" --jq ".[] | select(.name == \"$name\") | .id" 2>&1); then
  fail "$existing"
fi

if [ -n "$existing" ]; then
  out=$(echo "$body" | gh api -X PUT "repos/$repo/rulesets/$existing" --input - 2>&1) || fail "$out"
  echo "updated ruleset $existing on $repo"
else
  out=$(echo "$body" | gh api -X POST "repos/$repo/rulesets" --input - 2>&1) || fail "$out"
  echo "created ruleset on $repo"
fi
gh api "repos/$repo/rulesets" --jq '.[] | "  \(.id)  \(.name)  (\(.enforcement))"'
