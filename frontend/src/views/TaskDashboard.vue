<template>
  <div class="task-root">
    <!-- TopAppBar -->
    <header class="task-header">
      <div class="task-header__left">
        <button type="button" class="task-header__icon-btn" aria-label="返回" @click="goBack">
          <span class="mso">arrow_back</span>
        </button>
        <div class="task-header__brand">
          <div class="task-header__avatar">
            <span class="mso">checklist</span>
          </div>
          <div class="task-header__title-group">
            <h1 class="task-header__title">任务中心</h1>
            <span class="task-header__subtitle">Task Management</span>
          </div>
        </div>
      </div>
      <div class="task-header__right">
        <button type="button" class="task-btn task-btn--primary" @click="showCreateModal = true">
          <span class="mso">add</span>
          新建任务
        </button>
      </div>
    </header>

    <!-- Main Content -->
    <main class="task-main">

      <!-- Stats Cards -->
      <div class="task-stats">
        <div class="task-stat-card" :class="{ 'task-stat-card--active': filterStatus === 'in_progress' }" @click="setFilter('in_progress')">
          <div class="task-stat-card__icon task-stat-card__icon--running">
            <span class="mso">play_circle</span>
          </div>
          <div class="task-stat-card__info">
            <span class="task-stat-card__num">{{ summary.in_progress }}</span>
            <span class="task-stat-card__label">进行中</span>
          </div>
        </div>
        <div class="task-stat-card" :class="{ 'task-stat-card--active': filterStatus === 'pending' }" @click="setFilter('pending')">
          <div class="task-stat-card__icon task-stat-card__icon--pending">
            <span class="mso">schedule</span>
          </div>
          <div class="task-stat-card__info">
            <span class="task-stat-card__num">{{ summary.pending }}</span>
            <span class="task-stat-card__label">待开始</span>
          </div>
        </div>
        <div class="task-stat-card" :class="{ 'task-stat-card--active': filterStatus === 'completed' }" @click="setFilter('completed')">
          <div class="task-stat-card__icon task-stat-card__icon--done">
            <span class="mso">check_circle</span>
          </div>
          <div class="task-stat-card__info">
            <span class="task-stat-card__num">{{ summary.completed }}</span>
            <span class="task-stat-card__label">已完成</span>
          </div>
        </div>
        <div class="task-stat-card" :class="{ 'task-stat-card--active': filterStatus === null }" @click="setFilter(null)">
          <div class="task-stat-card__icon task-stat-card__icon--total">
            <span class="mso">list_alt</span>
          </div>
          <div class="task-stat-card__info">
            <span class="task-stat-card__num">{{ summary.total }}</span>
            <span class="task-stat-card__label">全部任务</span>
          </div>
        </div>
      </div>

      <!-- Filter Tabs -->
      <div class="task-filter-tabs">
        <button
          v-for="tab in filterTabs"
          :key="tab.value"
          type="button"
          class="task-filter-tab"
          :class="{ 'task-filter-tab--active': filterStatus === tab.value }"
          @click="setFilter(tab.value)"
        >
          {{ tab.label }}
          <span class="task-filter-tab__count">{{ tab.count }}</span>
        </button>
      </div>

      <!-- Loading State -->
      <div v-if="loading" class="task-loading">
        <div class="task-loading__spinner" />
        <p>加载中...</p>
      </div>

      <!-- Empty State -->
      <div v-else-if="!filteredTasks.length" class="task-empty">
        <span class="mso">inbox</span>
        <p v-if="filterStatus">没有{{ statusLabel }}的任务</p>
        <p v-else>暂无任务，点击右上角"新建任务"创建</p>
        <button type="button" class="task-btn task-btn--outline" @click="showCreateModal = true">
          <span class="mso">add</span>
          创建第一个任务
        </button>
      </div>

      <!-- Task List -->
      <div v-else class="task-list">
        <div
          v-for="task in filteredTasks"
          :key="task.id"
          class="task-card"
          :class="{
            'task-card--in_progress': task.status === 'in_progress',
            'task-card--completed': task.status === 'completed',
            'task-card--pending': task.status === 'pending',
          }"
        >
          <!-- Priority bar -->
          <div class="task-card__priority-bar" :style="{ opacity: Math.max(0.2, task.priority / 10) }" />

          <!-- Card Header -->
          <div class="task-card__header">
            <div class="task-card__status-icon">
              <!-- Running: pulsing dot -->
              <span v-if="task.status === 'in_progress'" class="task-card__status-dot task-card__status-dot--running" />
              <!-- Done: check -->
              <span v-else-if="task.status === 'completed'" class="task-card__status-check">
                <span class="mso">check</span>
              </span>
              <!-- Pending: empty circle -->
              <span v-else class="task-card__status-circle" />
            </div>

            <div class="task-card__info">
              <h3 class="task-card__subject">{{ task.subject }}</h3>
              <div class="task-card__meta">
                <span v-if="task.owner" class="task-card__owner">
                  <span class="mso">person</span>
                  {{ task.owner }}
                </span>
                <span v-if="task.status === 'in_progress'" class="task-card__active-form">
                  <span class="task-card__spinner-dot" />
                  {{ task.active_form || '进行中...' }}
                </span>
                <span class="task-card__time">
                  <span class="mso">schedule</span>
                  {{ formatTime(task.created_at) }}
                </span>
              </div>
            </div>

            <!-- Priority Badge -->
            <div v-if="task.priority > 0" class="task-card__priority-badge" :class="priorityClass(task.priority)">
              P{{ task.priority }}
            </div>

            <!-- Actions -->
            <div class="task-card__actions">
              <!-- Start button (for pending tasks) -->
              <button
                v-if="task.status === 'pending'"
                type="button"
                class="task-card__action-btn task-card__action-btn--start"
                title="开始任务"
                :disabled="busyTaskIds.has(task.id)"
                @click.stop="handleStart(task)"
              >
                <span class="mso">play_arrow</span>
              </button>

              <!-- Complete button (for in_progress tasks) -->
              <button
                v-if="task.status === 'in_progress'"
                type="button"
                class="task-card__action-btn task-card__action-btn--done"
                title="完成任务"
                :disabled="busyTaskIds.has(task.id)"
                @click.stop="handleComplete(task)"
              >
                <span class="mso">check</span>
              </button>

              <!-- Edit button -->
              <button
                type="button"
                class="task-card__action-btn task-card__action-btn--edit"
                title="编辑任务"
                @click.stop="openEditModal(task)"
              >
                <span class="mso">edit</span>
              </button>

              <!-- Delete button -->
              <button
                type="button"
                class="task-card__action-btn task-card__action-btn--delete"
                title="删除任务"
                :disabled="busyTaskIds.has(task.id)"
                @click.stop="handleDelete(task)"
              >
                <span class="mso">delete</span>
              </button>
            </div>
          </div>

          <!-- Description -->
          <div v-if="task.description" class="task-card__description">
            <p>{{ task.description }}</p>
          </div>

          <!-- Dependency info -->
          <div v-if="task.blocked_by && task.blocked_by.length" class="task-card__deps">
            <span class="mso">link</span>
            依赖 {{ task.blocked_by.length }} 个任务
          </div>
        </div>
      </div>
    </main>

    <!-- ── Create/Edit Modal ───────────────────────────────────── -->
    <div v-if="showCreateModal" class="task-modal-overlay" @click.self="closeModal">
      <div class="task-modal">
        <div class="task-modal__header">
          <h3 class="task-modal__title">
            <span class="mso">edit</span>
            {{ editingTask ? '编辑任务' : '新建任务' }}
          </h3>
          <button type="button" class="task-modal__close" @click="closeModal">
            <span class="mso">close</span>
          </button>
        </div>

        <div class="task-modal__body">
          <!-- Subject -->
          <div class="task-form-field">
            <label class="task-form-label">任务标题 *</label>
            <input
              v-model="form.subject"
              type="text"
              class="task-form-input"
              placeholder="例如：优化 AI 分析流式输出的展示效果"
              maxlength="255"
            />
          </div>

          <!-- Description -->
          <div class="task-form-field">
            <label class="task-form-label">详细描述</label>
            <textarea
              v-model="form.description"
              class="task-form-textarea"
              placeholder="描述任务的具体内容、目标、验收标准..."
              rows="4"
            />
          </div>

          <!-- Owner -->
          <div class="task-form-row">
            <div class="task-form-field">
              <label class="task-form-label">负责人</label>
              <input
                v-model="form.owner"
                type="text"
                class="task-form-input"
                placeholder="例如：kevin"
              />
            </div>
            <div class="task-form-field">
              <label class="task-form-label">优先级</label>
              <select v-model="form.priority" class="task-form-select">
                <option :value="0">无 (P0)</option>
                <option :value="1">低 (P1)</option>
                <option :value="2">中 (P2)</option>
                <option :value="3">高 (P3)</option>
                <option :value="5">紧急 (P5)</option>
                <option :value="8">最高 (P8)</option>
              </select>
            </div>
          </div>

          <!-- Active Form -->
          <div v-if="form.status === 'in_progress' || editingTask?.status === 'in_progress'" class="task-form-field">
            <label class="task-form-label">进行中动画文字</label>
            <input
              v-model="form.active_form"
              type="text"
              class="task-form-input"
              placeholder="例如：正在优化流式输出..."
            />
          </div>

          <!-- Status (edit only) -->
          <div v-if="editingTask" class="task-form-field">
            <label class="task-form-label">状态</label>
            <select v-model="form.status" class="task-form-select">
              <option value="pending">待开始</option>
              <option value="in_progress">进行中</option>
              <option value="completed">已完成</option>
            </select>
          </div>
        </div>

        <div class="task-modal__footer">
          <button type="button" class="task-btn task-btn--outline" @click="closeModal">
            取消
          </button>
          <button
            type="button"
            class="task-btn task-btn--primary"
            :disabled="!form.subject.trim() || submitting"
            @click="handleSubmit"
          >
            <span v-if="submitting" class="task-btn__spinner" />
            {{ submitting ? '保存中...' : (editingTask ? '保存修改' : '创建任务') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Confirm Delete Dialog -->
    <div v-if="confirmDeleteTask" class="task-modal-overlay" @click.self="confirmDeleteTask = null">
      <div class="task-modal task-modal--sm">
        <div class="task-modal__header">
          <h3 class="task-modal__title">
            <span class="mso">warning</span>
            确认删除
          </h3>
          <button type="button" class="task-modal__close" @click="confirmDeleteTask = null">
            <span class="mso">close</span>
          </button>
        </div>
        <div class="task-modal__body">
          <p>确定要删除任务 <strong>{{ confirmDeleteTask.subject }}</strong> 吗？</p>
          <p class="task-modal__hint">此操作可在创建新任务时撤销。</p>
        </div>
        <div class="task-modal__footer">
          <button type="button" class="task-btn task-btn--outline" @click="confirmDeleteTask = null">
            取消
          </button>
          <button type="button" class="task-btn task-btn--danger" :disabled="submitting" @click="handleConfirmDelete">
            <span v-if="submitting" class="task-btn__spinner" />
            {{ submitting ? '删除中...' : '确认删除' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  fetchTasks,
  createTask,
  updateTask,
  deleteTask,
  fetchTaskSummary,
  startTask,
  completeTask,
} from '@/api/tasks.js'

const router = useRouter()

// ─── State ───────────────────────────────────────────────────────────────
const tasks = ref([])
const summary = ref({ total: 0, pending: 0, in_progress: 0, completed: 0 })
const loading = ref(false)
const filterStatus = ref(null)  // null = all, 'pending' | 'in_progress' | 'completed'
const busyTaskIds = ref(new Set())

// Modal state
const showCreateModal = ref(false)
const editingTask = ref(null)
const submitting = ref(false)
const confirmDeleteTask = ref(null)

// Form state
const form = ref({
  subject: '',
  description: '',
  owner: '',
  priority: 0,
  active_form: '',
  status: 'pending',
})

// ─── Computed ───────────────────────────────────────────────────────────
const filterTabs = computed(() => [
  { label: '全部', value: null, count: summary.value.total },
  { label: '进行中', value: 'in_progress', count: summary.value.in_progress },
  { label: '待开始', value: 'pending', count: summary.value.pending },
  { label: '已完成', value: 'completed', count: summary.value.completed },
])

const filteredTasks = computed(() => {
  if (!filterStatus.value) return tasks.value
  return tasks.value.filter(t => t.status === filterStatus.value)
})

const statusLabel = computed(() => {
  const m = { pending: '待开始', in_progress: '进行中', completed: '已完成' }
  return m[filterStatus.value] || ''
})

// ─── Lifecycle ─────────────────────────────────────────────────────────
onMounted(() => {
  loadTasks()
  loadSummary()
})

// ─── Data Loading ─────────────────────────────────────────────────────
async function loadTasks() {
  loading.value = true
  try {
    tasks.value = await fetchTasks({ limit: 200 })
  } catch (e) {
    console.warn('[TaskDashboard] 加载任务失败:', e)
  } finally {
    loading.value = false
  }
}

async function loadSummary() {
  try {
    summary.value = await fetchTaskSummary()
  } catch (e) {
    console.warn('[TaskDashboard] 加载摘要失败:', e)
  }
}

// ─── Filter ───────────────────────────────────────────────────────────
function setFilter(status) {
  filterStatus.value = status
}

// ─── Modal ─────────────────────────────────────────────────────────────
function openEditModal(task) {
  editingTask.value = task
  form.value = {
    subject: task.subject,
    description: task.description || '',
    owner: task.owner || '',
    priority: task.priority || 0,
    active_form: task.active_form || '',
    status: task.status,
  }
  showCreateModal.value = true
}

function closeModal() {
  showCreateModal.value = false
  editingTask.value = null
  form.value = {
    subject: '',
    description: '',
    owner: '',
    priority: 0,
    active_form: '',
    status: 'pending',
  }
}

// ─── Actions ─────────────────────────────────────────────────────────
async function handleSubmit() {
  if (!form.value.subject.trim()) return
  submitting.value = true
  try {
    if (editingTask.value) {
      await updateTask(editingTask.value.id, {
        subject: form.value.subject.trim(),
        description: form.value.description.trim(),
        owner: form.value.owner.trim() || null,
        priority: form.value.priority,
        active_form: form.value.active_form.trim() || null,
        status: form.value.status,
      })
    } else {
      await createTask({
        subject: form.value.subject.trim(),
        description: form.value.description.trim(),
        owner: form.value.owner.trim() || null,
        priority: form.value.priority,
        active_form: form.value.active_form.trim() || null,
      })
    }
    closeModal()
    await Promise.all([loadTasks(), loadSummary()])
  } catch (e) {
    console.error('[TaskDashboard] 保存失败:', e)
    alert('保存失败: ' + (e.message || '未知错误'))
  } finally {
    submitting.value = false
  }
}

async function handleStart(task) {
  busyTaskIds.value = new Set([...busyTaskIds.value, task.id])
  try {
    await startTask(task.id, task.subject)
    await Promise.all([loadTasks(), loadSummary()])
  } catch (e) {
    console.error('[TaskDashboard] 开始任务失败:', e)
    alert('开始任务失败: ' + (e.message || '未知错误'))
  } finally {
    busyTaskIds.value = new Set([...busyTaskIds.value].filter(id => id !== task.id))
  }
}

async function handleComplete(task) {
  busyTaskIds.value = new Set([...busyTaskIds.value, task.id])
  try {
    await completeTask(task.id)
    await Promise.all([loadTasks(), loadSummary()])
  } catch (e) {
    console.error('[TaskDashboard] 完成任务失败:', e)
    alert('完成任务失败: ' + (e.message || '未知错误'))
  } finally {
    busyTaskIds.value = new Set([...busyTaskIds.value].filter(id => id !== task.id))
  }
}

async function handleDelete(task) {
  confirmDeleteTask.value = task
}

async function handleConfirmDelete() {
  if (!confirmDeleteTask.value) return
  submitting.value = true
  const task = confirmDeleteTask.value
  confirmDeleteTask.value = null
  try {
    await deleteTask(task.id)
    await Promise.all([loadTasks(), loadSummary()])
  } catch (e) {
    console.error('[TaskDashboard] 删除失败:', e)
    alert('删除失败: ' + (e.message || '未知错误'))
  } finally {
    submitting.value = false
  }
}

// ─── Utilities ───────────────────────────────────────────────────────
function formatTime(isoStr) {
  if (!isoStr) return ''
  try {
    const d = new Date(isoStr)
    const now = new Date()
    const diff = now - d  // ms
    const mins = Math.floor(diff / 60000)
    if (mins < 1) return '刚刚'
    if (mins < 60) return `${mins}分钟前`
    const hours = Math.floor(mins / 60)
    if (hours < 24) return `${hours}小时前`
    const days = Math.floor(hours / 24)
    if (days < 7) return `${days}天前`
    return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
  } catch {
    return isoStr
  }
}

function priorityClass(p) {
  if (p >= 5) return 'task-card__priority-badge--high'
  if (p >= 3) return 'task-card__priority-badge--medium'
  return ''
}

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/')
}
</script>

<style scoped>
/* ── Root ─────────────────────────────────────────────────────────── */
.task-root {
  min-height: 100dvh;
  background: var(--surface);
  color: var(--on-surface);
  font-family: var(--font-body, -apple-system, BlinkMacSystemFont, sans-serif);
  -webkit-font-smoothing: antialiased;
}

/* ── Header ─────────────────────────────────────────────────────── */
.task-header {
  position: sticky;
  top: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  height: 64px;
  padding: 0 24px;
  background: rgba(245, 242, 255, 0.9);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: 0 2px 12px rgba(46, 36, 73, 0.08);
}

.task-header__left { display: flex; align-items: center; gap: 12px; }
.task-header__brand { display: flex; align-items: center; gap: 10px; }
.task-header__avatar {
  width: 40px; height: 40px;
  border-radius: 12px;
  background: var(--primary, #3b1f8c);
  display: flex; align-items: center; justify-content: center;
  color: white; font-size: 20px;
}
.task-header__title-group { display: flex; flex-direction: column; gap: 1px; }
.task-header__title {
  font-family: var(--font-headline, 'Manrope', sans-serif);
  font-size: 1.05rem; font-weight: 800;
  color: var(--on-surface, #1e1633);
  letter-spacing: -0.02em; line-height: 1.2; margin: 0;
}
.task-header__subtitle {
  font-size: 10px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.06em; color: var(--on-surface-variant, #464455);
}
.task-header__right { display: flex; align-items: center; gap: 8px; }
.task-header__icon-btn {
  width: 40px; height: 40px; border-radius: 50%;
  border: none; background: transparent;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; color: var(--on-surface, #1e1633);
  transition: background 0.15s, transform 0.15s;
}
.task-header__icon-btn:active { transform: scale(0.92); }
.task-header__icon-btn:hover { background: rgba(59, 31, 140, 0.08); }
.task-header__icon-btn .mso { font-size: 22px; }

/* ── Main ───────────────────────────────────────────────────────── */
.task-main {
  max-width: 800px;
  margin: 0 auto;
  padding: 24px 16px 80px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ── Stats ─────────────────────────────────────────────────────── */
.task-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.task-stat-card {
  background: var(--surface-container-lowest, #fff);
  border-radius: 16px;
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  box-shadow: 0 2px 8px rgba(46, 36, 73, 0.05);
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
  border: 2px solid transparent;
}
.task-stat-card:hover { transform: translateY(-1px); box-shadow: 0 4px 16px rgba(46, 36, 73, 0.08); }
.task-stat-card--active { border-color: var(--primary, #3b1f8c); }

.task-stat-card__icon {
  width: 44px; height: 44px;
  border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  font-size: 22px;
}
.task-stat-card__icon--running { background: rgba(59, 31, 140, 0.1); color: var(--primary, #3b1f8c); }
.task-stat-card__icon--pending { background: rgba(113, 119, 134, 0.1); color: #737786; }
.task-stat-card__icon--done { background: rgba(8, 153, 129, 0.1); color: #089981; }
.task-stat-card__icon--total { background: rgba(59, 31, 140, 0.06); color: #5a34a8; }

.task-stat-card__info { display: flex; flex-direction: column; gap: 2px; }
.task-stat-card__num {
  font-family: var(--font-headline, 'Manrope', sans-serif);
  font-size: 1.5rem; font-weight: 800;
  color: var(--on-surface, #1e1633);
  letter-spacing: -0.03em; line-height: 1;
}
.task-stat-card__label { font-size: 11px; color: var(--on-surface-variant, #464455); }

/* ── Filter Tabs ─────────────────────────────────────────────────── */
.task-filter-tabs {
  display: flex;
  gap: 4px;
  background: var(--surface-container-low, #ede8ff);
  border-radius: 12px;
  padding: 4px;
}

.task-filter-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--on-surface-variant, #464455);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.task-filter-tab:hover { background: rgba(255, 255, 255, 0.5); }
.task-filter-tab--active {
  background: var(--surface-container-lowest, #fff);
  color: var(--primary, #3b1f8c);
  box-shadow: 0 1px 4px rgba(46, 36, 73, 0.1);
}

.task-filter-tab__count {
  font-size: 11px;
  background: var(--outline-variant, rgba(196, 198, 208, 0.3));
  padding: 1px 6px;
  border-radius: 999px;
}
.task-filter-tab--active .task-filter-tab__count {
  background: rgba(59, 31, 140, 0.1);
  color: var(--primary, #3b1f8c);
}

/* ── Loading ─────────────────────────────────────────────────────── */
.task-loading {
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  padding: 60px 0; gap: 12px;
  color: var(--on-surface-variant, #464455);
}
.task-loading__spinner {
  width: 32px; height: 32px;
  border: 3px solid var(--outline-variant, rgba(196, 198, 208, 0.3));
  border-top-color: var(--primary, #3b1f8c);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Empty ─────────────────────────────────────────────────────── */
.task-empty {
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  padding: 60px 0; gap: 16px;
  color: var(--on-surface-variant, #464455);
  text-align: center;
}
.task-empty .mso { font-size: 48px; opacity: 0.3; }
.task-empty p { margin: 0; font-size: 14px; }

/* ── Task List ──────────────────────────────────────────────────── */
.task-list { display: flex; flex-direction: column; gap: 12px; }

.task-card {
  background: var(--surface-container-lowest, #fff);
  border-radius: 16px;
  padding: 16px 16px 16px 20px;
  box-shadow: 0 2px 8px rgba(46, 36, 73, 0.05);
  position: relative;
  overflow: hidden;
  transition: box-shadow 0.15s, transform 0.15s;
  border-left: 3px solid var(--outline-variant, rgba(196, 198, 208, 0.3));
}
.task-card:hover { box-shadow: 0 4px 16px rgba(46, 36, 73, 0.1); transform: translateY(-1px); }
.task-card--in_progress { border-left-color: var(--primary, #3b1f8c); }
.task-card--completed { border-left-color: var(--down, #089981); opacity: 0.8; }
.task-card--pending { border-left-color: var(--outline, #747780); }

.task-card__priority-bar {
  position: absolute;
  top: 0; left: 0; bottom: 0; width: 3px;
  background: var(--up, #f23645);
}

.task-card__header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.task-card__status-icon { flex-shrink: 0; padding-top: 2px; }

.task-card__status-dot {
  display: block;
  width: 10px; height: 10px;
  border-radius: 50%;
}
.task-card__status-dot--running {
  background: var(--primary, #3b1f8c);
  animation: pulse-dot 1.2s ease-in-out infinite;
}
@keyframes pulse-dot {
  0%, 100% { box-shadow: 0 0 0 0 rgba(59, 31, 140, 0.4); }
  50% { box-shadow: 0 0 0 4px rgba(59, 31, 140, 0); }
}

.task-card__status-check {
  display: flex; align-items: center; justify-content: center;
  width: 18px; height: 18px;
  border-radius: 50%;
  background: var(--down, #089981);
  color: white;
  font-size: 12px;
}
.task-card__status-check .mso { font-size: 12px; }

.task-card__status-circle {
  display: block;
  width: 10px; height: 10px;
  border-radius: 50%;
  border: 2px solid var(--outline-variant, rgba(196, 198, 208, 0.5));
}

.task-card__info { flex: 1; min-width: 0; }

.task-card__subject {
  font-size: 15px; font-weight: 700;
  color: var(--on-surface, #1e1633);
  margin: 0 0 6px;
  line-height: 1.3;
}
.task-card--completed .task-card__subject {
  text-decoration: line-through;
  color: var(--on-surface-variant, #464455);
}

.task-card__meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.task-card__owner,
.task-card__time {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--on-surface-variant, #464455);
}
.task-card__owner .mso,
.task-card__time .mso { font-size: 14px; }

.task-card__active-form {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: var(--primary, #3b1f8c);
  font-weight: 600;
}

.task-card__spinner-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--primary, #3b1f8c);
  animation: pulse-dot 1.2s ease-in-out infinite;
}

.task-card__priority-badge {
  flex-shrink: 0;
  font-size: 10px; font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--surface-dim, #c7c2eb);
  color: var(--on-surface-variant, #464455);
}
.task-card__priority-badge--medium {
  background: rgba(59, 31, 140, 0.1);
  color: var(--primary, #3b1f8c);
}
.task-card__priority-badge--high {
  background: rgba(242, 54, 69, 0.1);
  color: var(--up, #f23645);
}

.task-card__actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.task-card__action-btn {
  width: 32px; height: 32px;
  border-radius: 8px;
  border: none;
  background: transparent;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer;
  color: var(--on-surface-variant, #464455);
  font-size: 18px;
  transition: background 0.15s, color 0.15s;
}
.task-card__action-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.task-card__action-btn:hover:not(:disabled) { background: var(--surface-container-low, #ede8ff); }

.task-card__action-btn--start:hover { color: var(--primary, #3b1f8c); background: rgba(59, 31, 140, 0.08); }
.task-card__action-btn--done:hover { color: var(--down, #089981); background: rgba(8, 153, 129, 0.08); }
.task-card__action-btn--delete:hover { color: var(--error, #ba1a1a); background: rgba(186, 26, 26, 0.08); }

.task-card__description {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--outline-variant, rgba(196, 198, 208, 0.3));
}
.task-card__description p {
  margin: 0;
  font-size: 13px;
  color: var(--on-surface-variant, #464455);
  line-height: 1.5;
}

.task-card__deps {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--on-surface-variant, #464455);
}
.task-card__deps .mso { font-size: 14px; }

/* ── Buttons ─────────────────────────────────────────────────────── */
.task-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 10px;
  border: none;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  font-family: inherit;
}
.task-btn .mso { font-size: 16px; }
.task-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.task-btn--primary {
  background: var(--primary, #3b1f8c);
  color: white;
}
.task-btn--primary:hover:not(:disabled) {
  background: var(--primary-container, #5a34a8);
  transform: translateY(-1px);
}

.task-btn--outline {
  background: transparent;
  color: var(--on-surface-variant, #464455);
  border: 1.5px solid var(--outline-variant, rgba(196, 198, 208, 0.5));
}
.task-btn--outline:hover:not(:disabled) { background: var(--surface-container-low, #ede8ff); }

.task-btn--danger {
  background: var(--error, #ba1a1a);
  color: white;
}
.task-btn--danger:hover:not(:disabled) {
  background: #93000a;
}

.task-btn__spinner {
  width: 14px; height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

/* ── Modal ─────────────────────────────────────────────────────── */
.task-modal-overlay {
  position: fixed; inset: 0;
  z-index: 100;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.task-modal {
  background: var(--surface-container-lowest, #fff);
  border-radius: 20px;
  width: 100%;
  max-width: 520px;
  box-shadow: 0 20px 60px rgba(46, 36, 73, 0.2);
  display: flex;
  flex-direction: column;
  max-height: 90dvh;
  overflow: hidden;
}
.task-modal--sm { max-width: 400px; }

.task-modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 20px 0;
}
.task-modal__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 1rem; font-weight: 800;
  color: var(--on-surface, #1e1633);
  margin: 0;
  letter-spacing: -0.02em;
}
.task-modal__title .mso { font-size: 20px; color: var(--primary, #3b1f8c); }

.task-modal__close {
  width: 32px; height: 32px;
  border-radius: 8px;
  border: none; background: transparent;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; color: var(--on-surface-variant, #464455);
  font-size: 20px;
  transition: background 0.15s;
}
.task-modal__close:hover { background: var(--surface-container-low, #ede8ff); }

.task-modal__body {
  padding: 20px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.task-modal__hint {
  font-size: 13px;
  color: var(--on-surface-variant, #464455);
  margin: 0;
}

.task-modal__footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding: 0 20px 20px;
}

/* ── Form ─────────────────────────────────────────────────────────── */
.task-form-field { display: flex; flex-direction: column; gap: 6px; }
.task-form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }

.task-form-label {
  font-size: 12px; font-weight: 700;
  color: var(--on-surface-variant, #464455);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.task-form-input,
.task-form-textarea,
.task-form-select {
  padding: 10px 14px;
  border-radius: 10px;
  border: 1.5px solid var(--outline-variant, rgba(196, 198, 208, 0.5));
  background: var(--surface, #f5f2ff);
  font-size: 14px;
  color: var(--on-surface, #1e1633);
  font-family: inherit;
  transition: border-color 0.15s;
  outline: none;
}
.task-form-input:focus,
.task-form-textarea:focus,
.task-form-select:focus {
  border-color: var(--primary, #3b1f8c);
}
.task-form-textarea { resize: vertical; min-height: 80px; line-height: 1.5; }
</style>
