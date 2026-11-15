# Still Waters Daily – instructions for Claude

Owner: Hans (speaks Dutch – always write to him in Dutch). Everything published is in **English**.
Channel: YouTube/Instagram/TikTok **@stillwatersdailyword** (YouTube channel ID UC4qn82I1neQTQ3t7-JyfX9Q, TikTok `still.waters.dail4`).
Interdenominational Christian channel for adult believers: daily KJV Bible verses and calm encouragement. Config: `config/channel.json`.

This project is completely separate from Whispers of the Soul and Toet Toet and Friends. Never touch their repos,
Metricool brands (7965951, 7587077) or posts. Our Metricool brand: **7823324**.

## Hard rules
- **Pause switch:** if `config/channel.json` has `"paused": true`, do nothing except tell Hans in one Dutch line that production is paused.
- Before scheduling, Metricool getBrandSettings must show brand 7823324 with youtubeData `UC4qn82I1neQTQ3t7-JyfX9Q`,
  instagramData `stillwatersdailyword`, tiktokData `still.waters.dail4`. YouTube mismatch → schedule nothing, tell Hans.
  Instagram/TikTok mismatch → schedule the rest (`--networks`), tell Hans.
- **Scripture is never typed by hand.** Scripts only hold a reference (`"ref": "Psalm 23:1"`); the text always comes verbatim from
  `data/kjv.json` (King James Version, public domain). No other translations (copyright).
- Never publish immediately; always schedule ahead (rolling buffer `schedule.bufferDays` = 8 days).
- Never schedule a video that failed textcheck, render, QC or the visual contact-sheet check. A gap is better than a bad video.
- No duplicates: before scheduling check `state/posts.json` AND Metricool getScheduledPosts for that slot. Record every Metricool
  post id in `state/posts.json` immediately after creating it; on a retry look the post up first instead of creating it again.
- Never delete or change posts that are already live. Keys/tokens never go into this repo.

## Content rules (Hans's brief)
- Calm, warm, biblical, for adult believers worldwide. Support and comfort; the full range of church and faith themes, following the
  church year. Interdenominational: nothing divisive (no denominations, no politics, no end-times speculation), never a depiction of
  God the Father, no prosperity promises, no medical promises, no fear or pressure.
- Follow `content/calendar.json` (approved 3-month plan, weeks 4–13 = 23 Nov 2026 – 31 Jan 2027): the Verse of the Day uses the
  day's `verseRef`, the Evening Encouragement uses `eveningRef` + `eveningTheme`. The loop verse is your choice: ONE short KJV verse
  (≤ 32 words) on the `dayTheme`, not used in the last 45 days (see `swd.plan` recentRefs).
- Hooks (heading on screen, ≤ 30 chars, normal case – the renderer capitalises): a feeling or a question, e.g. "Worried about tomorrow?",
  "If you feel lonely tonight", "He holds your hand". Vary them; never repeat a hook within 60 days.
- Evening lines: 2–3 short original lines (≤ 34 chars each, each ending in . ! or ?), gentle, second person, no clichés, e.g.
  "No room is too empty." / "No place is too far." / "His hand is already there."
- Captions are built automatically (`swd.postdata`) in the channel's fixed format: verse = "Verse of the Day — <ref> 🕊️ / <line> /
  Type "Amen" if you receive this. 🙏 / Follow for a daily word of peace."; evening = lines + quoted verse; loop = "<line> 🕊️ <ref> / <share>".
  `line` (verse/loop) is one short sentence of your own; `share` (loop) is a kind invitation like "Send this to someone who needs to
  know they are loved. 🤍" – never chain-letter pressure.
- Paintings: on about 2 Verse of the Day posts per week in Advent/Christmas (weeks 5–8) and Epiphany, use `"scene": "art:<id>"` from
  `art/met/catalog.json` where the painting fits the day (see `useFor`). Only those paintings. Otherwise leave `scene` empty
  (the renderer picks a calm landscape) or choose meadow / dawnlake / wheat / sunset; evening posts use moonlake.
- Every video already ends with the SUBSCRIBE button and voice-over (voice bm_george, reference spoken first) – do not change that.

## Script file
`content/scripts/<date>-<slot>-<slug>.json` with slot `verse` | `loop` | `evening`:
- verse: `{"id","date","slot","week","theme","hook","ref","title","tiktokTitle","line","scene"?}`
- loop: same + `"share"`
- evening: `{"id","date","slot","week","theme","hook","lines":[2-3],"ref","title","tiktokTitle","scene":"moonlake"}`
`date` = calendar day. Publication (Europe/Amsterdam): verse 13:00 same day, loop 18:00 same day, evening 02:00 the NEXT day.
`title` (YouTube, ≤ 80 chars): the key phrase of the verse in title case, e.g. "My Grace Is Sufficient for Thee".
`tiktokTitle`: short, with 🕊️ (day) or 🌙 (evening).
After scheduling, append one line to `content/archive.jsonl`: `{"date","slot","ref","hook","title","id"}` (memory against repetition).

## Pipeline
- `python3 -m swd.plan` → missing date/slot items for the buffer, with calendar refs and recent refs/hooks/titles to avoid.
- `python3 -m swd.textcheck content/scripts/<id>.json` → must print OK. Rewrite until OK – never weaken the checker.
- Push to main → GitHub Actions `.github/workflows/render.yml` renders each new script (Kokoro bm_george, generative piano, procedural
  moving landscapes or framed public-domain painting, read-along text, SUBSCRIBE end card, thumbnail), runs `swd.qc`, makes a contact
  sheet and publishes a release with tag = script id:
  `https://github.com/Hansieman-SM/still-waters-daily/releases/download/<id>/<id>.mp4` (+ `_thumb.jpg`, `.meta.json`, `.qc.json`, `_sheet.jpg`).
  Failed items go to prereleases `render-logs-<shard>`.
- Local render: `bash tools/get_models.sh; python3 -m swd.render content/scripts/<id>.json out/<id>`.
- Visual check: download `<id>_sheet.jpg` and LOOK at it: text readable and inside the frame, nothing overlapping, the scene moving,
  no artefacts, SUBSCRIBE button clean at the end. Reject and fix otherwise.
- `python3 -m swd.postdata <id>` → TWO Metricool posts per video (same structure as all posts since 2 Nov 2026):
  (1) Instagram Reel + TikTok with `videoThumbnailUrl`, (2) YouTube Short alone (no thumbnail – YouTube rejects custom Short thumbnails
  on this channel; a YouTube "ERROR" with publicUrl and detailedStatus "published with some warnings: Could not upload video thumbnail"
  IS published – never retry it). Call Metricool createScheduledPost with blogId, date and info for each.

## Daily run (scheduled task "Still Waters dagelijkse productie")
1. `git pull`. Pause switch. getBrandSettings: brand + network check.
2. Failures: getScheduledPosts (brand 7823324, past 2 days + next 9, extendedRange; split the range if the result is too big).
   Provider ERROR without publicUrl, or PENDING > 30 min after its time: fix if possible (updateScheduledPost to ≥ 15 min ahead, same
   content), max 2 attempts per post (tracked in state). MIXED status (one network published, another failed): never update that post;
   create ONE new post with only the failed network(s), same media/caption, ≥ 15 min ahead, after checking it does not exist yet.
   Needs Hans (disconnected account, permissions, limits) → tell him exactly what to do.
3. `swd.plan` → write the missing scripts (normally 3 per day: day +8), textcheck until OK, commit + push, wait for the Actions run
   (`gh` is not authenticated in scheduled sessions: poll `https://api.github.com/repos/Hansieman-SM/still-waters-daily/releases/tags/<id>`
   with curl, max ~25 min). One retry via a small fix + push. Still failing → do not schedule, tell Hans.
4. QC json pass + sheet looked at → schedule both posts → save ids in state → append to archive → commit + push.
5. Stock check: fewer than 15 future videos scheduled → catch up (up to 9 scripts in one run).
5b. Long video: if the next Sunday long video (or the Christmas Eve extra) within 8 days is not scheduled yet, write it, longcheck, push,
   wait for render-long (poll the release API, max ~45 min), check QC + sheet, schedule it, record it in state.
6. Calendar check: if `swd.plan` shows NO CALENDAR ENTRY within 14 days, write the next weeks in the same style (Lent from Ash Wednesday
   10 Feb 2027, Easter 28 Mar 2027) into `content/calendar.json` and tell Hans what you planned.
7. Report: all fine → end with one Dutch line `Still Waters: N video's ingepland t/m <datum>, geen problemen.` (no push).
   Anything failed or needs Hans → SendUserMessage + PushNotification in Dutch: what failed, what you fixed, what he must do.

## Weekly long Sunday video (16:9, built 15 Nov 2026 – Hans: "ja natuurlijk een lange video")
- One per week, from `content/calendar.json` → `sundayLongVideo[week]` (e.g. week 5 = Psalm 46). Script
  `content/long/<calendar Sunday>-long-<slug>.json`: `{"id","date","kind":"scripture","week","passage","title","subtitle","minutes":30,
  "scene","description","hashtags"?,"tags"?}`. `passage` = a whole chapter ("Psalm 46") or a range of 3–30 verses ("Isaiah 9:2-7");
  when the calendar names a long chapter, pick the best-known 5–25 verse section. Week 8 has an EXTRA one: Luke 2:1-20 for Christmas Eve
  (date 2026-12-23 so it goes live 24 Dec 03:00) besides John 1:1-14 on the Sunday.
- `title` (≤ 100): "<Passage> | <key phrase> | 30 Minutes of Peace | Bible Verses for Sleep"-style; `subtitle` = the key phrase.
  Scenes rotate: moonlake, dawnlake, meadow, sunset, wheat (night scenes suit sleep).
- `python3 -m swd.longcheck` → OK. Push → `.github/workflows/render-long.yml` renders with `swd.long` (~15 min): intro card, the passage
  read by George several times (the renderer picks 3–8 readings so each verse rests ~20–35 s in the quiet passes), quiet passes,
  subscribe card, soft piano, chapters in meta. QC (long branch) + contact sheet in the release (tag = id).
- LOOK at `<id>_sheet.jpg` and `<id>_thumb.jpg`, then `python3 -m swd.postdata <id>` → ONE Metricool post: YouTube video (not a Short)
  with custom thumbnail, Monday 03:00 Amsterdam (the day after `date`). Record the Metricool id in `state/posts.json` (`"slot": "long"`).
- Keep the next long video produced and scheduled at least 3 days before it goes live (daily run step 5b).

## State
`state/posts.json`: `{"posts": {"<id>": {"date","slot","status": "scripted|rendered|scheduled|published|failed","release",
"metricool": {"social": <id>, "youtube": <id>},"publishAt","attempts"}}}`

## Status log
- 2 – 22 Nov 2026: produced by hand in chat sessions (videos in `videos/2026-11/`, 3 posts a day: verse 13:00, loop 18:00, evening 02:00;
  a 30-min Psalm 23 long video on 9 Nov). Refs used are in `content/archive.jsonl`.
- 15 Nov 2026: automated pipeline built (Hans: "alles hetzelfde laten draaien" as Whispers of the Soul). First automatic items: 23 Nov.
- 15 Nov 2026: weekly long Sunday video automated (swd/long.py). First: Psalm 121 (Mon 23 Nov 03:00), Isaiah 40:1-11 (Mon 30 Nov 03:00).
- Facebook page is not connected yet (see the startplan doc); when Hans connects it to brand 7823324, add Facebook (Reel) to the social post.
