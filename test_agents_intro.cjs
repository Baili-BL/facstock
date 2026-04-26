// test_agents_intro.cjs - Test script for StrategyAgents intro page
const { chromium } = require('./node_modules/playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();

  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') {
      errors.push(`[ERROR] ${msg.text()}`);
    }
  });
  page.on('pageerror', err => errors.push(`[PAGEERROR] ${err.message}`));

  console.log('=== Navigating to http://localhost:5174/strategy/agents ===');

  try {
    const resp = await page.goto('http://localhost:5174/strategy/agents', {
      waitUntil: 'networkidle',
      timeout: 30000
    });
    console.log(`Status: ${resp.status()}`);
    console.log(`URL: ${page.url()}`);

    await page.waitForTimeout(3000);

    // SCREENSHOT 1: Hero section with intro card
    console.log('\n=== SCREENSHOT 1: Hero + Intro Card ===');

    const hero = await page.$('.agents-hero');
    console.log(`Hero section: ${hero ? 'FOUND' : 'NOT FOUND'}`);

    const introCard = await page.$('.intro-card');
    console.log(`Intro card (.intro-card): ${introCard ? 'FOUND' : 'NOT FOUND'}`);

    if (hero) {
      const heroTitle = await page.$eval('.agents-hero__title', el => el.textContent);
      console.log(`Hero title: ${heroTitle}`);
    }

    if (introCard) {
      const introTitle = await page.$eval('.intro-card__title', el => el.textContent);
      console.log(`Intro card title: ${introTitle}`);
      const learnMoreText = await page.$eval('.intro-card__action', el => el.textContent.trim());
      console.log(`Learn more button: ${learnMoreText}`);
    }

    await page.screenshot({ path: 'screenshot_1_hero_intro.png', fullPage: false });
    console.log('Screenshot 1 saved: screenshot_1_hero_intro.png');

    // CLICK intro card
    console.log('\n=== Clicking "了解更多" button ===');
    if (introCard) {
      await introCard.click();
      console.log('Clicked intro card');
      await page.waitForTimeout(1000);

      const introDetail = await page.$('.intro-detail');
      console.log(`Intro detail (.intro-detail): ${introDetail ? 'FOUND' : 'NOT FOUND'}`);

      const introCardAfter = await page.$('.intro-card');
      console.log(`Intro card after click: ${introCardAfter ? 'STILL VISIBLE' : 'HIDDEN (as expected)'}`);
    } else {
      console.log('Could not find intro card to click!');
    }

    await page.waitForTimeout(1500);

    // SCREENSHOT 2: Expanded intro detail
    console.log('\n=== SCREENSHOT 2: Expanded Intro Detail ===');

    const detailTitle = await page.$eval('.intro-detail__title', el => el.textContent).catch(() => 'NOT FOUND');
    console.log(`Detail title: ${detailTitle}`);

    const sections = [
      '.intro-highlight',
      '.intro-stats',
      '.intro-layers',
      '.intro-modes',
      '.intro-personas',
      '.intro-flow'
    ];

    for (const sel of sections) {
      const el = await page.$eval(sel, el => el.tagName).catch(() => null);
      console.log(`${sel}: ${el ? 'FOUND' : 'NOT FOUND'}`);
    }

    await page.screenshot({ path: 'screenshot_2_expanded_intro.png', fullPage: false });
    console.log('Screenshot 2 saved: screenshot_2_expanded_intro.png');

    // FINAL REPORT
    console.log('\n=== FINAL REPORT ===');
    console.log(`Final URL: ${page.url()}`);
    console.log(`Page loaded successfully: ${resp.ok()}`);

    console.log('\nConsole errors:');
    if (errors.length > 0) {
      errors.forEach(e => console.log(`  ${e}`));
    } else {
      console.log('  No console errors!');
    }

  } catch (err) {
    console.error('Navigation error:', err.message);
    await page.screenshot({ path: 'screenshot_error.png' });
    console.log('Error screenshot saved: screenshot_error.png');
  }

  await browser.close();
  console.log('\nDone!');
})();
