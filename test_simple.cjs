// test_simple.cjs - Simple test
const { chromium } = require('./node_modules/playwright');

(async () => {
  console.log('Starting browser...');
  const browser = await chromium.launch({ headless: true, timeout: 15000 });
  const page = await browser.newPage();

  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(`[ERROR] ${msg.text()}`);
  });
  page.on('pageerror', err => errors.push(`[PAGEERROR] ${err.message}`));

  let passed = 0, failed = 0;
  function check(label, cond, detail = '') {
    if (cond) { console.log(`  PASS ${label}`); passed++; }
    else { console.log(`  FAIL ${label}${detail ? ' - ' + detail : ''}`); failed++; }
  }

  // PAGE 1: Landing
  console.log('\n=== PAGE 1: /strategy/agents ===');
  try {
    await page.goto('http://localhost:5173/strategy/agents', { timeout: 20000 });
    await page.waitForTimeout(4000);
    check('Status 200', page.url().includes('strategy/agents'));
    const hero = await page.$('.agents-hero');
    check('Hero section', !!hero);
    const introCard = await page.$('.intro-card');
    check('系统介绍入口卡', !!introCard);
    if (introCard) {
      const href = await introCard.getAttribute('href').catch(() => '');
      check('Intro card href=/strategy/agents/intro', href === '/strategy/agents/intro', href);
    }
    const feishu = await page.$('.feishu-panel');
    check('飞书推送管理', !!feishu);
    const personaLib = await page.$('#persona-library');
    check('方法论人格库', !!personaLib);
    const removed = await page.$('.principle-grid');
    check('设计原则已移除', !removed);
    const layerStack = await page.$('.layer-stack');
    check('系统分层已移除', !layerStack);
    await page.screenshot({ path: 'shot1_landing.png' });
    console.log('  Screenshot: shot1_landing.png');
  } catch (e) { console.log('  PAGE 1 ERROR:', e.message); }

  // PAGE 2: Intro detail
  console.log('\n=== PAGE 2: /strategy/agents/intro ===');
  try {
    await page.goto('http://localhost:5173/strategy/agents/intro', { timeout: 20000 });
    await page.waitForTimeout(4000);
    check('URL correct', page.url().includes('/strategy/agents/intro'));
    const header = await page.$('.intro-top');
    check('Header', !!header);
    const hero = await page.$('.intro-hero');
    check('Hero banner', !!hero);
    const layers = await page.$$('.intro-layer-card');
    check('四层架构 cards', layers.length >= 4, `found ${layers.length}`);
    const learnCard = await page.$('.intro-learn-card');
    check('深入了解入口卡', !!learnCard);
    if (learnCard) {
      const href = await learnCard.getAttribute('href').catch(() => '');
      check('Learn href=/strategy/agents/intro/principles', href === '/strategy/agents/intro/principles', href);
    }
    const principles = await page.$('.principle-card');
    check('设计原则不在此页', !principles);
    await page.screenshot({ path: 'shot2_intro.png' });
    console.log('  Screenshot: shot2_intro.png');
  } catch (e) { console.log('  PAGE 2 ERROR:', e.message); }

  // PAGE 3: Principles
  console.log('\n=== PAGE 3: /strategy/agents/intro/principles ===');
  try {
    await page.goto('http://localhost:5173/strategy/agents/intro/principles', { timeout: 20000 });
    await page.waitForTimeout(4000);
    check('URL correct', page.url().includes('/principles'));
    const header = await page.$('.principles-top');
    check('Header', !!header);
    const hero = await page.$('.principles-hero');
    check('Hero', !!hero);
    const cards = await page.$$('.principle-card');
    check('设计原则 cards', cards.length >= 1, `found ${cards.length}`);
    await page.screenshot({ path: 'shot3_principles.png' });
    console.log('  Screenshot: shot3_principles.png');
  } catch (e) { console.log('  PAGE 3 ERROR:', e.message); }

  // REPORT
  console.log(`\n=== RESULTS: ${passed} passed, ${failed} failed ===`);
  console.log(`Errors: ${errors.length}`);
  errors.forEach(e => console.log('  ' + e));
  if (failed === 0 && errors.length === 0) console.log('\nAll tests passed!');
  else console.log('\nSome issues found.');

  await browser.close();
  process.exit(0);
})();
