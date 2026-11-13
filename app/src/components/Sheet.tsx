import { useEffect, useRef, type ReactNode } from 'react';

/** Bottom sheet on phone, centred dialog from 640px (CSS). Escape and scrim click close it when `onClose` is given. */
export function Sheet({ label, onClose, children }: { label: string; onClose?: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    const first = ref.current?.querySelector<HTMLElement>('input:not([disabled]), button, a[href]');
    first?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && onClose) onClose();
      if (e.key === 'Tab' && ref.current) {
        const els = ref.current.querySelectorAll<HTMLElement>('input:not([disabled]), button:not([disabled]), a[href]');
        if (!els.length) return;
        const a = els[0];
        const b = els[els.length - 1];
        if (e.shiftKey && document.activeElement === a) {
          e.preventDefault();
          b.focus();
        } else if (!e.shiftKey && document.activeElement === b) {
          e.preventDefault();
          a.focus();
        }
      }
    };
    ref.current?.addEventListener('keydown', onKey);
    const node = ref.current;
    return () => {
      node?.removeEventListener('keydown', onKey);
      prev?.focus?.();
    };
  }, [onClose]);

  return (
    <div className="scrim" onClick={(e) => e.target === e.currentTarget && onClose?.()}>
      <div ref={ref} className="sheet" role="dialog" aria-modal="true" aria-label={label}>
        {children}
      </div>
    </div>
  );
}
