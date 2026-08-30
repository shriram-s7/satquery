const BASE = '/api'

async function extractErrorDetail(res) {
  try {
    const data = await res.json()
    return data?.detail
  } catch {
    return null
  }
}

export async function checkHealth() {
  try {
    const res = await fetch(`${BASE}/health`)
    return res.ok
  } catch {
    return false
  }
}

export async function inspectFile(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/inspect`, { method: 'POST', body: form })
  if (!res.ok) {
    throw new Error((await extractErrorDetail(res)) || `Could not read ${file.name} (${res.status})`)
  }
  return res.json()
}

export async function runQuery(files, query) {
  const form = new FormData()
  for (const file of files) form.append('files', file)
  form.append('query', query)
  const res = await fetch(`${BASE}/query`, { method: 'POST', body: form })
  if (!res.ok) {
    throw new Error((await extractErrorDetail(res)) || `Query failed (${res.status})`)
  }
  return res.json()
}

export async function fetchReportPdf(response, images) {
  const res = await fetch(`${BASE}/report`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ response, images }),
  })
  if (!res.ok) {
    throw new Error((await extractErrorDetail(res)) || `Report generation failed (${res.status})`)
  }
  return res.blob()
}
