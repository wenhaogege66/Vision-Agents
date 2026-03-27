import { useState, useCallback, useEffect } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Button, Typography, Avatar, Dropdown, Divider, theme } from 'antd';
import {
  HomeOutlined,
  ProjectOutlined,
  LogoutOutlined,
  UserOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons';
import { useAuth } from '@/contexts/AuthContext';
import ProjectTree from '@/components/ProjectTree';
import NetworkStatusBar from '@/components/NetworkStatusBar';
import { LabelResolverProvider } from '@/hooks/useLabelResolver';

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

const NAV_ITEMS = [
  { key: '/', icon: <HomeOutlined />, label: '首页' },
  { key: '/projects', icon: <ProjectOutlined />, label: '我的项目' },
];

/** 侧边栏刷新计数器，用于在项目删除后触发 ProjectTree 重新加载 */
let _sidebarRefreshKey = 0;
export function triggerSidebarRefresh() {
  _sidebarRefreshKey++;
  window.dispatchEvent(new CustomEvent('sidebar-refresh'));
}

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const [sidebarKey, setSidebarKey] = useState(0);
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const { token } = theme.useToken();

  // 监听侧边栏刷新事件
  const handleSidebarRefresh = useCallback(() => {
    setSidebarKey((k) => k + 1);
  }, []);

  useEffect(() => {
    window.addEventListener('sidebar-refresh', handleSidebarRefresh);
    return () => window.removeEventListener('sidebar-refresh', handleSidebarRefresh);
  }, [handleSidebarRefresh]);

  const selectedKey = NAV_ITEMS.find((item) => location.pathname === item.key)?.key
    ?? (location.pathname.startsWith('/projects') ? '/projects' : '/');

  return (
    <LabelResolverProvider>
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        trigger={null}
        width={240}
        collapsedWidth={64}
        style={{
          background: token.colorBgContainer,
          borderRight: `1px solid ${token.colorBorderSecondary}`,
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Logo 区域 */}
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            padding: collapsed ? 0 : '0 20px',
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
            gap: 10,
            flexShrink: 0,
          }}
        >
          <div style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            background: `linear-gradient(135deg, ${token.colorPrimary}, ${token.colorPrimaryActive})`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}>
            <span style={{ fontSize: 18, filter: 'brightness(0) invert(1)' }}>🏆</span>
          </div>
          {!collapsed && (
            <Text strong style={{ fontSize: 15, whiteSpace: 'nowrap', color: token.colorText }}>
              AI评委系统
            </Text>
          )}
        </div>

        {/* 导航菜单 */}
        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          items={NAV_ITEMS}
          onClick={({ key }) => navigate(key)}
          style={{ border: 'none', marginTop: 4, flexShrink: 0 }}
        />

        {/* 项目列表区域 */}
        {!collapsed && (
          <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <Divider style={{ margin: '4px 16px', minWidth: 'auto', width: 'auto' }} />
            <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden' }}>
              <ProjectTree key={sidebarKey} />
            </div>
          </div>
        )}
      </Sider>

      <Layout>
        <Header
          style={{
            background: token.colorBgContainer,
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            height: 64,
          }}
        >
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
          />
          <Dropdown
            menu={{
              items: [
                {
                  key: 'logout',
                  icon: <LogoutOutlined />,
                  label: '退出登录',
                  onClick: () => { logout(); navigate('/login'); },
                },
              ],
            }}
          >
            <div style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Avatar size="small" icon={<UserOutlined />} />
              <Text>{user?.display_name ?? user?.email ?? '用户'}</Text>
            </div>
          </Dropdown>
        </Header>

        <NetworkStatusBar />

        <Content
          style={{
            margin: 0,
            minHeight: 280,
            background: token.colorBgLayout,
            overflow: 'auto',
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
    </LabelResolverProvider>
  );
}
