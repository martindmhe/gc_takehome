import { Button } from '@/components/ui/button'

export function Pagination({
  offset,
  pageSize,
  total,
  onChange,
}: {
  offset: number
  pageSize: number
  total: number
  onChange: (offset: number) => void
}) {
  if (total <= pageSize) return null
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted-foreground">
        {offset + 1}–{Math.min(offset + pageSize, total)} of {total}
      </span>
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={offset === 0}
          onClick={() => onChange(Math.max(0, offset - pageSize))}
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={offset + pageSize >= total}
          onClick={() => onChange(offset + pageSize)}
        >
          Next
        </Button>
      </div>
    </div>
  )
}
