当前主入口是 `pw.py`，使用 Playwright 抢场地，验证码使用本地 `ddddocr` 自动点选。

安装依赖：

```bash
pip install -r requirements.txt
playwright install chromium
```

运行：

```bash
python pw.py
```

说明：
1. 日期默认按“大后天”计算
2. 如果大后天日期还没放出，会在 11:59:45 开始刷新页面，直到该日期出现后立刻继续
3. 提交后会尝试用 `ddddocr` 自动处理点选验证码
4. 旧的 Selenium 版本脚本已归档到 `legacy_selenium/`
