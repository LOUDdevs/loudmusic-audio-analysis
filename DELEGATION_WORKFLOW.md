# Delegation Workflow — LOUDmusic Audio Analysis MVP

Purpose: make sure production work is implemented by the dev lane and independently verified by QA before Derrick reviews or ships it.

## Core rule

Cleo orchestrates. Dev implements. QA verifies. No agent reviews its own work.

## Roles

- **Cleo / Orchestrator**
  - Owns scope, sequencing, and reporting to Derrick.
  - Creates implementation tickets and QA gates.
  - Does not silently ship production code without dev + QA review.

- **Steve / Engineering Lead**
  - Owns technical implementation plan and final engineering decisions.
  - Delegates implementation tasks to dev specialists.
  - Ensures secrets remain server-side.

- **Dev Specialists**
  - Implement focused tasks using TDD.
  - Return exact files changed, tests run, and blockers.

- **QA / Sentinel**
  - Validates the deployed app independently.
  - Uses `QA_VALIDATION_PLAN.md` as the release gate.
  - Rejects any build that exposes secrets, fakes production results, or fails real Spotify analysis.

## Required handoff sequence

1. **Orchestrator intake**
   - Confirm product scope.
   - For this phase: Spotify + Chartmetric only.
   - Explicitly exclude SocialScraper, Soundcharts, direct Instagram/Meta, and Bandsintown.

2. **Engineering delegation**
   - Steve owns the implementation plan.
   - Dev team implements:
     - Backend hosting decision.
     - `POST /api/analyze-spotify`.
     - Spotify client credentials flow.
     - Chartmetric token flow and artist/track resolution.
     - Aggregated `AnalysisResult` response.
     - Frontend wiring from static demo to real backend.

3. **Engineering review gates**
   - Spec compliance review: does implementation match the task?
   - Code quality/security review: is it safe, tested, and maintainable?
   - Automated checks must pass:
     - `npm run test`
     - `npm run typecheck`
     - `npm run build`

4. **QA delegation**
   - QA validates the deployed environment, not just local code.
   - QA must use `QA_VALIDATION_PLAN.md`.
   - QA must return evidence: screenshots, sanitized API responses/logs, command outputs, defect list.

5. **Release decision**
   - Cleo reports status to Derrick only after dev + QA gates.
   - Release can be approved only if all acceptance gates pass.

## Current production implementation tasks

### Task 1 — Backend architecture

Owner: Steve / Engineering Lead

Acceptance criteria:

- Choose server-capable hosting because GitHub Pages cannot run API routes.
- Either:
  - keep GitHub Pages frontend and deploy separate backend, or
  - move the full Next.js app to server-capable hosting.
- Define production API contract for:

```text
POST /api/analyze-spotify
```

- Keep all private credentials server-side.

### Task 2 — Spotify integration

Owner: Dev Specialist

Acceptance criteria:

- Accept valid Spotify track URLs.
- Reject invalid/non-track URLs with safe `400` errors.
- Fetch real track, artist, album, release date, popularity, and external IDs.
- Use client credentials flow with token caching/refresh behavior.
- Unit tests cover success and failure cases.

### Task 3 — Chartmetric integration

Owner: Dev Specialist

Acceptance criteria:

- Use `CHARTMETRIC_REFRESH_TOKEN` server-side.
- Resolve Chartmetric artist/track IDs from Spotify data where possible.
- Fetch artist URLs, audience stats, platform/social momentum, and top content from Chartmetric only.
- Gracefully degrade to Spotify-only when Chartmetric has no match or fails.
- No SocialScraper, Soundcharts, direct Instagram/Meta, or Bandsintown calls.

### Task 4 — Aggregation + frontend wiring

Owner: Dev Specialist

Acceptance criteria:

- Replace demo Spotify timeout flow with a real backend call.
- Production failures must not silently display fake demo success.
- UI clearly shows:
  - full Spotify + Chartmetric result,
  - Spotify-only partial result,
  - safe error state.
- Existing audio upload tab remains usable.

### Task 5 — QA release gate

Owner: QA / Sentinel

Acceptance criteria:

- Execute `QA_VALIDATION_PLAN.md` against deployed environment.
- Verify real Spotify metadata appears for valid tracks.
- Verify browser does not call Spotify or Chartmetric directly.
- Verify secrets are absent from frontend bundle, network responses, and logs.
- Return release verdict: Pass, Conditional Pass, or Fail/Block.

## Default delegation prompt template

Use this shape for future dev tasks:

```text
Goal: [specific implementation task]

Context:
- Repo: LOUDdevs/loudmusic-audio-analysis
- Workspace: /home/derrick/workspace/loudmusic-audio-analysis
- Product scope: Spotify + Chartmetric only
- Do not use SocialScraper, Soundcharts, direct Instagram/Meta, or Bandsintown
- Follow TDD: failing test first, minimal implementation, full checks

Acceptance criteria:
- [explicit checklist]

Required output:
- Files changed
- Tests run and results
- Risks/blockers
- Whether ready for independent QA
```

## Default QA prompt template

```text
Goal: Independently validate the deployed LOUDmusic Audio Analysis app after backend integration.

Context:
- Use QA_VALIDATION_PLAN.md
- Validate deployed app, not just local code
- Confirm real Spotify metadata and Chartmetric behavior
- Confirm no secrets are exposed

Required output:
- Test environment and commit
- Test Spotify URLs/scenarios
- Pass/fail by acceptance gate
- Screenshots/API evidence summary
- Defects with severity and repro steps
- Release verdict
```
