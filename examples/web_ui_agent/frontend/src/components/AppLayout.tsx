import { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Button, Typography, Avatar, Dropdown, theme } from 'antd';
import {
  HomeOutlined,
  ProjectOutlined,
  LogoutOutlined,
  UserOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons';
import { useAuth } from '@/contexts/AuthContext';

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

const NAV_ITEMS = [
  { key: '/', icon: <HomeOutlined />, label: '首页' },
  { key: '/projects', icon: <ProjectOutlined />, label: '我的项目' },
];

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const { token } = theme.useToken();

  const selectedKey = NAV_ITEMS.find((item) => location.pathname === item.key)?.key
    ?? (location.pathname.startsWith('/projects') ? '/projects' : '/');

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        trigger={null}
        style={{
          background: token.colorBgContainer,
          borderRight: `1px solid ${token.colorBorderSecondary}`,
        }}
      >
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
            gap: 8,
          }}
        >
          <span style={{ fontSize: 24 }}>🏆</span>
          {!collapsed && (
            <Text strong style={{ fontSize: 15, whiteSpace: 'nowrap' }}>
              AI评委系统
            </Text>
          )}
        </div>
        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          items={NAV_ITEMS}
          onClick={({ key }) => navigate(key)}
          style={{ border: 'none', marginTop: 8 }}
        />
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
  );
}
