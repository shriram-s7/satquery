function formatLine(plan) {
  const [rows, cols] = plan.tile_grid
  const gsd = plan.input_gsd.toFixed(2)

  let factorLabel
  if (plan.strategy === 'passthrough') {
    factorLabel = 'passthrough (≈1x)'
  } else if (plan.strategy === 'upsample') {
    factorLabel = `${plan.scale_factor.toFixed(1)}x upsample`
  } else {
    factorLabel = `${(1 / plan.scale_factor).toFixed(1)}x downsample`
  }

  const tilingLabel =
    plan.tile_count > 1 ? `${rows}x${cols} tiling · ${plan.tile_count} patches aggregated` : '1 patch'

  return `${plan.path} · ${gsd} m/px → model domain 10 m/px · ${factorLabel} · ${tilingLabel}`
}

export default function NormalizationStrip({ plans }) {
  if (!plans?.length) return null

  const distinctPlans = Array.from(new Map(plans.map((plan) => [plan.path, plan])).values())

  return (
    <div className="rounded-lg border border-navy-600 bg-navy-850 px-4 py-3">
      <div className="space-y-2">
        {distinctPlans.map((plan) => (
          <p key={plan.path} className="font-mono text-[11px] leading-snug text-mist-300">
            <span className="text-teal-glow">▸</span> {formatLine(plan)}
          </p>
        ))}
      </div>
    </div>
  )
}
