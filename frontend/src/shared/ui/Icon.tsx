import type { SVGProps } from 'react'

/** Набор линейных пиктограмм 24×24, обводка 2 px. Рисованы под проект — без внешних зависимостей. */
const PATHS = {
  check: 'M5 12.5l4.5 4.5L19 7.5',
  x: 'M6 6l12 12M18 6L6 18',
  plus: 'M12 5v14M5 12h14',
  minus: 'M5 12h14',
  chevronLeft: 'M15 18l-6-6 6-6',
  chevronRight: 'M9 18l6-6-6-6',
  chevronDown: 'M6 9l6 6 6-6',
  clock: 'M12 7v5l3.5 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  alert: 'M12 4L2.5 20h19L12 4zM12 10v4.5M12 17.5v.01',
  camera:
    'M4 8h3l1.5-2.5h7L17 8h3a1 1 0 011 1v10a1 1 0 01-1 1H4a1 1 0 01-1-1V9a1 1 0 011-1zM12 17a3.5 3.5 0 100-7 3.5 3.5 0 000 7z',
  image: 'M4 5h16v14H4zM4 16l4.5-4.5 3.5 3.5 2.5-2.5L20 18M15.5 9.5v.01',
  pause: 'M8.5 5v14M15.5 5v14',
  play: 'M7 5l12 7-12 7V5z',
  mic: 'M12 3a3 3 0 00-3 3v5a3 3 0 006 0V6a3 3 0 00-3-3zM5.5 11a6.5 6.5 0 0013 0M12 17.5V21',
  search: 'M10.5 17a6.5 6.5 0 100-13 6.5 6.5 0 000 13zM15.5 15.5L20 20',
  qr: 'M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h2.5v2.5H14zM17.5 17.5H20V20h-2.5zM14 18.5v1.5M18.5 14H20',
  user: 'M12 12a4 4 0 100-8 4 4 0 000 8zM4.5 20.5c.6-3.6 3.7-5.5 7.5-5.5s6.9 1.9 7.5 5.5',
  users: 'M9 11a3.5 3.5 0 100-7 3.5 3.5 0 000 7zM2.5 20c.5-3.3 3.1-5 6.5-5s6 1.7 6.5 5M16 4.3a3.5 3.5 0 010 6.4M18 15.2c2 .6 3.2 2.2 3.5 4.8',
  bell: 'M6 16.5V11a6 6 0 1112 0v5.5l1.5 1.5h-15L6 16.5zM10 20.5a2 2 0 004 0',
  list: 'M9 6h11M9 12h11M9 18h11M4.5 6v.01M4.5 12v.01M4.5 18v.01',
  logout: 'M14 4h5v16h-5M10 8l-4 4 4 4M6 12h10',
  globe: 'M12 21a9 9 0 100-18 9 9 0 000 18zM3.5 9h17M3.5 15h17M12 3c2.5 2.6 3.5 5.6 3.5 9s-1 6.4-3.5 9c-2.5-2.6-3.5-5.6-3.5-9s1-6.4 3.5-9z',
  moon: 'M20 14.5A8.5 8.5 0 019.5 4a8.5 8.5 0 1010.5 10.5z',
  sun: 'M12 16.5a4.5 4.5 0 100-9 4.5 4.5 0 000 9zM12 2.5V4.5M12 19.5v2M4.6 4.6L6 6M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4L6 18M18 6l1.4-1.4',
  trash: 'M4 7h16M9.5 7V4.5h5V7M6.5 7l1 13h9l1-13M10 11v5M14 11v5',
  spark: 'M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3zM18.5 15.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7.7-1.8z',
  wrench: 'M14.5 6.5a4 4 0 005 5l-9 9a2.1 2.1 0 01-3-3l9-9a4 4 0 01-2-2zM14.5 6.5L17 4',
  filter: 'M4 5h16l-6 7.5V19l-4-2v-4.5L4 5z',
  chart: 'M4 20h16M7 16v-5M12 16V6M17 16v-8',
  report: 'M6 3h9l4 4v14H6zM14.5 3v4.5H19M9 12h7M9 16h7',
  history: 'M3.5 12a8.5 8.5 0 102.5-6M3.5 4.5V9H8M12 8v4.5l3 1.5',
  undo: 'M9 14L4 9l5-5M4 9h10.5a5.5 5.5 0 010 11H11',
  swap: 'M7 4L3 8l4 4M3 8h14M17 20l4-4-4-4M21 16H7',
  flag: 'M5 21V4M5 4h11l-2 4 2 4H5',
  signal: 'M5 18v-3M9.5 18v-6M14 18V9M18.5 18V6',
  send: 'M4 12L20 4l-5 16-3-7-8-1z',
  doc: 'M7 3h7l4 4v14H7zM13.5 3v4.5H18',
  eye: 'M2.5 12s3.5-6.5 9.5-6.5S21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12zM12 15a3 3 0 100-6 3 3 0 000 6z',
  edit: 'M4 20h4l11-11-4-4L4 16v4zM13.5 6.5l4 4',
} as const

export type IconName = keyof typeof PATHS

interface IconProps extends SVGProps<SVGSVGElement> {
  name: IconName
  size?: number
  label?: string
}

export function Icon({ name, size = 24, label, ...rest }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
      {...rest}
    >
      <path d={PATHS[name]} />
    </svg>
  )
}
