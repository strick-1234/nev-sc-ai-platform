import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5174,
    strictPort: true, // 固定端口，避免被环境变量影响
    proxy: {
      // 前端请求 /api/* 时，转发到 Python 融合平台 API（8503）
      '/api': {
        target: 'http://127.0.0.1:8503',
        changeOrigin: true,
      },
    },
  },
});
