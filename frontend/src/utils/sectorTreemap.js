/**
 * 二分递归矩形树图（无第三方依赖），面积与 weight 成正比。
 * @param {{ weight: number, data: unknown }[]} items
 * @param {number} x y w h 画布内矩形
 * @param {boolean} vertical 当前切分方向
 * @returns {{ x: number, y: number, w: number, h: number, data: unknown }[]}
 */
export function layoutBinaryTreemap(items, x, y, w, h, vertical = true) {
  const list = items
    .map((it) => ({
      weight: Math.max(Number(it.weight) || 0, 1e-9),
      data: it.data,
    }))
    .sort((a, b) => b.weight - a.weight)

  if (!list.length) return []

  function go(nodes, rx, ry, rw, rh, vert) {
    if (nodes.length === 1) {
      const n = nodes[0]
      return [{ x: rx, y: ry, w: rw, h: rh, data: n.data }]
    }
    const total = nodes.reduce((s, n) => s + n.weight, 0)
    let acc = 0
    let split = 1
    const half = total / 2
    for (let i = 0; i < nodes.length - 1; i++) {
      acc += nodes[i].weight
      if (acc >= half) {
        split = i + 1
        break
      }
    }
    const left = nodes.slice(0, split)
    const right = nodes.slice(split)
    const leftSum = left.reduce((s, n) => s + n.weight, 0)
    const ratio = leftSum / total

    if (vert) {
      const w1 = rw * ratio
      return [
        ...go(left, rx, ry, w1, rh, !vert),
        ...go(right, rx + w1, ry, rw - w1, rh, !vert),
      ]
    }
    const h1 = rh * ratio
    return [
      ...go(left, rx, ry, rw, h1, !vert),
      ...go(right, rx, ry + h1, rw, rh - h1, !vert),
    ]
  }

  return go(list, x, y, w, h, vertical)
}

function mixRgb(light, dark, t) {
  const a = (x) => Math.round(light[0] + (dark[0] - light[0]) * x)
  const b = (x) => Math.round(light[1] + (dark[1] - light[1]) * x)
  const c = (x) => Math.round(light[2] + (dark[2] - light[2]) * x)
  return `rgb(${a(t)}, ${b(t)}, ${c(t)})`
}

/** A 股配色：红涨绿跌（TradingView #f23645 / #089981）；|change| 越大颜色越深 */
export function fillForSectorChange(change, maxAbs) {
  const upLight = [255, 241, 242]
  const upDark = [242, 54, 69]
  const dnLight = [232, 248, 245]
  const dnDark = [8, 153, 129]
  const m = Math.max(Number(maxAbs) || 0, 0.01)
  const t = Math.min(Math.abs(Number(change) || 0) / m, 1)
  if (change >= 0) return mixRgb(upLight, upDark, t * 0.85 + 0.08)
  return mixRgb(dnLight, dnDark, t * 0.85 + 0.08)
}

/** change 为涨跌幅数值（百分点，如 5.97 表示 5.97%） */
export function textColorForChange(change) {
  const c = Number(change) || 0
  if (c >= 2) return '#b71c2c'
  if (c >= 0) return '#2a1418'
  if (c <= -2) return '#047857'
  return '#0d3020'
}

/** 主力净流入（亿）：正=红，负=绿（TV 色值） */
export function fillForNetYi(netYi, maxAbs) {
  const upLight = [255, 241, 242]
  const upDark = [242, 54, 69]
  const dnLight = [232, 248, 245]
  const dnDark = [8, 153, 129]
  const m = Math.max(Number(maxAbs) || 0, 0.01)
  const t = Math.min(Math.abs(Number(netYi) || 0) / m, 1)
  const ny = Number(netYi) || 0
  if (ny >= 0) return mixRgb(upLight, upDark, t * 0.85 + 0.08)
  return mixRgb(dnLight, dnDark, t * 0.85 + 0.08)
}

export function textColorForNetYi(netYi) {
  const n = Number(netYi) || 0
  const a = Math.abs(n)
  if (n >= 0 && a >= 40) return '#b71c2c'
  if (n >= 0) return '#2a1418'
  if (n < 0 && a >= 40) return '#047857'
  return '#0d3020'
}
