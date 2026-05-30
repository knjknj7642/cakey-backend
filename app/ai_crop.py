import json
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from PIL import Image


VISION_MODEL = "gemini-2.5-flash-lite"
VISION_MAX_RETRIES = 3
VISION_RETRY_DELAY_SECONDS = 20

CAKE_BOX_SCHEMA = {
    "type": "object",
    "properties": {
        "boxes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "box_2d": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 4,
                        "maxItems": 4,
                        "description": "[y_min, x_min, y_max, x_max] normalized to 0-1000",
                    },
                    "confidence": {"type": "number"},
                    "reason": {"type": "string"},
                },
                "required": ["box_2d", "confidence", "reason"],
            },
        }
    },
    "required": ["boxes"],
}


def call_vision_api_for_cake_boxes(image_path: str) -> str:
    load_dotenv()

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Warning: GEMINI_API_KEY is not set. Skipping Vision API crop detection.")
        return '{"boxes":[]}'

    from google import genai
    from google.genai import types

    prompt = (
        "이 이미지는 주문제작 케이크 사진이다. 이미지 안에서 실제 케이크 본체가 보이는 "
        "영역만 찾아라. 케이크 박스, 접시, 배경, 손, 테이블은 제외하고, 케이크 장식이 "
        "포함된 케이크 전체 영역만 반환하라. 케이크 외곽이 잘리지 않도록 장식과 외곽선이 "
        "모두 들어가는 약간 여유 있는 박스를 잡아라. 한 이미지에 케이크가 여러 개 있으면 "
        "보이는 모든 케이크를 각각 별도 박스로 반드시 반환하라. 같은 케이크를 중복 박스로 "
        "반환하지 말고, 케이크 일부만 잡은 박스도 반환하지 마라. 서로 다른 두 케이크를 "
        "하나의 큰 박스로 합치지 말고 물리적인 케이크 1개당 박스 1개만 반환하라. box_2d는 "
        "[y_min, x_min, y_max, x_max] 순서이며 0부터 1000 사이 "
        "정규화 좌표를 사용하라. 케이크가 명확하지 않으면 boxes를 빈 배열로 반환하라."
    )

    client = genai.Client(api_key=api_key)
    with Image.open(image_path) as image:
        response = client.models.generate_content(
            model=os.getenv("GEMINI_VISION_MODEL", VISION_MODEL),
            contents=[image, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=CAKE_BOX_SCHEMA,
            ),
        )
    return response.text or '{"boxes":[]}'


def parse_cake_boxes(raw_text: str, image_path: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        print("Warning: failed to parse Vision API crop detection JSON.")
        return []

    raw_boxes = parsed.get("boxes", []) if isinstance(parsed, dict) else []
    if not isinstance(raw_boxes, list):
        print("Warning: Vision API crop detection response did not contain a box list.")
        return []

    with Image.open(image_path) as image:
        width, height = image.size

    boxes = []
    for item in raw_boxes:
        if not isinstance(item, dict):
            continue
        try:
            y_min, x_min, y_max, x_max = [int(value) for value in item["box_2d"]]
            boxes.append(
                {
                    "x_min": int(x_min / 1000 * width),
                    "y_min": int(y_min / 1000 * height),
                    "x_max": int(x_max / 1000 * width),
                    "y_max": int(y_max / 1000 * height),
                    "confidence": float(item.get("confidence", 0.0)),
                    "reason": str(item.get("reason", "")),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return boxes


def detect_cake_boxes_with_vision_api(image_path: str) -> list[dict]:
    for attempt in range(1, VISION_MAX_RETRIES + 1):
        try:
            raw_text = call_vision_api_for_cake_boxes(image_path)
            return parse_cake_boxes(raw_text, image_path)
        except Exception as exc:
            message = str(exc)
            is_rate_limited = "429" in message or "RESOURCE_EXHAUSTED" in message
            if is_rate_limited and attempt < VISION_MAX_RETRIES:
                print(
                    f"Warning: Vision API rate limited for {image_path}. "
                    f"Retrying in {VISION_RETRY_DELAY_SECONDS}s."
                )
                time.sleep(VISION_RETRY_DELAY_SECONDS)
                continue
            print(f"Warning: Vision API crop detection failed for {image_path}: {exc}")
            return []
    return []


def auto_crop_cakes(original_image_path: str) -> list[dict]:
    return detect_cake_boxes_with_vision_api(original_image_path)
