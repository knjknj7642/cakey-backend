import json
import os
import base64
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


VISION_MODEL = "gpt-4.1-mini"

TAG_CHOICES = {
    "shape": ["원형", "하트", "사각", "판단불가"],
    "dominant_color": ["화이트", "핑크", "블루", "옐로우", "블랙", "퍼플", "브라운", "그린", "믹스", "판단불가"],
    "visual_style": ["심플", "러블리", "캐릭터", "레터링중심", "화려함", "판단불가"],
    "lettering_type": ["없음", "중앙레터링", "꽉찬레터링", "2겹레터링", "무지개레터링", "판단불가"],
    "board_lettering": ["없음", "있음", "판단불가"],
    "border_type": ["없음", "크림테두리", "점선테두리", "꽃테두리", "판단불가"],
    "cream_decoration": ["없음", "하트", "꽃", "리본", "레이스", "판단불가"],
    "topping_decoration": ["없음", "진주", "스프링클", "과일", "반짝이", "판단불가"],
    "character_type": ["없음", "이모티콘", "사람", "개", "고양이", "토끼", "곰", "기타동물", "기타캐릭터", "판단불가"],
    "text_presence": ["있음", "없음", "판단불가"],
}

TAG_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        **{
            key: {
                "type": "array",
                "items": {"type": "string", "enum": choices},
            }
            for key, choices in TAG_CHOICES.items()
        },
        "memo": {"type": "string"},
    },
    "required": [*TAG_CHOICES.keys(), "memo"],
}


def unknown_tag_result(memo: str = "자동 태깅 실패") -> dict[str, Any]:
    result: dict[str, Any] = {key: ["판단불가"] for key in TAG_CHOICES}
    result["memo"] = memo
    return result


def call_vision_api_for_tags(crop_image_path: str) -> str:
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Warning: OPENAI_API_KEY is not set. Returning 판단불가 tags.")
        return "{}"

    from openai import OpenAI

    prompt = (
        "이 crop 이미지는 주문제작 케이크 본체 이미지다. 이미지에서 확인 가능한 요소만 보고 "
        "서비스 태그를 추정하라. 맛, 가격, 픽업 정보처럼 사진에서 알 수 없는 정보는 제외하라. "
        "각 태그는 제공된 선택지 안에서만 고르고, 여러 값이 가능하면 배열로 반환하라. "
        "판단이 어려우면 판단불가를 사용하라.\n\n"
        f"선택지: {json.dumps(TAG_CHOICES, ensure_ascii=False)}"
    )

    image_bytes = Path(crop_image_path).read_bytes()
    image_base64 = base64.b64encode(image_bytes).decode("ascii")
    client = OpenAI(api_key=api_key, timeout=60.0)
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_TAGGING_MODEL", VISION_MODEL),
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}",
                            "detail": "low",
                        },
                    },
                ],
            }
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "cake_tags",
                "schema": TAG_RESPONSE_SCHEMA,
                "strict": True,
            },
        },
    )
    return response.choices[0].message.content or "{}"


def parse_tag_response(raw_text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        print("Warning: failed to parse Vision API tagging JSON.")
        return unknown_tag_result()

    if not isinstance(parsed, dict):
        print("Warning: Vision API tagging response was not a JSON object.")
        return unknown_tag_result()

    result: dict[str, Any] = {}
    for tag_key, choices in TAG_CHOICES.items():
        raw_values = parsed.get(tag_key, ["판단불가"])
        if isinstance(raw_values, str):
            raw_values = [raw_values]
        if not isinstance(raw_values, list):
            raw_values = ["판단불가"]

        valid_values = [value for value in raw_values if value in choices]
        result[tag_key] = valid_values or ["판단불가"]

    result["memo"] = str(parsed.get("memo") or "")
    return result


def auto_tag_crop(crop_image_path: str) -> dict:
    try:
        raw_text = call_vision_api_for_tags(crop_image_path)
    except Exception as exc:
        print(f"Warning: Vision API tagging failed for {crop_image_path}: {exc}")
        return unknown_tag_result()

    if raw_text == "{}":
        return unknown_tag_result("OPENAI_API_KEY 미설정")
    return parse_tag_response(raw_text)
