import { BottomNav } from "@/components/layout/BottomNav";
import { DetailPanelProvider } from "@/components/panels/DetailPanelProvider";
import { AccountFilterProvider } from "@/components/providers/AccountFilterProvider";
import { AuthGuard } from "@/components/providers/AuthGuard";
import { BottomNavProvider } from "@/components/providers/BottomNavProvider";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <AccountFilterProvider>
        <DetailPanelProvider>
          <BottomNavProvider>
            <main className="flex-1 pb-24">{children}</main>
            <BottomNav />
          </BottomNavProvider>
        </DetailPanelProvider>
      </AccountFilterProvider>
    </AuthGuard>
  );
}
