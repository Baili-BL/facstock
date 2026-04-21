const { chromium } = require('playwright');

async function testPage() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  try {
    // Navigate to the page
    console.log('Navigating to http://localhost:5177/strategy/agents...');
    await page.goto('http://localhost:5177/strategy/agents', { waitUntil: 'networkidle', timeout: 30000 });

    // Wait for initial render
    await page.waitForTimeout(3000);

    // Take screenshot of initial state
    await page.screenshot({ path: '/Users/kevin/Desktop/facSstock/screenshot_initial.png' });
    console.log('Saved screenshot_initial.png');

    // Check page title
    const title = await page.title();
    console.log('Page title:', title);

    // Check if tabs exist
    const tabs = await page.locator('.agents-tab').count();
    console.log('Number of tabs found:', tabs);

    // Get tab text
    const tabTexts = await page.locator('.agents-tab').allTextContents();
    console.log('Tab texts:', tabTexts);

    // Click the "全部智能体" tab (second tab)
    if (tabs >= 2) {
      console.log('Clicking "全部智能体" tab...');
      await page.locator('.agents-tab').nth(1).click();
      await page.waitForTimeout(2000);

      // Take screenshot after clicking tab
      await page.screenshot({ path: '/Users/kevin/Desktop/facSstock/screenshot_history.png' });
      console.log('Saved screenshot_history.png');
    }

    // Check for history cards
    const historyCards = await page.locator('.hist-card').count();
    console.log('Number of history cards found:', historyCards);

    // Get history card titles
    const cardTitles = await page.locator('.hist-card__name').allTextContents();
    console.log('History card titles:', cardTitles);

    // Check for "绩效洞察" section
    const perfSection = await page.locator('.hist-perf').count();
    console.log('Performance insight section found:', perfSection > 0);

    // Get performance text
    const perfText = await page.locator('.hist-perf__stat').textContent().catch(() => 'Not found');
    console.log('Performance insight text:', perfText);

    // Check for "查看完整报告" buttons
    const reportButtons = await page.locator('.hist-card__cta').count();
    console.log('Number of "查看完整报告" buttons:', reportButtons);

    // Check console errors
    const errors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    // Reload to capture any errors
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);

    if (errors.length > 0) {
      console.log('Console errors found:', errors);
    } else {
      console.log('No console errors detected');
    }

    console.log('\n--- TEST SUMMARY ---');
    console.log('Page loaded successfully: YES');
    console.log('Tabs found:', tabs);
    console.log('History cards visible:', historyCards);
    console.log('Performance insight section:', perfSection > 0 ? 'YES' : 'NO');
    console.log('Report buttons:', reportButtons);

  } catch (error) {
    console.error('Error during test:', error.message);
  } finally {
    await browser.close();
  }
}

testPage();
