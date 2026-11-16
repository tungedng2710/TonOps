// Model registry browser checks with isolated API fixtures. No live data is changed.
import assert from 'node:assert/strict';
import {createReadStream, existsSync, statSync} from 'node:fs';
import {mkdir, rm, writeFile} from 'node:fs/promises';
import {createServer} from 'node:http';
import {extname, resolve, sep} from 'node:path';
import {parseArgs} from 'node:util';
import {chromium} from '@playwright/test';

const {values} = parseArgs({options: {
  build: {type: 'string'}, artifacts: {type: 'string'}
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
const project = {id: 'fixture-project', name: 'Vision / Vehicle detection', company: {id: 'workspace'},
  user: {id: 'fixture-user', name: 'ML Engineer'}, basename: 'Vehicle detection'};
const model = {id: 'fixture-model-v2', name: 'vehicle-detector', project, company: {id: 'workspace'},
  user: {id: 'fixture-user', name: 'ML Engineer'}, framework: 'PyTorch', ready: false,
  created: '2026-11-10T08:00:00Z', last_update: '2026-11-10T08:00:00Z', last_change: '2026-11-10T08:00:00Z',
  uri: 's3://bucket/models/vehicle.pt', parent: {id: 'fixture-model-v1'}, tags: ['vision', 'version:2.0.0'], system_tags: []};
const previous = {...model, id: 'fixture-model-v1', ready: true, tags: ['version:1.0.0'], parent: null};
const results = {mode: 'isolated fixtures; no live writes', checks: []};
let currentPage;
async function fixture({empty = false, failUpload = false, failCreate = false, failVersions = false, readonly = false} = {}) {
  const context = await browser.newContext({viewport: {width: 1440, height: 1000}, reducedMotion: 'reduce'});
  const page = await context.newPage(); currentPage = page; page.setDefaultTimeout(10000);
  
  const writes = []; const errors = []; let uploadCount = 0; let versionAttempts = 0;
  page.on('pageerror', error => errors.push(error.message));
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.pathname.startsWith('/files')) {
      writes.push({action: 'upload', body: route.request().postData()}); uploadCount++;
      if (failUpload && uploadCount === 1) return route.fulfill({status: 503, json: {message: 'Upload unavailable'}});
      const body = route.request().postData();
      const path = body.match(/name="(models\/[^"\r\n]+)"/)?.[1];
      return route.fulfill({json: [path]});
    }
    if (url.hostname === 'updates.clear.ml') return route.fulfill({json: {}});
    if (url.origin !== base) return route.abort();
    if (!url.pathname.includes('/service/1/api/')) {
      if (url.pathname === '/configuration.json') return route.fulfill({json: {displayedServerUrls: {filesServer: '/files'}}});
      return route.continue();
    }
    const action = url.pathname.split('/').pop();
    const body = route.request().postDataJSON() || {};
    const selected = body.id?.[0] === previous.id ? previous : model;
    if (action === 'models.create') {
      writes.push({action, body});
      if (failCreate) return route.fulfill({status: 403, json: {meta: {result_code: 403, result_msg: 'Forbidden'}, data: {}}});
      return route.fulfill({json: {meta: {result_code: 200}, data: {id: 'created-draft'}}});
    }
    if (failVersions && action === 'models.get_all_ex' && body.name && versionAttempts++ === 0) return route.fulfill({status: 503,
      json: {meta: {result_code: 503, result_msg: 'Unavailable'}, data: {}}});
    const data = {
      'login.supported_modes': {authenticated: true, basic: {enabled: true}},
      'users.get_preferences': {preferences: {version: 1, views: {neverShowPopupAgain: ['tip-of-the-day']}}},
      'users.get_current_user': {user: {id: 'fixture-user', name: 'ML Engineer', role: 'user', company: {id: 'workspace'}}, settings: {}, getting_started: {}},
      'iam.status': {enabled: true}, 'iam.me': {user: {must_change_password: false}},
      'projects.get_by_id': {project}, 'projects.get_all_ex': {projects: [project]}, 'projects.get_all': {projects: [project]},
      'projects.get_user_names': {users: []}, 'projects.get_all_user_names': {users: []},
      'projects.get_task_tags': {tags: [], system_tags: []}, 'projects.get_project_tags': {tags: [], system_tags: []}, 'projects.get_model_tags': {tags: [], system_tags: []},
      'models.get_all_ex': {models: empty || (body.scroll_id && !body.refresh_scroll) ? [] : body.name ? [model, previous] : [model], scroll_id: body.name ? undefined : 'fixture-scroll'},
      'models.get_by_id_ex': {models: [{...selected, ...(readonly ? {company: null, readOnly: true} : {})}]},
      'models.get_frameworks': {frameworks: ['PyTorch']}, 'models.get_all': {models: []},
      'server.report_stats_option': {supported: false, enabled: false}, 'server.info': {version: 'fixture'},
      'auth.get_credentials': {credentials: []}, 'workers.get_all': {workers: []},
      'serving.get_endpoints': {endpoints: [{endpoint: 'Fixture model endpoint', model: model.name,
        url: 'http://inference.example/predict/model', instances: 1, requests: 7,
        requests_min: 2, latency_ms: 15, uptime_sec: 60, last_update: model.created}]},
      'serving.get_loading_instances': {instances: []},
      'serving.get_endpoint_details': {endpoint: 'Fixture model endpoint', model: model.name,
        url: 'http://inference.example/predict/model', model_source: 'PyTorch',
        instances: [{id: 'fixture-instance', uptime_sec: 60, requests: 7, requests_min: 2, latency_ms: 15,
          reference: [{type: 'model', value: model.id}]}]},
      'serving.get_endpoint_metrics_history': {total: {}, instances: []},
    };
    return route.fulfill({json: {meta: {result_code: 200}, data: data[action] || {}}});
  });
  return {page, writes, async close() { assert.deepEqual(errors, [], 'No browser errors'); await context.close(); }};
}
async function shot(page, name) { await page.screenshot({path: resolve(artifacts, name), animations: 'disabled'}); }
async function fillRegistration(page, source = 'file') {
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('Model name', {exact: true}).fill('vehicle-detector');
  await dialog.getByLabel('Version', {exact: true}).fill('3.0.0');
  if (source === 'file') await dialog.getByLabel('Model weights or model package').setInputFiles({name: "model's (v3).pt", mimeType: 'application/octet-stream', buffer: Buffer.from('fixture weights')});
  else { await dialog.getByLabel('Model source', {exact: true}).selectOption('uri'); await dialog.getByLabel('Storage URI').fill('s3://bucket/model.pt'); }
  return dialog;
}
try {
  const main = await fixture();
  await main.page.goto(base + '/projects/fixture-project/models');
  await main.page.getByRole('heading', {name: 'Registered models', exact: true}).waitFor();
  assert.equal(new URL(main.page.url()).pathname, '/models/registry/fixture-project', 'Legacy project route redirects to top-level management');
  await main.page.getByRole('heading', {name: 'Model management', exact: true}).waitFor();
  assert.equal(await main.page.getByRole('link', {name: 'Model management', exact: true}).getAttribute('aria-current'), 'page');
  const managementNav = main.page.getByRole('navigation', {name: 'Model management views'});
  const hubUrl = main.page.url();
  await managementNav.getByRole('link', {name: 'Endpoints', exact: true}).click();
  await main.page.locator('sm-serving-table').getByText('Fixture model endpoint', {exact: true}).waitFor();
  await shot(main.page, 'management-endpoints.png');
  await managementNav.getByRole('link', {name: 'Loading', exact: true}).click();
  await main.page.waitForURL(url => url.pathname === '/models/endpoints/loading');
  await managementNav.getByRole('link', {name: 'Model hub', exact: true}).click();
  await main.page.getByRole('heading', {name: 'Registered models', exact: true}).waitFor();
  assert.equal(main.page.url(), hubUrl, 'Hub tab preserves project and table query state');
  results.checks.push('Unified management navigation, legacy project redirect, live/loading endpoint tabs and independent query state');
  await shot(main.page, 'registry-desktop.png');
  await main.page.getByRole('button', {name: 'Register model', exact: true}).click();
  let dialog = await fillRegistration(main.page);
  await shot(main.page, 'registration-desktop.png');
  await dialog.getByRole('button', {name: 'Register draft', exact: true}).click();
  await dialog.waitFor({state: 'detached'});
  assert.equal(main.writes[0].body.ready, false);
  assert.equal(main.writes[0].body.project, project.id);
  assert.deepEqual(main.writes[0].body.tags, ['version:3.0.0']);
  assert.equal(main.writes[1].action, 'upload');
  assert.ok(main.writes[1].body.includes('fixture weights'));
  results.checks.push('GUI file registration creates a real draft then multipart upload; name/project/version payloads');
  await main.page.getByRole('button', {name: 'Register model', exact: true}).click();
  dialog = await fillRegistration(main.page, 'uri');
  await dialog.getByRole('button', {name: 'Register draft', exact: true}).click();
  await dialog.waitFor({state: 'detached'});
  assert.equal(main.writes.at(-1).body.uri, 's3://bucket/model.pt');
  assert.equal(main.writes.length, 3, 'URI registration does not reupload');
  await main.page.getByRole('button', {name: 'SDK / API', exact: true}).click();
  await main.page.getByRole('dialog').getByText('Python · upload and register', {exact: true}).waitFor();
  assert.ok((await main.page.getByRole('dialog').locator('pre').first().innerText()).includes('auto_delete_file=False'));
  await main.page.getByRole('dialog').getByText('REST API · register an existing storage object', {exact: true}).click();
  assert.ok((await main.page.getByRole('dialog').locator('pre').nth(1).innerText()).includes('/models.create'));
  await main.page.keyboard.press('Escape');
  await main.page.goto(base + '/projects/fixture-project/models/fixture-model-v2/general');
  await main.page.getByRole('heading', {name: 'Build on this model'}).waitFor();
  const hub = main.page.locator('sm-model-hub-panel');
  await hub.getByRole('link').filter({hasText: '1.0.0'}).waitFor();
  assert.ok((await hub.getByRole('link', {name: 'parent fixture-model-v1', exact: true}).getAttribute('href')).endsWith('/fixture-model-v1/general'), 'Joined parent object resolves to its ID');
  await shot(main.page, 'versions-desktop.png');
  await main.page.locator('sm-model-info-header [data-id="fullscreenIcon"]').click();
  await main.page.waitForURL(url => url.pathname.endsWith('/fixture-model-v2/output/general'));
  await main.page.locator('sm-model-info-header [data-id="experimentDetailsView"]').click();
  await main.page.waitForURL(url => url.pathname.endsWith('/fixture-model-v2/general'));
  await main.page.getByRole('heading', {name: 'Registered models', exact: true}).waitFor();
  results.checks.push('Full-screen model detail and return to registry split view');
  await hub.getByRole('button', {name: 'Add version', exact: true}).click();
  dialog = await fillRegistration(main.page, 'uri');
  await dialog.getByRole('button', {name: 'Register draft', exact: true}).click();
  await dialog.waitFor({state: 'detached'});
  assert.equal(main.writes.at(-1).body.parent, model.id);
  assert.deepEqual(main.writes.at(-1).body.tags, ['vision', 'version:3.0.0']);
  await hub.getByRole('button', {name: 'Use model', exact: true}).click();
  assert.ok((await hub.locator('pre').innerText()).includes(model.id));
  await hub.getByRole('button', {name: 'Serve & call', exact: true}).click();
  await hub.getByLabel('Serving service ID').fill("service'id");
  await hub.getByLabel('Inference URL').fill('https://inference.example/serve/vehicle');
  await hub.getByLabel('JSON request body').fill('{"instances": [[1,2,3]]}');
  assert.equal(await hub.locator('pre').count(), 3);
  assert.ok((await hub.locator('pre').first().innerText()).includes(model.id));
  await shot(main.page, 'serving-desktop.png');
  await hub.getByLabel('JSON request body').fill('{invalid');
  await hub.getByRole('alert').waitFor();
  assert.equal(await hub.locator('pre').count(), 1, 'Invalid JSON hides request code');
  await hub.getByLabel('JSON request body').fill('{}');
  for (const width of [1280, 1024, 768, 390]) {
    await main.page.setViewportSize({width, height: 1000});
    assert.ok(await main.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `No document overflow at ${width}`);
  }
  await main.page.locator('sm-models-table').waitFor({state: 'hidden'});
  await shot(main.page, 'serving-narrow.png');
  await hub.getByRole('button', {name: 'Versions', exact: true}).click();
  await hub.getByRole('link').filter({hasText: '1.0.0'}).click();
  await main.page.waitForURL('**/fixture-model-v1/general');
  await main.page.goBack();
  await main.page.waitForURL(url => url.pathname.endsWith('/fixture-model-v2/general'));
  await main.close();
  const redirect = await fixture();
  await redirect.page.goto(base + '/endpoints/active?order=-requests');
  await redirect.page.locator('sm-serving-table').getByText('Fixture model endpoint', {exact: true}).waitFor();
  assert.equal(new URL(redirect.page.url()).pathname, '/models/endpoints/active');
  assert.equal(new URL(redirect.page.url()).searchParams.get('order'), '-requests');
  await redirect.close();
  results.checks.push('Legacy endpoint route preserves sort query parameters');
  const all = await fixture();
  await all.page.goto(base + '/projects/*/models');
  await all.page.getByRole('button', {name: 'Register model', exact: true}).click();
  dialog = await fillRegistration(all.page, 'uri');
  await dialog.getByRole('combobox', {name: 'Project', exact: true}).fill('Vehicle');
  await all.page.getByRole('option', {name: project.name, exact: true}).click();
  await dialog.getByRole('button', {name: 'Register draft', exact: true}).click();
  await dialog.waitFor({state: 'detached'});
  assert.equal(all.writes[0].body.project, project.id, 'Resolve shared project selector name to project ID');
  await all.close();
  results.checks.push('All-project registry registration with searchable existing-project selector');
  results.checks.push('Version parent/tag payloads, exact-version download, serving CLI, JSON validation, call code, version deep links/back, 1280/1024/768/390 layouts');
  const retry = await fixture({failUpload: true});
  await retry.page.goto(base + '/projects/fixture-project/models');
  await retry.page.getByRole('button', {name: 'Register model', exact: true}).click();
  dialog = await fillRegistration(retry.page);
  await dialog.getByRole('button', {name: 'Register draft', exact: true}).click();
  await dialog.getByRole('alert').filter({hasText: 'browser could not confirm the upload'}).waitFor();
  await shot(retry.page, 'upload-failed.png');
  await dialog.getByRole('button', {name: 'Retry upload', exact: true}).click();
  await dialog.waitFor({state: 'detached'});
  assert.equal(retry.writes.filter(write => write.action === 'models.create').length, 1);
  assert.equal(retry.writes.filter(write => write.action === 'upload').length, 2);
  await retry.close();
  results.checks.push('Failed upload retains draft and retries without duplicate registration');
  const denied = await fixture({failCreate: true});
  await denied.page.goto(base + '/projects/fixture-project/models');
  await denied.page.getByRole('button', {name: 'Register model', exact: true}).click();
  dialog = await fillRegistration(denied.page, 'uri');
  await dialog.getByRole('button', {name: 'Register draft', exact: true}).click();
  await dialog.getByRole('alert').filter({hasText: 'Registration failed'}).waitFor();
  assert.equal(denied.writes.length, 1, 'No upload when registration fails');
  await denied.close();
  const versionError = await fixture({failVersions: true});
  await versionError.page.goto(base + '/projects/fixture-project/models/fixture-model-v2/general');
  await versionError.page.getByRole('alert').filter({hasText: 'Unable to load versions'}).waitFor();
  await versionError.page.getByRole('button', {name: 'Retry', exact: true}).click();
  await versionError.page.locator('sm-model-hub-panel .version-row').first().waitFor();
  await versionError.close();
  results.checks.push('Version lookup failure and successful retry');
  const readonly = await fixture({readonly: true});
  await readonly.page.goto(base + '/projects/fixture-project/models/fixture-model-v2/general');
  await readonly.page.getByRole('heading', {name: 'Build on this model'}).waitFor();
  assert.equal(await readonly.page.getByRole('button', {name: 'Add version', exact: true}).isDisabled(), true);
  await readonly.close();
  const empty = await fixture({empty: true});
  await empty.page.goto(base + '/projects/fixture-project/models');
  await empty.page.getByRole('heading', {name: 'Registered models', exact: true}).waitFor();
  await shot(empty.page, 'registry-empty.png');
  await empty.page.getByRole('button', {name: 'Register model', exact: true}).click();
  dialog = empty.page.getByRole('dialog');
  await dialog.getByRole('button', {name: 'Register draft', exact: true}).click();
  assert.equal(empty.writes.length, 0, 'Invalid forms do not submit');
  await empty.close();
  results.checks.push('Create denied, read-only model actions, empty registry and required-field validation');
  await rm(resolve(artifacts, 'failure.png'), {force: true});
  await writeFile(resolve(artifacts, 'results.json'), JSON.stringify(results, null, 2));
  console.log(JSON.stringify(results, null, 2));
} catch (error) {
  if (currentPage && !currentPage.isClosed()) await shot(currentPage, 'failure.png');
  throw error;
} finally { await browser.close(); await new Promise(done => server.close(done)); }
