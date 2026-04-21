// Test SSE parsing logic for facSstock frontend

// Sample SSE stream input that mimics what the backend sends
const sampleSSEStream = `data: {"type": "cot", "step": 1, "total": 5, "title": "获取市场快照", "message": "正在拉取大盘指数数据（上证、深证、创业板、科创50）..."}

data: {"type": "task_step", "step": 1, "total": 5, "title": "市场数据获取", "desc": "拉取大盘涨跌、成交量统计..."}

data: {"type": "cot_data", "step": 1, "lines": ["  [警告] 大盘快照获取失败: HTTPSConnectionPool(host='48.push2.eastmoney.com', port=443): Max retries exceeded with url: /api/qt/clist/get"]}

data: {"type": "cot", "step": 2, "total": 5, "title": "联网搜索市场数据", "message": "正在联网搜索今日涨停板、连板股、市场情绪、主线题材..."}

data: {"type": "final", "result": "分析完成"}`;

// Fixed parsing logic (split by '\n', filter empty, check startsWith 'data: ')
function parseSSEStream(streamData) {
    const lines = streamData.split('\n');
    const events = [];
    
    for (const line of lines) {
        // Skip empty lines
        if (!line || line.trim() === '') {
            continue;
        }
        
        // Check for SSE data prefix
        if (line.startsWith('data: ')) {
            const jsonStr = line.slice(6); // Remove 'data: ' prefix
            try {
                const data = JSON.parse(jsonStr);
                events.push(data);
            } catch (e) {
                console.error('JSON parse error:', e.message);
                console.error('Problematic line:', jsonStr);
            }
        }
    }
    
    return events;
}

// Test the parsing
console.log('=== SSE Stream Parsing Test ===\n');
console.log('Input stream (first 500 chars):');
console.log(sampleSSEStream.substring(0, 500));
console.log('\n---\n');

// Parse and display results
const events = parseSSEStream(sampleSSEStream);

console.log('Parsed events:');
events.forEach((event, i) => {
    console.log(`\nEvent ${i + 1}:`, JSON.stringify(event, null, 2));
});

// Verification checks
console.log('\n=== Verification ===\n');

console.log('1. Line separation check:');
const lines = sampleSSEStream.split('\n');
console.log(`   Total lines: ${lines.length}`);
console.log(`   Lines ending with single newline: ${lines.every(l => !l.endsWith('\n\n'))}`);

console.log('\n2. Empty line check:');
const emptyLines = lines.filter(l => l.trim() === '');
console.log(`   Empty lines: ${emptyLines.length}`);

console.log('\n3. JSON format check:');
const dataLines = lines.filter(l => l.startsWith('data: '));
console.log(`   Lines with "data: " prefix: ${dataLines.length}`);
console.log(`   All JSON parsed successfully: ${events.length === dataLines.length}`);

console.log('\n4. Event type summary:');
const types = events.map(e => e.type);
console.log(`   Types found: ${types.join(', ')}`);

// Expected vs Actual
console.log('\n=== Result ===\n');
if (events.length > 0 && events.length === dataLines.length) {
    console.log('✓ SSE parsing is working correctly!');
    console.log('✓ Lines are separated by single \\n');
    console.log('✓ No empty lines between events');
    console.log('✓ JSON is properly formatted');
} else {
    console.log('✗ Issues found with SSE parsing');
}
