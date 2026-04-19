"use client";

import * as React from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";

// 중첩 패널에서 scroll lock이 조기에 풀리는 것을 방지하는 카운터
let lockCount = 0;

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
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          setVisible(true);
        });
      });
    } else {
      setVisible(false);
    }
  }, [open]);

  // body scroll lock — 카운터로 중첩 패널 방어
  React.useEffect(() => {
    if (open) {
      if (lockCount === 0) {
        document.body.style.overflow = "hidden";
      }
      lockCount++;
      return () => {
        lockCount--;
        if (lockCount === 0) {
          document.body.style.overflow = "";
        }
      };
    }
  }, [open]);

  const handleTransitionEnd = React.useCallback(
    (e: React.TransitionEvent<HTMLDivElement>) => {
      if (!open && e.target === panelRef.current && e.propertyName === "transform") {
        setMounted(false);
      }
    },
    [open],
  );

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
      className={cn(
        "sticky top-0 z-10 flex items-center bg-background px-2",
        className,
      )}
      style={{
        height: `calc(3.5rem + env(safe-area-inset-top))`,
        paddingTop: "env(safe-area-inset-top)",
      }}
    >
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
      <span className="absolute left-1/2 -translate-x-1/2 text-[17px] font-bold text-foreground">
        {title}
      </span>
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

export function useSnapshotWhileOpen<T>(open: boolean, value: T): T {
  const ref = React.useRef(value);
  if (open) ref.current = value;
  return ref.current;
}

export {
  FullScreenPanel,
  FullScreenPanelContent,
  FullScreenPanelHeader,
  FullScreenPanelBody,
};
