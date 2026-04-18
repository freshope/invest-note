"use client";

import * as React from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";

interface FullScreenPanelContextValue {
  onClose: () => void;
  title?: string;
}

const FullScreenPanelContext = React.createContext<FullScreenPanelContextValue>({
  onClose: () => {},
});

interface FullScreenPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: React.ReactNode;
}

function FullScreenPanel({ onOpenChange, children }: FullScreenPanelProps) {
  const handleClose = React.useCallback(() => onOpenChange(false), [onOpenChange]);
  return (
    <FullScreenPanelContext.Provider value={{ onClose: handleClose }}>
      {children}
    </FullScreenPanelContext.Provider>
  );
}

interface FullScreenPanelContentProps {
  open: boolean;
  children: React.ReactNode;
  className?: string;
}

function FullScreenPanelContent({ open, children, className }: FullScreenPanelContentProps) {
  const [mounted, setMounted] = React.useState(false);
  const [visible, setVisible] = React.useState(false);
  const [animating, setAnimating] = React.useState(false);
  const panelRef = React.useRef<HTMLDivElement>(null);

  // Mount on open
  React.useEffect(() => {
    if (open) {
      setMounted(true);
      // Allow DOM to paint before triggering transition
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          setVisible(true);
          setAnimating(false);
        });
      });
    } else {
      if (mounted) {
        setAnimating(true);
        setVisible(false);
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Unmount after exit animation
  const handleTransitionEnd = React.useCallback(() => {
    if (!open) {
      setMounted(false);
      setAnimating(false);
    }
  }, [open]);

  // Lock body scroll
  React.useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  if (!mounted && !animating) return null;

  const content = (
    <div
      ref={panelRef}
      data-slot="full-screen-panel-content"
      onTransitionEnd={handleTransitionEnd}
      className={cn(
        "fixed inset-0 z-[100] flex flex-col bg-background",
        "transition-transform duration-300",
        // iOS-like ease curve
        "[transition-timing-function:cubic-bezier(0.32,0.72,0,1)]",
        visible ? "translate-x-0" : "translate-x-full",
        className
      )}
    >
      {children}
    </div>
  );

  if (typeof window === "undefined") return null;
  return createPortal(content, document.body);
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
        className
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

export {
  FullScreenPanel,
  FullScreenPanelContent,
  FullScreenPanelHeader,
  FullScreenPanelBody,
};
