# StudyReel — Android Sideload (PWA + Capacitor)

This covers **phone install** (not car Android Auto — StudyReel is not an Auto media app). No Play Store needed.

## Option A — PWA (30 sec, recommended for demo)
1. Open `http://<your-lan-ip>:8100/deck` on Android Chrome (not `127.0.0.1` — use `ip addr` on laptop).
2. Chrome menu → **Add to Home screen** / **Install app**.
3. App appears like native, standalone, offline cached via `sw.js` (deck/cabinet/slides cached, API stale-while-revalidate).
- Requires `manifest.webmanifest` + `sw.js` already shipped at `/static/`.
- No APK file, but fastest and sideload-like.

## Option B — Capacitor APK (true sideload, 1h)
**Prereqs:** Node 18+, Android Studio + SDK + `ANDROID_SDK_ROOT`, `adb`.

```bash
npm i -g @capacitor/cli
npm init -y # if no package.json
npm i @capacitor/core @capacitor/android
npx cap init StudyReel ai.studyreel.app --web-dir=instaclone
# Edit capacitor.config.json: server.url = "http://<your-lan-ip>:8100" (emulator uses 10.0.2.2:8100)
npx cap add android
npx cap copy
npx cap sync
cd android && ./gradlew assembleDebug
# APK at android/app/build/outputs/apk/debug/app-debug.apk
```

**Install on phone:**
- Phone: Settings → Security → **Install unknown apps** → allow Chrome/Files.
- `adb install android/app/build/outputs/apk/debug/app-debug.apk`
- Or send APK via Drive/email → open on phone → Install.

**LAN vs bundled:**
- Dev: `server.url` points to laptop LAN IP (phone + laptop same WiFi). Needs `android:usesCleartextTraffic="true"` + `network_security_config.xml` for `http://<lan-ip>:8100` (Capacitor adds by default if `cleartext:true`).
- Offline bundle: `npx cap copy` bundles `instaclone/deck.html` etc into `android/app/src/main/assets/public` — but API `http://127.0.0.1:8000/api/v1/*` still needs network. For offline demo, pre-seed `posts.json` + slides via `seed/seed_insta.py` before `cap copy`.

**Troubleshoot:**
- `net::ERR_CLEARTEXT_NOT_PERMITTED` → ensure `cleartext:true` and `androidScheme:http`.
- `ERR_CONNECTION_REFUSED` on phone → use LAN IP, not `127.0.0.1` (phone’s localhost ≠ laptop).
- `INSTALL_FAILED_UPDATE_INCOMPATIBLE` → `adb uninstall ai.studyreel.app` first.

## How post lands on *your* phone (per-user, after account)
1. Create account on Deck sheet: Name + College dropdown (vtu_belgaum/bmsce/rvce/pes_university/msrit/dsce/other) + Mail → `POST /api/v1/users` → `uuid` stored as `sr_user_real_id`, old `anon-xxxx` cards migrated via `POST /api/v1/users/migrate`.
2. Upload PDF in Dashboard → Generate → Review (edit back_header/back_body/exam_weight) → Render → auto-publish → `POST /api/v2/publish` copies PNGs to `instaclone/data/slides/{post_id}/` + `posts.json` global + `carousels` row.
3. Deck `GET /api/v1/shelves` per `X-User-Id` shows fill `mastered/total`, `GET /api/v1/deck?shelf=ID` shows your unfiled+review cards. Filing `POST /api/v1/file {post_id,slide_index,status}` updates **your** `user_card_states` only — post is sent only to you, global feed `/feed_legacy` stays global for discovery but Deck/Cabinet is per-user.
