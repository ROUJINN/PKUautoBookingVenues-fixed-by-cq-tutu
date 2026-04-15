import datetime
import time
from playwright.sync_api import Playwright, sync_playwright
from captcha_solver import solve_click_captcha


WEEKDAY_NAMES = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def build_target_date_text(days_ahead: int = 3) -> str:
    target_date = datetime.date.today() + datetime.timedelta(days=days_ahead)
    weekday = WEEKDAY_NAMES[target_date.weekday()]
    return f"{weekday}{target_date:%m月%d日}"


def wait_until_refresh_time() -> None:
    now = datetime.datetime.now()
    refresh_start = now.replace(hour=11, minute=59, second=45, microsecond=0)
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
    print(f"开始刷新，等待日期出现: {target_text}")
    attempt = 0
    while True:
        attempt += 1
        page.reload(wait_until="domcontentloaded")
        wait_for_page_ready(page)
        target_locator = find_target_date(page, target_text)
        if target_locator is not None:
            print(f"第 {attempt} 次刷新后找到目标日期: {target_text}")
            target_locator.click()
            return
        if attempt % 10 == 0:
            print(f"已刷新 {attempt} 次，仍未找到目标日期: {target_text}")
        time.sleep(1)


def run(playwright: Playwright) -> None:
    target_date_text = build_target_date_text(days_ahead=3)
    # target_date_text = 星期五04月17日
    print(f"目标日期: {target_date_text}")

    browser = playwright.chromium.launch(channel="msedge", headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://epe.pku.edu.cn/venue/venue-reservation/86")
    page.get_by_role("button", name="确定").click()
    page.get_by_role("link", name="统一身份认证登录（IAAA）").click()
    page.get_by_role("textbox", name="User ID / PKU Email / Cell").fill("2200011351")
    page.get_by_role("textbox", name="User ID / PKU Email / Cell").press("Tab")
    page.get_by_role("textbox", name="Password").fill("luo041010")
    page.get_by_role("button", name="Login", exact=True).click()
    wait_for_target_date(page, target_date_text)
    page.locator(".ivu-table-cell > .ivu-icon").first.click()
    page.locator("td:nth-child(6) > .ivu-table-cell > .ivu-icon").first.click()
    # 第一个数代表几号场地
    # 第二个数，3 代表晚上6-7点，4 代表 7-8，5 代表 8-9
    page.locator("tr:nth-child(7) > td:nth-child(5) > .reserveBlock > div > .two-tows-overflow-ellipsis").click()
    page.get_by_role("checkbox", name="已阅读并同意").check()
    page.get_by_text("提交", exact=True).click()
    try:
        solve_click_captcha(page)
    except Exception as exc:
        print(f"ddddocr 自动识别失败: {exc}")
    page.pause()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
