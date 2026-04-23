import io
import re
import time
import datetime
from pathlib import Path

from PIL import Image

try:
    from ddddocr.ddddocr import DdddOcr
    DDDDOCR_IMPORT_ERROR = None
except Exception as exc:
    DdddOcr = None
    DDDDOCR_IMPORT_ERROR = exc


_TEXT_DETECTOR = None
_TEXT_CLASSIFIER = None
CAPTCHA_IMAGE_XPATH = "/html/body/div[1]/div/div/div[3]/div[2]/div/div[1]/div[2]/div[4]/div[3]/div/div[2]/div/div[1]/div/img"
CAPTCHA_ORDER_XPATH = "/html/body/div[1]/div/div/div[3]/div[2]/div/div[1]/div[2]/div[4]/div[3]/div/div[2]/div/div[2]/span"


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


def recognize_click_targets(image_bytes):
    detector, classifier = get_ocr_engines()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    boxes = detector.detection(image_bytes)
    candidates = []

    for box in boxes:
        char_image = crop_box(image, box)
        buffer = io.BytesIO()
        char_image.save(buffer, format="PNG")
        text = classifier.classification(buffer.getvalue(), png_fix=True).strip()
        if text:
            candidates.append({
                "text": text,
                "box": box,
                "center": ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2),
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


def solve_click_captcha(
    page,
    before_click_delay: float = 1.0,
    click_interval: float = 0.8,
    after_click_delay: float = 1.0,
) -> None:
    print("开始处理验证码")
    captcha_image = page.locator(f"xpath={CAPTCHA_IMAGE_XPATH}")
    order_text = page.locator(f"xpath={CAPTCHA_ORDER_XPATH}")

    captcha_image.wait_for(state="visible", timeout=10000)
    order_text.wait_for(state="visible", timeout=10000)
    page.wait_for_timeout(int(before_click_delay * 1000))

    order_words = parse_order_words(order_text.inner_text())
    image_bytes = captcha_image.screenshot()

    try:
        candidates = recognize_click_targets(image_bytes)
        matched_targets = match_click_order(order_words, candidates)
    except Exception as exc:
        _save_captcha_for_debug(image_bytes, order_text.inner_text())
        raise

    box = captcha_image.bounding_box()
    if box is None:
        raise RuntimeError("无法获取验证码图片坐标")

    for target in matched_targets:
        click_x = box["x"] + target["center"][0]
        click_y = box["y"] + target["center"][1]
        print(f"点击验证码文字: {target['text']} @ ({click_x:.1f}, {click_y:.1f})")
        page.mouse.click(click_x, click_y)
        time.sleep(click_interval)

    page.wait_for_timeout(int(after_click_delay * 1000))
    print("验证码点击完成")


def _save_captcha_for_debug(image_bytes: bytes, order_text: str) -> None:
    """验证码识别失败时，将图片和文字保存到 testpic/ 目录，方便后续调试。"""
    debug_dir = Path("testpic")
    debug_dir.mkdir(exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    image_path = debug_dir / f"{timestamp}.png"
    text_path = debug_dir / f"{timestamp}.txt"
    image_path.write_bytes(image_bytes)
    text_path.write_text(order_text, encoding="utf-8")
    print(f"验证码识别失败，已保存调试文件: {image_path}, {text_path}")
