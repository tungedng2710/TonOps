# Authenticated UI redesign — first increment

## Objective and scope

Modernize the existing authenticated application shell (P0): labeled desktop
navigation, readable active/hover/focus states, and a restrained top bar. Preserve
all existing destinations, nested-mode links, tabs, breadcrumbs, search, refresh,
menus, permissions, and MLOps operations. This is a bounded first increment, not a
rewrite of feature screens.

Baseline: branch `main`, commit `86f7e04` (`update login page`), ClearML Web 2.5.0,
Angular/Material/NgRx 21. Node 22.22.0 and installed dependencies are available;
pnpm is unavailable. The checkout forces light mode in its existing selectors and
theme service. Do not change that behavior. Initial working tree: only the user's
untracked root `AGENTS.md`.

## Route and component map

| Existing route | Main component/area | Shell coverage |
| --- | --- | --- |
| `/home` | `features/home/HomeComponent` | Sidebar and header |
| `/dashboard`, `/projects` | Dashboard / ProjectsPage | Sidebar and header |
| `/projects/:projectId/overview`, `/workloads` | ProjectInfo / WorkloadsPage | Sidebar and header |
| `/projects/:projectId/tasks`, `/models`, `/compare-tasks`, `/compare-models` | Existing experiments/models/compare routes | Sidebar and header |
| `/datasets`, `/pipelines` | Existing dataset/pipeline routes and nested views | Sidebar and header |
| `/workers-and-queues/workers`, `/queues` | Orchestration and workers/queues containers | Sidebar and header |
| `/endpoints/active`, `/reports` | Existing serving/reports routes | Sidebar and header |
| `/settings`, `/user`, `/users` | Existing settings/profiles | Shell presentation only |

## Do not touch

- `/login` and `/login/signup`, all components under `features/login` and
  `webapp-common/login`, and `_auth-layout.scss`.
- Authentication, IAM, account onboarding/recovery, session/token handling, route
  guards, app initialization, API/services/state contracts, and backend code.
- Global themes, resets, Material overrides, font loading, assets, dependencies,
  shared sidebar-width variables, and deployment/proxy configuration.
- Feature tables, charts, task/model/data operations, permissions, and routes.

Auth pages render outside `AppComponent`; `sm-side-nav` and `sm-header` are mounted
only when the existing `currentUser()` condition is true. Their styles can safely
change locally. `AppComponent` uses global encapsulation, so avoid changing its
stylesheet. Breadcrumbs and tabs will retain their implementations in this slice.

## Implementation order

1. **Inspect/baseline:** trace shell selectors, route links, actions and services;
   compile the current app; capture representative shell and excluded-route images.
2. **Plan:** record boundaries and checks here before UI edits.
3. **Implement:** introduce a shell-only token mixin consumed by sidebar and header;
   add visible desktop navigation labels with a compact rail on narrower screens;
   retain tooltips, `aria-current`, route expressions and scroll behavior. Refine
   header surfaces/spacing without changing its 64px height or tab behavior. Use a
   native button for the profile menu trigger and label header icon controls.
4. **Verify/critique/refine:** focused lint, Angular build, browser fixture checks,
   before/after images, keyboard menus/navigation, responsive widths, and auth
   screenshot comparison. Fix observed regressions within this slice.
5. **Record:** put actual results, artifacts, limits and the next slice in
   `PROGRESS.md`.

## Risks and checkpoints

- Wider navigation reduces feature width: check 1440/1280/1024/768/390px layouts;
  retain compact navigation on narrow screens and scrolling on short screens.
- Context tabs compete with breadcrumbs and action menus: check both tabbed and
  tabless headers, long project context, and all header actions at narrow widths.
- Existing overlays and fixed sizing must remain functional; do not change
  shared sidebar-width constants used by the global loader.
- Authentication exclusion: no global CSS changes, no auth-file diff, and compare
  before/after login/sign-up screenshots with identical browser fixtures.
- The running local API requires authentication, and the dev proxy points at an
  unavailable port. Do not change configuration or seek credentials for this
  presentation slice. Browser fixtures must be explicit and isolated; they do not
  prove live MLOps operations or server permission enforcement.

## Definition of done

The shell increment is implemented and reviewable; links, actions and state
contracts remain intact; focused checks and an application build pass (or any
failures are accurately recorded); browser checks and visual critique are
performed where available; excluded pages are unchanged; and the progress log
contains reproducible verification and the next concrete step.

## Status

- [x] Repository, routes, selectors, actions/services and auth boundaries inspected.
- [x] Baseline development build and focused shell lint pass (existing warnings).
- [x] Baseline browser evidence captured.
- [x] Shell increment implemented and refined.
- [x] Final verification and progress record completed (see `PROGRESS.md`).

## Current increment — profiles and settings (2026-11-03)

The user explicitly requested these pages next. Preserve the uncommitted P0 shell
work listed above; initial status is the four modified shell files, untracked
shell tokens/smoke script, this documentation directory, and the user's untracked
`AGENTS.md`. Branch/version and stack are unchanged.

### Objective, routes and files

- `/user/:username` (`features/profiles/profiles.component.{html,scss}`): compact
  identity panel, clearer projects/reports hierarchy, readable cards, meaningful
  empty/loading/error presentation, and responsive long-text handling. Retain
  original bindings, report cards, pagination, profile search and owner-only actions.
- `/settings/*` (`features/settings/settings.component.html` and its existing
  local SCSS under `webapp-common/settings`): restyle the section menu with real
  keyboard-accessible links, active-route semantics, and an accessible narrow
  drawer that closes after section selection. Keep the existing drawer width so
  protected account panels retain their available width.
- `/settings/account` (`profile-name.component.scss` only): refine heading,
  identity summary and personal-information card via narrow selectors. Do not
  edit the component's TypeScript/template, password form, cloud/API key panels,
  validators, handlers, or shared `.settings-card`/form styling.
- `/settings/webapp-configuration` (its component template/SCSS): clearer heading
  and preference card using the unchanged `sm-profile-preferences` component.

Existing profile services and report actions/effects, settings actions/effects/
selectors, personal-info update service calls and preference dispatches were read
before editing. Do not alter them, routes, guards, API contracts, authentication,
onboarding, IAM panels or credential flows. Reuse the shell token mixin locally;
no global CSS changes or new dependencies.

### Execution and verification

1. Baseline build, focused lint and existing settings menu test; capture profile,
   account, configuration and protected-panel screenshots with isolated fixtures.
2. Implement profiles, then settings navigation and non-auth presentation.
3. Focused lint, existing settings test, development/production builds and browser
   checks: own/other profiles, report links/pagination/retry, populated/empty/
   loading/error states, long names, enabled/disabled controls, native keyboard
   links, admin visibility, narrow drawer, preference persistence and personal-info
   save behavior through the unchanged handlers.
4. Review before/after images; compare login/signup and protected account panels
   to baseline; refine observed issues and record actual outcomes in PROGRESS.md.

Risks: report-card minimum widths, double scroll containers inside settings,
drawer focus/keyboard behavior, long names/metadata, and accidental selectors
affecting password/credential panels. Keep those selectors isolated and test them.
Live API/permission enforcement and unexercised MLOps workflows remain outside
fixture evidence; never describe them as verified.

Done means both requested areas visibly improve in the real components, existing
data/actions/conditions remain intact, checks and limits are recorded accurately,
and excluded auth/onboarding experiences remain unchanged.

- [x] Inspect components, routes, state/services, tests and pre-existing changes.
- [x] Capture fresh baseline evidence.
- [x] Implement and critique profiles.
- [x] Implement and critique settings.
- [x] Verify boundaries, build/tests, and record results (see PROGRESS.md).
