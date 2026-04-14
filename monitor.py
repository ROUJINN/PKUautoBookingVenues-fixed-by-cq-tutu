import datetime
import os
import re
import time
from configparser import ConfigParser

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as Chrome_Options
from selenium.webdriver.edge.options import Options as Edge_Options
from selenium.webdriver.firefox.options import Options as Firefox_Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from notice import server_chan_notification
from page_func import go_to_venue, login


DATE_TAB_CONTAINER_XPATH = '/html/body/div[1]/div/div/div[3]/div[2]/div/div[1]/div[2]/div[1]/div[2]'
NEXT_PAGE_XPATH = '//*[@id="scrollTable"]/table/tbody/tr[last()]/td[last()]/div/i'
DEFAULT_MONITOR_FILE = 'monitor_rules.txt'
DEFAULT_VENUES = ['羽毛球场', '羽毛球馆']


def wait_until_ready(driver, timeout=10):
    WebDriverWait(driver, timeout).until_not(
        EC.visibility_of_element_located((By.CLASS_NAME, "loading.ivu-spin.ivu-spin-large.ivu-spin-fix")))


def load_monitor_config(config):
    conf = ConfigParser()
    conf.read(config, encoding='utf8')

    monitor_interval = conf.getint('monitor', 'interval_seconds', fallback=30)
    monitor_file = conf.get('monitor', 'state_file', fallback=DEFAULT_MONITOR_FILE).strip() or DEFAULT_MONITOR_FILE
    monitor_browser = conf.get('monitor', 'browser', fallback='edge').strip() or 'edge'
    monitor_headless = conf.getboolean('monitor', 'headless', fallback=True)
    venues_raw = conf.get('monitor', 'venues', fallback=','.join(DEFAULT_VENUES))
    venues = [item.strip() for item in re.split(r'[,，]', venues_raw) if item.strip()]
    if not venues:
        venues = DEFAULT_VENUES[:]

    return {
        'user_name': conf['login']['user_name'],
        'password': conf['login']['password'],
        'sckey': conf['wechat']['SCKEY'],
        'interval_seconds': max(5, monitor_interval),
        'state_file': monitor_file,
        'browser': monitor_browser.lower(),
        'headless': monitor_headless,
        'venues': venues,
    }


def build_driver(browser='edge', headless=True):
    if browser == "chrome":
        chrome_options = Chrome_Options()
        if headless:
            chrome_options.add_argument("--headless=new")
        return webdriver.Chrome(options=chrome_options)
    if browser == "edge":
        edge_options = Edge_Options()
        if headless:
            edge_options.add_argument("--headless=new")
        return webdriver.Edge(options=edge_options)
    if browser == "firefox":
        firefox_options = Firefox_Options()
        if headless:
            firefox_options.add_argument("--headless")
        return webdriver.Firefox(options=firefox_options)
    raise Exception("不支持此类浏览器")


def ensure_monitor_file(path):
    if os.path.exists(path):
        return
    with open(path, 'w', encoding='utf-8') as fw:
        fw.write("# 写日期可忽略整天，例如：2026-04-18\n")
        fw.write("# 也支持：IGNORE 2026-04-18\n")
        fw.write("# ALERT 行由程序自动追加；删掉某条 ALERT 后，若再次检测到同一空位，会重新提醒\n")


def read_monitor_state(path):
    ensure_monitor_file(path)
    ignore_dates = set()
    alerted_keys = set()
    with open(path, 'r', encoding='utf-8') as fr:
        for raw_line in fr:
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue
            if re.fullmatch(r'\d{4}-\d{2}-\d{2}', line):
                ignore_dates.add(line)
                continue
            if line.upper().startswith('IGNORE '):
                date_str = line.split(None, 1)[1].strip()
                if re.fullmatch(r'\d{4}-\d{2}-\d{2}', date_str):
                    ignore_dates.add(date_str)
                continue
            if line.upper().startswith('ALERT '):
                alerted_keys.add(line[6:].strip())
    return ignore_dates, alerted_keys


def append_alert_records(path, alert_keys):
    if not alert_keys:
        return
    ensure_monitor_file(path)
    with open(path, 'a', encoding='utf-8') as fw:
        for alert_key in alert_keys:
            fw.write(f'ALERT {alert_key}\n')


def slot_key(slot):
    return f"{slot['date']}|{slot['venue']}|{slot['court']}|{slot['time_range']}"


def describe_slots(slots):
    return '\n'.join([f"{slot['date']} {slot['venue']} {slot['court']}号场 {slot['time_range']}" for slot in slots])


def notify_slots(slots, sckey):
    if not sckey or sckey == 'XXXX':
        print("未配置 Server 酱 SCKEY，跳过通知")
        return False
    title = f"发现 {len(slots)} 个羽毛球空位"
    desp = describe_slots(slots)
    server_chan_notification(title, desp, sckey)
    return True


def reset_to_portal_tab(driver):
    handles = driver.window_handles
    while len(handles) > 1:
        driver.switch_to.window(handles[-1])
        driver.close()
        handles = driver.window_handles
    driver.switch_to.window(handles[0])


def get_visible_day_count(driver):
    container = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.XPATH, DATE_TAB_CONTAINER_XPATH)))
    return len(container.find_elements(By.XPATH, './div'))


def click_day_tab(driver, day_index):
    wait_until_ready(driver)
    driver.find_element(By.XPATH, f'{DATE_TAB_CONTAINER_XPATH}/div[{day_index + 1}]').click()
    time.sleep(0.5)
    wait_until_ready(driver)


def next_page(driver):
    wait_until_ready(driver)
    driver.find_element(By.XPATH, NEXT_PAGE_XPATH).click()
    time.sleep(0.3)
    wait_until_ready(driver)


def allowed_hours_for_date(target_date):
    if target_date.weekday() >= 5:
        return list(range(9, 22))
    return list(range(19, 22))


def venue_base_hour(venue):
    if venue == '羽毛球场':
        return 8
    if venue == '羽毛球馆':
        return 7
    return 0


def build_page_targets(venue, hours):
    base_hour = venue_base_hour(venue)
    page_targets = {}
    for hour in hours:
        offset = hour - base_hour
        if offset < 0:
            continue
        page = offset // 5
        col = offset % 5 + 1
        page_targets.setdefault(page, []).append((hour, col))
    return page_targets


def read_table_rows(driver):
    tbodies = driver.find_elements(By.TAG_NAME, 'tbody')
    if len(tbodies) < 2:
        return []
    trs = tbodies[1].find_elements(By.TAG_NAME, 'tr')
    rows = []
    for tr in trs[:-1]:
        rows.append(tr.find_elements(By.TAG_NAME, 'td'))
    return rows


def collect_free_slots_for_date(driver, venue, target_date):
    hours = allowed_hours_for_date(target_date)
    page_targets = build_page_targets(venue, hours)
    found_slots = []
    current_page = 0
    for page in sorted(page_targets.keys()):
        while current_page < page:
            next_page(driver)
            current_page += 1
        rows = read_table_rows(driver)
        for court_index, row in enumerate(rows, start=1):
            for hour, col in page_targets[page]:
                if col >= len(row):
                    continue
                class_name = row[col].find_element(By.TAG_NAME, 'div').get_attribute("class")
                if 'free' not in class_name.split():
                    continue
                found_slots.append({
                    'date': target_date.strftime('%Y-%m-%d'),
                    'venue': venue,
                    'court': court_index,
                    'time_range': f'{hour:02d}:00-{hour + 1:02d}:00',
                })
    return found_slots


def scan_venue(driver, venue, ignore_dates, alerted_keys):
    reset_to_portal_tab(driver)
    status, log_str = go_to_venue(driver, venue)
    print(log_str.strip())
    if not status:
        return []

    driver.switch_to.window(driver.window_handles[-1])
    wait_until_ready(driver)

    visible_day_count = get_visible_day_count(driver)
    print(f"{venue} 当前可见日期数：{visible_day_count}")
    today = datetime.date.today()
    new_slots = []

    for day_index in range(visible_day_count):
        driver.refresh()
        wait_until_ready(driver)
        click_day_tab(driver, day_index)
        target_date = today + datetime.timedelta(days=day_index)
        date_str = target_date.strftime('%Y-%m-%d')
        if date_str in ignore_dates:
            print(f"跳过忽略日期：{date_str}")
            continue
        found_slots = collect_free_slots_for_date(driver, venue, target_date)
        for slot in found_slots:
            if slot_key(slot) not in alerted_keys:
                new_slots.append(slot)
    return new_slots


def monitor(config='config0.ini'):
    monitor_conf = load_monitor_config(config)
    state_path = os.path.abspath(monitor_conf['state_file'])
    ensure_monitor_file(state_path)

    while True:
        driver = None
        try:
            driver = build_driver(monitor_conf['browser'], monitor_conf['headless'])
            print(f"[{datetime.datetime.now()}] 启动浏览器并登录")
            login(driver, monitor_conf['user_name'], monitor_conf['password'])

            while True:
                print(f"[{datetime.datetime.now()}] 开始新一轮监测")
                ignore_dates, alerted_keys = read_monitor_state(state_path)
                pending_slots = []
                for venue in monitor_conf['venues']:
                    pending_slots.extend(scan_venue(driver, venue, ignore_dates, alerted_keys))

                if pending_slots:
                    pending_slots.sort(key=lambda item: (item['date'], item['venue'], item['court'], item['time_range']))
                    alert_keys = [slot_key(slot) for slot in pending_slots]
                    print("发现空位：")
                    print(describe_slots(pending_slots))
                    if notify_slots(pending_slots, monitor_conf['sckey']):
                        append_alert_records(state_path, alert_keys)
                else:
                    print("本轮未发现新的可提醒空位")

                time.sleep(monitor_conf['interval_seconds'])
        except KeyboardInterrupt:
            print("监测已停止")
            break
        except Exception as exc:
            print(f"监测异常，稍后重试：{exc}")
            time.sleep(monitor_conf['interval_seconds'])
        finally:
            if driver is not None:
                driver.quit()
