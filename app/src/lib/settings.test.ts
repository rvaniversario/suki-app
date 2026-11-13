import { defaultSettings, isDefault, loadSettings, mergeOnSignIn, normalize, SETTINGS_KEY, type Settings } from './settings';

const changed = (patch: Partial<Settings>, updatedAt: string): Settings => ({ ...defaultSettings(), region: 'ncr', ...patch, updatedAt });

describe('settings storage', () => {
  beforeEach(() => localStorage.clear());

  it('falls back to defaults when missing', () => {
    expect(loadSettings()).toEqual(defaultSettings());
  });

  it('falls back to defaults when unreadable, never throwing', () => {
    localStorage.setItem(SETTINGS_KEY, '{not json');
    expect(loadSettings()).toEqual(defaultSettings());
  });

  it('repairs partial or invalid values', () => {
    const s = normalize({ region: 'ncr', usualKg: { fish: 2, pork: -1 }, budget: 'x', theme: 'neon' });
    expect(s.region).toBe('ncr');
    expect(s.usualKg).toEqual({ fish: 2, pork: 1, chicken: 1, beef: 0.5 });
    expect(s.budget).toBeNull();
    expect(s.theme).toBe('system');
  });
});

describe('merge on sign-in', () => {
  it('uploads local when there is no remote row', () => {
    const local = changed({ budget: 800 }, '2026-11-10T00:00:00Z');
    expect(mergeOnSignIn(local, null)).toEqual({ settings: local, kept: null, upload: true });
  });

  it('takes remote when local is still defaults (region aside)', () => {
    const local = { ...defaultSettings(), region: 'mimaropa', updatedAt: '2026-11-12T00:00:00Z' };
    const remote = changed({ budget: 900, region: null }, '2026-11-01T00:00:00Z');
    const res = mergeOnSignIn(local, remote);
    expect(isDefault(local)).toBe(true);
    expect(res.upload).toBe(false);
    expect(res.kept).toBeNull();
    expect(res.settings.budget).toBe(900);
    expect(res.settings.region).toBe('mimaropa');
  });

  it('keeps the newer one when both changed, and says which', () => {
    const local = changed({ budget: 800 }, '2026-11-10T00:00:00Z');
    const remote = changed({ budget: 900 }, '2026-11-11T00:00:00Z');
    expect(mergeOnSignIn(local, remote)).toMatchObject({ kept: 'remote', upload: false, settings: { budget: 900 } });
    expect(mergeOnSignIn({ ...local, updatedAt: '2026-11-12T00:00:00Z' }, remote)).toMatchObject({
      kept: 'local',
      upload: true,
      settings: { budget: 800 },
    });
  });
});
