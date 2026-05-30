import csv
import json
import mimetypes
import os
import urllib.parse
import urllib.request
from datetime import datetime
from html import escape
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


def _check_admin_token(token: str | None) -> None:
    admin_token = os.getenv("ADMIN_TOKEN")
    if admin_token and token != admin_token:
        raise HTTPException(status_code=401, detail="invalid admin token")


def _html(value: Any) -> str:
    return escape(str(value or ""), quote=True)


def _admin_url(path: str, token: str | None) -> str:
    if not token:
        return path
    return f"{path}?{urllib.parse.urlencode({'token': token})}"


def _image_url(value: str | None) -> str:
    value = value or ""
    if value.startswith("http://") or value.startswith("https://") or value.startswith("/"):
        return value
    return ""


def _admin_shell(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="ko">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>{_html(title)}</title>
          <style>
            body {{ margin: 0; background: #fff7fb; color: #382f35; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
            main {{ width: min(1100px, calc(100% - 32px)); margin: 0 auto; padding: 32px 0 80px; }}
            h1 {{ margin: 0 0 8px; color: #7f4e69; letter-spacing: 0; }}
            .meta {{ margin: 0 0 24px; color: #75676d; font-weight: 700; }}
            a {{ color: #7f4e69; font-weight: 900; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
            .topbar {{ display: flex; justify-content: space-between; gap: 12px; align-items: center; margin-bottom: 20px; }}
            .back {{ display: inline-flex; align-items: center; min-height: 42px; padding: 0 16px; border-radius: 999px; background: #f3e3ea; color: #7f4e69; font-weight: 900; }}
            .list {{ display: grid; gap: 12px; }}
            .order-row {{ display: grid; grid-template-columns: 1.2fr 1fr 1.8fr .7fr auto auto; gap: 14px; align-items: center; padding: 16px 18px; border-radius: 16px; background: white; box-shadow: 0 10px 26px rgba(127, 78, 105, .08); }}
            .order-row strong {{ display: block; color: #7f4e69; font-size: 17px; overflow-wrap: anywhere; }}
            .small {{ display: block; margin-top: 4px; color: #75676d; font-size: 13px; font-weight: 700; }}
            .status {{ display: inline-flex; align-items: center; justify-content: center; min-height: 32px; padding: 0 10px; border-radius: 999px; background: #fff1c6; color: #5e5359; font-weight: 900; white-space: nowrap; }}
            .status.ok {{ background: #e6f6ed; color: #24613f; }}
            .detail-link {{ display: inline-flex; align-items: center; justify-content: center; min-height: 38px; padding: 0 14px; border-radius: 999px; background: #7f4e69; color: white; white-space: nowrap; }}
            .empty {{ padding: 32px; border-radius: 20px; background: white; }}
            .detail-card {{ padding: 22px; border-radius: 22px; background: white; box-shadow: 0 18px 40px rgba(127, 78, 105, .1); }}
            .images {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin-bottom: 22px; }}
            figure {{ margin: 0; }}
            img {{ width: 100%; aspect-ratio: 1 / 1; object-fit: cover; border-radius: 18px; background: #f1e8ec; }}
            figcaption {{ margin-top: 8px; text-align: center; color: #75676d; font-weight: 900; }}
            dl {{ display: grid; grid-template-columns: 150px 1fr; gap: 11px 16px; margin: 0; }}
            dt {{ color: #7f4e69; font-weight: 900; }}
            dd {{ margin: 0; color: #5e5359; overflow-wrap: anywhere; font-weight: 700; }}
            .section-title {{ margin: 24px 0 12px; color: #7f4e69; font-size: 22px; }}
            @media (max-width: 860px) {{
              .order-row {{ grid-template-columns: 1fr; }}
              .topbar {{ display: block; }}
              .back {{ margin-top: 14px; }}
            }}
            @media (max-width: 720px) {{
              .images {{ grid-template-columns: 1fr; }}
              dl {{ grid-template-columns: 1fr; }}
            }}
          </style>
        </head>
        <body>
          <main>{body}</main>
        </body>
        </html>
        """
    )


def _order_archive_status(row: dict[str, str]) -> tuple[str, str]:
    if row.get("archive_recommended_view_url") or row.get("archive_generated_view_url"):
        return "ok", "보관 완료"
    if row.get("archive_error"):
        return "", "보관 오류"
    return "", "보관 없음"


@router.get("/admin", response_class=HTMLResponse)
def orders_admin(token: str | None = Query(default=None)) -> HTMLResponse:
    _check_admin_token(token)
    rows = list(reversed(_read_orders()))
    items = []
    for row in rows:
        status_class, status_label = _order_archive_status(row)
        option_summary = " · ".join(
            value
            for value in [
                row.get("size", ""),
                row.get("shape", ""),
                row.get("flavor", ""),
                row.get("style", ""),
                row.get("mood", ""),
            ]
            if value
        ) or "옵션 없음"
        detail_url = _admin_url(f"/orders/admin/{urllib.parse.quote(row.get('order_id', ''))}", token)
        items.append(
            f"""
            <article class="order-row">
              <div>
                <strong>{_html(row.get("order_id"))}</strong>
                <span class="small">{_html(row.get("saved_at"))}</span>
              </div>
              <div>
                {_html(row.get("recommended_shop_name") or "가게 미지정")}
                <span class="small">{_html(row.get("recommended_cake_crop_id") or "crop 없음")}</span>
              </div>
              <div>{_html(option_summary)}</div>
              <div>{_html(row.get("price") or "-")}</div>
              <div><span class="status {status_class}">{_html(status_label)}</span></div>
              <a class="detail-link" href="{_html(detail_url)}">자세히 보기</a>
            </article>
            """
        )

    body = "\n".join(items) if items else '<p class="empty">저장된 주문이 아직 없습니다.</p>'
    return _admin_shell(
        "CAKEY 주문 관리자",
        f"""
            <h1>CAKEY 주문 관리자</h1>
            <p class="meta">총 {_html(len(rows))}건의 주문이 저장되었습니다. 주문을 눌러 상세 내용을 확인하세요.</p>
            <section class="list">{body}</section>
        """
    )


@router.get("/admin/{order_id}", response_class=HTMLResponse)
def order_admin_detail(order_id: str, token: str | None = Query(default=None)) -> HTMLResponse:
    _check_admin_token(token)
    row = next((item for item in _read_orders() if item.get("order_id") == order_id), None)
    if not row:
        raise HTTPException(status_code=404, detail="order not found")

    list_url = _admin_url("/orders/admin", token)
    reference_url = _image_url(row.get("recommended_crop_image_url"))
    generated_url = _image_url(row.get("generated_customize_image_url"))
    reference_drive = row.get("archive_recommended_view_url") or row.get("drive_recommended_view_url") or ""
    generated_drive = row.get("archive_generated_view_url") or row.get("drive_generated_view_url") or ""

    def image_figure(src: str, label: str) -> str:
        if not src:
            return f'<figure><div class="empty">{_html(label)} 없음</div><figcaption>{_html(label)}</figcaption></figure>'
        return f"""
        <figure>
          <img src="{_html(src)}" alt="{_html(label)}">
          <figcaption>{_html(label)}</figcaption>
        </figure>
        """

    def link_or_empty(url: str) -> str:
        if not url:
            return "없음"
        return f'<a href="{_html(url)}" target="_blank" rel="noreferrer">{_html(url)}</a>'

    fields = [
        ("주문번호", row.get("order_id")),
        ("저장일시", row.get("saved_at")),
        ("가게", row.get("recommended_shop_name")),
        ("사이즈", row.get("size")),
        ("모양", row.get("shape")),
        ("맛", row.get("flavor")),
        ("스타일", row.get("style")),
        ("무드", row.get("mood")),
        ("테두리", row.get("border")),
        ("레터링 타입", row.get("lettering_type")),
        ("토핑", row.get("topping")),
        ("색상", row.get("color")),
        ("크림 데코", row.get("cream")),
        ("캐릭터", row.get("character")),
        ("판 레터링", row.get("plate")),
        ("가격", row.get("price")),
        ("문구", row.get("lettering_text")),
        ("추가 변경 요청", row.get("extra_request")),
        ("캐릭터 설명", row.get("character_description")),
        ("추천 crop ID", row.get("recommended_cake_crop_id")),
        ("캐릭터 참고 이미지", row.get("character_reference_image_url")),
        ("보관 오류", row.get("archive_error")),
        ("Drive 오류", row.get("drive_recommended_error") or row.get("drive_generated_error")),
    ]
    details = "\n".join(
        f"<dt>{_html(label)}</dt><dd>{_html(value) if value else '없음'}</dd>"
        for label, value in fields
    )

    return _admin_shell(
        "CAKEY 주문 상세",
        f"""
            <div class="topbar">
              <div>
                <h1>주문 상세</h1>
                <p class="meta">{_html(order_id)}</p>
              </div>
              <a class="back" href="{_html(list_url)}">← 목록으로 돌아가기</a>
            </div>
            <article class="detail-card">
              <div class="images">
                {image_figure(reference_url, "추천 이미지")}
                {image_figure(generated_url, "AI 생성 이미지")}
              </div>
              <h2 class="section-title">주문 내용</h2>
              <dl>{details}</dl>
              <h2 class="section-title">보관 링크</h2>
              <dl>
                <dt>추천 이미지 Drive</dt><dd>{link_or_empty(reference_drive)}</dd>
                <dt>AI 생성 이미지 Drive</dt><dd>{link_or_empty(generated_drive)}</dd>
                <dt>추천 원본 URL</dt><dd>{link_or_empty(row.get("recommended_crop_image_url") or "")}</dd>
                <dt>AI 생성 원본 URL</dt><dd>{link_or_empty(row.get("generated_customize_image_url") or "")}</dd>
              </dl>
            </article>
        """
    )
