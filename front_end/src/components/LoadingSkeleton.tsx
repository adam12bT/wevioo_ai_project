interface LoadingSkeletonProps {
  lines?: number;
  className?: string;
  height?: 'sm' | 'md' | 'lg';
}

export function LoadingSkeleton({ lines = 3, className = '', height = 'md' }: LoadingSkeletonProps) {
  const h = height === 'sm' ? 'h-3' : height === 'lg' ? 'h-6' : 'h-4';
  return (
    <div className={`space-y-2.5 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className={`skeleton ${h}`}
          style={{ width: i === lines - 1 ? '60%' : '100%' }}
        />
      ))}
    </div>
  );
}

export function CardSkeleton() {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="skeleton h-4 w-24 mb-3" />
      <div className="skeleton h-8 w-16" />
    </div>
  );
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4">
          <div className="skeleton h-4 flex-1" />
          <div className="skeleton h-4 flex-1" />
          <div className="skeleton h-4 w-24" />
        </div>
      ))}
    </div>
  );
}
