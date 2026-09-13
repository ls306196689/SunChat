// R-017 前端静态断言(先 npm run build 再运行;签名唯一性见负对照注)
// AC-3(前端面)→test_pose_button_and_api_dist
import { readFileSync, existsSync, readdirSync } from 'node:fs'

const read = (p) => readFileSync(new URL(p, import.meta.url), 'utf-8')
let pass = 0, fail = 0
const t = (name, cond, why = '') => {
  if (cond) { console.log('PASS', name); pass++ }
  else { console.error('FAIL', name, why); fail++ }
}

const req = read('../src/utils/request.js')
t('test_analyzeVideoPose_ct_undefined_timeout',
  /export function analyzeVideoPose[\s\S]*?\/chat\/video\/pose[\s\S]*?'Content-Type': undefined[\s\S]*?timeout: 180000/.test(req),
  'analyzeVideoPose 需 CT undefined + 180s 超时')

const mv = read('../src/pages/MobileView.vue')
t('test_mobileview_pose_entry',
  mv.includes('analyzeVideoPose') && mv.includes('pose_guide_seen') &&
  mv.includes('onPickPose') && mv.includes('跑步姿态分析') &&
  mv.includes('diag') && mv.includes('pose.pick'),
  'MobileView 需 按钮/引导/localStorage/pick/start/diag 埋点')

const cv = read('../src/pages/ChatView.vue')
t('test_chatview_pose_entry',
  cv.includes('analyzeVideoPose') && cv.includes('🏃 跑步分析') &&
  cv.includes('maybePoseGuideThenPick') && cv.includes('showPoseGuide') &&
  cv.includes('fetchMessages'),
  'ChatView 需 按钮/引导modal/成功后刷新消息')
t('test_guide_covers_both_scenes',
  mv.includes('跑步机') && mv.includes('侧面') && cv.includes('跑步机') && cv.includes('侧面'),
  '引导文案须含 路跑+跑步机 两支 (D-001)')

const distDir = new URL('../dist/assets/', import.meta.url)
if (existsSync(distDir)) {
  // 签名唯一:'/chat/video/pose' 为 R-017 新端点串,R-016 及旧产物必无(负对照:
  // git stash 旧 src 重 build → 本断言 FAIL)。朴素 includes,无正则嵌套/OPT-012。
  const js = readdirSync(distDir).filter(f => f.endsWith('.js'))
    .map(f => readFileSync(new URL(`../dist/assets/${f}`, import.meta.url), 'utf-8'))
    .join('')
  t('test_dist_pose_endpoint_signature',
    js.includes('/chat/video/pose') && js.includes('pose_guide_seen'),
    'dist 含 /chat/video/pose 与 pose_guide_seen(先 npm run build)')
  const distIdx = read('../dist/index.html')
  t('test_dist_html_fresh', distIdx.includes("ver: '1.1.0'"), 'dist HTML 版本注入完好(R-016 联动)')
} else {
  t('test_dist_pose_endpoint_signature', false, 'dist 未构建')
  t('test_dist_html_fresh', false, 'dist 未构建')
}

console.log(`\nr017_check: PASS=${pass} FAIL=${fail}`)
process.exit(fail ? 1 : 0)
