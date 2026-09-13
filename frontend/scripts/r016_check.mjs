// R-016 前端静态断言(等效单元测试;node scripts/r016_check.mjs 于 frontend/ 运行)
// OPT-012:先 npm run build 再断言;签名唯一性=负对照(旧产物含 multipart/form-data 且无 diag/client)
// AC→用例: AC-4→test_no_explicit_multipart_ct / AC-5→test_upload_timeout_20s /
//           FR-2→test_diag_module_contract+test_flush_triggers_present / dist→test_dist_signatures
import { readFileSync, existsSync, readdirSync } from 'node:fs'

const read = (p) => readFileSync(new URL(p, import.meta.url), 'utf-8')
let pass = 0, fail = 0
const t = (name, cond, why = '') => {
  if (cond) { console.log('PASS', name); pass++ }
  else { console.error('FAIL', name, why); fail++ }
}

const req = read('../src/utils/request.js')
t('test_no_explicit_multipart_ct', !req.includes('multipart/form-data'),
  'request.js 仍含显式 multipart CT')
const uploads = req.match(/export function upload\w+[\s\S]*?\n}/g) || []
t('test_all_uploads_ct_undefined', uploads.length === 2 && uploads.every(u => u.includes("'Content-Type': undefined")),
  '两个上传函数均应显式 CT undefined(视频漏网=R-010回归根因)')
t('test_upload_timeout_20s',
  /uploadChatImage[\s\S]*?timeout: 20000/.test(req) &&
  /transcribeSpeech[\s\S]*?timeout: 20000/.test(req) &&
  /uploadVideoFrames[\s\S]*?timeout: 120000/.test(req))

const dg = read('../src/utils/mobileDiag.js')
t('test_diag_module_contract',
  dg.includes('diagInit') && dg.includes('diagStep') && dg.includes('diagError') &&
  dg.includes('/diag/client') && dg.includes('serializeErr') && dg.includes('newReqId'))
t('test_flush_triggers_present',
  dg.includes('visibilitychange') && dg.includes('keepalive') &&
  dg.includes('BACKLOG_KEY') && dg.includes('BUFFER_MAX'))

const mv = read('../src/pages/MobileView.vue')
t('test_mobileview_instrumented',
  mv.includes("diagInit('/m')") &&
  mv.includes('upload.pick') && mv.includes('upload.start') &&
  mv.includes('upload.ok') && mv.includes('diagError') && mv.includes('reqId'))

const idx = read('../index.html')
t('test_inline_canary',
  idx.includes('page.canary') && idx.includes('js.hung') && idx.includes('unhandledrejection') &&
  idx.includes('sendBeacon'))
t('test_diag_beacon_path', dg.includes('sendBeacon'))
t('test_version_single_source',
  dg.includes('__APP_VERSION__') && idx.includes("ver: '%APP_VERSION%'"))

t('test_r014_invariants', mv.includes('useChatStore') && mv.includes('getUserMedia'))

const distDir = new URL('../dist/assets/', import.meta.url)
if (existsSync(distDir)) {
  const js = readdirSync(distDir).filter(f => f.endsWith('.js'))
    .map(f => readFileSync(new URL(`../dist/assets/${f}`, import.meta.url), 'utf-8')).join('')
  // 新行为签名(唯一性:负对照=R-015旧产物无 diag 链)。
  // 注:multipart 字面量在 axios 库内部固有(检测逻辑/工厂辅助),不做全包否定式断言;
  // 业务层无显式 CT 已由 test_no_explicit_multipart_ct(src)覆盖,build 成功=产物=src。
  t('test_dist_signatures',
    js.includes('/diag/client') && js.includes('upload.pick'),
    'dist 应含 diag/client 与 upload.pick 埋点串(先 npm run build)')
  const distIdx = read('../dist/index.html')
  t('test_dist_version_injected',
    distIdx.includes("ver: '1.1.0'") && !distIdx.includes('%APP_VERSION%'),
    'dist index.html 应已注入版本1.1.0(版本占位符零残留)')
} else {
  t('test_dist_signatures', false, 'dist 未构建')
}

console.log(`\nr016_check: PASS=${pass} FAIL=${fail}`)
process.exit(fail ? 1 : 0)
