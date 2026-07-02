"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { accountsApi, boardApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { useAuth } from "@/components/providers/AuthProvider";
import { Button } from "@/components/base/Button";
import {
  FullScreenPanel,
  FullScreenPanelContent,
  FullScreenPanelHeader,
  FullScreenPanelBody,
} from "@/components/base/FullScreenPanel";
import { AccountList } from "@/components/settings/AccountList";
import { AppearanceSection } from "@/components/settings/AppearanceSection";
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

  // unread 점/뱃지 — 인증 사용자만 조회. 3종 unread 단일 출처(page 비의존 전량 스캔 summary).
  const unreadSummaryQuery = useQuery({
    queryKey: queryKeys.unreadSummary,
    queryFn: () => boardApi.unreadSummary(),
    enabled: !!user,
  });
  const noticesQuery = useQuery({
    queryKey: queryKeys.notices,
    queryFn: () => boardApi.listNotices(),
    enabled: !!user,
  });

  // board_type 별 unread 점 — unread-summary 단일 출처. invalidate(myPosts 루트 prefix)로 자연 갱신.
  // BE-lag(summary 부재) 시 모두 false → 점 미표시 안전 degrade.
  const myPostsUnread = unreadSummaryQuery.data?.unread ?? {
    feedback: false,
    bug_report: false,
    broker_statement: false,
  };

  // 공지 점 — 서버 EXISTS 판정(has_unread). BE-lag 시 필드 부재면 점 미표시로 degrade.
  const noticeUnread = noticesQuery.data?.has_unread === true;

  // 메뉴 진입 = 목록 패널 오픈. 읽음은 상세 진입 시 서버에 기록되고 my-posts invalidate 로 점이 갱신된다.
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

        {/* 화면 */}
        <section className="space-y-3">
          <h2 className={SECTION_LABEL}>화면</h2>
          <AppearanceSection />
        </section>

        {/* 소식 */}
        <section className="space-y-3">
          <h2 className={SECTION_LABEL}>소식</h2>
          <div className={MENU_GROUP}>
            <SettingsMenuRow
              label="공지사항"
              dot={noticeUnread}
              onClick={() => {
                // 진입 시 서버 읽음 처리 → notices 재조회로 has_unread 갱신(점 해제). NoticePanel 무변경.
                // POST 성공 후 invalidate(race 회피: 미커밋 상태에서 refetch 시 has_unread=true 유지 방지).
                // 안읽은 공지가 없으면(점 꺼짐) seen 갱신이 무의미 → 진입마다 중복 쓰기/재조회 skip.
                if (noticeUnread) {
                  void boardApi
                    .markNoticesSeen()
                    .then(() =>
                      queryClient.invalidateQueries({ queryKey: queryKeys.notices }),
                    )
                    .catch(() => {});
                }
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
      <NoticePanel open={noticeOpen} onOpenChange={setNoticeOpen} />
      {/* 목록(메인) 패널 — 위에 작성 폼 패널이 스택된다. unread 점은 서버 플래그 + invalidate 로 갱신. */}
      <MyPostsListPanel
        open={feedbackListOpen}
        onOpenChange={setFeedbackListOpen}
        boardType="feedback"
        title="의견 보내기"
        onCompose={() => setFeedbackOpen(true)}
      />
      <MyPostsListPanel
        open={bugReportListOpen}
        onOpenChange={setBugReportListOpen}
        boardType="bug_report"
        title="오류 신고"
        onCompose={() => setBugReportOpen(true)}
      />
      <MyPostsListPanel
        open={brokerListOpen}
        onOpenChange={setBrokerListOpen}
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
