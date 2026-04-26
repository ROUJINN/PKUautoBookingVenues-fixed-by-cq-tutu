import datetime
import os
from pathlib import Path
import time
from playwright.sync_api import Playwright, sync_playwright
from booking_table import click_venue_by_semantics, normalize_time_range
from captcha_solver import solve_click_captcha, CAPTCHA_ORDER_XPATH


def _wait_for_captcha_refresh(page, old_order_text: str, timeout_ms: int = 3000):
    """点击刷新后，等待验证码提示文字变化（纯 DOM 事件驱动，无轮询截图）。"""
    page.wait_for_function(
        "(xpath, old) => { "
        "  const el = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue; "
        "  return el && el.textContent.trim() !== old; "
        "}",
        arg=[CAPTCHA_ORDER_XPATH, old_order_text],
        timeout=timeout_ms,
    )


WEEKDAY_NAMES = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
TARGET_DAYS_AHEAD = 3
REFRESH_START_HOUR = 12
REFRESH_START_MINUTE = 00
REFRESH_START_SECOND = 00
TARGET_VENUE_NO = 5
# TARGET_TIME_RANGE 按优先顺序排列，前面优先尝试；若某时间段无可用场地则自动尝试下一个
TARGET_TIME_RANGE = ["20:00-21:00","21:00-22:00","19:00-20:00"] # work day
# TARGET_TIME_RANGE = ["16:00-17:00","15:00-16:00","20:00-21:00","21:00-22:00","19:00-20:00"] # weekend
# TARGET_TIME_RANGE = ["20:00-21:00","21:00-22:00","06:50-07:50"]  # debug
# 这组参数是可以的，点太快会报非法校验
CAPTCHA_BEFORE_CLICK_DELAY = 0
CAPTCHA_CLICK_INTERVAL = 0.35  # 这里 0.2就不行,0.3有时候非法校验
CAPTCHA_AFTER_CLICK_DELAY = 0
DEBUG_DUMP_TABLE = os.getenv("DEBUG_DUMP_TABLE") == "1"
DEBUG_DIR = Path("debug_artifacts")
# 

def build_target_date_text(days_ahead: int = 3) -> str:
    target_date = datetime.date.today() + datetime.timedelta(days=days_ahead)
    weekday = WEEKDAY_NAMES[target_date.weekday()]
    return f"{weekday}{target_date:%m月%d日}"


def wait_until_refresh_time() -> None:
    now = datetime.datetime.now()
    refresh_start = now.replace(
        hour=REFRESH_START_HOUR,
        minute=REFRESH_START_MINUTE,
        second=REFRESH_START_SECOND,
        microsecond=0,
    )
    if now >= refresh_start:
        return

    wait_seconds = (refresh_start - now).total_seconds()
    print(f"等待到 {refresh_start.strftime('%H:%M:%S')} 开始刷新，剩余 {wait_seconds:.1f} 秒")
    time.sleep(wait_seconds)


def wait_for_page_ready(page) -> None:
    try:
        page.wait_for_load_state("domcontentloaded", timeout=3_000)
    except Exception:
        pass

    loading_mask = page.locator(".loading.ivu-spin.ivu-spin-large.ivu-spin-fix")
    try:
        loading_mask.wait_for(state="hidden", timeout=3_000)
    except Exception:
        pass

    # 给日期栏一个很短的渲染时间，避免刚 reload 完就立即判断。
    page.wait_for_timeout(200)


def find_target_date(page, target_text: str):
    locator = page.get_by_text(target_text, exact=False)
    return locator.first if locator.count() > 0 else None


def wait_for_target_date(page, target_text: str) -> None:
    wait_for_page_ready(page)

    target_locator = find_target_date(page, target_text)
    if target_locator is not None:
        print(f"目标日期已存在，直接点击: {target_text}")
        target_locator.click()
        return

    wait_until_refresh_time()
    print(f"到达刷新时间，执行一次刷新并等待日期出现: {target_text}")
    page.reload(wait_until="domcontentloaded")
    wait_for_page_ready(page)

    target_locator = page.get_by_text(target_text, exact=False).first
    print(f"等待页面内出现目标日期: {target_text}")
    target_locator.wait_for(state="visible", timeout=0)
    print(f"目标日期已出现，立即点击: {target_text}")
    target_locator.click()


def dump_booking_table_debug(page) -> None:
    DEBUG_DIR.mkdir(exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    html_path = DEBUG_DIR / f"booking_page_{timestamp}.html"
    screenshot_path = DEBUG_DIR / f"booking_page_{timestamp}.png"
    text_path = DEBUG_DIR / f"booking_table_text_{timestamp}.txt"

    html_path.write_text(page.content(), encoding="utf-8")
    page.screenshot(path=str(screenshot_path), full_page=True)

    table_candidates = page.locator("#scrollTable, .ivu-table-wrapper, table")
    text_parts = []
    for index in range(table_candidates.count()):
        candidate = table_candidates.nth(index)
        try:
            text_parts.append(f"--- candidate {index} ---\n{candidate.inner_text(timeout=1000)}")
        except Exception as exc:
            text_parts.append(f"--- candidate {index} read failed: {exc} ---")
    text_path.write_text("\n\n".join(text_parts), encoding="utf-8")

    print(f"已保存运行后页面 HTML: {html_path.resolve()}")
    print(f"已保存页面截图: {screenshot_path.resolve()}")
    print(f"已保存表格文本: {text_path.resolve()}")


def run(playwright: Playwright) -> None:
    target_date_text = build_target_date_text(days_ahead=TARGET_DAYS_AHEAD)
    # target_date_text = 星期五04月17日
    print(f"目标日期: {target_date_text}")

    browser = playwright.chromium.launch(channel="msedge", headless=False)
    context = browser.new_context()
    page = context.new_page()
    should_pause = False

    try:
        page.goto("https://epe.pku.edu.cn/venue/venue-reservation/86")
        page.get_by_role("button", name="确定").click()
        page.get_by_role("link", name="统一身份认证登录（IAAA）").click()
        page.get_by_role("textbox", name="User ID / PKU Email / Cell").fill("2200015825")
        page.get_by_role("textbox", name="User ID / PKU Email / Cell").press("Tab")
        page.get_by_role("textbox", name="Password").fill("Roujin520")
        page.get_by_role("button", name="Login", exact=True).click()
        wait_for_target_date(page, target_date_text)
        if DEBUG_DUMP_TABLE:
            dump_booking_table_debug(page)
            should_pause = True
            return

        selected_venue_no, selected_time = click_venue_by_semantics(
            page,
            TARGET_VENUE_NO,
            TARGET_TIME_RANGE,
            wait_for_page_ready,
        )
        print(f"已选择场地: {selected_venue_no}号场 {normalize_time_range(selected_time)}")
        page.get_by_role("checkbox", name="已阅读并同意").check()
        page.get_by_text("提交", exact=True).click()
        order_text_locator = page.locator(f"xpath={CAPTCHA_ORDER_XPATH}")
        max_captcha_retries = 10
        for captcha_attempt in range(1, max_captcha_retries + 1):
            try:
                solve_click_captcha(
                    page,
                    before_click_delay=CAPTCHA_BEFORE_CLICK_DELAY,
                    click_interval=CAPTCHA_CLICK_INTERVAL,
                    after_click_delay=CAPTCHA_AFTER_CLICK_DELAY,
                )
                break
            except Exception as exc:
                print(f"ddddocr 自动识别失败 (第{captcha_attempt}次): {exc}")
                if captcha_attempt < max_captcha_retries:
                    print("点击刷新按钮重试验证码")
                    old_order_text = order_text_locator.inner_text()
                    page.locator(".iconfont.icon-refresh").click()
                    try:
                        _wait_for_captcha_refresh(page, old_order_text)
                    except Exception:
                        pass  # 超时也继续，让 solve_click_captcha 自己判断
                else:
                    print(f"验证码重试已达上限 ({max_captcha_retries} 次)，放弃")
        page.pause()
    except Exception as exc:
        should_pause = True
        print(f"运行出错，已暂停浏览器供手动接管: {exc}")
    finally:
        if should_pause:
            page.pause()
        context.close()
        browser.close()


with sync_playwright() as playwright:
    run(playwright)
