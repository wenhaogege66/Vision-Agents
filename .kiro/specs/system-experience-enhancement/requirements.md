# 需求文档：AI评委系统体验增强

## 简介

本文档涵盖AI评委系统的全面体验增强需求，包括以下核心模块：

1. **评审就绪检查**：在前端增加材料状态检查机制，在评审发起前明确告知用户材料准备状态，禁用不满足条件的评审操作，并在多种评审类型均可用时提供选择界面
2. **中文标签与导航优化**：将赛事/赛道/组别英文ID替换为中文名称显示，为各子页面添加统一的返回导航按钮
3. **侧边栏项目树**：在侧边栏按赛事→赛道→组别层级展示项目树形结构，支持快速定位和切换
4. **进度时间线**：在比赛进度步骤条上显示各阶段日期信息
5. **会议分享与材料下载**：支持现场路演会议链接分享和材料版本历史下载
6. **AI项目简介提取**：从BP和文本PPT中自动提取项目结构化简介，用于展示和评审上下文
7. **自定义标签与项目管理**：支持自定义彩色标签、项目筛选和数据导出
8. **全局错误处理**：统一的网络错误提示和重试机制

## 术语表

- **评审就绪检查器（Readiness_Checker）**：前端逻辑模块，负责查询材料上传状态和PPT转换状态，计算各评审类型是否可发起
- **材料中心页面（Material_Center_Page）**：用户上传和管理项目材料的前端页面（`MaterialCenter.tsx`）
- **文本评审页面（Text_Review_Page）**：用户发起AI文本评审的前端页面（`TextReview.tsx`）
- **离线评审页面（Offline_Review_Page）**：用户发起离线路演评审的前端页面（`OfflineReview.tsx`）
- **项目仪表盘（Project_Dashboard）**：项目概览页面，包含快捷操作入口（`ProjectDashboard.tsx`）
- **文本PPT（text_ppt）**：文本评审所需的PPT材料，上传后需异步转换为PNG图像
- **路演PPT（presentation_ppt）**：离线路演评审所需的PPT材料，上传后需异步转换为PNG图像
- **BP（bp）**：商业计划书，文本评审的可选辅助材料
- **路演视频（presentation_video）**：离线路演评审所需的视频材料
- **image_paths**：`project_materials` 表中的字段，PPT上传后为 null，异步转换完成后填充为图像路径数组
- **材料状态API（Material_Status_API）**：后端接口，返回项目各材料的上传状态和转换就绪状态
- **评审选择对话框（Review_Selection_Dialog）**：当多种评审类型均可用时，弹出的选择界面，供用户选择评审类型
- **标签名称解析器（Label_Resolver）**：前端逻辑模块，负责将赛事/赛道/组别的英文ID解析为对应的中文名称
- **名称映射API（Name_Mapping_API）**：后端接口，返回赛事/赛道/组别ID与中文名称的映射关系（已有 `COMPETITION_NAMES`、`TRACK_NAMES`、`GROUP_NAMES`）
- **导航栏（Navigation_Bar）**：各子页面顶部的导航区域，包含返回按钮和页面标题
- **侧边栏（Sidebar）**：应用左侧导航栏（`AppLayout.tsx`），当前包含"首页"和"我的项目"两个菜单项
- **项目树（Project_Tree）**：侧边栏中按赛事→赛道→组别层级展示项目的树形结构
- **进度时间线（Progress_Timeline）**：项目仪表盘中展示比赛各阶段进度的步骤条组件
- **现场路演页面（Live_Presentation_Page）**：基于 GetStream 的实时音视频AI评委互动页面（`LivePresentation.tsx`）
- **会议分享链接（Meeting_Share_Link）**：可分享的URL，允许其他参与者加入同一现场路演会议
- **版本历史弹窗（Version_History_Modal）**：材料中心中展示材料历史版本列表的模态框
- **AI简介提取器（AI_Profile_Extractor）**：后端AI服务模块，从BP和文本PPT中提取项目关键信息生成结构化简介
- **项目简介（Project_Profile）**：AI提取的项目结构化信息，包含团队介绍、所属领域、创业状态、已有成果、产品链接、下一步目标等
- **自定义标签（Custom_Tag）**：用户创建的带颜色的项目分类标签，用于项目组织和筛选
- **评审历史页面（Review_History_Page）**：展示项目所有历史评审记录的页面（`ReviewHistory.tsx`）
- **评审详情页面（Review_Detail_Page）**：展示单次评审详细结果的页面（`ReviewDetail.tsx`）

## 需求

### 需求 1：材料就绪状态查询

**用户故事：** 作为用户，我希望系统能查询各材料的上传和转换状态，以便前端准确判断哪些评审类型可以发起。

#### 验收标准

1. THE Material_Status_API SHALL 返回项目所有四种材料类型（bp、text_ppt、presentation_ppt、presentation_video）的上传状态（已上传/未上传）
2. THE Material_Status_API SHALL 对 text_ppt 和 presentation_ppt 类型额外返回转换就绪状态（image_paths 是否非空）
3. WHEN 前端页面加载时，THE Readiness_Checker SHALL 调用 Material_Status_API 获取最新材料状态
4. WHEN 用户在材料中心页面上传新材料后，THE Readiness_Checker SHALL 重新获取材料状态以反映最新情况

### 需求 2：文本评审材料选择与就绪控制

**用户故事：** 作为用户，我希望在发起文本评审时能选择评审哪些材料（仅BP、仅文本PPT、仅路演PPT、或任意组合），并且只有至少一种材料已上传且就绪时才允许发起评审。

#### 验收标准

1. WHEN 用户进入文本评审页面，THE Text_Review_Page SHALL 显示材料选择区域，列出所有已上传且就绪的材料（bp、text_ppt、presentation_ppt）作为可勾选项
2. WHILE 没有任何材料已上传且就绪（PPT类型需 image_paths 非空），THE Text_Review_Page SHALL 禁用"发起文本评审"按钮并显示"请先上传至少一种评审材料"提示
3. WHILE 某种PPT材料已上传但 image_paths 为空（转换未完成），THE Text_Review_Page SHALL 将该材料选项标记为"转换中"并禁止勾选
4. WHEN 用户勾选至少一种已就绪的材料后，THE Text_Review_Page SHALL 启用"发起文本评审"按钮
5. WHEN 用户发起文本评审时，THE Text_Review_Page SHALL 将用户选择的材料类型列表传递给后端评审API
6. THE Text_Review_API SHALL 根据用户选择的材料类型列表，仅使用对应材料内容进行AI评审

### 需求 3：离线路演评审就绪控制

**用户故事：** 作为用户，我希望在路演视频未上传时离线评审按钮被禁用，路演视频是离线评审的核心材料，BP和PPT作为辅助材料参与评审（路演PPT优先级高于其他辅助材料）。

#### 验收标准

1. WHILE presentation_video 未上传，THE Offline_Review_Page SHALL 禁用"发起离线路演评审"按钮并显示"请先上传路演视频"提示
2. WHEN presentation_video 已上传，THE Offline_Review_Page SHALL 启用"发起离线路演评审"按钮
3. THE Offline_Review_Page SHALL 显示辅助材料状态列表（presentation_ppt、text_ppt、bp），标注各材料的上传和就绪状态
4. WHEN 用户发起离线路演评审时，THE Offline_Review_API SHALL 以路演视频为核心评审材料，自动附加所有已就绪的辅助材料（优先级：presentation_ppt > text_ppt > bp）
5. IF 路演PPT已上传但转换未完成，THE Offline_Review_Page SHALL 在辅助材料列表中标注"路演PPT转换中，评审将不包含PPT辅助内容"

### 需求 4：文本评审材料选择交互

**用户故事：** 作为用户，当多种材料都已就绪时，我希望在文本评审页面灵活选择评审哪些材料，以便针对性地获取AI评审反馈。

#### 验收标准

1. THE Text_Review_Page SHALL 以复选框形式展示所有已就绪的材料选项（bp、text_ppt、presentation_ppt）
2. WHEN 材料未上传时，THE Text_Review_Page SHALL 将该材料选项置灰并标注"未上传"
3. WHEN PPT材料已上传但转换未完成时，THE Text_Review_Page SHALL 将该材料选项置灰并标注"转换中"
4. THE Text_Review_Page SHALL 默认勾选所有已就绪的材料
5. WHEN 用户取消所有材料的勾选时，THE Text_Review_Page SHALL 禁用"发起文本评审"按钮
6. THE Text_Review_API SHALL 接受 `material_types: list[str]` 参数，仅使用指定材料进行评审

### 需求 5：转换状态轮询与实时反馈

**用户故事：** 作为用户，我希望在PPT转换过程中看到进度提示，并在转换完成后自动更新按钮状态，无需手动刷新页面。

#### 验收标准

1. WHILE text_ppt 或 presentation_ppt 的 image_paths 为空（转换进行中），THE Readiness_Checker SHALL 每隔 5 秒轮询一次材料状态
2. WHEN 轮询检测到 image_paths 从空变为非空（转换完成），THE Readiness_Checker SHALL 停止轮询并更新页面上的按钮状态和提示文案
3. THE Text_Review_Page SHALL 在转换进行中显示加载动画或进度指示器
4. THE Offline_Review_Page SHALL 在转换进行中显示加载动画或进度指示器
5. IF 轮询超过 5 分钟仍未检测到转换完成，THEN THE Readiness_Checker SHALL 停止轮询并显示"转换超时，请检查材料或重新上传"的提示

### 需求 6：项目仪表盘评审入口状态提示

**用户故事：** 作为用户，我希望在项目仪表盘的快捷操作卡片上直观看到各评审类型的就绪状态，以便快速了解当前可以进行哪些操作。

#### 验收标准

1. THE Project_Dashboard SHALL 在"文本评审"快捷操作卡片上显示就绪状态标签（如"就绪"或"材料未备齐"）
2. THE Project_Dashboard SHALL 在"离线评审"快捷操作卡片上显示就绪状态标签
3. WHILE 评审类型未就绪，THE Project_Dashboard SHALL 将对应快捷操作卡片置灰并显示缺失材料的简要提示
4. WHEN 用户点击未就绪的评审卡片，THE Project_Dashboard SHALL 显示提示信息引导用户前往材料中心上传所需材料

### 需求 7：赛事/赛道/组别中文标签显示

**用户故事：** 作为用户，我希望在项目列表、项目仪表盘等页面看到赛事、赛道、组别的中文名称标签，而非英文ID（如"guochuangsaigaojiaobenke_chuangyi"），以便直观理解项目所属分类。

#### 验收标准

1. THE Label_Resolver SHALL 将项目的 competition、track、group 英文ID解析为对应的中文名称
2. WHEN 项目列表页面加载时，THE Label_Resolver SHALL 将每个项目卡片上的赛事、赛道、组别标签显示为中文名称
3. WHEN 项目仪表盘页面加载时，THE Label_Resolver SHALL 将项目头部的赛事、赛道、组别标签显示为中文名称
4. IF Name_Mapping_API 返回的映射中不包含某个ID，THEN THE Label_Resolver SHALL 回退显示原始英文ID
5. THE Name_Mapping_API SHALL 提供一个批量查询接口，返回所有赛事、赛道、组别的 ID 到中文名称的映射，避免前端逐个请求

### 需求 8：子页面返回导航按钮

**用户故事：** 作为用户，我希望在材料中心、文本评审、离线评审、评审历史、评审详情、现场路演等子页面顶部看到统一的返回按钮，以便快速返回上一级页面。

#### 验收标准

1. THE Material_Center_Page SHALL 在页面顶部显示返回按钮，点击后导航至项目仪表盘
2. THE Text_Review_Page SHALL 在页面顶部显示返回按钮，点击后导航至项目仪表盘
3. THE Offline_Review_Page SHALL 在页面顶部显示返回按钮，点击后导航至项目仪表盘
4. THE Review_History_Page SHALL 在页面顶部显示返回按钮，点击后导航至项目仪表盘
5. THE Review_Detail_Page SHALL 在页面顶部显示返回按钮，点击后导航至评审历史页面
6. THE Live_Presentation_Page SHALL 在页面顶部显示返回按钮，点击后导航至项目仪表盘
7. THE Navigation_Bar SHALL 采用统一的视觉样式（左箭头图标 + 目标页面名称），与 Project_Dashboard 已有的返回按钮风格一致

### 需求 9：侧边栏项目树

**用户故事：** 作为用户，我希望在侧边栏的"我的项目"下看到按赛事→赛道→组别层级组织的项目树形结构，以便快速定位和切换项目。

#### 验收标准

1. THE Sidebar SHALL 在"我的项目"菜单项下展示可展开的 Project_Tree
2. THE Project_Tree SHALL 按赛事→赛道→组别三级层级组织项目，每级节点显示中文名称
3. WHEN 用户点击 Project_Tree 中的项目节点，THE Sidebar SHALL 导航至该项目的仪表盘页面
4. WHEN 用户创建新项目后，THE Project_Tree SHALL 自动更新以包含新项目
5. WHILE Sidebar 处于折叠状态，THE Project_Tree SHALL 隐藏，仅显示"我的项目"图标
6. IF 某个赛事/赛道/组别下没有项目，THEN THE Project_Tree SHALL 不显示该空节点

### 需求 10：进度时间线日期显示

**用户故事：** 作为用户，我希望在项目仪表盘的比赛进度步骤条上看到各阶段的日期信息，以便了解比赛时间安排。

#### 验收标准

1. THE Progress_Timeline SHALL 在每个阶段节点下方显示该阶段的日期信息
2. WHEN 后端返回的阶段数据包含日期字段时，THE Progress_Timeline SHALL 以"YYYY-MM-DD"格式显示日期
3. IF 某个阶段没有配置日期信息，THEN THE Progress_Timeline SHALL 在该节点下方显示"待定"
4. THE Material_Status_API SHALL 扩展返回项目所属赛事的各阶段日期配置（或提供独立的阶段日期查询接口）

### 需求 11：现场路演会议分享链接（需验证可行性）

**用户故事：** 作为用户，我希望在现场路演会议中生成可分享的链接，以便邀请团队成员或其他参与者加入同一会议。

**技术备注：** GetStream SDK 支持通过 call_id + 用户 token 加入已有通话，但当前前端尚未集成 GetStream React Video SDK（视频区域为占位符）。实现此需求需要先完成前端 GetStream SDK 集成。本需求标记为需验证可行性，优先级低于其他需求。

#### 验收标准

1. WHEN 用户发起现场路演会议后，THE Live_Presentation_Page SHALL 显示"复制会议链接"按钮
2. WHEN 用户点击"复制会议链接"按钮，THE Live_Presentation_Page SHALL 生成包含 call_id 的 URL 并复制到剪贴板
3. WHEN 其他已登录用户通过分享链接访问时，后端 SHALL 为该用户生成 GetStream token 并将其加入对应通话
4. IF 分享链接对应的会议已结束，THEN THE Live_Presentation_Page SHALL 显示"会议已结束"的提示信息
5. **前提条件**：需先完成前端 GetStream React Video SDK 集成，替换当前的视频占位符区域

### 需求 12：材料版本历史下载链接

**用户故事：** 作为用户，我希望在材料中心的版本历史弹窗中看到每个历史版本的下载链接，以便下载和查看之前上传的材料文件。

#### 验收标准

1. THE Version_History_Modal SHALL 在每个版本记录行中显示"下载"操作按钮
2. WHEN 用户点击"下载"按钮，THE Version_History_Modal SHALL 从 Supabase Storage 获取该版本文件的签名下载URL并触发浏览器下载
3. THE Material_Status_API SHALL 提供材料版本文件的下载URL生成接口
4. IF 文件在 Supabase Storage 中不存在或已过期，THEN THE Version_History_Modal SHALL 显示"文件不可用"的提示信息

### 需求 13：AI项目简介提取

**用户故事：** 作为用户，我希望在首次上传BP和文本PPT后，系统自动使用AI提取项目简介（团队介绍、所属领域、创业状态、已有成果、产品链接、下一步目标等），并在项目仪表盘展示，以便快速了解项目概况并在后续评审中为AI提供上下文。

#### 验收标准

1. WHEN 用户首次同时拥有已上传的 bp 和 text_ppt 材料时，THE AI_Profile_Extractor SHALL 自动触发项目简介提取任务
2. THE AI_Profile_Extractor SHALL 从 BP 和文本PPT 内容中提取以下结构化字段：团队介绍、所属领域、创业状态、已有成果、产品链接、下一步目标
3. WHEN 提取完成后，THE Project_Dashboard SHALL 在项目头部区域展示项目简介卡片
4. THE Project_Dashboard SHALL 允许用户编辑AI提取的项目简介内容，编辑后的内容保存至数据库
5. WHEN 用户发起任何类型的评审时，THE Readiness_Checker SHALL 将项目简介作为上下文信息传递给AI评审服务
6. WHEN 用户更新 bp 或 text_ppt 材料后，THE AI_Profile_Extractor SHALL 提示用户是否重新提取项目简介
7. IF AI提取过程失败，THEN THE AI_Profile_Extractor SHALL 显示错误提示并允许用户手动填写项目简介

### 需求 14：自定义项目标签

**用户故事：** 作为用户，我希望能为项目创建自定义的彩色标签，在侧边栏和项目列表中显示，并支持按标签筛选项目，以便更灵活地组织和管理项目。

#### 验收标准

1. THE Project_Dashboard SHALL 提供"添加标签"入口，允许用户创建自定义标签（包含标签名称和颜色选择）
2. THE Project_Dashboard SHALL 在项目头部区域显示该项目已关联的所有自定义标签
3. WHEN 用户创建新标签时，THE Project_Dashboard SHALL 提供至少 8 种预设颜色供选择
4. THE Project_Tree SHALL 在项目节点旁显示该项目的自定义标签色点
5. THE Project_Dashboard SHALL 允许用户移除项目上已关联的自定义标签
6. WHEN 用户在项目列表页面点击某个标签时，THE Label_Resolver SHALL 筛选并仅显示包含该标签的项目
7. THE Material_Status_API SHALL 扩展支持自定义标签的 CRUD 操作接口（创建、读取、更新、删除标签，以及项目-标签关联管理）

### 需求 15：全局错误状态统一处理（建议新增）

**用户故事：** 作为用户，我希望在网络请求失败或后端返回错误时，系统以统一的方式展示错误信息并提供重试选项，而非显示空白页面或无提示地失败。

#### 验收标准

1. WHEN 任何API请求返回 4xx 或 5xx 错误时，THE Navigation_Bar SHALL 以统一的通知样式展示错误信息
2. WHEN 网络连接中断时，THE Sidebar SHALL 在顶部显示"网络连接已断开"的持续性提示条
3. WHEN 网络连接恢复时，THE Sidebar SHALL 自动隐藏网络断开提示条
4. THE Navigation_Bar SHALL 在错误通知中提供"重试"按钮，点击后重新发起失败的请求
5. IF 连续 3 次重试均失败，THEN THE Navigation_Bar SHALL 显示"请检查网络连接或联系管理员"的提示

### 需求 16：项目数据导出（建议新增）

**用户故事：** 作为用户，我希望能将项目的评审结果和材料信息导出为结构化文件，以便在系统外进行汇报或存档。

#### 验收标准

1. THE Project_Dashboard SHALL 提供"导出项目报告"按钮
2. WHEN 用户点击"导出项目报告"按钮，THE Project_Dashboard SHALL 生成包含项目基本信息、材料状态、所有评审结果摘要的 PDF 报告
3. THE Project_Dashboard SHALL 在导出报告中包含项目简介（如已提取）和各维度评分汇总
4. IF 项目没有任何评审记录，THEN THE Project_Dashboard SHALL 在导出报告中标注"暂无评审记录"
