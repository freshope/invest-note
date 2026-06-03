"use client";

import * as React from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";

// 패널 슬라이드 애니메이션 duration (CSS duration-300과 동기화)
export const PANEL_ANIMATION_MS = 300;

// scroll lock 카운터를 DOM attribute에 저장해 HMR/SSR 모듈 재실행 시 오염 방지
function getLockCount(): number {
  return Number(document.body.dataset.panelLockCount ?? 0);
}
function setLockCount(n: number) {
  if (n <= 0) {
    delete document.body.dataset.panelLockCount;
  } else {
    document.body.dataset.panelLockCount = String(n);
  }
}

interface FullScreenPanelContextValue {
  onClose: () => void;
  visible: boolean;
  panelRef: React.RefObject<HTMLDivElement | null>;
  handleTransitionEnd: (e: React.TransitionEvent<HTMLDivElement>) => void;
}

const FullScreenPanelContext = React.createContext<FullScreenPanelContextValue>({
  onClose: () => {},
  visible: false,
  panelRef: { current: null },
  handleTransitionEnd: () => {},
});

interface FullScreenPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: React.ReactNode;
}

function FullScreenPanel({ open, onOpenChange, children }: FullScreenPanelProps) {
  const [mounted, setMounted] = React.useState(false);
  const [visible, setVisible] = React.useState(false);
  const panelRef = React.useRef<HTMLDivElement>(null);

  const handleClose = React.useCallback(() => onOpenChange(false), [onOpenChange]);

  // Enter: mount → double rAF → visible. Exit: visible=false, wait transitionEnd → unmount.
  React.useEffect(() => {
    if (open) {
      setMounted(true);
      let raf1 = 0, raf2 = 0;
      raf1 = requestAnimationFrame(() => {
        raf2 = requestAnimationFrame(() => setVisible(true));
      });
      return () => {
        cancelAnimationFrame(raf1);
        cancelAnimationFrame(raf2);
      };
    } else {
      setVisible(false);
    }
  }, [open]);

  // body scroll lock — DOM 카운터로 중첩 패널 방어. mounted 기준으로 exit 중에도 lock 유지.
  React.useEffect(() => {
    if (mounted) {
      const count = getLockCount();
      if (count === 0) document.body.style.overflow = "hidden";
      setLockCount(count + 1);
      return () => {
        const next = getLockCount() - 1;
        setLockCount(next);
        if (next === 0) document.body.style.overflow = "";
      };
    }
  }, [mounted]);

  const handleTransitionEnd = React.useCallback(
    (e: React.TransitionEvent<HTMLDivElement>) => {
      if (!open && e.target === panelRef.current && e.propertyName === "transform") {
        setMounted(false);
      }
    },
    [open],
  );

  // transitionEnd 미발생 대비 fallback — gesture cancel 등으로 이벤트가 오지 않을 때 강제 언마운트
  React.useEffect(() => {
    if (!open) {
      const id = setTimeout(() => setMounted(false), PANEL_ANIMATION_MS + 50);
      return () => clearTimeout(id);
    }
  }, [open]);

  if (!mounted) return null;

  return (
    <FullScreenPanelContext.Provider
      value={{ onClose: handleClose, visible, panelRef, handleTransitionEnd }}
    >
      {children}
    </FullScreenPanelContext.Provider>
  );
}

interface FullScreenPanelContentProps {
  children: React.ReactNode;
  className?: string;
}

function FullScreenPanelContent({ children, className }: FullScreenPanelContentProps) {
  const { visible, panelRef, handleTransitionEnd } = React.useContext(FullScreenPanelContext);

  if (typeof window === "undefined") return null;

  return createPortal(
    <div
      ref={panelRef}
      data-slot="full-screen-panel-content"
      onTransitionEnd={handleTransitionEnd}
      className={cn(
        "fixed inset-0 z-[100] flex flex-col bg-background",
        "transition-transform duration-300",
        "[transition-timing-function:cubic-bezier(0.32,0.72,0,1)]",
        visible ? "translate-x-0" : "translate-x-full",
        className,
      )}
    >
      {children}
    </div>,
    document.body,
  );
}

interface FullScreenPanelHeaderProps {
  title: string;
  className?: string;
}

function FullScreenPanelHeader({ title, className }: FullScreenPanelHeaderProps) {
  const { onClose } = React.useContext(FullScreenPanelContext);

  return (
    <div
      data-slot="full-screen-panel-header"
      className={cn("sticky top-0 z-10 bg-background", className)}
      style={{ paddingTop: "var(--safe-area-inset-top, env(safe-area-inset-top))" }}
    >
      <div className="relative flex h-14 items-center px-2">
        <button
          type="button"
          onClick={onClose}
          className="flex h-10 w-10 items-center justify-center rounded-full text-foreground transition-colors hover:bg-muted active:bg-muted"
          aria-label="뒤로"
        >
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </button>
        <span className="absolute inset-x-0 text-center text-[17px] font-bold text-foreground pointer-events-none">
          {title}
        </span>
      </div>
    </div>
  );
}

interface FullScreenPanelBodyProps {
  children: React.ReactNode;
  className?: string;
}

function FullScreenPanelBody({ children, className }: FullScreenPanelBodyProps) {
  return (
    <div
      data-slot="full-screen-panel-body"
      className={cn("flex-1 overflow-y-auto", className)}
      style={{ WebkitOverflowScrolling: "touch" } as React.CSSProperties}
    >
      {children}
    </div>
  );
}

interface FullScreenPanelFooterProps {
  children: React.ReactNode;
  className?: string;
  sticky?: boolean;
}

function FullScreenPanelFooter({
  children,
  className,
  sticky = true,
}: FullScreenPanelFooterProps) {
  return (
    <div
      data-slot="full-screen-panel-footer"
      className={cn(
        "bg-background px-5 pt-3 pb-4",
        sticky && "sticky bottom-0",
        className,
      )}
      style={{ paddingBottom: "calc(1rem + var(--safe-area-inset-bottom, env(safe-area-inset-bottom)))" }}
    >
      {children}
    </div>
  );
}

export function useSnapshotWhileOpen<T>(open: boolean, value: T): T {
  const ref = React.useRef(value);
  // render 중 ref를 직접 쓰는 것은 React 공식 허용 패턴 (escape hatch).
  // ref.current 변경은 렌더 출력에 영향을 주지 않아 concurrent 모드에서도 안전하다.
  // eslint-disable-next-line react-hooks/refs
  if (open) ref.current = value;
  // eslint-disable-next-line react-hooks/refs
  return ref.current;
}

// 외부 payload state 를 받아 슬라이드 lifecycle (open / 재마운트 key / close 후 정리) 을 캡슐화한다.
// payload 가 null 이 되어도 슬라이드 아웃 애니메이션 동안 이전 payload 를 살려두기 위해 internal state 를 사용한다.
export function useStaggeredPanel<T>(externalPayload: T | null): {
  open: boolean;
  payload: T | null;
  remountKey: number;
} {
  const [open, setOpen] = React.useState(false);
  const [payload, setPayload] = React.useState<T | null>(null);
  const [remountKey, setRemountKey] = React.useState(0);

  // useEffect 클로저에서 "이미 열린 상태였는지" 체크용 — state 직접 읽기는 stale closure 위험
  const internalPayloadRef = React.useRef<T | null>(null);
  React.useEffect(() => {
    internalPayloadRef.current = payload;
  });

  const closeTimer = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  React.useEffect(() => {
    if (closeTimer.current !== null) {
      clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
    if (externalPayload !== null) {
      // 이미 열린 상태에서 새 payload → content remount (애니메이션 cancel 효과)
      if (internalPayloadRef.current !== null) {
        setRemountKey((k) => k + 1);
      }
      setPayload(externalPayload);
      setOpen(true);
    } else if (internalPayloadRef.current !== null) {
      setOpen(false);
      closeTimer.current = setTimeout(() => {
        closeTimer.current = null;
        setPayload(null);
      }, PANEL_ANIMATION_MS + 50);
    }
  }, [externalPayload]);

  // unmount 시 timer leak 방지 (라우트 이동 등으로 Provider 자체가 사라질 때 대비)
  React.useEffect(() => {
    return () => {
      if (closeTimer.current !== null) clearTimeout(closeTimer.current);
    };
  }, []);

  return { open, payload, remountKey };
}

export {
  FullScreenPanel,
  FullScreenPanelContent,
  FullScreenPanelHeader,
  FullScreenPanelBody,
  FullScreenPanelFooter,
};
