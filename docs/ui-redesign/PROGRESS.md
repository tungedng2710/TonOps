# UI redesign progress

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
