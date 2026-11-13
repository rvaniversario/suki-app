import { useI18n } from '../i18n';
import { dateShort, pesoWhole } from '../lib/format';
import type { HistoryPoint } from '../lib/types';

/** Points further apart than this are drawn as separate segments (a gap), never interpolated. */
export const MAX_GAP_DAYS = 4;

const W = 350;
const H = 200;
const X0 = 40;
const X1 = 340;
const Y0 = 20;
const Y1 = 170;

const dayNum = (iso: string) => Math.round(Date.parse(`${iso}T00:00:00Z`) / 86400000);

export interface ChartSeries {
  segments: { x: number; y: number }[][];
  last: { x: number; y: number } | null;
  yMin: number;
  yMax: number;
  baselineY: number | null;
  count: number;
}

export function buildSeries(points: HistoryPoint[], asOf: string, rangeDays: number, baseline: number | null): ChartSeries | null {
  const end = dayNum(asOf);
  const start = end - rangeDays;
  const inRange = points.filter((p) => {
    const d = dayNum(p.d);
    return d > start && d <= end;
  });
  const values = inRange.map((p) => p.p).filter((p): p is number => p !== null);
  if (!values.length) return null;
  let lo = Math.min(...values, baseline ?? Infinity);
  let hi = Math.max(...values, baseline ?? -Infinity);
  const pad = Math.max((hi - lo) * 0.08, 2);
  lo = Math.floor((lo - pad) / 5) * 5;
  hi = Math.ceil((hi + pad) / 5) * 5;
  const x = (iso: string) => X0 + ((dayNum(iso) - start) / rangeDays) * (X1 - X0);
  const y = (p: number) => Y0 + ((hi - p) / (hi - lo)) * (Y1 - Y0);

  const segments: { x: number; y: number }[][] = [];
  let cur: { x: number; y: number }[] = [];
  let prevDay: number | null = null;
  for (const p of inRange) {
    const d = dayNum(p.d);
    if (p.p === null || (prevDay !== null && d - prevDay > MAX_GAP_DAYS)) {
      if (cur.length) segments.push(cur);
      cur = [];
    }
    if (p.p !== null) {
      cur.push({ x: x(p.d), y: y(p.p) });
      prevDay = d;
    }
  }
  if (cur.length) segments.push(cur);
  const lastPoint = [...inRange].reverse().find((p) => p.p !== null);
  return {
    segments,
    last: lastPoint ? { x: x(lastPoint.d), y: y(lastPoint.p as number) } : null,
    yMin: lo,
    yMax: hi,
    baselineY: baseline === null ? null : y(baseline),
    count: values.length,
  };
}

interface Props {
  name: string;
  points: HistoryPoint[];
  asOf: string;
  rangeDays: 30 | 90 | 365;
  baseline: number | null;
}

const f1 = (n: number) => n.toFixed(1);

export function PriceChart({ name, points, asOf, rangeDays, baseline }: Props) {
  const { t, lang } = useI18n();
  const s = buildSeries(points, asOf, rangeDays, baseline);
  if (!s) return <p className="empty">{t('item.noHistory')}</p>;

  const inRange = points.filter((p) => p.p !== null && dayNum(p.d) > dayNum(asOf) - rangeDays && dayNum(p.d) <= dayNum(asOf));
  const first = inRange[0]?.p ?? 0;
  const lastP = inRange[inRange.length - 1]?.p ?? 0;
  const rangeText = t(`item.range${rangeDays}`);
  const aria =
    baseline === null
      ? t('item.chartAriaNoBase', { name, range: rangeText, first: pesoWhole(first, lang), last: pesoWhole(lastP, lang) })
      : t('item.chartAria', { name, range: rangeText, first: pesoWhole(first, lang), last: pesoWhole(lastP, lang), usual: pesoWhole(baseline, lang) });

  return (
    <svg className="chart" role="img" aria-label={aria} viewBox={`0 0 ${W} ${H}`} fill="none">
      <path className="grid" d={`M${X0} ${Y0}h${X1 - X0}M${X0} ${(Y0 + Y1) / 2}h${X1 - X0}M${X0} ${Y1}h${X1 - X0}`} strokeWidth="1" />
      <text className="axis" x={X0 - 8} y={Y0 + 4} textAnchor="end">
        {pesoWhole(s.yMax, lang)}
      </text>
      <text className="axis" x={X0 - 8} y={Y1 + 4} textAnchor="end">
        {pesoWhole(s.yMin, lang)}
      </text>
      {s.baselineY !== null && baseline !== null && (
        <>
          <path className="baseline" d={`M${X0} ${f1(s.baselineY)}h${X1 - X0}`} strokeWidth="1.5" strokeDasharray="5 5" />
          <text className="baseline-label" x={X1} y={s.baselineY < Y0 + 14 ? s.baselineY + 15 : s.baselineY - 6} textAnchor="end">
            {t('item.usualLine', { price: pesoWhole(baseline, lang) })}
          </text>
        </>
      )}
      {s.segments.map((seg, i) =>
        seg.length === 1 ? (
          <circle key={i} className="dot" cx={f1(seg[0].x)} cy={f1(seg[0].y)} r="2.5" strokeWidth="0" />
        ) : (
          <polyline
            key={i}
            className="line"
            points={seg.map((p) => `${f1(p.x)},${f1(p.y)}`).join(' ')}
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ),
      )}
      {s.last && <circle className="dot" cx={f1(s.last.x)} cy={f1(s.last.y)} r="5" strokeWidth="2" />}
      <text className="axis" x={X0} y={H - 8}>
        {t(`item.ago${rangeDays}`)}
      </text>
      <text className="axis" x={X1} y={H - 8} textAnchor="end">
        {dateShort(asOf, lang)}
      </text>
    </svg>
  );
}
