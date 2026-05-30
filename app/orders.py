import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


router = APIRouter(prefix="/orders", tags=["orders"])

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ORDERS_CSV_PATH = PROJECT_ROOT / "data" / "metadata" / "orders.csv"
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]

ORDER_HEADERS = [
    "order_id",
    "saved_at",
    "page_url",
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
    "lettering_text",
    "extra_request",
    "character_description",
    "recommended_cake_crop_id",
    "recommended_shop_name",
    "recommended_crop_image_url",
    "recommended_original_image_url",
    "generated_customize_image_url",
    "drive_generated_file_id",
    "drive_generated_view_url",
    "character_reference_image_url",
    "user_agent",
]


class OrderPayload(BaseModel):
    pageUrl: str = ""
    userAgent: str = ""
    options: dict[str, Any] = Field(default_factory=dict)
    recommendation: dict[str, Any] = Field(default_factory=dict)
    customization: dict[str, Any] = Field(default_factory=dict)


def _credentials_file() -> Path | None:
    raw_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not raw_path:
        return None
    return Path(raw_path)


def _drive_folder_id() -> str | None:
    return os.getenv("GOOGLE_DRIVE_ORDER_FOLDER_ID")


def _load_credentials():
    from google.oauth2 import service_account

    credentials_path = _credentials_file()
    if credentials_path and credentials_path.exists():
        return service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=DRIVE_SCOPES,
        )

    raw_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if raw_json:
        return service_account.Credentials.from_service_account_info(
            json.loads(raw_json),
            scopes=DRIVE_SCOPES,
        )

    raise RuntimeError("Google service account credentials are not configured")


def _drive_service():
    from googleapiclient.discovery import build

    return build("drive", "v3", credentials=_load_credentials(), cache_discovery=False)


def _local_path_from_static_url(url: str | None) -> Path | None:
    if not url:
        return None
    prefixes = {
        "/static/generated/": PROJECT_ROOT / "data" / "generated",
        "/static/crops/": PROJECT_ROOT / "data" / "crops",
        "/static/reference/": PROJECT_ROOT / "data" / "reference",
    }
    for prefix, directory in prefixes.items():
        if url.startswith(prefix):
            candidate = directory / Path(url).name
            return candidate if candidate.exists() else None
    return None


def _upload_to_drive(file_path: Path, order_id: str) -> dict[str, str]:
    from googleapiclient.http import MediaFileUpload

    folder_id = _drive_folder_id()
    if not folder_id:
        raise RuntimeError("GOOGLE_DRIVE_ORDER_FOLDER_ID is not configured")

    service = _drive_service()
    metadata = {
        "name": f"{order_id}_{file_path.name}",
        "parents": [folder_id],
    }
    media = MediaFileUpload(str(file_path), mimetype="image/webp", resumable=False)
    uploaded = (
        service.files()
        .create(body=metadata, media_body=media, fields="id,webViewLink")
        .execute()
    )
    return {
        "file_id": uploaded["id"],
        "view_url": uploaded.get("webViewLink", f"https://drive.google.com/file/d/{uploaded['id']}/view"),
    }


def _write_order_row(
    order_id: str,
    payload: OrderPayload,
    drive_result: dict[str, str] | None,
) -> None:
    options = payload.options
    recommendation = payload.recommendation
    customization = payload.customization
    ORDERS_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    should_write_header = not ORDERS_CSV_PATH.exists() or ORDERS_CSV_PATH.stat().st_size == 0

    row = [
        order_id,
        datetime.utcnow().isoformat(timespec="seconds"),
        payload.pageUrl,
        options.get("size", ""),
        options.get("shape", ""),
        options.get("flavor", ""),
        options.get("style", ""),
        options.get("mood", ""),
        options.get("border", ""),
        options.get("letteringType", ""),
        options.get("topping", ""),
        options.get("color", ""),
        options.get("cream", ""),
        options.get("character", ""),
        options.get("plate", ""),
        options.get("price", ""),
        customization.get("letteringText", ""),
        customization.get("extraRequest", ""),
        customization.get("characterDescription", ""),
        recommendation.get("cakeCropId", ""),
        recommendation.get("shopName", ""),
        recommendation.get("cropImageUrl", ""),
        recommendation.get("originalImageUrl", ""),
        customization.get("generatedImageUrl", ""),
        drive_result.get("file_id", "") if drive_result else "",
        drive_result.get("view_url", "") if drive_result else "",
        customization.get("characterReferenceImageUrl", ""),
        payload.userAgent,
    ]

    with ORDERS_CSV_PATH.open("a", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        if should_write_header:
            writer.writerow(ORDER_HEADERS)
        writer.writerow(row)


@router.get("/drive/status")
def drive_status() -> dict[str, Any]:
    credentials_path = _credentials_file()
    return {
        "folder_id_configured": bool(_drive_folder_id()),
        "credentials_path_configured": bool(credentials_path),
        "credentials_file_exists": bool(credentials_path and credentials_path.exists()),
        "json_env_configured": bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")),
    }


@router.post("")
def create_order(payload: OrderPayload) -> dict[str, Any]:
    order_id = f"cakey_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    generated_url = payload.customization.get("generatedImageUrl")
    generated_path = _local_path_from_static_url(generated_url)

    drive_result = None
    if generated_path:
        try:
            drive_result = _upload_to_drive(generated_path, order_id)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Google Drive upload failed: {exc}") from exc

    _write_order_row(order_id, payload, drive_result)
    return {
        "status": "ok",
        "order_id": order_id,
        "drive_generated_file_id": drive_result["file_id"] if drive_result else None,
        "drive_generated_view_url": drive_result["view_url"] if drive_result else None,
    }
