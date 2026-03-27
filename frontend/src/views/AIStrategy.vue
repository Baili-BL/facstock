<template>
  <div>
    <nav class="navbar">
      <div class="nav-back" @click="$router.push('/strategy')">
        <svg class="icon" viewBox="0 0 24 24"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
      </div>
      <div class="nav-title">
        <svg class="icon" style="fill:var(--apple-purple);margin-right:6px"><use href="#icon-ai"/></svg>
        AI 智能策略
      </div>
    </nav>

    <div class="container">
      <!-- AI 配置状态 -->
      <div class="config-card" :class="{ configured: aiConfigured }">
        <div class="config-icon">
          <svg class="icon icon-lg"><use href="#icon-ai"/></svg>
        </div>
        <div class="config-info">
          <div class="config-title">{{ aiConfigured ? 'AI 已配置' : 'AI 未配置' }}</div>
          <div class="config-desc">{{ aiConfigured ? '腾讯混元大模型已可用' : '请先配置 API Key 以启用 AI 分析' }}</div>
        </div>
        <button v-if="!aiConfigured" class="config-btn" @click="showConfigModal = true">
          配置
        </button>
      </div>

      <!-- 分析按钮 -->
      <div class="action-section">
        <button class="analyze-btn" @click="startAnalyze" :disabled="!aiConfigured || analyzing">
          <svg class="icon" :class="{ spinning: analyzing }"><use href="#icon-ai"/></svg>
          {{ analyzing ? '分析中...' : '开始 AI 分析' }}
        </button>
        <p class="action-tip" v-if="!aiConfigured">配置 API Key 后可使用 AI 分析功能</p>
        <p class="action-tip" v-else-if="analyzing">正在分析市场数据，请稍候...</p>
        <p class="action-tip" v-else>基于最新扫描结果，AI 将深度解读市场机会</p>
      </div>

      <!-- 分析结果 -->
      <div v-if="analysisResult" class="analysis-result">
        <div class="result-header">
          <span class="result-title">AI 解读报告</span>
          <span class="result-model">{{ analysisResult.model || '混元大模型' }}</span>
        </div>
        <div class="result-content" v-html="formatAnalysis(analysisResult.analysis)"></div>
        <button class="save-btn" @click="saveReport">保存报告</button>
      </div>

      <!-- 历史报告 -->
      <div class="section">
        <div class="section-header">
          <svg class="icon"><use href="#icon-history"/></svg>
          <span class="section-title">历史报告</span>
        </div>

        <div v-if="reportsLoading" class="loading">
          <div class="spinner"></div>
        </div>
        <div v-else-if="reportsError" class="error">{{ reportsError }}</div>
        <div v-else-if="reports.length === 0" class="empty">暂无历史报告</div>
        <div v-else class="report-list">
          <div v-for="r in reports" :key="r.id" class="report-item" @click="viewReport(r)">
            <div class="report-info">
              <div class="report-date">
                <svg class="icon icon-sm"><use href="#icon-calendar"/></svg>
                {{ formatDate(r.created_at) }}
              </div>
              <div class="report-meta">
                <span v-if="r.model" class="report-model-tag">{{ r.model }}</span>
                <span v-if="r.scan_data_summary" class="report-summary">{{ r.scan_data_summary }}</span>
              </div>
            </div>
            <svg class="icon icon-chevron"><use href="#icon-chevron-right"/></svg>
          </div>
        </div>
      </div>
    </div>

    <!-- 配置弹窗 -->
    <div class="modal-overlay" :class="{ active: showConfigModal }" @click.self="showConfigModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <span class="modal-title">配置 AI</span>
          <button class="modal-close" @click="showConfigModal = false">✕</button>
        </div>
        <div class="modal-body">
          <div class="input-group">
            <label>腾讯云 API Key</label>
            <input type="password" v-model="apiKey" placeholder="请输入 API Key" />
          </div>
          <div class="input-tip">
            请在腾讯云控制台获取 API Key：
            <br />https://console.cloud.tencent.com/cam/capi
          </div>
          <div v-if="configError" class="config-error">{{ configError }}</div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="showConfigModal = false">取消</button>
          <button class="btn-primary" @click="saveConfig" :disabled="saving">保存</button>
        </div>
      </div>
    </div>

    <!-- 报告详情弹窗 -->
    <div class="modal-overlay" :class="{ active: showReportModal }" @click.self="showReportModal = false">
      <div class="modal-content report-modal">
        <div class="modal-header">
          <span class="modal-title">AI 解读报告</span>
          <button class="modal-close" @click="showReportModal = false">✕</button>
        </div>
        <div class="modal-body report-body" v-html="formatAnalysis(currentReport?.analysis || '')"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { scan } from '@/api/strategy.js'

const aiConfigured = ref(false)
const analyzing = ref(false)
const analysisResult = ref(null)
const showConfigModal = ref(false)
const showReportModal = ref(false)
const apiKey = ref('')
const configError = ref('')
const saving = ref(false)

const reports = ref([])
const reportsLoading = ref(true)
const reportsError = ref('')
const currentReport = ref(null)

// 检查 AI 配置状态
async function checkAiConfig() {
  try {
    const res = await fetch('/api/ai/config')
    const json = await res.json()
    if (json.success) {
      aiConfigured.value = json.configured
    }
  } catch (e) {
    console.error('检查 AI 配置失败:', e)
  }
}

// 保存配置
async function saveConfig() {
  if (!apiKey.value.trim()) {
    configError.value = '请输入 API Key'
    return
  }
  saving.value = true
  configError.value = ''
  try {
    const res = await fetch('/api/ai/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: apiKey.value.trim() }),
    })
    const json = await res.json()
    if (json.success) {
      aiConfigured.value = json.configured
      showConfigModal.value = false
      if (!json.configured) {
        configError.value = 'API Key 无效，请检查'
      }
    } else {
      configError.value = json.error || '配置失败'
    }
  } catch (e) {
    configError.value = '配置失败，请重试'
  } finally {
    saving.value = false
  }
}

// 开始分析
async function startAnalyze() {
  if (!aiConfigured.value || analyzing.value) return

  analyzing.value = true
  analysisResult.value = null
  try {
    const res = await fetch('/api/ai/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    })
    const json = await res.json()
    if (json.success) {
      analysisResult.value = json
      await loadReports()
    } else {
      alert(json.error || '分析失败')
    }
  } catch (e) {
    alert('分析失败: ' + e.message)
  } finally {
    analyzing.value = false
  }
}

// 加载报告列表
async function loadReports() {
  reportsLoading.value = true
  reportsError.value = ''
  try {
    const res = await fetch('/api/ai/reports')
    const json = await res.json()
    if (json.success) {
      reports.value = json.data || []
    } else {
      reportsError.value = json.error || '加载失败'
    }
  } catch (e) {
    reportsError.value = '网络错误'
  } finally {
    reportsLoading.value = false
  }
}

// 查看报告
async function viewReport(report) {
  currentReport.value = report
  showReportModal.value = true
}

// 保存报告（已自动保存，这里做个标记）
function saveReport() {
  alert('报告已自动保存到历史记录')
}

// 格式化日期
function formatDate(dateStr) {
  if (!dateStr) return '--'
  const d = new Date(dateStr)
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

// 格式化分析内容
function formatAnalysis(text) {
  if (!text) return ''
  return text
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^/, '<p>')
    .replace(/$/, '</p>')
}

onMounted(() => {
  checkAiConfig()
  loadReports()
})
</script>

<style scoped>
.navbar {
  position: sticky; top: 0; z-index: 100;
  background: rgba(255,255,255,0.78);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  padding: 10px 16px;
  padding-top: calc(10px + env(safe-area-inset-top));
  display: flex; align-items: center; gap: 12px;
}
.nav-back {
  width: 30px; height: 30px; border-radius: 8px;
  background: var(--apple-gray6); cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.nav-back .icon { fill: var(--apple-text2); }
.nav-title {
  font-size: 17px; font-weight: 600; flex: 1;
  display: flex; align-items: center; justify-content: center;
  padding-right: 30px;
}

.container { padding: 16px; }

/* 配置卡片 */
.config-card {
  background: var(--apple-card);
  border-radius: 18px; padding: 18px;
  margin-bottom: 16px;
  display: flex; align-items: center; gap: 14px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.05);
  border: 2px solid var(--apple-gray5);
}
.config-card.configured { border-color: var(--apple-green); }
.config-icon {
  width: 48px; height: 48px; border-radius: 14px;
  background: var(--apple-gray6);
  display: flex; align-items: center; justify-content: center;
}
.config-card.configured .config-icon { background: #E8F5E9; }
.config-icon .icon { fill: var(--apple-purple); }
.config-card.configured .config-icon .icon { fill: var(--apple-green); }
.config-info { flex: 1; }
.config-title { font-size: 16px; font-weight: 600; }
.config-desc { font-size: 13px; color: var(--apple-text3); margin-top: 4px; }
.config-btn {
  background: var(--apple-blue); color: #fff;
  border: none; padding: 8px 16px; border-radius: 20px;
  font-size: 14px; font-weight: 600; cursor: pointer;
}

/* 操作区域 */
.action-section { margin-bottom: 20px; text-align: center; }
.analyze-btn {
  width: 100%; background: linear-gradient(135deg, #AF52DE, #FF2D55);
  color: #fff; border: none; padding: 16px; border-radius: 16px;
  font-size: 17px; font-weight: 600; cursor: pointer;
  display: flex; align-items: center; justify-content: center; gap: 8px;
  box-shadow: 0 4px 16px rgba(175, 82, 222, 0.3);
}
.analyze-btn:disabled { opacity: 0.5; }
.analyze-btn .icon { fill: #fff; }
.action-tip { font-size: 13px; color: var(--apple-text3); margin-top: 10px; }

/* 分析结果 */
.analysis-result {
  background: var(--apple-card);
  border-radius: 18px; padding: 18px;
  margin-bottom: 20px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.05);
}
.result-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 14px; padding-bottom: 12px;
  border-bottom: 0.5px solid var(--apple-gray5);
}
.result-title { font-size: 16px; font-weight: 600; }
.result-model { font-size: 12px; color: var(--apple-purple); background: #F3E5F5; padding: 4px 10px; border-radius: 12px; font-weight: 500; }
.result-content {
  font-size: 14px; line-height: 1.7;
  color: var(--apple-text2);
  margin-bottom: 16px;
}
.save-btn {
  background: var(--apple-gray6); color: var(--apple-text2);
  border: none; padding: 10px 20px; border-radius: 20px;
  font-size: 14px; font-weight: 500; cursor: pointer;
}

/* 分区 */
.section { margin-bottom: 20px; }
.section-header {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 12px;
}
.section-header .icon { fill: var(--apple-blue); }
.section-title { font-size: 16px; font-weight: 600; }

/* 报告列表 */
.report-list { background: var(--apple-card); border-radius: 16px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.05); }
.report-item {
  padding: 14px 16px;
  border-bottom: 0.5px solid var(--apple-gray5);
  display: flex; justify-content: space-between; align-items: center;
  cursor: pointer;
  transition: background 0.15s;
}
.report-item:last-child { border-bottom: none; }
.report-item:active { background: var(--apple-gray6); }
.report-info { flex: 1; }
.report-date { font-size: 15px; font-weight: 600; display: flex; align-items: center; gap: 6px; }
.report-date .icon { fill: var(--apple-blue); }
.report-meta { display: flex; gap: 8px; margin-top: 6px; flex-wrap: wrap; }
.report-model-tag { font-size: 11px; color: var(--apple-purple); background: #F3E5F5; padding: 2px 8px; border-radius: 8px; font-weight: 500; }
.report-summary { font-size: 12px; color: var(--apple-text3); }
.icon-chevron { fill: var(--apple-gray3); }

/* 弹窗 */
.modal-overlay { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.4); z-index: 200; align-items: flex-end; justify-content: center; }
.modal-overlay.active { display: flex; }
.modal-content { background: var(--apple-bg); border-radius: 20px 20px 0 0; width: 100%; max-width: 500px; max-height: 80vh; display: flex; flex-direction: column; }
.modal-header { padding: 16px 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 0.5px solid var(--apple-gray5); }
.modal-title { font-size: 17px; font-weight: 600; }
.modal-close { background: var(--apple-gray6); border: none; width: 28px; height: 28px; border-radius: 50%; font-size: 16px; cursor: pointer; color: var(--apple-text2); }
.modal-body { padding: 20px; flex: 1; overflow-y: auto; }
.modal-footer { padding: 16px 20px; display: flex; gap: 12px; border-top: 0.5px solid var(--apple-gray5); }

/* 表单 */
.input-group { margin-bottom: 12px; }
.input-group label { display: block; font-size: 14px; font-weight: 500; margin-bottom: 8px; color: var(--apple-text2); }
.input-group input { width: 100%; padding: 12px 14px; border: 1px solid var(--apple-gray4); border-radius: 12px; font-size: 15px; background: var(--apple-card); }
.input-tip { font-size: 12px; color: var(--apple-text3); line-height: 1.5; }
.config-error { color: var(--apple-red); font-size: 13px; margin-top: 8px; }

/* 按钮 */
.btn-primary { flex: 1; background: var(--apple-blue); color: #fff; border: none; padding: 12px; border-radius: 12px; font-size: 16px; font-weight: 600; cursor: pointer; }
.btn-secondary { flex: 1; background: var(--apple-gray6); color: var(--apple-text2); border: none; padding: 12px; border-radius: 12px; font-size: 16px; font-weight: 600; cursor: pointer; }
.btn-primary:disabled, .btn-secondary:disabled { opacity: 0.5; }

/* 报告详情弹窗 */
.report-modal { max-height: 90vh; }
.report-body { font-size: 14px; line-height: 1.8; color: var(--apple-text2); }

.loading { text-align: center; padding: 40px; color: var(--apple-gray); }
.spinner { width: 28px; height: 28px; border: 2.5px solid var(--apple-gray5); border-top-color: var(--apple-blue); border-radius: 50%; animation: spin 0.7s linear infinite; margin: 0 auto; }
@keyframes spin { to { transform: rotate(360deg); } }
.spinning { animation: spin 0.7s linear infinite; }
.error { text-align: center; padding: 40px; color: var(--apple-red); }
.empty { text-align: center; padding: 40px; color: var(--apple-gray); font-size: 14px; }
</style>
