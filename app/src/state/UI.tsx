import { createContext, useContext } from 'react';

export interface UI {
  openRegionPicker: () => void;
  openMarketPicker: () => void;
  /** Null when installing is not possible here (already installed, or unsupported). */
  openInstall: (() => void) | null;
  toast: (message: string) => void;
}

export const UICtx = createContext<UI>({ openRegionPicker: () => {}, openMarketPicker: () => {}, openInstall: null, toast: () => {} });
export const useUI = () => useContext(UICtx);
