import csv
import json
import mimetypes
import os
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
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
    "drive_recommended_file_id",
    "drive_recommended_view_url",
    "drive_recommended_error",
    "generated_customize_image_url",
    "drive_generated_file_id",
    "drive_generated_view_url",
    "drive_generated_error",
    "archive_recommended_view_url",
    "archive_generated_view_url",
    "archive_error",
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


def _upload_to_drive(file_path: Path, order_id: str, label: str) -> dict[str, str]:
    from googleapiclient.http import MediaFileUpload

    folder_id = _drive_folder_id()
    if not folder_id:
        raise RuntimeError("GOOGLE_DRIVE_ORDER_FOLDER_ID is not configured")

    service = _drive_service()
    metadata = {
        "name": f"{order_id}_{label}_{file_path.name}",
        "parents": [folder_id],
    }
    media_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    media = MediaFileUpload(str(file_path), mimetype=media_type, resumable=False)
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
    drive_generated_result: dict[str, str] | None,
    drive_recommended_result: dict[str, str] | None,
    archive_result: dict[str, Any] | None,
    drive_generated_error: str = "",
    drive_recommended_error: str = "",
    archive_error: str = "",
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
        drive_recommended_result.get("file_id", "") if drive_recommended_result else "",
        drive_recommended_result.get("view_url", "") if drive_recommended_result else "",
        drive_recommended_error,
        customization.get("generatedImageUrl", ""),
        drive_generated_result.get("file_id", "") if drive_generated_result else "",
        drive_generated_result.get("view_url", "") if drive_generated_result else "",
        drive_generated_error,
        archive_result.get("recommendedDriveUrl", "") if archive_result else "",
        archive_result.get("generatedDriveUrl", "") if archive_result else "",
        archive_error,
        customization.get("characterReferenceImageUrl", ""),
        payload.userAgent,
    ]

    with ORDERS_CSV_PATH.open("a", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        if should_write_header:
            writer.writerow(ORDER_HEADERS)
        writer.writerow(row)


def _absolute_url(url: str | None) -> str:
    if not url:
        return ""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/"):
        return f"https://cakey-backend.onrender.com{url}"
    return url


def _archive_with_apps_script(order_id: str, payload: OrderPayload) -> dict[str, Any] | None:
    endpoint = os.getenv("ORDER_ARCHIVE_WEB_APP_URL")
    if not endpoint:
        return None

    options = payload.options
    recommendation = payload.recommendation
    customization = payload.customization
    archive_payload = {
        "mode": "order_archive",
        "orderId": order_id,
        "pageUrl": payload.pageUrl,
        "userAgent": payload.userAgent,
        "order": {
            **options,
            "letteringText": customization.get("letteringText", ""),
            "extraRequest": customization.get("extraRequest", ""),
            "characterDescription": customization.get("characterDescription", ""),
            "recommendedCakeCropId": recommendation.get("cakeCropId", ""),
            "recommendedShopName": recommendation.get("shopName", ""),
            "recommendedCropImageUrl": _absolute_url(recommendation.get("cropImageUrl")),
            "generatedCustomizeImageUrl": _absolute_url(customization.get("generatedImageUrl")),
        },
    }
    query = urllib.parse.urlencode(
        {"payload": json.dumps(archive_payload, ensure_ascii=False)}
    )
    separator = "&" if "?" in endpoint else "?"
    request_url = f"{endpoint}{separator}{query}"
    with urllib.request.urlopen(request_url, timeout=45) as response:
        response_body = response.read().decode("utf-8")
    result = json.loads(response_body)
    if not result.get("ok"):
        raise RuntimeError(result.get("message") or "Apps Script archive failed")
    return result


@router.get("/drive/status")
def drive_status() -> dict[str, Any]:
    credentials_path = _credentials_file()
    return {
        "folder_id_configured": bool(_drive_folder_id()),
        "credentials_path_configured": bool(credentials_path),
        "credentials_file_exists": bool(credentials_path and credentials_path.exists()),
        "json_env_configured": bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")),
        "archive_web_app_url_configured": bool(os.getenv("ORDER_ARCHIVE_WEB_APP_URL")),
    }


@router.post("")
def create_order(payload: OrderPayload) -> dict[str, Any]:
    order_id = f"cakey_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    recommended_url = payload.recommendation.get("cropImageUrl")
    generated_url = payload.customization.get("generatedImageUrl")
    recommended_path = _local_path_from_static_url(recommended_url)
    generated_path = _local_path_from_static_url(generated_url)

    drive_recommended_result = None
    drive_generated_result = None
    archive_result = None
    drive_recommended_error = ""
    drive_generated_error = ""
    archive_error = ""

    try:
        archive_result = _archive_with_apps_script(order_id, payload)
    except Exception as exc:
        archive_error = str(exc)

    if recommended_path:
        try:
            drive_recommended_result = _upload_to_drive(recommended_path, order_id, "recommended")
        except Exception as exc:
            drive_recommended_error = str(exc)

    if generated_path:
        try:
            drive_generated_result = _upload_to_drive(generated_path, order_id, "generated")
        except Exception as exc:
            drive_generated_error = str(exc)

    _write_order_row(
        order_id,
        payload,
        drive_generated_result,
        drive_recommended_result,
        archive_result,
        drive_generated_error,
        drive_recommended_error,
        archive_error,
    )
    return {
        "status": "ok",
        "order_id": order_id,
        "drive_recommended_file_id": drive_recommended_result["file_id"] if drive_recommended_result else None,
        "drive_recommended_view_url": drive_recommended_result["view_url"] if drive_recommended_result else None,
        "drive_recommended_error": drive_recommended_error or None,
        "drive_generated_file_id": drive_generated_result["file_id"] if drive_generated_result else None,
        "drive_generated_view_url": drive_generated_result["view_url"] if drive_generated_result else None,
        "drive_generated_error": drive_generated_error or None,
        "archive_recommended_view_url": archive_result.get("recommendedDriveUrl") if archive_result else None,
        "archive_generated_view_url": archive_result.get("generatedDriveUrl") if archive_result else None,
        "archive_error": archive_error or None,
    }


def _read_orders() -> list[dict[str, str]]:
    if not ORDERS_CSV_PATH.exists():
        return []
    with ORDERS_CSV_PATH.open("r", newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


@router.get("")
def list_orders() -> dict[str, Any]:
    orders = _read_orders()
    return {
        "count": len(orders),
        "results": list(reversed(orders)),
    }


@router.get("/admin", response_class=HTMLResponse)
def orders_admin(token: str | None = Query(default=None)) -> HTMLResponse:
    admin_token = os.getenv("ADMIN_TOKEN")
    if admin_token and token != admin_token:
        raise HTTPException(status_code=401, detail="invalid admin token")

    rows = list(reversed(_read_orders()))
    cards = []
    for row in rows:
        reference_url = row.get("recommended_crop_image_url") or ""
        generated_url = row.get("generated_customize_image_url") or ""
        if reference_url.startswith("/"):
            reference_url = reference_url
        if generated_url.startswith("/"):
            generated_url = generated_url
        cards.append(
            f"""
            <article class="order-card">
              <header>
                <div>
                  <strong>{row.get("order_id", "")}</strong>
                  <span>{row.get("saved_at", "")}</span>
                </div>
                <a href="{row.get("drive_generated_view_url", "#")}" target="_blank" rel="noreferrer">Drive 생성 이미지</a>
              </header>
              <div class="images">
                <figure>
                  <img src="{reference_url}" alt="추천 이미지">
                  <figcaption>추천 이미지</figcaption>
                </figure>
                <figure>
                  <img src="{generated_url}" alt="AI 생성 이미지">
                  <figcaption>AI 생성 이미지</figcaption>
                </figure>
              </div>
              <dl>
                <dt>가게</dt><dd>{row.get("recommended_shop_name", "")}</dd>
                <dt>옵션</dt><dd>{row.get("size", "")} · {row.get("shape", "")} · {row.get("flavor", "")} · {row.get("style", "")} · {row.get("mood", "")}</dd>
                <dt>장식</dt><dd>{row.get("border", "")} · {row.get("lettering_type", "")} · {row.get("topping", "")} · {row.get("cream", "")}</dd>
                <dt>요청</dt><dd>{row.get("extra_request", "") or "없음"}</dd>
                <dt>Drive 추천</dt><dd><a href="{row.get("drive_recommended_view_url", "#")}" target="_blank" rel="noreferrer">{row.get("drive_recommended_file_id", "") or "없음"}</a></dd>
                <dt>Drive 생성</dt><dd><a href="{row.get("drive_generated_view_url", "#")}" target="_blank" rel="noreferrer">{row.get("drive_generated_file_id", "") or "없음"}</a></dd>
                <dt>보관 추천</dt><dd><a href="{row.get("archive_recommended_view_url", "#")}" target="_blank" rel="noreferrer">{row.get("archive_recommended_view_url", "") or "없음"}</a></dd>
                <dt>보관 생성</dt><dd><a href="{row.get("archive_generated_view_url", "#")}" target="_blank" rel="noreferrer">{row.get("archive_generated_view_url", "") or "없음"}</a></dd>
                <dt>Drive 오류</dt><dd>{row.get("drive_recommended_error", "") or row.get("drive_generated_error", "") or "없음"}</dd>
                <dt>보관 오류</dt><dd>{row.get("archive_error", "") or "없음"}</dd>
              </dl>
            </article>
            """
        )

    body = "\n".join(cards) if cards else '<p class="empty">저장된 주문이 아직 없습니다.</p>'
    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="ko">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>CAKEY 주문 관리자</title>
          <style>
            body {{ margin: 0; background: #fff7fb; color: #382f35; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
            main {{ width: min(1100px, calc(100% - 32px)); margin: 0 auto; padding: 36px 0 80px; }}
            h1 {{ margin: 0 0 8px; color: #7f4e69; }}
            .meta {{ margin: 0 0 28px; color: #75676d; }}
            .order-card {{ margin: 0 0 24px; padding: 22px; border-radius: 22px; background: white; box-shadow: 0 18px 40px rgba(127, 78, 105, .1); }}
            .order-card header {{ display: flex; justify-content: space-between; gap: 16px; align-items: center; margin-bottom: 18px; }}
            .order-card header strong {{ display: block; color: #7f4e69; font-size: 20px; }}
            .order-card header span {{ color: #75676d; font-size: 13px; }}
            a {{ color: #7f4e69; font-weight: 800; }}
            .images {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }}
            figure {{ margin: 0; }}
            img {{ width: 100%; aspect-ratio: 1 / 1; object-fit: cover; border-radius: 18px; background: #f1e8ec; }}
            figcaption {{ margin-top: 8px; text-align: center; color: #75676d; font-weight: 800; }}
            dl {{ display: grid; grid-template-columns: 100px 1fr; gap: 10px 16px; margin: 18px 0 0; }}
            dt {{ color: #7f4e69; font-weight: 900; }}
            dd {{ margin: 0; color: #5e5359; overflow-wrap: anywhere; }}
            .empty {{ padding: 32px; border-radius: 20px; background: white; }}
            @media (max-width: 720px) {{ .images {{ grid-template-columns: 1fr; }} .order-card header {{ display: block; }} dl {{ grid-template-columns: 1fr; }} }}
          </style>
        </head>
        <body>
          <main>
            <h1>CAKEY 주문 관리자</h1>
            <p class="meta">총 {len(rows)}건의 주문이 저장되었습니다.</p>
            {body}
          </main>
        </body>
        </html>
        """
    )
