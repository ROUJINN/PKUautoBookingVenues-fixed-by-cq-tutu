import re
import threading

# 并行模式下，各线程通过此集合协调，避免 fallback 时抢同一个场地
_claimed_venues: set[int] = set()
_claimed_lock = threading.Lock()


def claim_venue(venue_no: int) -> bool:
    """尝试认领一个场地号，返回 True 表示成功，False 表示已被其他线程认领。"""
    with _claimed_lock:
        if venue_no in _claimed_venues:
            return False
        _claimed_venues.add(venue_no)
        return True


def reset_claims() -> None:
    """重置所有认领记录（新一轮抢场前调用）。"""
    with _claimed_lock:
        _claimed_venues.clear()


def normalize_time_range(text: str) -> str:
    match = re.search(
        r"(\d{1,2})\s*[:：]\s*(\d{2})\s*[-~－—–]\s*(\d{1,2})\s*[:：]\s*(\d{2})",
        text,
    )
    if not match:
        return re.sub(r"\s+", "", text)

    start_hour, start_minute, end_hour, end_minute = match.groups()
    return f"{int(start_hour):02d}:{start_minute}-{int(end_hour):02d}:{end_minute}"


def _parse_start_minutes(time_range: str) -> int | None:
    """从标准化时间段 'HH:MM-HH:MM' 提取起始时间的分钟数，用于比较先后。"""
    match = re.match(r"(\d{2}):(\d{2})-\d{2}:\d{2}$", time_range)
    if not match:
        return None
    return int(match.group(1)) * 60 + int(match.group(2))


def extract_venue_no(text: str) -> int | None:
    match = re.search(r"(\d+)\s*(?:号|#)?\s*(?:场|片|空间)?", text)
    return int(match.group(1)) if match else None


def wait_for_table_rendered(page, wait_for_page_ready) -> None:
    page.locator("#scrollTable table").wait_for(state="visible", timeout=10_000)
    wait_for_page_ready(page)


def get_visible_time_columns(page) -> dict[str, int]:
    header_cells = page.locator("#scrollTable thead tr").first.locator("td")
    time_columns = {}

    for index in range(1, header_cells.count()):
        text = header_cells.nth(index).inner_text(timeout=1_000)
        normalized = normalize_time_range(text)
        if re.match(r"\d{2}:\d{2}-\d{2}:\d{2}$", normalized):
            time_columns[normalized] = index

    return time_columns


def click_next_time_page(page, wait_for_page_ready) -> bool:
    next_buttons = [
        page.locator("#scrollTable thead tr td").last.locator(".ivu-icon"),
        page.locator("#scrollTable tbody tr").first.locator("td").last.locator(".ivu-icon"),
        page.locator("#scrollTable td:nth-child(6) > .ivu-table-cell > .ivu-icon"),
    ]

    for button in next_buttons:
        if button.count() == 0:
            continue
        button.first.click()
        wait_for_table_rendered(page, wait_for_page_ready)
        return True

    return False


def _decide_page_direction(time_columns: dict[str, int], target_start: int | None) -> int:
    """根据当前可见时间与目标时间比较，决定翻页方向。

    返回值: 1 向后翻页, -1 向前翻页, 0 无法判断。
    """
    if target_start is None:
        return 0

    visible_starts = []
    for tr in time_columns:
        m = _parse_start_minutes(tr)
        if m is not None:
            visible_starts.append(m)

    if not visible_starts:
        return 0

    min_visible = min(visible_starts)
    max_visible = max(visible_starts)

    if target_start < min_visible:
        return -1  # 目标在前方，向前翻页
    if target_start > max_visible:
        return 1   # 目标在后方，向后翻页
    return 0  # 目标在当前范围内但未精确匹配，默认向后


def click_prev_time_page(page, wait_for_page_ready) -> bool:
    button = page.locator("#scrollTable .ivu-table-cell > .ivu-icon").first
    if button.count() == 0:
        return False
    button.click()
    wait_for_table_rendered(page, wait_for_page_ready)
    return True


def find_time_column(page, target_time_range: str, wait_for_page_ready) -> int:
    target_time_range = normalize_time_range(target_time_range)
    target_start = _parse_start_minutes(target_time_range)
    seen_headers = set()

    for _ in range(8):
        time_columns = get_visible_time_columns(page)
        if target_time_range in time_columns:
            print(f"找到目标时间列: {target_time_range}")
            return time_columns[target_time_range]

        header_signature = tuple(time_columns)
        if header_signature in seen_headers:
            break
        seen_headers.add(header_signature)

        # 根据目标时间与当前可见时间的比较决定翻页方向
        direction = _decide_page_direction(time_columns, target_start)
        if direction > 0:
            print(f"当前可见时间: {', '.join(time_columns) or '无'}，目标 {target_time_range} 在后方，继续向后翻页")
            if not click_next_time_page(page, wait_for_page_ready):
                break
        elif direction < 0:
            print(f"当前可见时间: {', '.join(time_columns) or '无'}，目标 {target_time_range} 在前方，继续向前翻页")
            if not click_prev_time_page(page, wait_for_page_ready):
                break
        else:
            print(f"当前可见时间: {', '.join(time_columns) or '无'}，无法判断翻页方向，继续向后翻页")
            if not click_next_time_page(page, wait_for_page_ready):
                break

    raise RuntimeError(f"找不到目标时间段: {target_time_range}")


def is_reservation_cell_available(cell) -> bool:
    return cell.evaluate(
        """td => {
            const block = td.querySelector('.reserveBlock');
            if (!block) return false;

            const className = String(block.className || '');
            return /(^|\\s)free(\\s|$)/.test(className);
        }"""
    )


def click_reservation_cell(cell) -> None:
    clickable = cell.locator(
        ".reserveBlock div .two-tows-overflow-ellipsis, "
        ".reserveBlock .two-tows-overflow-ellipsis, "
        ".reserveBlock"
    ).first
    clickable.click()


def _try_book_time_column(page, venue_no: int, time_range: str, time_column: int, allow_fallback: bool = True):
    """尝试在指定时间列预订目标场地，返回 (venue_no, time_range) 或 None 表示该时间列无可用场地。

    allow_fallback=True 时，目标场地不可用会尝试其他可用场地；
    通过 claim_venue 协调机制确保并行线程不会抢同一个 fallback 场地。
    """
    # 先认领自己的目标场地号，防止其他线程 fallback 到这里
    claim_venue(venue_no)

    rows = page.locator("#scrollTable tbody tr")
    fallback_cells = []
    found_target_venue = False

    for row_index in range(rows.count()):
        row = rows.nth(row_index)
        cells = row.locator("td")
        if cells.count() <= time_column:
            continue

        current_venue_no = extract_venue_no(cells.first.inner_text(timeout=1_000))
        if current_venue_no is None:
            continue

        cell = cells.nth(time_column)
        is_available = is_reservation_cell_available(cell)
        if current_venue_no == venue_no:
            found_target_venue = True
            if is_available:
                print(f"点击目标场地: {venue_no}号场 {normalize_time_range(time_range)}")
                click_reservation_cell(cell)
                return venue_no, time_range

        if is_available and allow_fallback:
            fallback_cells.append((current_venue_no, cell))

    if allow_fallback and fallback_cells:
        # 从可用场地中挑第一个未被其他线程认领的
        for fallback_venue_no, fallback_cell in fallback_cells:
            if claim_venue(fallback_venue_no):
                print(
                    f"{venue_no}号场在 {normalize_time_range(time_range)} 不可订，"
                    f"改点同时间的 {fallback_venue_no}号场"
                )
                click_reservation_cell(fallback_cell)
                return fallback_venue_no, time_range
        print(
            f"{venue_no}号场在 {normalize_time_range(time_range)} 不可订，"
            f"且所有可用场地均已被其他线程认领"
        )

    if not found_target_venue:
        raise RuntimeError("当前表格没有找到场地行，可能还未到开放时间或页面未加载出可预约场地")

    return None


def click_venue_by_semantics(page, venue_no: int, time_ranges: list[str], wait_for_page_ready, *, allow_fallback: bool = True) -> tuple[int, str]:
    """按优先级依次尝试多个时间段，返回 (场地号, 实际选定的时间段)。

    time_ranges 为优先顺序列表，越靠前优先级越高。
    allow_fallback=False 时，目标场地不可用不会抢其他场地，避免并行线程冲突。
    """
    wait_for_table_rendered(page, wait_for_page_ready)
    unavailable_ranges = []

    for time_range in time_ranges:
        try:
            time_column = find_time_column(page, time_range, wait_for_page_ready)
        except RuntimeError:
            print(f"时间段 {normalize_time_range(time_range)} 在表格中不存在，跳过")
            continue

        result = _try_book_time_column(page, venue_no, time_range, time_column, allow_fallback=allow_fallback)
        if result is not None:
            return result

        unavailable_ranges.append(normalize_time_range(time_range))
        print(f"{normalize_time_range(time_range)} 没有可订场地，尝试下一个优先时间段")

    if unavailable_ranges:
        raise RuntimeError(f"以下时间段均无可订场地: {', '.join(unavailable_ranges)}")

    raise RuntimeError("所有目标时间段在表格中均不存在")
