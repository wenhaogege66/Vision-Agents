# 竞赛评委系统缺陷修复设计文档

## 概述

本设计文档针对竞赛评委系统中剩余的两个缺陷进行修复设计：（1）文件上传速度慢，主要原因是 PPT 上传后同步执行 PPT-to-Image 转换，阻塞了 HTTP 响应返回；（2）前端 `main.tsx` 中仍保留 `StrictMode`，导致开发模式下 `useEffect` 双重执行，API 被重复调用。

之前已修复的问题（RLS/auth 500 错误、Storage bucket 缺失、中文文件名 InvalidKey、maybe_single() NoneType 错误、MaterialCenter 卡片标题溢出）不在本次修复范围内。

## 术语表

- **Bug_Condition (C)**：触发缺陷的条件——PPT 文件上传时同步转换阻塞响应，或 StrictMode 导致 API 双重调用
- **Property (P)**：期望行为——上传应快速返回响应，PPT 转换在后台异步执行；API 请求不应重复发送
- **Preservation**：现有的文件上传功能、PPT 转换结果正确性、前端组件生命周期行为必须保持不变
- **PPTConvertService**：`backend/app/services/ppt_convert_service.py` 中的服务，负责将 PPTX 文件逐页转换为 PNG 图像并上传到 Supabase Storage
- **upload_material**：`backend/app/routes/materials.py` 中的路由处理函数，处理材料上传请求并触发 PPT 转换

## 缺陷详情

### Bug Condition

缺陷在以下两种场景中触发：

**场景 A - 上传慢**：用户上传 `.pptx` 类型的材料（text_ppt 或 presentation_ppt）时，`upload_material` 路由在文件上传到 Storage 后，同步调用 `ppt_svc.convert_to_images()` 和 `ppt_svc.update_material_image_paths()`。该转换过程包括：从 Storage 下载 PPT → 解析幻灯片 → 为每页生成 PNG 图像 → 逐张上传 PNG 到 Storage。整个过程在 HTTP 请求处理中同步执行，导致前端长时间等待响应。

**场景 B - API 双重调用**：前端 `main.tsx` 中使用 `<StrictMode>` 包裹应用，React 开发模式下会双重执行 `useEffect`，导致每个页面加载时 API 请求被发送两次。

**形式化规范：**
```
FUNCTION isBugCondition(input)
  INPUT: input of type {requestType, fileType, environment}
  OUTPUT: boolean
  
  scenarioA := input.requestType == "UPLOAD"
               AND input.fileType IN [".pptx"]
               AND materialType IN ["text_ppt", "presentation_ppt"]
  
  scenarioB := input.requestType == "PAGE_LOAD"
               AND input.environment == "development"
               AND strictModeEnabled == true
  
  RETURN scenarioA OR scenarioB
END FUNCTION
```

### 示例

- 用户上传一个 20 页的 PPTX 文件（text_ppt 类型），前端 loading 状态持续 30+ 秒才收到响应 → 期望：上传完成后立即返回响应（< 3 秒），PPT 转换在后台异步执行
- 用户上传一个 5 页的 PPTX 文件（presentation_ppt 类型），前端显示 loading 约 10 秒 → 期望：快速返回，后台转换
- 用户上传 PDF 文件（不触发 PPT 转换），响应正常快速 → 此场景不受影响
- 用户刷新 `/projects` 页面，`/api/auth/me` 和 `/api/projects` 各被调用两次 → 期望：每个 API 只调用一次

## 预期行为

### 不变行为（Preservation Requirements）

**不变行为：**
- 非 PPTX 文件（PDF、DOCX、MP4 等）的上传流程必须保持不变
- PPT 转换的最终结果（生成的 PNG 图像内容和路径）必须与当前同步转换完全一致
- `project_materials` 表中的记录（file_name、file_path、version 等）必须正确写入
- 材料版本管理（is_latest 标记切换）必须继续正常工作
- 前端所有组件的渲染结果和交互行为必须保持不变
- 认证流程、项目 CRUD、评审功能等不受影响

**范围：**
所有不涉及 PPTX 上传同步转换和 StrictMode 的输入应完全不受本次修复影响。包括：
- PDF/DOCX/MP4 文件上传
- 材料列表查询、版本历史查询
- 鼠标点击、表单提交等用户交互
- 所有非材料相关的 API 调用

## 假设根因分析

基于代码分析，最可能的问题是：

1. **PPT 转换同步阻塞**：`materials.py` 路由中 `upload_material` 函数在 `await svc.upload()` 完成后，直接 `await ppt_svc.convert_to_images(storage_path)` 和 `await ppt_svc.update_material_image_paths()`。`convert_to_images` 内部执行了：下载 PPT → 解析 → 为每页生成 PNG → 逐张上传到 Storage，这些 I/O 密集操作全部在请求处理链中同步完成，导致 HTTP 响应被阻塞。

2. **无上传进度反馈**：前端 `MaterialCenter.tsx` 中 `handleUpload` 使用 `materialApi.upload()` 发送请求，虽然设置了 `timeout: 120_000`（2 分钟），但没有上传进度条，用户只能看到 loading 按钮，体验差。

3. **StrictMode 未移除**：`main.tsx` 中仍然使用 `<StrictMode>` 包裹整个应用。虽然用户反馈"似乎已解决"，但代码中 StrictMode 仍然存在，开发模式下仍会导致 useEffect 双重执行。

## 正确性属性

Property 1: Bug Condition - PPT 上传应异步转换

_For any_ PPTX 文件上传请求（material_type 为 text_ppt 或 presentation_ppt 且文件扩展名为 .pptx），修复后的 `upload_material` 函数 SHALL 在文件上传到 Storage 并插入数据库记录后立即返回 `MaterialUploadResponse`，PPT-to-Image 转换 SHALL 在后台异步执行，不阻塞 HTTP 响应。

**Validates: Requirements 2.4**

Property 2: Preservation - 非 PPTX 上传行为不变

_For any_ 非 PPTX 文件上传请求（PDF、DOCX、MP4 等），修复后的代码 SHALL 产生与原始代码完全相同的行为，包括文件上传、数据库记录插入、响应内容，保持所有现有功能不变。

**Validates: Requirements 3.1, 3.2, 3.4**

Property 3: Preservation - PPT 转换结果一致性

_For any_ PPTX 文件上传，后台异步转换完成后，生成的 PNG 图像内容和 `project_materials` 表中的 `image_paths` 字段 SHALL 与同步转换时的结果完全一致。

**Validates: Requirements 3.2**

Property 4: Bug Condition - StrictMode 移除后 API 不重复调用

_For any_ 前端页面加载或导航操作，移除 StrictMode 后，每个 `useEffect` 中的 API 请求 SHALL 只执行一次，不再出现重复调用。

**Validates: Requirements 2.3**

## 修复实现

### 所需变更

假设根因分析正确：

**文件**：`examples/web_ui_agent/backend/app/routes/materials.py`

**函数**：`upload_material`

**具体变更**：
1. **异步化 PPT 转换**：将 PPT-to-Image 转换从同步 await 改为使用 `asyncio.create_task()` 或 `BackgroundTasks`（FastAPI 内置）在后台执行。推荐使用 FastAPI 的 `BackgroundTasks`，因为它与请求生命周期集成更好，且不需要额外的任务队列基础设施。
   - 在 `upload_material` 函数参数中添加 `background_tasks: BackgroundTasks`
   - 将 `ppt_svc.convert_to_images()` 和 `ppt_svc.update_material_image_paths()` 移入后台任务
   - 上传完成后立即返回 `MaterialUploadResponse`

2. **PPT 转换后台任务封装**：创建一个后台任务函数，封装 PPT 下载、转换、上传图像、更新数据库记录的完整流程，包含错误处理和日志记录。

**文件**：`examples/web_ui_agent/frontend/src/main.tsx`

**具体变更**：
3. **移除 StrictMode**：删除 `<StrictMode>` 包裹，直接渲染 `<ConfigProvider>` 和 `<App>`。同时移除 `import { StrictMode } from 'react'`。

## 测试策略

### 验证方法

测试策略分两阶段：首先在未修复代码上复现缺陷（探索性测试），然后验证修复后的行为正确且不引入回归。

### 探索性 Bug Condition 检查

**目标**：在实施修复前，复现缺陷以确认根因分析。如果根因被否定，需要重新分析。

**测试计划**：编写测试模拟 PPTX 文件上传，测量从请求发送到响应返回的时间，验证同步转换确实阻塞了响应。

**测试用例**：
1. **PPTX 上传耗时测试**：上传一个多页 PPTX 文件，测量响应时间（在未修复代码上预期 > 5 秒）
2. **PDF 上传对比测试**：上传同大小 PDF 文件，测量响应时间（预期快速返回，作为对照）
3. **StrictMode 双重调用测试**：在开发模式下加载页面，检查 API 调用次数（在未修复代码上预期每个请求调用两次）

**预期反例**：
- PPTX 上传响应时间远大于 PDF 上传，差异来自同步 PPT 转换
- 页面加载时 API 请求被发送两次

### Fix Checking

**目标**：验证对所有触发 bug condition 的输入，修复后的函数产生期望行为。

**伪代码：**
```
FOR ALL input WHERE isBugCondition(input) DO
  IF input.scenarioA THEN
    result := upload_material_fixed(input)
    ASSERT responseTime(result) < 3 seconds
    ASSERT result.status == 200
    ASSERT pptConversionScheduledInBackground()
    WAIT FOR backgroundTaskCompletion()
    ASSERT imagesGeneratedCorrectly()
  END IF
  IF input.scenarioB THEN
    loadCount := countApiCalls(pageLoad_fixed())
    ASSERT loadCount == 1 FOR EACH apiEndpoint
  END IF
END FOR
```

### Preservation Checking

**目标**：验证对所有不触发 bug condition 的输入，修复后的函数产生与原始函数相同的结果。

**伪代码：**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT upload_material_original(input) = upload_material_fixed(input)
END FOR
```

**测试方法**：推荐使用基于属性的测试（Property-Based Testing）进行 preservation checking，因为：
- 可以自动生成大量测试用例覆盖输入域
- 能捕获手动单元测试可能遗漏的边界情况
- 对非 bug 输入的行为不变性提供强保证

**测试计划**：先在未修复代码上观察非 PPTX 文件上传的行为，然后编写基于属性的测试验证修复后行为一致。

**测试用例**：
1. **PDF 上传 Preservation**：验证 PDF 文件上传在修复前后行为完全一致
2. **材料列表查询 Preservation**：验证 GET 材料列表在修复前后返回相同结果
3. **版本历史查询 Preservation**：验证版本历史查询在修复前后行为一致
4. **非 PPTX 材料类型 Preservation**：验证 bp、presentation_video 类型上传不受影响

### 单元测试

- 测试 `upload_material` 路由：PPTX 上传时 PPT 转换被添加到后台任务而非同步执行
- 测试 `upload_material` 路由：非 PPTX 上传时不触发 PPT 转换（与修复前一致）
- 测试后台任务函数：PPT 转换成功时正确更新 `image_paths`
- 测试后台任务函数：PPT 转换失败时正确记录日志，不影响已上传的材料记录

### 基于属性的测试

- 生成随机文件类型和大小，验证只有 PPTX 类型触发后台转换
- 生成随机材料类型，验证非 PPT 类型的上传行为与修复前完全一致
- 生成随机页数的 PPTX 文件，验证后台转换生成的图像数量与页数一致

### 集成测试

- 端到端测试：上传 PPTX 文件，验证响应快速返回，等待后台任务完成后验证图像已生成
- 端到端测试：上传 PDF 文件，验证行为与修复前一致
- 前端测试：移除 StrictMode 后，验证页面加载时 API 只调用一次
