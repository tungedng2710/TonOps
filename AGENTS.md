# AGENTS.md — ClearML Web UI Redesign Harness

## 1. Mission

You are an autonomous coding agent working in a fork of the **ClearML Web** repository.

Your mission is to modernize the **authenticated MLOps application interface** without changing how ClearML works. Deliver a production-quality, coherent UI for engineers managing experiments, models, datasets, pipelines, workers, and queues.

**Do not redesign, modify, or rebuild Login, Sign up, Create Account, password recovery, or any other authentication/account-onboarding page.** This is a strict project boundary, not a low-priority item.

Work from the existing codebase, not from a blank-slate mockup. Implement real changes, verify them, and leave the repository in a working state.

## 2. Non-negotiable constraints

1. **Preserve MLOps behavior.** Do not change API contracts, data models, permissions, task lifecycle, experiment comparison, model operations, dataset operations, worker/queue operations, or pipeline execution semantics merely to support a new design.
2. **Authentication is out of scope.** Do not edit auth screens, account creation, password reset, identity-provider flows, tokens, sessions, route guards, auth configuration, or authentication-related API logic. Do not introduce a new IAM feature.
3. **No accidental auth redesign.** Global theme changes must not visually or functionally alter excluded pages. Prefer styling scoped to the authenticated application shell; verify excluded routes remain unaffected where feasible.
4. **Use the existing stack.** The upstream project is Angular/TypeScript with NgRx and existing UI libraries. Inspect the checked-out version before making assumptions. Do not migrate to React, Next.js, Tailwind, or a new component framework unless the user explicitly requests it.
5. **Reuse before replacing.** Keep working data tables, plots, DAG views, charts, state management, and service integrations. Improve their presentation and usability incrementally.
6. **No fake production functionality.** Do not replace real data with hard-coded metrics, simulated runs, decorative controls, or non-functional links. If data is unavailable, use truthful empty, loading, error, or unavailable states.
7. **Offline/self-hosted friendly.** Avoid dependencies on runtime CDNs, hosted fonts, external icon services, remote telemetry, or SaaS-only UI features. Prefer local assets and packages already present.
8. **Do not modify unrelated code.** Avoid backend changes, broad refactors, dependency upgrades, and configuration churn unless necessary and justified.
9. **Preserve accessibility and responsiveness.** All navigation and interactive elements must remain keyboard-usable and work on supported desktop widths; narrower viewports should degrade gracefully.
10. **Never conceal failures.** Report incomplete work, skipped tests, known regressions, and missing test infrastructure accurately.

## 3. Source of truth and repository orientation

Before editing, inspect the actual repository. At minimum, read:

- `README.md` and `package.json` for install, run, test, and build commands.
- `angular.json`, `src/`, current routes, app-shell layout, theme variables, shared UI modules, and feature components.
- Existing NgRx actions/effects/reducers and services for every feature you touch.
- Any nested `AGENTS.md`, relevant tests, design tokens, lint rules, and established coding conventions.

The upstream ClearML Web README describes business-logic, core, feature, and shared-module responsibilities. Respect the boundaries present in this checkout rather than imposing a new architecture.

Useful upstream references (for orientation, not as substitutes for local inspection):

- https://github.com/clearml/clearml-web
- https://clear.ml/docs/latest/docs/webapp/webapp_overview/
- https://clear.ml/docs/latest/docs/references/api/

### Initial baseline

1. Run `git status --short` and record pre-existing changes. Never overwrite unrelated user work.
2. Identify the target branch/version and available scripts.
3. Run the most relevant baseline build/tests before making significant changes if the environment allows.
4. Map application routes to their components, with a separate **DO NOT TOUCH** list for auth/account-onboarding routes and any shared styles that affect them.
5. Identify shared design primitives that can safely be changed versus components requiring local, scoped overrides.

Do not guess filenames, selectors, route paths, or commands. Discover them first.

## 4. Product direction

Design a calm, efficient, professional **MLOps workspace** inspired by the interaction quality of Linear and Vercel, without copying their visual identity.

### Visual principles

- Minimal, content-first layouts with clear hierarchy and controlled whitespace.
- Modern typography; prefer an existing locally available font stack over a network font.
- Consistent spacing, radii, borders, elevations, icon sizes, and interaction states.
- Neutral surfaces with restrained blue/indigo accents; reserve semantic color for status and severity.
- Both light and dark themes **if the existing application supports them**; avoid introducing a broken half-theme.
- Compact, data-dense tables suitable for ML engineers; never sacrifice key metrics for decorative space.
- Strong contrast, visible focus, useful hover/selected states, accessible color usage.
- Consistent loading, empty, error, success, and permission-denied experiences.

### UX principles

- Keep important navigation discoverable. Prefer labeled primary navigation over ambiguous icon-only affordances.
- Retain deep links, browser back/forward behavior, filtering, sorting, pagination, and saved views if already supported.
- Preserve experiment plotting, comparison workflows, artifacts, logs, parameters, metrics, and actions.
- Make task status, queue state, worker health, and model version distinctions easy to scan.
- Avoid modal proliferation. Use existing detail panels, tabs, drawers, and confirmation patterns where appropriate.
- Treat potentially destructive actions carefully: retain existing confirmations, permissions, and disabled states.

## 5. Scope and implementation priority

Improve existing supported UI. The following is a **priority order**, not permission to invent features or backend endpoints:

| Priority | Area | Expected improvements |
| --- | --- | --- |
| P0 | Authenticated app shell | Sidebar, top bar, breadcrumbs/context, responsive layout, navigation active states, common tokens |
| P1 | Projects and Experiments | Listing density, search/filter controls, tables, status indicators, empty/loading states |
| P1 | Experiment details | Information hierarchy for metrics, logs, artifacts, hyperparameters, compare actions |
| P2 | Models and Datasets | Lists, metadata, version/history presentation, existing lineage links |
| P2 | Pipelines | Run summaries, node/status readability, navigation around existing DAG views |
| P2 | Workers and Queues / Orchestration | Capacity and execution-state clarity using existing data |
| P3 | Non-auth settings and common dialogs | Layout consistency and accessibility, only where related to the redesign |

Do not create a new Overview dashboard, global navigation destination, or feature unless the current app already provides it or the user specifically requests it. Existing functionality takes precedence over conceptual designs.

### Explicitly excluded

- Login / Sign in pages
- Sign up / registration / Create Account pages
- Forgot password, reset password, account verification, onboarding
- Authentication and authorization flows, SSO, session handling, route guards
- New user/role management functionality and IAM backend work
- ClearML Server, SDK, Agent, storage, database schema, or deployment changes

If a request would require changing an excluded area, leave that area untouched and document the dependency rather than proceeding.

## 6. Harness engineering: the execution loop

Use a **bounded, evidence-driven loop**, not an open-ended cosmetic rewrite:

**Inspect → Plan → Implement → Verify → Critique → Refine → Record**

### Step A — Inspect

- Trace the current route, component tree, templates, styles, shared widgets, state selectors, and service calls.
- Record baseline behavior and screenshots when a browser is available.
- Identify high-value usability problems and the smallest code surface that can fix them.
- List regression risks, especially shared styles and actions tied to real ClearML operations.

### Step B — Plan

For any change touching multiple components, write a short plan in `docs/ui-redesign/PLAN.md` (create the directory if necessary). Include:

- Objective, route(s), affected components, and user-visible behavior.
- Explicit non-goals and excluded auth-related files/routes.
- Expected modifications, implementation order, and risks.
- Test cases and visual checkpoints.
- Definition of done.

Keep the plan updated with factual completion status. Avoid a large speculative architecture document.

### Step C — Implement in small vertical slices

- Change one cohesive screen, layout region, or reusable primitive at a time.
- Prefer existing Angular components, SCSS conventions, and state-management patterns.
- Introduce reusable tokens/primitives only when at least two in-scope areas benefit.
- Keep business logic in existing services/state layers; presentational changes should remain presentational.
- Avoid changing the shape of API responses or introducing parallel data-fetching paths.
- Keep commits/diffs reviewable. Do not mix formatting-only churn with functional work.

### Step D — Verify after each slice

1. Run focused tests/lint/type checks available in the repository.
2. Run an application build when feasible.
3. Exercise changed screens in a browser against a configured ClearML API server, if available.
4. Test realistic states: populated, empty, loading, error, long text, large tables, and disabled actions.
5. Check desktop and narrower viewport behavior.
6. Check that excluded auth routes have not been changed by shared CSS or routing modifications.
7. Compare before/after screenshots for layout shifts and visual regressions, if tooling exists.

### Step E — Critique and refine

Ask, with evidence:

- Is the new layout easier to scan and navigate?
- Does it retain every important action and data field?
- Are statuses, filters, tables, charts, and details semantically correct?
- Does the screen look coherent in both dense and sparse states?
- Is the change accessible, performant, and compatible with existing app behavior?
- Did this work unintentionally affect auth/account pages or unrelated routes?

Fix issues before moving to the next slice. Do not mark work complete based solely on compilation.

### Step F — Record the result

Update `docs/ui-redesign/PROGRESS.md` with:

- Completed slice and changed routes/components.
- Tests and checks actually executed, with pass/fail outcomes.
- Screenshot locations, if generated.
- Known limitations, remaining risks, and the next concrete step.

This log is the handoff point for future agent sessions. Keep it concise and verifiable.

## 7. Repository commands and testing discipline

The upstream README currently documents **Node.js 24 + pnpm 10** and a development server that proxies a ClearML API server. Inspect the checked-out repository before using these commands:

```bash
pnpm install --frozen-lockfile
pnpm run build
pnpm run start
```

Also inspect `package.json` for available scripts such as `test`, `lint`, and `e2e`; execute those relevant to changed code. Do not claim a passing test when it could not run, and do not invent a validation command. The development server may require a configured API target in `proxy.config.mjs`; never commit private endpoints, credentials, or tokens.

### Verification gates

A slice is **done** only when:

- The intended design change is implemented in the existing application.
- Current data, links, actions, and permissions still work.
- Relevant tests/builds pass, or failures are clearly recorded with causes.
- Browser/visual checks are completed when tooling and a running app are available.
- No excluded authentication/account pages or flows were altered.
- The change is documented in the progress log.

If browser access, dependencies, or an API server are unavailable, proceed with code-level checks and clearly label visual/functional verification as **not performed**, never as passed.

## 8. Quality standards

### Angular / architecture

- Follow existing Angular and NgRx conventions in this repository version.
- Preserve typed inputs/outputs, observable/state patterns, existing error handling, and service contracts.
- Favor small, composable, reusable components and scoped SCSS.
- Prefer semantic design tokens over one-off color and spacing constants.
- Avoid `!important`, global selector overrides, and duplicated component styles unless well justified.
- Never bypass existing guards, permission checks, or feature flags.

### Accessibility

- Use semantic HTML and accessible component APIs.
- Keep all controls keyboard-operable with visible focus styles.
- Give icon-only controls accessible names.
- Do not communicate critical status only by color.
- Check text contrast, input labels, tooltips, table headings, and dialog focus behavior.

### Performance

- Preserve large-table performance, virtualization/pagination where present, and chart responsiveness.
- Avoid expensive template computations, unnecessary subscriptions, and redundant API calls.
- Do not add heavy dependencies for a minor visual improvement.

### Data integrity

- Show server-provided task/model/queue state accurately.
- Preserve IDs, timestamps, metric units, sorting semantics, and filter behavior.
- Do not rename domain concepts in ways that mislead ClearML users.

## 9. Change safety and review

Before changing a shared component or stylesheet, inspect where it is used. If it is used on excluded pages, either keep the change compatible or create an authenticated-app-scoped alternative.

Never:

- Delete functionality because it complicates visual design.
- Rewrite backend endpoints to suit a mockup.
- Replace real charts with static images.
- Remove audit/security-relevant notices or permission states.
- Introduce production-only runtime network dependencies.
- Alter login/sign-up/create-account rendering or behavior.
- Commit secrets, `.env` values, or local proxy targets.

For each substantive change, review `git diff` before completion. Explicitly look for accidental changes in routes, shared styles, dependencies, API interactions, and excluded auth components.

## 10. Definition of project success

The redesign succeeds when users can perform their existing ClearML MLOps workflows in a noticeably cleaner, more coherent interface **without losing functionality**.

Success criteria:

- Authenticated application pages share consistent design tokens and interaction patterns.
- Navigation, experiment tables, experiment details, model/dataset views, and orchestration views are clearer where implemented.
- Data-dense workflows remain fast and discoverable.
- Existing API integrations and task/model actions continue to work.
- Tests/builds and visual regression checks have been run to the extent supported by the environment.
- **Login, Sign up, Create Account, and all other authentication/account-onboarding experiences remain unchanged.**
- `docs/ui-redesign/PLAN.md` and `PROGRESS.md` accurately describe the work.

## 11. Agent response protocol

At the start of each task, briefly state: (1) the specific screen or component being changed, (2) the user-visible outcome, and (3) the verification you will perform.

Then execute the work. Do not stop after proposing a plan if implementation is possible. Make reasonable local design decisions independently, but do not cross the explicit scope boundaries.

At the end, report:

1. What changed, including principal files/routes.
2. How it was verified, with actual results.
3. Any unverified areas or regressions.
4. The next highest-value in-scope slice.

**Golden rule:** modernize ClearML's presentation, preserve ClearML's behavior, and leave authentication/account creation completely untouched.
