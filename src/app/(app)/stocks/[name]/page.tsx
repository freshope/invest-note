interface StockDetailPageProps {
  params: Promise<{ name: string }>;
}

export default async function StockDetailPage({ params }: StockDetailPageProps) {
  const { name } = await params;
  const decodedName = decodeURIComponent(name);

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-4 text-center">
      <h1 className="text-xl font-semibold text-foreground mb-2">{decodedName}</h1>
      <p className="text-sm text-muted-foreground">
        종목 상세 페이지 준비 중
      </p>
    </div>
  );
}
