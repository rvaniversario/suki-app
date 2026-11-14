import { Link } from 'react-router-dom';
import { useI18n } from '../i18n';
import { useInsights } from '../lib/data';
import type { Insights } from '../lib/types';
import { dateLong, kgOrUnit, pesoWhole } from '../lib/format';
import { useApp } from '../state/AppState';

/** The AI line for one market, in the active language (or null). */
export function marketLine(data: Insights | null, code: string | null, lang: 'en' | 'fil'): string | null {
  if (!data?.markets || !code) return null;
  const m = data.markets[code];
  return m ? m[lang] || m.en || null : null;
}

/** AI-written weekly note for the region (data/{region}/insights.json). Renders nothing if there is none. */
export function InsightsCard() {
  const { t, lang } = useI18n();
  const { region } = useApp();
  const insights = useInsights(region?.id ?? null);
  const note = insights.data?.[lang] ?? insights.data?.en;
  if (!insights.data || !note || !note.brief) return null;

  return (
    <section className="insights" aria-labelledby="insights-title">
      <div className="insights-head">
        <h2 id="insights-title">{t('insights.title')}</h2>
        <span className="detail">{t('insights.byAi', { date: dateLong(insights.data.asOf, lang) })}</span>
      </div>
      <p className="insights-brief">{note.brief}</p>
      {note.dishes.length > 0 && (
        <>
          <h3>{t('insights.dishes')}</h3>
          <ul className="insights-dishes">
            {note.dishes.map((d) => (
              <li key={d.name}>
                <div className="dish-head">
                  <strong>{d.name}</strong>
                  <span className="price">{t('insights.about', { cost: pesoWhole(d.cost, lang) })}</span>
                </div>
                {d.why && <span className="detail">{d.why}</span>}
                <span className="detail">
                  {d.ingredients.map((i, n) => (
                    <span key={i.id}>
                      {n > 0 && ', '}
                      <Link to={`/item/${i.id}`}>{i.name}</Link> {kgOrUnit(i.qty, i.unit)}
                    </span>
                  ))}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
      {insights.data.why && (
        <>
          <h3>{t('insights.why')}</h3>
          <p className="insights-brief">{insights.data.why[lang] || insights.data.why.en}</p>
          <ul className="insights-sources">
            {insights.data.why.sources.map((s) => (
              <li key={s.url}>
                <a href={s.url} target="_blank" rel="noopener noreferrer" className="detail">
                  {s.title}
                </a>
              </li>
            ))}
          </ul>
          <span className="detail">{t('insights.whyNote')}</span>
        </>
      )}
      {note.notes.length > 0 && (
        <ul className="insights-notes">
          {note.notes.map((n) => (
            <li key={n} className="detail">
              {n}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
