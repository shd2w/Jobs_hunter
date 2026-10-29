# All-platform post sources and automatic vacancy intake

Version 0.3.4d adds official read adapters for **LinkedIn organization posts, X user timelines, Reddit subreddit submissions, Telegram public-channel bot updates and Discord authorized guild-channel messages**. HN hiring-thread comments, approved RSS/Atom and authorized supplied posts share the same processing pipeline. **Forums use permitted feeds or authorized exports**, not a universal forum HTML scraper.

“All platforms” means these supported source types. It does not mean access to every account/channel on the internet or automatic membership enumeration. No source IDs, credentials, access approval or paid API consent have been supplied by this delivery. The new official adapters are **fixture-validated, not live-verified**. They appear as `setup_required` until local configuration is present, then `configured_not_live_verified`; neither state proves actual provider approval.

## What happens to posts

1. A manually requested approved-source scan retrieves one bounded page. Alternatively paste a permitted post, upload an RSS file, or run `posts-process` on an authorized JSON export.
2. Local deterministic rules distinguish possible vacancies, job-seeker posts, non-vacancies, negated/closed/test posts and ambiguous content. No external model or paid AI is called.
3. **Automatic addition** requires source-backed role, employer and application URL plus a source permalink. No author is assumed to be the employer. Explicit labels in English/German/Arabic and a narrow English hiring sentence are supported. This is conservative extraction, not comprehensive multilingual understanding or a measured high-accuracy classifier.
4. Incomplete, multiple-role/ambiguous, suspicious/fee-related, shortened-link and non-text/unavailable posts stay in review. Non-job/job-seeker/closed/negated posts are skipped. Images, PDFs, voice/video and embeds are not OCR'd or silently interpreted as jobs. Nothing is invented to fill missing data.
5. Clear candidates enter Opportunities and receive deterministic matching for the selected configured profile. If no profile exists, intake reports `profile_required`; it does not fabricate a match. Automatic discovery is **not human verification, employer legitimacy verification or a legal eligibility judgment**.
6. Original post body, permalink, field evidence and rule decision are preserved. Automatic provenance says `human_confirmed: false`. An explicit later human review can upgrade that record. Existing authoritative fields, aliases, notes/status and dismissed decisions are preserved. Exact canonical URLs deduplicate; conflicting role/employer at an existing URL remains for review rather than overwriting it.

Default processing is `auto` for approved post scans, dashboard post/feed processing and the new `posts-process` command. To require manual review instead, set `JOBHUNTER_POST_MODE=review` before starting the process; restart the dashboard after environment changes. Set it to `auto` to restore automatic handling. Legacy `posts-import` and local CLI `feed-import` retain their review-only behavior for script compatibility.

## Local configuration — do not put secrets in JSON/source identifiers

Use the activated project's Python environment; no new mandatory packages are required. Put credentials in local environment variables using your approved secret-management method, **not** source IDs, URLs, shared files, screenshots or chat. No token generation, OAuth sign-in, subscriptions or automatic paid requests are performed here. Source setup shows setting **names and presence only**, never values. Explicitly review costs and provider permission before setting an approval flag to `1`.

| Source kind | Registered identifier | Required local settings and real access limitations |
|---|---|---|
| `linkedin` | Numeric organization ID | `JOBHUNTER_LINKEDIN_TOKEN`, `JOBHUNTER_LINKEDIN_VERSION` (supported `YYYYMM` version), `JOBHUNTER_LINKEDIN_ACCESS_APPROVED=1`. Requires approved Posts API access, `r_organization_social` and appropriate organization role. Only PUBLIC/PUBLISHED posts for that exact organization. **Not arbitrary member feeds, LinkedIn Jobs search or all company pages.** |
| `x` | Numeric public user ID | `JOBHUNTER_X_BEARER`, `JOBHUNTER_X_ACCESS_APPROVED=1`, **`JOBHUNTER_X_COST_APPROVED=1`**. Existing app/access entitlement required; API access can be paid. The cost flag is deliberate consent to requests with the user's configured entitlement, not a guarantee of free access. No subscription/purchase here. Replies/reposts excluded. |
| `reddit` | Subreddit name without `r/` | `JOBHUNTER_REDDIT_TOKEN`, descriptive `JOBHUNTER_REDDIT_USER_AGENT`, `JOBHUNTER_REDDIT_API_APPROVED=1`. Approved OAuth/API use required. Read subreddit `new` submissions only; no profiles, comment trees, anonymous/RSS/HTML fallback or deleted/removed text. |
| `telegram` | Literal `channels` | `JOBHUNTER_TELEGRAM_READ_BOT_TOKEN`, `JOBHUNTER_TELEGRAM_CHANNELS` (comma-separated public usernames without `@`), **`JOBHUNTER_TELEGRAM_DEDICATED_BOT=1`**. Use a dedicated bot authorized in those channels, with the platform-required channel permissions. Reads only incoming channel posts/edited channel posts available to that bot and filters to the allowlist. **No historical channel scraping.** |
| `discord` | `guildID-channelID`, both numeric | `JOBHUNTER_DISCORD_BOT_TOKEN`, `JOBHUNTER_DISCORD_ACCESS_APPROVED=1`. Bot needs appropriate authorized guild membership, channel view/history access and message-content permissions/intent. **No user tokens, self-bots, DMs, automatic joining or member-list enumeration.** Blank/non-text/redacted content stays reviewable, not a verified empty vacancy feed. |
| `hn` | Explicit Who-is-hiring thread numeric ID | No secret; approve the specific public hiring thread. At most ten top-level comments per scan. A thread's purpose is not sufficient evidence that every comment is a job. |
| `feed` / forums | Approved public HTTPS RSS/Atom URL | No credentials supported. Feed terms must permit this use. Social feed URLs remain blocked; use their authorized official adapter instead. Arbitrary forum HTML/private URLs are not fetched. |

### Telegram queue warning

This is **not the notification bot**. Do not reuse `TELEGRAM_BOT_TOKEN` or any bot used by another application. `getUpdates` and webhooks are mutually exclusive; this code never deletes/changes webhooks. Updates are retained by Telegram for a limited time (currently up to 24 hours); manual infrequent scans can miss posts. No completeness claim.

Polling with a committed offset acknowledges earlier updates. This is why a **dedicated bot** and explicit flag are required. Acknowledgement only uses the previous committed checkpoint, so a failed new batch can be retried without acknowledging that new batch. Out-of-allowlist updates are intentionally discarded by this dedicated reader. Do not share its queue. Never fix conflicts by automatically removing a webhook or resetting another consumer.

## Register sources and run

In Discovery choose the new source type. The policy displays its setup state, setting names, identifier hint and bounds. Supply the exact authorized source ID, review approval, then save. Configure credentials in the same terminal that launches `python run_local.py serve` and restart a running dashboard. Registration is not an authentication success or an executed scan.

CLI examples use placeholders; do not run `ORG_ID`, `USER_ID`, `SUBREDDIT`, or `GUILD_ID-CHANNEL_ID` literally:

```powershell
python run_local.py source linkedin ORG_ID --approve
python run_local.py source x USER_ID --approve
python run_local.py source reddit SUBREDDIT --approve
python run_local.py source telegram channels --approve
python run_local.py source discord GUILD_ID-CHANNEL_ID --approve
python run_local.py source-health
python run_local.py scan EXACT_SAVED_SOURCE_ID
```

Set global `--db PATH --profile-id ID` **before** the command. The dashboard/CLI-selected profile is used for new automatic matches, not a guessed identity. Batch scans stay bounded to ten distinct sources; they do not silently enumerate all memberships. A conservative **one-hour provider-wide local cooldown** applies to the five new adapters, in addition to provider quotas/Retry-After. More source registrations do not grant more quota; some sources in a batch can therefore report cooldown rather than be scanned. Inspect every batch result. API pages are at most 50 posts; HN is at most ten comments. No periodic/background scheduling is added.

X/Reddit/LinkedIn/Discord resume supplied cursors or bounded chronological indices and return to a fresh first page after exhaustion. Live feeds are mutable; posts can be missed between snapshots or while traversing history. LinkedIn follows only a provider-supplied next index for the same author; absence of a next link is **not proof of complete organizational history**. A 100-page bound (and LinkedIn start-index bound) requires explicit review/reset rather than silent looping. Reset never clears cooldowns/Retry-After. Telegram resumes its dedicated update offset instead of resetting to history.

Source requests use exact documented HTTPS API hosts/paths, DNS-pinned public addressing, certificate verification, no redirects, identity encoding, byte/time bounds and a single GET per API page. Credentials are restricted to that provider's read endpoint. Telegram's token-bearing request path is redacted from HTTP errors. No cookies, browser login, hidden endpoints, arbitrary authenticated URL requests or automatic transport fallback.

Missing setup is rejected **before a provider request or run/cooldown reservation**. Malformed pages do not advance checkpoints. 401/403 pauses registered sources of that provider; 429 also saves its retry gate. Jobs, post provenance, selected-profile matches and source checkpoint/run completion commit atomically. No applications, messages, recruiter outreach or CV changes.

## Supplied exports from any listed platform

An authorized export can be normalized to a JSON array. Required post field: `body`; `origin_url` and explicit role/company/application link evidence are needed for automatic addition. Optional `source_label`, `published`, `title_hint`. Do not copy private conversations or other people's personal details without sufficient rights.

```powershell
python run_local.py --profile-id default posts-process authorized-posts.json --dry-run
python run_local.py --profile-id default posts-process authorized-posts.json --rights-attested
```

Preview does not store posts, jobs or matches. The dashboard offers the same Preview extraction / Process posts workflow. A rejected/uncertain post is not silently promoted. Posts with automatic provenance appear under Accepted and in Opportunities; ambiguous posts remain Pending.

## Documentation grounding

Read endpoint/access behavior was checked against first-party documentation, not inferred from a public page:

- [LinkedIn Posts API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api)
- [X user timelines](https://docs.x.com/x-api/posts/timelines/introduction) and [authentication](https://docs.x.com/x-api/posts/timelines/integrate)
- [Reddit API listings](https://www.reddit.com/dev/api/)
- [Telegram Bot API](https://core.telegram.org/bots/api#getupdates)
- [Discord messages](https://docs.discord.com/developers/resources/message)

The adapter fixtures validate software contracts; they do **not** establish live API compatibility, token scopes, actual membership, provider permission, cost, coverage, classification accuracy or future availability. The prior eight-job Wuzzuf/Naukrigulf browser sample is a separate verified route, not evidence for these new APIs.
