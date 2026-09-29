// Run: NODE_PATH=$(npm root -g) node tests/ui.test.js
const { chromium } = require('playwright');
const path = require('path');
const assert = require('assert');
const URL = 'file://' + path.resolve(__dirname, '..', 'index.html');
let fails = 0;
const ok = (c, m) => { if (!c) { fails++; console.log('FAIL', m); } else console.log('ok  ', m); };

(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' }).catch(() => chromium.launch());
  const ctx = await browser.newContext({ viewport: { width: 1200, height: 900 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  await page.addInitScript(() => { window.__opened = []; window.open = (u) => { window.__opened.push(u); return null; }; window.confirm = () => true; });
  await page.goto(URL);

  // empty state
  ok(await page.locator('h1').innerText() === 'Welcome', 'empty state shows onboarding');

  // pure functions
  const pure = await page.evaluate(() => ({
    p1: normPhone('98765 43210'), p2: normPhone('+91 86678-49698'), p3: normPhone('04172 123456'), p4: normPhone('0091 98765 43210'),
    m1: isMobile('+919876543210'), m2: isMobile('+914172123456'), m3: isMobile('+971501234567'),
    csv: parseTable('Name,Company,Phone,Interest\nAli,"Ali, Leather ""Co""",9876543210,Website\n'),
    noh: parseTable('Foo Shoes\t9876543210\tshoe factory\tAmbur'),
  }));
  ok(pure.p1 === '+919876543210' && pure.p2 === '+918667849698' && pure.p3 === '+914172123456' && pure.p4 === '+919876543210', 'phone normalisation');
  ok(pure.m1 && !pure.m2 && pure.m3, 'mobile vs landline');
  ok(pure.csv.length === 1 && pure.csv[0].name === 'Ali, Leather "Co"' && pure.csv[0].contact === 'Ali' && pure.csv[0].notes === 'Website', 'CSV quoting + Code.gs sheet mapping');
  ok(pure.noh[0].name === 'Foo Shoes' && pure.noh[0].area === 'Ambur', 'headerless paste');

  // import with duplicates, landline, inbound
  await page.evaluate(() => go('discover'));
  await page.fill('#im_text', 'name,phone,industry,area,website,rating,reviews\nMaryam Leather Products,8667849698,Leather goods manufacturer,Melvisharam,,4.9,19\nMaryam Leather Products,+91 86678 49698,dup,Melvisharam,,,\nDyecode Craft,9003850628,Shoe factory,Melvisharam,,4.9,92\nHotel Landline,04172 222333,Restaurant,Ambur,http://example.com,4.1,30\nNo Phone Shop,,Shop,Ambur,,,');
  await page.click('text=Preview import');
  ok((await page.locator('.mbox').innerText()).includes('Duplicates skipped'), 'import preview');
  await page.click('button:has-text("Import 4")');
  const leads = await page.evaluate(() => L().map(l => ({ n: l.name, s: score(l), st: l.status })));
  ok(leads.length === 4, 'imported 4 unique leads, got ' + leads.length);
  ok(leads.find(l => l.n === 'Dyecode Craft').s > leads.find(l => l.n === 'Hotel Landline').s, 'no-website mobile lead outranks landline restaurant with site');

  // Places form: real selects with options, "Other" reveals text box, search sends chosen values
  await page.evaluate(() => go('discover'));
  ok(await page.locator('#pl_type_s option').count() > 10 && await page.locator('#pl_area_s option').count() >= 6, 'type/area dropdowns populated');
  ok(await page.locator('#pl_area_s').inputValue() === 'Melvisharam', 'area defaults to first configured area');
  await page.selectOption('#pl_type_s', '__other'); ok(await page.locator('#pl_type').isVisible(), '"Other" shows a text box');
  await page.fill('#pl_type', 'tannery');
  const sent = await page.evaluate(async () => { let body; S.backend = 'http://x'; const f = window.fetch; window.fetch = async (u, o) => { body = JSON.parse(o.body); return new Response(JSON.stringify({ leads: [] }), { status: 200 }); }; await A.search(); window.fetch = f; S.backend = ''; return body; });
  ok(sent.type === 'tannery' && sent.area === 'Melvisharam', 'search uses dropdown/other values');

  // inbound import goes straight to reply queue
  await page.evaluate(() => go('discover'));
  await page.fill('#im_text', 'Name,Company,City,Phone,Email,Interest,Message\nRafi,Rafi Traders,Chennai,9444012345,r@x.com,Website,Need a site');
  await page.check('#im_in'); await page.click('text=Preview import'); await page.click('button:has-text("Import 1")');
  ok((await page.locator('.group h2').first().innerText()).includes('Reply to these first'), 'inbound enquiry lands in reply-first group');

  // today: WhatsApp flow — open must NOT count as sent
  const first = await page.evaluate(() => buildQueue().fresh[0].id);
  await page.evaluate(id => A.wa(id), first);
  let st = await page.evaluate(id => ({ o: window.__opened, sent: byId(id).activities.filter(a => a.type === 'Message Sent').length, pend: !!byId(id).pending, url: window.__opened[0] }), first);
  ok(st.o.length === 1 && st.sent === 0 && st.pend, 'opening WhatsApp does not log a send');
  ok(/^https:\/\/wa\.me\/91\d{10}\?text=/.test(st.url), 'wa.me url has digits only');
  ok(decodeURIComponent(st.url).includes('STOP'), 'intro carries opt-out line');
  ok(await page.locator('.banner').count() === 1, 'confirmation banner shown');
  await page.evaluate(id => A.confirm(id, 1), first);
  let l = await page.evaluate(id => { const x = byId(id); return { st: x.status, step: x.step, nd: x.nextDate, na: x.nextAction, peak: x.peak }; }, first);
  ok(l.st === 'Contacted' && l.step === 1 && l.nd === await page.evaluate(() => addDays(2)) && l.peak === 2, 'confirm -> Contacted, step 1, follow-up in 2 days');

  // cadence walk: fu1 (+2d) -> call (+3) -> proof -> breakup -> nurture
  const walk = await page.evaluate(id => {
    const x = byId(id), seq = [];
    for (let i = 0; i < 4; i++) { const nt = nextTouch(x); seq.push(nt.tpl); if (nt.ch === 'call') { A.callDone(id, 'noanswer'); A.callDone(id, 'noanswer'); } else { x.pending = { tpl: nt.tpl, text: 'x', at: nowIso(), cadence: true }; confirmPending(id, 1); } }
    return { seq, status: x.status, step: x.step, nd: x.nextDate, na: x.nextAction, exp: addDays(S.nurtureDays), cycles: x.cycles };
  }, first);
  ok(walk.seq.join() === 'fu1,call,proof,breakup' && walk.status === 'Nurture' && walk.nd === walk.exp && walk.cycles === 1, 'full cadence ends in Nurture: ' + JSON.stringify(walk));

  // a call attempt during a WhatsApp step must not advance cadence
  const dy = await page.evaluate(() => { const x = L().find(l => l.name === 'Dyecode Craft'); return x.id; });
  const callSafe = await page.evaluate(id => { const x = byId(id); if (x.status === 'Nurture') return null; const before = x.step; A.callDone(id, 'noanswer'); return [before, x.step]; }, dy);
  if (callSafe) ok(callSafe[0] === callSafe[1], 'stray call attempt does not skip a WhatsApp step');

  // reply stops cadence and creates reply task
  const r = await page.evaluate(() => {
    const x = L().find(l => l.name === 'Hotel Landline');
    x.pending = { tpl: 'intro', text: 'x', at: nowIso(), cadence: true }; confirmPending(x.id, 1);
    applyReply(x, 'price', { text: 'rate?' }); commit(x);
    const q = buildQueue();
    return { st: x.status, inReply: q.reply.some(l => l.id === x.id), tpl: templateStats().find(t => t.id === 'intro') };
  });
  ok(r.st === 'Replied' && r.inReply && r.tpl.replies >= 1, 'price reply -> Replied, in reply queue, attributed to template');

  // landline: no WhatsApp
  const ll = await page.evaluate(() => { const x = L().find(l => l.name === 'Hotel Landline'); return waOK(x); });
  ok(ll === false, 'landline is not WhatsApp-able');

  // proposal -> won
  const pw = await page.evaluate(() => {
    const x = L().find(l => l.name === 'Hotel Landline');
    x.pending = { kind: 'proposal', value: 30000, text: 'p', tpl: 'proposal', at: nowIso() }; confirmPending(x.id, 1);
    const afterP = { st: x.status, v: x.proposalValue, na: x.nextAction };
    closeWon(x, 28000, ''); commit(x);
    return { afterP, st: x.status, v: x.proposalValue, nd: x.nextDate, peak: x.peak, f: funnel().map(f => f[1]) };
  });
  ok(pw.afterP.st === 'Proposal' && pw.afterP.v === 30000, 'proposal sent -> Proposal stage');
  ok(pw.st === 'Won' && pw.v === 28000 && pw.peak === 6 && pw.f[5] === 1, 'won -> revenue + funnel peak');

  // render every page, open modal for each lead, no exceptions
  for (const p of ['today', 'pipeline', 'leads', 'discover', 'analytics', 'settings']) { await page.evaluate(p => go(p), p); await page.waitForTimeout(50); }
  await page.evaluate(() => { for (const l of L()) { A.open(l.id); } closeModal(); });

  // settings save round trip + bad regex rejected
  await page.evaluate(() => go('settings'));
  await page.fill('#s_me', 'Amin U'); await page.fill('#s_port', 'aminullah.example/portfolio'); await page.click('button:has-text("Save settings")');
  const s2 = await page.evaluate(() => [S.me, S.portfolio]);
  ok(s2[0] === 'Amin U' && s2[1] === 'https://aminullah.example/portfolio', 'settings persisted + portfolio url fixed');
  await page.fill('#s_rules', '[{"label":"x","match":"(","weight":1,"angle":"a"}]'); await page.click('button:has-text("Save settings")');
  ok((await page.evaluate(() => S.rules.length)) === 5, 'invalid regex in rules rejected');

  // template rendering drops lines with empty variables
  const t = await page.evaluate(() => { S.portfolio = ''; const x = L().find(l => l.name === 'Dyecode Craft'); return renderTpl('proof', x); });
  ok(!t.includes('{') && !t.includes('sites we\'ve built'), 'empty {portfolio} line dropped');

  // XSS: hostile names never execute
  await page.evaluate(() => { addLeads([newLead({ name: '<img src=x onerror="window.__xss=1">', phone: '9876543299', mapsUrl: 'javascript:alert(1)' })]); go('leads'); A.open(L().at(-1).id); });
  ok(await page.evaluate(() => !window.__xss), 'hostile name is escaped');
  ok(await page.locator('a[href^="javascript:"]').count() === 0, 'javascript: maps url not rendered as link');
  await page.evaluate(() => closeModal());

  // persistence
  await page.reload();
  ok(await page.evaluate(() => L().length) === 6, 'data survives reload');

  // legacy migration (v8 key)
  const ctx2 = await browser.newContext(); const p2 = await ctx2.newPage(); await p2.addInitScript(() => { window.open = () => null; });
  await p2.goto(URL);
  await p2.evaluate(() => { localStorage.clear(); localStorage.setItem('arr_lead_engine_v8', JSON.stringify([{ id: 'L1', name: 'Old Co', phone: '+918667849698', status: 'Follow-up 1', score: 90, created: '2025-01-01T00:00:00Z', activities: [{ type: 'Outreach Sent', at: '2025-01-02T00:00:00Z' }, { type: 'Response Received', at: '2025-01-03T00:00:00Z' }], nextActionDate: '2025-01-05T00:00:00Z' }])); });
  await p2.reload();
  const mig = await p2.evaluate(() => { const x = L()[0]; return [L().length, x.status, x.peak, x.activities.map(a => a.type).join()]; });
  ok(mig[0] === 1 && mig[1] === 'Contacted' && mig[2] === 3 && mig[3].includes('Message Sent') && mig[3].includes('Reply'), 'v8 data migrated: ' + JSON.stringify(mig));

  // cloud sync with mocked Supabase: merge newer wins, tombstones, push changed only
  const p3 = await (await browser.newContext()).newPage();
  await p3.goto(URL);
  const sync = await p3.evaluate(async () => {
    const remote = [{ id: 'R1', data: { id: 'R1', name: 'Remote One', phone: '+919999999999', updated: '2030-01-01T00:00:00.000Z', activities: [] }, updated_at: '2030-01-01T00:00:00.000Z' }];
    const posts = [];
    window.fetch = async (u, o = {}) => {
      if (o.method === 'POST') { posts.push(JSON.parse(o.body)); return new Response(null, { status: 204 }); }
      return new Response(JSON.stringify(remote), { status: 200 });
    };
    S.cloud = { url: 'https://x.supabase.co', key: 'k', email: 'e', session: { access: 'a', refresh: 'r', exp: Date.now() + 1e6 } };
    db.push(newLead({ name: 'Local One', phone: '+918888888888' }));
    const r1 = await cloudSync();
    const n1 = L().map(l => l.name).sort();
    const r2 = await cloudSync();
    return { r1, r2, n1, posted: posts.map(p => p.map(x => x.data.name)) };
  });
  ok(sync.n1.join() === 'Local One,Remote One' && sync.r1.pulled === 1 && sync.r1.pushed >= 1, 'sync pulls remote + pushes local: ' + JSON.stringify(sync.r1));
  ok(sync.r2.pushed === 0, 'second sync pushes nothing new');

  // mobile viewport renders bottom nav
  const p4 = await (await browser.newContext({ viewport: { width: 390, height: 800 } })).newPage(); await p4.goto(URL);
  ok(await p4.locator('.mobilenav').isVisible() && !(await p4.locator('.side').isVisible()), 'mobile layout: bottom nav');
  const overflow = await p4.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
  ok(!overflow, 'no horizontal page overflow on phone');

  ok(errors.length === 0, 'no console/page errors ' + errors.join(' | '));
  await browser.close();
  console.log(fails ? `\n${fails} FAILED` : '\nALL PASSED'); process.exit(fails ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
