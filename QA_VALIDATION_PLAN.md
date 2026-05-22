# QA Validation Plan — Real Spotify + Chartmetric Integration

Purpose: verify the LOUDmusic Audio Analysis MVP works after replacing demo Spotify results with a real server-side `POST /api/analyze-spotify` integration that calls Spotify + Chartmetric only and returns a clean LOUDmusic campaign analysis.

## Scope

- In scope: Spotify track URL flow, backend API behavior, Spotify metadata lookup, Chartmetric enrichment, frontend rendering, secrets handling, error states, regression checks for current static MVP behavior.
- Out of scope for this MVP gate: direct Instagram/Meta, TikTok, YouTube, Bandsintown, Soundcharts, SocialScraper, or any non-Spotify/non-Chartmetric provider.

## QA prerequisites

- Test environment deployed with real backend enabled.
- Server-side env vars configured only on backend/API host:
  - `SPOTIFY_CLIENT_ID`
  - `SPOTIFY_CLIENT_SECRET`
  - `CHARTMETRIC_REFRESH_TOKEN`
- At least 5 approved test Spotify track URLs:
  - Major-label/global artist.
  - Independent/medium artist.
  - Small/emerging artist.
  - Track with multiple artists/features.
  - Track/artist expected to have sparse Chartmetric data.
- Browser devtools access and API/log access for QA evidence.

## Smoke tests

- Page loads successfully in a clean browser session.
- Spotify tab is visible and accepts a Spotify track URL.
- Submitting a valid Spotify track calls `POST /api/analyze-spotify` exactly once.
- Response renders a non-demo result with:
  - Real track title.
  - Real artist name(s).
  - Spotify track ID/external reference.
  - Summary.
  - Tags.
  - Scores in the expected UI range.
  - Campaign recommendations.
  - Spotify enrichment true.
  - Chartmetric enrichment true when Chartmetric data was found, or a clearly labeled partial state when not found.
- No `Demo-mode Spotify analysis` copy appears after successful real analysis.
- Network tab shows no direct browser calls to Spotify or Chartmetric APIs.

## API contract tests for `POST /api/analyze-spotify`

For each test, capture request, status, response body, and relevant sanitized logs.

- Valid request:
  - Input: `{ "spotifyUrl": "https://open.spotify.com/track/<id>" }`
  - Expected: `200`, JSON, stable schema matching frontend needs.
- Spotify URI support if intended:
  - Input: `{ "spotifyUrl": "spotify:track:<id>" }`
  - Expected: `200` or documented `400`; behavior must match product decision.
- Invalid URL:
  - Input: non-Spotify URL or malformed string.
  - Expected: `400` with safe user-facing error; no provider calls.
- Missing body/field:
  - Expected: `400` with safe validation error.
- Non-track Spotify URL:
  - Input: album, playlist, artist URL.
  - Expected: `400`; no Chartmetric lookup.
- Unsupported method:
  - `GET /api/analyze-spotify` should return `405` or documented safe response.
- Response schema must not include secrets, raw tokens, provider credentials, or excessive raw provider dumps.

Minimum response fields to verify:

- `source: "spotify"`
- `track.title`
- `track.artist`
- `track.externalId`
- `summary`
- `tags[]`
- `scores.energy`, `scores.danceability`, `scores.mood`, `scores.commercialFit` as numbers from 0-100
- `recommendations[]`
- `enrichment.spotify`
- `enrichment.chartmetric`
- Optional but recommended: `warnings[]` for partial provider data

## End-to-end test cases

- Valid global artist track:
  - Verify accurate Spotify title/artist/album metadata.
  - Verify Chartmetric IDs resolve and audience/social fields influence recommendations.
- Valid independent artist track:
  - Verify no assumptions are made if Chartmetric data is limited.
  - Recommendations should remain actionable and not hallucinate unavailable metrics.
- Multi-artist/featured track:
  - Verify primary artist selection is documented and consistent.
  - Verify displayed artist name is acceptable for campaign context.
- Sparse Chartmetric artist:
  - API succeeds with partial analysis if Spotify succeeds.
  - UI clearly indicates limited Chartmetric enrichment instead of failing silently.
- Repeated submission of same URL:
  - Results remain consistent.
  - No duplicate UI states, stale loaders, or previous result leakage.
- Rapid submit/change URL:
  - Latest submitted URL wins.
  - Loading and error states remain correct.
- Mobile viewport:
  - Spotify form and result cards remain usable at common mobile widths.

## Regression checks

- Static/demo fallback behavior is intentionally removed or gated behind explicit config; it must not mask backend failures in production QA.
- Audio upload tab still renders and validates file selection as before.
- Invalid Spotify URL still shows `Paste a valid Spotify track URL.` or equivalent clear copy.
- Existing visual sections remain present:
  - Hero/status copy.
  - Analyzer tabs.
  - Score grid.
  - Tag list.
  - Campaign recommendations.
- `npm run test`, `npm run typecheck`, and `npm run build` pass before QA signoff.
- Existing parser/unit tests still pass; add/update tests for any new URL formats accepted by the backend.

## Failure-mode tests

- Spotify auth failure or expired credentials:
  - Expected: safe `502`/`503` style response, no secret exposure, clear retry/support message.
- Spotify track not found/private/region unavailable:
  - Expected: safe `404` or provider-mapped error with user-facing explanation.
- Chartmetric refresh token failure:
  - Expected: Spotify data may return only if product allows partials; response must mark Chartmetric unavailable.
- Chartmetric artist resolution returns no match:
  - Expected: partial analysis with `enrichment.chartmetric=false` and warning.
- Chartmetric timeout/rate limit:
  - Expected: bounded timeout, retry/backoff if implemented, safe partial/failure response, UI exits loading state.
- Provider returns malformed/incomplete data:
  - Expected: validation catches it; frontend does not crash.
- Backend env vars missing:
  - Expected: startup/config health failure or safe API error; never falls back to fake success in production.
- Network interruption from browser:
  - Expected: UI shows recoverable error and allows retry.
- CORS/config issue:
  - Expected: request succeeds from deployed frontend origin only; blocked origins cannot use the API if API is public.

## Security and privacy checks

- Browser bundle contains no `SPOTIFY_CLIENT_SECRET`, `CHARTMETRIC_REFRESH_TOKEN`, access tokens, or provider API keys.
- Devtools network shows frontend calls only the LOUDmusic backend endpoint, not Spotify/Chartmetric directly.
- API logs redact tokens, authorization headers, refresh tokens, and raw secrets.
- Error responses do not expose stack traces, provider tokens, internal URLs, or raw credential errors.
- Backend calls only Spotify and Chartmetric for this MVP.

## Performance checks

- Successful analysis completes within an agreed MVP threshold, recommended gate: p95 under 10 seconds for normal tracks.
- Provider timeout behavior is bounded, recommended gate: user receives a safe result/error within 15 seconds.
- UI loading state appears immediately and always clears on success or failure.
- Repeated requests do not trigger obvious memory leaks, browser console errors, or runaway provider calls.

## Evidence QA must return

For each test run, QA should attach:

- Environment tested: URL, branch/commit, backend version, date/time.
- Test data: Spotify URLs used and expected scenario labels.
- Browser/device matrix used.
- Screenshots or short screen recordings for:
  - Successful real analysis.
  - Partial Chartmetric analysis.
  - Invalid URL error.
  - Provider failure/error state.
- Network evidence:
  - `POST /api/analyze-spotify` request/response status and sanitized JSON.
  - Proof no direct Spotify/Chartmetric browser calls occurred.
- Backend evidence:
  - Sanitized logs showing Spotify lookup, Chartmetric lookup, and final response path.
  - Provider error logs for failure-mode tests, with secrets redacted.
- Automated evidence:
  - Output from `npm run test`.
  - Output from `npm run typecheck`.
  - Output from `npm run build`.
- Defect list with severity, reproduction steps, expected vs actual, and links to evidence.

## Acceptance gates

Do not approve release unless all gates pass:

- Functional gate: all smoke tests pass on deployed environment.
- Data gate: at least 4 of 5 approved valid Spotify tracks return accurate Spotify metadata; Chartmetric enrichment succeeds or degrades explicitly according to scenario.
- UX gate: frontend never displays stale demo success for failed real backend calls.
- Error gate: invalid inputs and provider failures show safe, actionable errors and clear loading states.
- Security gate: no secrets/tokens in frontend bundle, network responses, browser console, or logs supplied to QA.
- Provider gate: backend uses Spotify + Chartmetric only for MVP enrichment.
- Regression gate: current UI flow remains usable; automated test/typecheck/build commands pass.
- Evidence gate: QA returns the required screenshots, sanitized API/log samples, and automated command outputs.

## Recommended release decision rubric

- Pass: all acceptance gates pass; only minor cosmetic issues remain.
- Conditional pass: one non-blocking defect with owner and fix date; no data, security, or backend integration risk.
- Fail/block: any secret exposure, fake/demo success in production path, broken valid Spotify analysis, unhandled provider failure, or missing required QA evidence.
