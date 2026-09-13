// R-014 前端静态断言(等效单元测试;node scripts/r014_check.mjs 于 frontend/ 运行)
// AC→用例: test_baseurl_same_origin / test_router_mobile_route /
//          test_settings_pair_qr / test_mobile_view_contract / test_dist_built
import { readFileSync, existsSync } from 'node:fs'

const read = (p) => readFileSync(new URL(p, import.meta.url), 'utf-8')
let pass = 0, fail = 0
const t = (name, cond, why = '') => {
  if (cond) { console.log('PASS', name); pass++ }
  else { console.error('FAIL', name, why); fail++ }
}

const req = read('../src/utils/request.js')
t('test_baseurl_same_origin',
  req.includes("|| '/api/v1'") && !req.includes("'http://localhost:8000/api/v1'"))

const store = read('../src/stores/chat.js')
t('test_store_same_origin',
  store.includes("|| '/api/v1'") || !store.includes('http://localhost:8000'))

const router = read('../src/router/index.js')
t('test_router_mobile_route',
  router.includes("path: '/m'") &&
  /import MobileView from '\.\.?\/'/.test(router))

const settings = read('../src/pages/SettingsView.vue')
t('test_settings_pair_qr',
  settings.includes("request.get('/pair/info')") &&
  settings.includes('QrcodeVue') &&
  /:value="pair\.url"/.test(settings))

const mv = read('../src/pages/MobileView.vue')
t('test_mobile_view_contract',
  mv.includes('useChatStore') &&
  mv.includes('uploadChatImage') && mv.includes('uploadVideoFrames') &&
  mv.includes('transcribeSpeech') &&
  mv.includes('image/*') && mv.includes('video/*') &&
  mv.includes('audio/*') && mv.includes('getUserMedia') &&
  mv.includes('mediaDevices'))

t('test_r012_defense_used',
  mv.includes('r?.data?.data?.image_id') && mv.includes('r?.data?.frame_ids'))

const distIdx = existsSync(new URL('../dist/index.html', import.meta.url))
t('test_dist_built', distIdx)

const kb = read('../src/pages/KnowledgeView.vue')
t('test_kb_same_origin', !kb.includes('http://localhost:8000'))

console.log(`\nr014_check: PASS=${pass} FAIL=${fail}`)
process.exit(fail ? 1 : 0)
