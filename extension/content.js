// Injected into each frame on demand by popup.js. Reads form fields and fills them.
// It never clicks submit buttons and never overwrites a field the user already filled.
;(() => {
  if (window.__jpAssist) return

  const COLORS = { high: '#16a34a', medium: '#ca8a04', low: '#dc2626' }
  const SKIP_TYPES = new Set(['hidden', 'submit', 'button', 'reset', 'image', 'password', 'search'])
  const CV_WORDS = /resume|résumé|\bcv\b|curriculum/i
  let nextId = 0

  const clean = (t) => (t || '').replace(/\s+/g, ' ').replace(/[*:]+\s*$/, '').trim()

  function visible(el) {
    const r = el.getBoundingClientRect()
    return (r.width > 0 && r.height > 0) || el.type === 'file' || el.type === 'radio' || el.type === 'checkbox'
  }

  function textOfIds(ids) {
    return ids.split(/\s+/).map((id) => document.getElementById(id)?.innerText || '').join(' ')
  }

  function labelFor(el) {
    if (el.getAttribute('aria-labelledby')) {
      const t = clean(textOfIds(el.getAttribute('aria-labelledby')))
      if (t) return t
    }
    if (el.getAttribute('aria-label')) return clean(el.getAttribute('aria-label'))
    if (el.id) {
      const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`)
      if (l) return clean(l.innerText)
    }
    const wrap = el.closest('label')
    if (wrap) return clean(wrap.innerText)
    // Workday and many ATS forms: the label sits in the field's container
    const box = el.closest('[data-automation-id^="formField"], .field, .form-group, .application-question, li, div')
    const l = box?.querySelector('label, legend, [data-automation-id="formLabel"]')
    if (l && l.innerText) return clean(l.innerText)
    return clean(el.getAttribute('placeholder') || el.name || '')
  }

  function groupLabel(el) {
    const fs = el.closest('fieldset, [role="radiogroup"], [role="group"]')
    const l = fs?.querySelector('legend, label, [data-automation-id="formLabel"]')
    if (fs?.getAttribute('aria-labelledby')) return clean(textOfIds(fs.getAttribute('aria-labelledby')))
    return clean(l?.innerText || el.name)
  }

  function tag(el) {
    if (!el.dataset.jpId) el.dataset.jpId = String(nextId++)
    return el.dataset.jpId
  }

  function collect() {
    const out = []
    const radios = new Map()
    for (const el of document.querySelectorAll('input, textarea, select')) {
      if (el.disabled || SKIP_TYPES.has(el.type) || !visible(el)) continue
      if (el.type === 'radio') {
        const key = el.name || tag(el)
        if (!radios.has(key)) radios.set(key, [])
        radios.get(key).push(el)
        continue
      }
      const kind = el.tagName === 'TEXTAREA' ? 'textarea'
        : el.tagName === 'SELECT' ? 'select'
        : el.type === 'file' ? 'file'
        : el.type === 'checkbox' ? 'checkbox' : 'text'
      const label = labelFor(el)
      if (!label) continue
      const options = kind === 'select' ? [...el.options].map((o) => clean(o.text)).filter(Boolean) : []
      out.push({ id: tag(el), label, kind, options })
    }
    for (const group of radios.values()) {
      const first = group[0]
      out.push({
        id: tag(first), label: groupLabel(first), kind: 'radio',
        options: group.map((r) => labelFor(r)),
      })
    }
    // Workday-style dropdowns: a button that opens a listbox
    for (const el of document.querySelectorAll('button[aria-haspopup="listbox"]')) {
      if (!visible(el)) continue
      const label = labelFor(el)
      if (label) out.push({ id: tag(el), label, kind: 'select', options: [] })
    }
    return out
  }

  function setNative(el, value) {
    const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype
      : el.tagName === 'SELECT' ? HTMLSelectElement.prototype : HTMLInputElement.prototype
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, value) // React-controlled inputs
    el.dispatchEvent(new Event('input', { bubbles: true }))
    el.dispatchEvent(new Event('change', { bubbles: true }))
    el.dispatchEvent(new Event('blur', { bubbles: true }))
  }

  function mark(el, confidence, source) {
    el.style.outline = `2px solid ${COLORS[confidence]}`
    el.style.outlineOffset = '1px'
    el.dataset.jpSource = source
  }

  const wait = (ms) => new Promise((r) => setTimeout(r, ms))

  async function pickListbox(button, value) {
    button.click()
    for (let i = 0; i < 20; i++) {
      await wait(100)
      const opts = [...document.querySelectorAll('[role="option"]')]
      const want = value.toLowerCase()
      const hit = opts.find((o) => clean(o.innerText).toLowerCase() === want)
        || opts.find((o) => clean(o.innerText).toLowerCase().includes(want))
      if (hit) { hit.click(); return true }
    }
    document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    return false
  }

  function fileFrom(cv) {
    const bin = atob(cv.data)
    const bytes = new Uint8Array(bin.length)
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
    return new File([bytes], cv.name, { type: 'application/pdf' })
  }

  async function apply(results, cv) {
    const counts = { high: 0, medium: 0, low: 0 }
    for (const r of results) {
      const el = document.querySelector(`[data-jp-id="${r.id}"]`)
      if (!el) continue
      const label = labelFor(el)
      if (el.type === 'file') {
        if (cv && CV_WORDS.test(label) && !/cover/i.test(label) && !el.files?.length) {
          const dt = new DataTransfer()
          dt.items.add(fileFrom(cv))
          el.files = dt.files
          el.dispatchEvent(new Event('change', { bubbles: true }))
          mark(el, 'high', 'cv')
          counts.high++
        }
        continue
      }
      if (r.value == null) { mark(el, 'low', 'none'); counts.low++; continue }
      if (el.type === 'radio') {
        const group = el.name ? document.querySelectorAll(`input[type="radio"][name="${CSS.escape(el.name)}"]`) : [el]
        if ([...group].some((x) => x.checked)) continue
        const hit = [...group].find((x) => labelFor(x) === r.value)
        if (hit) { hit.click(); mark(hit, r.confidence, r.source); counts[r.confidence]++ }
        continue
      }
      if (el.type === 'checkbox') {
        if (!el.checked && /^(yes|true|agree|i agree)$/i.test(r.value)) el.click()
        mark(el, r.confidence, r.source)
        counts[r.confidence]++
        continue
      }
      if (el.tagName === 'BUTTON') {
        if (await pickListbox(el, r.value)) { mark(el, r.confidence, r.source); counts[r.confidence]++ }
        else { mark(el, 'low', 'none'); counts.low++ }
        continue
      }
      if (el.tagName === 'SELECT') {
        if (el.selectedIndex > 0) continue
        const opt = [...el.options].find((o) => clean(o.text) === r.value)
        if (!opt) { mark(el, 'low', 'none'); counts.low++; continue }
        setNative(el, opt.value)
      } else {
        if (el.value.trim()) continue
        setNative(el, r.value)
      }
      mark(el, r.confidence, r.source)
      counts[r.confidence]++
    }
    return counts
  }

  // Answers worth remembering: every labelled, filled field except personal details
  // (those live in the applicant profile) and files.
  function harvest() {
    const out = []
    const seen = new Set()
    for (const el of document.querySelectorAll('input, textarea, select')) {
      if (el.disabled || SKIP_TYPES.has(el.type) || el.type === 'file') continue
      if (el.dataset.jpSource === 'profile') continue
      let question, answer
      if (el.type === 'radio') {
        if (!el.checked) continue
        question = groupLabel(el); answer = labelFor(el)
      } else if (el.type === 'checkbox') {
        continue
      } else if (el.tagName === 'SELECT') {
        if (el.selectedIndex <= 0) continue
        question = labelFor(el); answer = clean(el.options[el.selectedIndex].text)
      } else {
        question = labelFor(el); answer = el.value.trim()
      }
      if (!question || !answer || seen.has(question)) continue
      seen.add(question)
      out.push({ question, answer })
    }
    return out
  }

  window.__jpAssist = { collect, apply, harvest }
})()
