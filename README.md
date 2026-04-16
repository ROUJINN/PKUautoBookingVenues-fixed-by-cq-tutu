当前主入口是 `pw.py`，使用 Playwright 抢场地，验证码使用本地 `ddddocr` 自动点选。
uv run pw.py
即可

目前逻辑是：如果指定的场地没了，会自动改点同一时间段下第一个可订的其他场地。

具体在 [booking_table.py](/Users/mac/Desktop/code/PKUautoBookingVenues-fixed-by-cq-tutu/booking_table.py:99) 的 `click_venue_by_semantics()`：

1. 先找到目标时间列，比如 `20:00-21:00`。
2. 遍历所有场地行。
3. 如果找到 `TARGET_VENUE_NO = 5` 且该格子有 `.reserveBlock.free`，就点击 5 号场。
4. 如果 5 号场不可订，但同时间还有其他可订场地，会把可订格子加入 `fallback_cells`。
5. 遍历完后，如果 `fallback_cells` 不为空，就点击第一个可订的其他场地，并打印：

```text
5号场在 20:00-21:00 不可订，改点同时间的 X号场
```

然后 `pw.py` 会继续执行提交和验证码流程。

如果同一时间段所有场地都没了，则会抛异常：

```text
20:00-21:00 没有可订场地
```
这个异常目前没有在 `pw.py` 里捕获，所以脚本会直接中断，不会提交。