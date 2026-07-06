// 어드민 네비게이션 정의. 범위표(spec 1차 증분)와 1:1 대응.
import {
  LayoutDashboard,
  Users,
  UserMinus,
  Wallet,
  ArrowLeftRight,
  Tags,
  LineChart,
  ListChecks,
  ScrollText,
  MessageSquare,
  type LucideIcon,
} from "lucide-react";
import {
  BOARD_TYPES,
  BOARD_TYPE_ICONS,
  boardTypeToSlug,
} from "@/components/board/constants";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

// 그룹은 헤더(라벨/아이콘) + 하위 항목. children 없으면 단일 링크.
export interface NavGroup {
  label: string;
  icon: LucideIcon;
  children: NavItem[];
}

// 게시판 그룹: board_type 별 개별 메뉴(slug·아이콘은 단일 출처에서 파생).
const BOARD_GROUP: NavGroup = {
  label: "게시판",
  icon: MessageSquare,
  children: BOARD_TYPES.map((b) => ({
    href: `/boards/${boardTypeToSlug(b.value)}`,
    label: b.label,
    icon: BOARD_TYPE_ICONS[b.value],
  })),
};

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "대시보드", icon: LayoutDashboard },
  { href: "/users", label: "사용자", icon: Users },
  { href: "/withdrawals", label: "탈퇴 통계", icon: UserMinus },
  { href: "/accounts", label: "계좌", icon: Wallet },
  { href: "/trades", label: "거래", icon: ArrowLeftRight },
  { href: "/custom-tags", label: "커스텀 태그", icon: Tags },
  { href: "/stocks", label: "종목", icon: LineChart },
  { href: "/nps-unmatched", label: "NPS 매칭 큐", icon: ListChecks },
  { href: "/import-ledger", label: "일괄등록 원장", icon: ScrollText },
];

export const NAV_GROUPS: NavGroup[] = [BOARD_GROUP];
