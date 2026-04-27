<template>
  <div class="fac-root">
    <!-- TopAppBar -->
    <header class="fac-header">
      <div class="fac-header__left">
        <button type="button" class="fac-header__icon-btn" aria-label="返回" @click="goBack">
          <span class="mso">arrow_back</span>
      </button>
        <div class="fac-header__brand">
          <div class="fac-header__avatar" :aria-label="agentName">{{ agentInitial }}</div>
          <div class="fac-header__title-group">
            <h1 class="fac-header__title">{{ agentName }}</h1>
            <span class="fac-header__subtitle">{{ roleSubtitle }}</span>
        </div>
        </div>
      </div>
      <div class="fac-header__right">
        <span v-if="isFromHistory" class="fac-badge fac-badge--history">
          <span class="mso" style="font-size:12px">history</span>
          今日记录
        </span>
        <span class="fac-badge" :class="isRunning ? 'fac-badge--running' : isDone ? 'fac-badge--done' : 'fac-badge--pending'">
          <span v-if="isRunning" class="fac-badge__dot fac-badge__dot--spin" />
          <span v-else-if="isDone" class="fac-badge__dot" />
          {{ isRunning ? '分析中' : isDone ? '已完成' : '待分析' }}
        </span>
      </div>
    </header>

    <!-- Content Canvas -->
    <main class="fac-main">

      <!-- ── 策略提示词卡片 ───────────────────────────────────── -->
      <section class="fac-prompt-card">
        <div class="fac-prompt-card__glow" />
        <div class="fac-prompt-card__head">
          <h2 class="fac-prompt-card__title">
            <span class="mso">terminal</span>
            策略核心理念
          </h2>
          <button type="button" class="fac-prompt-card__expand" @click="showPromptModal = true">
            查看全部 <span class="mso">chevron_right</span>
          </button>
        </div>
        <pre class="fac-prompt-card__code">{{ agentInfo.tagline || '加载中...' }}</pre>
      </section>

      <!-- ── 任务执行过程（横向步骤条）────────────────────────── -->
      <TaskProcessCard
        v-if="isRunning || isDone"
        :steps="cotSteps"
        :current-step="currentCotStep"
        :total-steps="totalCotSteps"
        :current-step-title="currentCotTitle"
        :current-step-detail="currentStepDetail"
        :is-running="isRunning"
        :is-done="isDone"
        :confidence="result?.cot_steps_confidence ?? confidence"
        :stance="result?.cot_steps_stance ?? structured?.stance"
        :market-commentary="result?.cot_steps_marketCommentary ?? structured?.marketCommentary"
      />

      <!-- ── AI 思考过程 ─────────────────────────────────── -->
      <section class="fac-thinking-card">
        <!-- 折叠头 -->
        <div
          class="fac-thinking-card__head"
          role="button"
          tabindex="0"
          @click="thinkingExpanded = !thinkingExpanded"
          @keydown.enter.prevent="thinkingExpanded = !thinkingExpanded"
          @keydown.space.prevent="thinkingExpanded = !thinkingExpanded"
        >
          <span class="mso">memory</span>
          <h2 class="fac-thinking-card__title">AI 分析过程</h2>
          <span class="fac-thinking-card__count">{{ thinkingLines.length }} 步</span>
          <span class="fac-thinking-card__toggle" :class="{ 'fac-thinking-card__toggle--open': thinkingExpanded }">
            <span class="mso">expand_more</span>
          </span>
        </div>

        <!-- 时间线 -->
        <div v-show="thinkingExpanded" class="fac-timeline">
          <div
            v-for="(line, i) in thinkingLines"
            :key="'tl-' + i"
            class="fac-timeline__item"
          >
            <div class="fac-timeline__dot" :class="{ 'fac-timeline__dot--active': (line.startsWith('[步骤') || line.startsWith('[阶段')) && i === thinkingLines.length - 1 }">
              <span class="mso">{{ line.startsWith('[步骤') ? 'task_alt' : line.startsWith('[调用') ? 'cloud_download' : line.startsWith('[数据') ? 'database' : line.startsWith('[结果') ? 'database' : line.startsWith('[阶段]') ? 'auto_awesome' : 'smart_toy' }}</span>
          </div>
            <div class="fac-timeline__content" :class="{ 'fac-timeline__content--active': (line.startsWith('[步骤') || line.startsWith('[阶段')) && i === thinkingLines.length - 1 }">
              <div class="fac-timeline__title">
                {{ line.startsWith('[步骤') ? '任务步骤' : line.startsWith('[调用') ? '数据获取' : line.startsWith('[数据') ? '数据获取' : line.startsWith('[结果') ? '返回数据' : line.startsWith('[阶段]') ? '推理阶段' : '思考中' }}
                <span v-if="line.startsWith('[阶段]') && i === thinkingLines.length - 1" class="fac-timeline__dots">
                  <span class="fac-timeline__dot-anim" />
                  <span class="fac-timeline__dot-anim" />
                  <span class="fac-timeline__dot-anim" />
                </span>
        </div>
              <p class="fac-timeline__desc">{{ line.replace(/^\[[^\]]+\]\s*/, '') }}</p>
            </div>
          </div>
        </div>

        <!-- 分析中时间线占位（实时滚动用） -->
        <div v-if="isRunning && !thinkingLines.length" class="fac-timeline">
          <div class="fac-timeline__item">
            <div class="fac-timeline__dot fac-timeline__dot--active">
              <span class="mso">model_training</span>
            </div>
            <div class="fac-timeline__content fac-timeline__content--active">
              <div class="fac-timeline__title">
                正在分析
                <span class="fac-timeline__dots">
                  <span class="fac-timeline__dot-anim" />
                  <span class="fac-timeline__dot-anim" />
                  <span class="fac-timeline__dot-anim" />
                </span>
              </div>
              <p class="fac-timeline__desc">等待 AI 智能体返回分析结果...</p>
            </div>
          </div>
        </div>

        <!-- 启动按钮 -->
        <div class="fac-thinking-card__run-btn-wrap">
        <button
          type="button"
            class="fac-btn-run"
            :class="{ 'fac-btn-run--running': isRunning }"
          :disabled="isRunning"
          @click="runAnalysis"
        >
            <span v-if="isRunning" class="fac-btn-run__spinner" />
            <span v-else class="mso">play_arrow</span>
            {{ isRunning ? '分析中...' : isFromHistory ? '再次分析' : '启动 AI 分析' }}
          </button>
        </div>
      </section>

      <!-- ── 实时分析报告 ─────────────────────────────────── -->
      <section v-if="liveReportLines.length || beijingExecution || qiaoExecution || jiaExecution" class="fac-report-card">
        <div class="fac-report-card__head">
          <span class="mso">description</span>
          <h2 class="fac-report-card__title">{{ isRunning ? '实时分析报告' : '分析报告' }}</h2>
          <span v-if="isRunning" class="fac-report-card__live">
            <span class="fac-report-card__live-dot" />
            实时输出
          </span>
        </div>
        <div class="fac-report-card__body" ref="liveEl">
          <div v-if="qiaoExecution" class="fac-report-card__module">
            <div class="fac-report-card__module-head">
              <span class="mso">dashboard</span>
              <span class="fac-report-card__module-title">乔帮主执行工件</span>
            </div>

            <section class="fac-beijing-card fac-beijing-card--embedded fac-qiao-card">
              <div class="fac-beijing-card__body">
                <div v-if="qiaoExecution.marketGate?.status" class="fac-beijing-card__gate">
                  <span class="fac-beijing-gate-chip" :class="`fac-beijing-gate-chip--${qiaoExecution.marketGate.status}`">
                    市场闸门 {{ qiaoExecution.marketGate.status }}
                  </span>
                  <span v-if="qiaoExecution.timeAnchor?.phase" class="fac-beijing-gate-chip fac-beijing-gate-chip--anchor">
                    时间锚点 {{ qiaoExecution.timeAnchor.phase }}
                  </span>
                  <span v-if="qiaoExecution.mainTheme?.name" class="fac-beijing-gate-chip fac-beijing-gate-chip--subtle">
                    主线 {{ qiaoExecution.mainTheme.name }}
                  </span>
                  <span v-if="qiaoExecution.mainTheme?.stage" class="fac-beijing-gate-chip fac-beijing-gate-chip--subtle">
                    阶段 {{ qiaoExecution.mainTheme.stage }}
                  </span>
                </div>

                <div class="fac-beijing-card__stats">
                  <div class="fac-beijing-stat">
                    <span class="fac-beijing-stat__label">今日涨停池</span>
                    <span class="fac-beijing-stat__value">{{ qiaoExecution.stats?.todayLimitUps ?? 0 }}</span>
                  </div>
                  <div class="fac-beijing-stat">
                    <span class="fac-beijing-stat__label">龙头样本</span>
                    <span class="fac-beijing-stat__value">{{ qiaoExecution.stats?.leaderCount ?? 0 }}</span>
                  </div>
                  <div class="fac-beijing-stat">
                    <span class="fac-beijing-stat__label">可买候选</span>
                    <span class="fac-beijing-stat__value">{{ qiaoExecution.stats?.actionableCount ?? 0 }}</span>
                  </div>
                  <div class="fac-beijing-stat">
                    <span class="fac-beijing-stat__label">低吸命中</span>
                    <span class="fac-beijing-stat__value">{{ qiaoExecution.stats?.lowAbsorbCount ?? 0 }}</span>
                  </div>
                </div>

                <div v-if="qiaoExecution.strategyPanels" class="fac-beijing-panels">
                  <section v-if="qiaoExecution.strategyPanels.timeAnchor?.phase" class="fac-beijing-panel">
                    <div class="fac-beijing-panel__head">
                      <span class="mso">schedule</span>
                      <h3 class="fac-beijing-panel__title">时间锚定</h3>
                    </div>
                    <article class="fac-beijing-panel__card fac-beijing-panel__card--anchor">
                      <div class="fac-beijing-panel__card-top">
                        <span class="fac-beijing-panel__pill fac-beijing-panel__pill--anchor">{{ qiaoExecution.strategyPanels.timeAnchor.phase }}</span>
                        <span class="fac-beijing-panel__count">{{ qiaoExecution.strategyPanels.timeAnchor.executionFocus }}</span>
                      </div>
                      <p class="fac-beijing-panel__desc">{{ qiaoExecution.strategyPanels.timeAnchor.window }}</p>
                      <p class="fac-beijing-panel__desc">{{ qiaoExecution.strategyPanels.timeAnchor.summary }}</p>
                      <div v-if="qiaoExecution.strategyPanels.timeAnchor.rules?.length" class="fac-beijing-panel__tags">
                        <span
                          v-for="(rule, idx) in qiaoExecution.strategyPanels.timeAnchor.rules"
                          :key="`qiao-anchor-rule-${idx}`"
                          class="fac-beijing-panel__tag fac-beijing-panel__tag--anchor"
                        >
                          {{ rule }}
                        </span>
                      </div>
                    </article>
                  </section>

                  <section v-if="qiaoExecution.strategyPanels.mainJudgement" class="fac-beijing-panel">
                    <div class="fac-beijing-panel__head">
                      <span class="mso">insights</span>
                      <h3 class="fac-beijing-panel__title">主线判断</h3>
                    </div>
                    <article class="fac-beijing-panel__card">
                      <div class="fac-beijing-panel__card-top">
                        <span class="fac-beijing-panel__pill">{{ qiaoExecution.strategyPanels.mainJudgement.mainTheme }}</span>
                        <span class="fac-beijing-panel__count">{{ qiaoExecution.strategyPanels.mainJudgement.stage }}</span>
                      </div>
                      <p class="fac-beijing-panel__desc">{{ qiaoExecution.strategyPanels.mainJudgement.summary }}</p>
                      <div class="fac-beijing-panel__tags">
                        <span class="fac-beijing-panel__tag">龙头 {{ qiaoExecution.strategyPanels.mainJudgement.leader }}</span>
                        <span class="fac-beijing-panel__tag">次主线 {{ qiaoExecution.strategyPanels.mainJudgement.backupTheme }}</span>
                      </div>
                      <div v-if="qiaoExecution.strategyPanels.mainJudgement.reasons?.length" class="fac-beijing-step__lines">
                        <p
                          v-for="(line, idx) in qiaoExecution.strategyPanels.mainJudgement.reasons"
                          :key="`qiao-main-judge-${idx}`"
                          class="fac-beijing-step__line"
                        >
                          {{ line }}
                        </p>
                      </div>
                    </article>
                  </section>

                  <section v-if="qiaoExecution.strategyPanels.cycleMap?.length" class="fac-beijing-panel">
                    <div class="fac-beijing-panel__head">
                      <span class="mso">sync</span>
                      <h3 class="fac-beijing-panel__title">情绪阶段</h3>
                    </div>
                    <div class="fac-beijing-panel__grid">
                      <article
                        v-for="item in qiaoExecution.strategyPanels.cycleMap"
                        :key="`qiao-cycle-${item.stage}`"
                        class="fac-beijing-panel__card"
                      >
                        <div class="fac-beijing-panel__card-top">
                          <span class="fac-beijing-panel__pill fac-beijing-panel__pill--board">{{ item.stage }}</span>
                          <span class="fac-beijing-panel__count">{{ item.count ? '当前' : '观察' }}</span>
                        </div>
                        <p class="fac-beijing-panel__desc">{{ item.description }}</p>
                      </article>
                    </div>
                  </section>

                  <section v-if="qiaoExecution.strategyPanels.leaderPaths?.length" class="fac-beijing-panel">
                    <div class="fac-beijing-panel__head">
                      <span class="mso">schema</span>
                      <h3 class="fac-beijing-panel__title">龙头路径</h3>
                    </div>
                    <div class="fac-beijing-panel__grid">
                      <article
                        v-for="item in qiaoExecution.strategyPanels.leaderPaths"
                        :key="`qiao-leader-${item.type}`"
                        class="fac-beijing-panel__card"
                      >
                        <div class="fac-beijing-panel__card-top">
                          <span class="fac-beijing-panel__pill">{{ item.type }}</span>
                          <span class="fac-beijing-panel__count">{{ item.count }}只</span>
                        </div>
                        <p class="fac-beijing-panel__desc">{{ item.description }}</p>
                      </article>
                    </div>
                  </section>

                  <section v-if="qiaoExecution.strategyPanels.entryPlaybook?.length" class="fac-beijing-panel">
                    <div class="fac-beijing-panel__head">
                      <span class="mso">style</span>
                      <h3 class="fac-beijing-panel__title">入场模型</h3>
                    </div>
                    <div class="fac-beijing-panel__grid">
                      <article
                        v-for="item in qiaoExecution.strategyPanels.entryPlaybook"
                        :key="`qiao-entry-${item.type}`"
                        class="fac-beijing-panel__card"
                      >
                        <div class="fac-beijing-panel__card-top">
                          <span class="fac-beijing-panel__pill fac-beijing-panel__pill--rule">{{ item.type }}</span>
                          <span class="fac-beijing-panel__count">{{ item.count }}只</span>
                        </div>
                        <p class="fac-beijing-panel__desc">{{ item.description }}</p>
                      </article>
                    </div>
                  </section>

                  <section v-if="qiaoExecution.strategyPanels.labelHits?.length" class="fac-beijing-panel">
                    <div class="fac-beijing-panel__head">
                      <span class="mso">sell</span>
                      <h3 class="fac-beijing-panel__title">标签命中</h3>
                    </div>
                    <div class="fac-beijing-panel__tags">
                      <span
                        v-for="item in qiaoExecution.strategyPanels.labelHits"
                        :key="`qiao-label-hit-${item.label}`"
                        class="fac-beijing-panel__tag"
                      >
                        {{ item.label }} · {{ item.count }}
                      </span>
                    </div>
                  </section>

                  <section v-if="qiaoExecution.strategyPanels.dailyRuleHits?.length" class="fac-beijing-panel">
                    <div class="fac-beijing-panel__head">
                      <span class="mso">checklist</span>
                      <h3 class="fac-beijing-panel__title">当日规则命中</h3>
                    </div>
                    <div class="fac-beijing-panel__grid">
                      <article
                        v-for="item in qiaoExecution.strategyPanels.dailyRuleHits"
                        :key="`qiao-rule-hit-${item.title}`"
                        class="fac-beijing-panel__card"
                      >
                        <div class="fac-beijing-panel__card-top">
                          <span class="fac-beijing-panel__pill fac-beijing-panel__pill--rule">{{ item.title }}</span>
                          <span class="fac-beijing-panel__count">{{ item.status }}</span>
                        </div>
                        <p class="fac-beijing-panel__desc">{{ item.detail }}</p>
                      </article>
                    </div>
                  </section>
                </div>

                <div v-if="qiaoExecution.stepOutputs?.length" class="fac-beijing-card__steps">
                  <article
                    v-for="step in qiaoExecution.stepOutputs"
                    :key="`qiao-${step.step}-${step.title}`"
                    class="fac-beijing-step"
                  >
                    <div class="fac-beijing-step__head">
                      <span class="fac-beijing-step__num">步骤 {{ step.step }}</span>
                      <div class="fac-beijing-step__copy">
                        <h3 class="fac-beijing-step__title">{{ step.title || `步骤 ${step.step}` }}</h3>
                        <p class="fac-beijing-step__summary">{{ step.summary || '暂无执行摘要' }}</p>
                      </div>
                    </div>
                    <div v-if="step.frameworkLines?.length" class="fac-beijing-step__section">
                      <div class="fac-beijing-step__section-label">方法论</div>
                      <div class="fac-beijing-step__lines fac-beijing-step__lines--method">
                        <p
                          v-for="(line, idx) in step.frameworkLines"
                          :key="`qiao-${step.step}-framework-${idx}`"
                          class="fac-beijing-step__line fac-beijing-step__line--method"
                        >
                          {{ line }}
                        </p>
                      </div>
                    </div>
                    <div v-if="step.lines?.length" class="fac-beijing-step__lines">
                      <div class="fac-beijing-step__section-label">当日判断</div>
                      <p
                        v-for="(line, idx) in step.lines"
                        :key="`qiao-${step.step}-${idx}`"
                        class="fac-beijing-step__line"
                      >
                        {{ line }}
                      </p>
                    </div>
                  </article>
                </div>

                <div v-if="qiaoExecution.leaderCandidates?.length" class="fac-beijing-card__section">
                  <div class="fac-beijing-card__section-head">龙头路径样本</div>
                  <div class="fac-beijing-card__list">
                    <article
                      v-for="item in qiaoExecution.leaderCandidates"
                      :key="`qiao-leader-candidate-${item.code}`"
                      class="fac-beijing-candidate"
                    >
                      <div class="fac-beijing-candidate__top">
                        <div class="fac-beijing-candidate__name">
                          {{ item.name }}
                          <span class="fac-beijing-candidate__code">{{ item.code }}</span>
                        </div>
                        <div class="fac-beijing-candidate__chips">
                          <span v-if="item.leaderType" class="fac-beijing-candidate__chip fac-beijing-candidate__chip--selection">{{ item.leaderType }}</span>
                          <span v-if="item.selectionType" class="fac-beijing-candidate__chip fac-beijing-candidate__chip--selection">{{ item.selectionType }}</span>
                          <span v-if="item.entryModel" class="fac-beijing-candidate__chip fac-beijing-candidate__chip--action">{{ item.entryModel }}</span>
                          <span v-if="item.sector" class="fac-beijing-candidate__chip">{{ item.sector }}</span>
                        </div>
                      </div>
                      <p class="fac-beijing-candidate__reason">{{ item.reason || item.classificationReason || '暂无龙头路径说明' }}</p>
                      <div class="fac-beijing-candidate__meta">
                        <span v-if="item.consecutiveDays">连板 {{ item.consecutiveDays }}</span>
                        <span v-if="item.firstSealTime">首封 {{ item.firstSealTime }}</span>
                        <span v-if="item.positionRatio">{{ item.positionRatio }}</span>
                        <span v-if="item.changePct || item.changePct === 0">涨幅 {{ normalizePctValue(item.changePct, item) }}%</span>
                        <span v-if="item.score">评分 {{ item.score }}</span>
                      </div>
                    </article>
                  </div>
                </div>

                <div v-if="qiaoExecution.actionableCandidates?.length" class="fac-beijing-card__section">
                  <div class="fac-beijing-card__section-head">主升可买候选池</div>
                  <div class="fac-beijing-card__list">
                    <article
                      v-for="item in qiaoExecution.actionableCandidates"
                      :key="`qiao-actionable-${item.code}`"
                      class="fac-beijing-candidate"
                    >
                      <div class="fac-beijing-candidate__top">
                        <div class="fac-beijing-candidate__name">
                          {{ item.name }}
                          <span class="fac-beijing-candidate__code">{{ item.code }}</span>
                        </div>
                        <div class="fac-beijing-candidate__chips">
                          <span v-if="item.selectionType" class="fac-beijing-candidate__chip fac-beijing-candidate__chip--selection">{{ item.selectionType }}</span>
                          <span v-if="item.leaderType" class="fac-beijing-candidate__chip fac-beijing-candidate__chip--selection">{{ item.leaderType }}</span>
                          <span v-if="item.tradeStatus" class="fac-beijing-candidate__chip fac-beijing-candidate__chip--status">{{ item.tradeStatus }}</span>
                          <span v-if="item.entryModel" class="fac-beijing-candidate__chip fac-beijing-candidate__chip--action">{{ item.entryModel }}</span>
                          <span v-if="item.stage" class="fac-beijing-candidate__chip">{{ item.stage }}</span>
                          <span
                            v-for="(label, idx) in (item.labels || []).slice(0, 3)"
                            :key="`${item.code}-qiao-actionable-label-${idx}`"
                            class="fac-beijing-candidate__chip fac-beijing-candidate__chip--label"
                          >{{ label }}</span>
                        </div>
                      </div>
                      <p class="fac-beijing-candidate__reason">{{ item.classificationReason || item.reason || '暂无入场说明' }}</p>
                      <div class="fac-beijing-candidate__meta">
                        <span v-if="item.entryTrigger">触发 {{ item.entryTrigger }}</span>
                        <span v-if="item.maSupportSummary">{{ item.maSupportSummary }}</span>
                        <span v-if="item.positionRatio">{{ item.positionRatio }}</span>
                        <span v-if="item.changePct || item.changePct === 0">涨幅 {{ normalizePctValue(item.changePct, item) }}%</span>
                        <span v-if="item.score">评分 {{ item.score }}</span>
                      </div>
                      <div v-if="item.matchedRules?.length" class="fac-beijing-rule-list">
                        <article
                          v-for="(rule, idx) in item.matchedRules.slice(0, 3)"
                          :key="`${item.code}-qiao-rule-${idx}`"
                          class="fac-beijing-rule-card"
                        >
                          <div class="fac-beijing-rule-card__title">{{ rule.title }}</div>
                          <div class="fac-beijing-rule-card__detail">{{ rule.detail }}</div>
                        </article>
                      </div>
                    </article>
                  </div>
                </div>
              </div>
            </section>
          </div>

          <div v-if="jiaExecution" class="fac-report-card__module">
            <div class="fac-report-card__module-head">
              <span class="mso">dashboard</span>
              <span class="fac-report-card__module-title">炒股养家执行工件</span>
            </div>

            <section class="fac-beijing-card fac-beijing-card--embedded fac-qiao-card">
              <div class="fac-beijing-card__body">
                <div class="fac-beijing-card__gate">
                  <span v-if="jiaExecution.emotionCycle?.stage" class="fac-beijing-gate-chip fac-beijing-gate-chip--subtle">
                    情绪阶段 {{ jiaExecution.emotionCycle.stage }}
                  </span>
                  <span v-if="jiaExecution.emotionCycle?.status" class="fac-beijing-gate-chip fac-beijing-gate-chip--anchor">
                    执行状态 {{ jiaExecution.emotionCycle.status }}
                  </span>
                  <span v-if="jiaExecution.timeAnchor?.phase" class="fac-beijing-gate-chip fac-beijing-gate-chip--anchor">
                    时间锚点 {{ jiaExecution.timeAnchor.phase }}
                  </span>
                  <span v-if="jiaExecution.mainTheme?.name" class="fac-beijing-gate-chip fac-beijing-gate-chip--subtle">
                    主线 {{ jiaExecution.mainTheme.name }}
                  </span>
                  <span v-if="jiaExecution.mainLeader?.name" class="fac-beijing-gate-chip fac-beijing-gate-chip--subtle">
                    龙头 {{ jiaExecution.mainLeader.name }}
                  </span>
                </div>

                <div class="fac-beijing-card__stats">
                  <div class="fac-beijing-stat">
                    <span class="fac-beijing-stat__label">今日涨停池</span>
                    <span class="fac-beijing-stat__value">{{ jiaExecution.stats?.todayLimitUps ?? 0 }}</span>
                  </div>
                  <div class="fac-beijing-stat">
                    <span class="fac-beijing-stat__label">龙头样本</span>
                    <span class="fac-beijing-stat__value">{{ jiaExecution.stats?.leaderCount ?? 0 }}</span>
                  </div>
                  <div class="fac-beijing-stat">
                    <span class="fac-beijing-stat__label">可交易候选</span>
                    <span class="fac-beijing-stat__value">{{ jiaExecution.stats?.actionableCount ?? 0 }}</span>
                  </div>
                  <div class="fac-beijing-stat">
                    <span class="fac-beijing-stat__label">真回封命中</span>
                    <span class="fac-beijing-stat__value">{{ jiaExecution.stats?.trueSealCount ?? 0 }}</span>
                  </div>
                </div>

                <div v-if="jiaExecution.strategyPanels" class="fac-beijing-panels">
                  <section v-if="jiaExecution.strategyPanels.timeAnchor?.phase" class="fac-beijing-panel">
                    <div class="fac-beijing-panel__head">
                      <span class="mso">schedule</span>
                      <h3 class="fac-beijing-panel__title">时间锚定</h3>
                    </div>
                    <article class="fac-beijing-panel__card fac-beijing-panel__card--anchor">
                      <div class="fac-beijing-panel__card-top">
                        <span class="fac-beijing-panel__pill fac-beijing-panel__pill--anchor">{{ jiaExecution.strategyPanels.timeAnchor.phase }}</span>
                        <span class="fac-beijing-panel__count">{{ jiaExecution.strategyPanels.timeAnchor.executionFocus }}</span>
                      </div>
                      <p class="fac-beijing-panel__desc">{{ jiaExecution.strategyPanels.timeAnchor.window }}</p>
                      <p class="fac-beijing-panel__desc">{{ jiaExecution.strategyPanels.timeAnchor.summary }}</p>
                      <div v-if="jiaExecution.strategyPanels.timeAnchor.rules?.length" class="fac-beijing-panel__tags">
                        <span
                          v-for="(rule, idx) in jiaExecution.strategyPanels.timeAnchor.rules"
                          :key="`jia-anchor-rule-${idx}`"
                          class="fac-beijing-panel__tag fac-beijing-panel__tag--anchor"
                        >{{ rule }}</span>
                      </div>
                    </article>
                  </section>

                  <section v-if="jiaExecution.strategyPanels.emotionStage?.stage" class="fac-beijing-panel">
                    <div class="fac-beijing-panel__head">
                      <span class="mso">insights</span>
                      <h3 class="fac-beijing-panel__title">情绪阶段</h3>
                    </div>
                    <article class="fac-beijing-panel__card">
                      <div class="fac-beijing-panel__card-top">
                        <span class="fac-beijing-panel__pill">{{ jiaExecution.strategyPanels.emotionStage.stage }}</span>
                        <span class="fac-beijing-panel__count">{{ jiaExecution.strategyPanels.emotionStage.positionCap }}</span>
                      </div>
                      <p class="fac-beijing-panel__desc">{{ jiaExecution.strategyPanels.emotionStage.summary }}</p>
                      <div v-if="jiaExecution.strategyPanels.emotionStage.reasons?.length" class="fac-beijing-step__lines">
                        <p
                          v-for="(line, idx) in jiaExecution.strategyPanels.emotionStage.reasons"
                          :key="`jia-emotion-${idx}`"
                          class="fac-beijing-step__line"
                        >{{ line }}</p>
                      </div>
                    </article>
                  </section>

                  <section v-if="jiaExecution.strategyPanels.mainFlow" class="fac-beijing-panel">
                    <div class="fac-beijing-panel__head">
                      <span class="mso">flare</span>
                      <h3 class="fac-beijing-panel__title">主流题材</h3>
                    </div>
                    <article class="fac-beijing-panel__card">
                      <div class="fac-beijing-panel__card-top">
                        <span class="fac-beijing-panel__pill">{{ jiaExecution.strategyPanels.mainFlow.mainTheme }}</span>
                        <span class="fac-beijing-panel__count">{{ jiaExecution.strategyPanels.mainFlow.leader }}</span>
                      </div>
                      <p class="fac-beijing-panel__desc">{{ jiaExecution.strategyPanels.mainFlow.summary }}</p>
                      <div class="fac-beijing-panel__tags">
                        <span class="fac-beijing-panel__tag">次主线 {{ jiaExecution.strategyPanels.mainFlow.backupTheme }}</span>
                        <span class="fac-beijing-panel__tag">龙头 {{ jiaExecution.strategyPanels.mainFlow.leader }}</span>
                      </div>
                    </article>
                  </section>

                  <section v-if="jiaExecution.strategyPanels.leaderStructure?.length" class="fac-beijing-panel">
                    <div class="fac-beijing-panel__head">
                      <span class="mso">hub</span>
                      <h3 class="fac-beijing-panel__title">龙头结构</h3>
                    </div>
                    <div class="fac-beijing-panel__grid">
                      <article
                        v-for="item in jiaExecution.strategyPanels.leaderStructure"
                        :key="`jia-leader-structure-${item.type}`"
                        class="fac-beijing-panel__card"
                      >
                        <div class="fac-beijing-panel__card-top">
                          <span class="fac-beijing-panel__pill">{{ item.type }}</span>
                          <span class="fac-beijing-panel__count">{{ item.count }}</span>
                        </div>
                        <p class="fac-beijing-panel__desc">{{ item.description }}</p>
                      </article>
                    </div>
                  </section>

                  <section v-if="jiaExecution.strategyPanels.buyPointPlaybook?.length" class="fac-beijing-panel">
                    <div class="fac-beijing-panel__head">
                      <span class="mso">touch_app</span>
                      <h3 class="fac-beijing-panel__title">三类买点</h3>
                    </div>
                    <div class="fac-beijing-panel__grid">
                      <article
                        v-for="item in jiaExecution.strategyPanels.buyPointPlaybook"
                        :key="`jia-buy-point-${item.type}`"
                        class="fac-beijing-panel__card"
                      >
                        <div class="fac-beijing-panel__card-top">
                          <span class="fac-beijing-panel__pill">{{ item.type }}</span>
                          <span class="fac-beijing-panel__count">{{ item.count }}</span>
                        </div>
                        <p class="fac-beijing-panel__desc">{{ item.description }}</p>
                      </article>
                    </div>
                  </section>

                  <section v-if="jiaExecution.strategyPanels.sealVerdictHits?.length" class="fac-beijing-panel">
                    <div class="fac-beijing-panel__head">
                      <span class="mso">verified</span>
                      <h3 class="fac-beijing-panel__title">回封真假</h3>
                    </div>
                    <div class="fac-beijing-panel__grid">
                      <article
                        v-for="item in jiaExecution.strategyPanels.sealVerdictHits"
                        :key="`jia-seal-${item.type}`"
                        class="fac-beijing-panel__card"
                      >
                        <div class="fac-beijing-panel__card-top">
                          <span class="fac-beijing-panel__pill">{{ item.type }}</span>
                          <span class="fac-beijing-panel__count">{{ item.count }}</span>
                        </div>
                        <p class="fac-beijing-panel__desc">{{ item.description }}</p>
                      </article>
                    </div>
                  </section>

                  <section v-if="jiaExecution.strategyPanels.positionRules?.length" class="fac-beijing-panel">
                    <div class="fac-beijing-panel__head">
                      <span class="mso">account_balance_wallet</span>
                      <h3 class="fac-beijing-panel__title">仓位规则</h3>
                    </div>
                    <div class="fac-beijing-panel__grid">
                      <article
                        v-for="item in jiaExecution.strategyPanels.positionRules"
                        :key="`jia-position-${item.stage}`"
                        class="fac-beijing-panel__card"
                      >
                        <div class="fac-beijing-panel__card-top">
                          <span class="fac-beijing-panel__pill" :class="{ 'fac-beijing-panel__pill--anchor': item.active }">{{ item.stage }}</span>
                          <span class="fac-beijing-panel__count">{{ item.range }}</span>
                        </div>
                        <p class="fac-beijing-panel__desc">{{ item.active ? '当前阶段对应的建议总仓位。' : '该阶段的标准仓位上限。' }}</p>
                      </article>
                    </div>
                  </section>

                  <section v-if="jiaExecution.strategyPanels.rotationSignal?.summary" class="fac-beijing-panel">
                    <div class="fac-beijing-panel__head">
                      <span class="mso">sync_alt</span>
                      <h3 class="fac-beijing-panel__title">龙头切换</h3>
                    </div>
                    <article class="fac-beijing-panel__card">
                      <div class="fac-beijing-panel__card-top">
                        <span class="fac-beijing-panel__pill fac-beijing-panel__pill--rule">{{ jiaExecution.strategyPanels.rotationSignal.status }}</span>
                        <span class="fac-beijing-panel__count">{{ jiaExecution.strategyPanels.rotationSignal.newLeader }}</span>
                      </div>
                      <p class="fac-beijing-panel__desc">{{ jiaExecution.strategyPanels.rotationSignal.summary }}</p>
                      <div class="fac-beijing-panel__tags">
                        <span class="fac-beijing-panel__tag">旧龙头 {{ jiaExecution.strategyPanels.rotationSignal.oldLeader }}</span>
                        <span class="fac-beijing-panel__tag">预备方向 {{ jiaExecution.strategyPanels.rotationSignal.newLeader }}</span>
                      </div>
                    </article>
                  </section>

                  <section v-if="jiaExecution.strategyPanels.labelHits?.length" class="fac-beijing-panel">
                    <div class="fac-beijing-panel__head">
                      <span class="mso">sell</span>
                      <h3 class="fac-beijing-panel__title">标签命中</h3>
                    </div>
                    <div class="fac-beijing-panel__grid">
                      <article
                        v-for="item in jiaExecution.strategyPanels.labelHits"
                        :key="`jia-label-hit-${item.label}`"
                        class="fac-beijing-panel__card"
                      >
                        <div class="fac-beijing-panel__card-top">
                          <span class="fac-beijing-panel__pill">{{ item.label }}</span>
                          <span class="fac-beijing-panel__count">{{ item.count }}</span>
                        </div>
                      </article>
                    </div>
                  </section>

                  <section v-if="jiaExecution.strategyPanels.dailyRuleHits?.length" class="fac-beijing-panel">
                    <div class="fac-beijing-panel__head">
                      <span class="mso">task_alt</span>
                      <h3 class="fac-beijing-panel__title">当日规则命中</h3>
                    </div>
                    <div class="fac-beijing-panel__grid">
                      <article
                        v-for="item in jiaExecution.strategyPanels.dailyRuleHits"
                        :key="`jia-rule-hit-${item.title}`"
                        class="fac-beijing-panel__card"
                      >
                        <div class="fac-beijing-panel__card-top">
                          <span class="fac-beijing-panel__pill fac-beijing-panel__pill--rule">{{ item.title }}</span>
                          <span class="fac-beijing-panel__count">{{ item.status }}</span>
                        </div>
                        <p class="fac-beijing-panel__desc">{{ item.detail }}</p>
                      </article>
                    </div>
                  </section>
                </div>

                <div v-if="jiaExecution.stepOutputs?.length" class="fac-beijing-card__steps">
                  <article
                    v-for="step in jiaExecution.stepOutputs"
                    :key="`jia-${step.step}-${step.title}`"
                    class="fac-beijing-step"
                  >
                    <div class="fac-beijing-step__head">
                      <span class="fac-beijing-step__num">步骤 {{ step.step }}</span>
                      <div class="fac-beijing-step__copy">
                        <h3 class="fac-beijing-step__title">{{ step.title || `步骤 ${step.step}` }}</h3>
                        <p class="fac-beijing-step__summary">{{ step.summary || '暂无执行摘要' }}</p>
                      </div>
                    </div>
                    <div v-if="step.frameworkLines?.length" class="fac-beijing-step__section">
                      <div class="fac-beijing-step__section-label">方法论</div>
                      <div class="fac-beijing-step__lines fac-beijing-step__lines--method">
                        <p
                          v-for="(line, idx) in step.frameworkLines"
                          :key="`jia-${step.step}-framework-${idx}`"
                          class="fac-beijing-step__line fac-beijing-step__line--method"
                        >{{ line }}</p>
                      </div>
                    </div>
                    <div v-if="step.lines?.length" class="fac-beijing-step__lines">
                      <div class="fac-beijing-step__section-label">当日判断</div>
                      <p
                        v-for="(line, idx) in step.lines"
                        :key="`jia-${step.step}-${idx}`"
                        class="fac-beijing-step__line"
                      >{{ line }}</p>
                    </div>
                  </article>
                </div>

                <div v-if="jiaExecution.leaderCandidates?.length" class="fac-beijing-card__section">
                  <div class="fac-beijing-card__section-head">龙头结构样本</div>
                  <div class="fac-beijing-card__list">
                    <article
                      v-for="item in jiaExecution.leaderCandidates"
                      :key="`jia-leader-candidate-${item.code}`"
                      class="fac-beijing-candidate"
                    >
                      <div class="fac-beijing-candidate__top">
                        <div class="fac-beijing-candidate__name">
                          {{ item.name }}
                          <span class="fac-beijing-candidate__code">{{ item.code }}</span>
                        </div>
                        <div class="fac-beijing-candidate__chips">
                          <span v-if="item.leaderType" class="fac-beijing-candidate__chip fac-beijing-candidate__chip--selection">{{ item.leaderType }}</span>
                          <span v-if="item.selectionType" class="fac-beijing-candidate__chip fac-beijing-candidate__chip--selection">{{ item.selectionType }}</span>
                          <span v-if="item.reboundSealVerdict" class="fac-beijing-candidate__chip fac-beijing-candidate__chip--action">{{ item.reboundSealVerdict }}</span>
                          <span v-if="item.sector" class="fac-beijing-candidate__chip">{{ item.sector }}</span>
                        </div>
                      </div>
                      <p class="fac-beijing-candidate__reason">{{ item.reason || '暂无龙头结构说明' }}</p>
                      <div class="fac-beijing-candidate__meta">
                        <span v-if="item.consecutiveDays">连板 {{ item.consecutiveDays }}</span>
                        <span v-if="item.firstSealTime">首封 {{ item.firstSealTime }}</span>
                        <span v-if="item.positionRatio">{{ item.positionRatio }}</span>
                        <span v-if="item.changePct || item.changePct === 0">涨幅 {{ normalizePctValue(item.changePct, item) }}%</span>
                        <span v-if="item.score">评分 {{ item.score }}</span>
                      </div>
                    </article>
                  </div>
                </div>

                <div v-if="jiaExecution.actionableCandidates?.length" class="fac-beijing-card__section">
                  <div class="fac-beijing-card__section-head">情绪龙头可交易池</div>
                  <div class="fac-beijing-card__list">
                    <article
                      v-for="item in jiaExecution.actionableCandidates"
                      :key="`jia-actionable-${item.code}`"
                      class="fac-beijing-candidate"
                    >
                      <div class="fac-beijing-candidate__top">
                        <div class="fac-beijing-candidate__name">
                          {{ item.name }}
                          <span class="fac-beijing-candidate__code">{{ item.code }}</span>
                        </div>
                        <div class="fac-beijing-candidate__chips">
                          <span v-if="item.selectionType" class="fac-beijing-candidate__chip fac-beijing-candidate__chip--selection">{{ item.selectionType }}</span>
                          <span v-if="item.leaderType" class="fac-beijing-candidate__chip fac-beijing-candidate__chip--selection">{{ item.leaderType }}</span>
                          <span v-if="item.tradeStatus" class="fac-beijing-candidate__chip fac-beijing-candidate__chip--status">{{ item.tradeStatus }}</span>
                          <span v-if="item.buyPointType" class="fac-beijing-candidate__chip fac-beijing-candidate__chip--action">{{ item.buyPointType }}</span>
                          <span
                            v-for="(label, idx) in (item.labels || []).slice(0, 3)"
                            :key="`${item.code}-jia-actionable-label-${idx}`"
                            class="fac-beijing-candidate__chip fac-beijing-candidate__chip--label"
                          >{{ label }}</span>
                        </div>
                      </div>
                      <p class="fac-beijing-candidate__reason">{{ item.classificationReason || item.reason || '暂无入场说明' }}</p>
                      <div class="fac-beijing-candidate__meta">
                        <span v-if="item.entryTrigger">触发 {{ item.entryTrigger }}</span>
                        <span v-if="item.reboundSealVerdict">{{ item.reboundSealVerdict }}</span>
                        <span v-if="item.positionRatio">{{ item.positionRatio }}</span>
                        <span v-if="item.changePct || item.changePct === 0">涨幅 {{ normalizePctValue(item.changePct, item) }}%</span>
                        <span v-if="item.score">评分 {{ item.score }}</span>
                      </div>
                      <div v-if="item.matchedRules?.length" class="fac-beijing-rule-list">
                        <article
                          v-for="(rule, idx) in item.matchedRules.slice(0, 3)"
                          :key="`${item.code}-jia-rule-${idx}`"
                          class="fac-beijing-rule-card"
                        >
                          <div class="fac-beijing-rule-card__title">{{ rule.title }}</div>
                          <div class="fac-beijing-rule-card__detail">{{ rule.detail }}</div>
                        </article>
                      </div>
                    </article>
                  </div>
                </div>
              </div>
            </section>
          </div>

          <div v-if="beijingExecution" class="fac-report-card__module">
            <div class="fac-report-card__module-head">
              <span class="mso">dashboard</span>
              <span class="fac-report-card__module-title">北京炒家执行工件</span>
            </div>

            <section class="fac-beijing-card fac-beijing-card--embedded">
              <div class="fac-beijing-card__body">
                <div v-if="beijingExecution.marketGate?.status" class="fac-beijing-card__gate">
                  <span class="fac-beijing-gate-chip" :class="`fac-beijing-gate-chip--${beijingExecution.marketGate.status}`">
                    市场闸门 {{ beijingExecution.marketGate.status }}
                  </span>
                  <span v-if="beijingExecution.marketGate.positionCap" class="fac-beijing-gate-chip fac-beijing-gate-chip--subtle">
                    仓位上限 {{ beijingExecution.marketGate.positionCap }}
                  </span>
                  <span v-if="beijingExecution.scanIsStale" class="fac-beijing-gate-chip fac-beijing-gate-chip--warn">
                    ⚠ 今日未扫描
                  </span>
                  <span v-if="beijingExecution.timeAnchor?.phase" class="fac-beijing-gate-chip fac-beijing-gate-chip--anchor">
                    时间锚点 {{ beijingExecution.timeAnchor.phase }}
                  </span>
                </div>

                <div class="fac-beijing-card__stats">
                  <div class="fac-beijing-stat">
                    <span class="fac-beijing-stat__label">今日涨停池</span>
                    <span class="fac-beijing-stat__value">{{ beijingExecution.stats?.todayLimitUps ?? 0 }}</span>
                  </div>
                  <div class="fac-beijing-stat">
                    <span class="fac-beijing-stat__label">三有达标</span>
                    <span class="fac-beijing-stat__value">{{ beijingExecution.stats?.qualifiedCount ?? 0 }}</span>
                  </div>
                  <div class="fac-beijing-stat">
                    <span class="fac-beijing-stat__label">可买候选</span>
                    <span class="fac-beijing-stat__value">{{ beijingExecution.stats?.actionableCount ?? beijingExecution.stats?.recommendedCount ?? 0 }}</span>
                  </div>
                  <div class="fac-beijing-stat">
                    <span class="fac-beijing-stat__label">半小时换手</span>
                    <span class="fac-beijing-stat__value">{{ beijingExecution.stats?.minuteConfirmedCount ?? 0 }}</span>
                  </div>
                </div>

                <div v-if="beijingExecution.boardTypeSummary?.length" class="fac-beijing-card__summary">
                  <span
                    v-for="item in beijingExecution.boardTypeSummary"
                    :key="item.type"
                    class="fac-beijing-summary-chip"
                  >
                    {{ item.type }} {{ item.count }}只
                  </span>
                </div>

                <div v-if="beijingExecution.strategyPanels" class="fac-beijing-panels">
                  <section v-if="beijingExecution.strategyPanels.timeAnchor?.phase" class="fac-beijing-panel">
                    <div class="fac-beijing-panel__head">
                      <span class="mso">schedule</span>
                      <h3 class="fac-beijing-panel__title">时间锚定</h3>
                    </div>
                    <article class="fac-beijing-panel__card fac-beijing-panel__card--anchor">
                      <div class="fac-beijing-panel__card-top">
                        <span class="fac-beijing-panel__pill fac-beijing-panel__pill--anchor">{{ beijingExecution.strategyPanels.timeAnchor.phase }}</span>
                        <span class="fac-beijing-panel__count">{{ beijingExecution.strategyPanels.timeAnchor.executionFocus }}</span>
                      </div>
                      <p class="fac-beijing-panel__desc">{{ beijingExecution.strategyPanels.timeAnchor.window }}</p>
                      <p class="fac-beijing-panel__desc">{{ beijingExecution.strategyPanels.timeAnchor.summary }}</p>
                      <div v-if="beijingExecution.strategyPanels.timeAnchor.rules?.length" class="fac-beijing-panel__tags">
                        <span
                          v-for="(rule, idx) in beijingExecution.strategyPanels.timeAnchor.rules"
                          :key="`anchor-rule-${idx}`"
                          class="fac-beijing-panel__tag fac-beijing-panel__tag--anchor"
                        >
                          {{ rule }}
                        </span>
                      </div>
                    </article>
                  </section>

                  <section v-if="beijingExecution.strategyPanels.selectionPath?.length" class="fac-beijing-panel">
                    <div class="fac-beijing-panel__head">
                      <span class="mso">schema</span>
                      <h3 class="fac-beijing-panel__title">选股路径</h3>
                    </div>
                    <div class="fac-beijing-panel__grid fac-beijing-panel__grid--selection">
                      <article
                        v-for="item in beijingExecution.strategyPanels.selectionPath"
                        :key="`selection-${item.type}`"
                        class="fac-beijing-panel__card"
                      >
                        <div class="fac-beijing-panel__card-top">
                          <span class="fac-beijing-panel__pill">{{ item.type }}</span>
                          <span class="fac-beijing-panel__count">{{ item.count }}只</span>
                        </div>
                        <p class="fac-beijing-panel__desc">{{ item.description }}</p>
                      </article>
                    </div>
                  </section>

                  <section v-if="beijingExecution.strategyPanels.boardPlaybook?.length" class="fac-beijing-panel">
                    <div class="fac-beijing-panel__head">
                      <span class="mso">style</span>
                      <h3 class="fac-beijing-panel__title">六类板型</h3>
                    </div>
                    <div class="fac-beijing-panel__grid">
                      <article
                        v-for="item in beijingExecution.strategyPanels.boardPlaybook"
                        :key="`board-${item.type}`"
                        class="fac-beijing-panel__card"
                      >
                        <div class="fac-beijing-panel__card-top">
                          <span class="fac-beijing-panel__pill fac-beijing-panel__pill--board">{{ item.type }}</span>
                          <span class="fac-beijing-panel__count">{{ item.count }}只</span>
                        </div>
                        <p class="fac-beijing-panel__desc">{{ item.description }}</p>
                      </article>
                    </div>
                  </section>

                  <section v-if="beijingExecution.strategyPanels.labelHits?.length" class="fac-beijing-panel">
                    <div class="fac-beijing-panel__head">
                      <span class="mso">sell</span>
                      <h3 class="fac-beijing-panel__title">标签命中</h3>
                    </div>
                    <div class="fac-beijing-panel__tags">
                      <span
                        v-for="item in beijingExecution.strategyPanels.labelHits"
                        :key="`label-hit-${item.label}`"
                        class="fac-beijing-panel__tag"
                      >
                        {{ item.label }} · {{ item.count }}
                      </span>
                    </div>
                  </section>

                  <section v-if="beijingExecution.strategyPanels.dailyRuleHits?.length" class="fac-beijing-panel">
                    <div class="fac-beijing-panel__head">
                      <span class="mso">checklist</span>
                      <h3 class="fac-beijing-panel__title">当日规则命中</h3>
                    </div>
                    <div class="fac-beijing-panel__grid">
                      <article
                        v-for="item in beijingExecution.strategyPanels.dailyRuleHits"
                        :key="`rule-hit-${item.title}`"
                        class="fac-beijing-panel__card"
                      >
                        <div class="fac-beijing-panel__card-top">
                          <span class="fac-beijing-panel__pill fac-beijing-panel__pill--rule">{{ item.title }}</span>
                          <span class="fac-beijing-panel__count">{{ item.status }}</span>
                        </div>
                        <p class="fac-beijing-panel__desc">{{ item.detail }}</p>
                      </article>
                    </div>
                  </section>
                </div>

                <div v-if="beijingExecution.stepOutputs?.length" class="fac-beijing-card__steps">
                  <article
                    v-for="step in beijingExecution.stepOutputs"
                    :key="`${step.step}-${step.title}`"
                    class="fac-beijing-step"
                  >
                    <div class="fac-beijing-step__head">
                      <span class="fac-beijing-step__num">步骤 {{ step.step }}</span>
                      <div class="fac-beijing-step__copy">
                        <h3 class="fac-beijing-step__title">{{ step.title || `步骤 ${step.step}` }}</h3>
                        <p class="fac-beijing-step__summary">{{ step.summary || '暂无执行摘要' }}</p>
                      </div>
                    </div>
                    <div v-if="step.frameworkLines?.length" class="fac-beijing-step__section">
                      <div class="fac-beijing-step__section-label">方法论</div>
                      <div class="fac-beijing-step__lines fac-beijing-step__lines--method">
                        <p
                          v-for="(line, idx) in step.frameworkLines"
                          :key="`${step.step}-framework-${idx}`"
                          class="fac-beijing-step__line fac-beijing-step__line--method"
                        >
                          {{ line }}
                        </p>
                      </div>
                    </div>
                    <div v-if="step.lines?.length" class="fac-beijing-step__lines">
                      <div class="fac-beijing-step__section-label">当日判断</div>
                      <p
                        v-for="(line, idx) in step.lines"
                        :key="`${step.step}-${idx}`"
                        class="fac-beijing-step__line"
                      >
                        {{ line }}
                      </p>
                    </div>
                  </article>
                </div>

                <div v-if="beijingExecution.actionableCandidates?.length" class="fac-beijing-card__section">
                  <div class="fac-beijing-card__section-head">盘中可买候选池</div>
                  <div class="fac-beijing-card__list">
                    <article
                      v-for="item in beijingExecution.actionableCandidates"
                      :key="`actionable-${item.code}`"
                      class="fac-beijing-candidate"
                    >
                      <div class="fac-beijing-candidate__top">
                        <div class="fac-beijing-candidate__name">
                          {{ item.name }}
                          <span class="fac-beijing-candidate__code">{{ item.code }}</span>
                        </div>
                        <div class="fac-beijing-candidate__chips">
                          <span v-if="item.selectionType" class="fac-beijing-candidate__chip fac-beijing-candidate__chip--selection">{{ item.selectionType }}</span>
                          <span v-if="item.tradeStatus" class="fac-beijing-candidate__chip fac-beijing-candidate__chip--status">{{ item.tradeStatus }}</span>
                          <span v-if="item.entryModel" class="fac-beijing-candidate__chip fac-beijing-candidate__chip--action">{{ item.entryModel }}</span>
                          <span v-if="item.entryPlan" class="fac-beijing-candidate__chip">{{ item.entryPlan }}</span>
                          <span v-if="item.actionableNow" class="fac-beijing-candidate__chip fac-beijing-candidate__chip--action">当前可执行</span>
                          <span
                            v-for="(label, idx) in (item.labels || []).slice(0, 3)"
                            :key="`${item.code}-actionable-label-${idx}`"
                            class="fac-beijing-candidate__chip fac-beijing-candidate__chip--label"
                          >{{ label }}</span>
                        </div>
                      </div>
                      <p class="fac-beijing-candidate__reason">{{ item.classificationReason || item.reason || '暂无盘中执行说明' }}</p>
                      <div class="fac-beijing-candidate__meta">
                        <span v-if="item.entryTrigger">触发 {{ item.entryTrigger }}</span>
                        <span v-if="item.positionRatio">{{ item.positionRatio }}</span>
                        <span v-if="item.changePct || item.changePct === 0">涨幅 {{ normalizePctValue(item.changePct, item) }}%</span>
                        <span v-if="item.score">评分 {{ item.score }}</span>
                        <span v-if="item.timeAnchorPhase">{{ item.timeAnchorPhase }}</span>
                      </div>
                      <div v-if="item.matchedRules?.length" class="fac-beijing-rule-list">
                        <article
                          v-for="(rule, idx) in item.matchedRules.slice(0, 3)"
                          :key="`${item.code}-rule-${idx}`"
                          class="fac-beijing-rule-card"
                        >
                          <div class="fac-beijing-rule-card__title">{{ rule.title }}</div>
                          <div class="fac-beijing-rule-card__detail">{{ rule.detail }}</div>
                        </article>
                      </div>
                    </article>
                  </div>
                </div>

                <div v-if="beijingExecution.boardCandidates?.length" class="fac-beijing-card__list">
                  <div class="fac-beijing-card__section-head">板池样本</div>
                  <article
                    v-for="item in beijingExecution.boardCandidates"
                    :key="item.code"
                    class="fac-beijing-candidate"
                  >
                    <div class="fac-beijing-candidate__top">
                      <div class="fac-beijing-candidate__name">
                        {{ item.name }}
                        <span class="fac-beijing-candidate__code">{{ item.code }}</span>
                      </div>
                      <div class="fac-beijing-candidate__chips">
                        <span v-if="item.boardType" class="fac-beijing-candidate__chip fac-beijing-candidate__chip--board">{{ item.boardType }}</span>
                        <span v-if="item.selectionType" class="fac-beijing-candidate__chip fac-beijing-candidate__chip--selection">{{ item.selectionType }}</span>
                        <span v-if="item.buyMethod" class="fac-beijing-candidate__chip">{{ item.buyMethod }}</span>
                        <span v-if="item.minuteTurnoverLabel && item.minuteTurnoverLabel !== '待观察'" class="fac-beijing-candidate__chip fac-beijing-candidate__chip--label">{{ item.minuteTurnoverLabel }}</span>
                        <span v-if="item.auctionStrength && item.auctionStrength !== '待观察'" class="fac-beijing-candidate__chip">{{ item.auctionStrength }}</span>
                        <span v-if="item.teammateStrength && item.teammateStrength !== '待观察'" class="fac-beijing-candidate__chip">{{ item.teammateStrength }}</span>
                        <span v-if="item.threeHaveSummary" class="fac-beijing-candidate__chip fac-beijing-candidate__chip--pass">{{ item.threeHaveSummary }}</span>
                        <span
                          v-for="(label, idx) in (item.labels || []).slice(0, 3)"
                          :key="`${item.code}-label-${idx}`"
                          class="fac-beijing-candidate__chip fac-beijing-candidate__chip--label"
                        >{{ label }}</span>
                      </div>
                    </div>
                    <p class="fac-beijing-candidate__reason">{{ item.classificationReason || item.meta || '暂无分类说明' }}</p>
                    <div class="fac-beijing-candidate__meta">
                      <span v-if="item.firstSealTime">首封 {{ item.firstSealTime }}</span>
                      <span v-if="item.lastSealTime">末封 {{ item.lastSealTime }}</span>
                      <span v-if="item.brokenBoardCount !== undefined && item.brokenBoardCount !== null">炸板 {{ item.brokenBoardCount }} 次</span>
                      <span v-if="item.minuteLongestStreak">横盘 {{ item.minuteLongestStreak }} 分</span>
                      <span v-if="item.auctionStrength">竞价 {{ item.auctionStrength }}</span>
                      <span v-if="item.teammateStrength">队友 {{ item.teammateStrength }}</span>
                      <span v-if="item.positionRatio">{{ item.positionRatio }}</span>
                    </div>
                  </article>
                </div>
              </div>
            </section>
          </div>

          <div v-if="(beijingExecution || qiaoExecution || jiaExecution) && liveReportLines.length" class="fac-report-card__divider" />

          <div
            v-for="(line, i) in liveReportLines"
            :key="i"
            class="fac-report-line"
            :class="'fac-report-line--' + line.type"
          >{{ line.text }}</div>
        </div>
      </section>

      <!-- ── 分析结果（完成后展示）──────────────────────── -->
      <template v-if="isDone && result">

        <!-- 共识标尺 -->
        <section v-if="structured" class="fac-consensus-card">
          <div class="fac-consensus__gauge">
            <svg viewBox="0 0 96 96" class="fac-consensus__svg">
                <circle cx="48" cy="48" r="40" fill="none" stroke-width="8" stroke="var(--track)" />
                <circle
                  cx="48" cy="48" r="40"
                  fill="none"
                  stroke-width="8"
                  stroke-linecap="round"
                  :stroke="stanceColor"
                  :stroke-dasharray="gaugeCirc"
                  :stroke-dashoffset="gaugeOffset"
                  transform="rotate(-90 48 48)"
                class="fac-consensus__arc"
                />
              <text x="48" y="44" text-anchor="middle" class="fac-consensus__num">{{ confidence }}</text>
              <text x="48" y="58" text-anchor="middle" class="fac-consensus__unit">%</text>
              </svg>
            </div>
          <div class="fac-consensus__right">
            <div class="fac-consensus__stance-row">
              <span class="fac-stance-tag" :class="'fac-stance-tag--' + (structured?.stance || 'neutral')">
                {{ stanceLabel }}
              </span>
              <span class="fac-consensus__conf-label">信心指数 {{ confidence }}%</span>
            </div>
            <p class="fac-consensus__comm">{{ structured?.marketCommentary || '' }}</p>
            <p class="fac-consensus__advice"><strong>策略建议：</strong>{{ structured?.positionAdvice || '' }}</p>
            <div v-if="structured?.riskWarning" class="fac-consensus__warning">
              <span class="mso">warning</span>
              {{ structured.riskWarning }}
            </div>
          </div>
        </section>

        <!-- 推荐股票（对齐设计图） -->
        <section v-if="recommendedStocks.length" class="fac-recs-card">
          <h2 class="fac-recs__title">
            <span class="mso">star</span>
            推荐结果
          </h2>
          <div>
            <div
              v-for="(s, i) in recommendedStocks"
              :key="i + '-' + (s.routeCode || s.code)"
              class="fac-rec-item"
            >
              <!-- 顶部：名称 + 评级 + 趋势标签 -->
              <div class="fac-rec-item__top">
                <div class="fac-rec-item__name-group">
                  <div class="fac-rec-item__name">
                    {{ s.name }}
                    <span class="fac-rec-item__code-badge">{{ s.displayCode }}</span>
                    <span v-if="s.grade" class="fac-rec-item__grade-badge" :class="'fac-rec-item__grade-badge--' + s.grade.toLowerCase()">
                      {{ s.grade }}
                    </span>
                    </div>
                  <!-- 现价 + 涨跌幅 -->
                  <div v-if="s.price || s.chg_pct !== 0" class="fac-rec-item__price-row">
                    <span v-if="s.price" class="fac-rec-item__price">{{ s.price }}</span>
                    <span v-if="s.chg_pct !== 0" class="fac-rec-item__chg" :class="s.chg_pct >= 0 ? 'fac-rec-item__chg--up' : 'fac-rec-item__chg--down'">
                      {{ s.chg_pct >= 0 ? '+' : '' }}{{ s.chg_pct }}%
                    </span>
                    <span v-if="s.score > 0" class="fac-rec-item__score-chip">
                      <span class="mso">star</span>
                      {{ s.score }}分
                    </span>
                  </div>
                </div>
                <div class="fac-rec-item__badges">
                <span v-if="s.trendTag || s.adviseType" class="fac-rec-item__trend-chip">
                  <span class="mso">{{ s.trendTag.includes('高动能') || s.adviseType.includes('打板') ? 'bolt' : s.trendTag.includes('强势') || s.trendTag.includes('突破') ? 'trending_up' : 'favorite' }}</span>
                  {{ s.trendTag || s.adviseType }}
                </span>
                <span v-if="s.boardType" class="fac-rec-item__board-chip">{{ s.boardType }}</span>
                <span v-if="s.buyPointType" class="fac-rec-item__board-chip">{{ s.buyPointType }}</span>
                <span v-if="s.tradeStatus" class="fac-rec-item__sector-chip fac-rec-item__sector-chip--status">{{ s.tradeStatus }}</span>
                <span v-if="s.leaderType" class="fac-rec-item__sector-chip fac-rec-item__sector-chip--selection">{{ s.leaderType }}</span>
                <span v-if="s.selectionType" class="fac-rec-item__sector-chip fac-rec-item__sector-chip--selection">{{ s.selectionType }}</span>
                <span v-if="s.themeRole" class="fac-rec-item__sector-chip fac-rec-item__sector-chip--selection">{{ s.themeRole }}</span>
                <span v-if="s.stage" class="fac-rec-item__sector-chip">{{ s.stage }}</span>
                <span v-if="s.sector" class="fac-rec-item__sector-chip">{{ s.sector }}</span>
                <span v-if="s.riskLevel" class="fac-rec-item__risk-chip" :class="'fac-rec-item__risk-chip--' + s.riskLevel">
                  {{ s.riskLevel }}风险
                </span>
                </div>
              </div>

              <!-- 信号标签行 -->
              <div v-if="s.signal" class="fac-rec-item__signals">
                <span
                  v-for="(sig, si) in s.signal.split('/').filter(Boolean)"
                  :key="si"
                  class="fac-rec-item__signal-chip"
                >{{ sig.trim() }}</span>
                <span v-if="s.threeHaveSummary" class="fac-rec-item__signal-chip fac-rec-item__signal-chip--primary">{{ s.threeHaveSummary }}</span>
                <span
                  v-for="(label, li) in (s.labels || []).slice(0, 4)"
                  :key="`${s.routeCode}-label-${li}`"
                  class="fac-rec-item__signal-chip fac-rec-item__signal-chip--muted"
                >{{ label }}</span>
                <span v-if="s.actionableNow" class="fac-rec-item__signal-chip fac-rec-item__signal-chip--primary">当前可执行</span>
                <span v-if="s.emotionFit" class="fac-rec-item__signal-chip fac-rec-item__signal-chip--muted">{{ s.emotionFit }}</span>
                <span v-if="s.maSupportSummary" class="fac-rec-item__signal-chip fac-rec-item__signal-chip--muted">{{ s.maSupportSummary }}</span>
                <span v-if="s.auctionStrength" class="fac-rec-item__signal-chip fac-rec-item__signal-chip--muted">{{ s.auctionStrength }}</span>
                <span v-if="s.teammateStrength" class="fac-rec-item__signal-chip fac-rec-item__signal-chip--muted">{{ s.teammateStrength }}</span>
              </div>

              <!-- 核心指标网格 -->
              <div class="fac-rec-item__metrics">
                <div class="fac-rec-item__metric">
                  <p class="fac-rec-item__metric-label">目标盈利</p>
                  <p class="fac-rec-item__metric-value fac-rec-item__metric-value--up">
                    {{ s.targetProfit || '--' }}
                  </p>
                </div>
                <div class="fac-rec-item__metric">
                  <p class="fac-rec-item__metric-label">硬性防守</p>
                  <p class="fac-rec-item__metric-value fac-rec-item__metric-value--down">
                    {{ s.hardStop || '--' }}
                  </p>
                </div>
                <div class="fac-rec-item__metric">
                  <p class="fac-rec-item__metric-label">合理建仓区间</p>
                  <p class="fac-rec-item__metric-value fac-rec-item__metric-value--range">
                    {{ s.priceRange || '--' }}
                  </p>
                </div>
              </div>

              <!-- 操作信息：仓位 + 持股周期 -->
              <div v-if="s.positionRatio || s.holdPeriod || s.buyMethod" class="fac-rec-item__ops">
                <span v-if="s.positionRatio" class="fac-rec-item__op-chip">
                  <span class="mso">account_balance_wallet</span>
                  {{ s.positionRatio }}
                </span>
                <span v-if="s.tradeStatus" class="fac-rec-item__op-chip">
                  <span class="mso">bolt</span>
                  {{ s.tradeStatus }}
                </span>
                <span v-if="s.entryModel" class="fac-rec-item__op-chip">
                  <span class="mso">track_changes</span>
                  {{ s.entryModel }}
                </span>
                <span v-if="s.buyMethod" class="fac-rec-item__op-chip">
                  <span class="mso">flash_on</span>
                  {{ s.buyMethod }}
                </span>
                <span v-if="s.entryPlan" class="fac-rec-item__op-chip">
                  <span class="mso">touch_app</span>
                  {{ s.entryPlan }}
                </span>
                <span v-if="s.holdPeriod" class="fac-rec-item__op-chip">
                  <span class="mso">schedule</span>
                  {{ s.holdPeriod }}
                </span>
              </div>

              <div v-if="s.entryTrigger" class="fac-rec-item__sell-plan">
                <span class="mso">ads_click</span>
                入场触发：{{ s.entryTrigger }}
              </div>

              <div v-if="s.exitTrigger" class="fac-rec-item__sell-plan">
                <span class="mso">logout</span>
                离场触发：{{ s.exitTrigger }}
              </div>

              <div v-if="s.timeAnchorWindow" class="fac-rec-item__sell-plan">
                <span class="mso">schedule</span>
                时段策略：{{ s.timeAnchorWindow }}
              </div>

              <div v-if="s.nextDaySellPlan" class="fac-rec-item__sell-plan">
                <span class="mso">logout</span>
                次日卖法：{{ s.nextDaySellPlan }}
              </div>

              <div v-if="s.auctionTeammateSummary" class="fac-rec-item__sell-plan">
                <span class="mso">insights</span>
                盘口判断：{{ s.auctionTeammateSummary }}
              </div>

              <div v-if="s.sealVerdictSummary" class="fac-rec-item__sell-plan">
                <span class="mso">verified</span>
                回封判断：{{ s.sealVerdictSummary }}
              </div>

              <div v-if="s.rotationSignal" class="fac-rec-item__sell-plan">
                <span class="mso">sync_alt</span>
                切换信号：{{ s.rotationSignal }}
              </div>

              <div v-if="s.firstSealTime || s.lastSealTime || s.brokenBoardCountText" class="fac-rec-item__board-meta">
                <span v-if="s.firstSealTime" class="fac-rec-item__board-meta-chip">首封 {{ s.firstSealTime }}</span>
                <span v-if="s.lastSealTime" class="fac-rec-item__board-meta-chip">末封 {{ s.lastSealTime }}</span>
                <span v-if="s.brokenBoardCountText" class="fac-rec-item__board-meta-chip">炸板 {{ s.brokenBoardCountText }}</span>
                <span v-if="s.minuteTurnoverLabel" class="fac-rec-item__board-meta-chip">{{ s.minuteTurnoverLabel }}</span>
                <span v-if="s.minuteLongestStreak" class="fac-rec-item__board-meta-chip">横盘 {{ s.minuteLongestStreak }} 分</span>
              </div>

              <div v-if="s.matchedRules?.length" class="fac-rec-item__rules">
                <p class="fac-rec-item__reason-label">
                  <span class="mso">rule</span>
                  命中规则
                </p>
                <div class="fac-rec-item__rule-grid">
                  <article
                    v-for="(rule, ri) in s.matchedRules"
                    :key="`${s.routeCode}-rule-${ri}`"
                    class="fac-rec-item__rule-card"
                  >
                    <div class="fac-rec-item__rule-title">{{ rule.title }}</div>
                    <div class="fac-rec-item__rule-detail">{{ rule.detail }}</div>
                  </article>
                </div>
              </div>

              <!-- 推荐逻辑 -->
              <div class="fac-rec-item__reason">
                <p class="fac-rec-item__reason-label">
                  <span class="mso">lightbulb</span>
                  推荐逻辑
                </p>
                <p class="fac-rec-item__reason-text">{{ s.reason || '暂无详细逻辑说明' }}</p>
              </div>

              <!-- 底部：收藏按钮 -->
              <div class="fac-rec-item__footer">
                <button
                  type="button"
                  class="fac-btn-fav"
                  :class="{ 'fac-btn-fav--on': favAdded[s.routeCode] }"
                  :disabled="favBusy[s.routeCode]"
                  @click="favoriteStock(s)"
                >
                  <span class="mso">{{ favAdded[s.routeCode] ? 'favorite' : 'favorite_border' }}</span>
                  {{ favAdded[s.routeCode] ? '已自选' : '加入自选' }}
                </button>
              </div>
            </div>
          </div>
        </section>

        <!-- 任务拆解 -->
        <section v-if="hasTaskDecomposition" class="fac-decomp-card">
          <div class="fac-decomp-card__head">
            <span class="mso">assignment</span>
            <h2 class="fac-decomp-card__title">任务拆解</h2>
          </div>
          <div class="fac-decomp-card__body">
            <p v-if="taskCoreObjective" class="fac-decomp-card__objective">
              <strong>核心目标：</strong>{{ taskCoreObjective }}
            </p>
            <div
              v-for="(step, idx) in taskDecomposition"
              :key="idx"
              class="fac-decomp-step"
            >
              <div class="fac-decomp-step__header">
                <span class="fac-decomp-step__num">{{ idx + 1 }}</span>
                <span class="fac-decomp-step__title">{{ step.title || step.name || `步骤 ${idx + 1}` }}</span>
              </div>
              <p class="fac-decomp-step__desc">{{ step.description || step.desc || step.content || '' }}</p>
            </div>
          </div>
        </section>
      </template>

    </main>

    <!-- 底部分享栏 -->
    <div v-if="isDone" class="fac-bottom-bar">
      <button type="button" class="fac-btn-share" @click="openShareModal">
        <span class="mso">share</span>
        分享此深度报告
      </button>
    </div>

    <!-- Share Modal -->
    <ShareModal
      :visible="showShareModal"
      :share-data="shareData"
      @close="showShareModal = false"
    />

    <!-- Footer: Risk Disclosure -->
    <footer class="fac-footer">
      <div class="fac-footer__inner">
        <div class="fac-footer__warn">
          <span class="mso">warning</span>
          Risk Disclosure
      </div>
        <p class="fac-footer__text">
          免责声明：本智能体所提供的所有分析仅供参考，不构成任何形式的投资建议。市场有风险，投资需谨慎。AI 智能分析可能存在延迟或算法误差，用户应根据自身风险承受能力独立做出决策。
        </p>
      </div>
    </footer>

    <!-- Prompt Modal -->
    <div v-if="showPromptModal" class="fac-modal-overlay" @click.self="showPromptModal = false">
      <div class="fac-modal">
        <div class="fac-modal__header">
          <h3 class="fac-modal__title">{{ agentName }} - 提示词模板</h3>
          <button type="button" class="fac-modal__close" @click="showPromptModal = false" aria-label="关闭">
            <span class="mso">close</span>
          </button>
        </div>
        <div class="fac-modal__body">
          <div class="fac-modal__section">
            <h4 class="fac-modal__label">System Prompt</h4>
            <pre class="fac-modal__code">{{ realPrompts.systemPrompt || '加载中...' }}</pre>
          </div>
          <div class="fac-modal__section">
            <h4 class="fac-modal__label">User Prompt 模板</h4>
            <pre class="fac-modal__code">{{ realPrompts.userPrompt || '加载中...' }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>

</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { analyzeWithAgent, fetchTodayAnalysis, fetchAgentInfo } from '@/api/agents.js'
import { watchlist } from '@/api/strategy.js'
import TaskProcessCard from './components/TaskProcessCard.vue'
import ShareModal from '@/components/ShareModal.vue'
import { useShare } from '@/composables/useShare.js'

const route = useRoute()
const router = useRouter()

const basePath = computed(() =>
  route.path.startsWith('/strategy/youzi_agents') ? '/strategy/youzi_agents' : '/strategy/agents'
)

const agentId = computed(() => route.params.id || 'jun')
const agentName = computed(() => _nameMap[agentId.value] || agentId.value)
const roleSubtitle = computed(() => _roleMap[agentId.value] || '')
const agentInitial = computed(() => {
  const n = (result.value?.name_brand || result.value?.agent_name || agentName.value || '').trim()
  for (const ch of n) {
    if (ch && !/\s/.test(ch)) return ch
  }
  return '?'
})

const _nameMap = {
  jun: '钧哥天下无双', qiao: '乔帮主', jia: '炒股养家',
  speed: '极速先锋', trend: '趋势追随者', quant: '量化之翼',
  deepseek: '深度思考者', beijing: '北京炒家',
  chenxiaoqun: '陈小群', zhaolaoge: '赵老哥',
  zhangmengzhu: '章盟主', xiaoyueyu: '小鳄鱼',
}
const _roleMap = {
  jun: '龙头战法', qiao: '龙头主升', jia: '情绪龙头',
  speed: '打板专家', trend: '中线波段', quant: '算法回测',
  deepseek: '深度推理', beijing: '游资打板',
  chenxiaoqun: '情绪合力龙头', zhaolaoge: '主升浪战法',
  zhangmengzhu: '涨停开路+缩量回踩', xiaoyueyu: '二板接力',
}

const agentDescMap = {
  jun: '专注挖掘市场领涨龙头，捕捉短线爆发动能，并针对高频情绪波动进行深度解析与即时反馈。',
  qiao: '只做主线龙头与主升机会，偏爱买在转折的低吸与充分换手后的确定性打板。',
  jia: '情绪周期优先，只做主流题材里的最强龙头，严格收敛到分歧低吸、回封打板和反包确认三类买点。',
  speed: '专注于打板策略，识别最强封板意愿，结合量价关系寻找最优介入时机。',
  trend: '追踪中期趋势方向，结合均线系统与动能指标，把握波段性机会。',
  quant: '运用量化模型与回测数据，从统计学角度验证交易逻辑的可靠性。',
  deepseek: '宏观+行业+个股三维共振；布林带+资金流+催化剂三角验证。',
  beijing: '临盘先判市场闸门，只做前排首板与辨识度后排，扫排分明，次日机械处理。',
  chenxiaoqun: '新生代游资典范，以情绪合力龙头战法为核心，专做主线龙头，擅长高位接力、分歧转一致和反核博弈。',
  zhaolaoge: '主要手法为板上买，以首板和二板接力为主，精于捕捉主升浪，坚持"不创新高不做、不回踩不重仓"的铁律。',
  zhangmengzhu: '从5万做到百亿体量的老牌游资，江湖人称"游资教父"，深耕A股30年，核心模式为涨停开路后缩量回踩20日线确认，专攻高确定性主升浪。',
  xiaoyueyu: '90后新生代游资领军人物，以二板接力为核心战法，操盘手法灵活多样，市场好时追龙头、弱势时空仓或低吸，从万元起步四年过亿，风控意识极强。',
}

// 任务标签配置（人格工件型 Agent 单独定义）
const agentTaskTags = {
  jia: [
    { label: '情绪阶段', icon: 'M12 21q-3.75 0-6.375-2.625T3 12t2.625-6.375T12 3q3.75 0 6.375 2.625T21 12t-2.625 6.375T12 21Zm1-6h-2V7h2v8Zm-1 4q.425 0 .713-.288T13 18q0-.425-.288-.713T12 17q-.425 0-.713.288T11 18q0 .425.288.713T12 19Z' },
    { label: '主流题材', icon: 'M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z' },
    { label: '龙头结构', icon: 'M5 3h14a2 2 0 0 1 2 2v4h-2V5H5v14h6v2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2zm8 7 6 4-6 4v-3H7v-2h6v-3z' },
    { label: '买点模型', icon: 'M13 3L4 14h6v7l9-11h-6z' },
    { label: '卖点切换', icon: 'M6.4 19 5 17.6 10.6 12 5 6.4 6.4 5 12 10.6 17.6 5 19 6.4 13.4 12 19 17.6 17.6 19 12 13.4 6.4 19Z' },
  ],
  qiao: [
    { label: '主线识别', icon: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 14l-5-5h3V7h4v4h3l-5 5z' },
    { label: '情绪阶段', icon: 'M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z' },
    { label: '龙头路径', icon: 'M3 13h2v-2H3v2zm0 4h2v-2H3v2zm0-8h2V7H3v2zm4 8h14v-2H7v2zm0-4h14v-2H7v2zm0-6v2h14V7H7z' },
    { label: '入场模型', icon: 'M13 3L4 14h6v7l9-11h-6z' },
    { label: '次日卖出', icon: 'M19 13H5v-2h14v2z' },
  ],
  beijing: [
    { label: '联网搜索', icon: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54' },
    { label: '三有筛选', icon: 'M3 5v14h18V5H3zm16 12H5V7h14v10z' },
    { label: '板型分类', icon: 'M4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm16-4H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z' },
    { label: '仓位分配', icon: 'M11.8 10.9c-2.27-.59-3-1.2-3-2.15 0-1.09 1.01-1.85 2.7-1.85 1.78 0 2.44.85 2.5 2.1h2.21c-.07-1.72-1.12-3.3-3.21-3.81V3h-3v2.16c-1.94.42-3.5 1.68-3.5 3.61 0 2.31 1.91 3.46 4.7 4.13 2.5.6 3 1.48 3 2.41 0 .69-.49 1.79-2.7 1.79-2.06 0-2.87-.92-2.98-2.1h-2.2c.12 2.19 1.76 3.42 3.68 3.83V21h3v-2.15c1.95-.37 3.5-1.5 3.5-3.55 0-2.84-2.43-3.81-4.7-4.4z' },
    { label: '离场预案', icon: 'M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z' },
  ],
  deepseek: [
    { label: '宏观研判', icon: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z' },
    { label: '行业验证', icon: 'M4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm16-4H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z' },
    { label: '个股筛选', icon: 'M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z' },
    { label: '风险评估', icon: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z' },
  ],
}

const taskTags = computed(() => agentTaskTags[agentId.value] || [])

// ── 生命周期 & 请求取消 ─────────────────────────────────────────────────
let abortCtrl = null
let analysisAbortRequested = false

function isStalePersonaHistoryPayload(analysisResult = {}) {
  const structured = analysisResult?.structured || {}
  const execution = structured?.personaExecution || {}
  const steps = Array.isArray(execution?.stepOutputs) ? execution.stepOutputs : []
  if (agentId.value === 'beijing') {
    const selectionPath = execution?.strategyPanels?.selectionPath || []
    const timeAnchorPhase = String(execution?.timeAnchor?.phase || execution?.strategyPanels?.timeAnchor?.phase || '').trim()
    if (!execution || execution.kind !== 'beijing') return true
    if (!steps.length) return true
    if (!Array.isArray(selectionPath) || !selectionPath.length) return true
    if (!timeAnchorPhase) return true
    return !steps.some(step => Array.isArray(step?.frameworkLines) && step.frameworkLines.length > 0)
  }
  if (agentId.value === 'qiao') {
    const mainJudgement = execution?.strategyPanels?.mainJudgement || {}
    const entryPlaybook = execution?.strategyPanels?.entryPlaybook || []
    const timeAnchorPhase = String(execution?.timeAnchor?.phase || execution?.strategyPanels?.timeAnchor?.phase || '').trim()
    if (!execution || execution.kind !== 'qiao') return true
    if (!steps.length) return true
    if (!timeAnchorPhase) return true
    if (!mainJudgement?.mainTheme || !mainJudgement?.stage) return true
    if (!Array.isArray(entryPlaybook) || !entryPlaybook.length) return true
    return !steps.some(step => Array.isArray(step?.frameworkLines) && step.frameworkLines.length > 0)
  }
  if (agentId.value === 'jia') {
    const emotionStage = execution?.strategyPanels?.emotionStage || {}
    const buyPointPlaybook = execution?.strategyPanels?.buyPointPlaybook || []
    const timeAnchorPhase = String(execution?.timeAnchor?.phase || execution?.strategyPanels?.timeAnchor?.phase || '').trim()
    if (!execution || execution.kind !== 'jia') return true
    if (!steps.length) return true
    if (!timeAnchorPhase) return true
    if (!emotionStage?.stage || !emotionStage?.status) return true
    if (!Array.isArray(buyPointPlaybook) || !buyPointPlaybook.length) return true
    return !steps.some(step => Array.isArray(step?.frameworkLines) && step.frameworkLines.length > 0)
  }
  return false
}

onBeforeUnmount(() => {
  if (abortCtrl) {
    analysisAbortRequested = true
    abortCtrl.abort()
    abortCtrl = null
  }
  isRunning.value = false
})

onMounted(async () => {
  try {
    const today = await fetchTodayAnalysis(agentId.value)
    if (today) {
      const ar = today.analysis_result || {}
      if (isStalePersonaHistoryPayload(ar)) {
        console.info(`[AgentAnalysis] ${agentName.value} 历史结果版本较旧，等待用户触发新版分析`)
      } else {
      const st = ar.structured || {}
      result.value = {
        agent_id: today.agent_id || agentId.value,
        agent_name: st.agentName || agentName.value,
        name_brand: st.agentName || agentName.value,
        structured: st,
        analysis: ar.raw_text || today.raw_response_text || ar.analysis || '',
        thinking: ar.thinking || today.thinking_text || '',
        report_date: today.report_date,
        report_time: today.report_time,
        tokens_used: today.tokens_used || 0,
      }
      if (result.value.thinking) {
        const merged = cleanThinkingChunk(result.value.thinking)
        if (merged) {
          thinkingBuffer = merged
          thinkingLines.value = [merged]
          mergedThinkingIndex = 0
        }
      }
      if (result.value.analysis) {
        liveReportLines.value = result.value.analysis
          .split('\n')
          .map(line => line.trim())
          .filter(Boolean)
          .map(text => ({
            text,
            type: text.startsWith('【') ? 'section' : 'normal',
          }))
      } else if (thinkingBuffer) {
        liveReportLines.value = [{ text: thinkingBuffer, type: 'normal' }]
        mergedThinkingReportIndex = 0
      }
        isDone.value = true
        isFromHistory.value = true
      }
    }
  } catch (e) {
    console.warn('[AgentAnalysis] 加载今日记录失败:', e)
  }

  // 加载 Agent 信息（tagline 等）
  try {
    const info = await fetchAgentInfo(agentId.value)
    if (info) {
      agentInfo.value = info
      seedTaskFlow(info.reasoningSteps || [])
    }
  } catch (e) {
    console.warn('[AgentAnalysis] 加载 Agent 信息失败:', e)
  }

})
const isRunning = ref(false)
const isDone = ref(false)
const isFromHistory = ref(false)
const result = ref(null)
const favBusy = ref({})
const favAdded = ref({})
const showPromptModal = ref(false)
const showShareModal = ref(false)
const thinkingLines = ref([])
const liveReportLines = ref([])
const normalBuffer = []
const liveEl = ref(null)
let thinkingBuffer = ''
let mergedThinkingIndex = -1
let mergedThinkingReportIndex = -1
const realPrompts = ref({ systemPrompt: '', userPrompt: '' })
const agentInfo = ref({ tagline: '', coreObjective: '', reasoningSteps: [] })

// 思考过程展开/折叠状态（分析中可折叠以减少干扰）
const thinkingExpanded = ref(true)

// COT 任务拆解状态
const cotSteps = ref([])        // [{step, title, desc, done}]
const currentCotStep = ref(0)
const totalCotSteps = ref(5)
const currentCotTitle = ref('')
const currentStepDetail = ref('')   // 当前步骤详细描述（用于 TaskProcessCard）
const cotDataLines = ref([])    // 数据获取过程的输出
let cotDataIndexes = {}

function normalizeTaskSteps(steps = []) {
  if (!Array.isArray(steps)) return []
  return steps.map((step, idx) => ({
    step: Number(step?.step) || idx + 1,
    title: step?.title || step?.name || `步骤 ${idx + 1}`,
    desc: step?.description || step?.desc || step?.content || '',
    done: Boolean(step?.done),
  }))
}

function seedTaskFlow(steps = []) {
  const normalized = normalizeTaskSteps(steps)
  if (!normalized.length) return
  cotSteps.value = normalized
  totalCotSteps.value = normalized.length
  currentCotStep.value = 0
  currentCotTitle.value = ''
  currentStepDetail.value = ''
}

function isAbortLikeError(err) {
  const message = String(err?.message || '')
  return (
    err?.name === 'AbortError' ||
    /分析已取消|aborted|aborterror|BodyStreamBuffer was aborted/i.test(message) ||
    (analysisAbortRequested && /network error/i.test(message))
  )
}

function cleanThinkingChunk(text = '') {
  return String(text)
    .replace(/^思考中[:：]\s*/gm, '')
    .trim()
}

function upsertMergedThinking(chunk = '') {
  const cleaned = cleanThinkingChunk(chunk)
  if (!cleaned) return

  thinkingBuffer = cleanThinkingChunk(
    [thinkingBuffer, cleaned].filter(Boolean).join('\n')
  )

  if (mergedThinkingIndex === -1) {
    thinkingLines.value.push(thinkingBuffer)
    mergedThinkingIndex = thinkingLines.value.length - 1
  } else {
    thinkingLines.value[mergedThinkingIndex] = thinkingBuffer
  }

  const reportItem = { text: thinkingBuffer, type: 'normal' }
  if (mergedThinkingReportIndex === -1) {
    liveReportLines.value.push(reportItem)
    mergedThinkingReportIndex = liveReportLines.value.length - 1
  } else {
    liveReportLines.value[mergedThinkingReportIndex] = reportItem
  }

  scrollLive()
}

function upsertCotDataBlock(step, lines = []) {
  const normalized = (lines || [])
    .map(line => String(line || '').trim())
    .filter(Boolean)

  if (!normalized.length) return

  const nextText = `[数据] ${normalized.join('\n')}`
  const existingIndex = cotDataIndexes[step]

  if (Number.isInteger(existingIndex) && thinkingLines.value[existingIndex]) {
    const existingText = String(thinkingLines.value[existingIndex] || '')
      .replace(/^\[数据\]\s*/, '')
      .trim()
    const merged = [existingText, ...normalized].filter(Boolean).join('\n')
    thinkingLines.value[existingIndex] = `[数据] ${merged}`
  } else {
    thinkingLines.value.push(nextText)
    cotDataIndexes[step] = thinkingLines.value.length - 1
  }
}

// ── 加载真实 prompt（弹窗打开时）─────────────────────────────────────
watch(showPromptModal, async (open) => {
  if (!open || realPrompts.value.systemPrompt) return
  try {
    const data = await fetchAgentInfo(agentId.value)
    if (data) {
      realPrompts.value.systemPrompt = data.system_prompt || ''
      realPrompts.value.userPrompt = data.user_prompt_template || ''
    }
  } catch (e) {
    console.warn('[AgentAnalysis] 加载 prompt 失败:', e)
  }
})

// ── 计算属性 ────────────────────────────────────────────────────────────────
const structured = computed(() => result.value?.structured)
const confidence = computed(() => structured.value?.confidence ?? 0)
const recommendedStocks = computed(() => {
  const raw = structured.value?.recommendedStocks ?? []
  if (!Array.isArray(raw)) return []
  return raw.map(s => normalizeRecRow(s)).filter(Boolean)
})
const personaExecution = computed(() => structured.value?.personaExecution || null)
const beijingExecution = computed(() => {
  const execution = personaExecution.value
  if (agentId.value !== 'beijing' || !execution || execution.kind !== 'beijing') return null
  return execution
})
const qiaoExecution = computed(() => {
  const execution = personaExecution.value
  if (agentId.value !== 'qiao' || !execution || execution.kind !== 'qiao') return null
  return execution
})
const jiaExecution = computed(() => {
  const execution = personaExecution.value
  if (agentId.value !== 'jia' || !execution || execution.kind !== 'jia') return null
  return execution
})

const stanceLabel = computed(() => {
  const m = { bull: '看多', bear: '看空', neutral: '中性' }
  return m[structured.value?.stance] || '中性'
})

const stanceColor = computed(() => {
  const m = { bull: '#f23645', bear: '#089981', neutral: '#717786' }
  return m[structured.value?.stance] || '#717786'
})

const gaugeR = 40
const gaugeCirc = computed(() => 2 * Math.PI * gaugeR)
const gaugeOffset = computed(() => gaugeCirc.value * (1 - confidence.value / 100))

const analysisText = computed(() => result.value?.analysis || result.value?.thinking || '')

// ── 分享功能 ────────────────────────────────────────────────────────────────
const shareLoading = ref(false)
const shareShortUrl = ref('')

function encodeSharePayload(payload) {
  try {
    const json = JSON.stringify(payload || {})
    const bytes = new TextEncoder().encode(json)
    let binary = ''
    bytes.forEach(byte => {
      binary += String.fromCharCode(byte)
    })
    return window.btoa(binary)
  } catch (err) {
    console.warn('[AgentAnalysis] 分享 payload 编码失败:', err)
    return ''
  }
}

function buildShareDescription(payload) {
  const stockNames = (payload.stocks || []).map(item => item.name).filter(Boolean)
  if (stockNames.length) {
    return `${payload.confidence}% 信心 | 推荐: ${stockNames.join('、')}`
  }
  if (payload.market_commentary) {
    return `${payload.confidence}% 信心 | ${payload.market_commentary}`
  }
  if (payload.position_advice) {
    return `${payload.confidence}% 信心 | ${payload.position_advice}`
  }
  return `${payload.confidence}% 信心指数`
}

function syncShareMeta(url = shareShortUrl.value || window.location.href) {
  const payload = getSharePayload()
  const stanceLabelMap = { bull: '看多', bear: '看空', neutral: '中性' }
  const stanceText = stanceLabelMap[payload.stance] || '中性'
  const encoded = encodeSharePayload(payload)
  useShare({
    title: `${payload.agent_name}｜${stanceText}深度报告`,
    description: buildShareDescription(payload),
    image: encoded ? `/api/og-image?data=${encodeURIComponent(encoded)}` : '/api/og-image?title=FacSstock',
    url,
  })
}

function getSharePayload() {
  const recs = recommendedStocks.value.slice(0, 3).map(s => ({
    name: s.name || '',
    code: s.code || '',
    changePct: Number(s.changePct ?? 0) || 0,
    reason: String(s.reason || s.signal || '').substring(0, 80),
    role: s.role || '',
    entryModel: s.entryModel || '',
    tradeStatus: s.tradeStatus || '',
  }))
  return {
    agent_id: agentId.value,
    agent_name: agentName.value,
    stance: structured.value?.stance || 'neutral',
    confidence: confidence.value || 0,
    market_commentary: (structured.value?.marketCommentary || '').substring(0, 120),
    position_advice: (structured.value?.positionAdvice || '').substring(0, 120),
    stocks: recs,
    original_url: window.location.href,
  }
}

const shareData = computed(() => {
  const payload = getSharePayload()
  const stanceLabelMap = { bull: '看多', bear: '看空', neutral: '中性' }
  const stanceText = stanceLabelMap[payload.stance] || '中性'
  return {
    title: `${payload.agent_name}｜${stanceText}深度报告`,
    description: buildShareDescription(payload),
    shortUrl: shareShortUrl.value || window.location.href,
    stocks: payload.stocks,
    confidence: payload.confidence,
    stance: payload.stance,
    marketCommentary: payload.market_commentary,
    positionAdvice: payload.position_advice,
    stanceText,
  }
})

async function openShareModal() {
  showShareModal.value = true
  const payload = getSharePayload()

  try {
    shareLoading.value = true
    const res = await fetch('/api/share/shorten', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    const json = await res.json()
    shareShortUrl.value = json.short_url || window.location.href
    syncShareMeta(shareShortUrl.value)
  } catch {
    shareShortUrl.value = window.location.href
    syncShareMeta(window.location.href)
  } finally {
    shareLoading.value = false
  }
}

// 页面加载时更新 meta（使用精简 OG 图片）
onMounted(async () => {
  syncShareMeta(window.location.href)
})

watch(shareData, () => {
  syncShareMeta(shareShortUrl.value || window.location.href)
}, { deep: true })

// 是否有真实思考内容（非占位符）
const hasThinkingContent = computed(() => {
  return thinkingLines.value.some(l =>
    l && !l.startsWith('[阶段]') &&
    l !== 'Waiting to start...' &&
    !l.startsWith('[调用工具]') &&
    !l.startsWith('[数据]')
  )
})

// ── 任务拆解（层次化模式特有）────────────────────────────────────────────
const hasTaskDecomposition = computed(() => {
  const decomp = result.value?.task_decomposition || agentInfo.value?.reasoningSteps
  return Array.isArray(decomp) && decomp.length > 0
})

const taskDecomposition = computed(() => {
  const decomp = result.value?.task_decomposition || agentInfo.value?.reasoningSteps
  return Array.isArray(decomp) ? decomp : []
})

const taskCoreObjective = computed(() => {
  return result.value?.task_core_objective || agentInfo.value?.coreObjective || ''
})

const systemPromptPreview = computed(() => {
  return `你是一位专业的A股短线交易策略分析师，代号「${agentName.value}」，使用${roleSubtitle.value}风格。
你拥有丰富的题材炒作、龙头战法、板块轮动实战经验，熟悉游资操盘手法与量化指标。
请始终以专业、严谨、客观的态度输出分析，禁止提供具体买卖价格建议。`
})

const userPromptPreview = computed(() => {
  const m = {
    'jun': '请根据以下今日市场数据，从龙头视角给出你的策略分析...',
    'qiao': '请先识别主线、阶段与龙头，再从低吸、分歧回流和下午换手板角度给出乔帮主式分析...',
    'jia': '请先判断情绪阶段、主流题材和龙头结构，再仅在分歧低吸、回封打板、反包确认三类模型里给出炒股养家式分析...',
    'speed': '请根据以下市场数据，分析打板机会与风险...',
    'trend': '请根据以下市场数据，分析中期趋势方向与波段机会...',
    'quant': '请根据以下市场数据，给出量化视角的分析...',
    'deepseek': '请从宏观+行业+个股三维深度推理，结合扫描数据给出分析...',
    'beijing': '请先判断市场闸门，再从题材前排、辨识度后排、板型与次日卖点角度分析首板机会...',
    'chenxiaoqun': '请从情绪合力龙头视角，分析主线题材、龙头梯队与高位接力机会...',
    'zhaolaoge': '请从主升浪战法视角，分析首板、二板与板上买机会...',
    'zhangmengzhu': '请从涨停开路+缩量回踩视角，分析主升浪与波段持有机会...',
    'xiaoyueyu': '请从二板接力视角，分析情绪周期、择时控仓与超短机会...',
  }
  return m[agentId.value] || '正在加载 Prompt...'
})

// ── 工具函数 ────────────────────────────────────────────────────────────────
function scrollLive() {
  nextTick(() => {
    if (liveEl.value) {
      liveEl.value.scrollTop = liveEl.value.scrollHeight
    }
  })
}

function roleColor(role) {
  if (!role) return 'neutral'
  if (role.includes('龙头') || role.includes('中军')) return 'primary'
  if (role.includes('跟风') || role.includes('补涨')) return 'muted'
  return 'neutral'
}

function stockRouteCode6(code) {
  const s = String(code || '').trim()
  const m = s.match(/^(\d{6})/)
  if (m) return m[1]
  const digits = s.replace(/\D/g, '')
  return digits.length >= 6 ? digits.slice(0, 6) : digits
}

function normalizePctValue(raw, row = {}) {
  const n = Number(raw)
  if (!Number.isFinite(n)) return 0
  return Math.round(n * 100) / 100
}

function normalizeRecRow(s) {
  if (!s || typeof s !== 'object') return null
  const codeRaw = String(s.code || '').trim()
  const routeCode = stockRouteCode6(codeRaw)

  // 涨跌幅：changePct / chg_pct / change_pct
  const chgRaw = s.changePct ?? s.chg_pct ?? s.change_pct
  const chg_pct = normalizePctValue(chgRaw, s)

  // 现价（后端已补调，不应为 0）
  const price = s.price !== undefined && s.price !== null && s.price !== ''
    ? String(s.price) : ''

  const name = String(s.name || '').trim()
  const displayCode = codeRaw || routeCode || '--'

  // 趋势标签：从 grade / adviseType 综合判断
  const gradeRaw = String(s.grade || '').trim()
  const adviseType = String(s.adviseType || '').trim()
  const signal = String(s.signal || '').trim()
  let trendTag = String(s.trendTag || '').trim()
  if (!trendTag) {
    const gradeMap = { 'S': '顶级标的', 'A': '重点关注', 'B': '普通关注', 'C': '观察标的' }
    if (gradeRaw && gradeMap[gradeRaw]) trendTag = gradeMap[gradeRaw]
    else if (adviseType) trendTag = adviseType
  }

  // 目标盈利
  let targetProfit = String(s.targetProfit || s.profit_target || '').trim()
  if (!targetProfit && s.targetPrice) targetProfit = String(s.targetPrice)
  if (!targetProfit && s.target) targetProfit = String(s.target)

  // 硬性止损
  const hardStop = String(s.hardStop || s.stopLoss || s.stop_loss || '').trim()

  // 建仓区间
  const priceRange = String(s.priceRange || s.price_range || s.entry_range || s.buyRange || '').trim()

  // 推荐逻辑
  const reason = String(s.reason || s.meta || signal || '').trim()
  const boardType = String(s.boardType || '').trim()
  const leaderType = String(s.leaderType || '').trim()
  const stage = String(s.stage || '').trim()
  const selectionType = String(s.selectionType || '').trim()
  const buyMethod = String(s.buyMethod || '').trim()
  const buyPointType = String(s.buyPointType || '').trim()
  const tradeStatus = String(s.tradeStatus || '').trim()
  const entryPlan = String(s.entryPlan || '').trim()
  const entryModel = String(s.entryModel || '').trim()
  const entryTrigger = String(s.entryTrigger || '').trim()
  const exitTrigger = String(s.exitTrigger || '').trim()
  const actionableNow = Boolean(s.actionableNow)
  const emotionStage = String(s.emotionStage || '').trim()
  const emotionFit = String(s.emotionFit || '').trim()
  const themeRole = String(s.themeRole || '').trim()
  const labels = Array.isArray(s.labels) ? s.labels.map(v => String(v || '').trim()).filter(Boolean) : []
  const matchedRules = Array.isArray(s.matchedRules)
    ? s.matchedRules
      .map(rule => ({
        title: String(rule?.title || '').trim(),
        detail: String(rule?.detail || '').trim(),
      }))
      .filter(rule => rule.title && rule.detail)
    : []
  const threeHaveSummary = String(s.threeHaveSummary || '').trim()
  const firstSealTime = String(s.firstSealTime || '').trim()
  const lastSealTime = String(s.lastSealTime || '').trim()
  const nextDaySellPlan = String(s.nextDaySellPlan || '').trim()
  const reboundSealVerdict = String(s.reboundSealVerdict || '').trim()
  const sealVerdictSummary = String(s.sealVerdictSummary || '').trim()
  const rotationSignal = String(s.rotationSignal || '').trim()
  const maSupportSummary = String(s.maSupportSummary || '').trim()
  const minuteTurnoverLabel = String(s.minuteTurnoverLabel || '').trim()
  const minuteEvidence = String(s.minuteEvidence || '').trim()
  const auctionStrength = String(s.auctionStrength || '').trim()
  const teammateStrength = String(s.teammateStrength || '').trim()
  const auctionTeammateSummary = String(s.auctionTeammateSummary || '').trim()
  const minuteLongestStreak = Number(s.minuteLongestStreak || 0)
  const timeAnchorPhase = String(s.timeAnchorPhase || '').trim()
  const timeAnchorWindow = String(s.timeAnchorWindow || '').trim()
  const brokenBoardCount = s.brokenBoardCount ?? s.brokenBoardCountText ?? ''
  const brokenBoardCountText = brokenBoardCount !== '' && brokenBoardCount !== null && brokenBoardCount !== undefined
    ? `${brokenBoardCount}`
    : ''

  return {
    ...s,
    name,
    routeCode,
    displayCode,
    chg_pct,
    price,
    trendTag,
    targetProfit,
    hardStop,
    priceRange,
    reason,
    grade: gradeRaw,
    adviseType,
    signal,
    boardType,
    leaderType,
    stage,
    selectionType,
    buyMethod,
    buyPointType,
    tradeStatus,
    entryPlan,
    entryModel,
    entryTrigger,
    exitTrigger,
    actionableNow,
    emotionStage,
    emotionFit,
    themeRole,
    labels,
    matchedRules,
    threeHaveSummary,
    firstSealTime,
    lastSealTime,
    nextDaySellPlan,
    reboundSealVerdict,
    sealVerdictSummary,
    rotationSignal,
    maSupportSummary,
    minuteTurnoverLabel,
    minuteEvidence,
    auctionStrength,
    teammateStrength,
    auctionTeammateSummary,
    minuteLongestStreak,
    timeAnchorPhase,
    timeAnchorWindow,
    brokenBoardCount,
    brokenBoardCountText,
  }
}

function goStockDetail(s) {
  const c = s.routeCode
  if (!c || !/^\d{6}$/.test(c)) return
  router.push({ name: 'StockDetail', params: { code: c } })
}

async function favoriteStock(s) {
  const code = s.routeCode
  if (!code || !/^\d{6}$/.test(code)) return
  if (favAdded.value[code]) return
  favBusy.value = { ...favBusy.value, [code]: true }
  try {
    await watchlist.add(code, s.name || '', s.sector || '')
    favAdded.value = { ...favAdded.value, [code]: true }
  } catch (e) {
    console.warn('[AgentAnalysis] 加自选失败', e)
  } finally {
    const next = { ...favBusy.value }
    delete next[code]
    favBusy.value = next
  }
}

// 合并普通内容缓冲区：积累的短句合并成一段输出
function flushNormalBuffer() {
  if (!normalBuffer.length) return
  const text = normalBuffer.join(' ')
  thinkingLines.value.push(text)
  liveReportLines.value.push({ text, type: 'normal' })
  normalBuffer.length = 0
}

// ── 分析执行 ────────────────────────────────────────────────────────────────
async function runAnalysis() {
  if (isRunning.value) return
  isRunning.value = true
  isDone.value = false
  isFromHistory.value = false
  result.value = null
  thinkingLines.value = []
  liveReportLines.value = []
  thinkingBuffer = ''
  mergedThinkingIndex = -1
  mergedThinkingReportIndex = -1
  cotDataIndexes = {}
  normalBuffer.length = 0
  cotSteps.value = []
  currentCotStep.value = 0
  seedTaskFlow(agentInfo.value?.reasoningSteps || [])
  analysisAbortRequested = false

  abortCtrl = new AbortController()

  try {
    // 使用流式接口
    await runAnalysisStream(agentId.value, abortCtrl.signal)
  } catch (err) {
    if (isAbortLikeError(err) || abortCtrl?.signal?.aborted) return
    console.warn('[AgentAnalysis] 分析中断:', err.message)
    console.error('[AgentAnalysis] 分析失败:', err)
  } finally {
    isRunning.value = false
    abortCtrl = null
  }
}

async function runAnalysisStream(agentId, signal) {
  console.log('[AgentAnalysisStream] 开始请求流式接口:', agentId)
  const response = await fetch(`/api/agents/analyze/${agentId}/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
    signal,
  })

  console.log('[AgentAnalysisStream] 响应状态:', response.status, response.statusText)
  console.log('[AgentAnalysisStream] Response headers:', Object.fromEntries(response.headers.entries()))

  if (!response.ok) {
    // 尝试读取错误响应
    let text
    try {
      text = await response.text()
      console.error('[AgentAnalysisStream] 错误响应体:', text)
    } catch (e) {
      text = ''
    }
    // 尝试从 SSE 格式解析错误信息
    try {
      const lines = text.split('\n\n')
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = JSON.parse(line.slice(6))
          if (data.type === 'error') {
            throw new Error(data.error || '请求失败')
          }
        }
      }
    } catch (e) {
      if (e.message !== '请求失败') throw e
    }
    throw new Error(text || `请求失败 (HTTP ${response.status})`)
  }

  // 检查 Content-Type
  const contentType = response.headers.get('content-type') || ''
  console.log('[AgentAnalysisStream] Content-Type:', contentType)

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    let chunk
    try {
      chunk = await reader.read()
    } catch (err) {
      if (signal?.aborted || isAbortLikeError(err)) {
        throw new Error('分析已取消')
      }
      throw err
    }

    const { done, value } = chunk
    if (done) {
      console.log('[AgentAnalysisStream] 流读取完成')
      break
    }

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    console.log('[AgentAnalysisStream] 收到数据块, 行数:', lines.length, 'buffer长度:', buffer.length)

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed) continue
      if (!trimmed.startsWith('data: ')) continue
      const payload = trimmed.slice(6).trim()
      if (payload === '[DONE]') {
        continue
      }

      try {
        const data = JSON.parse(payload)
        handleStreamEvent(data)
      } catch (e) {
        console.warn('[Stream] 解析失败:', payload, e)
      }
    }
  }
}

function handleStreamEvent(data) {
  switch (data.type) {
    case 'task_flow_init': {
      const steps = normalizeTaskSteps(data.steps || [])
      if (steps.length) {
        cotSteps.value = steps
        totalCotSteps.value = data.total || steps.length
        currentCotStep.value = 0
        currentCotTitle.value = data.coreObjective ? '核心目标' : ''
        currentStepDetail.value = data.coreObjective || ''
      }
      break
    }

    case 'task_step': {
      // 任务执行过程：前端展示步骤进度
      const step = data.step || 1
      const total = data.total || cotSteps.value.length || 5
      const title = data.title || ''
      const desc = data.desc || ''

      currentCotStep.value = step
      totalCotSteps.value = total
      currentCotTitle.value = title
      currentStepDetail.value = desc

      // 更新或追加步骤
      const existing = cotSteps.value.find(s => s.step === step)
      if (existing) {
        existing.title = title
        existing.desc = desc
      } else {
        cotSteps.value.push({ step, title, desc, done: false })
        cotSteps.value.sort((a, b) => a.step - b.step)
      }
      cotSteps.value = cotSteps.value.map(item => ({
        ...item,
        done: item.step < step,
      }))
      break
    }

    case 'cot': {
      currentCotStep.value = data.step || 0
      totalCotSteps.value = data.total || 5
      currentCotTitle.value = data.title || ''
      thinkingLines.value.push(`[阶段] ${data.title} → ${data.message}`)
      break
    }

    case 'cot_step': {
      flushNormalBuffer()
      cotSteps.value.push({
        step: data.step,
        title: data.title,
        desc: data.desc,
        done: data.step < (currentCotStep.value || 0),
      })
      thinkingLines.value.push(`[步骤${data.step}] ${data.title}：${data.desc}`)
      break
    }

    case 'cot_data': {
      flushNormalBuffer()
      const lines = data.lines || []
      for (const line of lines) {
        cotDataLines.value.push({ step: data.step, text: line })
      }
      upsertCotDataBlock(data.step || 0, lines)
      break
    }

    case 'thinking': {
      upsertMergedThinking(data.content || '')
      break
    }

    case 'content': {
      const text = (data.content || '').trim()
      if (text) {
        liveReportLines.value.push({
          text,
          type: text.startsWith('【') ? 'section' : 'normal',
        })
        scrollLive()
      }
      break
    }

    case 'analysis': {
      // 同步分析模式下的最终报告分段（联网思考已完成，最终报告分段输出）
      const text = (data.content || '').trim()
      if (text) {
        const type = text.startsWith('【') ? 'section' : 'normal'
        liveReportLines.value.push({ text, type })
        scrollLive()
      }
      break
    }

    case 'status':
      // 更新进度提示
      break

    case 'tool_call':
      // 工具调用属于内部执行细节，不直接暴露给用户端
      break

    case 'tool_result': {
      // 工具原始返回只供模型内部消费，不直接展示到时间线
      break
    }

    case 'done':
      // flush 剩余 thinking
      if (thinkingBuffer.trim()) {
        thinkingBuffer = cleanThinkingChunk(thinkingBuffer)
      }
      // 如果没有实时内容但有分析文本，转成报告
      if (!liveReportLines.value.length && data.analysis) {
        const lines = data.analysis.split('\n').filter(l => l.trim())
        for (const l of lines) {
          const text = l.trim()
          const type = text.startsWith('【') ? 'section' : 'normal'
          liveReportLines.value.push({ text, type })
        }
      }
      const st = data.structured || {}
      result.value = {
        agent_id: data.agent_id,
        agent_name: data.agent_name,
        structured: st,
        analysis: data.analysis,
        thinking: data.thinking,
        tokens_used: data.tokens_used,
        // 同步 stance / confidence 到 cotSteps 用于 TaskProcessCard 的共识仪表
        cot_steps_confidence: st.confidence || 0,
        cot_steps_stance: st.stance || 'neutral',
        cot_steps_marketCommentary: st.marketCommentary || '',
        // 任务拆解数据
        task_decomposition: data.task_decomposition || [],
        task_core_objective: data.task_core_objective || '',
      }
      if (Array.isArray(data.task_decomposition) && data.task_decomposition.length) {
        cotSteps.value = normalizeTaskSteps(data.task_decomposition)
        totalCotSteps.value = data.task_decomposition.length
      }
      const finalSteps = cotSteps.value || []
      const lastStep = finalSteps[finalSteps.length - 1]
      currentCotStep.value = finalSteps.length || totalCotSteps.value || currentCotStep.value
      totalCotSteps.value = finalSteps.length || totalCotSteps.value
      currentCotTitle.value = lastStep?.title || '执行完成'
      currentStepDetail.value = lastStep?.desc || '全部任务步骤已完成'
      isDone.value = true
      // 分析完成：将所有 COT 步骤标记为已完成，flush 剩余缓冲区
      flushNormalBuffer()
      cotSteps.value = cotSteps.value.map(s => ({ ...s, done: true }))
      break

    case 'error':
      throw new Error(data.error || '流式分析错误')
  }
}

function resetAnalysis() {
  isRunning.value = false
  isDone.value = false
  result.value = null
  isFromHistory.value = false
  favAdded.value = {}
  favBusy.value = {}
  thinkingLines.value = []
  liveReportLines.value = []
  thinkingBuffer = ''
  mergedThinkingIndex = -1
  mergedThinkingReportIndex = -1
  cotDataIndexes = {}
  normalBuffer.length = 0
  cotSteps.value = []
  currentCotStep.value = 0
  totalCotSteps.value = 5
  currentCotTitle.value = ''
  currentStepDetail.value = ''
  currentStepDetail.value = ''
  cotDataLines.value = []
  thinkingExpanded.value = true
  analysisAbortRequested = false
  seedTaskFlow(agentInfo.value?.reasoningSteps || [])
}

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push(basePath.value)
}
</script>

<style scoped>
/* ── Precision Ledger Design System ────────────────────────────────────── */

/* Color Palette — root vars */
.fac-root {
  /* Primary: Deep Ocean Navy */
  --primary: #3b1f8c;
  --primary-container: #5a34a8;
  --on-primary: #ffffff;
  --on-primary-container: #e8deff;
  --primary-fixed: #e8deff;
  --primary-fixed-dim: #c9b8ff;
  --on-primary-fixed: #26005a;
  --on-primary-fixed-variant: #4600b3;

  /* Surface Tiers (No-line tonal hierarchy) */
  --surface: #f5f2ff;
  --surface-bright: #f5f2ff;
  --surface-container-lowest: #ffffff;
  --surface-container-low: #ede8ff;
  --surface-container: #e5e0ff;
  --surface-container-high: #ddd8ff;
  --surface-container-highest: #d5d0ff;
  --surface-dim: #c7c2eb;
  --surface-variant: #ddd8ff;

  /* Semantic — A股红涨绿跌 */
  --secondary: #6b3fa0;
  --secondary-container: #e5d0ff;
  --secondary-fixed: #eed9ff;
  --secondary-fixed-dim: #dab8ff;
  --on-secondary: #ffffff;
  --on-secondary-container: #4a0080;
  --on-secondary-fixed: #380066;
  --on-secondary-fixed-variant: #5600b3;

  --tertiary: #390002;
  --tertiary-container: #600007;
  --tertiary-fixed: #ffdad6;
  --tertiary-fixed-dim: #ffb3ac;
  --on-tertiary: #ffffff;
  --on-tertiary-container: #ff5a53;
  --on-tertiary-fixed: #410003;
  --on-tertiary-fixed-variant: #930010;

  --error: #ba1a1a;
  --error-container: #ffdad6;
  --on-error: #ffffff;
  --on-error-container: #93000a;

  /* Neutrals */
  --background: #f5f2ff;
  --on-background: #1e1633;
  --on-surface: #1e1633;
  --on-surface-variant: #464455;
  --inverse-surface: #2d2449;
  --inverse-on-surface: #f0ecff;
  --inverse-primary: #c9b8ff;

  --outline: #747780;
  --outline-variant: rgba(196, 198, 208, 0.3);

  /* A股涨跌语义 */
  --up: #f23645;
  --up-alpha: rgba(242, 54, 69, 0.1);
  --down: #089981;
  --down-alpha: rgba(8, 153, 129, 0.1);

  /* Elevation */
  --shadow-card: 0 8px 24px rgba(46, 36, 73, 0.06);
  --shadow-nav: 0 -4px 20px rgba(46, 36, 73, 0.08);
  --shadow-header: 0 8px 24px rgba(46, 36, 73, 0.06);
  --track: #c7c2eb;

  /* Typography */
  --font-headline: 'Manrope', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-body: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-mono: 'Roboto Mono', 'SF Mono', Menlo, monospace;
}

.fac-root {
  font-family: var(--font-body);
  min-height: 100dvh;
  background: var(--surface);
  color: var(--on-surface);
  -webkit-font-smoothing: antialiased;
}

/* ── TopAppBar ─────────────────────────────────────────────────────────── */
.fac-header {
  position: sticky;
  top: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  height: 64px;
  padding: 0 24px;
  background: rgba(245, 242, 255, 0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: var(--shadow-header);
  transition: background 0.2s;
}

.fac-header__left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.fac-header__icon-btn {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  border: none;
  background: transparent;
  color: var(--on-surface);
  cursor: pointer;
  transition: background 0.15s, transform 0.15s;
  flex-shrink: 0;
}
.fac-header__icon-btn:active { transform: scale(0.92); }
.fac-header__icon-btn:hover { background: rgba(221, 216, 255, 0.6); }
.fac-header__icon-btn .mso { font-size: 24px; }

.fac-header__brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.fac-header__avatar {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: var(--primary);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--on-primary);
  font-family: var(--font-headline);
  font-size: 18px;
  font-weight: 800;
  letter-spacing: -0.03em;
  flex-shrink: 0;
}

.fac-header__title-group {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.fac-header__title {
  font-family: var(--font-headline);
  font-size: 1.05rem;
  font-weight: 800;
  color: var(--on-surface);
  letter-spacing: -0.02em;
  line-height: 1.2;
}

.fac-header__subtitle {
  font-family: var(--font-body);
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--on-surface-variant);
}

.fac-header__right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.fac-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 12px;
  border-radius: 999px;
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}
.fac-badge--history {
  background: var(--surface-dim);
  color: var(--on-surface-variant);
}
.fac-badge--running {
  background: rgba(0, 22, 55, 0.1);
  color: var(--primary);
}
.fac-badge--done {
  background: rgba(8, 153, 129, 0.1);
  color: var(--down);
}
.fac-badge--pending {
  background: var(--surface-dim);
  color: var(--on-surface-variant);
}
.fac-badge__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
}
.fac-badge__dot--spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Main Canvas ─────────────────────────────────────────────────────── */
.fac-main {
  max-width: 720px;
  margin: 0 auto;
  padding: 20px 16px 100px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ── Prompt Card ─────────────────────────────────────────────────────── */
.fac-prompt-card {
  background: var(--surface-container-lowest);
  border-radius: 24px;
  padding: 24px;
  box-shadow: var(--shadow-card);
  position: relative;
  overflow: hidden;
}
.fac-prompt-card__glow {
  position: absolute;
  top: -20px;
  right: -20px;
  width: 120px;
  height: 120px;
  background: var(--primary-container);
  opacity: 0.06;
  border-radius: 0 0 0 100%;
  pointer-events: none;
}
.fac-prompt-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  position: relative;
  z-index: 1;
}
.fac-prompt-card__title {
  font-family: var(--font-headline);
  font-size: 1.1rem;
  font-weight: 800;
  color: var(--on-surface);
  display: flex;
  align-items: center;
  gap: 8px;
  letter-spacing: -0.02em;
  margin: 0;
}
.fac-prompt-card__title .mso {
  color: var(--primary-container);
  font-size: 20px;
}
.fac-prompt-card__expand {
  display: flex;
  align-items: center;
  gap: 4px;
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 500;
  color: var(--on-surface-variant);
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 8px;
  transition: color 0.15s, background 0.15s;
}
.fac-prompt-card__expand:hover { color: var(--primary); background: rgba(0, 22, 55, 0.05); }
.fac-prompt-card__expand .mso { font-size: 16px; }
.fac-prompt-card__code {
  background: var(--surface-container-low);
  border-radius: 16px;
  padding: 16px;
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.8;
  color: var(--on-surface-variant);
  overflow-x: auto;
  position: relative;
  z-index: 1;
  border: 1px solid rgba(196, 198, 208, 0.15);
  white-space: pre-wrap;
  word-break: break-all;
}
.fac-prompt-card__code .kw { color: var(--primary-container); font-weight: 600; }

/* ── Thinking Timeline ──────────────────────────────────────────────── */
.fac-thinking-card {
  background: var(--surface-container-lowest);
  border-radius: 24px;
  padding: 24px;
  box-shadow: var(--shadow-card);
}
.fac-thinking-card__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
  cursor: pointer;
  border-radius: 12px;
  padding: 4px;
  margin: -4px -4px 20px;
  transition: background 0.15s;
}
.fac-thinking-card__head:hover { background: rgba(207, 230, 242, 0.4); }
.fac-thinking-card__head:active { background: rgba(207, 230, 242, 0.7); }
.fac-thinking-card__head .mso {
  color: var(--primary-container);
  font-size: 20px;
}
.fac-thinking-card__title {
  font-family: var(--font-headline);
  font-size: 1.1rem;
  font-weight: 800;
  color: var(--on-surface);
  flex: 1;
  letter-spacing: -0.02em;
  margin: 0;
}
.fac-thinking-card__count {
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 700;
  background: var(--surface-dim);
  color: var(--on-surface-variant);
  padding: 2px 8px;
  border-radius: 999px;
}
.fac-thinking-card__toggle {
  color: var(--on-surface-variant);
  transition: transform 0.2s;
  display: flex;
  align-items: center;
}
.fac-thinking-card__toggle--open { transform: rotate(180deg); }
.fac-thinking-card__toggle .mso { font-size: 20px; }

.fac-timeline {
  position: relative;
  padding-left: 36px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.fac-timeline::before {
  content: '';
  position: absolute;
  left: 14px;
  top: 8px;
  bottom: 8px;
  width: 2px;
  background: var(--surface-dim);
  border-radius: 1px;
}

.fac-timeline__item {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  position: relative;
}
.fac-timeline__dot {
  position: absolute;
  left: -30px;
  top: 2px;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--surface-container-highest);
  border: 2px solid var(--surface-container-lowest);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.3s;
}
.fac-timeline__dot .mso {
  font-size: 14px;
  color: var(--primary-container);
}
.fac-timeline__dot--active {
  background: var(--primary);
  border-color: var(--surface-container-lowest);
  box-shadow: 0 0 16px rgba(0, 22, 55, 0.35);
}
.fac-timeline__dot--active .mso {
  color: var(--on-primary);
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.fac-timeline__content {
  flex: 1;
  min-width: 0;
  background: var(--surface-container-low);
  border-radius: 16px;
  padding: 14px 16px;
  transition: all 0.3s;
}
.fac-timeline__content--active {
  background: rgba(0, 42, 93, 0.06);
  border: 1px solid rgba(0, 42, 93, 0.15);
}
.fac-timeline__content--done { opacity: 0.7; }

.fac-timeline__title {
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 600;
  color: var(--on-surface);
  margin: 0 0 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.fac-timeline__dots {
  display: flex;
  gap: 3px;
  align-items: center;
}
.fac-timeline__dot-anim {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--primary-container);
  animation: bounce 1s infinite;
}
.fac-timeline__dot-anim:nth-child(2) { animation-delay: 0.2s; }
.fac-timeline__dot-anim:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce {
  0%, 100% { transform: translateY(0); opacity: 1; }
  50% { transform: translateY(-3px); opacity: 0.4; }
}

.fac-timeline__desc {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--on-surface-variant);
  margin: 0;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.fac-thinking-card__run-btn-wrap {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}
.fac-btn-run {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 14px 32px;
  border-radius: 999px;
  background: var(--primary);
  color: var(--on-primary);
  font-family: var(--font-body);
  font-size: 15px;
  font-weight: 600;
  border: none;
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(7, 30, 39, 0.12);
  transition: background 0.15s, transform 0.1s, box-shadow 0.15s;
}
.fac-btn-run:hover {
  background: var(--primary-container);
  box-shadow: 0 12px 32px rgba(7, 30, 39, 0.18);
}
.fac-btn-run:active { transform: scale(0.97); }
.fac-btn-run:disabled { opacity: 0.5; cursor: not-allowed; }
.fac-btn-run--running {
  background: var(--on-surface-variant);
  box-shadow: none;
}
.fac-btn-run .mso { font-size: 20px; }
.fac-btn-run__spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* ── Report Card ────────────────────────────────────────────────────── */
.fac-report-card {
  background: var(--surface-container-lowest);
  border-radius: 24px;
  padding: 24px;
  box-shadow: var(--shadow-card);
}
.fac-report-card__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}
.fac-report-card__head .mso {
  color: var(--primary-container);
  font-size: 18px;
}
.fac-report-card__title {
  font-family: var(--font-headline);
  font-size: 1rem;
  font-weight: 800;
  color: var(--on-surface);
  flex: 1;
  letter-spacing: -0.02em;
  margin: 0;
}
.fac-report-card__live {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-family: var(--font-body);
  font-size: 10px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--primary-container);
  background: rgba(0, 42, 93, 0.08);
  padding: 3px 10px;
  border-radius: 999px;
}
.fac-report-card__live-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--primary-container);
  animation: pulse-dot 1.2s ease-in-out infinite;
}
@keyframes pulse-dot {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.6); opacity: 0.5; }
}

.fac-report-card__body {
  background: var(--surface-container-low);
  border-radius: 16px;
  padding: 16px;
  max-height: 400px;
  overflow-y: auto;
  scrollbar-width: thin;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.fac-report-card__module {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.fac-report-card__module-head {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--primary-container);
}
.fac-report-card__module-head .mso {
  font-size: 18px;
}
.fac-report-card__module-title {
  font-family: var(--font-headline);
  font-size: 13px;
  font-weight: 800;
  letter-spacing: -0.01em;
}
.fac-report-card__divider {
  height: 1px;
  background: rgba(196, 198, 208, 0.22);
  margin: 8px 0 10px;
}
.fac-report-line {
  font-family: var(--font-body);
  font-size: 13px;
  line-height: 1.75;
  color: var(--on-surface);
  animation: fadein 0.3s ease;
}
.fac-report-line--section {
  font-family: var(--font-headline);
  font-size: 14px;
  font-weight: 800;
  color: var(--primary-container);
  padding: 8px 0 4px;
  border-bottom: 1px solid rgba(196, 198, 208, 0.2);
  margin-top: 8px;
}
.fac-report-line--section:first-child { margin-top: 0; border-top: none; padding-top: 0; }
@keyframes fadein {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ── Consensus Gauge ────────────────────────────────────────────────── */
.fac-consensus-card {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 20px;
  padding: 24px;
  background: var(--surface-container-lowest);
  border-radius: 24px;
  box-shadow: var(--shadow-card);
}
@media (max-width: 380px) { .fac-consensus-card { grid-template-columns: 1fr; } }

.fac-consensus__gauge {
  display: flex;
  align-items: center;
}
.fac-consensus__svg { width: 96px; height: 96px; }
.fac-consensus__arc { transition: stroke-dashoffset 1s ease; }
.fac-consensus__num {
  font-family: var(--font-headline);
  font-size: 20px;
  font-weight: 800;
  fill: var(--on-surface);
  font-variant-numeric: tabular-nums;
}
.fac-consensus__unit {
  font-family: var(--font-body);
  font-size: 10px;
  font-weight: 600;
  fill: var(--on-surface-variant);
}

.fac-consensus__right { display: flex; flex-direction: column; gap: 8px; }
.fac-consensus__stance-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }

.fac-stance-tag {
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 800;
  padding: 4px 14px;
  border-radius: 999px;
}
.fac-stance-tag--bull { background: var(--up-alpha); color: var(--up); }
.fac-stance-tag--bear { background: var(--down-alpha); color: var(--down); }
.fac-stance-tag--neutral { background: var(--surface-dim); color: var(--on-surface-variant); }

.fac-consensus__conf-label {
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 600;
  color: var(--on-surface-variant);
}
.fac-consensus__comm {
  font-family: var(--font-body);
  font-size: 13px;
  line-height: 1.65;
  color: var(--on-surface);
  margin: 0;
}
.fac-consensus__advice {
  font-family: var(--font-body);
  font-size: 13px;
  line-height: 1.65;
  color: var(--on-surface-variant);
  margin: 0;
}
.fac-consensus__advice strong { font-weight: 800; color: var(--on-surface); }
.fac-consensus__warning {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-family: var(--font-body);
  font-size: 12px;
  color: var(--error);
  background: rgba(186, 26, 26, 0.06);
  padding: 8px 12px;
  border-radius: 10px;
  line-height: 1.5;
}
.fac-consensus__warning .mso { font-size: 14px; flex-shrink: 0; }

/* ── Recommendations ────────────────────────────────────────────────── */
.fac-recs-card {
  padding: 0;
  background: var(--surface-container-lowest);
  border-radius: 24px;
  overflow: hidden;
  box-shadow: var(--shadow-card);
}
.fac-recs__title {
  font-family: var(--font-headline);
  font-size: 1.2rem;
  font-weight: 800;
  color: var(--on-surface);
  letter-spacing: -0.02em;
  padding: 24px 24px 0;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 10px;
}
.fac-recs__title .mso { color: var(--primary-container); font-size: 22px; }

.fac-rec-item {
  display: flex;
  flex-direction: column;
  padding: 20px 24px;
  border-top: 1px solid rgba(196, 198, 208, 0.15);
  position: relative;
  overflow: hidden;
  transition: background 0.15s;
}
.fac-rec-item:last-child { border-bottom: none; }
.fac-rec-item::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, transparent 0%, rgba(0, 42, 93, 0.025) 100%);
  opacity: 0;
  transition: opacity 0.3s;
  pointer-events: none;
}
.fac-rec-item:hover::before { opacity: 1; }

/* 顶部行：名称代码 | 标签 */
.fac-rec-item__top {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  margin-bottom: 14px;
  gap: 12px;
}
.fac-rec-item__name-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}
.fac-rec-item__name {
  font-family: var(--font-headline);
  font-size: 1.3rem;
  font-weight: 800;
  color: var(--on-surface);
  letter-spacing: -0.03em;
  line-height: 1.2;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.fac-rec-item__code-badge {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  color: var(--on-surface-variant);
  background: var(--surface-dim);
  padding: 2px 8px;
  border-radius: 6px;
  letter-spacing: 0.04em;
}
.fac-rec-item__grade-badge {
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 800;
  padding: 2px 8px;
  border-radius: 6px;
  letter-spacing: 0.03em;
}
.fac-rec-item__grade-badge--s { background: rgba(242, 54, 69, 0.12); color: var(--up); border: 1px solid rgba(242, 54, 69, 0.25); }
.fac-rec-item__grade-badge--a { background: rgba(0, 42, 93, 0.1); color: var(--primary-container); border: 1px solid rgba(0, 42, 93, 0.2); }
.fac-rec-item__grade-badge--b, .fac-rec-item__grade-badge--c { background: var(--surface-dim); color: var(--on-surface-variant); }

.fac-rec-item__badges {
  display: flex;
  gap: 6px;
  align-items: flex-start;
  flex-wrap: wrap;
  justify-content: flex-start;
  width: 100%;
}
.fac-rec-item__trend-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 999px;
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 700;
  background: var(--up-alpha);
  color: var(--up);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.fac-rec-item__trend-chip .mso { font-size: 12px; }
.fac-rec-item__board-chip {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 700;
  background: rgba(59, 31, 140, 0.1);
  color: var(--primary-container);
}
.fac-rec-item__sector-chip {
  display: inline-flex;
  padding: 4px 10px;
  border-radius: 999px;
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 600;
  background: var(--surface-dim);
  color: var(--on-surface-variant);
}
.fac-rec-item__sector-chip--selection {
  background: rgba(59, 31, 140, 0.08);
  color: var(--primary-container);
}
.fac-rec-item__sector-chip--status {
  background: rgba(8, 153, 129, 0.12);
  color: #0f766e;
}
.fac-rec-item__risk-chip {
  font-family: var(--font-body);
  font-size: 10px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 999px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.fac-rec-item__risk-chip--高 { background: var(--up-alpha); color: var(--up); }
.fac-rec-item__risk-chip--中 { background: rgba(0, 42, 93, 0.08); color: var(--primary-container); }
.fac-rec-item__risk-chip--低 { background: var(--down-alpha); color: var(--down); }

/* 信号行 */
.fac-rec-item__signals {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 14px;
}
.fac-rec-item__signal-chip {
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 6px;
  background: rgba(0, 42, 93, 0.07);
  color: var(--primary-container);
}
.fac-rec-item__signal-chip--primary {
  background: rgba(59, 31, 140, 0.1);
  color: var(--primary-container);
}
.fac-rec-item__signal-chip--muted {
  background: var(--surface-dim);
  color: var(--on-surface-variant);
}

/* 指标网格 */
.fac-rec-item__metrics {
  display: grid;
  grid-template-columns: 1fr 1fr 2fr;
  gap: 10px;
  margin-bottom: 14px;
}
.fac-rec-item__metric {
  background: var(--surface-container-low);
  border-radius: 14px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  text-align: center;
}
.fac-rec-item__metric-label {
  font-family: var(--font-body);
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--on-surface-variant);
  margin: 0;
}
.fac-rec-item__metric-value {
  font-family: var(--font-headline);
  font-size: 17px;
  font-weight: 800;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
}
.fac-rec-item__metric-value--up { color: var(--up); }
.fac-rec-item__metric-value--down { color: var(--down); }
.fac-rec-item__metric-value--range {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--on-surface);
}

/* 现价+涨跌行 */
.fac-rec-item__price-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 0;
  flex-wrap: wrap;
}
.fac-rec-item__price {
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 700;
  color: var(--on-surface);
}
.fac-rec-item__chg {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.fac-rec-item__chg--up { color: var(--up); }
.fac-rec-item__chg--down { color: var(--down); }
.fac-rec-item__score-chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 700;
  color: var(--primary-container);
}
.fac-rec-item__score-chip .mso { font-size: 12px; }

/* 操作行 */
.fac-rec-item__ops {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.fac-rec-item__op-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 600;
  color: var(--on-surface);
  background: var(--surface-container-low);
  padding: 4px 10px;
  border-radius: 8px;
}
.fac-rec-item__op-chip .mso { font-size: 14px; color: var(--on-surface-variant); }
.fac-rec-item__board-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.fac-rec-item__board-meta-chip {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  background: var(--surface-dim);
  color: var(--on-surface-variant);
}
.fac-rec-item__sell-plan {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 14px;
  padding: 8px 12px;
  border-radius: 10px;
  background: rgba(242, 54, 69, 0.06);
  color: var(--on-surface);
  font-family: var(--font-body);
  font-size: 12px;
  line-height: 1.5;
}
.fac-rec-item__sell-plan .mso {
  font-size: 14px;
  color: var(--up);
}
.fac-rec-item__rules {
  border-top: 1px solid rgba(196, 198, 208, 0.15);
  padding-top: 14px;
  margin-bottom: 14px;
}
.fac-rec-item__rule-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.fac-rec-item__rule-card {
  padding: 12px;
  border-radius: 14px;
  background: linear-gradient(180deg, rgba(245, 242, 255, 0.9) 0%, rgba(240, 235, 255, 0.78) 100%);
  border: 1px solid rgba(90, 52, 168, 0.12);
}
.fac-rec-item__rule-title {
  margin-bottom: 6px;
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 800;
  color: var(--primary-container);
}
.fac-rec-item__rule-detail {
  font-family: var(--font-body);
  font-size: 12px;
  line-height: 1.65;
  color: var(--on-surface);
}

/* 推荐逻辑 */
.fac-rec-item__reason {
  border-top: 1px solid rgba(196, 198, 208, 0.15);
  padding-top: 14px;
  margin-bottom: 14px;
}
.fac-rec-item__reason-label {
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 700;
  color: var(--on-surface-variant);
  margin: 0 0 6px;
  display: flex;
  align-items: center;
  gap: 5px;
}
.fac-rec-item__reason-label .mso { font-size: 14px; color: var(--primary-container); }
.fac-rec-item__reason-text {
  font-family: var(--font-body);
  font-size: 13px;
  line-height: 1.7;
  color: var(--on-surface);
  margin: 0;
}

/* 底部按钮 */
.fac-rec-item__footer {
  display: flex;
  justify-content: flex-end;
}
.fac-btn-fav {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 999px;
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 700;
  background: var(--surface-dim);
  color: var(--on-surface);
  border: none;
  cursor: pointer;
  transition: all 0.15s;
}
.fac-btn-fav:active { transform: scale(0.97); }
.fac-btn-fav:disabled { opacity: 0.5; }
.fac-btn-fav--on {
  background: var(--primary);
  color: var(--on-primary);
  box-shadow: 0 4px 16px rgba(7, 30, 39, 0.15);
}
.fac-btn-fav .mso { font-size: 16px; }

/* ── Beijing Execution ─────────────────────────────────────────────── */
.fac-beijing-card {
  background: var(--surface-container-lowest);
  border-radius: 24px;
  overflow: hidden;
  box-shadow: var(--shadow-card);
}
.fac-beijing-card--embedded {
  background: transparent;
  border-radius: 18px;
  box-shadow: none;
  border: 1px solid rgba(90, 52, 168, 0.12);
}
.fac-beijing-card__head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  background: var(--surface-container-low);
  border-bottom: 1px solid rgba(196, 198, 208, 0.15);
}
.fac-beijing-card__head .mso { color: var(--primary-container); font-size: 18px; }
.fac-beijing-card__title {
  margin: 0;
  font-family: var(--font-headline);
  font-size: 1rem;
  font-weight: 800;
  color: var(--on-surface);
}
.fac-beijing-card__body {
  padding: 18px 20px 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.fac-beijing-card--embedded .fac-beijing-card__body {
  padding: 16px;
  background: linear-gradient(180deg, rgba(247, 244, 255, 0.96) 0%, rgba(242, 238, 255, 0.9) 100%);
}
.fac-beijing-card__gate {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.fac-beijing-gate-chip {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.01em;
}
.fac-beijing-gate-chip--放行 {
  background: rgba(8, 153, 129, 0.12);
  color: var(--down);
}
.fac-beijing-gate-chip--轻仓试错 {
  background: rgba(255, 176, 32, 0.16);
  color: #9a5b00;
}
.fac-beijing-gate-chip--空仓等待 {
  background: rgba(242, 54, 69, 0.1);
  color: var(--up);
}
.fac-beijing-gate-chip--subtle {
  background: var(--surface-dim);
  color: var(--on-surface-variant);
}
.fac-beijing-gate-chip--anchor {
  background: rgba(59, 31, 140, 0.1);
  color: var(--primary-container);
}
.fac-beijing-gate-chip--warn {
  background: rgba(255, 152, 0, 0.16);
  color: #b35c00;
  font-weight: 700;
}
.fac-beijing-card__stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.fac-beijing-stat {
  padding: 12px 14px;
  border-radius: 14px;
  background: var(--surface-container-low);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.fac-beijing-stat__label {
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 700;
  color: var(--on-surface-variant);
}
.fac-beijing-stat__value {
  font-family: var(--font-headline);
  font-size: 20px;
  font-weight: 800;
  color: var(--on-surface);
}
.fac-beijing-card__summary {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.fac-beijing-panels {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.fac-beijing-panel {
  padding: 14px 16px;
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.82) 0%, rgba(247, 244, 255, 0.88) 100%);
  border: 1px solid rgba(90, 52, 168, 0.10);
}
.fac-beijing-panel__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.fac-beijing-panel__head .mso {
  color: var(--primary-container);
  font-size: 18px;
}
.fac-beijing-panel__title {
  margin: 0;
  font-family: var(--font-headline);
  font-size: 14px;
  font-weight: 800;
  color: var(--on-surface);
}
.fac-beijing-panel__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.fac-beijing-panel__grid--selection {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.fac-beijing-panel__card {
  padding: 12px 12px 10px;
  border-radius: 14px;
  background: rgba(241, 236, 255, 0.72);
  border: 1px solid rgba(90, 52, 168, 0.08);
}
.fac-beijing-panel__card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}
.fac-beijing-panel__pill {
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-radius: 999px;
  background: rgba(59, 31, 140, 0.12);
  color: var(--primary-container);
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 800;
}
.fac-beijing-panel__pill--board {
  background: rgba(79, 70, 229, 0.12);
  color: #4338ca;
}
.fac-beijing-panel__pill--rule {
  background: rgba(0, 150, 136, 0.12);
  color: #0f766e;
}
.fac-beijing-panel__pill--anchor {
  background: rgba(255, 176, 32, 0.18);
  color: #9a5b00;
}
.fac-beijing-panel__count {
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 800;
  color: var(--on-surface);
}
.fac-beijing-panel__desc {
  margin: 0;
  font-family: var(--font-body);
  font-size: 12px;
  line-height: 1.65;
  color: var(--on-surface-variant);
}
.fac-beijing-panel__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.fac-beijing-panel__tag {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(90, 52, 168, 0.09);
  color: var(--primary-container);
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 700;
}
.fac-beijing-panel__tag--anchor {
  background: rgba(255, 176, 32, 0.14);
  color: #9a5b00;
}
.fac-beijing-card__steps {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.fac-beijing-card__section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.fac-beijing-card__section-head {
  font-family: var(--font-headline);
  font-size: 13px;
  font-weight: 800;
  color: var(--on-surface);
}
.fac-beijing-step {
  padding: 14px 16px;
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(245, 242, 255, 0.92) 0%, rgba(240, 235, 255, 0.84) 100%);
  border: 1px solid rgba(90, 52, 168, 0.12);
}
.fac-beijing-step__head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.fac-beijing-step__num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 56px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(59, 31, 140, 0.12);
  color: var(--primary-container);
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 800;
}
.fac-beijing-step__copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.fac-beijing-step__title {
  margin: 0;
  font-family: var(--font-headline);
  font-size: 14px;
  font-weight: 800;
  color: var(--on-surface);
}
.fac-beijing-step__summary {
  margin: 0;
  font-family: var(--font-body);
  font-size: 13px;
  line-height: 1.6;
  color: var(--on-surface);
}
.fac-beijing-step__lines {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.fac-beijing-step__section {
  margin-top: 10px;
}
.fac-beijing-step__section-label {
  margin-bottom: 6px;
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.04em;
  color: var(--primary-container);
}
.fac-beijing-step__lines--method {
  margin-top: 0;
}
.fac-beijing-step__line {
  margin: 0;
  padding-left: 12px;
  position: relative;
  font-family: var(--font-body);
  font-size: 12px;
  line-height: 1.6;
  color: var(--on-surface-variant);
}
.fac-beijing-step__line--method {
  color: var(--on-surface);
}
.fac-beijing-step__line::before {
  content: '';
  position: absolute;
  left: 0;
  top: 8px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--primary-container);
}
.fac-beijing-summary-chip,
.fac-beijing-candidate__chip {
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-radius: 999px;
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 700;
  background: var(--surface-dim);
  color: var(--on-surface-variant);
}
.fac-beijing-candidate__chip--board {
  background: rgba(59, 31, 140, 0.1);
  color: var(--primary-container);
}
.fac-beijing-candidate__chip--selection {
  background: rgba(0, 42, 93, 0.08);
  color: var(--primary-container);
}
.fac-beijing-candidate__chip--pass {
  background: rgba(0, 42, 93, 0.08);
  color: var(--primary-container);
}
.fac-beijing-candidate__chip--status {
  background: rgba(8, 153, 129, 0.12);
  color: #0f766e;
}
.fac-beijing-candidate__chip--action {
  background: rgba(59, 31, 140, 0.12);
  color: var(--primary-container);
}
.fac-beijing-candidate__chip--label {
  background: var(--surface-container-high);
  color: var(--on-surface-variant);
}
.fac-beijing-card__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.fac-beijing-rule-list {
  margin-top: 10px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.fac-beijing-rule-card {
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(90, 52, 168, 0.08);
}
.fac-beijing-rule-card__title {
  margin-bottom: 4px;
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 800;
  color: var(--primary-container);
}
.fac-beijing-rule-card__detail {
  font-family: var(--font-body);
  font-size: 12px;
  line-height: 1.55;
  color: var(--on-surface);
}
.fac-beijing-candidate {
  padding: 14px 16px;
  border-radius: 16px;
  background: var(--surface-container-low);
  border: 1px solid rgba(196, 198, 208, 0.12);
}
.fac-beijing-candidate__top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 8px;
}
.fac-beijing-candidate__name {
  font-family: var(--font-headline);
  font-size: 15px;
  font-weight: 800;
  color: var(--on-surface);
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.fac-beijing-candidate__code {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--on-surface-variant);
  background: var(--surface-dim);
  padding: 2px 8px;
  border-radius: 999px;
}
.fac-beijing-candidate__chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.fac-beijing-candidate__reason {
  margin: 0 0 8px;
  font-family: var(--font-body);
  font-size: 13px;
  line-height: 1.6;
  color: var(--on-surface);
}
.fac-beijing-candidate__meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--on-surface-variant);
}
@media (max-width: 640px) {
  .fac-rec-item__rule-grid,
  .fac-beijing-rule-list,
  .fac-beijing-card__stats {
    grid-template-columns: 1fr;
  }
  .fac-beijing-panel__grid,
  .fac-beijing-panel__grid--selection {
    grid-template-columns: 1fr;
  }
  .fac-beijing-step__head {
    flex-direction: column;
  }
  .fac-beijing-candidate__top {
    flex-direction: column;
  }
  .fac-beijing-candidate__chips {
    justify-content: flex-start;
  }
}

/* ── Task Decomposition ─────────────────────────────────────────────── */
.fac-decomp-card {
  background: var(--surface-container-lowest);
  border-radius: 24px;
  overflow: hidden;
  box-shadow: var(--shadow-card);
}
.fac-decomp-card__head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  background: var(--surface-container-low);
  border-bottom: 1px solid rgba(196, 198, 208, 0.15);
}
.fac-decomp-card__head .mso { color: var(--primary-container); font-size: 18px; }
.fac-decomp-card__title {
  font-family: var(--font-headline);
  font-size: 1rem;
  font-weight: 800;
  color: var(--on-surface);
  flex: 1;
  letter-spacing: -0.02em;
  margin: 0;
}
.fac-decomp-card__body { padding: 16px 20px; display: flex; flex-direction: column; gap: 12px; }
.fac-decomp-card__objective {
  margin: 0;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(59, 31, 140, 0.08);
  color: var(--on-surface);
  line-height: 1.55;
}
.fac-decomp-step {
  padding: 14px 16px;
  background: var(--surface-container-low);
  border-radius: 12px;
  border-left: 4px solid var(--primary-container);
}
.fac-decomp-step__header { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.fac-decomp-step__num {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--primary-container);
  color: var(--on-primary);
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.fac-decomp-step__title {
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 700;
  color: var(--on-surface);
}
.fac-decomp-step__desc {
  font-family: var(--font-body);
  font-size: 12px;
  line-height: 1.6;
  color: var(--on-surface-variant);
  margin: 0;
  padding-left: 34px;
}

/* ── JSON Block ────────────────────────────────────────────────────── */
.fac-analysis-card { background: var(--surface-container-lowest); border-radius: 24px; overflow: hidden; box-shadow: var(--shadow-card); }
.fac-analysis-card__head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  background: var(--surface-container-low);
  border-bottom: 1px solid rgba(196, 198, 208, 0.15);
}
.fac-analysis-card__head .mso { color: var(--primary-container); font-size: 18px; }
.fac-analysis-card__title {
  font-family: var(--font-headline);
  font-size: 1rem;
  font-weight: 800;
  color: var(--on-surface);
  flex: 1;
  margin: 0;
  letter-spacing: -0.02em;
}
.fac-json-block {
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.6;
  color: var(--on-surface);
  background: var(--surface-container-low);
  padding: 16px;
  margin: 0;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

/* ── Prompt Modal ───────────────────────────────────────────────────── */
.fac-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}
.fac-modal {
  background: var(--surface-container-lowest);
  border-radius: 20px;
  width: 100%;
  max-width: 680px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.2);
}
.fac-modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  background: var(--surface-container-low);
  border-bottom: 1px solid rgba(196, 198, 208, 0.15);
  flex-shrink: 0;
}
.fac-modal__title {
  font-family: var(--font-headline);
  font-size: 1rem;
  font-weight: 800;
  color: var(--on-surface);
  margin: 0;
  letter-spacing: -0.02em;
}
.fac-modal__close {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--surface-dim);
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--on-surface-variant);
  transition: background 0.15s;
}
.fac-modal__close:hover { background: var(--surface-container-highest); }
.fac-modal__close .mso { font-size: 18px; }
.fac-modal__body {
  flex: 1;
  overflow-y: auto;
  padding: 0 24px 32px;
  display: flex;
  flex-direction: column;
  scrollbar-width: thin;
}
.fac-modal__section { padding: 20px 0; border-bottom: 1px solid rgba(196, 198, 208, 0.15); }
.fac-modal__section:last-child { border-bottom: none; }
.fac-modal__label {
  font-family: var(--font-body);
  font-size: 10px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--primary-container);
  margin: 0 0 12px;
}
.fac-modal__code {
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.75;
  color: var(--on-surface);
  background: var(--surface-container-low);
  border-radius: 12px;
  padding: 16px;
  margin: 0;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 300px;
  overflow-y: auto;
  scrollbar-width: thin;
  border: 1px solid rgba(196, 198, 208, 0.15);
}

/* ── Bottom Bar ──────────────────────────────────────────────────────── */
.fac-bottom-bar {
  display: flex;
  justify-content: center;
  padding: 16px 20px;
  background: var(--surface);
}
.fac-btn-share {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 14px 36px;
  border-radius: 16px;
  background: var(--primary);
  color: var(--on-primary);
  font-family: var(--font-body);
  font-size: 15px;
  font-weight: 700;
  border: none;
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(7, 30, 39, 0.15);
  transition: all 0.15s;
}
.fac-btn-share:hover {
  background: var(--primary-container);
  box-shadow: 0 12px 32px rgba(7, 30, 39, 0.2);
}
.fac-btn-share:active { transform: scale(0.97); }
.fac-btn-share .mso { font-size: 20px; }

/* 主内容区底部间距 */
.fac-main { padding-bottom: 24px; }

/* ── Footer ─────────────────────────────────────────────────────────── */
.fac-footer {
  margin-top: auto;
  padding: 24px 16px 40px;
  border-top: 1px solid rgba(196, 198, 208, 0.15);
}
.fac-footer__inner { max-width: 640px; margin: 0 auto; text-align: center; }
.fac-footer__warn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-body);
  font-size: 10px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--error);
  margin-bottom: 8px;
}
.fac-footer__warn .mso { font-size: 14px; }
.fac-footer__text {
  font-family: var(--font-body);
  font-size: 11px;
  line-height: 1.65;
  color: var(--on-surface-variant);
  margin: 0;
}

/* ── Material Symbols Outlined ───────────────────────────────────────── */
.mso {
  font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
  font-family: 'Material Symbols Outlined';
  user-select: none;
}
.mso-fill { font-variation-settings: 'FILL' 1, 'wght' 400, 'GRAD' 0, 'opsz' 24; }

/* ── Print ────────────────────────────────────────────────────────────── */
@media print {
  .fac-header, .fac-footer, .fac-btn-run, .fac-btn-share, .fac-modal-overlay, .fac-bottom-bar { display: none !important; }
  .fac-main { padding: 0 !important; max-width: 100% !important; }
  .fac-report-card { box-shadow: none !important; }
  .fac-report-card__body { max-height: none !important; overflow: visible !important; }
  @page { margin: 16mm; size: A4; }
}
</style>
