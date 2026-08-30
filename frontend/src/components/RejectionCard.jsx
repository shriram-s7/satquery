export default function RejectionCard({ validations }) {
  const rejections = validations.filter((v) => v.severity === 'reject')

  return (
    <div className="rounded-xl border border-danger/50 bg-danger/10 p-5">
      <div className="mb-3 flex items-center gap-2">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.75"
          className="h-5 w-5 text-danger"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
          />
        </svg>
        <h3 className="text-sm font-semibold uppercase tracking-wide text-danger">Rejected by the Trust Gate</h3>
      </div>

      <div className="space-y-4">
        {rejections.map((v) => (
          <div key={v.message} className="rounded-lg border border-danger/30 bg-navy-950/40 p-4">
            <p className="mb-2 font-mono text-[11px] font-semibold uppercase tracking-wide text-danger">
              {v.code}
            </p>
            <p className="text-sm leading-relaxed text-mist-100">{v.message}</p>
            <p className="mt-3 text-xs leading-relaxed text-mist-300">
              <span className="font-semibold text-teal-glow">Remedy — </span>
              {v.remedy}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}
