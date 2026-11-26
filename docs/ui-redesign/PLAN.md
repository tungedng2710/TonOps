# Authenticated UI redesign — first increment

## Restore signed-in project access — 2026-11-26 (complete)

- Restore the routes, startup redirects, sidebar and project visibility copy
  from `4f07f43`. Remove the guest Projects and Playground pages, their API
  service and schema, guest feature tests, and feature-specific instructions.
- Preserve signed-in Projects and its existing visibility rules. Login and
  signup components, credential handling, and deployment are outside this change.
- Verify the production build, signed-out redirects, signed-in navigation, and
  login/signup screenshots. Confirm the removed pages and API have no active
  references, and record the outcome in PROGRESS.md.
- Restored the application and repository instructions to `4f07f43`. Production
  and development builds, focused lint, browser checks and screenshot comparison
  passed. Both frontend builds contain no references to the removed features.

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

## Explicit operational request — project artifacts on S3 (2026-11-10)

The user requested storage migration separately from UI redesign. Limit this
operation to existing registered artifact/model URIs and output destinations;
leave authentication and application source unchanged. Preflight source files
and task activity, copy and hash-verify all accessible files, conditionally update
links, retain sources and a private rollback manifest, and verify final records.

- [x] Inspect and preview the running stack; identify unavailable local models.
- [x] Copy and SHA-256 verify 339 files, then update registered links/destinations.
- [x] Verify all 334 current task artifact objects and record model exceptions.
- [x] Record results and recovery details in
  `docs/rustfs-artifact-migration-2026-11-10.md`.

## Model hub — 2026-11-10 (UI implementation and verification complete)

- Objective: improve existing `/projects/:projectId/models` registry and model
  details, retaining the NgRx table, search, comparison, publishing, archive,
  permissions and deep links. Add GUI file/URI registration, SDK/API examples,
  native parent lineage and version tags, and serving command/call examples.
- Implementation: scoped registry heading/actions; registration dialog using
  existing model/fileserver APIs; model detail hub with version navigation and
  deployment guidance. Keep all existing detail tabs and fields.
- Boundaries: no backend, SDK, dependencies, API contracts, shell/global theme,
  guards or authentication changes. DO NOT TOUCH `/login` and `/login/signup`,
  login feature, auth services/state, account/onboarding and global styles.
- Risks: fileserver requires a registered URI before upload; retain failed drafts
  for retry and explain partial failures. Versions use existing parent and tags;
  never infer release order from pagination. Existing serving APIs monitor
  endpoints, not provision inference servers; show explicit setup requirements.
- Verification: baseline/final Angular builds, focused lint, browser checks with
  fixtures for success/failure/retry/version payloads, desktop/narrow screenshots,
  shell/auth regression checks, and configured-account live checks where possible.
- Done: functional controls and truthful states, no auth diff, checks/results
  recorded in PROGRESS.md. Preserve earlier pre-existing documentation edits.
- Completed: registry registration, versions, SDK/REST/download/serving snippets,
  retry/error/read-only states and responsive details. Development/production
  builds, isolated browser suite, live GUI upload/download/cleanup and auth image
  comparisons passed. Existing lint/focus failures and deployment limits are
  recorded in PROGRESS.md. No inference runtime was provisioned.

### Activate model hub in the running web app (2026-11-10)

The user checked the running application and could not see the source update.
Deploy the verified production frontend by deriving the current local image and
recreating only the webserver. Retain the original image for rollback and keep
backend images/containers, runtime configuration, authentication and data intact.
Capture the running login/signup pages before/after, verify registry navigation
under the configured account, and record the actual URL and deployment result.

Completed: frontend image activated, only webserver recreated, runtime hashes and
backend container identities preserved, authenticated registry checks passed, and
the four deployed login/signup screenshots remain pixel-identical. Direct entry:
`http://27.66.108.30:7861/projects/*/models`. Rollback details are in PROGRESS.md.

### Normal-login acceptance test (2026-11-10)

Test the deployed public web app on port 7861 with the supplied account through
the normal login form. Use no injected SDK token, mocked API response or CORS
override. Exercise GUI upload, project selection, authenticated download, adding
a version, REST registration, serving snippets, validation and narrow layouts.
Create only clearly labeled disposable models in an existing owned project and
remove their files/records afterward. Test authentication as-is; do not edit it.
Record actual results and separate snippet generation from live inference.

Normal-login test found a live dependency: credentialed GUI uploads save the file
but the fileserver response omits Access-Control-Allow-Credentials. The existing
/files proxy strips the host port and rewrites the URI path, which conflicts with
registered-model file authorization. Do not work around this by changing token
handling, permissions, temporary fake URIs or auth/deployment configuration. Keep
those excluded areas unchanged and report the dependency. Continue testing all
remaining registry workflows with disposable models and clean up after testing.

The live API also returns joined parent objects rather than only strings. Normalize
that value locally in the model hub so parent navigation uses the actual model ID.
Clarify upload confirmation errors without claiming the saved file is absent.
Build/lint these scoped corrections, deploy only frontend assets over the current
image, rerun the normal-login acceptance test, and retain the CORS blocker.

Completed normal-login acceptance testing: login, registry, version creation,
REST registration, parent navigation, code generation and narrow layouts passed;
all disposable data was removed. Scoped parent-link/message fixes are deployed.
GUI upload confirmation remains failed pending the excluded server CORS change;
actual inference remains unverified because there are no endpoints. Results and
artifacts are recorded in PROGRESS.md.

### Explicit serving request — tungn197 YOLO models (2026-11-10)

The user now explicitly requests deploying YOLO models under tungn197. This
authorizes a separate inference deployment; authentication/account changes and
unrelated UI work remain excluded. Reuse the existing YOLO runtime and owned
YOLO11/YOLO12/YOLO26 best checkpoints. Download and hash-check the registered
weights, serve real image inference on a free port, register native endpoint
references/heartbeat metrics using the configured account, and keep the service
running with a restart policy. Preserve existing applications and model status.
Verify real detections, invalid input handling, persistence and visibility on
Model endpoints, then document URLs, request examples and operating commands.

Completed: three owned best checkpoints served on 7872, independent Docker
deployment with automatic restart, matching checkpoint hashes, actual remote
JSON/multipart predictions, input validation, live ClearML metrics, restart
recovery and normal-login browser verification. No model lifecycle or auth
changes. Details: `docs/yolo-serving-2026-11-10.md`.

## Unified Model Management — 2026-11-10 (in progress)

- User request: combine model hub and endpoints into a top-level management page,
  outside Projects. Add one sidebar destination with Model hub and Endpoints
  views, retaining endpoint loading/monitor views and all registry detail tabs.
- Canonical routes: `/models/registry/:projectId` (`*` for all projects),
  `/models/endpoints/active`, `/models/endpoints/loading`, and model comparison.
  Legacy `/projects/:projectId/models/**` and `/endpoints/**` redirect while
  preserving suffixes, query parameters and project context.
- Reuse existing Angular/NgRx tables, effects, split panels, forms, permissions,
  charts and APIs. Limit effect changes to navigation destinations. Preserve
  comparison, full-screen/minimized views, sorting/filtering and browser history.
- Changes: scoped management layout/tabs, sidebar entry, canonical routes and
  compatibility redirects, project-tab removal, navigation links/breadcrumbs.
- Excluded: login/signup/onboarding, guards/auth configuration, API contracts,
  runtime/model services, unrelated pre-existing work. Leave the known upload
  CORS dependency unchanged. Existing YOLO endpoints must remain healthy.
- Verify: baseline/final builds, focused lint, fixture navigation and regression
  checks, normal-login browser test against live registry/YOLO endpoints, desktop/
  narrow layouts, legacy redirects/queries, auth screenshot equality. Deploy only
  the frontend with rollback retained and record results in PROGRESS.md.
