<template>
  <Teleport to="body">
    <Transition name="share-modal">
      <div v-if="visible" class="fac-share-overlay" @click.self="emit('close')">
        <div class="fac-share-sheet">
          <div class="fac-share-sheet__header">
            <h3 class="fac-share-sheet__title">分享</h3>
            <button type="button" class="fac-share-sheet__close" @click="emit('close')" aria-label="关闭">
              <span class="mso">close</span>
            </button>
          </div>

          <div class="fac-share-sheet__body">
            <!-- 精简分享卡片：信心指数 + 推荐结果 -->
            <div class="fac-share-card" ref="shareCardRef">
              <div class="fac-share-card__left">
                <!-- 信心指数圆环 -->
                <div class="fac-share-gauge">
                  <svg viewBox="0 0 100 100" class="fac-share-gauge__svg">
                    <circle cx="50" cy="50" r="42" class="fac-share-gauge__track" />
                    <circle
                      cx="50" cy="50" r="42"
                      class="fac-share-gauge__arc"
                      :class="`fac-share-gauge__arc--${shareData.stance}`"
                      :stroke-dasharray="`${(shareData.confidence / 100) * 264} 264`"
                    />
                    <text x="50" y="46" class="fac-share-gauge__num">{{ shareData.confidence }}</text>
                    <text x="50" y="62" class="fac-share-gauge__unit">%</text>
                  </svg>
                </div>
                <div class="fac-share-card__stance">
                  <span class="fac-share-stance-tag" :class="`fac-share-stance-tag--${shareData.stance}`">
                    {{ shareData.stanceText }}
                  </span>
                </div>
                <p class="fac-share-card__commentary">{{ shareData.marketCommentary || '暂无市场评论' }}</p>
              </div>

              <div class="fac-share-card__divider" />

              <div class="fac-share-card__right">
                <h4 class="fac-share-card__section-title">
                  <span class="mso" style="color:var(--primary-container)">star</span>
                  推荐股票
                </h4>
                <div class="fac-share-stocks">
                  <div
                    v-for="(stock, idx) in (shareData.stocks || [])"
                    :key="idx"
                    class="fac-share-stock-item"
                  >
                    <div class="fac-share-stock-item__top">
                      <div class="fac-share-stock-item__left">
                        <span class="fac-share-stock-item__name">{{ stock.name || stock.stock_name }}</span>
                        <span class="fac-share-stock-item__code">{{ stock.code || stock.stock_code }}</span>
                      </div>
                      <span class="fac-share-stock-item__chg">
                        {{ formatPct(stock.changePct ?? stock.chg_pct) }}
                      </span>
                    </div>
                    <div v-if="stock.reason" class="fac-share-stock-item__reason">
                      {{ stock.reason }}
                    </div>
                  </div>
                  <p v-if="!shareData.stocks?.length" class="fac-share-stocks__empty">暂无推荐股票</p>
                </div>
              </div>
            </div>

            <div class="fac-share-channels">
              <button type="button" class="fac-share-channel-btn" @click="handleWeChat">
                <div class="fac-share-channel-btn__icon fac-share-channel-btn__icon--wechat">
                  <svg viewBox="0 0 1025 1024" xmlns="http://www.w3.org/2000/svg">
                    <path d="M338.895 385.219c17.067 0 29.257-12.19 29.257-30.476s-12.19-29.257-29.257-29.257-35.352 12.19-35.352 29.257c0 18.286 17.067 30.476 35.352 30.476z m164.572-59.733c-17.067 0-35.353 12.19-35.353 29.257 0 18.286 18.286 30.476 35.353 30.476 18.285 0 29.257-12.19 29.257-30.476 0-17.067-10.972-29.257-29.257-29.257z m206.019 221.866c18.285 0 29.257-12.19 29.257-24.38s-12.19-24.382-29.257-24.382c-12.19 0-23.162 12.191-23.162 24.381s12.19 24.381 23.162 24.381z m-129.22 0c18.286 0 29.258-12.19 29.258-24.38s-12.19-24.382-29.257-24.382c-12.19 0-23.162 12.191-23.162 24.381s10.971 24.381 23.162 24.381zM1.22 512c0 282.819 229.181 512 512 512s512-229.181 512-512S794.819 0 512 0C230.4 0 1.219 229.181 1.219 512z m629.029-121.905c-112.153 0-199.924 85.334-199.924 188.953 0 17.066 2.438 34.133 7.314 49.98-7.314 1.22-14.628 1.22-21.943 1.22-29.257 0-53.638-6.096-82.895-12.19l-82.895 41.447 23.162-71.924c-58.515-41.448-93.867-95.086-93.867-160.914 0-113.372 106.057-203.581 235.276-203.581 115.81 0 216.99 71.924 237.714 168.228-6.095 0-14.628-1.219-21.942-1.219zM846.019 576.61c0 53.638-35.352 101.18-82.895 137.752l18.286 59.733-64.61-35.352c-23.162 6.095-47.543 12.19-70.705 12.19-112.152 0-201.143-78.019-201.143-173.104 0-95.086 88.99-173.105 201.143-173.105 104.838-1.22 199.924 76.8 199.924 171.886z" fill="#04D102"/>
                  </svg>
                </div>
                <span class="fac-share-channel-btn__label">微信</span>
              </button>

              <button type="button" class="fac-share-channel-btn" @click="handleFeishu">
                <div class="fac-share-channel-btn__icon fac-share-channel-btn__icon--feishu">
                  <svg viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg">
                    <path d="M770.91584 373.312c-2.688 0.128-3.392-1.088-3.648-3.648-0.32-2.688-0.128-5.952-1.472-8.064-2.56-4.032-1.856-8.768-4.032-12.928a23.04 23.04 0 0 1-2.56-7.04c-0.128-1.536 0.256-3.584-0.832-4.352-2.304-1.664-1.408-4.416-2.88-6.592-1.6-2.368-1.728-5.76-2.944-8.64-1.28-3.008-2.752-6.208-3.072-9.536-0.128-1.6-1.92-1.664-1.92-3.264 0.192-2.688-1.792-4.928-2.432-7.488-0.896-3.392-2.816-6.72-4.096-10.048a78.528 78.528 0 0 0-3.392-7.936c-1.856-3.648-3.392-7.36-5.504-10.944-2.048-3.2-2.56-7.232-4.8-10.688a59.2 59.2 0 0 1-4.672-8.96c-2.112-4.992-5.248-9.344-7.68-14.08a196.48 196.48 0 0 0-7.488-13.824c-2.56-4.288-4.8-8.832-7.808-12.992-1.216-1.728-3.072-3.392-3.392-5.312-0.448-2.752-2.56-4.736-3.84-6.4-1.856-2.112-1.92-6.016-5.504-6.848 0 0-0.128-0.32-0.064-0.512 0.256-2.88-3.84-3.712-3.456-6.72-3.2-1.088-2.24-5.696-5.824-6.592 0 0-0.192-0.256-0.128-0.384 0.32-2.944-2.56-4.544-3.776-6.464a48.96 48.96 0 0 0-5.504-6.848c-0.96-1.024-2.56-1.92-2.88-3.2-1.28-4.352-5.44-6.528-7.552-10.368-1.984-3.52-5.44-5.824-8.128-8.768a28.16 28.16 0 0 0-9.536-7.296c-3.392-1.28-6.144-4.096-10.24-4.352-4.224-0.192-8.256-2.688-12.672-2.56C617.18784 128.704 616.86784 128 615.71584 128H172.38784c-1.216 0-1.472 0.704-1.472 1.664-2.944-0.192-4.544 2.24-5.504 3.968-2.176 3.84 0.96 10.944 5.184 12.672 1.792 0.64 2.752 1.92 3.968 3.072 0.64 0.64 1.28 1.664 2.176 1.536 1.792-0.192 2.56 1.088 3.072 2.112 0.64 1.408 1.92 1.92 2.944 2.432a37.12 37.12 0 0 1 8.512 6.016c3.776 3.52 8 6.4 12.16 9.408 3.392 2.496 6.144 5.76 9.92 7.808 2.816 1.472 4.352 4.736 7.04 6.08 3.84 1.92 5.952 5.568 9.6 7.424a19.328 19.328 0 0 1 5.632 4.992c1.472 1.664 4.096 1.792 5.312 3.456 3.392 5.12 9.28 7.424 13.312 12.032 3.904 4.48 9.472 7.168 13.568 11.904 4.864 5.632 11.392 9.6 16.64 14.912 3.712 3.648 7.424 7.04 11.136 10.56 2.944 2.752 5.888 5.44 8.64 8.32 2.048 2.048 4.672 3.648 6.592 5.44 4.736 4.608 10.24 8.704 13.568 14.656l0.704 0.896c3.648 3.392 7.296 6.848 10.88 10.368 4.352 4.352 8.576 9.088 13.312 13.248a17.92 17.92 0 0 1 4.864 5.376c0.96 2.24 2.56 3.648 4.096 5.12 4.032 3.84 8.384 7.552 11.264 12.544 1.152 2.048 3.584 2.752 4.8 4.736 1.6 2.496 4.032 4.224 5.632 6.912 2.368 3.84 6.4 6.528 9.088 10.56 2.624 3.968 6.144 7.744 9.536 11.136 3.776 3.84 6.4 8.448 10.432 11.904 2.112 1.792 2.304 5.12 5.056 6.208 1.344 0.64 1.792 1.792 2.176 2.752 1.472 3.136 4.16 5.312 5.888 8.256 1.664 2.88 4.48 4.736 6.4 7.616 3.52 5.376 7.552 10.56 11.904 15.36 1.408 1.6 1.28 4.096 3.328 4.864 3.072 1.28 3.584 4.544 5.12 6.72 2.112 2.88 4.864 5.312 6.4 8.448 1.664 3.328 4.416 5.824 6.144 8.96 1.664 2.752 3.712 5.248 5.376 8 1.28 2.112 2.432 4.48 4.224 6.4 1.92 1.92 2.56 4.928 4.864 6.784 2.048 1.664 2.432 4.352 4.352 6.272 1.984 2.176 2.816 5.44 4.992 7.552 1.92 1.792 2.816 4.288 4.16 6.4 0.96 1.472 2.944 2.368 3.2 4.352 0.192 2.176 1.856 3.52 2.944 5.12 1.664 2.496 3.84 4.928 4.8 7.296 1.792 4.416 4.8 7.744 6.912 11.712 2.496 4.352 5.568 8.768 8.064 13.312 1.92 3.264 3.776 6.592 5.824 9.6 0.896 1.6 0.704 3.648 2.432 4.8 2.048 1.472 2.496 3.968 3.648 6.016 1.024 1.792 1.728 4.032 3.2 5.248 1.152 1.024 1.152 1.92 1.408 3.2 1.728 0.64 2.624-0.704 3.648-1.664l8.192-8.128 16.896-16.64c4.8-4.8 9.28-9.856 14.272-14.464 8.768-8 16.832-16.64 25.6-24.768 5.696-5.312 10.816-11.2 17.088-16 5.504-4.16 10.112-9.472 15.104-14.336l11.008-11.008c3.84-3.84 8.768-6.272 12.288-10.368a3.072 3.072 0 0 1 1.088-0.96c3.712-1.472 6.272-4.48 9.344-6.72 3.584-2.56 7.168-5.12 10.624-7.808 1.792-1.408 4.032-2.048 5.568-3.584 4.416-4.416 10.24-6.4 15.36-9.472 5.44-3.2 11.008-6.4 16.64-9.088 4.096-1.92 7.68-4.928 12.032-5.76 5.12-1.088 8.768-4.48 13.568-6.016 1.472-0.384 3.264-0.576 4.608-1.6 2.752-2.176 6.528-2.176 9.6-3.648 1.472-0.704 3.136-1.664 4.8-1.92 3.84-0.448 7.168-2.24 10.88-3.2 0.96-0.192 1.792-0.768 0.896-2.048" fill="#00D6B9"/>
                    <path d="M876.19584 641.28c-1.024-0.64-1.728 0.256-2.368 0.896-1.92 1.792-3.392 4.096-5.056 6.144l-8.384 9.856c-5.76 6.336-12.032 12.416-18.304 18.112-4.928 4.48-10.368 8.32-15.68 12.288-1.92 1.472-3.904 3.072-5.952 4.416-2.24 1.536-4.16 3.584-6.592 4.608-4.608 1.92-8.704 4.8-12.992 7.296-7.424 4.096-15.168 7.68-23.04 10.752-4.48 1.856-8.896 3.84-13.44 5.248-3.712 1.152-7.296 2.752-11.008 3.648-1.28 0.32-2.56 0.192-3.776 0.64-3.648 1.344-7.488 2.176-11.328 3.136-3.264 0.832-6.848 0.128-9.728 1.472-4.352 2.048-9.344 0.128-13.44 2.88-6.4 0-12.736 0.64-19.072 1.216-11.264 0.832-22.528-0.768-33.792-1.088-5.12-0.128-9.984-2.688-15.168-1.92a1.088 1.088 0 0 1-0.832-0.32c-1.664-1.28-3.648-1.28-5.504-1.28-3.968 0-7.808-0.832-11.52-1.536-3.648-0.768-7.36-2.176-10.944-3.392-2.112-0.704-4.416-0.32-6.336-1.28a32.576 32.576 0 0 0-8.768-2.752c-7.04-1.472-13.504-4.416-20.608-5.568-4.672-0.768-8.768-3.392-13.44-4.352-3.328-0.768-6.528-1.92-9.664-2.944-4.032-1.28-8.064-2.688-12.16-3.712-6.528-1.792-12.48-4.544-18.88-6.592-7.616-2.56-14.976-5.504-22.592-8.064-4.48-1.472-8.448-4.16-13.312-4.928a16.768 16.768 0 0 1-5.824-2.176c-3.584-2.048-7.68-2.752-11.264-4.48-3.072-1.536-6.528-2.24-9.536-3.712-4.992-2.56-10.752-3.328-15.296-6.912a1.92 1.92 0 0 0-1.088-0.32c-3.648-0.384-6.912-2.048-10.112-3.648-6.912-3.392-14.4-5.632-21.184-9.344-5.44-3.008-11.392-4.736-16.832-7.68-1.28-0.256-2.368 0-3.648-0.64-2.24-1.152-4.416-2.944-6.72-3.584-4.48-1.216-7.808-4.48-12.224-5.76-2.496-0.704-4.416-2.944-6.72-3.52-2.944-0.704-5.376-2.176-7.68-3.52-3.84-2.176-8.064-3.648-11.968-6.016-2.112-1.344-4.864-1.792-6.72-3.328-2.752-2.304-7.04-2.176-8.96-5.696-4.672-0.384-7.808-3.968-11.84-5.632-4.8-1.92-9.088-4.992-13.632-7.552-1.92-1.088-3.648-3.072-5.504-3.392-4.928-1.024-8.32-4.544-12.416-6.784a142.72 142.72 0 0 1-13.888-8.32c-0.768-0.448-1.856-0.384-2.368-0.96-2.88-3.264-7.04-4.928-10.688-7.168a484.608 484.608 0 0 1-10.56-6.4c-4.352-2.752-8.768-5.44-12.864-8.32-2.752-1.984-6.144-3.2-8.512-5.44-1.728-1.6-3.84-2.176-5.632-3.648-3.2-2.624-6.976-4.8-10.432-7.168-1.6-1.088-3.776-2.112-4.864-3.328-2.112-2.304-4.992-3.52-7.232-5.376-3.392-2.88-7.616-4.864-10.944-7.872-1.984-1.728-4.928-2.048-6.4-4.48-0.512-0.96-1.472-1.664-2.752-1.984-2.24-0.64-3.776-2.432-5.568-3.648-2.688-1.856-5.12-4.352-7.936-6.272-3.328-2.24-6.272-5.248-9.728-7.296-3.712-2.24-6.336-5.76-10.048-7.872-2.304-1.408-3.648-3.968-5.888-4.992-3.904-1.728-6.272-5.184-9.856-7.296-2.752-1.792-4.672-5.12-7.616-6.592-3.456-1.856-5.504-5.056-8.576-7.168-0.832-0.64-1.92-0.768-2.688-1.792-1.92-2.368-4.672-4.16-6.912-6.272-2.432-2.176-5.44-3.648-7.68-6.272-1.728-1.92-3.584-4.48-5.76-5.376-3.392-1.28-4.864-4.224-7.488-6.144-3.328-2.304-5.76-5.696-8.96-8.256-2.048-1.6-4.352-2.88-5.952-4.928-2.432-3.072-5.504-5.696-8.32-8.32C63.58784 417.92 60.06784 414.208 56.35584 410.752c-2.944-2.56-5.632-5.504-8.64-8.192-2.752-2.432-5.248-5.248-8.064-7.68C35.93984 391.424 32.54784 387.584 29.09184 384 25.63584 380.416 21.92384 377.024 18.53184 373.312 15.65184 370.048 12.70784 366.08 7.07584 367.232c-2.816 0.64-4.096 2.368-5.12 4.608-2.88 0.32-1.728 2.56-1.728 3.776v414.208c0 1.664 0.192 3.264 0.128 4.864 0 1.28 0.384 1.856 1.6 1.92-0.768 3.84 1.792 6.848 2.368 10.368 0.384 2.56 1.984 4.608 2.944 6.976 1.408 3.2 4.096 5.888 6.016 8.96a24.96 24.96 0 0 0 6.4 6.72c2.688 1.92 5.376 3.904 8.192 5.632 3.392 1.92 6.592 4.288 9.728 6.464 0.96 0.64 2.048 0.768 3.072 1.728a47.36 47.36 0 0 0 10.24 6.4c2.432 1.28 4.736 2.944 7.36 4.032 5.824 2.432 10.816 6.784 16.832 9.152 3.328 1.28 5.888 3.648 9.344 4.672 0.768 0.32 1.728 0.384 2.432 0.832 4.8 3.328 10.24 5.248 15.488 7.872 1.088 0.64 2.496 0.64 3.328 1.28a21.504 21.504 0 0 0 9.536 4.288c0.64 0.128 1.152 0.192 1.856 0.704 1.408 1.088 3.2 1.92 4.928 2.88 1.92 1.088 4.416 0.448 6.144 2.304 0.64 0.768 2.24 1.728 3.456 1.92 5.12 0.96 9.856 3.392 14.656 5.248 1.408 0.64 3.328 0 4.352 1.152 1.92 1.92 4.608 1.92 6.784 2.88 3.2 1.408 6.592 2.56 10.24 3.392 1.472 0.384 3.584 0 4.544 1.088 1.856 2.048 4.608 2.176 6.592 2.688 5.248 1.28 10.368 2.944 15.488 4.672 4.096 1.472 8.704 1.792 13.056 3.072 3.648 1.024 7.296 2.24 10.944 2.88 1.728 0.32 4.16-0.384 5.12 0.512 2.816 2.752 6.592 1.152 9.728 2.688a23.552 23.552 0 0 0 11.264 1.792c0.768-0.064 1.856-0.256 2.24 0.128 2.88 2.944 7.424 0 10.24 3.008 6.528 0.576 13.12 0.896 19.584 2.752 4.16 1.28 8.768 0.64 13.184 1.6 5.312 1.28 11.072 0.896 16.64 1.472 3.648 0.32 7.232 0.192 10.88 0.256 0 1.152 0.64 1.6 1.792 1.536h78.976c1.152 0 1.856-0.384 1.856-1.536 8.768 0.448 17.408-1.6 26.112-1.28h4.8c1.216 0 1.856-0.448 1.792-1.664 3.904-0.256 7.808-0.704 11.712-1.472 6.144-1.28 12.544-0.96 18.688-2.944 3.072-1.024 6.592-0.832 9.856-1.664 3.84-0.896 7.872-1.92 12.032-1.6 0.448 0 1.152 0 1.408-0.192 2.048-2.752 5.44-1.472 8.192-2.752a21.184 21.184 0 0 1 9.472-1.664c0.448 0 1.024 0 1.472-0.192a23.488 23.488 0 0 1 9.344-3.008 62.08 62.08 0 0 0 12.992-3.392 56.96 56.96 0 0 1 9.6-2.56c0.64-0.128 1.472-0.128 1.856-0.576 1.856-1.92 4.48-1.92 6.592-2.56 4.224-1.088 8.256-2.688 12.416-3.968 1.408-0.32 3.008 0.064 4.16-0.704a25.792 25.792 0 0 1 10.88-4.416 3.392 3.392 0 0 0 1.792-0.576c1.92-1.152 3.648-2.56 6.08-2.816 3.328-0.384 6.592-2.048 9.472-3.52 2.56-1.28 5.312-2.24 7.872-3.52 1.92-1.024 4.096-2.304 6.464-2.752 3.456-0.576 5.76-3.52 9.216-4.288a25.984 25.984 0 0 0 7.488-3.2c3.712-2.048 7.616-3.84 11.392-5.632 2.432-1.28 5.184-2.304 7.168-3.712a54.336 54.336 0 0 1 9.536-5.312c4.224-1.92 8-4.608 12.16-6.4 3.712-1.728 7.04-4.416 10.624-6.4 1.856-1.088 3.52-2.688 5.312-3.584 1.984-1.024 3.968-2.176 5.824-3.392 2.496-1.728 5.44-2.752 7.552-4.864 1.92-1.92 4.48-2.56 6.4-4.288 2.368-1.984 5.504-2.944 7.68-5.12 0.768-0.768 1.216-1.472 2.24-1.472a3.52 3.52 0 0 0 2.688-1.856 6.272 6.272 0 0 1 2.944-2.496c3.456-1.216 5.248-4.48 8.448-6.144 1.984-0.896 3.648-2.752 5.504-4.096 3.2-2.176 6.144-4.48 9.152-6.848 1.664-1.28 3.136-3.584 4.8-4.096 3.712-1.152 4.8-5.12 8.192-6.592a11.328 11.328 0 0 0 3.2-2.368c2.56-2.88 5.76-5.248 8.768-8.064 1.792-1.92 4.288-2.816 6.08-4.864a52.608 52.608 0 0 1 6.848-6.912 57.984 57.984 0 0 0 6.144-5.888l10.944-10.88c3.648-3.52 7.104-7.104 10.752-10.56a45.824 45.824 0 0 0 5.888-6.848 37.056 37.056 0 0 1 6.592-6.976c1.92-1.536 2.496-3.84 4.224-5.44a31.104 31.104 0 0 0 6.656-7.552c1.92-3.392 5.312-5.504 7.168-8.96 1.28-2.432 3.84-4.096 5.376-6.528 1.6-2.624 3.712-4.992 5.696-7.36 2.176-2.56 4.672-5.376 6.144-8.32 1.536-3.2 4.288-5.12 5.76-8.32a49.536 49.536 0 0 1 5.696-8.064c1.472-1.856 2.368-3.84 3.584-5.76 1.92-2.944 3.968-5.76 6.016-8.64 0.768-1.28 0.96-2.56 2.048-3.84 1.92-2.048 4.16-4.48 3.648-7.872" fill="#3370FF"/>
                    <path d="M1022.49984 392.32c-0.384-0.576-0.832-0.576-1.408-0.704-1.664-0.512-3.456-0.896-4.928-1.728a30.08 30.08 0 0 0-5.12-2.944c-2.688-1.088-5.824-1.472-8.128-3.072-3.136-2.432-7.04-2.368-10.432-4.096a26.24 26.24 0 0 0-7.68-2.752c-1.984-0.32-4.096-1.28-6.08-1.92-2.688-0.832-5.568-1.792-8.32-2.56a163.84 163.84 0 0 1-12.992-3.712 22.848 22.848 0 0 0-9.216-1.536c-0.704-2.944-3.136-1.216-4.8-1.6-2.176 0-4.224-1.088-6.272-1.408-6.656-1.216-13.44-1.408-20.224-2.944-5.312-1.152-11.136-0.512-16.64-1.28-3.328-0.512-6.592-0.192-9.984-0.256 0-1.28-0.64-1.6-1.792-1.6h-32.128c-1.152 0-1.856 0.32-1.856 1.6-8.192-0.448-16.192 1.344-24.384 1.28h-4.864c-1.152 0-1.664 0.448-1.728 1.536-4.672-0.384-9.088 1.664-13.76 1.28a1.472 1.472 0 0 0-0.832 0.256c-3.584 2.56-7.936 1.664-11.84 2.944-3.072 1.024-6.784 0.896-9.728 1.984-2.368 0.832-4.992 1.472-7.296 2.432a21.312 21.312 0 0 1-9.152 1.792c0.064 0.64 0.192 1.28-0.64 1.408-1.792 0.128-3.456 1.088-5.12 1.472-4.8 1.28-9.344 3.072-14.016 4.672-4.096 1.472-7.872 3.648-11.904 4.608-4.608 1.088-7.808 4.736-12.672 5.312a8.064 8.064 0 0 0-4.16 1.472 15.04 15.04 0 0 1-4.48 2.752 30.08 30.08 0 0 0-7.296 3.584c-3.328 2.176-7.04 3.648-10.24 5.76-1.28 0.96-3.264 0.576-3.84 1.536-2.368 4.096-7.168 4.16-10.496 6.72-3.52 2.688-7.68 4.736-11.2 7.36-2.88 2.24-5.952 4.288-8.768 6.592-3.648 3.2-7.616 6.016-11.52 8.768-1.984 1.472-3.2 4.224-5.376 4.864-3.328 1.152-5.12 3.968-7.296 6.016-2.176 2.176-4.672 4.48-6.912 6.784-3.328 3.456-6.912 6.656-10.432 9.984-2.624 2.56-4.928 5.632-7.808 7.552-4.416 2.944-7.68 6.784-11.264 10.24-3.648 3.456-7.36 7.04-10.88 10.624-4.032 4.16-8.576 7.872-12.48 12.16-3.328 3.84-7.232 7.168-10.816 10.624-3.648 3.584-7.04 7.424-10.944 10.88-3.84 3.456-7.424 7.04-10.88 10.816-2.752 2.88-5.696 5.76-8.576 8.512-2.944 2.816-5.44 6.08-9.088 8.064-0.384 1.792-1.856 2.496-3.2 3.392-3.776 2.368-6.784 5.696-10.048 8.768-2.176 1.92-3.968 4.608-6.4 6.016-4.16 2.176-7.04 5.824-10.688 8.448-4.416 3.2-8.96 6.528-12.8 10.368-1.92 1.856-4.864 2.176-6.08 4.544-1.024 2.048-3.648 1.6-4.928 3.2-2.56 3.456-6.72 4.864-9.792 7.68-1.856 1.664-4.416 3.008-6.592 4.352-1.408 0.704-2.944 1.28-4.096 2.368a47.36 47.36 0 0 1-9.408 6.528c-1.472 0.896-3.456 1.472-4.544 2.752-2.048 2.176-4.928 3.2-7.232 5.12a29.568 29.568 0 0 1-7.744 4.672c-3.712 1.408-6.464 3.968-9.856 5.632-4.48 2.176-8.768 4.864-13.248 7.04-1.152 0.64-3.136 1.024-3.776 2.56 0 1.088 0.448 1.344 1.28 1.92 2.048 1.152 4.224 1.408 6.208 2.24 3.2 1.472 6.272 3.264 9.472 4.608 3.072 1.28 5.632 3.328 9.28 3.648 1.664 0.32 3.2 1.088 4.48 2.176 2.176 1.92 4.992 2.624 7.296 3.52 2.048 0.704 4.032 2.048 6.4 2.496 1.472 0.256 3.456 0.192 4.608 1.088 2.048 1.6 4.352 2.496 6.592 3.84 1.472 0.832 3.392-0.32 4.288 0.96 1.28 1.856 3.52 2.176 4.928 2.688 4.16 1.408 8 3.136 12.16 4.8 3.456 1.472 7.04 2.496 10.496 4.416 2.88 1.536 6.656 1.6 9.92 2.944 1.28 0.64 1.92 1.792 3.328 1.92 3.2 0.192 6.208 1.152 8.96 2.688 0.896 0.64 1.856 1.664 2.944 1.92 3.2 0.64 6.4 1.408 9.536 2.688 2.88 1.216 5.952 2.56 9.024 2.944 1.728 0.256 2.048 1.92 3.712 1.92 2.816 0 5.12 1.856 7.808 2.432 3.648 0.832 7.232 2.176 10.816 3.264 0.832 0.256 2.176-0.128 2.56 0.32 2.176 2.88 5.824 1.408 8.768 2.88 3.2 1.6 7.296 2.368 11.008 3.584 3.264 1.216 6.528 2.432 10.048 2.56a2.56 2.56 0 0 1 1.6 0.512 26.24 26.24 0 0 0 7.808 2.944c1.28 0.256 2.56 0.512 3.84 0.64 2.368 0.384 4.224 1.984 6.528 2.112 3.328 0.192 6.208 2.24 9.728 2.368 1.28 0.064 3.52-0.128 4.608 0.96 2.24 2.24 5.504 2.112 8.064 2.752 5.504 1.472 11.456 1.152 17.152 3.008 3.328 1.152 7.04 0.768 10.688 1.6 5.824 1.28 12.16 0.896 18.432 1.28 11.52 0.704 23.04 0.448 34.432-0.896 2.944-0.384 5.632-0.512 8.512-1.28 4.096-1.024 8.256-1.664 12.416-1.984 3.584-0.32 6.912-1.856 10.56-1.472a1.344 1.344 0 0 0 0.704-0.256c3.2-1.92 6.848-1.92 10.112-3.072 2.368-0.704 5.12-0.64 7.04-1.792a20.096 20.096 0 0 1 6.72-2.56c3.648-0.64 6.208-3.648 9.92-3.392l0.448-0.256c2.496-1.92 5.568-2.944 8.32-3.84 3.072-1.088 6.016-2.304 8.896-3.712 3.84-1.92 7.424-4.416 11.136-6.592 1.152-0.64 2.752 0.32 3.52-1.472 0.64-1.472 1.984-2.176 3.712-2.56 1.92-0.512 4.096-1.28 4.864-3.456 0.384-0.896 1.088-1.024 1.856-0.896 1.024 0 1.92-0.512 2.432-1.408 2.368-3.52 6.4-5.12 9.6-7.488 3.392-2.304 6.016-5.44 9.536-7.552 4.16-2.432 7.168-6.336 10.496-9.664 2.88-2.944 5.568-5.952 8.576-8.576 2.368-2.048 3.456-4.864 5.76-6.912 1.664-1.408 4.224-2.88 4.864-5.12 1.024-3.392 3.84-4.8 6.144-6.912a13.312 13.312 0 0 1 3.584-4.608l0.896-1.408c1.216-0.704 0.576-2.56 1.92-3.328 2.304-1.536 3.2-4.416 4.224-6.592 1.6-3.392 3.52-6.656 5.44-9.792 2.048-3.456 3.328-7.296 5.888-10.496 1.92-2.496 3.136-5.76 4.48-8.704a369.92 369.92 0 0 1 7.808-15.104 130.56 130.56 0 0 0 4.48-9.088c1.408-3.2 3.2-6.208 4.736-9.28 1.472-3.2 3.52-6.144 4.672-9.28 1.472-3.904 3.648-7.168 5.312-10.88 0.512-1.344 0.384-2.944 1.28-3.904a18.688 18.688 0 0 0 4.16-7.168c1.472-3.84 4.736-6.912 5.12-11.2l0.256-0.128c1.472-1.152 1.984-2.944 2.816-4.48 1.28-2.432 1.92-5.248 3.52-7.488 2.496-3.52 3.904-7.424 5.824-11.2 1.28-2.304 2.176-4.928 3.52-7.04 2.176-3.456 3.648-7.36 5.76-10.752a43.776 43.776 0 0 0 3.584-7.68c0.64-1.792 1.92-3.52 3.008-5.12 1.984-3.072 3.392-6.592 5.952-9.344 1.088-1.152 1.024-2.752 2.304-4.096 2.24-2.176 3.392-5.12 5.12-7.68 1.28-1.92 2.24-4.224 3.776-5.696a47.232 47.232 0 0 0 7.04-9.344c1.984-3.2 4.544-6.016 6.848-8.704 3.712-4.48 7.68-8.96 11.84-13.44l11.136-11.776c2.176-2.304 1.6-2.816 0-4.416" fill="#133C9A"/>
                  </svg>
                </div>
                <span class="fac-share-channel-btn__label">飞书</span>
              </button>

              <button type="button" class="fac-share-channel-btn" @click="handleCopy">
                <div class="fac-share-channel-btn__icon fac-share-channel-btn__icon--copy">
                  <span v-if="!copied" class="mso">link</span>
                  <span v-else class="mso" style="color:#22c55e">check</span>
                </div>
                <span class="fac-share-channel-btn__label">{{ copied ? '已复制' : '复制链接' }}</span>
              </button>

              <button type="button" class="fac-share-channel-btn" @click="downloadShareCard">
                <div class="fac-share-channel-btn__icon fac-share-channel-btn__icon--download">
                  <span v-if="screenshotLoading" class="mso" style="color:#6462d2">hourglass_bottom</span>
                  <span v-else class="mso" style="color:#6462d2">download</span>
                </div>
                <span class="fac-share-channel-btn__label">{{ screenshotLoading ? '生成中' : '保存分享图' }}</span>
              </button>
            </div>

            <div class="fac-share-url-row">
              <input
                type="text"
                class="fac-share-url-input"
                :value="currentUrl"
                readonly
                ref="urlInputRef"
              />
            </div>
          </div>
        </div>
      </div>
    </Transition>

  </Teleport>
</template>

<script setup>
import { ref, watch, nextTick, computed } from 'vue'
import html2canvas from 'html2canvas'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
  shareData: {
    type: Object,
    default: () => ({
      title: 'FacSstock - 智能股票策略分析',
      description: '基于AI的股票策略分析工具',
      shortUrl: '',
      stocks: [],
      confidence: 0,
      stance: 'neutral',
      stanceText: '中性',
      marketCommentary: '',
    }),
  },
})

const emit = defineEmits(['close'])

const copied = ref(false)
const urlInputRef = ref(null)
const shareCardRef = ref(null)
const screenshotLoading = ref(false)

const currentUrl = computed(() => props.shareData.shortUrl || window.location.href)

function toPctNumber(value) {
  const num = Number(value)
  return Number.isFinite(num) ? num : 0
}

function formatPct(value) {
  const num = toPctNumber(value)
  return `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`
}

watch(() => props.visible, (val) => {
  if (val) {
    copied.value = false
  }
})

async function handleWeChat() {
  // 优先使用系统原生分享面板（手机端会列出所有支持分享的 App，包括微信）
  if (navigator.share) {
    try {
      await navigator.share({
        title: props.shareData.title,
        text: props.shareData.description || `${props.shareData.confidence}% 信心`,
        url: currentUrl.value,
      })
      return
    } catch (err) {
      // 用户取消或分享失败，继续尝试其他方式
      if (err.name === 'AbortError') return
    }
  }

  // 回退：在支持 weixin:// scheme 的浏览器尝试直接调起（部分 Android 浏览器有效）
  const iframe = document.createElement('iframe')
  iframe.style.display = 'none'
  iframe.src = 'weixin://'
  document.body.appendChild(iframe)
  setTimeout(() => document.body.removeChild(iframe), 1000)

  // 如果 iframe 方式失败（iOS 大多数情况），提示用户
  setTimeout(() => {
    if (!document.hidden) {
      // 提示长按复制链接后手动在微信打开
      handleCopy()
    }
  }, 1500)
}

function handleFeishu() {
  // 优先使用系统原生分享面板
  if (navigator.share) {
    navigator.share({
      title: props.shareData.title,
      text: props.shareData.description || `${props.shareData.confidence}% 信心`,
      url: currentUrl.value,
    }).catch(() => {})
    return
  }

  const encodedTitle = encodeURIComponent(props.shareData.title)
  const encodedDesc = encodeURIComponent(props.shareData.description || `${props.shareData.confidence}% 信心`)
  const encodedUrl = encodeURIComponent(currentUrl.value)

  // 移动端：使用飞书 universal link（可被系统识别并打开飞书 App）
  const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent)
  if (isMobile) {
    // 尝试调起飞书 App
    const iframe = document.createElement('iframe')
    iframe.style.display = 'none'
    iframe.src = 'feishu://'
    document.body.appendChild(iframe)
    setTimeout(() => document.body.removeChild(iframe), 1000)

    // 同时打开网页版分享链接作为兜底
    const feishuWebUrl = `https://applink.feishu.cn/client/share/open?title=${encodedTitle}&desc=${encodedDesc}&url=${encodedUrl}`
    setTimeout(() => window.open(feishuWebUrl, '_blank'), 500)
  } else {
    // 桌面端：打开飞书网页版分享链接
    const feishuWebUrl = `https://applink.feishu.cn/client/share/open?title=${encodedTitle}&desc=${encodedDesc}&url=${encodedUrl}`
    window.open(feishuWebUrl, '_blank', 'width=600,height=500')
  }
}

async function handleCopy() {
  try {
    await navigator.clipboard.writeText(currentUrl.value)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch {
    if (urlInputRef.value) {
      urlInputRef.value.select()
      document.execCommand('copy')
      copied.value = true
      setTimeout(() => { copied.value = false }, 2000)
    }
  }
}

async function downloadShareCard() {
  if (!shareCardRef.value || screenshotLoading.value) return
  screenshotLoading.value = true
  try {
    const card = shareCardRef.value
    const canvas = await html2canvas(card, {
      backgroundColor: '#ffffff',
      scale: 2,
      useCORS: true,
      logging: false,
    })
    const link = document.createElement('a')
    link.download = `facSstock-${Date.now()}.png`
    link.href = canvas.toDataURL('image/png')
    link.click()
  } catch (e) {
    console.error('[ShareModal] 截图失败:', e)
  } finally {
    screenshotLoading.value = false
  }
}

</script>

<style scoped>
.fac-share-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  z-index: 300;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding: 0;
}

.fac-share-sheet {
  background: var(--surface-container-lowest, #fff);
  border-radius: 20px 20px 0 0;
  width: 100%;
  max-width: 480px;
  max-height: 90vh;
  overflow: hidden;
  box-shadow: 0 -4px 40px rgba(0, 0, 0, 0.15);
}

.fac-share-sheet__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 20px 16px;
  border-bottom: 1px solid rgba(196, 198, 208, 0.2);
}

.fac-share-sheet__title {
  font-family: var(--font-headline, -apple-system, sans-serif);
  font-size: 1rem;
  font-weight: 800;
  color: var(--on-surface, #1e1633);
  margin: 0;
  letter-spacing: -0.02em;
}

.fac-share-sheet__close {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--surface-dim, #c7c2eb);
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--on-surface-variant, #464455);
  transition: background 0.15s;
}
.fac-share-sheet__close:hover { background: var(--surface-container-highest, #d5d0ff); }
.fac-share-sheet__close .mso { font-size: 16px; }

.fac-share-sheet__body {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-height: calc(90vh - 60px);
  overflow-y: auto;
}

/* 精简分享卡片：信心指数 + 推荐股票 */
.fac-share-card {
  background: var(--surface-container-low, #ede8ff);
  border-radius: 16px;
  padding: 16px;
  display: flex;
  gap: 16px;
  align-items: stretch;
}

.fac-share-card__left {
  width: 110px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.fac-share-card__divider {
  width: 1px;
  background: rgba(196, 198, 208, 0.3);
  align-self: stretch;
  flex-shrink: 0;
}

.fac-share-card__right {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.fac-share-card__section-title {
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--primary-container, #5a34a8);
  margin: 0;
  display: flex;
  align-items: center;
  gap: 4px;
}

.fac-share-card__stance {
  text-align: center;
}

.fac-share-gauge {
  width: 90px;
  height: 90px;
}

.fac-share-gauge__svg {
  width: 100%;
  height: 100%;
}

.fac-share-gauge__track {
  fill: none;
  stroke: #e5e0ff;
  stroke-width: 8;
  transform-origin: center;
}

.fac-share-gauge__arc {
  fill: none;
  stroke-width: 8;
  stroke-linecap: round;
  transform-origin: center;
  transform: rotate(-90deg);
  transition: stroke-dasharray 0.8s ease;
}

.fac-share-gauge__arc--bull { stroke: #f23645; }
.fac-share-gauge__arc--bear { stroke: #f23645; }
.fac-share-gauge__arc--neutral { stroke: #f23645; }

.fac-share-gauge__num {
  font-size: 22px;
  font-weight: 800;
  fill: var(--on-surface, #1e1633);
  text-anchor: middle;
  dominant-baseline: auto;
}

.fac-share-gauge__unit {
  font-size: 10px;
  fill: var(--on-surface-variant, #464455);
  text-anchor: middle;
  dominant-baseline: auto;
}

.fac-share-stance-tag {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: #f23645;
  background: rgba(242, 54, 69, 0.15);
}

.fac-share-stance-tag--bull { }
.fac-share-stance-tag--bear { }
.fac-share-stance-tag--neutral { }

.fac-share-card__commentary {
  font-size: 10px;
  color: var(--on-surface-variant, #464455);
  margin: 0;
  text-align: center;
  line-height: 1.4;
  overflow: visible;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  word-break: break-word;
}

.fac-share-stocks {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
  overflow-y: auto;
}

.fac-share-stock-item {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  background: var(--surface-container-lowest, #fff);
  border-radius: 10px;
  padding: 8px 12px;
  gap: 4px;
}

.fac-share-stock-item__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.fac-share-stock-item__left {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.fac-share-stock-item__name {
  font-size: 13px;
  font-weight: 700;
  color: var(--on-surface, #1e1633);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.fac-share-stock-item__code {
  font-size: 10px;
  color: var(--on-surface-variant, #464455);
  font-family: var(--font-mono, monospace);
}

.fac-share-stock-item__chg {
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
  padding: 2px 8px;
  border-radius: 6px;
  color: #f23645;
  background: rgba(242, 54, 69, 0.12);
}

.fac-share-stock-item__reason {
  font-size: 11px;
  color: var(--on-surface-variant, #464455);
  line-height: 1.4;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  margin-top: 2px;
  padding-left: 2px;
}

.fac-share-stocks__empty {
  font-size: 12px;
  color: var(--on-surface-variant, #464455);
  text-align: center;
  margin: 0;
  padding: 16px 0;
}

.fac-share-channels {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.fac-share-channel-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  border-radius: 12px;
  transition: background 0.15s;
}
.fac-share-channel-btn:hover { background: var(--surface-container-low, #ede8ff); }
.fac-share-channel-btn:active { background: var(--surface-container, #e5e0ff); }

.fac-share-channel-btn__icon {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
}

.fac-share-channel-btn__icon--wechat { background: #f0f9f5; }
.fac-share-channel-btn__icon--wechat svg { width: 28px; height: 28px; }
.fac-share-channel-btn__icon--feishu { background: #eef2ff; }
.fac-share-channel-btn__icon--feishu svg { width: 28px; height: 28px; }
.fac-share-channel-btn__icon--native { background: var(--primary-container, #5a34a8); color: #fff; }
.fac-share-channel-btn__icon--copy { background: var(--surface-container-high, #ddd8ff); color: var(--on-surface-variant, #464455); }
.fac-share-channel-btn__icon--download { background: var(--surface-container-high, #ddd8ff); color: var(--on-surface-variant, #464455); }
.fac-share-channel-btn__icon--native .mso { font-size: 24px; }

.fac-share-channel-btn__label {
  font-size: 11px;
  color: var(--on-surface-variant, #464455);
  font-family: var(--font-body, -apple-system, sans-serif);
}

.fac-share-url-row {
  display: flex;
  gap: 8px;
}

.fac-share-url-input {
  flex: 1;
  height: 40px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid rgba(196, 198, 208, 0.3);
  background: var(--surface-container-low, #ede8ff);
  color: var(--on-surface-variant, #464455);
  font-size: 12px;
  font-family: var(--font-mono, monospace);
  outline: none;
  min-width: 0;
}

.share-modal-enter-active,
.share-modal-leave-active {
  transition: opacity 0.25s ease;
}
.share-modal-enter-active .fac-share-sheet,
.share-modal-leave-active .fac-share-sheet {
  transition: transform 0.3s cubic-bezier(0.32, 0.72, 0, 1);
}
.share-modal-enter-active .fac-share-sheet {
  transform: translateY(100%);
}
.share-modal-leave-active .fac-share-sheet {
  transform: translateY(100%);
}
.share-modal-enter-from,
.share-modal-leave-to {
  opacity: 0;
}

@media (min-width: 480px) {
  .fac-share-overlay {
    align-items: center;
  }
  .fac-share-sheet {
    border-radius: 20px;
    max-height: 85vh;
  }
  .share-modal-enter-active .fac-share-sheet,
  .share-modal-leave-active .fac-share-sheet {
    transform: translateY(0);
  }
  .share-modal-enter-from .fac-share-sheet,
  .share-modal-leave-to .fac-share-sheet {
    transform: translateY(40px);
    opacity: 0;
  }
}
</style>
