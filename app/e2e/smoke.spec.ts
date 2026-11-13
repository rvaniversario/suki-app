import { expect, test, type Page } from '@playwright/test';

const WIDTHS = [
  { name: 'phone', width: 390, height: 844 },
  { name: 'tablet', width: 820, height: 1180 },
  { name: 'desktop', width: 1440, height: 900 },
];

async function chooseRegion(page: Page) {
  const dialog = page.getByRole('dialog', { name: 'Choose your region' });
  await expect(dialog).toBeVisible();
  await dialog.getByRole('radio', { name: /MIMAROPA/ }).check();
  await dialog.getByRole('button', { name: 'Use MIMAROPA' }).click();
  await expect(dialog).toBeHidden();
}

for (const { name, width, height } of WIDTHS) {
  test(`smoke at ${width}px (${name})`, async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(e.message));
    await page.setViewportSize({ width, height });
    await page.goto('/');
    await chooseRegion(page);

    await expect(page.getByRole('heading', { name: 'Best buys today' })).toBeVisible();
    await expect(page.getByText(/As of .* · DA MIMAROPA AMAD/)).toBeVisible();
    await expect(page.getByText(/below usual|above usual|Same as usual/).first()).toBeVisible();

    // The page never scrolls sideways.
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);

    // Layout per width.
    if (name === 'phone') await expect(page.locator('.tabbar')).toBeVisible();
    if (name === 'tablet') await expect(page.locator('.rail')).toBeVisible();
    if (name === 'desktop') {
      await expect(page.locator('.sidebar')).toBeVisible();
      await expect(page.getByRole('table')).toBeVisible();
      await expect(page.getByRole('img', { name: /price per kilo over the last/ })).toBeVisible();
    }

    // Plan.
    await page.getByRole('link', { name: 'Plan' }).first().click();
    await expect(page.getByRole('heading', { name: "This week's plan" })).toBeVisible();
    await expect(page.getByText('Estimated total')).toBeVisible();

    // History -> item with chart.
    await page.getByRole('link', { name: 'History' }).first().click();
    await page.getByRole('searchbox').fill('tilapia');
    await page.getByRole('link', { name: /Tilapia/ }).click();
    await expect(page.getByRole('heading', { name: 'Tilapia' })).toBeVisible();
    await expect(page.getByRole('img', { name: /Tilapia price per kilo/ })).toBeVisible();
    await page.getByRole('button', { name: '1 year' }).click();
    await expect(page.getByRole('img', { name: /over the last 1 year/ })).toBeVisible();

    // Dark theme.
    await page.goto('/settings');
    await page.getByRole('radiogroup', { name: 'Appearance' }).getByRole('radio', { name: 'Dark' }).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');

    expect(errors).toEqual([]);
  });
}

test('works offline after the first visit', async ({ page, context }) => {
  await page.goto('/');
  await chooseRegion(page);
  await expect(page.getByText(/below usual|above usual|Same as usual/).first()).toBeVisible();
  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.reload(); // let the service worker control the page and cache data
  await expect(page.getByRole('heading', { name: 'Best buys today' })).toBeVisible();
  await context.setOffline(true);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Best buys today' })).toBeVisible();
  await expect(page.getByText(/Offline — showing prices as of/)).toBeVisible();
  await expect(page.getByText(/below usual|above usual|Same as usual/).first()).toBeVisible();
});
