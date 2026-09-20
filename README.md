# 🎨 蓝湖设计稿自动截图与 VLM UI JSON 提取工具

一键式自动化脚本，通过 Playwright 自动遍历蓝湖（Lanhu）项目画板并截取高清设计稿，随后调用多模态大模型（VLM）将截图逆向解析为结构化的 UI JSON DSL。

## ✨ 核心特性

- 🤖 **VLM 智能解析**：内置优化的 System Prompt，自动将设计稿截图转换为标准 UI JSON（支持 GPT-4o / Qwen-VL / Claude 等）。
- 🔐 **智能登录管理**：自动检测 Cookie 有效性。失效或未配置时，自动降级为手动登录，并**自动抓取打印最新 Cookie**。
- 🔄 **断点续传**：截图与 JSON 分离存储，中断后重新运行会自动跳过已完成的任务。
- 🖼️ **高清画布截取**：支持 2x 视网膜级分辨率截图，精准捕获 UI 细节，自动过滤蓝湖外围 UI 干扰。
- 🛡️ **Hash 路由保护**：专门针对蓝湖 SPA 架构优化，彻底解决 URL 参数（`?pid=xxx`）丢失问题。

---

## 📦 环境准备与安装

### 1. 环境要求

- Python 3.9+
- 稳定的网络连接（用于访问蓝湖和 VLM API）

### 2. 安装依赖

```bash
# 安装 Python 依赖包
pip install playwright openai

# 安装 Playwright 所需的 Chromium 浏览器内核
playwright install chromium
```

---

## 🚀 快速开始

### 第一步：基础配置

打开 `lanhu_to_json.py`，修改顶部配置区的基础信息：

```python
# 1. 填入你的蓝湖项目链接（必须包含完整的 #/...?pid=xxx）
LANHU_URL = "https://lanhuapp.com/web/#/item/project/board?pid=YOUR_PROJECT_ID"

# 2. 填入你的大模型 API Key（支持 OpenAI 兼容接口）
VLM_API_KEY = "sk-xxxxxxxxxxxxxxxx"
VLM_BASE_URL = "https://api.openai.com/v1" # 或国内代理/其他兼容端点
VLM_MODEL = "gpt-4o"                       # 推荐 gpt-4o / qwen-vl-max
```

### 第二步：首次运行（获取 Cookie）

1. 保持 `COOKIE_STRING = "your_cookie_here"` 不变。
2. 在终端运行脚本：
  
  ```bash
  python lanhu_to_json.py
  ```
  
3. 脚本会自动打开浏览器并停在蓝湖首页。
4. **在浏览器中手动完成登录**，进入项目页面。
5. 回到终端，**按下 Enter 键**。
6. 终端会打印出最新的 Cookie 字符串，**复制它并粘贴到脚本的 `COOKIE_STRING` 配置中**。

### 第三步：后续自动化运行

配置好 Cookie 后，再次运行脚本：

```bash
python lanhu_to_json.py
```

脚本将自动注入 Cookie，跳过登录，依次点击 Tab 截图并调用 VLM 生成 JSON。

---

## ⚙️ 配置项详细说明

| 配置项 | 默认值 | 说明  |
| --- | --- | --- |
| `LANHU_URL` | -   | 蓝湖项目看板链接，**必须包含 `#` 和 `?pid=` 参数**。 |
| `COOKIE_STRING` | `"your_cookie_here"` | 蓝湖登录凭证。建议改为 `os.getenv("LANHU_COOKIE", "your_cookie_here")`。 |
| `OUTPUT_DIR` | `"./lanhu_output"` | 输出根目录，内部会自动创建 `screenshots/` 和 `json/` 子目录。 |
| `VLM_API_KEY` | -   | 多模态大模型的 API Key。 |
| `VLM_BASE_URL` | OpenAI 官方 | API 请求地址。通义千问、DeepSeek 等需替换为对应兼容端点。 |
| `VLM_MODEL` | `"gpt-4o"` | 模型名称。推荐视觉能力强的模型（如 `gpt-4o`, `qwen-vl-max`）。 |
| `DEVICE_SCALE_FACTOR` | `2` | 截图设备像素比。`2` 为高清，若 VLM 识别不佳可改为 `3`（会增加 Token 消耗）。 |
| `CANVAS_ONLY` | `True` | `True`: 仅截取画布区域；`False`: 截取包含蓝湖侧边栏的完整网页。 |
| `DELAY_BETWEEN_TABS` | `3` | 切换 Tab 后的等待时间（秒），防止页面未渲染完就截图。 |
| `SKIP_EXISTING` | `True` | 开启断点续传。若某 Tab 的截图和 JSON 均已存在，则跳过。 |
| `TAB_SELECTOR` | `".page-list-item"` | 蓝湖左侧/顶部页面列表的 DOM 选择器。蓝湖改版时需用 F12 重新获取。 |
| `CANVAS_SELECTOR` | `".board-canvas..."` | 蓝湖画布区域的 DOM 选择器。 |

---

## 💡 使用场景

1. **设计稿转代码 (Design to Code)**
  将生成的 UI JSON 直接作为 Context 喂给代码生成大模型（如 Cursor / Copilot），Prompt 示例：
  
  > *"根据以下 UI JSON 结构，生成 React + TailwindCSS 组件代码：[粘贴 JSON]"*
  
2. **UI 自动化测试基线生成**
  通过解析 JSON 中的元素类型和层级，自动生成 Cypress / Playwright 的 UI 自动化测试脚本骨架。
3. **设计资产归档与检索**
  将设计稿转化为结构化数据，存入数据库，实现基于 UI 组件语义（如“查找所有包含搜索框的页面”）的检索。
4. **竞品分析**
  批量提取竞品设计稿的布局结构（Flex/Grid 比例、嵌套层级），进行量化分析。

---

## ❓ 常见问题 (FAQ)

### Q1: 运行后提示“未检测到 Tab”或截图全白？

**原因**：蓝湖前端版本更新，导致默认的 DOM 选择器失效。
**解决**：

1. 在浏览器中打开蓝湖项目页，按 `F12` 打开开发者工具。
2. 使用“元素选择器”点击左侧的页面列表项，复制其 CSS 选择器，替换脚本中的 `TAB_SELECTOR`。
3. 同样操作获取画布区域的选择器，替换 `CANVAS_SELECTOR`。

### Q2: VLM 返回的 JSON 格式报错或包含 Markdown 标记？

**原因**：部分小模型对 `response_format={"type": "json_object"}` 支持不佳。
**解决**：

1. 更换为 `gpt-4o` 或 `qwen-vl-max` 等指令遵循能力强的模型。
2. 在 `SYSTEM_PROMPT` 中追加强制约束：`"绝对不要输出 ```json 和 ``` 标记，只输出纯 JSON 字符串。"`

### Q3: 如何切换不同的 VLM 模型？

只需修改配置区的 `VLM_BASE_URL` 和 `VLM_MODEL`：

```python
# 通义千问 VL
VLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
VLM_MODEL = "qwen-vl-max"

# Claude Sonnet (需使用第三方兼容代理)
VLM_BASE_URL = "https://your-claude-proxy.com/v1"
VLM_MODEL = "claude-3-5-sonnet-20240620"
```

### Q4: 截图太模糊，VLM 识别不出小字？

**解决**：将 `DEVICE_SCALE_FACTOR` 从 `2` 提高到 `3`。注意：这会显著增加图片体积和 API Token 消耗。

---

## 🔒 安全与最佳实践

**切勿将包含真实 Cookie 的脚本提交到 Git 仓库！**

建议将 Cookie 改为从环境变量读取：

```python
# 修改脚本配置区
import os
COOKIE_STRING = os.getenv("LANHU_COOKIE", "your_cookie_here")
```

**运行方式**：

```bash
# Linux / macOS
LANHU_COOKIE="your_actual_cookie_string" python lanhu_to_json.py

# Windows (CMD)
set LANHU_COOKIE=your_actual_cookie_string
python lanhu_to_json.py

# Windows (PowerShell)
$env:LANHU_COOKIE="your_actual_cookie_string"
python lanhu_to_json.py
```

---

## 📂 输出目录结构

运行成功后，将在 `OUTPUT_DIR` 下生成以下结构：

```text
lanhu_output/
├── screenshots/          # 高清设计稿截图
│   ├── 001_首页.png
│   ├── 002_用户中心.png
│   └── 003_设置页.png
└── json/                 # VLM 提取的结构化 UI JSON
    ├── 001_首页.json
    ├── 002_用户中心.json
    └── 003_设置页.json
```
