// Talks to the local JobPilot API and drives content.js in every frame of the active tab.
// It fills fields only; submitting is always left to the user.
const API = 'http://127.0.0.1:8000/api'
const $ = (id) => document.getElementById(id)
const say = (text) => { $('status').textContent = text }

async function api(method, path, body) {
  const res = await fetch(API + path, {
    method,
    headers: { 'X-JobPilot': '1', 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail ?? detail } catch { /* not JSON */ }
    throw new Error(detail)
  }
  return res.json()
}

async function activeTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
  return tab
}

function siteOf(url) {
  try { return new URL(url).hostname.replace(/^www\./, '') } catch { return '' }
}

function isDisabled(host, disabled) {
  return disabled.some((d) => host === d || host.endsWith('.' + d))
}

// Forms often live in a cross-origin iframe (Greenhouse, Lever embeds), which needs host
// access to that origin; ask once for all sites, from this click.
async function ensureAccess() {
  const all = { origins: ['https://*/*', 'http://*/*'] }
  if (await chrome.permissions.contains(all)) return true
  return chrome.permissions.request(all)
}

async function inject(tabId) {
  await chrome.scripting.executeScript({ target: { tabId, allFrames: true }, files: ['content.js'] })
}

async function inFrames(tabId, func, args = []) {
  const res = await chrome.scripting.executeScript({ target: { tabId, allFrames: true }, func, args })
  return res.filter((r) => r.result)
}

async function cvFile() {
  const res = await fetch(API + '/apply/cv')
  if (!res.ok) return null
  const bytes = new Uint8Array(await res.arrayBuffer())
  let bin = ''
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  const name = (res.headers.get('content-disposition') || '').match(/filename="?([^";]+)/)?.[1] || 'CV.pdf'
  return { name, data: btoa(bin) }
}

async function fill() {
  const tab = await activeTab()
  if (!(await ensureAccess())) return say('Access to the page was not granted.')
  say('Reading the form…')
  await inject(tab.id)
  const frames = await inFrames(tab.id, () => window.__jpAssist.collect())
  const fields = frames.flatMap((f) => f.result.map((x) => ({ ...x, id: `${f.frameId}:${x.id}` })))
  if (!fields.length) return say('No form fields found. Open the application form first.')
  say(`Filling ${fields.length} fields…` + ($('draft').checked ? '\nAI drafts can take a minute.' : ''))
  const r = await api('POST', '/apply/fill', { url: tab.url, fields, draft: $('draft').checked })
  const cv = fields.some((f) => f.kind === 'file') ? await cvFile() : null
  const counts = { high: 0, medium: 0, low: 0 }
  for (const f of frames) {
    const mine = r.fields.filter((x) => x.id.startsWith(`${f.frameId}:`))
      .map((x) => ({ ...x, id: x.id.slice(x.id.indexOf(':') + 1) }))
    const res = await chrome.scripting.executeScript({
      target: { tabId: tab.id, frameIds: [f.frameId] },
      func: (results, file) => window.__jpAssist.apply(results, file),
      args: [mine, cv],
    })
    const c = res[0]?.result || {}
    for (const k of Object.keys(counts)) counts[k] += c[k] || 0
  }
  const job = r.job_title ? `Job: ${r.job_title}\n` : 'Job not in JobPilot (Mark applied will not work).\n'
  say(`${job}${counts.high} sure, ${counts.medium} to check, ${counts.low} empty.\nReview, then submit yourself.`)
}

async function save() {
  const tab = await activeTab()
  await inject(tab.id)
  const frames = await inFrames(tab.id, () => window.__jpAssist.harvest())
  const answers = frames.flatMap((f) => f.result)
  if (!answers.length) return say('Nothing to save.')
  await api('POST', '/answers', answers)
  say(`Saved ${answers.length} answers for next time.`)
}

async function markApplied() {
  const tab = await activeTab()
  const job = await api('POST', '/apply/mark-applied', { url: tab.url })
  say(`Marked applied: ${job.title}`)
}

async function init() {
  const tab = await activeTab()
  const host = siteOf(tab.url || '')
  $('site').textContent = host
  let applicant
  try {
    applicant = await api('GET', '/applicant')
  } catch {
    say('JobPilot is not running. Start the backend (127.0.0.1:8000).')
    for (const b of document.querySelectorAll('button')) b.disabled = true
    return
  }
  const sync = () => {
    const on = !isDisabled(host, applicant.disabled_sites)
    $('siteOn').checked = on
    $('fill').disabled = !on
  }
  sync()
  $('siteOn').onchange = async () => {
    const base = host.split('.').slice(-2).join('.')
    const rest = applicant.disabled_sites.filter((d) => !(host === d || host.endsWith('.' + d)))
    applicant = await api('PUT', '/applicant', {
      ...applicant, disabled_sites: $('siteOn').checked ? rest : [...rest, base],
    })
    sync()
  }
  try {
    const { draft } = await chrome.storage.local.get('draft')
    if (draft === false) $('draft').checked = false
  } catch { /* storage unavailable */ }
  $('draft').onchange = () => chrome.storage.local.set({ draft: $('draft').checked })
  const run = (fn) => async () => {
    try { await fn() } catch (e) { say('Error: ' + (e?.message || e)) }
  }
  $('fill').onclick = run(fill)
  $('save').onclick = run(save)
  $('applied').onclick = run(markApplied)
}

init()
