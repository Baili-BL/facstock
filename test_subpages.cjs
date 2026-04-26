// test_subpages.cjs - Test the three-page architecture
const { chromium } = require('./node_modules/playwright');

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();

  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(`[ERROR] ${msg.text()}`);
  });
  page.on('pageerror', err => errors.push(`[PAGEERROR] ${err.message}`));

  let passed = 0;
  let failed = 0;

  function check(label, condition, detail = '') {
    if (condition) {
      console.log(`  ✓ ${label}`);
      passed++;
    } else {
      console.log(`  ✗ ${label}${detail ? ' — ' + detail : ''}`);
      failed++;
    }
  }

  // ── PAGE 1: Landing page ───────────────────────────────────────
  console.log('\n=== PAGE 1: Landing page /strategy/agents ===');

  const resp1 = await page.goto('http://localhost:5173/strategy/agents', {
    waitUntil: 'networkidle', timeout: 30000
  });
  check('Landing page loads', resp1.ok(), `status=${resp1.status()}`);
  check('URL is correct', page.url().includes('/strategy/agents'));

  await sleep(3000);

  // Hero section
  const hero = await page.$('.agents-hero');
  check('Hero section visible', !!hero);
  if (hero) {
    const heroTitle = await page.$eval('.agents-hero__title', el => el.textContent.trim()).catch(() => '');
    check('Hero title present', heroTitle.length > 0, heroTitle);
  }

  // Intro card (系统介绍入口)
  const introCard = await page.$('.intro-card');
  check('系统介绍入口卡 visible', !!introCard);
  if (introCard) {
    const cardTitle = await page.$eval('.intro-card__title', el => el.textContent.trim()).catch(() => '');
    check('Card title correct', cardTitle === '游资智能体架构台是什么？', cardTitle);
    const actionText = await page.$eval('.intro-card__action', el => el.textContent.trim()).catch(() => '');
    check('Action button shows "系统介绍"', actionText.includes('系统介绍'), actionText);
  }

  // Feishu panel
  const feishu = await page.$('.feishu-panel');
  check('飞书推送管理面板 visible', !!feishu);

  // Persona library
  const personaLib = await page.$('#persona-library');
  check('方法论人格库 section visible', !!personaLib);
  if (personaLib) {
    const personaTitle = await page.$eval('#persona-library .agents-section__title', el => el.textContent.trim()).catch(() => '');
    check('Persona library title correct', personaTitle === '方法论人格库', personaTitle);
  }

  // Check that removed sections are gone
  const principlesSection = await page.$('.principle-grid');
  check('设计原则 section REMOVED from landing', !principlesSection);
  const layerStack = await page.$('.layer-stack');
  check('系统分层 section REMOVED from landing', !layerStack);
  const contextGrid = await page.$('.context-grid');
  check('共享事实协议 section REMOVED from landing', !contextGrid);
  const flowGrid = await page.$('.flow-grid');
  check('执行链路 section REMOVED from landing', !flowGrid);
  const modeGrid = await page.$('.mode-grid');
  check('运行模式 section REMOVED from landing', !modeGrid);

  await page.screenshot({ path: 'test_screenshot_1_landing.png', fullPage: false });
  console.log('  Screenshot: test_screenshot_1_landing.png');

  // ── Navigate to intro detail page ─────────────────────────────
  console.log('\n=== PAGE 2: Intro detail page /strategy/agents/intro ===');

  if (introCard) {
    await introCard.click();
    await page.waitForURL('**/strategy/agents/intro', { timeout: 10000 });
  } else {
    await page.goto('http://localhost:5173/strategy/agents/intro', { waitUntil: 'networkidle' });
  }

  await sleep(3000);

  check('Intro page URL correct', page.url().includes('/strategy/agents/intro'));
  check('Intro page URL does NOT contain /principles', !page.url().includes('/principles'));

  // Header
  const header = await page.$('.intro-top');
  check('Intro page header visible', !!header);

  // Hero
  const introHero = await page.$('.intro-hero');
  check('Intro hero banner visible', !!introHero);
  if (introHero) {
    const heroTitle = await page.$eval('.intro-hero__title', el => el.textContent.trim()).catch(() => '');
    check('Intro hero title correct', heroTitle === '游资智能体架构台', heroTitle);
  }

  // Stats
  const stats = await page.$$('.intro-hero-stat');
  check('Intro stats count >= 3', stats.length >= 3, `found ${stats.length}`);

  // Four layer architecture
  const layerCards = await page.$$('.intro-layer-card');
  check('四层系统架构 cards present', layerCards.length >= 4, `found ${layerCards.length}`);

  // Shared context
  const contextCards = await page.$$('.intro-context-card');
  check('共享事实协议 cards present', contextCards.length >= 1, `found ${contextCards.length}`);

  // Execution flow
  const flowCards = await page.$$('.intro-flow-card');
  check('完整执行链路 cards present', flowCards.length >= 1, `found ${flowCards.length}`);

  // Runtime modes
  const modeCards = await page.$$('.intro-mode-card');
  check('三种运行模式 cards present', modeCards.length >= 1, `found ${modeCards.length}`);

  // Learn more card (链接到 principles 子页)
  const learnCard = await page.$('.intro-learn-card');
  check('深入了解入口卡 visible', !!learnCard);
  if (learnCard) {
    const learnTitle = await page.$eval('.intro-learn-card__title', el => el.textContent.trim()).catch(() => '');
    check('Learn more title contains 设计原则', learnTitle.includes('设计原则'), learnTitle);
    const learnAction = await page.$eval('.intro-learn-card__action', el => el.textContent.trim()).catch(() => '');
    check('Learn more action shows "了解更多"', learnAction.includes('了解更多'), learnAction);
    const learnHref = await page.$eval('.intro-learn-card', el => el.getAttribute('href')).catch(() => '');
    check('Learn more href correct', learnHref === '/strategy/agents/intro/principles', learnHref);
  }

  // Footer back button
  const backBtn = await page.$('.intro-footer__back');
  check('Footer 返回 button visible', !!backBtn);

  // Design principles should NOT be directly on this page
  const principlesOnIntro = await page.$('.principle-card');
  check('设计原则 NOT directly on intro page', !principlesOnIntro);

  await page.screenshot({ path: 'test_screenshot_2_intro.png', fullPage: false });
  console.log('  Screenshot: test_screenshot_2_intro.png');

  // ── Navigate to principles sub-page ────────────────────────────
  console.log('\n=== PAGE 3: Principles sub-page /strategy/agents/intro/principles ===');

  if (learnCard) {
    await learnCard.click();
    await page.waitForURL('**/strategy/agents/intro/principles', { timeout: 10000 });
  } else {
    await page.goto('http://localhost:5173/strategy/agents/intro/principles', { waitUntil: 'networkidle' });
  }

  await sleep(3000);

  check('Principles page URL correct', page.url().includes('/principles'));

  // Header
  const principlesHeader = await page.$('.principles-top');
  check('Principles page header visible', !!principlesHeader);
  if (principlesHeader) {
    const headerTitle = await page.$eval('.principles-top__title', el => el.textContent.trim()).catch(() => '');
    check('Header title = 设计原则', headerTitle === '设计原则', headerTitle);
  }

  // Hero
  const principlesHero = await page.$('.principles-hero');
  check('Principles hero visible', !!principlesHero);
  if (principlesHero) {
    const heroTitle = await page.$eval('.principles-hero__title', el => el.textContent.trim()).catch(() => '');
    check('Principles hero title correct', heroTitle.includes('设计原则'), heroTitle);
  }

  // Principle cards
  const principleCards = await page.$$('.principle-card');
  check('设计原则 cards present', principleCards.length >= 1, `found ${principleCards.length}`);

  // Footer back button
  const principlesBack = await page.$('.principles-footer__back');
  check('Footer 返回系统介绍 button visible', !!principlesBack);
  if (principlesBack) {
    const backText = await page.$eval('.principles-footer__back', el => el.textContent.trim()).catch(() => '');
    check('Back button text correct', backText.includes('返回系统介绍'), backText);
  }

  await page.screenshot({ path: 'test_screenshot_3_principles.png', fullPage: false });
  console.log('  Screenshot: test_screenshot_3_principles.png');

  // ── Test back navigation ──────────────────────────────────────
  console.log('\n=== BACK NAVIGATION ===');

  // Back from principles to intro
  if (principlesBack) {
    await principlesBack.click();
    await page.waitForURL('**/strategy/agents/intro', { timeout: 10000 });
    check('Back to intro page works', page.url().includes('/strategy/agents/intro'));
  }

  // Back from intro to landing
  await page.goto('http://localhost:5173/strategy/agents/intro', { waitUntil: 'networkidle' });
  await sleep(2000);
  const introBack = await page.$('.intro-footer__back');
  if (introBack) {
    await introBack.click();
    await page.waitForURL('**/strategy/agents', { timeout: 10000 });
    check('Back to landing page works', page.url().endsWith('/strategy/agents') || page.url().includes('/strategy/agents'));
  }

  // ── Final Report ──────────────────────────────────────────────
  console.log('\n=== FINAL REPORT ===');
  console.log(`Console errors: ${errors.length}`);
  if (errors.length > 0) {
    errors.forEach(e => console.log(`  ${e}`));
  }
  console.log(`\nResults: ${passed} passed, ${failed} failed`);

  if (failed === 0 && errors.length === 0) {
    console.log('\n✓ All tests passed!');
  } else {
    console.log('\n✗ Some tests failed or errors occurred.');
    console.log('Screenshots saved:');
    console.log('  - test_screenshot_1_landing.png');
    console.log('  - test_screenshot_2_intro.png');
    console.log('  - test_screenshot_3_principles.png');
  }

  await browser.close();
})();
