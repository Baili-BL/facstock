/**
 * 任务管理 API 客户端
 * 对接后端 /api/tasks/* 端点
 *
 * 参考 tasktool 的 TaskCreateTool, TaskListTool, TaskUpdateTool 等工具设计
 */

const BASE = '/api'

// ─── 通用请求 ────────────────────────────────────────────────────────────

async function apiPost(path, body = {}, options = {}) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    ...options,
  })
  const json = await res.json()
  if (!json.success) throw new Error(json.error || '请求失败')
  return json
}

async function apiGet(path) {
  const res = await fetch(path)
  const json = await res.json()
  if (!json.success) throw new Error(json.error || '请求失败')
  return json
}

async function apiPut(path, body = {}) {
  const res = await fetch(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const json = await res.json()
  if (!json.success) throw new Error(json.error || '请求失败')
  return json
}

async function apiDel(path) {
  const res = await fetch(path, { method: 'DELETE' })
  const json = await res.json()
  if (!json.success) throw new Error(json.error || '请求失败')
  return json
}

// ─── Task 数据结构（参考 tasktool）───────────────────────────────────────
/**
 * @typedef {Object} Task
 * @property {number} id
 * @property {string} subject        - 任务标题（祈使句）
 * @property {string} description    - 详细描述
 * @property {'pending'|'in_progress'|'completed'|'deleted'} status
 * @property {string|null} owner      - 负责人
 * @property {string|null} active_form - 进行中动画文字
 * @property {number} priority        - 优先级（越大越高）
 * @property {Object|null} metadata   - 扩展数据
 * @property {string[]} blocked_by    - 依赖的任务 ID 列表
 * @property {string[]} blocks        - 被阻塞的任务 ID 列表
 * @property {string|null} created_at - 创建时间 (ISO)
 * @property {string|null} updated_at - 更新时间 (ISO)
 * @property {string|null} started_at - 开始时间 (ISO)
 * @property {string|null} completed_at - 完成时间 (ISO)
 */

// ─── CRUD 操作 ───────────────────────────────────────────────────────────

/**
 * 列出任务
 * @param {Object} params
 * @param {'pending'|'in_progress'|'completed'} [params.status]
 * @param {string} [params.owner]
 * @param {number} [params.limit=100]
 * @returns {Promise<Task[]>}
 */
export async function fetchTasks(params = {}) {
  const qs = new URLSearchParams()
  if (params.status)  qs.set('status', params.status)
  if (params.owner)    qs.set('owner', params.owner)
  if (params.limit)    qs.set('limit', params.limit)
  const path = `${BASE}/tasks${qs.size ? '?' + qs : ''}`
  const json = await apiGet(path)
  return json.data
}

/**
 * 获取单个任务
 * @param {number} taskId
 * @returns {Promise<Task>}
 */
export async function fetchTask(taskId) {
  const json = await apiGet(`${BASE}/tasks/${taskId}`)
  return json.data
}

/**
 * 创建任务
 * @param {Object} params
 * @param {string} params.subject         - 任务标题（必填）
 * @param {string} [params.description]   - 详细描述
 * @param {string} [params.owner]        - 负责人
 * @param {string} [params.active_form]  - 进行中动画文字
 * @param {number} [params.priority=0]  - 优先级
 * @param {Object} [params.metadata]     - 扩展数据
 * @param {string[]} [params.blocked_by] - 依赖任务 ID 列表
 * @returns {Promise<Task>}
 */
export async function createTask(params) {
  const body = {
    subject: params.subject,
    description: params.description || '',
    owner: params.owner || null,
    active_form: params.active_form || null,
    priority: params.priority || 0,
    metadata: params.metadata || null,
    blocked_by: params.blocked_by || null,
  }
  const json = await apiPost(`${BASE}/tasks`, body)
  return json.data
}

/**
 * 更新任务
 * @param {number} taskId
 * @param {Object} params
 * @param {string} [params.subject]
 * @param {string} [params.description]
 * @param {'pending'|'in_progress'|'completed'} [params.status]
 * @param {string} [params.owner]
 * @param {string} [params.active_form]
 * @param {number} [params.priority]
 * @param {Object} [params.metadata]
 * @param {string[]} [params.blocked_by]
 * @returns {Promise<Task>}
 */
export async function updateTask(taskId, params = {}) {
  const body = {}
  if (params.subject !== undefined)    body.subject     = params.subject
  if (params.description !== undefined) body.description = params.description
  if (params.status !== undefined)      body.status      = params.status
  if (params.owner !== undefined)       body.owner       = params.owner
  if (params.active_form !== undefined)body.active_form= params.active_form
  if (params.priority !== undefined)   body.priority    = params.priority
  if (params.metadata !== undefined)  body.metadata    = params.metadata
  if (params.blocked_by !== undefined)body.blocked_by  = params.blocked_by
  const json = await apiPut(`${BASE}/tasks/${taskId}`, body)
  return json.data
}

/**
 * 删除任务（软删除）
 * @param {number} taskId
 * @returns {Promise<{id: number}>}
 */
export async function deleteTask(taskId) {
  const json = await apiDel(`${BASE}/tasks/${taskId}`)
  return json.data
}

/**
 * 获取任务统计摘要
 * @returns {Promise<{total: number, pending: number, in_progress: number, completed: number}>}
 */
export async function fetchTaskSummary() {
  const json = await apiGet(`${BASE}/tasks/summary`)
  return json.data
}

// ─── 快捷操作 ───────────────────────────────────────────────────────────

/**
 * 开始任务（status → in_progress）
 */
export async function startTask(taskId, activeForm = null) {
  return updateTask(taskId, {
    status: 'in_progress',
    active_form: activeForm,
  })
}

/**
 * 完成任务（status → completed）
 */
export async function completeTask(taskId) {
  return updateTask(taskId, { status: 'completed' })
}
