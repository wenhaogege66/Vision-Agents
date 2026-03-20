import { Alert } from 'antd';
import { useEffect, useState } from 'react';

export interface OnboardingGuideProps {
  projectId: string;
  trigger: string;
  message: string;
  onClose: () => void;
}

/** Build the localStorage key for a given project + trigger pair. */
export function getOnboardingKey(projectId: string, trigger: string): string {
  return `onboarding_${projectId}_${trigger}`;
}

/** Check whether a guide has already been dismissed. */
export function isDismissed(projectId: string, trigger: string): boolean {
  return localStorage.getItem(getOnboardingKey(projectId, trigger)) === 'dismissed';
}

/** Mark a guide as dismissed in localStorage. */
export function dismiss(projectId: string, trigger: string): void {
  localStorage.setItem(getOnboardingKey(projectId, trigger), 'dismissed');
}

/**
 * 用户引导提示组件。
 *
 * 首次展示后，用户关闭即写入 localStorage，同一项目 + trigger 组合不再重复弹出。
 */
export default function OnboardingGuide({
  projectId,
  trigger,
  message,
  onClose,
}: OnboardingGuideProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    setVisible(!isDismissed(projectId, trigger));
  }, [projectId, trigger]);

  if (!visible) return null;

  const handleClose = () => {
    dismiss(projectId, trigger);
    setVisible(false);
    onClose();
  };

  return (
    <Alert
      message="操作提示"
      description={message}
      type="info"
      showIcon
      closable
      onClose={handleClose}
      style={{ marginBottom: 16 }}
    />
  );
}
