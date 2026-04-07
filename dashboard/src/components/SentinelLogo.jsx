/**
 * SentinelLogo — custom SVG shield logo with "S" monogram
 */
export default function SentinelLogo({ size = 32, className = '' }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="Sentinel logo"
    >
      <defs>
        <linearGradient id="shield-grad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#6366f1" />
          <stop offset="100%" stopColor="#06b6d4" />
        </linearGradient>
        <linearGradient id="s-grad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#fff" stopOpacity="0.95" />
          <stop offset="100%" stopColor="#c7d2fe" stopOpacity="0.9" />
        </linearGradient>
        <filter id="glow">
          <feGaussianBlur stdDeviation="1.5" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
      </defs>

      {/* Shield shape */}
      <path
        d="M20 2 L36 8 L36 20 C36 29.5 28.5 37 20 38.5 C11.5 37 4 29.5 4 20 L4 8 Z"
        fill="url(#shield-grad)"
        opacity="0.9"
      />

      {/* Inner ring */}
      <path
        d="M20 5 L33 10 L33 20 C33 27.8 27 34.2 20 35.5 C13 34.2 7 27.8 7 20 L7 10 Z"
        fill="none"
        stroke="rgba(255,255,255,0.15)"
        strokeWidth="0.8"
      />

      {/* S monogram */}
      <path
        d="M24.5 14.5 C24.5 14.5 22 13 19.5 13 C17 13 15.5 14.2 15.5 15.8 C15.5 17.4 17 18 19.8 18.8 C22.6 19.6 24.5 20.5 24.5 22.5 C24.5 24.5 22.5 27 19.5 27 C16.5 27 14.5 25.5 14.5 25.5"
        stroke="url(#s-grad)"
        strokeWidth="2.2"
        strokeLinecap="round"
        fill="none"
        filter="url(#glow)"
      />
    </svg>
  )
}
