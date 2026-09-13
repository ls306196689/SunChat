// R-016: 手机端交互诊断通道(默认开启,可信内网边界)。
// drop_console 致生产无现场 → 阶段事件环形缓冲 + 批量回传 /api/v1/diag/client。
// 原则:diag 自身失败绝不影响业务,也不递归诊断(静默)。
const API = import.meta.env.VITE_API_URL || '/api/v1'
const BUFFER_MAX = 200
const BATCH_MAX = 50
const FLUSH_MIN_MS = 2000
const BACKLOG_KEY = 'sunchat_diag_backlog'

let page = ''
let buf = []
let seq = 0
let lastFlush = 0
let timer = null
let booting = false
let initialized = false

function now() { return Date.now() }

function enqueue(ev) {
  buf.push(ev)
  if (buf.length > BUFFER_MAX) buf.splice(0, buf.length - BUFFER_MAX)
}

// 错误序列化:杜绝 JSON.stringify(Error) 得 "{}"(message/stack 不可枚举)。
export function serializeErr(err) {
  if (err == null) return { msg: 'null' }
  if (typeof err === 'string') return { msg: err }
  const out = { msg: err.message || String(err), name: err.name || 'Error' }
  if (err.stack) out.stack = String(err.stack).slice(0, 300)
  if (err.response) {
    out.status = err.response.status
    out.rdata = safeTrunc(err.response.data)
  }
  if (err.code) out.code = err.code
  // 补充自有可枚举字段(截断)
  for (const k of ['reason', 'config', 'line', 'column', 'error']) {
    if (err[k] != null && !(k in out)) out[k] = safeTrunc(err[k])
  }
  return out
}

function safeTrunc(v) {
  try {
    const s = typeof v === 'string' ? v : JSON.stringify(v)
    return s && s.length > 400 ? s.slice(0, 400) : s
  } catch { return String(v).slice(0, 400) }
}

function post(body, keepalive) {
  // 裸 fetch:避开业务 request 拦截器,静默失败(不递归诊断)
  return fetch(`${API}/diag/client`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    keepalive: !!keepalive,
  }).catch(() => { backlog(body); return null })
}

function backlog(body) {
  try {
    const arr = JSON.parse(localStorage.getItem(BACKLOG_KEY) || '[]')
    arr.push(body)
    while (arr.length > 2) arr.shift()  // ≥50×2=100 事件上限
    localStorage.setItem(BACKLOG_KEY, JSON.stringify(arr))
  } catch { /* 存不下就丢 */ }
}

function drainBacklog() {
  try {
    const arr = JSON.parse(localStorage.getItem(BACKLOG_KEY) || '[]')
    if (!arr.length) return []
    localStorage.removeItem(BACKLOG_KEY)
    return arr
  } catch { return [] }
}

async function flush(force = false) {
  const stale = drainBacklog()
  if (!buf.length && !stale.length) return
  if (now() - lastFlush < (force ? 300 : FLUSH_MIN_MS)) { schedule(); return }
  const events = buf.splice(0, BATCH_MAX)
  lastFlush = now()
  await post({ page, events }, false)
  for (const b of stale) post(b, false)          // 补发失败批次
  if (buf.length) schedule()
}

function schedule() {
  if (timer) return
  timer = setTimeout(() => { timer = null; flush() }, 5000)   // 5s 兜底
}

export function diagStep(step, extra, lvl = 'info') {
  if (!initialized) return
  enqueue({ ts: now(), seq: seq++, lvl, step, msg: step, extra })
  if (lvl === 'err') { flush(true); return }
  schedule()
}

export function diagError(step, err) {
  if (!initialized) return
  const s = serializeErr(err)
  enqueue({ ts: now(), seq: seq++, lvl: 'err', step, msg: s.msg, extra: s })
  flush(true)
}

export function newReqId() {
  // 8 位 reqId,贯穿 pick/start/fail,与服务端 http.post 行时间窗对账
  return (crypto.randomUUID ? crypto.randomUUID().replace(/-/g, '').slice(0, 8)
    : Math.random().toString(16).slice(2, 10))
}

export function diagInit(pg) {
  if (initialized) return
  initialized = true
  page = pg
  // 页面进入(一次);离开/隐藏 flush(keepalive 尽力送达)
  diagStep('page.enter', { ua: navigator.userAgent.slice(0, 120), href: location.href })
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') flush(true)
  })
  window.addEventListener('pagehide', () => flush(true))
  flush(true)  // 送达 page.enter
}
