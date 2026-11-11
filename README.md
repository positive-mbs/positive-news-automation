# Positive News Instagram — free starter

## What works
- RSS discovery into `data/candidates.json` (not verification)
- Human verification and approval via `data/approved.json`
- Text-only JPEG slides in `docs/posts/<post_id>/`
- Hosting through GitHub Pages
- Meta Graph API carousel publishing, manually triggered after approval
- Deduplication of published stories and posts

## Prerequisites
1. Public GitHub repository, GitHub Pages enabled with **GitHub Actions** as source.
2. Instagram professional account with Meta Content Publishing API access, suitable Facebook Page/permissions if using Facebook Login.
3. Valid Meta long-lived access token, Instagram professional account ID.
4. Repository Settings → Secrets and variables → Actions: secrets `META_ACCESS_TOKEN`, `IG_USER_ID`; variable `PAGES_BASE_URL` set to `https://YOURUSERNAME.github.io/YOURREPO`.
5. Check Meta's current permission requirements and token expiry/refresh for your login flow. Do not commit tokens.

## Run
1. Edit `config.json` to set your brand and RSS feeds. Confirm the feeds are active and terms permit use of the metadata.
2. Actions → **Discover and render positive news** → Run workflow. It saves `data/candidates.json`.
3. Read each candidate's original article. Independently verify its material claims, publication date, scope, and whether any summary is misleading. Never approve solely from an RSS headline.
4. Edit `data/approved.json` as an array of objects:
```json
[
  {"id":"ID_FROM_CANDIDATES", "verified":true, "rights_checked":true,
   "evidence_url":"https://source.example/independent-evidence",
   "approved_headline":"A short verified fact, not a fabricated headline",
   "approved_summary":"A factual 1–2 sentence summary of what happened."}
]
```
`rights_checked=true` means you have checked that you are writing original short factual summaries rather than copying protected article text. No third-party photographs are used.
5. Commit your approval. Run **Discover and render positive news** again. It renders only when 3 approved, unpublished stories exist.
6. Inspect `docs/posts/...` and `data/ready.json`. Confirm public images are accessible on GitHub Pages (may take a minute).
7. Copy the `post_id` from `data/ready.json` into `data/approved_posts.json` as an array, commit.
8. Actions → **Publish approved carousel** → Run workflow. It publishes once and saves IDs in `data/published.json` and `data/published_posts.json`.

## Important caveats
- The system intentionally does not auto-approve facts. Fully unattended editorial verification is not solved by this free stack.
- The daily workflow is automatic discovery and rendering, not automatic posting without approval.
- Public Pages URLs and repository content are public. Never store personal/private data, passwords or tokens in files.
- GitHub Actions schedules may be delayed or disabled for inactive public repositories.
- GitHub Pages can be unsuitable for large-scale media/CDN use; monitor usage and GitHub terms.
- `publish` makes no automatic retry on the final publish call, but ambiguous failures can still require checking Instagram before re-running.
- Check API version and current Meta app permissions before launch; Meta can change them.
- Free-tier limits, access token maintenance, and feed licensing can interrupt operation.
