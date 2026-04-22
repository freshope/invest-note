import { BottomNav } from "@/components/layout/BottomNav";
import { DetailPanelProvider } from "@/components/panels/DetailPanelProvider";

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <DetailPanelProvider>
      <main className="flex-1 pb-24">{children}</main>
      <BottomNav />
    </DetailPanelProvider>
  );
}
