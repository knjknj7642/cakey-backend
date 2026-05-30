from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from PIL import Image


router = APIRouter(tags=["demo"])

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CROP_DIR = PROJECT_ROOT / "data" / "crops"
THUMB_DIR = PROJECT_ROOT / "data" / "thumbs" / "crops"


@router.get("/demo/thumbs/crops/{file_name}")
def crop_thumbnail(file_name: str) -> FileResponse:
    source_path = CROP_DIR / Path(file_name).name
    if not source_path.exists() or not source_path.is_file():
        raise HTTPException(status_code=404, detail="crop image not found")

    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    thumb_path = THUMB_DIR / f"{source_path.stem}.webp"
    if not thumb_path.exists() or source_path.stat().st_mtime > thumb_path.stat().st_mtime:
        with Image.open(source_path) as image:
            image.thumbnail((420, 420))
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGB")
            image.save(thumb_path, "WEBP", quality=72, method=6)

    return FileResponse(thumb_path, media_type="image/webp")


@router.get("/demo", response_class=HTMLResponse)
def buyer_demo() -> HTMLResponse:
    return HTMLResponse(
        """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Cake Finder MVP</title>
  <style>
    :root {
      --bg: #f5f6f8;
      --panel: #fff;
      --line: #d9dde3;
      --text: #18202a;
      --muted: #667085;
      --accent: #111827;
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
      grid-template-columns: 320px 1fr;
      gap: 16px;
      padding: 16px;
    }
    aside, section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }
    aside {
      padding: 16px;
      height: calc(100vh - 88px);
      overflow: auto;
    }
    section {
      padding: 16px;
      min-height: calc(100vh - 88px);
    }
    h2 {
      margin: 0 0 12px;
      font-size: 16px;
    }
    .group {
      padding: 14px 0;
      border-bottom: 1px solid var(--line);
    }
    .group-title {
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
    }
    .chips {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .chip {
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
    .chip:has(input:checked) {
      border-color: var(--accent);
      background: #eef2ff;
    }
    .chip input { margin: 0; }
    button {
      width: 100%;
      height: 42px;
      border: 1px solid var(--accent);
      border-radius: 6px;
      background: var(--accent);
      color: #fff;
      font-weight: 700;
      cursor: pointer;
      margin-top: 14px;
    }
    #clear {
      background: #fff;
      color: var(--accent);
      border-color: var(--line);
      margin-top: 8px;
    }
    .results {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
      gap: 14px;
    }
    .card {
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      background: #fff;
    }
    .card img {
      width: 100%;
      aspect-ratio: 1 / 1;
      object-fit: cover;
      display: block;
      background: #f8fafc;
    }
    .card img.loading {
      opacity: 0.18;
    }
    .card-body {
      padding: 10px;
      display: grid;
      gap: 6px;
      font-size: 13px;
    }
    .score {
      font-weight: 700;
    }
    .tags {
      color: var(--muted);
      line-height: 1.4;
    }
    .mini-actions {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-top: 4px;
    }
    .mini-actions button {
      height: 34px;
      margin: 0;
      font-size: 12px;
    }
    .mini-actions .secondary {
      background: #fff;
      color: var(--accent);
      border-color: var(--line);
    }
    .customize-box {
      display: grid;
      gap: 8px;
      margin-top: 6px;
      padding: 10px;
      border-radius: 6px;
      background: #f8fafc;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
      white-space: pre-wrap;
    }
    .customize-box img {
      width: 100%;
      border-radius: 6px;
      background: #fff;
    }
    .empty {
      color: var(--muted);
      padding: 40px 0;
      text-align: center;
    }
    .status-line {
      color: var(--muted);
      margin-bottom: 12px;
      font-size: 14px;
    }
    .loading-note {
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }
    .loading-note::before {
      content: "";
      width: 12px;
      height: 12px;
      border: 2px solid #d9dde3;
      border-top-color: var(--accent);
      border-radius: 50%;
      animation: spin 700ms linear infinite;
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    @media (max-width: 900px) {
      main { grid-template-columns: 1fr; }
      aside { height: auto; }
    }
  </style>
</head>
<body>
  <header>
    <strong>Cake Finder MVP</strong>
    <span id="summary">옵션을 선택하세요</span>
  </header>
  <main>
    <aside>
      <h2>원하는 옵션</h2>
      <div id="filters"></div>
      <button id="search">비슷한 케이크 찾기</button>
      <button id="clear">초기화</button>
    </aside>
    <section>
      <h2>추천 결과</h2>
      <div class="status-line" id="status-line">옵션을 선택하면 추천 버튼을 사용할 수 있습니다.</div>
      <div class="results" id="results"></div>
    </section>
  </main>
  <script>
    const labelMap = {
      shape: "모양",
      dominant_color: "대표 색상",
      visual_style: "스타일",
      lettering_type: "레터링",
      board_lettering: "판 위 글씨",
      border_type: "테두리",
      cream_decoration: "크림 장식",
      topping_decoration: "토핑",
      character_type: "캐릭터",
      text_presence: "문구"
    };
    const order = [
      "shape", "dominant_color", "visual_style", "character_type",
      "lettering_type", "border_type", "cream_decoration",
      "topping_decoration", "board_lettering", "text_presence"
    ];
    let activeRequest = null;

    async function loadTags() {
      const response = await fetch("/tags");
      const tags = await response.json();
      const filters = document.getElementById("filters");
      filters.innerHTML = "";
      order.filter((key) => tags[key]).forEach((key) => {
        const group = document.createElement("div");
        group.className = "group";
        const title = document.createElement("div");
        title.className = "group-title";
        title.textContent = labelMap[key] || key;
        const chips = document.createElement("div");
        chips.className = "chips";
        tags[key].forEach((value) => {
          const label = document.createElement("label");
          label.className = "chip";
          const input = document.createElement("input");
          input.type = "checkbox";
          input.name = key;
          input.value = value;
          input.checked = false;
          label.append(input, value);
          chips.append(label);
        });
        group.append(title, chips);
        filters.append(group);
      });
    }

    function selectedTags() {
      const tags = {};
      document.querySelectorAll("#filters input:checked").forEach((input) => {
        if (!tags[input.name]) tags[input.name] = [];
        tags[input.name].push(input.value);
      });
      return tags;
    }

    function tagText(tags) {
      return Object.entries(tags)
        .map(([key, values]) => `${labelMap[key] || key}: ${values.join(", ")}`)
        .join(" · ");
    }

    function thumbUrl(imageUrl) {
      const fileName = imageUrl.split("/").pop();
      const stem = fileName.replace(/\.[^.]+$/, "");
      return `/static/thumbs/crops/${encodeURIComponent(stem)}.webp`;
    }

    async function customizePreview(item, box) {
      box.textContent = "수정 지시문을 만드는 중입니다.";
      const response = await fetch("/customize/preview", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          cake_crop_id: item.cake_crop_id,
          target_tags: selectedTags()
        })
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      box.textContent = data.prompt;
    }

    async function customizeGenerate(item, box) {
      box.textContent = "AI 이미지 수정을 1회 요청 중입니다. 잠시 기다려주세요.";
      const response = await fetch("/customize/generate", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          cake_crop_id: item.cake_crop_id,
          target_tags: selectedTags(),
          model: "gpt-image-1-mini"
        })
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (data.status !== "ok") {
        box.textContent = `AI 수정 실패: ${data.error || "unknown error"}\n\n${data.prompt}`;
        return;
      }
      box.innerHTML = `
        <strong>AI 수정 결과</strong>
        <img src="${data.generated_image_url}" alt="AI 수정 결과">
        <span>${data.prompt}</span>
      `;
    }

    async function search() {
      const tags = selectedTags();
      const selectedCount = Object.values(tags).flat().length;
      document.getElementById("summary").textContent = selectedCount ? `${selectedCount}개 옵션 선택` : "옵션을 선택하세요";
      if (!selectedCount) {
        if (activeRequest) activeRequest.abort();
        document.getElementById("status-line").textContent = "옵션을 선택하면 추천 버튼을 사용할 수 있습니다.";
        document.getElementById("results").innerHTML = "";
        return;
      }
      if (activeRequest) activeRequest.abort();
      activeRequest = new AbortController();
      document.getElementById("status-line").innerHTML = '<span class="loading-note">추천 결과를 불러오는 중입니다.</span>';
      document.getElementById("search").disabled = true;
      try {
        const response = await fetch("/recommend", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({tags, limit: 8}),
          signal: activeRequest.signal
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        document.getElementById("status-line").textContent = `${data.results.length}개 결과`;
        renderResults(data.results || []);
      } catch (error) {
        if (error.name === "AbortError") return;
        document.getElementById("status-line").textContent = `추천 요청 실패: ${error.message}`;
      } finally {
        document.getElementById("search").disabled = false;
      }
    }

    function renderResults(results) {
      const root = document.getElementById("results");
      root.innerHTML = "";
      if (!results.length) {
        root.innerHTML = '<div class="empty">일치하는 추천 결과가 없습니다.</div>';
        return;
      }
      results.forEach((item) => {
        const card = document.createElement("article");
        card.className = "card";
        const image = document.createElement("img");
        image.src = thumbUrl(item.crop_image_url);
        image.alt = `cake ${item.cake_crop_id}`;
        image.loading = "lazy";
        image.decoding = "async";
        image.className = "loading";
        image.addEventListener("load", () => image.classList.remove("loading"));
        const body = document.createElement("div");
        body.className = "card-body";
        body.innerHTML = `
          <div class="score">score ${item.score}</div>
          <div>${item.shop_name}</div>
          <div class="tags">매칭: ${tagText(item.matched_tags)}</div>
          <div class="tags">${tagText(item.all_tags)}</div>
          <div class="mini-actions">
            <button class="secondary" type="button" data-action="preview">수정 지시문</button>
            <button type="button" data-action="generate">AI 수정 1회</button>
          </div>
          <div class="customize-box" hidden></div>
        `;
        const box = body.querySelector(".customize-box");
        body.querySelector('[data-action="preview"]').addEventListener("click", async () => {
          box.hidden = false;
          try {
            await customizePreview(item, box);
          } catch (error) {
            box.textContent = `수정 지시문 생성 실패: ${error.message}`;
          }
        });
        body.querySelector('[data-action="generate"]').addEventListener("click", async () => {
          box.hidden = false;
          try {
            await customizeGenerate(item, box);
          } catch (error) {
            box.textContent = `AI 수정 요청 실패: ${error.message}`;
          }
        });
        card.append(image, body);
        root.append(card);
      });
    }

    document.getElementById("search").addEventListener("click", search);
    document.getElementById("filters").addEventListener("change", () => {
      const count = Object.values(selectedTags()).flat().length;
      document.getElementById("summary").textContent = count ? `${count}개 옵션 선택` : "옵션을 선택하세요";
      document.getElementById("status-line").textContent = count
        ? "옵션 선택 후 버튼을 누르면 추천됩니다."
        : "옵션을 선택하면 추천 버튼을 사용할 수 있습니다.";
    });
    document.getElementById("clear").addEventListener("click", () => {
      if (activeRequest) activeRequest.abort();
      document.querySelectorAll("#filters input").forEach((input) => { input.checked = false; });
      document.getElementById("results").innerHTML = "";
      document.getElementById("summary").textContent = "옵션을 선택하세요";
      document.getElementById("status-line").textContent = "옵션을 선택하면 추천 버튼을 사용할 수 있습니다.";
    });
    loadTags();
  </script>
</body>
</html>
        """
    )
