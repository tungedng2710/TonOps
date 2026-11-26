# UI redesign progress

## 2026-11-26 — Restored signed-in project access

Removed the guest Projects and Playground pages, anonymous chat, their API
endpoints and feature tests. Restored routes, redirects, sidebar navigation,
project visibility copy, AGENTS.md and user-facing documentation from `4f07f43`.
All application files match that commit. The existing Public visibility setting
continues to apply to signed-in users in the same company.

- Production and development builds and focused ESLint passed. The builds
  retain the existing markdown import and component style warnings. Both builds
  contain no references to the removed components or API calls.
- Chromium browser checks with API fixtures passed. Signed-out visits to `/`,
  `/projects`, `/public/projects` and `/playground` go to sign-in without project
  or chat requests. Signed-in Projects renders, and the former public routes
  show 404. The authenticated shell suite passed. Login and signup screenshots
  at 1440px and 390px are byte-identical to the pre-feature baseline.
  Results and screenshots are in `/tmp/tonops-guest-rollback-browser/`.
- `git diff --check` passed. Deployment and live API testing were outside this
  rollback. Authenticated Projects remains the next UI review area in the plan.

## 2026-11-03 — P0 authenticated shell, first increment

Implemented desktop navigation labels, a compact rail at widths <=1100px,
restrained neutral surfaces, blue active indicators, and shared shell-only tokens.
The header retains its 64px height and existing breadcrumbs, context tabs, menus,
search and refresh controls. Its profile trigger is now a native keyboard button;
search, resources and profile controls have accessible names. Context tab height
was refined after screenshot review to align with the new header border.

Principal files:

- `clearml-web/src/app/layout/side-nav/side-nav.component.html`
- `clearml-web/src/app/webapp-common/layout/side-navbar/side-navbar.scss`
- `clearml-web/src/app/webapp-common/layout/header/header.component.{html,scss}`
- `clearml-web/src/app/webapp-common/styles/_workspace-shell.scss`
- `clearml-web/scripts/ui-shell-smoke.mjs` (isolated, repeatable browser harness)

This slice changes the existing shell across authenticated routes; `/home` and
`/workers-and-queues/{workers,queues}` are browser checkpoints. No routes,
TypeScript production logic, API calls/contracts, NgRx state, guards, permissions,
feature components, dependencies, global styles, assets, authentication or account
creation files were changed. The user's pre-existing untracked `AGENTS.md` is
untouched.

### Verification

- Baseline and final development builds: **PASS**. Used the installed Angular CLI
  directly; the package scripts also copy the excluded authentication artwork,
  which this slice deliberately avoids. Existing `ngx-markdown-editor`
  `ignored-bare-import` warning remains.
- Focused ESLint for sidebar/header TypeScript and templates: **PASS** before and
  after changes. Existing `.eslintignore` deprecation warning remains.
- `node --check scripts/ui-shell-smoke.mjs` and `git diff --check`: **PASS**.
- Baseline browser harness: **PASS**, with pre-existing header action overflow
  recorded at 390px on the tabbed view.
- Final browser harness: **PASS** after the tab alignment refinement, with no
  unexpected browser runtime errors. All four login/signup screenshots are
  byte-for-byte identical to baseline. Context tabs also remain keyboard-operable
  at 390px. The final shell action area has no document overflow at tested widths.
- Production build: **PASS**. Warnings remain for the markdown import and five
  unchanged stylesheets over the 6kB budget: experiment graphs (7.16kB), Home
  (16.05kB), pipelines (7.97kB), markdown editor (12.55kB), and table (8.37kB).
  There are no shell component style budget warnings.
- Final diff review: **PASS**. No excluded auth/account files, routes, shared
  global styles, API/state logic, dependency files, or backend files changed.

The browser harness uses explicit fixtures and a loopback-only static build
server. It does not contact a live API, submit real operations, override guards,
or alter application routes. It checks:

- All six original sidebar destinations and default/nested dataset/pipeline links.
- Active states, keyboard navigation, tab switching and browser back/forward.
- Narrow context-tab keyboard activation; the harness allows the existing 100ms
  orchestration route-context debounce to settle before back/forward checks.
- Profile menu Enter/Escape and focus restoration; help menu; search button and
  Ctrl+K; visible keyboard focus.
- Tabless shell widths 1440/1280/1101/1100/1024/768/390px; tabbed shell widths
  1440/1280/1024/768/390px; short-screen navigation scrolling.
- Populated/long-text, empty, loading and error presentation using the unchanged
  Home data path.
- Login/signup shell isolation and desktop/narrow screenshot equality to baseline.

### Reproduce

From `clearml-web`, use installed dependencies (no upgrades needed):

```bash
node node_modules/@angular/cli/bin/ng.js build --configuration development --output-path /tmp/tonops-redesign-after
node node_modules/eslint/bin/eslint.js src/app/layout/side-nav/side-nav.component.ts src/app/layout/side-nav/side-nav.component.html src/app/webapp-common/layout/header/header.component.ts src/app/webapp-common/layout/header/header.component.html
node --check scripts/ui-shell-smoke.mjs
node scripts/ui-shell-smoke.mjs --build /tmp/tonops-redesign-after/browser --artifacts /tmp/tonops-ui-redesign/after --baseline /tmp/tonops-ui-redesign/before
node node_modules/@angular/cli/bin/ng.js build --configuration production --output-path /tmp/tonops-redesign-production
```

Set `CHROME_BIN` to an existing Chromium executable if the installed Playwright
browser revision is unavailable. This session used cached Chromium 1228 via that
environment variable. Omit `--baseline` for standalone future smoke checks. To
capture a pre-change development build, use `--capture-baseline` and a separate
artifact directory; it records baseline overflow without applying new-design
assertions. `--baseline` requires that reference artifact directory to exist.

Artifacts and logs from this session (temporary, not checked in):

- `/tmp/tonops-ui-redesign/{before,after}/results.json`
- Same directories: `home-populated-desktop.png`, `home-populated-narrow.png`,
  `home-{empty,loading,error}.png`, `workers-desktop.png`, `workers-narrow.png`,
  `login-{1440,390}.png`, `signup-{1440,390}.png`.
- `/tmp/tonops-ui-redesign/{baseline,after}-smoke.log`
- `/tmp/tonops-redesign-{baseline,after,production}-build.log`

### Critique, limits and next step

Desktop destinations are now discoverable without tooltips, selected navigation
has a non-color indicator, and the header keeps content/action boundaries clear.
The compact rail preserves space for existing tables at narrower widths. Feature
data fields, charts and operations retain their implementations.

No new regressions were observed within the fixture coverage. The first shell
increment is complete; the wider redesign remains incremental.

Live workflow and server permission verification was **not performed**: the local
API requires authentication and the checked-in dev proxy target is unavailable.
Full Karma and end-to-end suites were **not run**; this slice uses the focused
browser harness and lint/build gates. Large populated feature tables, experiment
comparison, report printing, and live worker/model/dataset operations remain
unverified. Dark mode is not added: this checkout already forces light mode. No
new runtime network dependencies were introduced.

Next concrete slice: inspect and modernize the existing Projects listing toolbar,
search/filter hierarchy and row/card density (P1), preserving sorting, pagination,
visibility rules, deep links and existing create/edit/delete confirmations.

## 2026-11-03 — requested profile and settings increment

The user requested these pages before the Projects listing. Preserved all
uncommitted P0 work and the user's untracked `AGENTS.md`.

### Changes

- `/user/:username`: compact identity panel, clear page/section headings,
  project visibility badges, responsive project/report grids, local report-card
  surface tokens, and descriptive empty/loading/error states. Existing report
  cards, pagination, profile search, project links and owner-only actions remain.
- `/settings/*`: restyled section navigation with native links, `aria-current`,
  keyboard focus, and narrow-drawer open/close semantics. Section selection closes
  the narrow drawer. Original destinations, 265px desktop drawer width and the
  exact administrator visibility condition are retained.
- `/settings/account`: updated heading, identity-summary and personal-information
  card styling only. No template/TypeScript/validator/handler edits. Security,
  cloud-key and API-credential panels keep their existing styles and controls.
- `/settings/webapp-configuration`: new heading and preference card, wrapping
  preference rows; the underlying toggles, dispatches and persistence are unchanged.
- Added `scripts/ui-profile-settings-smoke.mjs` and a focused
  `tsconfig.ui-settings-spec.json`. Repaired the existing settings unit test's mock
  store by adding `dispatch`; the footer already called it before this increment.
  The shell smoke harness now checks programmatic menu focus restoration and
  actual Tab focus separately, avoiding a browser-dependent `:focus-visible`
  assumption on programmatic restoration.

Principal presentation files are under `features/profiles`,
`features/settings/settings.component.html`, the local settings SCSS under
`webapp-common/settings`, `profile-name.component.scss`, and the existing
webapp-configuration component template/SCSS. No production TypeScript, API/state
logic, routes, guards, global styles, IAM panels, credentials logic, auth screens,
onboarding, dependencies or backend files changed in this increment.

### Checks and visual critique

- Fresh baseline development build: **PASS**; baseline focused ESLint: **PASS**.
- Existing settings test baseline: **FAIL**, `this.store.dispatch is not a
  function` in `AdminFooterComponent`, before presentation changes. After the
  targeted mock repair: **PASS**, 1 test, including admin/non-admin menu visibility.
- Development and production builds after refinement: **PASS**. Only the existing
  markdown import warning and the five unchanged feature style budget warnings
  from the P0 log remain; the profile/settings styles stay within budget.
- Final focused ESLint, both harness syntax checks and `git diff --check`:
  **PASS**. Existing ESLint ignore-file and Karma Sass deprecation warnings remain.
- Profile/settings browser harness: **PASS**, with no unexpected runtime errors.
  Own/other profiles, original links and owner controls, report pagination and
  retry, report creation/search dialogs, profile validation/save payloads,
  preference persistence, menu visibility and keyboard drawer behavior all passed
  against isolated fixtures. Profiles, account and configuration were checked at
  1440/1280/1024/768/390px; the root document has no horizontal overflow.
- Protected security/cloud/API-key panel comparison: **PASS**. Baseline and final
  computed style snapshots are identical at the desktop checkpoint. Their
  templates, controls, validators and handlers were not edited.
- Shell regression harness: **PASS**. All four login/signup desktop/narrow PNGs
  are byte-for-byte identical to the original baseline; no shell tokens leak into
  excluded pages. Existing navigation/search/menu/tab/history checks also pass.
- Final source review: **PASS**; no excluded routes, authentication/onboarding
  files, production service/state code, dependencies or backend files changed.
- Browser baseline captures include own/other profiles, account and configuration
  screens, empty/loading/error/report-retry states and protected-panel images/styles.
- Visual critique found a global `.page-header` 64px rule colliding with the
  profile header on narrow screens. Renamed the local class and added a header/
  content non-overlap gate. Report-card surface tokens preserve the shared card
  implementation while matching the redesigned page.
- An initial profile style budget warning was resolved by removing redundant
  scoped overrides; the final production build confirms no new style warnings.
- The original shell focus assertion also reproduced on the pre-increment build;
  its keyboard check now uses actual Tab navigation. No shell production code was
  changed by that test-harness correction.

### Reproduce and artifacts

From `clearml-web`, with installed dependencies and `CHROME_BIN` pointing to an
installed Chromium executable when Playwright's default revision is absent:

```bash
node node_modules/@angular/cli/bin/ng.js build --configuration development --output-path /tmp/tonops-profile-settings-after
node node_modules/@angular/cli/bin/ng.js test trains-webapp --main= --ts-config=tsconfig.ui-settings-spec.json --karma-config=karma.datastudio.conf.cjs --include=src/app/features/settings/settings.component.spec.ts --styles=src/app/webapp-common/styles/style.scss --watch=false --polyfills=zone.js --polyfills=zone.js/testing
node scripts/ui-profile-settings-smoke.mjs --build /tmp/tonops-profile-settings-after/browser --artifacts /tmp/tonops-profile-settings/after --baseline /tmp/tonops-profile-settings/before
node scripts/ui-shell-smoke.mjs --build /tmp/tonops-profile-settings-after/browser --artifacts /tmp/tonops-profile-settings/shell-regression --baseline /tmp/tonops-ui-redesign/before
node node_modules/@angular/cli/bin/ng.js build --configuration production --output-path /tmp/tonops-profile-settings-production
```

Omit `--baseline` for future standalone smoke runs. Capture the pre-change build
with `--capture-baseline` and a separate artifact directory when comparisons are
needed. No live accounts or requests are used by either browser harness.

This session's temporary artifacts:

- `/tmp/tonops-profile-settings/{before,after}/`: `results.json`, profile/account/
  configuration desktop/narrow PNGs, profile state PNGs, protected security/cloud/
  API-key PNGs and `protected-styles.json`.
- `/tmp/tonops-profile-settings/shell-regression/`: shell checkpoints, login/signup
  screenshots and `results.json`.
- `/tmp/tonops-profile-settings/`: baseline/final browser logs, baseline/final
  settings test logs, final lint log and shell-regression log.
- `/tmp/tonops-profile-settings-{baseline,after,production}-build.log`.

### Limits and next step

Fixtures verify client behavior and presentation, not live server operations or
permission enforcement. Full Karma/e2e suites, live profile saves, report editor
contents, external DataStudio, storage cleanup and IAM administration were not
exercised. Existing contained horizontal scrolling in account content at 390px is
retained; the root document does not overflow. Protected account panels are
excluded from restyling. Dark mode remains the checkout's existing forced light
mode; no new runtime dependencies or external assets were introduced.

No new regressions were observed in the tested coverage. Both requested page
redesigns are complete for this increment.

Next highest-value in-scope slice remains the Projects listing toolbar, filters
and density, followed by experiment listing/details.

## 2026-11-10 — Explicit request: project artifacts on S3

Completed an operational migration, with no UI/authentication/source changes.
Copied and SHA-256 verified 327 task artifacts plus 12 fileserver model files;
updated their links and 79 task output destinations. All 20 project defaults and
all 83 current task destinations use RustFS. All 334 current task artifacts have
verified S3 objects; all 339 original source files remain as backups. Repeat
preview reports nothing remaining to migrate.

Five unavailable local model references and one pre-existing missing S3 model
placeholder remain unchanged. Browser/SDK workflows and builds were not run.
Details, the initial resolved streaming error, and the persistent private rollback
manifest are recorded in [the migration log](../rustfs-artifact-migration-2026-11-10.md).
Next storage step: recover the unavailable model files and check client upload
overrides/credentials; the next UI slice remains the Projects listing.

## 2026-11-10 — Model registry hub

Implemented in `/projects/:projectId/models` and existing model General tabs:

- Added registry heading/actions and GUI file/URI registration using existing
  model and fileserver APIs. Retained the table, search, filters, menus, comparison,
  permissions, export and detail tabs. No routing or global stylesheet changes.
- Versions use separate model IDs, native parent links and `version:` tags.
  Added same-name/project version history with pagination, parent navigation,
  searchable project selection, SDK/REST snippets and exact-model download code.
- Uploads register the draft URI before transferring bytes, as required by the
  fileserver's existing authorization. Failed uploads retain a draft for retry
  without another create. Filenames are normalized for consistent authorization.
- Added framework-aware ClearML Serving commands, setup links, endpoint navigation
  and Python/cURL request examples with JSON validation. The UI explicitly requires
  an existing inference runtime and preprocessing; it does not start containers.
- Scoped existing workspace tokens to model components. Below 700px, open model
  details use the splitter width; the existing close action returns to the list.

Baseline: `main`, app 2.5.0 / Angular 21.2. Preserved pre-existing PLAN.md,
PROGRESS.md and the untracked RustFS migration note. Used installed Node 22.22.0
and node_modules directly because pnpm was unavailable; no dependencies changed.

Verification:

- Baseline and final development builds: PASS. Final production build: PASS;
  only the existing markdown import and five unrelated style-budget warnings.
- New model-hub files and model General container focused ESLint: PASS. The parent
  ModelsComponent retains two lint errors (`any` and unused `mode`), reproduced
  against HEAD using ESLint stdin; no new errors were introduced there.
- Live SDK reads: PASS under the configured Tung Nguyen account. Existing models
  and projects are accessible; serving currently reports no endpoints.
- Live GUI registration: PASS. Uploaded a fitted 1,590-byte scikit-learn model and
  verified a byte-identical authenticated download. Live model details, version
  link, code rendering and 390px document overflow check passed. Both test model
  and uploaded file were deleted (HTTP 200); existing data was preserved.
- The live harness uses the configured SDK session in a temporary local proxy.
  Browser-origin CORS headers were adapted only in the harness. Initial attempts
  exposed Snap Chromium's isolated /tmp and the temporary origin's CORS mismatch;
  passing file bytes and adapting harness responses resolved them. Failed test
  drafts/files were cleaned up. No server or auth configuration was edited.
- Shell capture/auth regression: PASS. Login/signup screenshots at 1440/390px
  match the baseline byte for byte. Capture-mode navigation/history, empty/loading/
  error and narrow-screen checks pass. The full shell harness's profile-focus
  assertion fails on unchanged baseline line 148; capture mode was used consistently
  before/after without changing that existing harness.

Reproduce from `clearml-web` with installed dependencies:

```bash
node node_modules/@angular/cli/bin/ng.js build --configuration development --output-path /tmp/tonops-model-hub-final
CHROME_BIN=/snap/bin/chromium node scripts/ui-model-hub-smoke.mjs --build /tmp/tonops-model-hub-final/browser --artifacts /tmp/tonops-model-hub/fixtures-final
node node_modules/@angular/cli/bin/ng.js build --configuration production --output-path /tmp/tonops-model-hub-production
```

Artifacts: `/tmp/tonops-model-hub/{fixtures-final,live-before,live-after,
baseline-shell,after-shell}/` contains registry/registration/version/serving/upload
failure/auth screenshots and results. Logs: `/tmp/tonops-model-hub-*.log`.
The temporary live session is removed after verification and is never committed.

Limits: no live inference runtime or serving execution was provisioned/verified.
GUI file upload uses the configured HTTP(S) fileserver; S3 uses SDK upload or an
existing object URI. History groups by exact name/project and displays explicit
version tags; it does not infer semantic release order or introduce a new schema.
Full Karma/e2e suites, huge model tables and existing destructive menu operations
were not exercised. No auth, backend, SDK, dependency or API-contract changes.
Source builds are local; the running production webserver is unchanged.

Next slice: connect and validate a running inference service, within an explicitly
authorized deployment scope, so users can exercise the generated request code.

Final verification: the repository fixture harness passes file upload, normalized
filenames, storage URI registration, SDK/REST rendering, all-project project
selection, parent/version-tag payloads, version deep links/back, read-only states,
upload failure/retry without duplicate drafts, version-query failure/retry, empty
registry, form validation, JSON validation, exact-model download and generated
serving/request code. Responsive checks passed at 1280/1024/768/390px, including
waiting for the model list to hide when narrow details expand. No unexpected
browser runtime errors occurred. Live upload/download/detail checks also passed
on the final build and all disposable data was cleaned up. Shell auth PNGs remain
byte-identical. Shell-quote roundtrips, regex escaping, generated Python syntax,
script syntax, focused new-code lint and `git diff --check`: PASS. Existing parent
lint errors and baseline shell focus failure remain as documented above.

## 2026-11-10 — Activate the model hub frontend

The user checked Model endpoints and could not see the registry update. The
registry lives at `/projects/*/models` (all projects) or
`/projects/:projectId/models`; serving guidance is in a model's General tab.
The previous source-only handoff left the running frontend on its earlier build.

Deployed the verified production frontend at `http://27.66.108.30:7861` by
deriving the currently running image and recreating only `webserver`. Copied
frontend assets while preserving env.js, configuration.json, credentials.json
and onboarding.json. No repository deployment configuration was changed.
The API/fileserver containers retain their exact previous IDs and start times;
all data and inference services remain in place. Runtime configuration, env.js
and nginx configuration SHA-256 hashes match their pre-deployment values, and
the served index exactly matches the tested production build.

- Active image: `clearml/local-server:model-hub-20261110-164434`, also tagged
  `clearml/local-server:dev` for the existing Compose setup.
- Original image retained as
  `clearml/local-server:before-model-hub-20261110-164434` for rollback.
- Deployment manifest: `/tmp/tonops-model-hub-deployment.json`; browser artifacts:
  `/tmp/tonops-model-hub/deployed-{before,after}/`.
- Frontend readiness and public registry route: HTTP 200; webserver healthy.
- Deployed browser check: PASS under the configured account. The all-project
  registry heading, Register model dialog and SDK/API tab are visible and produce
  no unexpected runtime errors. No model data was written by this deployment check.
- Deployed login/signup comparison: PASS, all four 1440/390px PNGs byte-identical
  to the pre-deployment running app. The first authenticated harness attempt
  intercepted the proxy path while production uses the API port directly; correcting
  the test target resolved its login redirect. No auth code/settings were changed.
- Removed the temporary SDK session file after verification. Rollback image remains.

This supersedes the previous entry's source-only deployment limitation. Serving
runtime provisioning remains outside this frontend activation.

## 2026-11-10 — Normal-login acceptance test on port 7861

Used the supplied account through the normal login form at
`http://27.66.108.30:7861`. No mocked responses, injected SDK tokens, modified
CORS headers or authentication changes. Credentials were supplied through
non-echoing stdin, held in process memory, and were not written to the repository
or test artifacts. Tested the actual deployed production app.

Confirmed a live upload blocker that the earlier proxy-assisted test masked:
the fileserver on 7863 saves the upload but its response lacks
`Access-Control-Allow-Credentials: true`. Chromium rejects the credentialed
response, leaving the draft's upload unconfirmed. Independently downloaded the
file with the authenticated test context and verified identical bytes. This is
a **FAIL** for GUI upload completion, despite the file reaching storage. The
earlier adapted-CORS test is not evidence of unmodified browser upload success.

The existing same-origin files proxy also strips the host port and rewrites the
path, conflicting with registered-model file authorization. No workaround using
fake URIs, token handling, permissions, backend or auth/server configuration was
introduced. Correcting the fileserver CORS/deployment dependency requires a
scope exception to the project's excluded server/auth-configuration boundary.

Found and fixed a separate in-scope defect: joined model APIs return parent
objects (`{id: ...}`), while the new parent link assumed a string. Normalize the
parent ID locally before routing. Updated the fixture to reflect the actual
response and assert the parent link. Also clarified the upload alert: the browser
could not confirm the upload and the file may already be stored.

Final normal-browser results:

- PASS: normal login as Tung Nguyen and authenticated account identity.
- PASS: registry visibility, existing-project search, draft/version tags, actual
  stored file and byte-identical authenticated download.
- FAIL: GUI upload completion/confirmation because of the CORS header above.
- PASS: GUI version creation via an existing URI, native parent relationship,
  corrected parent link and version navigation.
- PASS: direct REST model registration and refreshed version history.
- PASS: exact-model download snippet, serving command, Python/cURL request
  generation and invalid-JSON handling.
- PASS: 1024/768/390px document layout and expanded narrow model details.
- PASS: SDK/REST examples and Model endpoints navigation. The API returns zero
  endpoints, so actual serving/inference execution remains UNVERIFIED.
- PASS: cleanup of the test file and all three final-run models (HTTP 200 each).
  Earlier diagnostic runs' temporary models/files were also removed.
- No unexpected JavaScript page errors or HTTP error statuses occurred; browser
  console errors explicitly report the known fileserver CORS rejection.

Validation of the scoped corrections: focused new-code ESLint, development and
production builds, registry fixture browser suite, script syntax and
`git diff --check`: PASS. All four shell login/signup 1440/390px PNGs remain
byte-identical to baseline. Builds retain the existing markdown/style warnings.
Existing parent-component lint errors and baseline shell-focus failure remain
as previously recorded. No additional backend tests were needed or executed.

Deployed only the corrected frontend over the then-current image. Active image:
`clearml/local-server:model-hub-tested-20261110-165859` (also `:dev`); rollback:
`clearml/local-server:before-parent-link-fix-20261110-165859`. API/fileserver
container identities/start times and runtime config/env.js/nginx hashes remained
unchanged. No auth source, API contracts or dependency files changed.

Evidence: `/tmp/tonops-model-hub/normal-login/results.json` and screenshots
`registry-desktop.png`, `upload-confirmation-failed.png`, `versions-desktop.png`,
`serve-and-call-desktop.png`, `serve-and-call-narrow.png`, `model-endpoints.png`.
Fixture artifacts: `/tmp/tonops-model-hub/normal-login-fixtures/`; build/lint logs:
`/tmp/tonops-model-hub-normal-login-*.log`. The temporary normal-login harness
reads credentials from stdin and contains no saved password or browser state.

Next concrete step: resolve the fileserver CORS configuration dependency under
explicit authorization, then rerun this normal-login upload test. Inference
testing additionally needs a running model endpoint.

## 2026-11-10 — Explicit request: serve YOLO models as tungn197

Completed a separate inference deployment authorized by the user's latest
request. The existing application/auth/backend services were not modified or
restarted. Reused the installed YOLO runtime and existing account-owned YOLO11n,
YOLO12n and YOLO26n best checkpoints. Downloaded the registered S3 objects and
verified SHA-256 against their original training files.

All three models are live on port 7872 in the independent
`tonops-yolo-serving-inference-1` container with a read-only root filesystem,
read-only model/credential mount, CPU/memory limits and `unless-stopped` restart
policy. Native ClearML endpoint references point to their real model IDs;
heartbeats report actual request counts, uptime/rate and latency every 15 seconds.
Stale entries expire after 120 seconds. Model metadata contains the live URLs
and input format; model URI, tags, Draft status and training tasks were preserved.

Verification: five input-contract tests passed both on the host and in the actual
serving image without networking. Image build, dependency check, Python compile
and diff whitespace check passed. Real public JSON and multipart predictions
passed for all three models, with 6/5/7 detections on the bus smoke image at 0.1
confidence. Invalid base64/image/model/confidence returned 400/400/404/422.
The existing client script passed. Restarted the service, repeated actual
predictions and confirmed fresh reports/nonzero counts and latency for all three.
Normal browser login confirmed all three endpoint rows and YOLO12 details;
no unexpected runtime errors occurred. The service remains healthy and running.

Code: `examples/yolo_serving/{serve.py,prepare.py,Dockerfile,compose.yaml,README.md}`;
tests: `tests/test_yolo_serving.py`. The configured account's existing SDK keys
are in a mode-0600 file under ignored `docker-data`, outside the image/repository;
no new IAM credentials, auth changes or saved passwords were introduced. An
initial optional codec auto-install during a host test was removed and disabled;
corrected tests and the serving runtime do not install packages at request time.

Limits: CPU smoke serving validates deployment mechanics, not production
accuracy, throughput or a long-duration soak. Prediction URLs are unauthenticated
under the existing trusted-network demo pattern. Full unrelated app/backend
suites were not rerun. The pre-existing GUI fileserver CORS blocker is unchanged
and does not affect these prediction requests.

URLs, exact model IDs, test evidence, private artifact locations and operating/
stop commands: [YOLO deployment record](../yolo-serving-2026-11-10.md).
Next serving step: validate these checkpoints on the intended images and workload
before treating them as production detectors.
