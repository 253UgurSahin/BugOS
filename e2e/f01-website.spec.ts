// F01: the BugOS website (website/index.html). Case IDs come from forge-work/test-plan.md.
// Every test fails on a console error, a page error, a 5xx, or a 4xx on one of the site's own
// scripts, stylesheets, images or fonts. Selectors are roles and labels, never CSS classes.
import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const BASE_URL = process.env.FORGE_BASE_URL || 'http://localhost:8080';
test.use({ baseURL: BASE_URL });

const ASSETS = ['script', 'stylesheet', 'image', 'font'];
let problems: string[] = [];

test.beforeEach(async ({ page }) => {
  problems = [];
  page.on('console', (message) => {
    if (message.type() === 'error' && !message.text().startsWith('Failed to load resource')) {
      problems.push(`console error: ${message.text()}`);
    }
  });
  page.on('pageerror', (error) => problems.push(`page error: ${error.message}`));
  page.on('response', (response) => {
    const status = response.status();
    const ownAsset = ASSETS.includes(response.request().resourceType())
      && new URL(response.url()).origin === new URL(BASE_URL).origin;
    if (status >= 500 || (status >= 400 && ownAsset)) problems.push(`${status} on ${response.url()}`);
  });
});

test.afterEach(() => {
  expect(problems).toEqual([]);
});

async function expectAccessible(page: Page) {
  const result = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    .analyze();
  expect(result.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.length}x, e.g. ${v.nodes[0]?.target})`))
    .toEqual([]);
}

// Scroll to the bottom in steps, so lazy images load and scroll effects run.
async function scrollThrough(page: Page) {
  const height = await page.evaluate(() => document.documentElement.scrollHeight);
  for (let y = 0; y <= height; y += 600) {
    await page.evaluate((top) => window.scrollTo(0, top), y);
    await page.waitForTimeout(40);
  }
  await page.waitForLoadState('networkidle');
}

test('F01-H1 the home page loads and passes the accessibility scan (light)', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light', reducedMotion: 'reduce' });
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await expect(page.getByRole('link', { name: /download/i }).first()).toBeVisible();
  await expectAccessible(page);
});

test('F01-H2 the home page passes the accessibility scan in dark too', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark', reducedMotion: 'reduce' });
  await page.goto('/');
  await expectAccessible(page);
});

test('F01-H3 every image on the page loads, lazy ones too, and has a text or is marked decorative', async ({ page }) => {
  await page.goto('/');
  await scrollThrough(page);
  // Only images people can see: a lazy image in a part that is hidden at this width (display: none)
  // never loads, and does not need to.
  const broken = await page.evaluate(() => [...document.images]
    .filter((img) => img.getClientRects().length && img.getBoundingClientRect().width > 0)
    .filter((img) => !img.complete || img.naturalWidth === 0).map((img) => img.currentSrc || img.src));
  expect(broken).toEqual([]);
  const noAlt = await page.evaluate(() => [...document.images]
    .filter((img) => !img.hasAttribute('alt')).map((img) => img.src));
  expect(noAlt).toEqual([]);
});

test('F01-H4 after scrolling through the whole page, every revealed part passes the accessibility scan', async ({ page }) => {
  // The whole page as it looks once everything has come in: the desktop stage, the terminal, and
  // the scroll-driven text (the moments and the story words, B004) wherever the scroll left them.
  for (const scheme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme: scheme, reducedMotion: 'reduce' });
    await page.goto('/');
    await scrollThrough(page);
    const result = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
      .analyze();
    expect(result.violations.map((v) => `${scheme} ${v.id}: ${v.nodes.map((n) => String(n.target)).join(', ')}`))
      .toEqual([]);
  }
});

test('F01-E1 every link inside the page goes to a part that exists', async ({ page }) => {
  await page.goto('/');
  const missing = await page.evaluate(() => [...document.querySelectorAll('a[href^="#"]')]
    .map((a) => a.getAttribute('href')!)
    .filter((href) => href !== '#' && !document.getElementById(href.slice(1))));
  expect(missing).toEqual([]);
});

test('F01-E2 the light/dark button switches, swaps the screenshots and is remembered after a reload', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light' });
  await page.goto('/');
  const button = page.getByRole('button', { name: 'Light or dark' });
  await button.click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  const src = await page.locator('img[data-donker]').first().getAttribute('src');
  expect(src).toContain('dark');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expectAccessible(page);
});

test('F01-E3 phone width (390px): no sideways scrolling, and the menu opens and closes', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await scrollThrough(page);
  const wider = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(wider).toBeLessThanOrEqual(0);
  await page.evaluate(() => window.scrollTo(0, 0));
  const menu = page.getByRole('button', { name: 'Menu' });
  await expect(menu).toHaveAttribute('aria-expanded', 'false');
  await menu.click();
  await expect(menu).toHaveAttribute('aria-expanded', 'true');
  const nav = page.getByRole('navigation', { name: 'Main menu' });
  await nav.getByRole('link').first().click();
  await expect(menu).toHaveAttribute('aria-expanded', 'false');
  await expectAccessible(page);
});

test('F01-E4 keyboard only: Tab reaches the menu, the theme button works with Enter, questions open with Space', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light', reducedMotion: 'reduce' });
  await page.goto('/');
  const seen: string[] = [];
  for (let i = 0; i < 12; i++) {
    await page.keyboard.press('Tab');
    seen.push(await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      return el ? (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 40) : '';
    }));
  }
  expect(seen).toContain('Light or dark');
  await page.getByRole('button', { name: 'Light or dark' }).focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  const question = page.locator('summary').first();
  await question.focus();
  await page.keyboard.press('Space');
  await expect(page.locator('details').first()).toHaveAttribute('open', '');
  // The focused element must be visible: an outline or a box-shadow.
  const ring = await question.evaluate((el) => {
    const s = getComputedStyle(el);
    return (s.outlineStyle !== 'none' && s.outlineWidth !== '0px') || s.boxShadow !== 'none';
  });
  expect(ring).toBe(true);
});

test('F01-E5 the light/dark slider works with the arrow keys', async ({ page }) => {
  await page.goto('/');
  const slider = page.getByRole('slider', { name: 'Slide between light and dark' });
  await slider.scrollIntoViewIfNeeded();
  await slider.focus();
  const before = Number(await slider.inputValue());
  await page.keyboard.press('ArrowRight');
  await page.keyboard.press('ArrowRight');
  expect(Number(await slider.inputValue())).toBeGreaterThan(before);
});

test('F01-E6 the "pretend something goes wrong" demo can be undone with "Pick yesterday"', async ({ page }) => {
  await page.goto('/');
  const wrong = page.getByRole('button', { name: 'Pretend something goes wrong' });
  await wrong.scrollIntoViewIfNeeded();
  await wrong.click();
  const back = page.getByRole('button', { name: 'Pick yesterday' });
  await expect(back).toBeVisible();
  await back.click();
  // After going back, the first button says "One more time" (on purpose) and starts the demo again.
  await expect(page.getByRole('button', { name: 'One more time' })).toBeVisible();
  await expect(back).toBeHidden();
  await expectAccessible(page);
});

test('F01-E7 with full motion (no reduced motion) the page still scrolls through without errors', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.goto('/');
  await scrollThrough(page);
  await expect(page.getByRole('heading', { level: 1 })).toBeAttached();
});

test('F01-N1 storage blocked (private window, cookies off): the page and the theme button still work', async ({ browser }) => {
  const context = await browser.newContext({ baseURL: BASE_URL });
  await context.addInitScript(() => {
    Object.defineProperty(window, 'localStorage', { get() { throw new DOMException('blocked', 'SecurityError'); } });
  });
  const page = await context.newPage();
  page.on('pageerror', (error) => problems.push(`page error: ${error.message}`));
  await page.goto('/');
  await page.getByRole('button', { name: 'Light or dark' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', /dark|light/);
  await context.close();
});

test('F01-N2 a page that does not exist gives a 404, not the home page', async ({ page }) => {
  const response = await page.request.get('/this-page-does-not-exist');
  expect(response.status()).toBe(404);
});
