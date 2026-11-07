export default function RejectionCard({ validations }) {
  const rejections = validations.filter((v) => v.severity === 'reject')

  return (
    <div className="rounded-xl border-2 border-danger/60 bg-danger/10 p-6 shadow-[0_0_40px_-12px_rgba(248,113,113,0.35)]">
      <div className="mb-4 flex items-center gap-3">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.75"
          className="h-6 w-6 shrink-0 text-danger"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
          />
        </svg>
        <h3 className="text-base font-bold uppercase tracking-wide text-danger">Rejected by the Trust Gate</h3>
      </div>

      <div className="space-y-5">
        {rejections.map((v) => (
          <div key={v.message} className="rounded-lg border border-danger/30 bg-navy-950/50 p-5">
            <p className="mb-3 font-mono text-2xl font-bold tracking-tight text-danger">{v.code}</p>
            <p className="text-[15px] leading-relaxed text-mist-100">{v.message}</p>
            <div className="mt-4 rounded-md border border-teal-glow/30 bg-teal-glow/5 p-3">
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-teal-glow">Remedy</p>
              <p className="text-sm leading-relaxed text-mist-300">{v.remedy}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
