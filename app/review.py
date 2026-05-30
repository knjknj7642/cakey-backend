from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import CakeCrop, CakeCropReview


router = APIRouter(prefix="/review", tags=["review"])

REVIEW_STATUSES = {"approved", "rejected", "duplicate", "partial", "merged"}


class CropReviewUpdate(BaseModel):
    status: str
    note: str | None = None


def serialize_crop(crop: CakeCrop) -> dict:
    return {
        "cake_crop_id": crop.cake_crop_id,
        "crop_image_url": crop.crop_file_path,
        "original_image_url": crop.original_image.file_path,
        "original_file_name": crop.original_image.file_name,
        "crop_file_name": crop.crop_file_name,
        "shop_name": crop.original_image.shop_name,
        "confidence": crop.detection_confidence,
        "bbox": {
            "x_min": crop.x_min,
            "y_min": crop.y_min,
            "x_max": crop.x_max,
            "y_max": crop.y_max,
        },
        "status": crop.review.status if crop.review else "pending",
        "note": crop.review.note if crop.review else None,
    }


@router.get("/crops", response_class=HTMLResponse)
def review_page() -> HTMLResponse:
    return HTMLResponse(
        """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Crop Review</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f4f5f7;
      --panel: #ffffff;
      --line: #d9dde3;
      --text: #18202a;
      --muted: #667085;
      --ok: #137333;
      --bad: #b42318;
      --warn: #b54708;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
    }
    header {
      height: 56px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 20px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }
    .header-tools {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    select {
      height: 34px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      padding: 0 8px;
      font: inherit;
    }
    .empty {
      display: none;
      padding: 40px;
      color: var(--muted);
      text-align: center;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      margin: 16px;
    }
    main {
      display: grid;
      grid-template-columns: 1fr 420px;
      gap: 16px;
      padding: 16px;
      min-height: calc(100vh - 56px);
    }
    .viewer, .sidebar {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }
    .viewer {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      padding: 12px;
      min-height: 700px;
    }
    figure {
      margin: 0;
      display: flex;
      flex-direction: column;
      min-width: 0;
    }
    figcaption {
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 8px;
    }
    img {
      width: 100%;
      height: min(72vh, 760px);
      object-fit: contain;
      background: #f8fafc;
      border: 1px solid var(--line);
      border-radius: 6px;
    }
    .image-wrap {
      position: relative;
    }
    .loading {
      position: absolute;
      inset: 0;
      display: none;
      align-items: center;
      justify-content: center;
      background: rgba(248, 250, 252, 0.82);
      color: var(--muted);
      border-radius: 6px;
      font-size: 14px;
    }
    .image-wrap.is-loading .loading {
      display: flex;
    }
    .sidebar {
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .meta {
      display: grid;
      gap: 8px;
      font-size: 14px;
    }
    .meta div {
      display: flex;
      justify-content: space-between;
      gap: 12px;
    }
    .meta span:first-child { color: var(--muted); }
    textarea {
      width: 100%;
      min-height: 88px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      font: inherit;
    }
    .actions {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }
    button {
      height: 42px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      cursor: pointer;
      font-weight: 600;
    }
    button[data-status="approved"] { color: var(--ok); }
    button[data-status="rejected"] { color: var(--bad); }
    button[data-status="duplicate"],
    button[data-status="partial"],
    button[data-status="merged"] { color: var(--warn); }
    .toolbar {
      display: flex;
      gap: 8px;
    }
    .toolbar button { flex: 1; }
    .status {
      font-weight: 700;
    }
    @media (max-width: 960px) {
      main { grid-template-columns: 1fr; }
      .viewer { grid-template-columns: 1fr; min-height: 0; }
      img { height: min(48vh, 520px); }
    }
  </style>
</head>
<body>
  <header>
    <strong>Crop Review</strong>
    <div class="header-tools">
      <select id="status-filter">
        <option value="pending">미검수</option>
        <option value="approved">승인</option>
        <option value="rejected">반려</option>
        <option value="duplicate">중복</option>
        <option value="partial">부분잘림</option>
        <option value="merged">여러 케이크 포함</option>
      </select>
      <span id="counter">loading...</span>
    </div>
  </header>
  <div class="empty" id="empty">해당 상태의 crop이 없습니다.</div>
  <main>
    <section class="viewer">
      <figure>
        <figcaption>Original</figcaption>
        <div class="image-wrap" id="original-wrap">
          <img id="original" alt="original">
          <div class="loading">loading...</div>
        </div>
      </figure>
      <figure>
        <figcaption>Crop</figcaption>
        <div class="image-wrap" id="crop-wrap">
          <img id="crop" alt="crop">
          <div class="loading">loading...</div>
        </div>
      </figure>
    </section>
    <aside class="sidebar">
      <div class="meta">
        <div><span>ID</span><strong id="crop-id"></strong></div>
        <div><span>Shop</span><strong id="shop"></strong></div>
        <div><span>Original</span><strong id="original-name"></strong></div>
        <div><span>Crop</span><strong id="crop-name"></strong></div>
        <div><span>Confidence</span><strong id="confidence"></strong></div>
        <div><span>BBox</span><strong id="bbox"></strong></div>
        <div><span>Status</span><strong class="status" id="status"></strong></div>
      </div>
      <textarea id="note" placeholder="메모"></textarea>
      <div class="actions">
        <button data-status="approved">승인</button>
        <button data-status="rejected">반려</button>
        <button data-status="duplicate">중복</button>
        <button data-status="partial">부분잘림</button>
        <button data-status="merged">여러 케이크 포함</button>
      </div>
      <div class="toolbar">
        <button id="prev">이전</button>
        <button id="next">다음</button>
      </div>
    </aside>
  </main>
  <script>
    let items = [];
    let index = 0;

    function setLoading(isLoading) {
      document.getElementById("original-wrap").classList.toggle("is-loading", isLoading);
      document.getElementById("crop-wrap").classList.toggle("is-loading", isLoading);
    }

    function preloadItem(item) {
      if (!item) return;
      [item.original_image_url, item.crop_image_url].forEach((src) => {
        const image = new Image();
        image.src = src;
      });
    }

    async function loadItems() {
      const status = document.getElementById("status-filter").value;
      const response = await fetch(`/review/api/crops?status=${status}`);
      items = await response.json();
      index = 0;
      render();
    }

    function render() {
      const item = items[index];
      document.getElementById("counter").textContent = items.length ? `${index + 1} / ${items.length}` : "0 / 0";
      document.querySelector("main").style.display = item ? "grid" : "none";
      document.getElementById("empty").style.display = item ? "none" : "block";
      if (!item) {
        document.getElementById("original").removeAttribute("src");
        document.getElementById("crop").removeAttribute("src");
        return;
      }
      setLoading(true);
      document.getElementById("original").src = item.original_image_url;
      document.getElementById("crop").src = item.crop_image_url;
      document.getElementById("crop-id").textContent = item.cake_crop_id;
      document.getElementById("shop").textContent = item.shop_name;
      document.getElementById("original-name").textContent = item.original_file_name;
      document.getElementById("crop-name").textContent = item.crop_file_name;
      document.getElementById("confidence").textContent = item.confidence.toFixed(3);
      document.getElementById("bbox").textContent = `${item.bbox.x_min}, ${item.bbox.y_min}, ${item.bbox.x_max}, ${item.bbox.y_max}`;
      document.getElementById("status").textContent = item.status;
      document.getElementById("note").value = item.note || "";
      preloadItem(items[index + 1]);
      preloadItem(items[index - 1]);
    }

    async function update(status) {
      const item = items[index];
      if (!item) return;
      await fetch(`/review/api/crops/${item.cake_crop_id}`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({status, note: document.getElementById("note").value || null})
      });
      items.splice(index, 1);
      if (index >= items.length) index = Math.max(0, items.length - 1);
      render();
    }

    document.querySelectorAll("[data-status]").forEach((button) => {
      button.addEventListener("click", () => update(button.dataset.status));
    });
    document.getElementById("prev").addEventListener("click", () => {
      index = Math.max(0, index - 1);
      render();
    });
    document.getElementById("next").addEventListener("click", () => {
      index = Math.min(Math.max(0, items.length - 1), index + 1);
      render();
    });
    document.getElementById("status-filter").addEventListener("change", loadItems);
    ["original", "crop"].forEach((id) => {
      document.getElementById(id).addEventListener("load", () => {
        const originalLoaded = document.getElementById("original").complete;
        const cropLoaded = document.getElementById("crop").complete;
        if (originalLoaded && cropLoaded) setLoading(false);
      });
    });
    loadItems();
  </script>
</body>
</html>
        """
    )


@router.get("/api/crops")
def list_crops(status: str = "pending", db: Session = Depends(get_db)) -> list[dict]:
    query = (
        db.query(CakeCrop)
        .options(joinedload(CakeCrop.original_image), joinedload(CakeCrop.review))
        .filter(CakeCrop.detection_confidence != 0.1)
        .order_by(CakeCrop.cake_crop_id.desc())
    )
    if status == "pending":
        query = query.outerjoin(CakeCropReview).filter(CakeCropReview.cake_crop_id.is_(None))
    elif status in REVIEW_STATUSES:
        query = query.join(CakeCropReview).filter(CakeCropReview.status == status)
    else:
        raise HTTPException(status_code=400, detail="invalid review status")
    return [serialize_crop(crop) for crop in query.all()]


@router.post("/api/crops/{cake_crop_id}")
def update_crop_review(
    cake_crop_id: int,
    payload: CropReviewUpdate,
    db: Session = Depends(get_db),
) -> dict:
    if payload.status not in REVIEW_STATUSES:
        raise HTTPException(status_code=400, detail="invalid review status")

    crop = db.get(CakeCrop, cake_crop_id)
    if crop is None:
        raise HTTPException(status_code=404, detail="crop not found")

    review = crop.review
    if review is None:
        review = CakeCropReview(cake_crop_id=cake_crop_id)
        db.add(review)
    review.status = payload.status
    review.note = payload.note.strip() if payload.note else None
    review.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(review)
    return {"cake_crop_id": cake_crop_id, "status": review.status}
