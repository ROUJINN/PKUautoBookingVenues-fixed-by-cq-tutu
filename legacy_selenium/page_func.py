from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from urllib.parse import quote
import time
import datetime
import warnings
import io
import os
import re
import traceback
from selenium.webdriver.common.action_chains import ActionChains
import base64
from PIL import Image

try:
    from ddddocr.ddddocr import DdddOcr
    DDDDOCR_IMPORT_ERROR = None
except Exception as exc:
    DdddOcr = None
    DDDDOCR_IMPORT_ERROR = exc

warnings.filterwarnings('ignore')

_TEXT_DETECTOR = None
_TEXT_CLASSIFIER = None


def dump_debug_artifacts(driver, prefix):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = f"{prefix}_{timestamp}.png"
    html_path = f"{prefix}_{timestamp}.html"

    try:
        driver.save_screenshot(screenshot_path)
        print(f"已保存截图: {os.path.abspath(screenshot_path)}")
    except Exception as exc:
        print(f"保存截图失败: {exc}")

    try:
        with open(html_path, "w", encoding="utf-8") as fw:
            fw.write(driver.page_source)
        print(f"已保存页面源码: {os.path.abspath(html_path)}")
    except Exception as exc:
        print(f"保存页面源码失败: {exc}")


def login(driver, user_name, password, retry=0):
    if retry == 3:
        return '门户登录失败\n'

    print('门户登录中...')

    appID = 'portal2017'
    iaaaUrl = 'https://iaaa.pku.edu.cn/iaaa/oauth.jsp'
    appName = quote('北京大学校内信息门户新版')
    redirectUrl = 'https://portal.pku.edu.cn/portal2017/ssoLogin.do'
    driver.get('https://portal.pku.edu.cn/portal2017/')
    driver.get(f'{iaaaUrl}?appID={appID}&appName={appName}&redirectUrl={redirectUrl}')
    time.sleep(2)
    WebDriverWait(driver, 10).until_not(
        EC.visibility_of_element_located((By.CLASS_NAME, "loading.ivu-spin.ivu-spin-large.ivu-spin-fix")))
    WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, 'logon_button')))
    driver.find_element(By.ID, 'user_name').send_keys(user_name)
    WebDriverWait(driver, 10).until_not(
        EC.visibility_of_element_located((By.CLASS_NAME, "loading.ivu-spin.ivu-spin-large.ivu-spin-fix")))
    time.sleep(0.2)
    driver.find_element(By.ID, 'password').send_keys(password)
    WebDriverWait(driver, 10).until_not(
        EC.visibility_of_element_located((By.CLASS_NAME, "loading.ivu-spin.ivu-spin-large.ivu-spin-fix")))
    time.sleep(0.2)
    driver.find_element(By.ID, 'logon_button').click()
    try:
        WebDriverWait(driver, 50).until(EC.visibility_of_element_located((By.ID, 'all')))
        print('门户登录成功')
        return '门户登录成功\n'
    except:
        print('Retrying...')
        login(driver, user_name, password, retry + 1)


def go_to_venue(driver, venue, retry=0):
    if retry == 3:
        print("进入预约 %s 界面失败" % venue)
        log_str = "进入预约 %s 界面失败\n" % venue
        return False, log_str

    print("进入预约 %s 界面" % venue)
    log_str = "进入预约 %s 界面\n" % venue

    try:
        butt_all = driver.find_element(By.ID, 'all')
        driver.execute_script('arguments[0].click();', butt_all)
        WebDriverWait(driver, 10).until_not(
            EC.visibility_of_element_located((By.CLASS_NAME, "loading.ivu-spin.ivu-spin-large.ivu-spin-fix")))
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.ID, 'tag_s_venues')))
        time.sleep(0.5)
        driver.find_element(By.ID, 'tag_s_venues').click()
        while len(driver.window_handles) < 2:
            time.sleep(0.5)
        driver.switch_to.window(driver.window_handles[-1])
        WebDriverWait(driver, 10).until_not(
            EC.visibility_of_element_located((By.CLASS_NAME, "loading.ivu-spin.ivu-spin-large.ivu-spin-fix")))
        time.sleep(5)
        WebDriverWait(driver, 10).until(EC.visibility_of_element_located(
            (By.XPATH, "/html/body/div[1]/div/div/div[2]/div[1]/div[2]/div[1]/div[2]/div[2]/div")))
        driver.find_element(By.XPATH,
                            "/html/body/div[1]/div/div/div[2]/div[1]/div[2]/div[1]/div[2]/div[2]/div").click()
        WebDriverWait(driver, 10).until_not(
            EC.visibility_of_element_located((By.CLASS_NAME, "loading.ivu-spin.ivu-spin-large.ivu-spin-fix")))
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, f"//*[contains(text(), '{venue}')]")))
        time.sleep(2)
        driver.find_element(By.XPATH,
                            f"//*[contains(text(), '{venue}')]").click()
        status = True
        log_str += "进入预约 %s 界面成功\n" % venue
    except Exception as exc:
        print(f"go_to_venue 第 {retry + 1} 次失败: {type(exc).__name__}: {exc}")
        print(f"当前 URL: {driver.current_url}")
        print(f"当前标题: {driver.title}")
        print(traceback.format_exc())
        dump_debug_artifacts(driver, f"debug_go_to_venue_retry{retry + 1}")
        print("retrying")
        status, log_str = go_to_venue(driver, venue, retry + 1)
    return status, log_str


def click_agree(driver):
    print("点击同意")
    log_str = "点击同意\n"
    driver.switch_to.window(driver.window_handles[-1])
    WebDriverWait(driver, 10).until_not(
        EC.visibility_of_element_located((By.CLASS_NAME, "loading.ivu-spin.ivu-spin-large.ivu-spin-fix")))
    WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.CLASS_NAME, 'ivu-checkbox-wrapper')))
    driver.find_element(By.CLASS_NAME, 'ivu-checkbox-wrapper').click()
    print("点击同意成功\n")
    log_str += "点击同意成功\n"
    return log_str


def judge_exceeds_days_limit(start_time, end_time):
    start_time_list = start_time.split('/')
    end_time_list = end_time.split('/')
    print(start_time_list, end_time_list)
    now = datetime.datetime.today()
    today = datetime.datetime.strptime(str(now)[:10], "%Y-%m-%d")
    time_hour = datetime.datetime.strptime(
        str(now).split()[1][:-7], "%H:%M:%S")
    time_11_55 = datetime.datetime.strptime(
        "11:55:00", "%H:%M:%S")
    # time_11_55 = datetime.datetime.strptime(
    #     str(now).split()[1][:-7], "%H:%M:%S")

    start_time_list_new = []
    end_time_list_new = []
    delta_day_list = []
    log_str = ""
    for k in range(len(start_time_list)):
        start_time = start_time_list[k]
        end_time = end_time_list[k]
        if len(start_time) > 8:
            date = datetime.datetime.strptime(
                start_time.split('-')[0], "%Y%m%d")
            delta_day = (date - today).days
        else:
            delta_day = (int(start_time[0]) + 6 - today.weekday()) % 7
            date = today + datetime.timedelta(days=delta_day)
        print("日期:", str(date).split()[0])

        if delta_day > 3 or (delta_day == 3 and (time_hour < time_11_55)):
            print("只能在当天中午11:55后预约未来3天以内的场馆")
            log_str = "只能在当天中午11:55后预约未来3天以内的场馆\n"
            break
        else:
            start_time_list_new.append(start_time)
            end_time_list_new.append(end_time)
            delta_day_list.append(delta_day)
            print("在预约可预约日期范围内")
            log_str = "在预约可预约日期范围内\n"
    return start_time_list_new, end_time_list_new, delta_day_list, log_str


def book(driver, start_time_list, end_time_list, delta_day_list, venue, venue_num=-1):
    print("查找空闲场地")
    log_str = "查找空闲场地\n"

    def judge_close_to_time_12():
        now = datetime.datetime.today()
        time_hour = datetime.datetime.strptime(
            str(now).split()[1][:-7], "%H:%M:%S")
        time_11_55 = datetime.datetime.strptime(
            "11:55:00", "%H:%M:%S")
        time_12 = datetime.datetime.strptime(
            "12:00:00", "%H:%M:%S")
        if time_hour < time_11_55:
            return 0
        elif time_11_55 < time_hour < time_12:
            return 1
        elif time_hour > time_12:
            return 2

    def judge_in_time_range(start_time, end_time, venue_time_range):
        vt = venue_time_range.split('-')
        vt_start_time = datetime.datetime.strptime(vt[0], "%H:%M")
        vt_end_time = datetime.datetime.strptime(vt[1], "%H:%M")
        # print(vt_start_time)
        # print(start_time)
        if start_time <= vt_start_time and vt_end_time <= end_time:
            return True
        else:
            return False

    def move_to_date(delta_day):
        # for i in range(delta_day):
        WebDriverWait(driver, 10).until_not(
            EC.visibility_of_element_located((By.CLASS_NAME, "loading.ivu-spin.ivu-spin-large.ivu-spin-fix")))
        driver.find_element(By.XPATH,
                            f'/html/body/div[1]/div/div/div[3]/div[2]/div/div[1]/div[2]/div[1]/div[2]/div[{delta_day + 1}]').click()
        # time.sleep(0.2)

    def next_page():
        # 如果第一页没有，就往后翻，直到不存在下一页
        WebDriverWait(driver, 10).until_not(
            EC.visibility_of_element_located((By.CLASS_NAME, "loading.ivu-spin.ivu-spin-large.ivu-spin-fix")))
        # time.sleep(0.1)
        driver.find_element(By.XPATH,
                            '//*[@id="scrollTable"]/table/tbody/tr[last()]/td[last()]/div/i').click()

    def page_num(venue, start_time):
        start = str(start_time).split()[1]
        list_num = int(start[:2])
        if venue == "羽毛球场":
            lst = [0, 0, 0, 0, 0, 0, 0, 0, [0, 1], [0, 2], [0, 3], [0, 4], [0, 5], [1, 1], [1, 2], [1, 3], [1, 4], [1, 5], [2, 1], [2, 2], [2, 3], [2, 4], [2, 5]]
            return lst[list_num][0], lst[list_num][1]
        if venue == "羽毛球馆":
            lst = [0, 0, 0, 0, 0, 0, 0, [0, 1], [0, 2], [0, 3], [0, 4], [0, 5], [1, 1], [1, 2], [1, 3], [1, 4], [1, 5], [2, 1], [2, 2], [2, 3], [2, 4], [2, 5], [3, 1]]
            return lst[list_num][0], lst[list_num][1]
        return 0, 0

    def click_free(venue_num_click, time_num):
        WebDriverWait(driver, 5).until_not(
            EC.visibility_of_element_located((By.CLASS_NAME, "loading.ivu-spin.ivu-spin-large.ivu-spin-fix")))
        trs = driver.find_elements(By.TAG_NAME, 'tr')
        trs = (driver.find_elements(By.TAG_NAME, 'tbody'))
        trs = trs[1].find_elements(By.TAG_NAME, 'tr')
        trs_list = []
        for i in range(0, len(trs) - 1):
            trs_list.append(trs[i].find_elements(By.TAG_NAME, 'td'))
        # print(len(trs_list))
        if len(trs_list) == 0:
            return False, -1, 0
        # print(len(trs_list[0]))
        # print(len(trs_list[1]))
        # print(len(trs_list[2]))
        # print(venue_num_click, time_num)
        if venue_num_click != -1:
            class_name = trs_list[venue_num_click - 1][time_num].find_element(By.TAG_NAME,
                                                                              'div').get_attribute("class")
            print(class_name)
            if class_name.split()[2] == 'free':
                trs_list[venue_num_click - 1][time_num].find_element(By.TAG_NAME, 'div').click()
                return True, venue_num_click

        else:
            # 随机点一列free的，防止每次都点第一列
            for i in range(len(trs_list) - 1):
                class_name = trs_list[i][time_num].find_element(By.TAG_NAME,
                                                                'div').get_attribute("class")
                print(class_name)
                if class_name.split()[2] == 'free':
                    venue_num_click = i
                    trs_list[i][time_num].find_element(By.TAG_NAME, 'div').click()
                    return True, venue_num_click

        return False, venue_num_click

    driver.switch_to.window(driver.window_handles[-1])
    WebDriverWait(driver, 10).until_not(
        EC.visibility_of_element_located((By.CLASS_NAME, "loading.ivu-spin.ivu-spin-large.ivu-spin-fix")))
    # 若接近但是没到12点，停留在此页面
    flag = judge_close_to_time_12()
    if flag == 1:
        while True:
            flag = judge_close_to_time_12()
            if flag == 2:
                break
            else:
                time.sleep(0.5)
        driver.refresh()
        WebDriverWait(driver, 5).until_not(
            EC.visibility_of_element_located((By.CLASS_NAME, "loading.ivu-spin.ivu-spin-large.ivu-spin-fix")))
    status = False
    for k in range(len(start_time_list)):
        start_time = start_time_list[k]
        end_time = end_time_list[k]
        delta_day = delta_day_list[k]

        if k != 0:
            driver.refresh()
            time.sleep(0.5)

        move_to_date(delta_day)

        start_time = datetime.datetime.strptime(
            start_time.split('-')[1], "%H%M")
        end_time = datetime.datetime.strptime(end_time.split('-')[1], "%H%M")
        print("开始时间:%s" % str(start_time).split()[1])
        print("结束时间:%s" % str(end_time).split()[1])
        page, time_num = page_num(venue, start_time)
        print(page, time_num)
        for _ in range(page):
            next_page()
        status, venue_num = click_free(venue_num, time_num)

        if status:
            log_str += "找到空闲场地，场地编号为%d\n" % venue_num
            print("找到空闲场地，场地编号为%d\n" % venue_num)
            now = datetime.datetime.now()
            today = datetime.datetime.strptime(str(now)[:10], "%Y-%m-%d")
            date = today + datetime.timedelta(days=delta_day)
            return status, log_str, str(date)[:10] + str(start_time)[10:], str(date)[:10] + str(end_time)[
                                                                                            10:], venue_num
        else:
            log_str += "没有空余场地\n"
            print("没有空余场地\n")
    return status, log_str, None, None, None


def click_book(driver):
    print("确定预约")
    log_str = "确定预约\n"
    driver.switch_to.window(driver.window_handles[-1])
    WebDriverWait(driver, 10).until_not(
        EC.visibility_of_element_located((By.CLASS_NAME, "loading.ivu-spin.ivu-spin-large.ivu-spin-fix")))
    # WebDriverWait(driver, 10).until(
    #     EC.visibility_of_element_located(
    #         (By.XPATH, '/html/body/div[1]/div/div/div[3]/div[2]/div/div[2]/div[5]/div/div[2]')))
    driver.find_element(By.XPATH,
                        '/html/body/div[1]/div/div/div[3]/div[2]/div/div[1]/div[2]/div[5]/div[2]/div[1]').click()
    print("确定预约成功")
    log_str += "确定预约成功\n"
    return log_str


def click_submit_order(driver):
    print("提交订单")
    log_str = "提交订单\n"
    driver.switch_to.window(driver.window_handles[-1])
    WebDriverWait(driver, 10).until_not(
        EC.visibility_of_element_located((By.CLASS_NAME, "loading.ivu-spin.ivu-spin-large.ivu-spin-fix")))
    time.sleep(3)
    driver.find_element(By.XPATH,
                        '/html/body/div[1]/div/div/div[3]/div[2]/div/div[2]/div[2]/div[1]').click()
    # result = EC.alert_is_present()(driver)
    print("提交订单成功")
    log_str += "提交订单成功\n"
    return log_str


def get_ocr_engines():
    global _TEXT_DETECTOR, _TEXT_CLASSIFIER

    if DDDDOCR_IMPORT_ERROR is not None:
        raise RuntimeError(f"ddddocr 不可用: {DDDDOCR_IMPORT_ERROR}")

    if _TEXT_DETECTOR is None:
        _TEXT_DETECTOR = DdddOcr(det=True, ocr=False, show_ad=False)
    if _TEXT_CLASSIFIER is None:
        _TEXT_CLASSIFIER = DdddOcr(det=False, ocr=True, beta=True, show_ad=False)
    return _TEXT_DETECTOR, _TEXT_CLASSIFIER


def crop_box(image, box, padding=4):
    x_min, y_min, x_max, y_max = box
    left = max(0, x_min - padding)
    upper = max(0, y_min - padding)
    right = min(image.width, x_max + padding)
    lower = min(image.height, y_max + padding)
    return image.crop((left, upper, right, lower))


def parse_order_words(order_str):
    quoted_words = re.findall(r'[“"]([^”"]+)[”"]', order_str)
    if quoted_words:
        return [word.strip() for word in re.split(r'[,，\s]+', quoted_words[-1]) if word.strip()]

    colon_split = re.split(r'[:：]', order_str)
    if len(colon_split) > 1:
        return [word.strip() for word in re.split(r'[,，\s]+', colon_split[-1]) if word.strip()]

    return [word for word in re.findall(r'[\u4e00-\u9fffA-Za-z0-9]', order_str)[-3:]]


def recognize_click_targets(image_content):
    detector, classifier = get_ocr_engines()
    image = Image.open(io.BytesIO(image_content)).convert("RGB")
    boxes = detector.detection(image_content)
    candidates = []

    for box in boxes:
        char_image = crop_box(image, box)
        buffer = io.BytesIO()
        char_image.save(buffer, format='PNG')
        text = classifier.classification(buffer.getvalue(), png_fix=True).strip()
        if text:
            candidates.append({
                "text": text,
                "box": box,
                "center": ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2),
            })

    return candidates


def match_click_order(order_words, candidates):
    matched = []
    used_indexes = set()

    for order_word in order_words:
        candidate_index = None
        for index, candidate in enumerate(candidates):
            if index in used_indexes:
                continue
            candidate_text = candidate["text"]
            if candidate_text == order_word or order_word in candidate_text or candidate_text in order_word:
                candidate_index = index
                break

        if candidate_index is None:
            raise RuntimeError(f"未识别到目标文字: {order_word}")

        used_indexes.add(candidate_index)
        matched.append(candidates[candidate_index])

    return matched


def manual_verify(driver, message):
    driver.switch_to.window(driver.window_handles[-1])
    print(message)
    input("完成安全验证后按回车继续：")
    return "手动安全验证完成\n"


def verify(driver, captcha_auto_verify):
    print("进入安全验证")
    log_str = "进入安全验证\n"
    if not captcha_auto_verify:
        log_str += manual_verify(driver, "已关闭自动验证码识别。请在浏览器里完成安全验证，然后回到终端按回车继续。")
        return log_str

    # 创建ActionChains对象
    actions = ActionChains(driver)
    target_element = driver.find_element(By.XPATH,
                                         "/html/body/div[1]/div/div/div[3]/div[2]/div/div[1]/div[2]/div[4]/div[3]/div/div[2]/div/div[1]/div/img")
    order = driver.find_element(By.XPATH,
                                "/html/body/div[1]/div/div/div[3]/div[2]/div/div[1]/div[2]/div[4]/div[3]/div/div[2]/div/div[2]/span")
    image_uri = target_element.get_attribute("src")
    order_str = order.text
    order_words = parse_order_words(order_str)
    data_start = image_uri.find(",") + 1
    image_base64 = image_uri[data_start:]
    image_content = base64.b64decode(image_base64)

    try:
        candidates = recognize_click_targets(image_content)
        matched_targets = match_click_order(order_words, candidates)
    except Exception as exc:
        print(f"ddddocr 自动识别失败: {exc}")
        log_str += manual_verify(driver, "ddddocr 自动识别失败，请在浏览器里完成安全验证，然后回到终端按回车继续。")
        return log_str

    element_width = target_element.size["width"]
    element_height = target_element.size["height"]
    for target in matched_targets:
        click_x, click_y = target["center"]
        actions.move_to_element_with_offset(
            target_element,
            click_x - element_width / 2,
            click_y - element_height / 2,
        ).click().perform()
        time.sleep(0.2)
    print("安全验证成功")
    log_str += "安全验证成功\n"
    return log_str


def click_pay(driver):
    print("付款（校园卡）")
    log_str = "付款（校园卡）\n"
    time.sleep(30)
    print("需要用户自行付款")
    log_str += "需要用户自行付款\n"
    return log_str


if __name__ == '__main__':
    pass
