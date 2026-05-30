import csv
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.ai_tagging import TAG_CHOICES
from app.database import SessionLocal
from app.models import CropTag


router = APIRouter(prefix="/review/tags", tags=["tag-review"])

BASE_DIR = Path(__file__).resolve().parent.parent
DRAFT_PATH = BASE_DIR / "data" / "metadata" / "crop_tags_draft.csv"
FIELDNAMES = [
    "cake_crop_id",
    "crop_file_name",
    "shape",
    "dominant_color",
    "visual_style",
    "lettering_type",
    "board_lettering",
    "border_type",
    "cream_decoration",
    "topping_decoration",
    "character_type",
    "text_presence",
    "memo",
]


class TagReviewUpdate(BaseModel):
    tags: dict[str, list[str]]
    memo: str | None = None


def split_values(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split("|") if item.strip()]


def join_values(values: list[str]) -> str:
    return "|".join(values)


def read_draft_rows() -> list[dict[str, str]]:
    if not DRAFT_PATH.exists():
        return []
    with DRAFT_PATH.open("r", encoding="utf-8-sig", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def write_draft_rows(rows: list[dict[str, str]]) -> None:
    DRAFT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DRAFT_PATH.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def serialize_row(row: dict[str, str]) -> dict:
    return {
        "cake_crop_id": int(row["cake_crop_id"]),
        "crop_file_name": row["crop_file_name"],
        "crop_image_url": f"/static/crops/{row['crop_file_name']}",
        "tags": {key: split_values(row.get(key)) for key in TAG_CHOICES},
        "memo": row.get("memo", ""),
    }


@router.get("", response_class=HTMLResponse)
def tag_review_page() -> HTMLResponse:
    return HTMLResponse(
        """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Tag Review</title>
  <style>
    :root {
      --bg: #f4f5f7;
      --panel: #fff;
      --line: #d9dde3;
      --text: #18202a;
      --muted: #667085;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Arial, sans-serif;
    }
    header {
      height: 56px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 20px;
      background: var(--panel);
      border-bottom: 1px solid var(--line);
    }
    main {
      display: grid;
      grid-template-columns: 180px minmax(360px, 0.9fr) 1.1fr;
      gap: 16px;
      padding: 16px;
    }
    .list-panel, .image-panel, .form-panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }
    .list-panel {
      display: flex;
      flex-direction: column;
      gap: 8px;
      max-height: calc(100vh - 88px);
      overflow: auto;
    }
    .thumb {
      width: 100%;
      border: 2px solid transparent;
      border-radius: 6px;
      padding: 4px;
      background: #fff;
      cursor: pointer;
      text-align: left;
    }
    .thumb.is-active {
      border-color: #18202a;
    }
    .thumb img {
      height: 96px;
      border: 1px solid var(--line);
    }
    .thumb span {
      display: block;
      margin-top: 4px;
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    img {
      width: 100%;
      max-height: calc(100vh - 140px);
      object-fit: contain;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #f8fafc;
    }
    .meta {
      color: var(--muted);
      font-size: 13px;
      margin: 0 0 10px;
      word-break: break-all;
    }
    .tag-row {
      display: grid;
      grid-template-columns: 160px 1fr;
      gap: 12px;
      padding: 10px 0;
      border-bottom: 1px solid var(--line);
    }
    .tag-row label {
      color: var(--muted);
      font-size: 13px;
      padding-top: 6px;
    }
    .choices {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .choice {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 6px 9px;
      font-size: 13px;
      cursor: pointer;
      background: #fff;
    }
    .choice input { margin: 0; }
    textarea {
      width: 100%;
      min-height: 76px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      font: inherit;
      resize: vertical;
    }
    .actions {
      display: flex;
      gap: 8px;
      margin-top: 14px;
    }
    button {
      height: 42px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      cursor: pointer;
      font-weight: 700;
      padding: 0 14px;
    }
    #save { background: #18202a; color: #fff; }
    @media (max-width: 980px) {
      main { grid-template-columns: 1fr; }
      img { max-height: 55vh; }
    }
  </style>
</head>
<body>
  <header>
    <strong>Tag Review</strong>
    <span id="counter">loading...</span>
  </header>
  <main>
    <section class="list-panel" id="thumbs"></section>
    <section class="image-panel">
      <p class="meta" id="crop-meta"></p>
      <img id="crop" alt="crop">
    </section>
    <section class="form-panel">
      <div id="form"></div>
      <label class="meta" for="memo">memo</label>
      <textarea id="memo"></textarea>
      <div class="actions">
        <button id="prev">이전</button>
        <button id="save">저장 후 다음</button>
        <button id="next">다음</button>
      </div>
    </section>
  </main>
  <script>
    const choices = __TAG_CHOICES__;
    let items = [];
    let index = 0;

    async function loadItems() {
      const response = await fetch("/review/tags/api/drafts");
      items = await response.json();
      render();
    }

    function render() {
      const item = items[index];
      document.getElementById("counter").textContent = items.length ? `${index + 1} / ${items.length}` : "0 / 0";
      if (!item) return;
      renderThumbs();
      document.getElementById("crop").src = item.crop_image_url;
      document.getElementById("crop-meta").textContent = `${item.cake_crop_id} · ${item.crop_file_name}`;
      document.getElementById("memo").value = item.memo || "";
      const form = document.getElementById("form");
      form.innerHTML = "";
      Object.entries(choices).forEach(([key, values]) => {
        const row = document.createElement("div");
        row.className = "tag-row";
        const label = document.createElement("label");
        label.textContent = key;
        const group = document.createElement("div");
        group.className = "choices";
        values.forEach((value) => {
          const wrapper = document.createElement("label");
          wrapper.className = "choice";
          const input = document.createElement("input");
          input.type = "checkbox";
          input.name = key;
          input.value = value;
          input.checked = (item.tags[key] || []).includes(value);
          wrapper.append(input, value);
          group.append(wrapper);
        });
        row.append(label, group);
        form.append(row);
      });
    }

    function renderThumbs() {
      const thumbs = document.getElementById("thumbs");
      thumbs.innerHTML = "";
      items.forEach((item, itemIndex) => {
        const button = document.createElement("button");
        button.className = itemIndex === index ? "thumb is-active" : "thumb";
        const image = document.createElement("img");
        image.src = item.crop_image_url;
        image.alt = item.crop_file_name;
        const label = document.createElement("span");
        label.textContent = `${itemIndex + 1}. ${item.crop_file_name}`;
        button.append(image, label);
        button.addEventListener("click", () => {
          index = itemIndex;
          render();
        });
        thumbs.append(button);
      });
    }

    function collect() {
      const tags = {};
      Object.keys(choices).forEach((key) => {
        tags[key] = [...document.querySelectorAll(`input[name="${key}"]:checked`)].map((node) => node.value);
      });
      return {tags, memo: document.getElementById("memo").value || null};
    }

    async function save() {
      const item = items[index];
      if (!item) return;
      const payload = collect();
      await fetch(`/review/tags/api/drafts/${item.cake_crop_id}`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
      });
      item.tags = payload.tags;
      item.memo = payload.memo;
      index = Math.min(index + 1, items.length - 1);
      render();
    }

    document.getElementById("prev").addEventListener("click", () => {
      index = Math.max(0, index - 1);
      render();
    });
    document.getElementById("next").addEventListener("click", () => {
      index = Math.min(items.length - 1, index + 1);
      render();
    });
    document.getElementById("save").addEventListener("click", save);
    loadItems();
  </script>
</body>
</html>
        """.replace("__TAG_CHOICES__", json_choices())
    )


def json_choices() -> str:
    import json

    return json.dumps(TAG_CHOICES, ensure_ascii=False)


@router.get("/api/drafts")
def list_tag_drafts() -> list[dict]:
    return [serialize_row(row) for row in read_draft_rows()]


@router.post("/api/drafts/{cake_crop_id}")
def update_tag_draft(cake_crop_id: int, payload: TagReviewUpdate) -> dict:
    rows = read_draft_rows()
    for row in rows:
        if int(row["cake_crop_id"]) != cake_crop_id:
            continue

        for tag_key, choices in TAG_CHOICES.items():
            values = payload.tags.get(tag_key, [])
            invalid = [value for value in values if value not in choices]
            if invalid:
                raise HTTPException(
                    status_code=400,
                    detail=f"invalid {tag_key}: {invalid}",
                )
            row[tag_key] = join_values(values)
        row["memo"] = payload.memo or ""
        write_draft_rows(rows)
        sync_crop_tags(cake_crop_id, row)
        return {"cake_crop_id": cake_crop_id, "status": "saved"}
    raise HTTPException(status_code=404, detail="draft not found")


def sync_crop_tags(cake_crop_id: int, row: dict[str, str]) -> None:
    db = SessionLocal()
    try:
        db.query(CropTag).filter(CropTag.cake_crop_id == cake_crop_id).delete(
            synchronize_session=False
        )
        for tag_key, choices in TAG_CHOICES.items():
            for tag_value in split_values(row.get(tag_key)):
                if tag_value == "판단불가" or tag_value not in choices:
                    continue
                db.add(
                    CropTag(
                        cake_crop_id=cake_crop_id,
                        tag_key=tag_key,
                        tag_value=tag_value,
                        confidence=1.0,
                        source_type="reviewed",
                    )
                )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
