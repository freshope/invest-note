"use client";

import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { accountsApi, boardApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import {
  getLastSeenNotice,
  setLastSeenNotice,
  getLastReadMyPostMap,
} from "@/lib/board-seen";
import { isMyPostUnread } from "@/lib/board-post";
import type { MyPostBoardType } from "@/lib/api-client";
import { useAuth } from "@/components/providers/AuthProvider";
import { Button } from "@/components/base/Button";
import {
  FullScreenPanel,
  FullScreenPanelContent,
  FullScreenPanelHeader,
  FullScreenPanelBody,
} from "@/components/base/FullScreenPanel";
import { AccountList } from "@/components/settings/AccountList";
import { SettingsMenuRow } from "@/components/settings/SettingsMenuRow";
import { NoticePanel } from "@/components/settings/NoticePanel";
import { MyPostsListPanel } from "@/components/settings/MyPostsListPanel";
import { FeedbackPanel } from "@/components/settings/FeedbackPanel";
import { BugReportPanel } from "@/components/settings/BugReportPanel";
import { DeleteAccountSection } from "@/components/settings/DeleteAccountSection";
import { BrokerStatementPanel } from "@/components/broker-statement/BrokerStatementPanel";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState } from "@/components/shared/ErrorState";
import { useAppVersion } from "@/hooks/useAppVersion";
import { openExternal } from "@/lib/external-link";
import { LEGAL_LINKS } from "@/lib/legal-links";
import { signOut } from "@/lib/auth";

const SECTION_LABEL = "text-[13px] font-semibold text-muted-foreground px-1";
const MENU_GROUP = "rounded-2xl bg-muted/60 overflow-hidden";

export default function SettingsPage() {
  const { user } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { version, build } = useAppVersion();

  const [accountsOpen, setAccountsOpen] = useState(false);
  const [noticeOpen, setNoticeOpen] = useState(false);
  // 메뉴 진입 = 목록 패널. 그 위에 "작성" 으로 write 폼 패널을 스택한다.
  const [feedbackListOpen, setFeedbackListOpen] = useState(false);
  const [bugReportListOpen, setBugReportListOpen] = useState(false);
  const [brokerListOpen, setBrokerListOpen] = useState(false);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [bugReportOpen, setBugReportOpen] = useState(false);
  const [brokerStatementOpen, setBrokerStatementOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);

  // unread 점/뱃지 — 인증 사용자만 조회. 목록 패널과 queryKey 공유(dedup).
  const myPostsQuery = useQuery({
    queryKey: queryKeys.myPosts,
    queryFn: () => boardApi.myPosts(),
    enabled: !!user,
  });
  const noticesQuery = useQuery({
    queryKey: queryKeys.notices,
    queryFn: () => boardApi.listNotices(),
    enabled: !!user,
  });

  // localStorage 는 비반응형이라 query.data + recomputeTick 으로 파생 계산(useMemo).
  // 첫 렌더 data=undefined 라 안전. 패널/상세 닫힐 때 recomputeTick 으로 재계산해 점 해제.
  const [recomputeTick, setRecomputeTick] = useState(0);

  // board_type 별 unread 점. read map 1회 읽어 글마다 재파싱 방지, 3개 type 1회 순회.
  const myPostsUnread = useMemo<Record<MyPostBoardType, boolean>>(() => {
    const items = myPostsQuery.data?.items ?? [];
    const lastReadMap = getLastReadMyPostMap();
    const result: Record<MyPostBoardType, boolean> = {
      feedback: false,
      bug_report: false,
      broker_statement: false,
    };
    for (const p of items) {
      if (!result[p.board_type] && isMyPostUnread(p, lastReadMap)) {
        result[p.board_type] = true;
      }
    }
    return result;
  }, [myPostsQuery.data, recomputeTick]);

  // 최신 공지 created_at > lastSeenNotice 면 뱃지. 시각은 getTime 수치 비교(ISO 포맷 차이 회피).
  const noticeUnread = useMemo(() => {
    const lastSeen = getLastSeenNotice();
    const items = noticesQuery.data?.items ?? [];
    const latestMs = items.reduce(
      (max, n) => Math.max(max, new Date(n.created_at).getTime()),
      0,
    );
    return latestMs > 0 && (!lastSeen || latestMs > new Date(lastSeen).getTime());
  }, [noticesQuery.data, recomputeTick]);

  // 메뉴 진입 = 목록 패널 오픈. 읽음은 상세를 열 때 글별로 기록되므로 여기선 점을 건드리지 않는다.
  // (목록/상세에서 읽은 뒤 목록 패널이 닫힐 때 recomputeTick 으로 메뉴 점 재계산)
  const openListPanel = (setOpen: (open: boolean) => void) => {
    setOpen(true);
  };

  async function handleSignOut() {
    setSigningOut(true);
    try {
      // 서버 호출 실패에도 로컬 세션은 무조건 비우도록 scope: "local"(signOut 내부 고정)
      await signOut();
    } catch (error) {
      console.error("[signOut]", error);
      toast.error("로그아웃 중 문제가 발생했어요. 다시 시도해주세요.");
    } finally {
      // AuthGuard에 의존하지 않고 직접 정리·이동 — 어떤 환경에서도 동일하게 동작.
      queryClient.clear();
      router.replace("/login");
      setSigningOut(false);
    }
  }

  return (
    <>
      <PageHeader title="설정" />
      <div className="px-5 pt-2 pb-8 space-y-10">
        {/* 프로필 헤더 */}
        <div className="rounded-2xl bg-muted/60 p-5 space-y-1">
          <p className="text-[12px] font-semibold text-muted-foreground">이메일</p>
          <p className="text-[15px] font-medium text-foreground">
            {user?.email ?? ""}
          </p>
        </div>

        {/* 자산 관리 */}
        <section className="space-y-3">
          <h2 className={SECTION_LABEL}>자산 관리</h2>
          <div className={MENU_GROUP}>
            <SettingsMenuRow
              label="계좌 관리"
              onClick={() => setAccountsOpen(true)}
            />
          </div>
        </section>

        {/* 소식 */}
        <section className="space-y-3">
          <h2 className={SECTION_LABEL}>소식</h2>
          <div className={MENU_GROUP}>
            <SettingsMenuRow
              label="공지사항"
              dot={noticeUnread}
              onClick={() => {
                // 진입 시 마지막 확인 시각 기록 + recompute 로 뱃지 해제(NoticePanel 은 손대지 않음).
                setLastSeenNotice();
                setRecomputeTick((t) => t + 1);
                setNoticeOpen(true);
              }}
            />
          </div>
        </section>

        {/* 고객 지원 */}
        <section className="space-y-3">
          <h2 className={SECTION_LABEL}>고객 지원</h2>
          <div className={MENU_GROUP}>
            <SettingsMenuRow
              label="의견 보내기"
              dot={myPostsUnread.feedback}
              onClick={() => openListPanel(setFeedbackListOpen)}
            />
            <SettingsMenuRow
              label="오류 신고"
              dot={myPostsUnread.bug_report}
              onClick={() => openListPanel(setBugReportListOpen)}
            />
            <SettingsMenuRow
              label="거래내역서 제보"
              dot={myPostsUnread.broker_statement}
              onClick={() => openListPanel(setBrokerListOpen)}
            />
          </div>
        </section>

        {/* 약관·정책 */}
        <section className="space-y-3">
          <h2 className={SECTION_LABEL}>약관·정책</h2>
          <div className={MENU_GROUP}>
            <SettingsMenuRow
              label="서비스 이용약관"
              variant="external"
              onClick={() => openExternal(LEGAL_LINKS.terms)}
            />
            <SettingsMenuRow
              label="개인정보 처리방침"
              variant="external"
              onClick={() => openExternal(LEGAL_LINKS.privacy)}
            />
          </div>
        </section>

        {/* 계정 */}
        <section className="space-y-3">
          <h2 className={SECTION_LABEL}>계정</h2>
          <div className={MENU_GROUP}>
            <Button
              type="button"
              variant="ghost"
              className="w-full justify-start h-12 px-5 text-[15px] text-foreground hover:bg-foreground/5"
              disabled={signingOut}
              onClick={handleSignOut}
            >
              {signingOut ? "로그아웃 중..." : "로그아웃"}
            </Button>
            <DeleteAccountSection />
          </div>
        </section>

        <p className="text-xs text-center text-muted-foreground">
          투자노트 v{version}
          {build ? ` (${build})` : ""}
        </p>
      </div>

      {/* 패널들 — 각 메뉴 진입점 */}
      <AccountListPanel open={accountsOpen} onOpenChange={setAccountsOpen} />
      <NoticePanel
        open={noticeOpen}
        onOpenChange={(o) => {
          setNoticeOpen(o);
          if (!o) setRecomputeTick((t) => t + 1);
        }}
      />
      {/* 목록(메인) 패널 — 닫힐 때 unread 재계산. 위에 작성 폼 패널이 스택된다. */}
      <MyPostsListPanel
        open={feedbackListOpen}
        onOpenChange={(o) => {
          setFeedbackListOpen(o);
          if (!o) setRecomputeTick((t) => t + 1);
        }}
        boardType="feedback"
        title="의견 보내기"
        onCompose={() => setFeedbackOpen(true)}
      />
      <MyPostsListPanel
        open={bugReportListOpen}
        onOpenChange={(o) => {
          setBugReportListOpen(o);
          if (!o) setRecomputeTick((t) => t + 1);
        }}
        boardType="bug_report"
        title="오류 신고"
        onCompose={() => setBugReportOpen(true)}
      />
      <MyPostsListPanel
        open={brokerListOpen}
        onOpenChange={(o) => {
          setBrokerListOpen(o);
          if (!o) setRecomputeTick((t) => t + 1);
        }}
        boardType="broker_statement"
        title="거래내역서 제보"
        onCompose={() => setBrokerStatementOpen(true)}
      />

      {/* 작성 폼 패널(write 전용) — 목록 패널 위에 스택. 제출 성공 시 myPosts invalidate 됨. */}
      <FeedbackPanel open={feedbackOpen} onOpenChange={setFeedbackOpen} />
      <BugReportPanel open={bugReportOpen} onOpenChange={setBugReportOpen} />
      <BrokerStatementPanel
        open={brokerStatementOpen}
        onOpenChange={setBrokerStatementOpen}
        defaultType="unsupported_broker"
        brokerSource={{ mode: "freetext" }}
      />
    </>
  );
}

interface AccountListPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function AccountListPanel({ open, onOpenChange }: AccountListPanelProps) {
  // accounts 로딩/에러는 이 패널 안으로 격리 — 설정 메인 화면은 막지 않는다.
  const { data: accounts, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.accounts,
    queryFn: accountsApi.list,
    enabled: open,
  });

  return (
    <FullScreenPanel open={open} onOpenChange={onOpenChange}>
      <FullScreenPanelContent>
        <FullScreenPanelHeader title="계좌 관리" />
        <FullScreenPanelBody>
          <div className="px-5 pt-2 pb-6">
            {isLoading ? (
              <div className="space-y-4 animate-pulse">
                {[0, 1].map((i) => (
                  <div key={i} className="rounded-2xl bg-muted/60 h-24" />
                ))}
              </div>
            ) : isError ? (
              <ErrorState onRetry={refetch} />
            ) : (
              <AccountList accounts={accounts ?? []} />
            )}
          </div>
        </FullScreenPanelBody>
      </FullScreenPanelContent>
    </FullScreenPanel>
  );
}
