// Small pure helpers for the lecturer AI Assistant tab (kept out of the screen so they can be unit tested).

// What the collapsed Materials header shows: "34 files · all ready" / "34 files · 2 not ready"
export function materialsSummary(materials) {
  if (!materials) return ''
  if (materials.length === 0) return 'none yet'
  const problems = materials.filter(m => m.status !== 'indexed').length
  const files = `${materials.length} file${materials.length === 1 ? '' : 's'}`
  return problems ? `${files} · ${problems} not ready` : `${files} · all ready`
}
