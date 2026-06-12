"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import {
  QUERY_DEFAULT_RETRY,
  QUERY_DEFAULT_STALE_TIME_MS,
} from "@/lib/constants/query";

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: QUERY_DEFAULT_STALE_TIME_MS,
            retry: QUERY_DEFAULT_RETRY,
          },
        },
      }),
  );

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
