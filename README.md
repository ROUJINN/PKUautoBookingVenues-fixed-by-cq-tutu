当前主入口是 `pw.py`，使用 Playwright 抢场地，验证码使用本地 `ddddocr` 自动点选。

uv run pw.py

即可

说明：
1. 日期默认按“大后天”计算
2. 如果大后天日期还没放出，会在 11:59:55 开始刷新页面，直到该日期出现后立刻继续
3. 提交后会尝试用 `ddddocr` 自动处理点选验证码  

todo :

现在有一个问题，pw.py在选场地时，是需要在一个表格里来选，但是目前这样子 
    page.locator(".ivu-table-cell > .ivu-icon").first.click()
    page.locator("td:nth-child(6) > .ivu-table-cell > .ivu-icon").first.click()
    # 第一个数代表几号场地
    # 第二个数，3 代表晚上6-7点，4 代表 7-8，5 代表 8-9
    page.locator("tr:nth-child(7) > td:nth-child(5) > .reserveBlock > div > .two-tows-overflow-ellipsis").click()

test_captcha_solver.py已经确认没问题，需要到真实的网络里验证

