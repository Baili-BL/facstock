"""
AI 分析服务 - 使用腾讯混元 OpenAI 兼容 API
"""
import os
import json
import requests
from datetime import datetime

# 腾讯混元 OpenAI 兼容 API 配置
HUNYUAN_API_KEY = os.environ.get('HUNYUAN_API_KEY', 'sk-YDYlUOiUi5VzumSjhppTWry9bBfWJFbN7IsCLN0XpD1ysM0Z')
HUNYUAN_BASE_URL = "https://api.hunyuan.cloud.tencent.com/v1"


def fetch_market_news(scan_date: str = None):
    """
    获取市场新闻和政策消息
    
    Args:
        scan_date: 扫描日期，格式 YYYY-MM-DD，新闻必须早于或等于此日期
    """
    news_list = []
    
    # 解析扫描日期
    if scan_date:
        try:
            scan_dt = datetime.strptime(scan_date[:10], '%Y-%m-%d')
        except:
            scan_dt = datetime.now()
    else:
        scan_dt = datetime.now()
    
    try:
        import akshare as ak
        
        # 辅助函数：从 DataFrame 行中提取时间
        def extract_time(row):
            for col in ['发布时间', '时间', 'time', 'datetime', '日期']:
                if col in row.index:
                    val = row[col]
                    if val is not None and str(val).strip():
                        return str(val).strip()
            return datetime.now().strftime('%m-%d %H:%M')
        
        # 辅助函数：从 DataFrame 行中提取内容
        def extract_content(row):
            for col in ['内容', '标题', 'content', 'title', '新闻内容']:
                if col in row.index:
                    val = row[col]
                    if val is not None and str(val).strip():
                        return str(val).strip()[:120]
            return ''
        
        # 1. 财联社电报 - 最快的财经新闻
        try:
            df = ak.stock_telegraph_cls()
            if df is not None and not df.empty:
                print(f"[财联社] 列名: {df.columns.tolist()}")
                for _, row in df.head(8).iterrows():
                    time_str = extract_time(row)
                    title = extract_content(row)
                    if title and len(title) > 5:
                        news_list.append({
                            'time': time_str,
                            'title': title,
                            'source': '财联社'
                        })
        except Exception as e:
            print(f"获取财联社新闻失败: {e}")
        
        # 2. 东方财富全球财经快讯
        try:
            df = ak.stock_info_global_em()
            if df is not None and not df.empty:
                print(f"[东方财富] 列名: {df.columns.tolist()}")
                for _, row in df.head(8).iterrows():
                    time_str = extract_time(row)
                    title = extract_content(row)
                    if title and len(title) > 5:
                        news_list.append({
                            'time': time_str,
                            'title': title,
                            'source': '东方财富'
                        })
        except Exception as e:
            print(f"获取东方财富新闻失败: {e}")
        
        # 3. 同花顺财经新闻
        try:
            df = ak.stock_info_global_ths()
            if df is not None and not df.empty:
                print(f"[同花顺] 列名: {df.columns.tolist()}")
                for _, row in df.head(5).iterrows():
                    time_str = extract_time(row)
                    title = extract_content(row)
                    if title and len(title) > 5:
                        news_list.append({
                            'time': time_str,
                            'title': title,
                            'source': '同花顺'
                        })
        except Exception as e:
            print(f"获取同花顺新闻失败: {e}")
        
        # 4. 富途资讯
        try:
            df = ak.stock_info_global_futu()
            if df is not None and not df.empty:
                print(f"[富途] 列名: {df.columns.tolist()}")
                for _, row in df.head(4).iterrows():
                    time_str = extract_time(row)
                    title = extract_content(row)
                    if title and len(title) > 5:
                        news_list.append({
                            'time': time_str,
                            'title': title,
                            'source': '富途资讯'
                        })
        except Exception as e:
            print(f"获取富途新闻失败: {e}")
        
    except ImportError:
        print("akshare 未安装，跳过新闻获取")
    except Exception as e:
        print(f"获取新闻失败: {e}")
    
    # 去重（按标题）
    seen_titles = set()
    unique_news = []
    for news in news_list:
        title = news.get('title', '')[:50]  # 用前50字符判断重复
        if title not in seen_titles and len(title) > 5:
            seen_titles.add(title)
            unique_news.append(news)
    
    return unique_news[:15]  # 最多返回15条

# 钧哥低吸策略 Prompt 模板
JUNGE_STRATEGY_PROMPT = """
你是一位专业的A股技术分析师。请基于下方提供的扫描数据和市场新闻进行分析。

## 重要时间说明
- 股票扫描时间：{current_time}
- 下方新闻均为扫描时间当天或之前的消息
- 分析时请注意：新闻发布时间 ≤ 股票数据更新时间

## 最新市场消息（扫描日期及之前）
{news_data}

## 选股策略：钧哥低吸策略
优先级：政策利好 > 布林带收缩 > 量价配合 > 资金流向（CMF）

### 关键指标解读
- **收缩率**：越高表示布林带越收紧，突破信号越强
- **带宽%**：<5% 表示极度收缩，可能即将突破
- **量比**：>1.5 表示放量，配合收缩更佳
- **CMF**：>0 资金流入，<0 资金流出
- **RSV**：<20 超卖区，>80 超买区

## 扫描结果数据
{scan_data}

## 任务要求
请从上述扫描结果中，结合最新市场消息，筛选 2-3 只股票：

### 筛选条件
1. **必须是主板股票**（代码以 60 或 00 开头）
2. **政策关联**：优先选择与最新政策/新闻相关的板块
3. **评分优先**：优先选择 S级 或 A级
4. **技术形态**：收缩率高 + 带宽低 = 布林带收紧，突破概率大
5. **量价配合**：量比>1 且 CMF>0 更佳

### 输出格式

#### 一、今日重点消息
从上方新闻列表中，原文复制 2-3 条最重要的消息（必须是原文，不能改写）：

1. 【新闻X】原文复制：「[时间] 新闻标题」（来源）
   - 影响板块：xxx

2. 【新闻X】原文复制：「[时间] 新闻标题」（来源）
   - 影响板块：xxx

#### 二、精选股票（2-3只）

**1. 股票名称（代码）** - 评分X分（X级）
- 所属板块：xxx
- 📰 关联消息：
  - 引用【新闻X】原文：「[时间] 完整的新闻标题」（来源）
  - 关联分析：解释为什么这条消息利好该股票
- 📊 技术指标（从扫描数据复制）：
  - 收缩率：XX% | 带宽：XX% | 量比：XX | CMF：XX | RSV：XX
- 💡 操作建议：低吸策略
- ⚠️ 风险提示：风险点

**2. 股票名称（代码）** - 评分X分（X级）
...（同上格式）

**3. 股票名称（代码）** - 评分X分（X级）
...（如无关联消息：📰 关联消息：无直接相关新闻，基于纯技术面选择）

#### 三、风险提示
整体市场风险

### ⚠️ 严格规则（违反将导致分析无效）
1. **新闻必须原文引用**：从上方新闻列表复制原文，格式「[时间] 标题」（来源），禁止改写或编造
2. **技术数据必须真实**：从扫描结果表格复制真实数值，禁止编造数字
3. **股票必须来自列表**：只能推荐扫描结果中存在的股票
4. **无关联就说无关联**：如果没有相关新闻，直接写"无直接相关新闻"

## 重要提醒
- 股票必须来自扫描数据，不要推荐数据中没有的股票
- 技术指标数值必须引用扫描数据中的真实数值
- 新闻解读要客观，不要过度解读
"""


class AIAnalysisService:
    """AI 分析服务"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key or HUNYUAN_API_KEY
        self.base_url = HUNYUAN_BASE_URL
    
    def is_configured(self):
        """检查是否已配置"""
        return bool(self.api_key)
    
    def analyze_stocks(self, scan_data: dict, current_time: str) -> dict:
        """
        分析股票数据
        
        Args:
            scan_data: 扫描结果数据
            current_time: 当前时间字符串
            
        Returns:
            分析结果字典
        """
        if not self.is_configured():
            return {
                'success': False,
                'error': 'AI 服务未配置'
            }
        
        try:
            # 格式化扫描数据
            formatted_data = self._format_scan_data(scan_data)
            
            # 获取扫描日期
            scan_date = scan_data.get('scan_time', '')[:10] if scan_data.get('scan_time') else None
            
            # 获取最新新闻（早于扫描日期）
            news_data = self._format_news_data(scan_date)
            
            # 构建 prompt
            prompt = JUNGE_STRATEGY_PROMPT.format(
                current_time=current_time,
                news_data=news_data,
                scan_data=formatted_data
            )
            
            # 调用 OpenAI 兼容 API
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'model': 'hunyuan-lite',  # 免费模型
                'messages': [
                    {
                        'role': 'system',
                        'content': '你是一位严谨的A股技术分析助手。你只能基于用户提供的扫描数据进行分析，绝对不能编造任何数据中没有的股票、价格、涨幅等信息。如果数据不足，请如实说明。'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'temperature': 0.3,  # 降低温度，减少幻觉
                'max_tokens': 2000,
                'stream': False
            }
            
            response = requests.post(
                f'{self.base_url}/chat/completions',
                headers=headers,
                json=payload,
                timeout=120
            )
            
            result = response.json()
            
            # 检查错误
            if 'error' in result:
                return {
                    'success': False,
                    'error': f"API 错误: {result['error'].get('message', '未知错误')}"
                }
            
            # 提取回复
            if 'choices' in result and len(result['choices']) > 0:
                analysis = result['choices'][0].get('message', {}).get('content', '')
                usage = result.get('usage', {})
                
                return {
                    'success': True,
                    'analysis': analysis,
                    'model': result.get('model', 'hunyuan-lite'),
                    'tokens_used': usage.get('total_tokens', 0)
                }
            
            return {
                'success': False,
                'error': f'API 返回格式异常: {json.dumps(result, ensure_ascii=False)[:200]}'
            }
            
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'AI 分析超时，请稍后重试'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'AI 分析失败: {str(e)}'
            }
    
    def _format_news_data(self, scan_date: str = None) -> str:
        """
        格式化新闻数据
        
        Args:
            scan_date: 扫描日期，新闻必须早于此日期
        """
        news_list = fetch_market_news(scan_date)
        
        if not news_list:
            return "【暂无最新消息】"
        
        lines = [f"以下是 {scan_date or '今日'} 及之前的真实新闻，引用时必须原文复制：\n"]
        for i, news in enumerate(news_list, 1):
            time_str = news.get('time', '')
            title = news.get('title', '')
            source = news.get('source', '')
            # 格式便于复制：【新闻1】「[时间] 标题」（来源）
            lines.append(f"【新闻{i}】「[{time_str}] {title}」（{source}）")
        
        lines.append("\n★ 引用规则：必须原文复制「」内的内容，包括时间和标题，禁止改写")
        
        return "\n".join(lines)
    
    def _format_scan_data(self, scan_data: dict) -> str:
        """格式化扫描数据为文本"""
        if not scan_data or 'results' not in scan_data:
            return "【无扫描数据】"
        
        results = scan_data.get('results', [])
        if not results:
            return "【无扫描数据】"
        
        # 只取评分较高的股票，优先主板
        main_board_stocks = [s for s in results if s.get('code', '').startswith(('60', '00'))]
        other_stocks = [s for s in results if not s.get('code', '').startswith(('60', '00'))]
        
        # 按评分排序（字段名是 total_score）
        main_board_stocks = sorted(main_board_stocks, key=lambda x: x.get('total_score', 0), reverse=True)[:15]
        other_stocks = sorted(other_stocks, key=lambda x: x.get('total_score', 0), reverse=True)[:5]
        
        lines = [f"共扫描到 {len(results)} 只股票，以下为筛选结果：\n"]
        
        if main_board_stocks:
            lines.append("## 主板股票（可选范围）")
            lines.append("| 序号 | 股票 | 代码 | 板块 | 评分 | 收缩率 | 带宽% | 量比 | CMF | RSV |")
            lines.append("|------|------|------|------|------|--------|-------|------|-----|-----|")
            
            for i, stock in enumerate(main_board_stocks, 1):
                code = stock.get('code', '')
                name = stock.get('name', '')
                sector = stock.get('sector', '')
                score = stock.get('total_score', 0)  # 使用 total_score
                grade = stock.get('grade', '')
                squeeze_ratio = stock.get('squeeze_ratio', 0)
                bb_width_pct = stock.get('bb_width_pct', 0)
                volume_ratio = stock.get('volume_ratio', 0)
                cmf = stock.get('cmf', 0)
                rsv = stock.get('rsv', 0)
                
                lines.append(f"| {i} | {name} | {code} | {sector} | {score}({grade}) | {squeeze_ratio:.1f}% | {bb_width_pct:.2f}% | {volume_ratio:.2f} | {cmf:.3f} | {rsv:.1f} |")
            
            lines.append("")
        
        if other_stocks:
            lines.append("## 创业板/科创板（仅供参考）")
            for i, stock in enumerate(other_stocks, 1):
                code = stock.get('code', '')
                name = stock.get('name', '')
                score = stock.get('total_score', 0)  # 使用 total_score
                lines.append(f"- {name}（{code}）评分{score}分")
            lines.append("")
        
        lines.append("【注意：请仅从上述主板股票中选择推荐】")
        
        return "\n".join(lines)


# 单例实例
ai_service = AIAnalysisService()


def get_ai_service(api_key=None):
    """获取 AI 服务实例"""
    global ai_service
    if api_key:
        ai_service = AIAnalysisService(api_key)
    return ai_service
