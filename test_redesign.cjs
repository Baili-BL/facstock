const { chromium } = require('playwright');

async function test() {
  const browser = await chromium.launch({
    headless: true,
    executablePath: '/var/folders/z1/lbsptxjx3j54g213xkq79slw0000gn/T/cursor-sandbox-cache/fb1eea31cfd46df33b002162a2acedcf/playwright/chromium-1217/chrome-mac-x64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing'
  });
  const page = await browser.newPage();

  const routes = [
    { name: 'StrategyAgents (Landing)', url: 'http://localhost:5174/strategy/agents' },
    { name: 'StrategyAgentsIntro', url: 'http://localhost:5174/strategy/agents/intro' },
    { name: 'StrategyAgentsIntroPrinciples', url: 'http://localhost:5174/strategy/agents/intro/principles' },
  ];

  let allPassed = true;

  for (const route of routes) {
    const errors = [];
    const listener = msg => {
      if (msg.type() === 'error') errors.push(msg.text());
    };
    const errListener = err => errors.push(err.message);
    page.on('console', listener);
    page.on('pageerror', errListener);

    try {
      const response = await page.goto(route.url, { waitUntil: 'networkidle', timeout: 20000 });
      const status = response ? response.status() : 'N/A';
      const content = await page.content();
      const hasContent = content && content.length > 500;

      console.log(`\n=== ${route.name} ===`);
      console.log(`URL: ${route.url}`);
      console.log(`HTTP Status: ${status}`);
      console.log(`Has Content: ${hasContent ? 'YES' : 'NO'}`);
      console.log(`Content Length: ${content ? content.length : 0}`);

      if (errors.length > 0) {
        console.log(`Console Errors (${errors.length}):`);
        errors.forEach(e => console.log(`  - ${e}`));
        allPassed = false;
      } else {
        console.log('Console Errors: NONE');
      }

    } catch (err) {
      console.log(`\n=== ${route.name} ===`);
      console.log(`ERROR: ${err.message}`);
      allPassed = false;
    }

    page.off('console', listener);
    page.off('pageerror', errListener);
  }

  await browser.close();
  console.log(`\n\nOverall: ${allPassed ? 'ALL PASSED' : 'SOME FAILED'}`);
}

test().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
