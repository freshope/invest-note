"use client";

import { Calendar as CalendarUI } from "@/components/ui/calendar";
import type { ComponentProps } from "react";
import { ko } from "date-fns/locale";

function Calendar(props: ComponentProps<typeof CalendarUI>) {
  return (
    <CalendarUI
      locale={ko}
      {...props}
    />
  );
}

export { Calendar };
