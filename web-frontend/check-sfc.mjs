// 临时脚本：用 Vue 编译器检查所有 .vue 文件语法（无需 esbuild 子进程）
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const files = [
  'src/App.vue',
  'src/components/KpiCard.vue',
  'src/components/TransitMap.vue',
  'src/components/AlertsPanel.vue',
  'src/components/InventoryPanel.vue',
  'src/components/DataSourcePanel.vue',
  'src/components/TrendCharts.vue',
];

let ok = true;
for (const f of files) {
  const src = fs.readFileSync(path.join(__dirname, f), 'utf8');
  try {
    const { descriptor, errors } = parse(src, { filename: f });
    if (errors.length) {
      ok = false;
      console.log('✗', f);
      errors.forEach((e) => console.log('   ', e.message || String(e)));
      continue;
    }
    if (descriptor.script || descriptor.scriptSetup) {
      compileScript(descriptor, { id: 'check' });
    }
    if (descriptor.template) {
      compileTemplate({ source: descriptor.template.content, filename: f, id: 'check' });
    }
    console.log('✓', f);
  } catch (e) {
    ok = false;
    console.log('✗', f, '->', e.message);
  }
}
console.log(ok ? '\n全部 .vue 文件语法正确 ✔' : '\n存在语法错误，请修复');
if (!ok) process.exit(1);
