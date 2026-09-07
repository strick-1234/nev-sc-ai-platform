// 临时脚本：用 Node 下载中国地图 GeoJSON（Node 网络可用）
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const urls = [
  'https://registry.npmmirror.com/echarts/4.9.0/files/map/json/china.json',
  'https://cdn.jsdelivr.net/npm/echarts@4.9.0/map/json/china.json',
  'https://unpkg.com/echarts@4.9.0/map/json/china.json',
];
const out = path.join(__dirname, 'src', 'assets', 'china.json');

for (const u of urls) {
  try {
    console.log('尝试:', u);
    const res = await fetch(u, { redirect: 'follow' });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const buf = Buffer.from(await res.arrayBuffer());
    if (buf.length < 50000) throw new Error('文件太小 ' + buf.length);
    fs.writeFileSync(out, buf);
    console.log('成功 ✔', buf.length, 'bytes');
    process.exit(0);
  } catch (e) {
    console.log('  失败:', e.message);
  }
}
console.error('所有源都失败了');
process.exit(1);
