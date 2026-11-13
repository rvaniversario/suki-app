/* Inline stroke icons from the design. Decorative: always aria-hidden. */
type P = { size?: number };

export const TodayIcon = ({ size = 22 }: P) => (
  <svg aria-hidden="true" width={size} height={size} viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <path d="M4 6h14M4 11h10M4 16h6" />
  </svg>
);
export const PlanIcon = ({ size = 22 }: P) => (
  <svg aria-hidden="true" width={size} height={size} viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 8h16l-1.6 9H4.6L3 8ZM7.5 8l3.5-5 3.5 5" />
  </svg>
);
export const HistoryIcon = ({ size = 22 }: P) => (
  <svg aria-hidden="true" width={size} height={size} viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 16l5-6 4 3 7-8" />
  </svg>
);
export const SettingsIcon = ({ size = 20 }: P) => (
  <svg aria-hidden="true" width={size} height={size} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
    <path d="M3 6h7M14 6h3M3 14h3M10 14h7" />
    <circle cx="12" cy="6" r="2" />
    <circle cx="8" cy="14" r="2" />
  </svg>
);
export const ChevronDown = () => (
  <svg aria-hidden="true" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2.5 4.5 6 8l3.5-3.5" />
  </svg>
);
export const BackIcon = () => (
  <svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10 3 5 8l5 5" />
  </svg>
);
export const DownArrow = () => (
  <svg aria-hidden="true" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M6 2v8M2.5 6.5 6 10l3.5-3.5" />
  </svg>
);
export const UpArrow = () => (
  <svg aria-hidden="true" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M6 10V2M2.5 5.5 6 2l3.5 3.5" />
  </svg>
);
export const Dash = () => (
  <svg aria-hidden="true" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
    <path d="M2.5 6h7" />
  </svg>
);
export const Minus = () => (
  <svg aria-hidden="true" width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <path d="M3 7h8" />
  </svg>
);
export const Plus = () => (
  <svg aria-hidden="true" width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <path d="M3 7h8M7 3v8" />
  </svg>
);
export const Check = () => (
  <svg aria-hidden="true" width="20" height="22" viewBox="0 0 20 22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 12l4 4 8-9" />
  </svg>
);
export const Alert = () => (
  <svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M8 2.5 14.5 13.5h-13L8 2.5ZM8 6.5v3.2M8 11.6v.1" />
  </svg>
);
export const ShareIcon = () => (
  <svg aria-hidden="true" width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 11V2.5M5.5 6 9 2.5 12.5 6M4 9H3v6.5h12V9h-1" />
  </svg>
);
export const SearchIcon = () => (
  <svg aria-hidden="true" width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
    <circle cx="8" cy="8" r="5" />
    <path d="m12 12 4 4" />
  </svg>
);
