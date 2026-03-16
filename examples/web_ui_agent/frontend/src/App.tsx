import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from '@/contexts/AuthContext';
import ProtectedRoute from '@/components/ProtectedRoute';
import Login from '@/pages/Login';
import Register from '@/pages/Register';
import ProjectList from '@/pages/ProjectList';
import ProjectCreate from '@/pages/ProjectCreate';
import ProjectDashboard from '@/pages/ProjectDashboard';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Protected routes */}
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <Routes>
                  <Route path="/" element={<Navigate to="/projects" replace />} />
                  <Route path="/projects" element={<ProjectList />} />
                  <Route path="/projects/create" element={<ProjectCreate />} />
                  <Route path="/projects/:id" element={<ProjectDashboard />} />
                </Routes>
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
