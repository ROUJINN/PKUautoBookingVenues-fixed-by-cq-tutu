import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
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
    page.get_by_text("星期五04月17日").click()
    page.locator(".ivu-table-cell > .ivu-icon").first.click()
    page.locator("td:nth-child(6) > .ivu-table-cell > .ivu-icon").first.click()
    # 第一个数代表几号场地
    # 第二个数，3 代表晚上6-7点，4 代表 7-8，5 代表 8-9
    page.locator("tr:nth-child(7) > td:nth-child(5) > .reserveBlock > div > .two-tows-overflow-ellipsis").click()
    page.get_by_role("checkbox", name="已阅读并同意").check()
    page.get_by_text("提交", exact=True).click()
    page.pause()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
