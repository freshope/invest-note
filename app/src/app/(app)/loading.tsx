export default function Loading() {
  return (
    <div className="px-5 pt-5 space-y-4 animate-pulse">
      <div className="space-y-2">
        <div className="h-4 w-16 rounded-md bg-muted" />
        <div className="h-9 w-48 rounded-md bg-muted" />
        <div className="h-3 w-56 rounded-md bg-muted" />
      </div>
      <div className="grid grid-cols-3 gap-2">
        {[0, 1, 2].map((i) => (
          <div key={i} className="rounded-2xl bg-muted/60 p-3.5 space-y-1.5">
            <div className="h-3 w-12 rounded bg-muted" />
            <div className="h-4 w-16 rounded bg-muted" />
          </div>
        ))}
      </div>
      <div className="rounded-2xl bg-muted/60 h-64" />
      {[0, 1, 2].map((i) => (
        <div key={i} className="rounded-2xl bg-muted/60 h-28" />
      ))}
    </div>
  );
}
