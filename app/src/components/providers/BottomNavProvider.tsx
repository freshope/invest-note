"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

interface BottomNavContextValue {
  hidden: boolean;
  setHidden: (next: boolean) => void;
}

const BottomNavContext = createContext<BottomNavContextValue | null>(null);

export function BottomNavProvider({ children }: { children: React.ReactNode }) {
  const [hidden, setHiddenState] = useState(false);
  const setHidden = useCallback((next: boolean) => setHiddenState(next), []);
  const value = useMemo(() => ({ hidden, setHidden }), [hidden, setHidden]);
  return <BottomNavContext.Provider value={value}>{children}</BottomNavContext.Provider>;
}

function useBottomNavContext(): BottomNavContextValue {
  const ctx = useContext(BottomNavContext);
  if (!ctx) throw new Error("useBottomNav must be used inside BottomNavProvider");
  return ctx;
}

export function useBottomNavHidden(): boolean {
  return useBottomNavContext().hidden;
}

// 선언적으로 하단 네비 숨김을 요청한다. 컴포넌트 언마운트 또는 hidden=false 전환 시 자동 복구.
export function useHideBottomNav(hidden: boolean): void {
  const { setHidden } = useBottomNavContext();
  useEffect(() => {
    if (!hidden) return;
    setHidden(true);
    return () => setHidden(false);
  }, [hidden, setHidden]);
}
