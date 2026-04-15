from pathlib import Path
from PIL import Image, ImageDraw

from captcha_solver import match_click_order, parse_order_words, recognize_click_targets


def save_debug_image(image_path: Path, matched, output_path: Path):
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)

    for index, candidate in enumerate(matched, start=1):
        x_min, y_min, x_max, y_max = candidate["box"]
        center_x, center_y = candidate["center"]
        draw.rectangle((x_min, y_min, x_max, y_max), outline="red", width=2)
        draw.ellipse((center_x - 4, center_y - 4, center_x + 4, center_y + 4), fill="blue")
        draw.text((x_min, max(0, y_min - 16)), f"{index}:{candidate['text']}", fill="red")

    image.save(output_path)


def evaluate_case(image_path: Path, text_path: Path):
    prompt = text_path.read_text(encoding="utf-8").strip()
    order_words = parse_order_words(prompt)
    image_bytes = image_path.read_bytes()
    candidates = recognize_click_targets(image_bytes)
    matched = match_click_order(order_words, candidates)
    debug_image_path = image_path.with_name(f"{image_path.stem}_debug.png")
    save_debug_image(image_path, matched, debug_image_path)

    return {
        "image": image_path.name,
        "prompt": prompt,
        "order_words": order_words,
        "candidates": candidates,
        "matched": matched,
        "success": [candidate["text"] for candidate in matched] == order_words,
        "debug_image": debug_image_path.name,
    }


def main():
    test_dir = Path("testpic")
    image_paths = sorted(test_dir.glob("*.png"))
    results = []

    for image_path in image_paths:
        text_path = image_path.with_suffix(".txt")
        if not text_path.exists():
            print(f"SKIP {image_path.name}: 缺少 {text_path.name}")
            continue

        try:
            result = evaluate_case(image_path, text_path)
            results.append(result)
            print(f"[{'OK' if result['success'] else 'FAIL'}] {result['image']}")
            print(f"  prompt: {result['prompt']}")
            print(f"  target: {result['order_words']}")
            print(f"  detected: {[candidate['text'] for candidate in result['candidates']]}")
            print(f"  matched: {[candidate['text'] for candidate in result['matched']]}")
            print(f"  boxes: {[candidate['box'] for candidate in result['matched']]}")
            print(f"  centers: {[candidate['center'] for candidate in result['matched']]}")
            print(f"  debug_image: {result['debug_image']}")
        except Exception as exc:
            print(f"[ERROR] {image_path.name}: {type(exc).__name__}: {exc}")

    if results:
        success_count = sum(result["success"] for result in results)
        print(f"\nSummary: {success_count}/{len(results)} success")


if __name__ == "__main__":
    main()
