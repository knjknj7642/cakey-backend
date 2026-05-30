import base64
import os
import urllib.request
import uuid
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from openai import OpenAI
from PIL import Image
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import CakeCrop
from app.recommender import build_static_url, group_tags
from app.schemas import (
    CustomizeGenerateRequest,
    CustomizeGenerateResponse,
    CustomizePreviewRequest,
    CustomizePreviewResponse,
)


router = APIRouter(prefix="/customize", tags=["customize"])

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = PROJECT_ROOT / "data" / "generated"
REFERENCE_DIR = PROJECT_ROOT / "data" / "reference"
DEMO_BASE_CROP = "/static/crops/_onyourday_1667207242_2961071421200629117_12861674625_cake_1.jpg"
DEMO_GENERATED = (
    "/static/generated/"
    "_onyourday_1667207242_2961071421200629117_12861674625_cake_1_custom_20260524_044951.webp"
)

TAG_LABELS = {
    "shape": "케이크 모양",
    "dominant_color": "대표 색상",
    "visual_style": "전체 스타일",
    "lettering_type": "레터링 위치/형태",
    "board_lettering": "케이크판 레터링",
    "border_type": "테두리",
    "cream_decoration": "크림 장식",
    "topping_decoration": "토핑",
    "character_type": "캐릭터",
    "text_presence": "문구 존재",
}


def _get_crop(db: Session, cake_crop_id: int) -> CakeCrop:
    crop = (
        db.query(CakeCrop)
        .options(joinedload(CakeCrop.original_image), joinedload(CakeCrop.tags))
        .filter(CakeCrop.cake_crop_id == cake_crop_id)
        .first()
    )
    if crop is None:
        raise HTTPException(status_code=404, detail="cake crop not found")
    return crop


def _actual_crop_path(crop: CakeCrop) -> Path:
    return PROJECT_ROOT / "data" / "crops" / crop.crop_file_name


def _reference_path_from_url(url: str | None) -> Path | None:
    if not url or not url.startswith("/static/reference/"):
        return None
    file_name = Path(url).name
    if not file_name:
        return None
    path = REFERENCE_DIR / file_name
    return path if path.exists() else None


def _normalize_tags(tags: dict[str, list[str]]) -> dict[str, list[str]]:
    normalized = {}
    for key, values in tags.items():
        clean_values = [value for value in values if value and value != "판단불가"]
        if clean_values:
            normalized[key] = sorted(set(clean_values))
    return normalized


def _build_diff_tags(
    current_tags: dict[str, list[str]],
    target_tags: dict[str, list[str]],
) -> dict[str, dict[str, list[str]]]:
    diff = {}
    for key, target_values in _normalize_tags(target_tags).items():
        current_values = sorted(set(current_tags.get(key, [])))
        wanted_values = sorted(set(target_values))
        if set(current_values) != set(wanted_values):
            diff[key] = {
                "from": current_values,
                "to": wanted_values,
            }
    return diff


def _build_edit_prompt(
    diff_tags: dict[str, dict[str, list[str]]],
    lettering_text: str | None,
    extra_request: str | None,
    character_description: str | None,
    character_reference_image_url: str | None,
) -> str:
    clean_extra_request = extra_request.strip() if extra_request else None
    clean_character_description = character_description.strip() if character_description else None
    has_reference_image = bool(character_reference_image_url)
    if (
        not diff_tags
        and not lettering_text
        and not clean_extra_request
        and not clean_character_description
        and not has_reference_image
    ):
        return (
            "원본 케이크 사진의 구도, 색감, 장식, 배경을 유지한다. "
            "불필요한 변형 없이 실제 주문제작 케이크 사진처럼 자연스럽게 보정한다."
        )

    changes = []
    for key, diff in diff_tags.items():
        label = TAG_LABELS.get(key, key)
        before = ", ".join(diff["from"]) if diff["from"] else "없음"
        after = ", ".join(diff["to"]) if diff["to"] else "없음"
        changes.append(f"- {label}: 현재 {before}에서 {after}로 변경")

    if lettering_text:
        changes.append(f'- 케이크 위 레터링 문구를 "{lettering_text}"로 자연스럽게 반영')

    if clean_character_description:
        changes.append(f"- 캐릭터 상세 요청: {clean_character_description}")

    if has_reference_image:
        changes.append(
            "- 첨부된 캐릭터 참고 이미지의 형태, 색감, 인상을 그대로 복사하지 말고 "
            "케이크 크림, 아이싱, 초코펜, 토핑 질감으로 자연스럽게 재해석"
        )

    if clean_extra_request:
        changes.append(f"- 추가 사용자 요청: {clean_extra_request}")

    joined_changes = "\n".join(changes)
    return (
        "이 이미지는 주문제작 케이크 crop 사진이다. "
        "케이크 본체의 촬영 구도, 질감, 조명, 배경은 최대한 유지하고, "
        "아래 변경사항만 반영해서 실제 케이크 사진처럼 자연스럽게 편집한다. "
        "상표권/저작권 캐릭터를 직접 복제하지 말고 주문제작 케이크용 오리지널 장식처럼 변환한다. "
        "케이크 박스, 손, 테이블, 배경은 새로 만들거나 과하게 바꾸지 않는다.\n"
        f"{joined_changes}"
    )


def _preview_from_crop(
    crop: CakeCrop,
    request: CustomizePreviewRequest,
) -> CustomizePreviewResponse:
    current_tags = group_tags(crop.tags)
    diff_tags = _build_diff_tags(current_tags, request.target_tags)
    prompt = _build_edit_prompt(
        diff_tags,
        request.lettering_text,
        request.extra_request,
        request.character_description,
        request.character_reference_image_url,
    )
    return CustomizePreviewResponse(
        cake_crop_id=crop.cake_crop_id,
        base_crop_image_url=build_static_url(crop.crop_file_path, "crops"),
        original_image_url=build_static_url(crop.original_image.file_path, "originals"),
        diff_tags=diff_tags,
        prompt=prompt,
    )


def _edit_image_with_openai(
    image_path: Path,
    prompt: str,
    output_path: Path,
    model: str,
    reference_image_path: Path | None = None,
) -> None:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not configured")

    client = OpenAI()
    with ExitStack() as stack:
        image_file = stack.enter_context(image_path.open("rb"))
        image_input = image_file
        if reference_image_path:
            reference_file = stack.enter_context(reference_image_path.open("rb"))
            image_input = [image_file, reference_file]
        result = client.images.edit(
            model=model,
            image=image_input,
            prompt=prompt,
            n=1,
            size="1024x1024",
        )

    if not result.data:
        raise RuntimeError("OpenAI image edit response did not include image data")

    item = result.data[0]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(".tmp")
    if item.b64_json:
        temp_path.write_bytes(base64.b64decode(item.b64_json))
    elif item.url:
        urllib.request.urlretrieve(item.url, temp_path)
    else:
        raise RuntimeError("OpenAI image edit response did not include image data")

    with Image.open(temp_path) as image:
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")
        image.save(output_path, "WEBP", quality=72, method=6)
    temp_path.unlink(missing_ok=True)


@router.post("/reference-image")
async def upload_reference_image(file: UploadFile = File(...)) -> dict[str, str]:
    suffix = Path(file.filename or "").suffix.lower()
    allowed_suffixes = {".jpg", ".jpeg", ".png", ".webp"}
    if suffix not in allowed_suffixes:
        raise HTTPException(status_code=400, detail="jpg, jpeg, png, webp 파일만 업로드할 수 있습니다")

    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    output_name = f"character_ref_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.webp"
    output_path = REFERENCE_DIR / output_name
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty file")

    temp_path = output_path.with_suffix(suffix)
    try:
        temp_path.write_bytes(raw)
        with Image.open(temp_path) as image:
            image.thumbnail((1024, 1024))
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGB")
            image.save(output_path, "WEBP", quality=82, method=6)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"이미지 파일을 처리할 수 없습니다: {exc}") from exc
    finally:
        temp_path.unlink(missing_ok=True)

    return {"image_url": f"/static/reference/{output_name}"}


@router.post("/preview", response_model=CustomizePreviewResponse)
def customize_preview(
    request: CustomizePreviewRequest,
    db: Session = Depends(get_db),
) -> CustomizePreviewResponse:
    crop = _get_crop(db, request.cake_crop_id)
    return _preview_from_crop(crop, request)


@router.post("/generate", response_model=CustomizeGenerateResponse)
def customize_generate(
    request: CustomizeGenerateRequest,
    db: Session = Depends(get_db),
) -> CustomizeGenerateResponse:
    crop = _get_crop(db, request.cake_crop_id)
    preview = _preview_from_crop(crop, request)
    image_path = _actual_crop_path(crop)
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="crop file not found")

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output_name = f"{Path(crop.crop_file_name).stem}_custom_{timestamp}.webp"
    output_path = GENERATED_DIR / output_name

    try:
        _edit_image_with_openai(
            image_path,
            preview.prompt,
            output_path,
            request.model,
            _reference_path_from_url(request.character_reference_image_url),
        )
    except Exception as exc:
        return CustomizeGenerateResponse(
            **preview.model_dump(),
            status="failed",
            generated_image_url=None,
            error=str(exc),
        )

    return CustomizeGenerateResponse(
        **preview.model_dump(),
        status="ok",
        generated_image_url=f"/static/generated/{output_name}",
        error=None,
    )


@router.get("/mvp", response_class=HTMLResponse)
def customize_mvp_page() -> HTMLResponse:
    return HTMLResponse(
        f"""
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CAKEY AI 수정 MVP</title>
  <style>
    :root {{
      --bg: #fff5f7;
      --ink: #332b30;
      --muted: #75676d;
      --line: #eadde1;
      --pink: #ffc0e2;
      --deep: #7f4e69;
      --cream: #fff0bd;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: #fff;
      color: var(--ink);
      font-family: Pretendard, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    .shell {{
      width: min(100%, 450px);
      min-height: 100vh;
      margin: 0 auto;
      padding: 26px 28px 96px;
      background:
        radial-gradient(circle at 54% 13%, #ffe4f1 0 12%, transparent 33%),
        linear-gradient(180deg, #fff8fa, var(--bg));
    }}
    header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 26px;
    }}
    .brand {{
      font-size: 28px;
      font-weight: 1000;
      color: var(--deep);
      letter-spacing: 0;
    }}
    .step {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 900;
    }}
    h1 {{
      margin: 0;
      color: var(--deep);
      font-size: 30px;
      line-height: 1.32;
      letter-spacing: 0;
    }}
    .lead {{
      margin: 14px 0 24px;
      color: var(--muted);
      line-height: 1.65;
      font-weight: 650;
    }}
    .panel {{
      margin-top: 18px;
      padding: 20px;
      border-radius: 24px;
      background: rgba(255, 255, 255, 0.8);
      box-shadow: 0 16px 34px rgba(127, 78, 105, 0.08);
    }}
    .panel h2 {{
      margin: 0 0 14px;
      font-size: 19px;
      color: var(--deep);
    }}
    .request-list {{
      display: grid;
      gap: 10px;
      margin: 0;
      padding: 0;
      list-style: none;
    }}
    .request-list li {{
      display: grid;
      gap: 4px;
      padding: 12px 14px;
      border-radius: 16px;
      background: #fff7fa;
      font-size: 14px;
      font-weight: 800;
    }}
    .request-list span {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 750;
    }}
    .compare {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 14px;
    }}
    figure {{
      margin: 0;
      overflow: hidden;
      border-radius: 22px;
      background: #fff;
      box-shadow: 0 12px 24px rgba(127, 78, 105, 0.09);
    }}
    figure img {{
      display: block;
      width: 100%;
      aspect-ratio: 1;
      object-fit: cover;
      background: #f3e8eb;
    }}
    figcaption {{
      padding: 12px 14px 14px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 850;
    }}
    .after figcaption {{
      color: var(--deep);
    }}
    .prompt {{
      white-space: pre-wrap;
      color: #5f5559;
      font-size: 13px;
      line-height: 1.6;
    }}
    .primary {{
      display: block;
      width: 100%;
      margin-top: 22px;
      padding: 17px 18px;
      border: 0;
      border-radius: 28px;
      background: var(--cream);
      color: #5f4b53;
      text-align: center;
      text-decoration: none;
      font-weight: 950;
      box-shadow: 0 12px 24px rgba(127, 78, 105, 0.13);
    }}
  </style>
</head>
<body>
  <main class="shell">
    <header>
      <div class="brand">CAKEY</div>
      <div class="step">AI CUSTOM MVP</div>
    </header>

    <h1>추천 케이크를<br>내 옵션에 맞게 수정했어요</h1>
    <p class="lead">추천된 실제 케이크 사진을 기준으로 사용자가 고른 옵션과 다른 부분만 AI가 수정하는 흐름입니다.</p>

    <section class="panel">
      <h2>변경 요청사항</h2>
      <ul class="request-list">
        <li><span>대표 색상</span>브라운 · 블랙 · 핑크 · 화이트 → 블루</li>
        <li><span>전체 스타일</span>러블리 · 캐릭터 → 러블리</li>
        <li><span>캐릭터</span>사람 → 토끼</li>
      </ul>
    </section>

    <section class="panel">
      <h2>비교 결과</h2>
      <div class="compare">
        <figure>
          <img src="{DEMO_BASE_CROP}" alt="기존 추천 케이크">
          <figcaption>기존 추천 이미지</figcaption>
        </figure>
        <figure class="after">
          <img src="{DEMO_GENERATED}" alt="AI 수정 케이크">
          <figcaption>AI 수정 예시 이미지</figcaption>
        </figure>
      </div>
    </section>

    <section class="panel">
      <h2>AI 수정 지시문</h2>
      <div class="prompt">케이크 본체의 촬영 구도, 질감, 조명, 배경은 최대한 유지한다.
아래 변경사항만 반영해서 실제 케이크 사진처럼 자연스럽게 편집한다.
- 대표 색상은 블루 중심으로 변경
- 캐릭터 요소는 사람에서 토끼로 변경
- 전체 느낌은 러블리하게 유지
- 케이크 박스, 손, 테이블, 배경은 과하게 바꾸지 않음</div>
    </section>

    <a class="primary" href="/demo">추천 화면으로 돌아가기</a>
  </main>
</body>
</html>
        """
    )


@router.get("/flow", response_class=HTMLResponse)
def customize_flow_page() -> HTMLResponse:
    return HTMLResponse(
        f"""
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CAKEY MVP Flow</title>
  <style>
    :root {{
      --bg: #fff5f7;
      --ink: #332b30;
      --muted: #75676d;
      --line: #eadde1;
      --pink: #ffc0e2;
      --deep: #7f4e69;
      --cream: #fff0bd;
      --mint: #d8eee9;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: #fff;
      color: var(--ink);
      font-family: Pretendard, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    .shell {{
      width: min(100%, 460px);
      min-height: 100vh;
      margin: 0 auto;
      padding: 24px 24px 90px;
      background:
        radial-gradient(circle at 58% 8%, #ffe4f1 0 12%, transparent 34%),
        linear-gradient(180deg, #fff8fa, var(--bg));
    }}
    header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 22px;
    }}
    .brand {{
      color: var(--deep);
      font-size: 29px;
      font-weight: 1000;
    }}
    .badge {{
      padding: 7px 10px;
      border-radius: 999px;
      background: var(--pink);
      color: var(--deep);
      font-size: 11px;
      font-weight: 950;
    }}
    h1 {{
      margin: 0;
      color: var(--deep);
      font-size: 31px;
      line-height: 1.32;
    }}
    .lead {{
      margin: 14px 0 22px;
      color: var(--muted);
      line-height: 1.65;
      font-weight: 700;
    }}
    .step {{
      margin-top: 18px;
      padding: 18px;
      border-radius: 24px;
      background: rgba(255, 255, 255, 0.82);
      box-shadow: 0 16px 34px rgba(127, 78, 105, 0.08);
    }}
    .step-head {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 14px;
    }}
    .num {{
      display: grid;
      place-items: center;
      width: 30px;
      height: 30px;
      border-radius: 50%;
      background: var(--deep);
      color: #fff;
      font-size: 13px;
      font-weight: 950;
    }}
    h2 {{
      margin: 0;
      color: var(--deep);
      font-size: 19px;
    }}
    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .chip {{
      padding: 8px 11px;
      border-radius: 999px;
      background: #fff7fa;
      color: #5f4b53;
      font-size: 13px;
      font-weight: 850;
    }}
    .chip.strong {{
      background: var(--cream);
      color: var(--deep);
    }}
    .recommend-card {{
      display: grid;
      grid-template-columns: 112px 1fr;
      gap: 13px;
      align-items: start;
    }}
    .recommend-card img,
    .compare img {{
      width: 100%;
      aspect-ratio: 1;
      border-radius: 18px;
      object-fit: cover;
      background: #f3e8eb;
    }}
    .meta {{
      display: grid;
      gap: 8px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
      font-weight: 760;
    }}
    .score {{
      color: var(--deep);
      font-size: 18px;
      font-weight: 1000;
    }}
    .diff {{
      display: grid;
      gap: 9px;
      margin: 0;
      padding: 0;
      list-style: none;
    }}
    .diff li {{
      display: grid;
      gap: 3px;
      padding: 11px 12px;
      border-radius: 16px;
      background: #fff7fa;
      font-size: 13px;
      font-weight: 850;
    }}
    .diff span {{
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
    }}
    .compare {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }}
    figure {{
      margin: 0;
    }}
    figcaption {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 850;
      text-align: center;
    }}
    .arrow {{
      margin: 14px auto 0;
      width: 2px;
      height: 22px;
      background: var(--line);
      position: relative;
    }}
    .arrow::after {{
      content: "";
      position: absolute;
      left: 50%;
      bottom: -4px;
      width: 8px;
      height: 8px;
      border-right: 2px solid var(--line);
      border-bottom: 2px solid var(--line);
      transform: translateX(-50%) rotate(45deg);
    }}
    .note {{
      margin-top: 12px;
      padding: 13px 14px;
      border-radius: 16px;
      background: var(--mint);
      color: #48645f;
      font-size: 13px;
      line-height: 1.55;
      font-weight: 800;
    }}
    .actions {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-top: 22px;
    }}
    .button {{
      display: block;
      padding: 14px 12px;
      border-radius: 24px;
      background: var(--cream);
      color: #5f4b53;
      text-align: center;
      text-decoration: none;
      font-size: 14px;
      font-weight: 950;
    }}
    .button.secondary {{
      background: #fff;
      border: 1px solid var(--line);
    }}
  </style>
</head>
<body>
  <main class="shell">
    <header>
      <div class="brand">CAKEY</div>
      <div class="badge">FULL MVP FLOW</div>
    </header>

    <h1>구매자 옵션에서<br>AI 수정 예시까지</h1>
    <p class="lead">사용자가 원하는 케이크 옵션을 고르면, 비슷한 실제 케이크를 먼저 추천하고 다른 부분만 AI로 수정하는 흐름입니다.</p>

    <section class="step">
      <div class="step-head"><div class="num">1</div><h2>사용자 옵션 선택</h2></div>
      <div class="chips">
        <span class="chip strong">대표 색상: 블루</span>
        <span class="chip strong">스타일: 러블리</span>
        <span class="chip strong">캐릭터: 토끼</span>
        <span class="chip">레터링: 중앙레터링</span>
      </div>
    </section>
    <div class="arrow"></div>

    <section class="step">
      <div class="step-head"><div class="num">2</div><h2>유사 케이크 추천</h2></div>
      <div class="recommend-card">
        <img src="{DEMO_BASE_CROP}" alt="추천된 기존 케이크">
        <div class="meta">
          <div class="score">추천 점수 8</div>
          <div>기존 제작 사례 중 태그가 가장 가까운 crop 이미지를 먼저 보여줍니다.</div>
          <div>현재 태그: 핑크 · 화이트 · 러블리 · 캐릭터 · 중앙레터링</div>
        </div>
      </div>
    </section>
    <div class="arrow"></div>

    <section class="step">
      <div class="step-head"><div class="num">3</div><h2>다른 부분만 계산</h2></div>
      <ul class="diff">
        <li><span>대표 색상</span>브라운 · 블랙 · 핑크 · 화이트 → 블루</li>
        <li><span>전체 스타일</span>러블리 · 캐릭터 → 러블리</li>
        <li><span>캐릭터</span>사람 → 토끼</li>
      </ul>
    </section>
    <div class="arrow"></div>

    <section class="step">
      <div class="step-head"><div class="num">4</div><h2>AI 수정 결과 확인</h2></div>
      <div class="compare">
        <figure>
          <img src="{DEMO_BASE_CROP}" alt="기존 추천 케이크">
          <figcaption>기존 추천</figcaption>
        </figure>
        <figure>
          <img src="{DEMO_GENERATED}" alt="AI 수정 케이크">
          <figcaption>AI 수정 예시</figcaption>
        </figure>
      </div>
      <div class="note">실제 서비스에서는 이 단계가 사용자가 명확히 버튼을 눌렀을 때만 실행됩니다. 자동 실행하면 비용과 대기시간이 커집니다.</div>
    </section>

    <div class="actions">
      <a class="button secondary" href="/demo">추천 데모</a>
      <a class="button" href="/customize/mvp">수정 비교 화면</a>
    </div>
  </main>
</body>
</html>
        """
    )
