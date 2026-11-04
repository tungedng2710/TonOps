// Isolated presentation checks. All API responses are fixtures; no live account
// or ClearML operations are used. Run against an existing development build.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createReadStream, existsSync, statSync} from 'node:fs';
import {mkdir, readFile, rm, writeFile} from 'node:fs/promises';
import {createServer} from 'node:http';
import {extname, resolve, sep} from 'node:path';
import {parseArgs} from 'node:util';
import {chromium} from '@playwright/test';

const {values} = parseArgs({options: {
  build: {type: 'string'}, artifacts: {type: 'string'}, baseline: {type: 'string'},
  'capture-baseline': {type: 'boolean', default: false}
}});
assert.ok(values.build && values.artifacts, 'Provide --build <browser directory> --artifacts <directory>');
const root = resolve(values.build);
const artifacts = resolve(values.artifacts);
assert.ok(existsSync(resolve(root, 'index.html')), 'Build the application first');
await mkdir(artifacts, {recursive: true});
const mime = {'.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css',
  '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png',
  '.woff2': 'font/woff2', '.woff': 'font/woff', '.ttf': 'font/ttf', '.ico': 'image/x-icon'};
const server = createServer((request, response) => {
  let file = resolve(root, '.' + new URL(request.url, 'http://localhost').pathname);
  if (!file.startsWith(root + sep)) file = resolve(root, 'index.html');
  if (!existsSync(file) || statSync(file).isDirectory()) file = resolve(root, 'index.html');
  response.setHeader('Content-Type', mime[extname(file)] || 'application/octet-stream');
  createReadStream(file).pipe(response);
});
await new Promise(done => server.listen(0, '127.0.0.1', done));
const base = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch(process.env.CHROME_BIN ? {executablePath: process.env.CHROME_BIN} : {});
const results = {mode: 'mocked APIs; live MLOps operations not verified', checks: [], authImages: {}};
const longProjectName = 'Computer vision / Vehicle detection / Production candidate with a long project name';
const project = {id: 'fixture-project', name: longProjectName, user: {id: 'fixture-user', name: 'ML Engineer'},
  last_update: '2026-01-15T09:00:00Z', visibility: 'private', stats: {active: {total_tasks: 3,
    status_count: {completed: 1, in_progress: 1, failed: 1}}}};
const task = {id: 'fixture-task', name: 'Vehicle detector training with a long experiment name',
  project: {id: project.id, name: project.name}, status: 'in_progress', type: 'training', last_update: project.last_update};
const navLinks = [['Home', '/home'], ['Workers and queues', '/workers-and-queues'],
  ['Model endpoints', '/endpoints/active'], ['Datasets', '/datasets'], ['Projects', '/dashboard'], ['Pipelines', '/pipelines']];
let currentPage;

async function fixturePage({authenticated = true, state = 'empty', nested = false} = {}) {
  const context = await browser.newContext({viewport: {width: 1440, height: 900}, reducedMotion: 'reduce'});
  const page = await context.newPage();
  currentPage = page;
  page.setDefaultTimeout(10000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.origin !== base) {
      if (url.hostname === 'updates.clear.ml') return route.fulfill({json: {}});
      return route.abort();
    }
    if (!url.pathname.includes('/service/1/api/')) return route.continue();
    const action = url.pathname.split('/').pop();
    if (action === 'projects.get_all_ex' && state === 'loading') await new Promise(done => setTimeout(done, 2000));
    if (action === 'projects.get_all_ex' && state === 'error') {
      return route.fulfill({status: 503, json: {meta: {result_code: 503, result_msg: 'Fixture unavailable'}, data: {}}});
    }
    const data = {
      'login.supported_modes': {authenticated, basic: {enabled: true}},
      'users.get_preferences': {preferences: {version: 1, views: {neverShowPopupAgain: ['tip-of-the-day']},
        rootProjects: {defaultNestedModeForFeature: {datasets: nested, pipelines: nested}}}},
      'users.get_current_user': {user: {id: 'fixture-user', name: 'ML Engineer', role: 'user',
        company: {id: 'fixture-workspace', name: 'Workspace'}}, settings: {}, getting_started: {}},
      'iam.status': {enabled: true, self_signup_enabled: true},
      'iam.me': {user: {must_change_password: false}},
      'projects.get_all_ex': {projects: ['populated', 'loading'].includes(state) ? [project] : []},
      'projects.get_all': {projects: []}, 'projects.get_user_names': {users: []},
      'tasks.get_all_ex': {tasks: state === 'populated' ? [task] : []},
      'server.report_stats_option': {supported: false, enabled: false}, 'server.info': {version: 'fixture'},
      'auth.get_credentials': {credentials: []}, 'workers.get_all': {workers: []},
      'workers.get_activity_report': {total: {dates: [], counts: []}, active: {dates: [], counts: []}},
      'queues.get_all_ex': {queues: []}, 'queues.get_queue_metrics': {queues: []},
      'projects.get_project_tags': {tags: [], system_tags: []}, 'tasks.get_types': {types: []},
      'projects.get_all_user_names': {users: []}
    };
    return route.fulfill({json: {meta: {result_code: 200}, data: data[action] || {}}});
  });
  return {page, async close() {
    assert.deepEqual(errors, [], 'Unexpected browser runtime errors');
    await context.close();
  }};
}

async function screenshot(page, name) {
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({path: resolve(artifacts, name), animations: 'disabled'});
}

async function checkShell(page, widths, tabbed = false) {
  for (const width of widths) {
    await page.setViewportSize({width, height: 900});
    const layout = await page.evaluate(() => {
      const header = document.querySelector('sm-header');
      const nav = document.querySelector('sm-side-nav');
      const buttons = document.querySelector('sm-header .right-buttons');
      const tabs = document.querySelector('sm-header-navbar-tabs');
      return {body: document.documentElement.scrollWidth, viewport: innerWidth,
        nav: nav.getBoundingClientRect().toJSON(), header: header.getBoundingClientRect().toJSON(),
        buttons: buttons.getBoundingClientRect().toJSON(), tabs: tabs?.getBoundingClientRect().toJSON(),
        labels: [...nav.querySelectorAll('.nav-label')].map(label => getComputedStyle(label).display)};
    });
    if (values['capture-baseline']) {
      if (layout.body > width || layout.buttons.right > width) {
        results.checks.push(`Baseline layout overflow at ${width}px (${tabbed ? 'tabbed' : 'tabless'} header)`);
      }
    } else {
      assert.ok(layout.body <= width, `Document overflow at ${width}px`);
      assert.ok(layout.buttons.right <= width && layout.buttons.left >= layout.nav.right, `Header actions overflow at ${width}px`);
    }
    assert.equal(Math.round(layout.header.height), 64, 'Preserve feature viewport height');
    if (!values['capture-baseline']) {
      assert.equal(layout.nav.width, width > 1100 ? 216 : 64);
      assert.ok(layout.labels.every(display => (display !== 'none') === (width > 1100)), 'Responsive navigation labels');
      if (tabbed) assert.ok(layout.tabs.right <= layout.buttons.left, `Context tabs overlap actions at ${width}px`);
    }
  }
}

try {
  const home = await fixturePage({state: 'populated'});
  await home.page.goto(base + '/home');
  await home.page.getByRole('heading', {name: 'Your projects', exact: true}).waitFor();
  assert.deepEqual(await home.page.locator('sm-side-nav a').evaluateAll(links => links.map(link =>
    [link.getAttribute('aria-label'), link.getAttribute('href')])), navLinks, 'Preserve all existing navigation destinations');
  assert.equal(await home.page.getByRole('link', {name: 'Home', exact: true}).getAttribute('aria-current'), 'page');
  await screenshot(home.page, 'home-populated-desktop.png');
  await checkShell(home.page, [1440, 1280, 1101, 1100, 1024, 768, 390]);
  await screenshot(home.page, 'home-populated-narrow.png');
  await home.page.setViewportSize({width: 1440, height: 900});

  if (!values['capture-baseline']) {
    const profile = home.page.getByRole('button', {name: 'Open profile menu'});
    await profile.focus();
    await home.page.keyboard.press('Enter');
    await home.page.getByRole('menuitem', {name: 'My profile', exact: true}).waitFor();
    await home.page.getByRole('menuitem', {name: 'Logout', exact: true}).waitFor();
    await home.page.keyboard.press('Escape');
    assert.equal(await profile.evaluate(element => element === document.activeElement), true, 'Menu restores focus');
    // Focus restoration is programmatic; test :focus-visible using real Tab input.
    await home.page.keyboard.press('Shift+Tab');
    await home.page.keyboard.press('Tab');
    assert.equal(await profile.evaluate(element => element === document.activeElement), true, 'Tab reaches the profile trigger');
    const focus = await profile.evaluate(element => getComputedStyle(element).outlineStyle);
    assert.notEqual(focus, 'none', 'Keyboard focus remains visible');
    await home.page.getByRole('button', {name: 'Help and resources'}).click();
    await home.page.getByRole('menuitem', {name: 'ClearML Python Package setup'}).waitFor();
    await home.page.keyboard.press('Escape');
    await home.page.getByRole('button', {name: 'Search workspace'}).click();
    await home.page.locator('sm-global-search-dialog').waitFor();
    await home.page.keyboard.press('Escape');
    await home.page.locator('sm-global-search-dialog').waitFor({state: 'detached'});
    await home.page.keyboard.press('Control+k');
    await home.page.locator('sm-global-search-dialog').waitFor();
    await home.page.keyboard.press('Escape');
    results.checks.push('Profile menu Enter/Escape/focus restoration, help menu, search button and Ctrl+K');
  }
  await home.page.getByRole('link', {name: 'Workers and queues', exact: true}).focus();
  await home.page.keyboard.press('Enter');
  await home.page.waitForURL('**/workers-and-queues/workers');
  await home.page.locator('sm-header-navbar-tabs').getByRole('tab', {name: /^workers$/i}).waitFor();
  await screenshot(home.page, 'workers-desktop.png');
  assert.equal(await home.page.getByRole('link', {name: 'Workers and queues', exact: true}).getAttribute('aria-current'), 'page');
  await checkShell(home.page, [1440, 1280, 1024, 768, 390], true);
  await screenshot(home.page, 'workers-narrow.png');
  if (!values['capture-baseline']) {
    await home.page.locator('sm-header-navbar-tabs').getByRole('tab', {name: /^workers$/i}).focus();
    await home.page.keyboard.press('ArrowRight');
    await home.page.keyboard.press('Enter');
    await home.page.waitForURL('**/workers-and-queues/queues');
    // Orchestration debounces route context by 100ms. Let that existing work
    // settle before sending a back/forward event in this automated sequence.
    await home.page.waitForTimeout(200);
    await home.page.goBack();
    await home.page.waitForURL('**/workers-and-queues/workers');
    await home.page.locator('sm-header-navbar-tabs').getByRole('tab', {name: /^workers$/i, selected: true}).waitFor();
    results.checks.push('Context tabs remain keyboard-operable at 390px');
  }
  await home.page.setViewportSize({width: 1280, height: 900});
  await home.page.locator('sm-header-navbar-tabs').getByRole('tab', {name: /^queues$/i}).click();
  await home.page.waitForURL('**/workers-and-queues/queues');
  await home.page.locator('sm-header-navbar-tabs').getByRole('tab', {name: /^queues$/i}).getAttribute('aria-selected').then(selected => assert.equal(selected, 'true'));
  await home.page.waitForTimeout(200);
  await home.page.goBack();
  await home.page.waitForURL('**/workers-and-queues/workers');
  await home.page.goBack();
  await home.page.waitForURL('**/home');
  await home.page.goForward();
  await home.page.waitForURL('**/workers-and-queues/workers');
  await home.close();
  results.checks.push('Existing navigation links, active states, keyboard navigation, tabs and browser back/forward');

  for (const state of ['empty', 'loading', 'error']) {
    const fixture = await fixturePage({state});
    await fixture.page.goto(base + '/home');
    if (state === 'empty') await fixture.page.getByText('A fresh start', {exact: true}).waitFor();
    if (state === 'loading') await fixture.page.getByRole('status', {name: 'Loading your dashboard'}).waitFor();
    if (state === 'error') await fixture.page.getByRole('alert').filter({hasText: 'Unable to load your dashboard'}).waitFor();
    await screenshot(fixture.page, `home-${state}.png`);
    await fixture.close();
  }
  const nested = await fixturePage({nested: true});
  await nested.page.goto(base + '/home');
  await nested.page.locator('sm-side-nav').waitFor();
  assert.equal(await nested.page.getByRole('link', {name: 'Datasets', exact: true}).getAttribute('href'), '/datasets/simple/*/projects');
  assert.equal(await nested.page.getByRole('link', {name: 'Pipelines', exact: true}).getAttribute('href'), '/pipelines/*/projects');
  await nested.page.setViewportSize({width: 1280, height: 300});
  const lastLink = nested.page.getByRole('link', {name: 'Pipelines', exact: true});
  await lastLink.focus();
  await lastLink.scrollIntoViewIfNeeded();
  assert.ok(await lastLink.evaluate(element => element.getBoundingClientRect().bottom <= innerHeight), 'Navigation scrolls on short screens');
  await nested.close();
  results.checks.push('Populated/long-text, empty, loading and error states; nested-mode links; short-screen scrolling');

  for (const [route, heading, name] of [['/login', 'Welcome back', 'login'], ['/login/signup', 'Create your account', 'signup']]) {
    const fixture = await fixturePage({authenticated: false});
    await fixture.page.goto(base + route);
    await fixture.page.getByRole('heading', {name: heading, exact: true}).waitFor();
    assert.equal(await fixture.page.locator('sm-side-nav, sm-header').count(), 0, 'Authenticated shell is absent on excluded pages');
    assert.equal(await fixture.page.locator('main').evaluate(element => getComputedStyle(element).getPropertyValue('--workspace-shell-accent')), '');
    for (const width of [1440, 390]) {
      await fixture.page.setViewportSize({width, height: 900});
      const file = `${name}-${width}.png`;
      await screenshot(fixture.page, file);
      const data = await readFile(resolve(artifacts, file));
      results.authImages[file] = createHash('sha256').update(data).digest('hex');
      if (values.baseline) assert.deepEqual(data, await readFile(resolve(values.baseline, file)), `${file}: excluded page must be pixel-identical`);
    }
    await fixture.close();
  }
  results.checks.push('Login/signup shell isolation; desktop and narrow screenshots' + (values.baseline ? ' pixel-identical to baseline' : ' captured'));
  await rm(resolve(artifacts, 'failure.png'), {force: true});
  await writeFile(resolve(artifacts, 'results.json'), JSON.stringify(results, null, 2) + '\n');
  console.log(JSON.stringify(results, null, 2));
} catch (error) {
  if (currentPage && !currentPage.isClosed()) await screenshot(currentPage, 'failure.png');
  throw error;
} finally {
  await browser.close();
  await new Promise(done => server.close(done));
}
