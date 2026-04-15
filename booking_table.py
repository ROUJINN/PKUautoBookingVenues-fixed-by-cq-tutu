import re


def normalize_time_range(text: str) -> str:
    match = re.search(
        r"(\d{1,2})\s*[:：]\s*(\d{2})\s*[-~－—–]\s*(\d{1,2})\s*[:：]\s*(\d{2})",
        text,
    )
    if not match:
        return re.sub(r"\s+", "", text)

    start_hour, start_minute, end_hour, end_minute = match.groups()
    return f"{int(start_hour):02d}:{start_minute}-{int(end_hour):02d}:{end_minute}"


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


def find_time_column(page, target_time_range: str, wait_for_page_ready) -> int:
    target_time_range = normalize_time_range(target_time_range)
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

        print(f"当前可见时间: {', '.join(time_columns) or '无'}，继续翻页查找 {target_time_range}")
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


def click_venue_by_semantics(page, venue_no: int, time_range: str, wait_for_page_ready) -> int:
    wait_for_table_rendered(page, wait_for_page_ready)
    time_column = find_time_column(page, time_range, wait_for_page_ready)
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
                return venue_no

        if is_available:
            fallback_cells.append((current_venue_no, cell))

    if fallback_cells:
        fallback_venue_no, fallback_cell = fallback_cells[0]
        print(
            f"{venue_no}号场在 {normalize_time_range(time_range)} 不可订，"
            f"改点同时间的 {fallback_venue_no}号场"
        )
        click_reservation_cell(fallback_cell)
        return fallback_venue_no

    if not found_target_venue:
        raise RuntimeError("当前表格没有找到场地行，可能还未到开放时间或页面未加载出可预约场地")

    raise RuntimeError(f"{normalize_time_range(time_range)} 没有可订场地")
