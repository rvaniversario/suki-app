import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from '../App';
import { clearDataCache } from '../lib/data';
import { defaultSettings, SETTINGS_KEY, type Settings } from '../lib/settings';
import type { Latest, Region } from '../lib/types';
import { mk } from './fixtures';

const REGIONS: Region[] = [
  { id: 'mimaropa', name: 'MIMAROPA', status: 'daily', source: 'DA MIMAROPA AMAD', hasRange: true },
  { id: 'ncr', name: 'NCR (Metro Manila)', status: 'daily', source: 'DA Bantay Presyo', hasRange: false },
  { id: 'car', name: 'CAR (Cordillera)', status: 'unavailable' },
];

const today = new Date(Date.now() + 8 * 3600e3).toISOString().slice(0, 10);

const LATEST: Latest = {
  region: 'ncr',
  asOf: today,
  generatedAt: `${today}T02:00:00Z`,
  items: [
    mk('beef.rump', 'beef', 450.26, 12, { name: 'Beef rump' }),
    mk('chicken.whole', 'chicken', 183.58, 2, { name: 'Whole chicken' }),
    mk('fish.tilapia', 'fish', 150.34, -8, { name: 'Tilapia' }),
    mk('pork.kasim', 'pork', 320.84, -4, { name: 'Pork kasim' }),
    mk('fish.bangus', 'fish', 222.23, -5, { name: 'Bangus', featured: false }),
  ],
};

function mockFetch(latest: Latest = LATEST) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      const body = url.endsWith('regions.json') ? REGIONS : url.endsWith('latest.json') ? latest : { id: 'x', points: [] };
      return new Response(JSON.stringify(body), { status: 200 });
    }),
  );
}

const settings = (patch: Partial<Settings> = {}): Settings => ({ ...defaultSettings(), region: 'ncr', language: 'en', ...patch });

function renderAt(path: string, s?: Settings) {
  window.history.pushState({}, '', path);
  return render(<App initialSettings={s} />);
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  clearDataCache();
  mockFetch();
});
afterEach(() => vi.unstubAllGlobals());

describe('Today', () => {
  it('ranks tracked goods by how far below usual, not by price', async () => {
    renderAt('/', settings());
    const list = await screen.findByRole('list');
    const names = within(list)
      .getAllByRole('link')
      .map((a) => a.querySelector('strong')?.textContent);
    expect(names).toEqual(['Tilapia', 'Pork kasim', 'Whole chicken', 'Beef rump']); // Bangus is not featured
    expect(within(list).getByText('8% below usual')).toBeInTheDocument();
    expect(within(list).getByText('12% above usual')).toBeInTheDocument();
  });

  it('filters by category chip', async () => {
    renderAt('/', settings());
    await screen.findByText('Tilapia');
    await userEvent.click(screen.getByRole('button', { name: 'Pork' }));
    expect(screen.getByRole('button', { name: 'Pork' })).toHaveAttribute('aria-pressed', 'true');
    const list = screen.getByRole('list');
    expect(within(list).getAllByRole('link')).toHaveLength(1);
    expect(within(list).getByText('Pork kasim')).toBeInTheDocument();
  });

  it('shows the source and report date', async () => {
    renderAt('/', settings());
    expect(await screen.findByText(/DA Bantay Presyo/)).toBeInTheDocument();
  });

  it('shows a stale notice for old reports', async () => {
    mockFetch({ ...LATEST, asOf: '2026-01-01' });
    renderAt('/', settings());
    expect(await screen.findByText(/days old/)).toBeInTheDocument();
  });

  it('asks for a region on first launch', async () => {
    renderAt('/', settings({ region: null }));
    const dialog = await screen.findByRole('dialog', { name: 'Choose your region' });
    expect(within(dialog).getByRole('radio', { name: /CAR/ })).toBeDisabled();
    await userEvent.click(within(dialog).getByRole('radio', { name: /NCR/ }));
    await userEvent.click(within(dialog).getByRole('button', { name: 'Use NCR (Metro Manila)' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(JSON.parse(localStorage.getItem(SETTINGS_KEY)!).region).toBe('ncr');
  });
});

describe('Plan', () => {
  it('suggests kilos per category and totals them', async () => {
    renderAt('/plan', settings());
    // fish -8% -> 1.75 kg, pork -4% -> 1.5 kg, chicken +2% -> 0.75 kg, beef +12% -> skip
    expect(await screen.findByText('Fish · Buy more')).toBeInTheDocument();
    expect(screen.getByText('Beef · Skip this week')).toBeInTheDocument();
    const total = 1.75 * 150.34 + 1.5 * 320.84 + 0.75 * 183.58;
    expect(screen.getByText(`₱${Math.round(total)}`)).toBeInTheDocument();
  });

  it('steppers change quantities and the total', async () => {
    renderAt('/plan', settings());
    await screen.findByText('Fish · Buy more');
    await userEvent.click(screen.getByRole('button', { name: 'More Tilapia' }));
    expect(screen.getByText('Fish · Buy more · Changed by you')).toBeInTheDocument();
    const total = 2 * 150.34 + 1.5 * 320.84 + 0.75 * 183.58;
    expect(screen.getByText(`₱${Math.round(total)}`)).toBeInTheDocument();
  });

  it('trims to the weekly budget and says so', async () => {
    renderAt('/plan', settings({ budget: 600 }));
    expect(await screen.findByText(/Trimmed to fit your weekly budget of ₱600/)).toBeInTheDocument();
  });
});

describe('Settings', () => {
  it('switches theme immediately', async () => {
    renderAt('/settings', settings());
    const group = await screen.findByRole('radiogroup', { name: 'Appearance' });
    await userEvent.click(within(group).getByRole('radio', { name: 'Dark' }));
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(document.querySelector('meta[name="theme-color"]')?.getAttribute('content')).toBe('#0F1614');
    await userEvent.click(within(group).getByRole('radio', { name: 'Light' }));
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(JSON.parse(localStorage.getItem(SETTINGS_KEY)!).theme).toBe('light');
  });

  it('switches language and sets <html lang>', async () => {
    renderAt('/settings', settings());
    const group = await screen.findByRole('radiogroup', { name: 'Language' });
    await userEvent.click(within(group).getByRole('radio', { name: 'Filipino' }));
    expect(await screen.findByRole('heading', { name: 'Settings' })).toBeInTheDocument();
    expect(screen.getByText('Karaniwang binibili mo sa isang linggo')).toBeInTheDocument();
    expect(document.documentElement.lang).toBe('fil');
  });

  it('changes usual weekly kilos with steppers', async () => {
    renderAt('/settings', settings());
    await act(async () => {
      await userEvent.click(await screen.findByRole('button', { name: 'More Beef' }));
    });
    expect(JSON.parse(localStorage.getItem(SETTINGS_KEY)!).usualKg.beef).toBe(0.75);
    expect(screen.getByText('3¾ kg a week')).toBeInTheDocument();
  });

  it('never crashes on unreadable stored settings', async () => {
    localStorage.setItem(SETTINGS_KEY, '{{{');
    renderAt('/');
    expect(await screen.findByRole('dialog', { name: 'Choose your region' })).toBeInTheDocument();
  });
});
