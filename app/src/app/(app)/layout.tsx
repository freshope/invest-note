"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { BottomNav } from "@/components/layout/BottomNav";
import { DetailPanelProvider } from "@/components/panels/DetailPanelProvider";
import { AccountFilterProvider } from "@/components/providers/AccountFilterProvider";
import { useAuth } from "@/components/providers/AuthProvider";
import { FullPageSpinner } from "@/components/base/FullPageSpinner";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, user, router]);

  if (loading) return <FullPageSpinner />;

  if (!user) return null;

  return (
    <AccountFilterProvider>
      <DetailPanelProvider>
        <main className="flex-1 pb-24">{children}</main>
        <BottomNav />
      </DetailPanelProvider>
    </AccountFilterProvider>
  );
}
