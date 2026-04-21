const { chromium } = require('/opt/homebrew/lib/node_modules/playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  const page = await context.newPage();

  const consoleMessages = [];
  const errors = [];
  page.on('console', msg => {
    consoleMessages.push(`[${msg.type()}] ${msg.text()}`);
  });
  page.on('pageerror', err => {
    errors.push(`PAGE ERROR: ${err.message}`);
  });

  console.log('=== Navigating to http://localhost:5177/strategy/agents ===');
  await page.goto('http://localhost:5177/strategy/agents', { waitUntil: 'networkidle', timeout: 30000 });

  console.log('Page title:', await page.title());

  // Wait for initial load
  await page.waitForTimeout(3000);

  // Try to find and click the "全部智能体" tab (second tab button)
  const tabs = await page.locator('.tab-button, .agent-tab, button:has-text("全部智能体")').all();
  console.log(`Found ${tabs.length} tab-like elements`);

  // Try to find the tab by text
  const allAgentsTab = page.locator('button', { hasText: '全部智能体' });
  const count = await allAgentsTab.count();
  console.log(`"全部智能体" tab count: ${count}`);

  if (count > 0) {
    console.log('Clicking "全部智能体" tab...');
    await allAgentsTab.first().click();
    await page.waitForTimeout(3000);
  }

  // Check for history cards
  const cardTexts = [
    '周度策略共识',
    '宏观同步快讯',
    '收益率优化建议',
    '绩效洞察',
    '查看完整报告'
  ];

  console.log('\n=== Content Check ===');
  const bodyText = await page.locator('body').innerText();
  for (const text of cardTexts) {
    const found = bodyText.includes(text);
    console.log(`"${text}": ${found ? 'FOUND' : 'NOT FOUND'}`);
  }

  // Count cards
  const cards = await page.locator('.card, .agent-card, [class*="card"]').all();
  console.log(`\nTotal card-like elements found: ${cards.length}`);

  // Screenshot
  console.log('\n=== Taking screenshot ===');
  await page.screenshot({ path: 'screenshot_strategy_agents.png', fullPage: false });
  console.log('Screenshot saved as screenshot_strategy_agents.png');

  // Report console messages
  console.log('\n=== Console Messages ===');
  if (consoleMessages.length === 0) {
    console.log('No console messages');
  } else {
    consoleMessages.forEach(m => console.log(m));
  }

  console.log('\n=== Page Errors ===');
  if (errors.length === 0) {
    console.log('No page errors');
  } else {
    errors.forEach(e => console.log(e));
  }

  // Also get some HTML context for key sections
  console.log('\n=== Key HTML Sections ===');
  try {
    const perfSection = await page.locator('*', { hasText: '绩效洞察' }).first().innerHTML().catch(() => 'N/A');
    console.log('绩效洞察 section HTML (first 500 chars):', perfSection.substring(0, 500));
  } catch (e) {
    console.log('Could not get 绩效洞察 section:', e.message);
  }

  await browser.close();
  console.log('\nDone!');
})();
