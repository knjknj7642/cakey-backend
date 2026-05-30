import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field


router = APIRouter(prefix="/survey", tags=["survey"])

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SURVEY_CSV_PATH = PROJECT_ROOT / "data" / "metadata" / "survey_responses.csv"

HEADERS = [
    "saved_at",
    "submitted_at",
    "submitted_at_local",
    "page_url",
    "q1",
    "q2",
    "q3",
    "q4",
    "q5",
    "q6",
    "comment",
    "size",
    "shape",
    "flavor",
    "style",
    "mood",
    "border",
    "lettering_type",
    "topping",
    "color",
    "cream",
    "character",
    "plate",
    "price",
    "recommended_cake_crop_id",
    "recommended_shop_name",
    "generated_customize_image_url",
    "character_reference_image_url",
    "user_agent",
]


class SurveyScore(BaseModel):
    question: str = ""
    score: int | str | None = ""


class SurveyPayload(BaseModel):
    submittedAt: str = ""
    submittedAtLocal: str = ""
    pageUrl: str = ""
    userAgent: str = ""
    scores: list[SurveyScore] = Field(default_factory=list)
    comment: str = ""
    order: dict[str, Any] = Field(default_factory=dict)


def _score(scores: list[SurveyScore], index: int) -> int | str:
    if index >= len(scores):
        return ""
    return scores[index].score if scores[index].score is not None else ""


def _row(payload: SurveyPayload) -> list[Any]:
    order = payload.order
    return [
        datetime.utcnow().isoformat(timespec="seconds"),
        payload.submittedAt,
        payload.submittedAtLocal,
        payload.pageUrl,
        _score(payload.scores, 0),
        _score(payload.scores, 1),
        _score(payload.scores, 2),
        _score(payload.scores, 3),
        _score(payload.scores, 4),
        _score(payload.scores, 5),
        payload.comment,
        order.get("size", ""),
        order.get("shape", ""),
        order.get("flavor", ""),
        order.get("style", ""),
        order.get("mood", ""),
        order.get("border", ""),
        order.get("letteringType", ""),
        order.get("topping", ""),
        order.get("color", ""),
        order.get("cream", ""),
        order.get("character", ""),
        order.get("plate", ""),
        order.get("price", ""),
        order.get("recommendedCakeCropId", ""),
        order.get("recommendedShopName", ""),
        order.get("generatedCustomizeImageUrl", ""),
        order.get("characterReferenceImageUrl", ""),
        payload.userAgent,
    ]


@router.post("/responses")
def save_survey_response(payload: SurveyPayload) -> dict[str, Any]:
    SURVEY_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    should_write_header = not SURVEY_CSV_PATH.exists() or SURVEY_CSV_PATH.stat().st_size == 0

    with SURVEY_CSV_PATH.open("a", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        if should_write_header:
            writer.writerow(HEADERS)
        writer.writerow(_row(payload))

    return {
        "status": "ok",
        "saved_to": str(SURVEY_CSV_PATH.relative_to(PROJECT_ROOT)),
    }
