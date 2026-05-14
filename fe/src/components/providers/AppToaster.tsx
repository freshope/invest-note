"use client";

import { Toaster } from "sonner";

export function AppToaster() {
  return (
    <Toaster
      position="top-center"
      offset="16px"
      mobileOffset={{
        top: "calc(env(safe-area-inset-top) + 16px)",
        right: "16px",
        bottom: "16px",
        left: "16px",
      }}
      richColors
    />
  );
}
