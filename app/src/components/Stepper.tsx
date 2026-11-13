import { kg as fmtKg } from '../lib/format';
import { STEP_KG } from '../lib/plan';
import { Minus, Plus } from './Icons';

interface Props {
  value: number;
  onChange: (v: number) => void;
  lessLabel: string;
  moreLabel: string;
  valueLabel?: string;
  max?: number;
}

export function Stepper({ value, onChange, lessLabel, moreLabel, valueLabel, max = 50 }: Props) {
  const set = (v: number) => onChange(Math.max(0, Math.min(max, Math.round(v * 100) / 100)));
  return (
    <div className="stepper">
      <button type="button" aria-label={lessLabel} disabled={value <= 0} onClick={() => set(value - STEP_KG)}>
        <Minus />
      </button>
      <output aria-live="polite" aria-label={valueLabel}>
        {fmtKg(value)}
      </output>
      <button type="button" aria-label={moreLabel} disabled={value >= max} onClick={() => set(value + STEP_KG)}>
        <Plus />
      </button>
    </div>
  );
}
