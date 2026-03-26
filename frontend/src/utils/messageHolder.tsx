/**
 * 全局 message holder — 解决 antd v6 静态方法无法消费 context 的问题。
 *
 * 用法：在组件中 `import { msg } from '@/utils/messageHolder'`，
 * 然后 `msg.success('...')`、`msg.error('...')` 等。
 */

import { message } from 'antd';
import type { MessageInstance } from 'antd/es/message/interface';

// 默认使用 antd 静态方法，App 挂载后会被替换为 context 版本
let msg: MessageInstance = message;

export function setMessageInstance(instance: MessageInstance) {
  msg = instance;
}

export { msg };
