import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { App as AntdApp, ConfigProvider, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { AuthProvider } from '@/contexts/AuthContext';
import { setMessageInstance } from '@/utils/messageHolder';
import ProtectedRoute from '@/components/ProtectedRoute';
import AppLayout from '@/components/AppLayout';
import Login from '@/pages/Login';
import Register from '@/pages/Register';
import Home from '@/pages/Home';
import ProjectList from '@/pages/ProjectList';
import ProjectCreate from '@/pages/ProjectCreate';
import ProjectDashboard from '@/pages/ProjectDashboard';
import MaterialCenter from '@/pages/MaterialCenter';
import TextReview from '@/pages/TextReview';
import ReviewHistory from '@/pages/ReviewHistory';
import ReviewDetail from '@/pages/ReviewDetail';
import LivePresentation from '@/pages/LivePresentation';
import OfflineReview from '@/pages/OfflineReview';

export default function App() {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: '#4f46e5',
          borderRadius: 8,
          fontFamily:
            "'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', system-ui, sans-serif",
        },
      }}
    >
      <AntdApp>
        <AppInner />
      </AntdApp>
    </ConfigProvider>
  );
}

/** 在 AntdApp 内部获取 context 版 message 并注入全局 holder */
function AppInner() {
  const { message: contextMessage } = AntdApp.useApp();
  setMessageInstance(contextMessage);

  return (
    <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />

            <Route
              element={
                <ProtectedRoute>
                  <AppLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Home />} />
              <Route path="projects" element={<ProjectList />} />
              <Route path="projects/create" element={<ProjectCreate />} />
              <Route path="projects/:projectId" element={<ProjectDashboard />} />
              <Route path="projects/:projectId/materials" element={<MaterialCenter />} />
              <Route path="projects/:projectId/text-review" element={<TextReview />} />
              <Route path="projects/:projectId/reviews" element={<ReviewHistory />} />
              <Route path="projects/:projectId/reviews/:reviewId" element={<ReviewDetail />} />
              <Route path="projects/:projectId/live" element={<LivePresentation />} />
              <Route path="projects/:projectId/offline-review" element={<OfflineReview />} />
            </Route>

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
  );
}
