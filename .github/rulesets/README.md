# Repository Rulesets

The `*.json` files here are payloads for GitHub's **server-side repository rulesets** (Settings → Rules → Rulesets). They are configuration *records*, not live config: nothing in the repo or CI reads them, and editing a file here changes nothing until it is re-applied. The live rules are stored in GitHub's settings database and enforce at push time on GitHub's side.

## Current rules

| File | Live state | What it enforces |
|---|---|---|
| `require-signed-commits.json` | active (id 17573315) | every commit pushed to the default branch must carry a valid signature from a verified key — unsigned pushes are rejected by GitHub before CI ever runs |

## Applying and exporting

```bash
# Apply a payload as a new ruleset
gh api repos/OWNER/REPO/rulesets --input .github/rulesets/require-signed-commits.json

# Export a live ruleset (to update the record here)
gh api repos/OWNER/REPO/rulesets/<id>

# List live rulesets
gh api repos/OWNER/REPO/rulesets
```

Keep these files in sync with the live rules when configuration changes — they exist so branch protection survives repo recreation and can be replicated onto sibling repos.
