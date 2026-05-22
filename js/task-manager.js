/**
 * Task Manager - 任务管理系统
 * 创建、筛选、统计任务，支持异步批量操作
 */

// ============================================================
// 常量定义
// ============================================================

/** 优先级枚举 */
const PRIORITY = { LOW: 'low', MEDIUM: 'medium', HIGH: 'high', URGENT: 'urgent' };

/** 状态枚举 */
const STATUS = { TODO: 'todo', IN_PROGRESS: 'in_progress', DONE: 'done', ARCHIVED: 'archived' };

/** 优先级对应的排序权重（数值越大越优先） */
const PRIORITY_ORDER = { [PRIORITY.LOW]: 1, [PRIORITY.MEDIUM]: 2, [PRIORITY.HIGH]: 3, [PRIORITY.URGENT]: 4 };

/** 优先级显示标签 */
const PRIORITY_LABELS = { [PRIORITY.LOW]: '🟢 低', [PRIORITY.MEDIUM]: '🟡 中', [PRIORITY.HIGH]: '🟠 高', [PRIORITY.URGENT]: '🔴 紧急' };

/** 状态显示标签 */
const STATUS_LABELS = { [STATUS.TODO]: '待办', [STATUS.IN_PROGRESS]: '进行中', [STATUS.DONE]: '已完成', [STATUS.ARCHIVED]: '已归档' };

// 全局自增 ID 计数器（用于辅助生成唯一 ID）
let idCounter = 0;

/**
 * 生成唯一任务 ID
 * 组合：时间戳(36进制) + 随机字符串(6位) + 自增计数器
 */
function generateId() {
  idCounter++;
  return `task_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}_${idCounter}`;
}

// ============================================================
// Task 类 —— 单个任务实体
// ============================================================

class Task {
  /**
   * @param {string} title       - 任务标题（必填，不能为空）
   * @param {string} description - 任务描述（可选，默认为空）
   * @param {string} priority    - 优先级（可选，默认 MEDIUM）
   */
  constructor(title, description = '', priority = PRIORITY.MEDIUM) {
    if (!title || !title.trim()) throw new Error('任务标题不能为空');

    this.id = generateId();           // 唯一标识
    this.title = title.trim();        // 标题
    this.description = description.trim(); // 描述
    this.priority = priority;         // 优先级
    this.status = STATUS.TODO;        // 状态（初始为待办）
    this.createdAt = new Date();      // 创建时间
    this.updatedAt = new Date();      // 最后更新时间
    this.completedAt = null;          // 完成时间（未完成时为 null）
    this.tags = [];                   // 标签列表
    this.assignedTo = null;           // 负责人
    this.estimatedHours = 0;          // 预估工时（小时）
    this.actualHours = 0;             // 实际工时（小时）
  }

  /**
   * 更新任务基本信息
   * @param {string|undefined} title       - 新标题（传 undefined 表示不改）
   * @param {string|undefined} description - 新描述
   * @param {string|undefined} priority    - 新优先级
   */
  update(title, description, priority) {
    if (title !== undefined && !title.trim()) throw new Error('任务标题不能为空');
    if (title !== undefined) this.title = title.trim();
    if (description !== undefined) this.description = description.trim();
    if (priority !== undefined) {
      if (!Object.values(PRIORITY).includes(priority)) throw new Error(`无效优先级: ${priority}`);
      this.priority = priority;
    }
    this.updatedAt = new Date();
  }

  /** 标记为「进行中」（已完成的任务不允许重新开始） */
  markAsInProgress() {
    if (this.status === STATUS.DONE) throw new Error('已完成的任务不能重新开始');
    this.status = STATUS.IN_PROGRESS;
    this.updatedAt = new Date();
  }

  /** 标记为「已完成」，记录完成时间 */
  markAsDone() { this.status = STATUS.DONE; this.completedAt = new Date(); this.updatedAt = new Date(); }

  /** 标记为「已归档」 */
  markAsArchived() { this.status = STATUS.ARCHIVED; this.updatedAt = new Date(); }

  /** 添加标签（去重） */
  addTag(tag) { const t = tag.trim(); if (t && !this.tags.includes(t)) this.tags.push(t); }

  /** 移除指定标签 */
  removeTag(tag) { this.tags = this.tags.filter(t => t !== tag.trim()); }

  /** 指派负责人 */
  assignTo(person) { this.assignedTo = person.trim(); this.updatedAt = new Date(); }

  /** 设置预估工时 */
  setEstimatedHours(h) { if (h < 0) throw new Error('预估时间不能为负'); this.estimatedHours = h; }

  /** 增加实际工时（累加） */
  addActualHours(h) { if (h < 0) throw new Error('工时不能为负'); this.actualHours += h; this.updatedAt = new Date(); }

  /**
   * 获取任务摘要（含优先级图标、标题、状态、标签、负责人）
   * 示例输出：🔴 修复登录页 Bug - 进行中 [紧急修复, 前端] 负责人: 王五
   */
  getSummary() {
    const p = PRIORITY_LABELS[this.priority];
    const s = STATUS_LABELS[this.status];
    const tags = this.tags.length ? ` [${this.tags.join(', ')}]` : '';
    const person = this.assignedTo ? ` 负责人: ${this.assignedTo}` : '';
    return `${p} ${this.title} - ${s}${tags}${person}`;
  }

  /** 序列化为普通对象（用于 JSON 输出 / 持久化） */
  toJSON() {
    return {
      id: this.id, title: this.title, description: this.description,
      priority: this.priority, status: this.status,
      createdAt: this.createdAt.toISOString(),
      updatedAt: this.updatedAt.toISOString(),
      completedAt: this.completedAt?.toISOString() || null,
      tags: [...this.tags], assignedTo: this.assignedTo,
      estimatedHours: this.estimatedHours, actualHours: this.actualHours
    };
  }
}

// ============================================================
// TaskManager 类 —— 任务管理器（增删改查 + 筛选/排序/统计）
// ============================================================

class TaskManager {
  constructor() {
    this.tasks = new Map();   // 以 task.id 为 key 的任务映射表
  }

  /** 创建并添加一个新任务 */
  addTask(title, description, priority) {
    const task = new Task(title, description, priority);
    this.tasks.set(task.id, task);
    return task;
  }

  /** 根据 ID 获取任务（不存在则抛异常） */
  getTask(id) {
    const task = this.tasks.get(id);
    if (!task) throw new Error(`任务不存在: ${id}`);
    return task;
  }

  /** 删除指定任务，返回是否成功删除 */
  removeTask(id) {
    if (!this.tasks.has(id)) throw new Error(`任务不存在: ${id}`);
    return this.tasks.delete(id);
  }

  /** 获取全部任务列表 */
  getAll() { return Array.from(this.tasks.values()); }

  /** 按状态筛选 */
  filterByStatus(status) { return this.getAll().filter(t => t.status === status); }

  /** 按优先级筛选 */
  filterByPriority(priority) { return this.getAll().filter(t => t.priority === priority); }

  /** 按标签筛选（精确匹配） */
  filterByTag(tag) { return this.getAll().filter(t => t.tags.includes(tag)); }

  /** 按关键词搜索标题和描述（大小写不敏感） */
  search(keyword) {
    const kw = keyword.toLowerCase();
    return this.getAll().filter(t =>
      t.title.toLowerCase().includes(kw) || t.description.toLowerCase().includes(kw)
    );
  }

  /** 按优先级降序排序（紧急 > 高 > 中 > 低） */
  getSortedByPriority() {
    return this.getAll().sort((a, b) => PRIORITY_ORDER[b.priority] - PRIORITY_ORDER[a.priority]);
  }

  /** 按创建时间排序（asc=true 升序，false 降序） */
  getSortedByCreatedAt(asc = true) {
    return this.getAll().sort((a, b) => asc ? a.createdAt - b.createdAt : b.createdAt - a.createdAt);
  }

  /**
   * 统计信息
   * @returns {{ total, byStatus, completed, completionRate, totalEstimatedHours, totalActualHours }}
   */
  getStatistics() {
    const total = this.tasks.size;
    const byStatus = {};
    let completed = 0;
    for (const t of this.tasks.values()) {
      byStatus[t.status] = (byStatus[t.status] || 0) + 1;
      if (t.status === STATUS.DONE) completed++;
    }
    const totalEst = this.getAll().reduce((s, t) => s + t.estimatedHours, 0);
    const totalAct = this.getAll().reduce((s, t) => s + t.actualHours, 0);
    return {
      total, byStatus, completed,
      completionRate: total > 0 ? `${((completed / total) * 100).toFixed(1)}%` : '0%',
      totalEstimatedHours: totalEst, totalActualHours: totalAct
    };
  }

  /** 按照优先级排序后打印全部任务到控制台 */
  printAll() {
    const sorted = this.getSortedByPriority();
    console.log(`\n========== 任务列表 (共 ${sorted.length} 项) ==========\n`);
    sorted.forEach((t, i) => console.log(`${i + 1}. ${t.getSummary()}`));
    console.log('\n============================================\n');
  }
}

// ============================================================
// 辅助函数
// ============================================================

/** 返回一个指定毫秒后 resolve 的 Promise（用于模拟异步延迟） */
function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

// ============================================================
// 批量操作（异步，带模拟延迟）
// ============================================================

/**
 * 批量创建任务（逐个创建，间隔 50ms 模拟耗时）
 * @param {TaskManager} manager
 * @param {Array<{title, description, priority}>} entries
 * @returns {Promise<Task[]>}
 */
async function batchCreateTasks(manager, entries) {
  const created = [];
  for (const e of entries) {
    await delay(50);
    const task = manager.addTask(e.title, e.description, e.priority);
    created.push(task);
    console.log(`✅ 创建: ${task.title}`);
  }
  return created;
}

/**
 * 批量完成任务（逐个完成，间隔 30ms；单个失败不影响其他）
 * @param {TaskManager} manager
 * @param {string[]} ids
 * @returns {Promise<Array<{id, success, error?}>>}
 */
async function batchCompleteTasks(manager, ids) {
  const results = [];
  for (const id of ids) {
    await delay(30);
    try {
      const task = manager.getTask(id);
      task.markAsDone();
      results.push({ id, success: true });
      console.log(`✅ 完成: ${task.title}`);
    } catch (err) {
      results.push({ id, success: false, error: err.message });
    }
  }
  return results;
}

// ============================================================
// 演示入口
// ============================================================

async function main() {
  console.log('🚀 任务管理系统启动\n');
  const mgr = new TaskManager();

  // --- 创建示例任务 ---
  const t1 = mgr.addTask('完成年终总结报告', '撰写并提交年度工作总结', PRIORITY.HIGH);
  const t2 = mgr.addTask('准备团队周会材料', '整理本周工作进度', PRIORITY.MEDIUM);
  const t3 = mgr.addTask('修复登录页 Bug', '点击登录按钮无响应', PRIORITY.URGENT);
  const t4 = mgr.addTask('更新项目文档', '补充 API 接口说明', PRIORITY.LOW);
  const t5 = mgr.addTask('代码审查', 'Review feature 分支的 PR', PRIORITY.MEDIUM);

  // --- 设置任务属性 ---
  t1.assignTo('张三'); t1.addTag('文档'); t1.setEstimatedHours(4);
  t2.assignTo('李四'); t2.addTag('会议'); t2.setEstimatedHours(1);
  t3.assignTo('王五'); t3.addTag('紧急修复'); t3.addTag('前端'); t3.setEstimatedHours(3);
  t4.addTag('文档'); t4.setEstimatedHours(2);
  t5.assignTo('张三'); t5.addTag('代码质量'); t5.setEstimatedHours(2.5);

  // --- 变更状态 ---
  t3.markAsInProgress();
  t5.markAsInProgress();

  mgr.printAll();

  console.log('📊 统计:', JSON.stringify(mgr.getStatistics(), null, 2));

  console.log('\n🔍 搜索"文档"的任务:');
  mgr.search('文档').forEach(t => console.log(`   - ${t.title}`));

  console.log('\n📦 批量创建...');
  await batchCreateTasks(mgr, [
    { title: '数据库备份', description: '每周全量备份', priority: PRIORITY.HIGH },
    { title: '清理临时文件', description: '删除过期日志', priority: PRIORITY.LOW }
  ]);

  console.log('\n📦 批量完成...');
  await batchCompleteTasks(mgr, [t1.id, t4.id]);

  mgr.printAll();
  console.log('🎉 演示结束');
}

// 直接运行脚本时执行演示
if (require.main === module) main().catch(console.error);

// 导出供其他模块使用
module.exports = { PRIORITY, STATUS, Task, TaskManager, batchCreateTasks, batchCompleteTasks };
