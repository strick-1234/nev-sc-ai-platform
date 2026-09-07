// ============================================================
// 前端 API 封装：统一通过 /api 访问后端（由 Vite 代理转发到 3000）
// ============================================================
async function get(path) {
  const res = await fetch('/api' + path);
  if (!res.ok) throw new Error('请求失败: ' + path);
  return res.json();
}

async function post(path, body) {
  const res = await fetch('/api' + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('请求失败: ' + path);
  return res.json();
}

export const api = {
  overview: () => get('/overview'),
  datasources: () => get('/datasources'),
  shipments: () => get('/shipments'),
  shipmentStatus: () => get('/shipments/status'),
  tracking: (id) => get('/tracking/' + id),
  alerts: () => get('/alerts'),
  inventory: () => get('/inventory'),
  inventorySummary: () => get('/inventory/summary'),
  ordersTrend: () => get('/orders/trend'),
  replenishmentProposal: () => get('/replenishment/proposal'),
  skuList: () => get('/skus'),
  forecastAccuracy: () => get('/forecast/accuracy'),
  skuDetail: (sku) => get('/sku/' + sku),
  shipmentDetail: (id) => get('/shipment/' + id),
  orders: () => get('/orders'),
  complaints: () => get('/complaints'),
  chat: (message) => post('/ai/chat', { message }),
  reset: () => post('/ai/reset', {}),
};
