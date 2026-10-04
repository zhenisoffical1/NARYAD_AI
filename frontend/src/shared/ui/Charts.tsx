import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { cn } from '@/shared/lib/format'

/**
 * Графики по правилам dataviz: тонкие столбцы (≤ 24 px) со скруглением 4 px только у
 * вершины, волосяная сетка, один цвет-акцент для выделенного и приглушённый для фона
 * (пара проверена валидатором в обеих темах), подсказка при наведении и скрытая таблица
 * с теми же числами — значение никогда не доступно только через цвет или курсор.
 */

export interface ColumnPoint {
  label: string
  value: number
  accent?: boolean
}

const AXIS = { fill: 'var(--ink-3)', fontSize: 12 }

function ChartTooltip({
  active,
  payload,
  unit,
}: {
  active?: boolean
  payload?: { payload: ColumnPoint }[]
  unit: string
}) {
  const point = payload?.[0]?.payload
  if (!active || !point) return null
  return (
    <div className="rounded-[6px] border border-line bg-surface px-3 py-2 shadow-raised">
      <p className="cond text-h2 leading-none font-semibold tabular">
        {point.value} <span className="text-small font-normal text-ink-2">{unit}</span>
      </p>
      <p className="mt-1 text-small text-ink-2">{point.label}</p>
    </div>
  )
}

/** Столбцы по времени: недели или дни. Выделенные (accent) — последний период. */
export function ColumnChart({
  data,
  label,
  unit,
  height = 140,
  accentNote,
}: {
  data: ColumnPoint[]
  label: string
  unit: string
  height?: number
  /** Что значит выделенный цвет — подпись под графиком, чтобы цвет не был единственным носителем */
  accentNote?: string
}) {
  const ticks = data.length > 14 ? Math.ceil(data.length / 7) : 0
  return (
    <figure className="m-0">
      <div style={{ height }} aria-hidden>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 6, right: 4, bottom: 0, left: -18 }} barCategoryGap={2}>
            <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
            <XAxis
              dataKey="label"
              tick={AXIS}
              tickLine={false}
              axisLine={{ stroke: 'var(--line)' }}
              interval={ticks ? ticks - 1 : 0}
            />
            <YAxis tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false} width={40} />
            <Tooltip
              cursor={{ fill: 'var(--plate)', opacity: 0.6 }}
              content={<ChartTooltip unit={unit} />}
              isAnimationActive={false}
            />
            <Bar dataKey="value" maxBarSize={24} radius={[4, 4, 0, 0]} isAnimationActive={false}>
              {data.map((point) => (
                <Cell
                  key={point.label}
                  fill={point.accent ? 'var(--chart-accent)' : 'var(--chart-muted)'}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {accentNote && (
        <figcaption className="mt-1.5 flex items-center gap-3 text-small text-ink-3">
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden className="inline-block h-2.5 w-2.5 rounded-[2px] bg-chart-accent" />
            {accentNote}
          </span>
        </figcaption>
      )}
      <DataTable caption={label} unit={unit} rows={data} />
    </figure>
  )
}

/** Скрытая таблица с числами графика — для экранного диктора и копирования. */
function DataTable({ caption, unit, rows }: { caption: string; unit: string; rows: ColumnPoint[] }) {
  return (
    <table className="sr-only">
      <caption>{caption}</caption>
      <tbody>
        {rows.map((row) => (
          <tr key={row.label}>
            <th scope="row">{row.label}</th>
            <td>
              {row.value} {unit}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

/**
 * Горизонтальные полосы со значением у конца — сравнение «о ком находка» с остальными,
 * топ оборудования, рейтинг. Подпись и число — текстом, полоса — только масштаб.
 */
export function BarList({
  rows,
  max,
  format = (v) => String(v),
  className,
}: {
  rows: { label: string; value: number; accent?: boolean; hint?: string }[]
  max?: number
  format?: (value: number) => string
  className?: string
}) {
  const top = max ?? Math.max(...rows.map((r) => r.value), 1)
  return (
    <ul className={cn('flex flex-col gap-2.5', className)}>
      {rows.map((row) => (
        <li key={row.label} className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-3 gap-y-1">
          <span className="min-w-0 truncate text-small" title={row.label}>
            {row.label}
            {row.hint && <span className="text-ink-3"> · {row.hint}</span>}
          </span>
          <span className="cond text-body font-semibold tabular">{format(row.value)}</span>
          <span aria-hidden className="col-span-2 h-2 overflow-hidden rounded-[3px] bg-plate">
            <span
              className={cn('block h-full rounded-[3px]', row.accent ? 'bg-chart-accent' : 'bg-chart-muted')}
              style={{ width: `${Math.max(2, (row.value / top) * 100)}%` }}
            />
          </span>
        </li>
      ))}
    </ul>
  )
}
