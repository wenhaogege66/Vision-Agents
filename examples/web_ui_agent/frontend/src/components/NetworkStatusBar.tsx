import { useState, useEffect } from 'react';
import { Alert } from 'antd';

export default function NetworkStatusBar() {
  const [online, setOnline] = useState(navigator.onLine);

  useEffect(() => {
    const handleOnline = () => setOnline(true);
    const handleOffline = () => setOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  if (online) return null;

  return (
    <Alert
      message="网络连接已断开"
      type="warning"
      banner
      showIcon
    />
  );
}
