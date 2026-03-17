# 实施计划

- [x] 1. 编写 Bug Condition 探索性测试（PPT 上传同步阻塞）
  - **Property 1: Bug Condition** - PPT 上传同步转换阻塞 HTTP 响应
  - **重要**：此测试必须在实施修复之前编写
  - **此测试在未修复代码上必须失败 — 失败即确认缺陷存在**
  - **不要在测试失败时尝试修复测试或代码**
  - **注意**：此测试编码了期望行为 — 修复后测试通过即验证修复正确
  - **目标**：生成反例证明缺陷存在
  - **Scoped PBT 方法**：针对确定性缺陷，将属性范围限定为具体失败场景以确保可复现性
  - 测试场景 A：模拟上传 `.pptx` 文件（material_type 为 `text_ppt` 或 `presentation_ppt`），mock `PPTConvertService.convert_to_images` 和 `update_material_image_paths` 为耗时操作（如 sleep 5 秒）
  - 断言：在未修复代码上，`upload_material` 路由的响应时间 >= 5 秒（因为 PPT 转换同步阻塞了 HTTP 响应）
  - 期望行为（修复后）：响应时间 < 1 秒，PPT 转换被调度到后台任务而非同步 await
  - 测试场景 B：验证 `main.tsx` 中 `StrictMode` 仍然存在（通过读取文件内容断言包含 `<StrictMode>`）
  - 在未修复代码上运行测试
  - **预期结果**：测试失败（这是正确的 — 证明缺陷存在）
  - 记录发现的反例以理解根因
  - 测试编写、运行并记录失败后标记任务完成
  - _Requirements: 2.4, 2.3_

- [x] 2. 编写 Preservation 属性测试（修复前）
  - **Property 2: Preservation** - 非 PPTX 上传行为不变
  - **重要**：遵循观察优先方法论
  - 观察：在未修复代码上，上传 PDF 文件（material_type 为 `bp`）时不触发 PPT 转换，响应快速返回 `MaterialUploadResponse`
  - 观察：在未修复代码上，上传 MP4 文件（material_type 为 `presentation_video`）时不触发 PPT 转换，响应快速返回
  - 观察：在未修复代码上，`list_materials`、`get_material`、`get_material_versions` 路由正常返回数据
  - 编写基于属性的测试：对于所有非 PPTX 文件上传（PDF、DOCX、MP4 等），`upload_material` 路由不调用 `ppt_svc.convert_to_images()`，且返回正确的 `MaterialUploadResponse`
  - 编写基于属性的测试：对于所有 material_type 不在 `_PPT_TYPES` 中的上传，PPT 转换服务不被调用
  - 编写基于属性的测试：材料版本管理（`is_latest` 标记切换）在修复前后行为一致
  - 在未修复代码上运行测试
  - **预期结果**：测试通过（确认需要保持的基线行为）
  - 测试编写、运行并通过后标记任务完成
  - _Requirements: 3.1, 3.2, 3.4_

- [x] 3. 修复 PPT 上传同步阻塞和 StrictMode 双重调用

  - [x] 3.1 实现 PPT 转换异步化修复
    - 修改 `examples/web_ui_agent/backend/app/routes/materials.py`
    - 在 `upload_material` 函数参数中添加 `background_tasks: BackgroundTasks`（从 `fastapi` 导入 `BackgroundTasks`）
    - 创建后台任务函数 `_convert_ppt_background(ppt_svc, storage_path, material_id)` 封装 PPT 转换流程，包含 try/except 错误处理和日志记录
    - 将 `await ppt_svc.convert_to_images(storage_path)` 和 `await ppt_svc.update_material_image_paths(result.id, image_paths)` 从同步 await 改为 `background_tasks.add_task(_convert_ppt_background, ...)`
    - 上传完成后立即返回 `MaterialUploadResponse`，PPT 转换在后台异步执行
    - _Bug_Condition: isBugCondition(input) where input.requestType == "UPLOAD" AND input.fileType == ".pptx" AND materialType IN ["text_ppt", "presentation_ppt"]_
    - _Expected_Behavior: 上传 PPTX 文件后 HTTP 响应立即返回（< 3 秒），PPT 转换在后台异步执行_
    - _Preservation: 非 PPTX 文件上传流程不受影响，PPT 转换最终结果（PNG 图像和 image_paths）与同步转换一致_
    - _Requirements: 2.4, 3.1, 3.2_

  - [x] 3.2 移除前端 StrictMode
    - 修改 `examples/web_ui_agent/frontend/src/main.tsx`
    - 删除 `import { StrictMode } from 'react'`
    - 删除 `<StrictMode>` 和 `</StrictMode>` 包裹，直接渲染 `<ConfigProvider>` 和 `<App>`
    - _Bug_Condition: isBugCondition(input) where input.requestType == "PAGE_LOAD" AND input.environment == "development" AND strictModeEnabled == true_
    - _Expected_Behavior: 每个 useEffect 中的 API 请求只执行一次，不再重复调用_
    - _Preservation: 前端所有组件的渲染结果和交互行为保持不变_
    - _Requirements: 2.3_

  - [x] 3.3 验证 Bug Condition 探索性测试现在通过
    - **Property 1: Expected Behavior** - PPT 上传异步转换，响应快速返回
    - **重要**：重新运行任务 1 中的同一测试 — 不要编写新测试
    - 任务 1 中的测试编码了期望行为
    - 当此测试通过时，确认期望行为已满足
    - 运行任务 1 中的 Bug Condition 探索性测试
    - **预期结果**：测试通过（确认缺陷已修复）
    - _Requirements: 2.4, 2.3_

  - [x] 3.4 验证 Preservation 测试仍然通过
    - **Property 2: Preservation** - 非 PPTX 上传行为不变
    - **重要**：重新运行任务 2 中的同一测试 — 不要编写新测试
    - 运行任务 2 中的 Preservation 属性测试
    - **预期结果**：测试通过（确认无回归）
    - 确认修复后所有测试仍然通过（无回归）

- [x] 4. 检查点 - 确保所有测试通过
  - 确保所有测试通过，如有问题请询问用户。
