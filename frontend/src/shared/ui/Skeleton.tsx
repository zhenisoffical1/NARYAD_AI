import { cn } from '@/shared/lib/format'

/** Заготовка на время загрузки. Статичная: интерфейс не двигается без причины. */
export function Skeleton({ className }: { className?: string }) {
  return <span aria-hidden className={cn('block rounded-tag bg-plate', className)} />
}

export function TagSkeleton() {
  return (
    <div className="flex rounded-tag border border-line bg-surface" aria-busy="true">
      <span className="w-3.5 rounded-l-tag bg-plate" />
      <div className="flex flex-1 flex-col gap-2 p-3">
        <div className="flex justify-between">
          <Skeleton className="h-7 w-28" />
          <Skeleton className="h-7 w-24" />
        </div>
        <Skeleton className="h-5 w-3/5" />
        <Skeleton className="h-5 w-4/5" />
        <Skeleton className="mt-1 h-5 w-full" />
      </div>
    </div>
  )
}
