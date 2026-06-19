// 어드민 네비게이션 정의. 범위표(spec 1차 증분)와 1:1 대응.
import {
  LayoutDashboard,
  Users,
  Wallet,
  ArrowLeftRight,
  Tags,
  LineChart,
  ListChecks,
  MessageSquare,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "대시보드", icon: LayoutDashboard },
  { href: "/users", label: "사용자", icon: Users },
  { href: "/accounts", label: "계좌", icon: Wallet },
  { href: "/trades", label: "거래", icon: ArrowLeftRight },
  { href: "/custom-tags", label: "커스텀 태그", icon: Tags },
  { href: "/stocks", label: "종목", icon: LineChart },
  { href: "/nps-unmatched", label: "NPS 매칭 큐", icon: ListChecks },
  { href: "/boards", label: "게시판", icon: MessageSquare },
];
