// R-015 前端静态断言(等效单元测试;node scripts/r015_check.mjs 于 frontend/ 运行)
// AC-1→用例: test_app_bare_branch / test_bare_condition_exact /
//             test_settings_dev_hint / test_dist_contains_branch / test_r014_invariants
import { readFileSync, existsSync, readdirSync } from 'node:fs'

const read = (p) => readFileSync(new URL(p, import.meta.url), 'utf-8')
let pass = 0, fail = 0
const t = (name, cond, why = '') => {
  if (cond) { console.log('PASS', name); pass++ }
  else { console.error('FAIL', name, why); fail++ }
}

const app = read('../src/App.vue')
t('test_app_bare_branch',
  app.includes('const bare = computed(') &&
  /<router-view\s+v-if="bare"\s*\/>/.test(app) &&
  app.includes('<n-message-provider v-else>'))

t('test_bare_condition_exact',
  app.includes("route.path === '/m'"))

const settings = read('../src/pages/SettingsView.vue')
t('test_settings_dev_hint',
  settings.includes('5173') && settings.includes('手机无法直连'))

const distDir = new URL('../dist/assets/', import.meta.url)
if (existsSync(distDir)) {
  const js = readdirSync(distDir).filter(f => f.endsWith('.js'))
    .map(f => readFileSync(new URL(`../dist/assets/${f}`, import.meta.url), 'utf-8'))
    .join('')
  const bareCmp = js.includes('"/m"===') || js.includes('==="/m"')
  t('test_dist_contains_branch',
    bareCmp && (js.includes('mv-bar') || js.includes('MobileView')))
} else {
  t('test_dist_contains_branch', false, 'dist 未构建(先 npm run build)')
}

// R-014 不变量:壳零改动仅加分支,移动契约文件仍完整
const mv = read('../src/pages/MobileView.vue')
t('test_r014_invariants',
  mv.includes('useChatStore') && mv.includes('getUserMedia') &&
  read('../src/router/index.js').includes("path: '/m'"))

console.log(`\nr015_check: PASS=${pass} FAIL=${fail}`)
process.exit(fail ? 1 : 0)
