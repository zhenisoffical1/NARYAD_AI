import { useMemo } from 'react'
import { encode } from 'uqr'

import { cn } from '@/shared/lib/format'

/**
 * QR-код одним SVG-контуром. Всегда чёрный на белом с полем в 2 модуля — так его читает
 * любая камера, в том числе с экрана проектора и в тёмной теме.
 */
export function QrCode({ value, label, className }: { value: string; label: string; className?: string }) {
  const { path, size } = useMemo(() => {
    const qr = encode(value, { ecc: 'M', border: 2 })
    let d = ''
    qr.data.forEach((row, y) => {
      row.forEach((dark, x) => {
        if (dark) d += `M${x} ${y}h1v1h-1z`
      })
    })
    return { path: d, size: qr.size }
  }, [value])

  return (
    <svg
      role="img"
      aria-label={label}
      viewBox={`0 0 ${size} ${size}`}
      shapeRendering="crispEdges"
      className={cn('block bg-white', className)}
    >
      <path d={path} fill="#000" />
    </svg>
  )
}
