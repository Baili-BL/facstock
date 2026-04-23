import { ref, watch } from 'vue'

const DEFAULT_SHARE_TITLE = 'FacSstock - 智能股票策略分析'
const DEFAULT_SHARE_DESC = '基于AI的股票策略分析工具，支持布林带策略、AI选股、主题投资等多种功能。'
const DEFAULT_SHARE_IMAGE = '/og-default.png'
const DEFAULT_SHARE_URL = window.location.origin

const shareState = ref({
  title: DEFAULT_SHARE_TITLE,
  description: DEFAULT_SHARE_DESC,
  image: DEFAULT_SHARE_IMAGE,
  url: DEFAULT_SHARE_URL,
})

function updateMeta(name, content) {
  let el = document.querySelector(`meta[property="${name}"]`)
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute('property', name)
    document.head.appendChild(el)
  }
  el.setAttribute('content', content)
}

function updateMetaName(name, content) {
  let el = document.querySelector(`meta[name="${name}"]`)
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute('name', name)
    document.head.appendChild(el)
  }
  el.setAttribute('content', content)
}

export function useShare(options = {}) {
  const { title, description, image, url } = options

  const resolvedTitle = title || shareState.value.title
  const resolvedDesc = description || shareState.value.description
  const resolvedImage = image || shareState.value.image
  const resolvedUrl = url || shareState.value.url || (window.location.href)

  shareState.value = { title: resolvedTitle, description: resolvedDesc, image: resolvedImage, url: resolvedUrl }

  updateMeta('og:title', resolvedTitle)
  updateMeta('og:description', resolvedDesc)
  updateMeta('og:image', resolvedImage)
  updateMeta('og:url', resolvedUrl)
  updateMetaName('twitter:title', resolvedTitle)
  updateMetaName('twitter:description', resolvedDesc)
  updateMetaName('twitter:image', resolvedImage)

  const canUseNativeShare = 'share' in navigator
  const isWeChat = /micromessenger/i.test(navigator.userAgent)
  const isFeishu = /feishu|larksuite/i.test(navigator.userAgent)
  const isDesktopFeishu = /desktop.*feishu|feishu.*desktop/i.test(navigator.userAgent)

  async function nativeShare() {
    if (!canUseNativeShare) {
      throw new Error('Browser does not support Web Share API')
    }
    await navigator.share({
      title: resolvedTitle,
      text: resolvedDesc,
      url: resolvedUrl,
    })
  }

  function shareToWeChat() {
    if (!isWeChat) {
      return { type: 'qr', url: resolvedUrl }
    }
    return { type: 'jssdk', url: resolvedUrl }
  }

  function shareToFeishu() {
    const encodedTitle = encodeURIComponent(resolvedTitle)
    const encodedDesc = encodeURIComponent(resolvedDesc)
    const encodedUrl = encodeURIComponent(resolvedUrl)
    const feishuUrl = `https://applink.feishu.cn/client/share/open?appId=&title=${encodedTitle}&desc=${encodedDesc}&url=${encodedUrl}`
    window.open(feishuUrl, '_blank', 'width=600,height=500')
    return feishuUrl
  }

  function getShareUrl() {
    return resolvedUrl
  }

  function getShareData() {
    return {
      title: resolvedTitle,
      description: resolvedDesc,
      image: resolvedImage,
      url: resolvedUrl,
    }
  }

  return {
    shareState,
    canUseNativeShare,
    isWeChat,
    isFeishu,
    isDesktopFeishu,
    nativeShare,
    shareToWeChat,
    shareToFeishu,
    getShareUrl,
    getShareData,
  }
}

export function getDefaultShareData() {
  return {
    title: DEFAULT_SHARE_TITLE,
    description: DEFAULT_SHARE_DESC,
    image: DEFAULT_SHARE_IMAGE,
    url: DEFAULT_SHARE_URL,
  }
}
