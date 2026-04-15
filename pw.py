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


def wait_for_target_date(page, target_text: str) -> None:
    target_locator = page.get_by_text(target_text, exact=True)
    if target_locator.count() > 0:
        target_locator.first.click()
        return

    wait_until_refresh_time()
    print(f"开始刷新，等待日期出现: {target_text}")
    while True:
        page.reload(wait_until="domcontentloaded")
        if target_locator.count() > 0:
            print(f"目标日期已出现: {target_text}")
            target_locator.first.click()
            return


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
