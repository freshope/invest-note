export default function HomePage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-4 text-center">
      <h1 className="text-xl font-semibold text-foreground mb-2">홈</h1>
      <p className="text-sm text-muted-foreground">
        총 자산, 계좌 요약, 보유 종목이 여기에 표시됩니다
      </p>
    </div>
  );
}
