// Isolated browser fixtures for profile/settings presentation and existing actions.
// Never sends requests to a live server or changes application guards/routes.
import assert from 'node:assert/strict';
import {createReadStream, existsSync, statSync} from 'node:fs';
import {mkdir, readFile, rm, writeFile} from 'node:fs/promises';
import {createServer} from 'node:http';
import {resolve, extname, sep} from 'node:path';
import {parseArgs} from 'node:util';
import {chromium} from '@playwright/test';
const {values} = parseArgs({options: {build: {type: 'string'}, artifacts: {type: 'string'}, baseline: {type: 'string'}, 'capture-baseline': {type: 'boolean', default: false}}});
assert.ok(values.build && values.artifacts, 'Provide --build and --artifacts');
const root = resolve(values.build), artifacts = resolve(values.artifacts);
assert.ok(existsSync(resolve(root, 'index.html')), 'Build the app first');
await mkdir(artifacts, {recursive: true});
const mime = {'.html':'text/html', '.js':'application/javascript', '.css':'text/css', '.json':'application/json', '.svg':'image/svg+xml', '.png':'image/png', '.woff2':'font/woff2', '.woff':'font/woff', '.ttf':'font/ttf'};
const server = createServer((request, response) => {
  let file = resolve(root, '.' + new URL(request.url, 'http://localhost').pathname);
  if (!file.startsWith(root + sep) || !existsSync(file) || statSync(file).isDirectory()) file = resolve(root, 'index.html');
  response.setHeader('Content-Type', mime[extname(file)] || 'application/octet-stream');
  createReadStream(file).pipe(response);
});
await new Promise(done => server.listen(0, '127.0.0.1', done));
const base = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch(process.env.CHROME_BIN ? {executablePath: process.env.CHROME_BIN} : {});
const results = {mode: 'Isolated API fixtures; live server operations not verified', checks: [], baselineLayoutIssues: []};
let currentPage;
async function fixture({state = 'populated', admin = false} = {}) {
  const context = await browser.newContext({viewport: {width:1440, height:900}, reducedMotion: 'reduce'});
  const page = await context.newPage(); currentPage = page; page.setDefaultTimeout(10000);
  const errors = [], requests = [];
  let reportFailed = false;
  const user = {id:'fixture-user', username:'ml-engineer', name:'Alex Nguyen', display_name:'Alex Nguyen', given_name:'Alex', family_name:'Nguyen', bio:'Machine learning engineer. Building reproducible experiments and reliable models.', email:'alex@example.test', role:admin?'admin':'user', company:{id:'fixture-workspace', name:'Workspace'}, must_change_password:false};
  const projects = Array.from({length:4}, (_,i) => ({id:`project-${i}`, name:i===0?'Computer vision / Vehicle detection / Production candidate with a long project name':`Research project ${i}`, description:'Versioned experiments, datasets, and models with reproducible evaluation results.', visibility:i%2?'private':'public', last_update:'2026-11-01T09:00:00Z'}));
  page.on('pageerror', error => errors.push(error.message));
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.origin !== base) return url.hostname==='updates.clear.ml' ? route.fulfill({json:{}}) : route.abort();
    if (!url.pathname.includes('/service/1/api/')) return route.continue();
    const action = url.pathname.split('/').pop();
    const body = route.request().postDataJSON() || {};
    requests.push({action, body});
    const fail = () => route.fulfill({status:503, json:{meta:{result_code:503, result_msg:'Fixture unavailable'},data:{}}});
    if (action==='iam.get_profile' && state==='error') return fail();
    if (action==='iam.get_profile' && state==='loading') await new Promise(done => setTimeout(done,2000));
    if (action==='reports.get_all_ex' && state==='report-error' && !reportFailed) { reportFailed=true; return fail(); }
    if (action==='users.update') Object.assign(user,body);
    const person = {...user, id:body.username==='other-engineer'?'other-user':user.id, username:body.username||user.username, display_name:body.username==='other-engineer'?'Researcher with a very long display name for responsive testing':user.name};
    const reports = Array.from({length:body.page===1?1:6}, (_,i) => ({id:`report-${(body.page||0)*6+i}`, name:`Evaluation report ${(body.page||0)*6+i}`, comment:'Experiment results and analysis.', company:{id:user.company.id}, user:{id:person.id,name:person.display_name}, project:{id:'project-0', name:'.reports'}, tags:['evaluation'], system_tags:[], status:'published'}));
    const data = {
      'login.supported_modes':{authenticated:true,basic:{enabled:true}},
      'users.get_current_user':{user,settings:{},getting_started:{}},
      'users.get_preferences':{preferences:{version:1,views:{neverShowPopupAgain:['tip-of-the-day']}}},
      'users.update':{updated:1},'users.set_preferences':{},
      'iam.status':{enabled:true,self_signup_enabled:true},'iam.me':{user},
      'iam.get_profile':{user:person,projects:state==='empty'?[]:projects},
      'iam.search_profiles':{users:[],total:0},
      'reports.get_all_ex':{tasks:state==='empty'?[]:reports},
      'projects.get_all_ex':{projects:[]},'projects.get_all':{projects:[]},'projects.get_user_names':{users:[]},
      'auth.get_credentials':{credentials:[]},
      'server.report_stats_option':{supported:false,enabled:false},'server.info':{version:'fixture',api_version:'fixture'},
    };
    return route.fulfill({json:{meta:{result_code:200},data:data[action]||{}}});
  });
  return {page,requests,async close(){ assert.deepEqual(errors,[],'Unexpected runtime errors'); await context.close(); }};
}
async function snap(page,name,locator) {
  await page.waitForFunction(()=>!document.querySelector('sm-spinner .loader-container'));
  await page.evaluate(() => document.fonts.ready);
  await (locator||page).screenshot({path:resolve(artifacts,name),animations:'disabled'});
}
async function layout(page,name) {
  for (const width of [1440,1280,1024,768,390]) {
    await page.setViewportSize({width,height:900});
    await page.waitForFunction(()=>{
      const content=document.querySelector('sm-settings mat-drawer-content');
      return !content || Math.abs(parseFloat(getComputedStyle(content).marginLeft)-(innerWidth<=760?0:265))<1;
    });
    const sizes = await page.evaluate(() => ({width:innerWidth,document:document.documentElement.scrollWidth,overflow:[...document.querySelectorAll('sm-profiles,sm-webapp-configuration')].some(el=>el.scrollWidth>el.clientWidth+1)}));
    if (sizes.document>width || sizes.overflow) {
      if (values['capture-baseline']) results.baselineLayoutIssues.push(`${name} at ${width}px`);
      else assert.fail(`Overflow in ${name} at ${width}px: ${JSON.stringify(sizes)}`);
    }
    if(!values['capture-baseline']) {
      const header=page.locator('.profile-page-header');
      if(await header.count()) assert.ok((await header.boundingBox()).y+(await header.boundingBox()).height <= (await page.locator('.profile-layout').boundingBox()).y, 'Profile header must not overlap identity/content');
    }
  }
  await snap(page,`${name}-narrow.png`);
  await page.setViewportSize({width:1440,height:900});
}
try {
  const own = await fixture();
  await own.page.goto(base+'/user');
  await own.page.waitForURL('**/user/ml-engineer');
  await own.page.locator('.profile-identity').waitFor();
  await own.page.locator('sm-report-card').first().waitFor();
  assert.equal(await own.page.getByRole('link',{name:'Edit account settings'}).getAttribute('href'),'/settings/account');
  assert.equal(await own.page.locator('.project-card').first().getAttribute('href'),'/projects/project-0/overview');
  await snap(own.page,'profile-desktop.png');
  await layout(own.page,'profile');
  await own.page.getByRole('button',{name:'Load more reports'}).click();
  await own.page.waitForFunction(()=>document.querySelectorAll('sm-report-card').length===7);
  assert.equal(own.requests.filter(r=>r.action==='reports.get_all_ex').at(-1).body.page,1);
  await own.page.getByRole('button',{name:/new report/i}).click();
  await own.page.getByText('CREATE NEW REPORT',{exact:true}).waitFor();
  await own.page.keyboard.press('Escape');
  await own.page.getByRole('button',{name:'Find a profile',exact:true}).click();
  await own.page.getByLabel('Name or username').waitFor();
  await own.page.getByRole('button',{name:'Close profile search'}).click();
  await own.close();
  results.checks.push('Own-profile redirect, original project links, report pagination, report creation dialog and profile search');

  const other = await fixture();
  await other.page.goto(base+'/user/other-engineer');
  await other.page.locator('.profile-identity').waitFor();
  assert.equal(await other.page.getByRole('link',{name:'Edit account settings'}).count(),0);
  assert.equal(await other.page.getByRole('button',{name:/new report/i}).count(),0);
  await layout(other.page,'other-profile');
  await other.close();
  for (const state of ['empty','loading','error','report-error']) {
    const f=await fixture({state}); await f.page.goto(base+'/user/ml-engineer');
    if(state==='empty') await f.page.getByText(/^No projects to show/).waitFor();
    if(state==='loading') await f.page.getByText('Loading…',{exact:true}).waitFor();
    if(state==='error') await f.page.getByRole('alert').filter({hasText:'This profile is unavailable.'}).waitFor();
    if(state==='report-error') { await f.page.getByText('Unable to load reports.').waitFor(); await f.page.getByRole('button',{name:'Retry',exact:true}).click(); await f.page.locator('sm-report-card').first().waitFor(); }
    await snap(f.page,`profile-${state}.png`); await f.close();
  }
  results.checks.push('Other-profile owner controls absent; long names; empty/loading/error states; report retry');

  const settings=await fixture();
  await settings.page.goto(base+'/settings/account');
  await settings.page.getByRole('heading',{name:'Personal information'}).waitFor();
  await settings.page.locator('sm-user-credentials').waitFor();
  await settings.page.waitForFunction(()=>!document.querySelector('sm-spinner .loader-container'));
  await snap(settings.page,'account-desktop.png');
  const protectedStyles={};
  for(const [name,selector] of [['security','.password-card'],['cloud-keys','section[aria-label="Cloud access keys"]'],['api-keys','section[aria-label="API credentials"]']]) {
    const target=settings.page.locator(selector);
    await snap(settings.page,`protected-${name}.png`,target);
    protectedStyles[name]=await target.evaluate(el=>[el,...el.querySelectorAll('*')].map(node=>{
      const style=getComputedStyle(node);
      return Object.fromEntries(['display','fontFamily','fontSize','fontWeight','lineHeight','color','backgroundColor','borderRadius','borderWidth','padding','margin','gap','width','height'].map(key=>[key,style[key]]));
    }));
  }
  await writeFile(resolve(artifacts,'protected-styles.json'),JSON.stringify(protectedStyles,null,2));
  if(values.baseline) assert.deepEqual(protectedStyles,JSON.parse(await readFile(resolve(values.baseline,'protected-styles.json'),'utf8')),'Protected panel styles must remain identical');
  await settings.page.locator('sm-settings mat-drawer-content > .section').evaluate(el=>el.scrollTop=0);
  const save=settings.page.getByRole('button',{name:'Save changes',exact:true});
  assert.equal(await save.isDisabled(),true);
  await settings.page.locator('input[formControlName="name"]').fill('A');
  assert.equal(await save.isDisabled(),true);
  await settings.page.locator('input[formControlName="name"]').fill('Alex Updated');
  await save.click(); await settings.page.getByRole('status').filter({hasText:'Profile saved.'}).waitFor();
  assert.equal(settings.requests.find(r=>r.action==='users.update').body.name,'Alex Updated');
  assert.equal(settings.requests.some(r=>r.action==='iam.change_password'||r.action==='auth.create_credentials'),false);
  await layout(settings.page,'account');
  await settings.page.goto(base+'/settings/webapp-configuration');
  await settings.page.locator('sm-profile-preferences').waitFor();
  await snap(settings.page,'configuration-desktop.png');
  if(!values['capture-baseline']) {
    const nav=settings.page.getByRole('navigation',{name:'Settings sections'});
    assert.equal(await nav.getByRole('link',{name:'Configuration',exact:true}).getAttribute('aria-current'),'page');
    assert.deepEqual(await nav.getByRole('link').evaluateAll(links=>links.map(link=>link.getAttribute('href'))),['/settings/account','/settings/datastudio','/settings/webapp-configuration','/settings/storage-credentials']);
    const examples=settings.page.getByRole('switch',{name:"Don't show TonOps examples"});
    await examples.click(); assert.equal(await examples.getAttribute('aria-checked'),'true');
    await settings.page.waitForFunction(()=>JSON.parse(localStorage.getItem('_saved_state_')).rootProjects.hideExamples===true);
  }
  await layout(settings.page,'configuration');
  if(!values['capture-baseline']) {
    await settings.page.setViewportSize({width:390,height:900});
    const menu=settings.page.getByRole('button',{name:'Settings menu',exact:true});
    await menu.click();
    await settings.page.locator('button[aria-controls="settings-navigation"][aria-expanded="true"]').waitFor();
    const account=settings.page.getByRole('link',{name:'Account settings',exact:true});
    await account.focus(); await settings.page.keyboard.press('Enter');
    await settings.page.waitForURL('**/settings/account');
    await settings.page.locator('button[aria-controls="settings-navigation"][aria-expanded="false"]').waitFor();
    await menu.click(); await settings.page.getByRole('button',{name:'Close settings menu'}).click();
    await settings.page.locator('button[aria-controls="settings-navigation"][aria-expanded="false"]').waitFor();
  }
  await settings.close();
  const admin=await fixture({admin:true}); await admin.page.goto(base+'/settings/webapp-configuration');
  await admin.page.getByText('User Management',{exact:true}).waitFor(); await admin.close();
  results.checks.push('Account validation/disabled state/save payload; protected panel screenshots/styles captured; admin visibility');
  if(values.baseline) results.checks.push('Protected security/cloud/API panel computed styles identical to baseline');
  if(!values['capture-baseline']) results.checks.push('Settings routes/current-page semantics; configuration toggle persistence; narrow keyboard drawer');
  await rm(resolve(artifacts,'failure.png'),{force:true});
  await writeFile(resolve(artifacts,'results.json'),JSON.stringify(results,null,2)+'\n');
  console.log(JSON.stringify(results,null,2));
} catch(error) {
  if(currentPage&&!currentPage.isClosed()) await snap(currentPage,'failure.png');
  throw error;
} finally { await browser.close(); await new Promise(done=>server.close(done)); }
