// test_chrome.cjs - Use system Chrome
const { chromium } = require('./node_modules/playwright');

(async () => {
  console.log('Starting Chrome...');
  const browser = await chromium.launch({
    headless: true,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    timeout: 15000,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  const page = await browser.newPage();
  const errors = [];
  page.on('console', msg => { if (msg.type() === 'error') errors.push('[ERROR] ' + msg.text()); });
  page.on('pageerror', err => errors.push('[PAGEERROR] ' + err.message));

  let passed = 0, failed = 0;
  function check(label, cond, detail) {
    if (cond) { console.log('  PASS ' + label); passed++; }
    else { console.log('  FAIL ' + label + (detail ? ' - ' + detail : '')); failed++; }
  }

  // PAGE 1: Landing
  console.log('\n=== PAGE 1: /strategy/agents ===');
  try {
    await page.goto('http://localhost:5173/strategy/agents', { timeout: 20000 });
    await page.waitForTimeout(5000);
    check('URL correct', page.url().includes('strategy/agents'));
    check('Hero section', !!(await page.$('.agents-hero')));
    const introCard = await page.$('.intro-card');
    check('系统介绍入口卡', !!introCard);
    if (introCard) {
      const href = await introCard.getAttribute('href').catch(() => '');
      check('href=/strategy/agents/intro', href === '/strategy/agents/intro', href);
    }
    check('飞书推送管理', !!(await page.$('.feishu-panel')));
    check('方法论人格库', !!(await page.$('#persona-library')));
    check('设计原则已移除', !(await page.$('.principle-grid')));
    check('系统分层已移除', !(await page.$('.layer-stack')));
    check('共享事实协议已移除', !(await page.$('.context-grid')));
    check('执行链路已移除', !(await page.$('.flow-grid')));
    check('运行模式已移除', !(await page.$('.mode-grid')));
    await page.screenshot({ path: 'shot1_landing.png' });
    console.log('  Screenshot: shot1_landing.png');
  } catch (e) { console.log('  ERROR: ' + e.message); }

  // PAGE 2: Intro detail
  console.log('\n=== PAGE 2: /strategy/agents/intro ===');
  try {
    await page.goto('http://localhost:5173/strategy/agents/intro', { timeout: 20000 });
    await page.waitForTimeout(5000);
    check('URL correct', page.url().includes('/strategy/agents/intro'));
    check('Header visible', !!(await page.$('.intro-top')));
    check('Hero banner', !!(await page.$('.intro-hero')));
    const layers = await page.$$('.intro-layer-card');
    check('四层架构 cards >= 4', layers.length >= 4, 'found ' + layers.length);
    check('共享事实协议', !!(await page.$('.intro-context-card')));
    check('执行链路', !!(await page.$('.intro-flow-card')));
    check('运行模式', !!(await page.$('.intro-mode-card')));
    const learnCard = await page.$('.intro-learn-card');
    check('深入了解入口卡', !!learnCard);
    if (learnCard) {
      const href = await learnCard.getAttribute('href').catch(() => '');
      check('href=/strategy/agents/intro/principles', href === '/strategy/agents/intro/principles', href);
    }
    check('设计原则不在此页', !(await page.$('.principle-card')));
    await page.screenshot({ path: 'shot2_intro.png' });
    console.log('  Screenshot: shot2_intro.png');
  } catch (e) { console.log('  ERROR: ' + e.message); }

  // PAGE 3: Principles sub-page
  console.log('\n=== PAGE 3: /strategy/agents/intro/principles ===');
  try {
    await page.goto('http://localhost:5173/strategy/agents/intro/principles', { timeout: 20000 });
    await page.waitForTimeout(5000);
    check('URL correct', page.url().includes('/principles'));
    check('Header visible', !!(await page.$('.principles-top')));
    check('Hero visible', !!(await page.$('.principles-hero')));
    const cards = await page.$$('.principle-card');
    check('设计原则 cards >= 1', cards.length >= 1, 'found ' + cards.length);
    check('Footer back button', !!(await page.$('.principles-footer__back')));
    await page.screenshot({ path: 'shot3_principles.png' });
    console.log('  Screenshot: shot3_principles.png');
  } catch (e) { console.log('  ERROR: ' + e.message); }

  console.log('\n=== RESULTS: ' + passed + ' passed, ' + failed + ' failed ===');
  console.log('Console errors: ' + errors.length);
  errors.forEach(e => console.log('  ' + e));
  if (failed === 0 && errors.length === 0) console.log('\nAll tests passed!');
  await browser.close();
  process.exit(0);
})();
