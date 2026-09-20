import os
import re
import json
import base64
import asyncio
from playwright.async_api import async_playwright
from openai import AsyncOpenAI

# ==================== 配置区（仅需修改这里） ====================

# 1. 蓝湖项目链接（必须包含完整的 #/...?pid=xxx）
LANHU_URL = "https://lanhuapp.com/web/#/item/project/board?pid=YOUR_PROJECT_ID"

# 2. 蓝湖 Cookie（首次运行可留空或保持默认，脚本会引导手动登录并输出新值）
# 💡 推荐改为: os.getenv("LANHU_COOKIE", "your_cookie_here") 避免硬编码泄露
COOKIE_STRING = "your_cookie_here"

# 3. 输出目录（截图和JSON会分别存入 screenshots/ 和 json/ 子文件夹）
OUTPUT_DIR = "./lanhu_output"

# 4. 🤖 VLM API 配置（必填）
VLM_API_KEY = "sk-xxxxxxxxxxxxxxxx"          # 你的大模型 API Key
VLM_BASE_URL = "https://api.openai.com/v1"   # API 地址（国内代理或兼容端点）
VLM_MODEL = "gpt-4o"                         # 模型名称 (推荐 gpt-4o / qwen-vl-max / claude-sonnet)

# 5. 分辨率与截图配置
VIEWPORT_WIDTH = 1920
VIEWPORT_HEIGHT = 1080
DEVICE_SCALE_FACTOR = 2       # 2x 高清，保证 VLM 识别细节
CANVAS_ONLY = True            # 仅截画布，去除蓝湖 UI 干扰
DELAY_BETWEEN_TABS = 3        # 操作间隔(秒)
RENDER_BUFFER = 2             # 渲染缓冲(秒)
SKIP_EXISTING = True          # 断点续传
MAX_RETRY = 2                 # 失败重试次数

# 6. 选择器（蓝湖改版时需 F12 调整）
TAB_SELECTOR = ".group_item_box > .image_name"
CANVAS_SELECTOR = ".detail_box"

# ==================== 配置区结束 ====================

# VLM 系统提示词（已内置最佳实践，无需修改）
SYSTEM_PROMPT = """你是一个资深 UI 逆向工程师。输入是设计稿截图，输出必须是严格的 JSON UI DSL。
规则：
1. 仅输出合法 JSON，不要任何解释、Markdown 标记或代码块符号
2. type 只能是: container | text | image | button | input | icon | divider
3. layout 只能是: flex-row | flex-col | grid | absolute
4. 所有尺寸单位为 px，颜色使用 HEX 格式
5. 忽略纯装饰性元素（如微弱阴影、复杂渐变背景），只保留结构与语义
6. 文本内容如果模糊不可读，用 "[placeholder]" 代替
7. 嵌套层级尽量扁平化，不超过 5 层
8. 为可复用模块添加 componentId 字段（如 "user-card", "nav-item"）"""


def parse_cookies(cookie_str: str) -> list:
    """将 Cookie 字符串解析为 Playwright 格式"""
    cookies = []
    if not cookie_str or cookie_str.strip() == "your_cookie_here":
        return cookies
    for item in cookie_str.split(';'):
        item = item.strip()
        if '=' in item:
            name, value = item.split('=', 1)
            cookies.append({
                "name": name.strip(),
                "value": value.strip(),
                "domain": ".lanhuapp.com",
                "path": "/"
            })
    return cookies


def safe_filename(name: str) -> str:
    """生成安全的文件名"""
    return re.sub(r'[\\/*?:"<>|\n\r\t]', '_', name.strip()) or "unnamed"


async def screenshot_to_ui_json(client: AsyncOpenAI, image_path: str) -> dict:
    """调用 VLM 将截图转换为 UI JSON"""
    with open(image_path, "rb") as f:
        img_base64 = base64.b64encode(f.read()).decode()

    try:
        response = await client.chat.completions.create(
            model=VLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}},
                    {"type": "text", "text": "将此设计稿转换为 UI JSON"}
                ]}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        raw = response.choices[0].message.content.strip()
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "json_parse_failed", "raw": raw}
    except Exception as e:
        return {"error": "api_call_failed", "message": str(e)}


async def take_tab_screenshot(page, index, filepath_template):
    """点击 Tab 并截图，返回最终文件路径"""
    tabs = await page.query_selector_all(TAB_SELECTOR)
    if index >= len(tabs):
        raise Exception(f"Tab 索引 {index} 超出范围（当前 {len(tabs)} 个）")

    tab_name = safe_filename(await tabs[index].inner_text())
    final_path = filepath_template.replace("__NAME__", tab_name)

    await tabs[index].click()
    await page.wait_for_selector(CANVAS_SELECTOR, timeout=15000)
    await page.wait_for_timeout(RENDER_BUFFER * 1000)

    if CANVAS_ONLY:
        canvas = await page.query_selector(CANVAS_SELECTOR)
        if canvas:
            await canvas.screenshot(path=final_path)
        else:
            print(f"   ⚠️ 未找到画布选择器，回退到全页截图")
            await page.screenshot(path=final_path)
    else:
        await page.screenshot(path=final_path)

    return final_path


async def main():
    # 创建输出子目录
    ss_dir = os.path.join(OUTPUT_DIR, "screenshots")
    json_dir = os.path.join(OUTPUT_DIR, "json")
    os.makedirs(ss_dir, exist_ok=True)
    os.makedirs(json_dir, exist_ok=True)

    # 初始化 VLM 客户端
    vlm_client = AsyncOpenAI(api_key=VLM_API_KEY, base_url=VLM_BASE_URL)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
            device_scale_factor=DEVICE_SCALE_FACTOR,
            locale="zh-CN",
        )
        page = await context.new_page()

        # ==================== ✅ 智能 Cookie 处理逻辑 ====================
        has_valid_cookie = COOKIE_STRING and COOKIE_STRING.strip() != "your_cookie_here"

        if has_valid_cookie:
            print("🍪 检测到配置区已填写 Cookie，尝试注入...")
            cookies = parse_cookies(COOKIE_STRING)
            await context.add_cookies(cookies)
            try:
                await page.goto(LANHU_URL, wait_until="commit", timeout=20000)
                await page.wait_for_url("**/project/board?pid=**", timeout=10000)
                print("✅ Cookie 验证通过，项目页面加载成功")
            except Exception:
                print("⚠️ Cookie 已失效或无法访问项目，将切换为手动登录模式...")
                has_valid_cookie = False
        else:
            print("ℹ️ 未检测到有效 Cookie，请准备手动登录")

        # ✅ 手动登录兜底 + 自动抓取新 Cookie
        if not has_valid_cookie:
            print("\n🔐 请在弹出的浏览器窗口中完成蓝湖登录")
            print("👉 登录成功并看到项目画布后，回到终端按 Enter 键继续...\n")

            # 先打开蓝湖首页方便用户登录
            if "lanhuapp.com" not in page.url:
                await page.goto("https://lanhuapp.com/", wait_until="domcontentloaded")

            input()  # ⏸️ 暂停等待用户操作

            # 用户确认后，导航到目标项目页
            print("🔄 正在跳转到目标项目...")
            try:
                await page.goto(LANHU_URL, wait_until="commit", timeout=30000)
                await page.wait_for_url("**/project/board?pid=**", timeout=15000)
            except Exception as e:
                print(f"⚠️ 跳转超时(可能已自动跳转): {e}")

            await page.wait_for_timeout(3000)

            # 🎯 抓取并输出最新 Cookie
            new_cookies = await context.cookies()
            new_cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in new_cookies])

            print("\n" + "=" * 70)
            print("🎉 登录成功！以下是最新的 Cookie 值：")
            print("-" * 70)
            print(new_cookie_str)
            print("-" * 70)
            print("💡 提示: 请复制上方内容粘贴到脚本配置区的 COOKIE_STRING 中")
            print("=" * 70 + "\n")
        # ==================== Cookie 处理逻辑结束 ====================

        # Tab 检测
        tabs = await page.query_selector_all(TAB_SELECTOR)
        if len(tabs) == 0:
            print("\n⚠️  未检测到 Tab，可能页面未加载完成。")
            print("👉 请确认项目页面已完全加载，然后回终端按 Enter...")
            input()
            await page.wait_for_timeout(2000)
            tabs = await page.query_selector_all(TAB_SELECTOR)
            if len(tabs) == 0:
                print("❌ 仍未检测到 Tab，请检查 TAB_SELECTOR")
                print(f"   当前URL: {page.url}")
                await browser.close()
                return

        total = len(tabs)
        print(f"\n✅ 检测到 {total} 个 Tab | 模型: {VLM_MODEL} | 倍率: {DEVICE_SCALE_FACTOR}x")
        print("=" * 60)

        success, skip, fail_list = 0, 0, []

        for i in range(total):
            ss_template = os.path.join(ss_dir, f"{i+1:03d}___NAME__.png")
            json_template = os.path.join(json_dir, f"{i+1:03d}___NAME__.json")

            # 断点续传：截图和JSON都存在才跳过
            if SKIP_EXISTING:
                prefix = f"{i+1:03d}_"
                ss_exists = any(f.startswith(prefix) for f in os.listdir(ss_dir))
                json_exists = any(f.startswith(prefix) for f in os.listdir(json_dir))
                if ss_exists and json_exists:
                    print(f"⏭️  [{i+1}/{total}] 已存在，跳过")
                    skip += 1
                    continue

            for attempt in range(1, MAX_RETRY + 1):
                try:
                    # Step 1: 截图
                    if not any(f.startswith(f"{i+1:03d}_") for f in os.listdir(ss_dir)):
                        img_path = await take_tab_screenshot(page, i, ss_template)
                    else:
                        existing = [f for f in os.listdir(ss_dir) if f.startswith(f"{i+1:03d}_")]
                        img_path = os.path.join(ss_dir, existing[0])

                    # Step 2: VLM 转 JSON
                    tab_name = safe_filename(
                        os.path.basename(img_path).replace('.png', '')
                    )
                    name_part = tab_name.split('_', 1)[-1] if '_' in tab_name else tab_name
                    json_path = json_template.replace("__NAME__", name_part)

                    print(f"🔄 [{i+1}/{total}] VLM 解析中: {os.path.basename(img_path)}")
                    ui_json = await screenshot_to_ui_json(vlm_client, img_path)

                    if "error" in ui_json:
                        raise Exception(ui_json.get("message", ui_json["error"]))

                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(ui_json, f, ensure_ascii=False, indent=2)

                    print(f"✅ [{i+1}/{total}] 完成: {os.path.basename(json_path)}")
                    success += 1
                    break

                except Exception as e:
                    print(f"   ⚠️ [{i+1}/{total}] 第{attempt}次失败: {e}")
                    if attempt == MAX_RETRY:
                        fail_list.append(i + 1)
                    else:
                        await asyncio.sleep(2)

            await asyncio.sleep(DELAY_BETWEEN_TABS)

        await browser.close()

    print("\n" + "=" * 60)
    print(f"🎉 全部完成！成功: {success} | 跳过: {skip} | 失败: {fail_list}")
    print(f"📁 截图目录: {os.path.abspath(ss_dir)}")
    print(f"📁 JSON 目录: {os.path.abspath(json_dir)}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
