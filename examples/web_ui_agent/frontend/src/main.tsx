import { createRoot } from 'react-dom/client';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import App from './App';
import './index.css';

const antdTheme = {
  token: {
    colorPrimary: '#1a365d',
    colorLink: '#2a4a7f',
    fontFamily:
      "'Noto Sans SC', -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif",
    borderRadius: 8,
    colorBgContainer: '#ffffff',
    colorBgLayout: '#f8f7f4',
  },
};

createRoot(document.getElementById('root')!).render(
  <ConfigProvider locale={zhCN} theme={antdTheme}>
    <App />
  </ConfigProvider>,
);
