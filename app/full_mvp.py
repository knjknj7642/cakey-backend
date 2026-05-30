from fastapi import APIRouter
from fastapi.responses import HTMLResponse


router = APIRouter(tags=["full-mvp"])


@router.get("/mvp/app", response_class=HTMLResponse)
def full_mvp_app() -> HTMLResponse:
    return HTMLResponse(
        """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CAKEY End-to-End MVP</title>
  <style>
    :root {
      --bg: #fff5f7;
      --ink: #332b30;
      --muted: #75676d;
      --line: #eadde1;
      --pink: #ffc0e2;
      --deep: #7f4e69;
      --cream: #fff0bd;
      --mint: #d8eee9;
      --panel: rgba(255, 255, 255, 0.84);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: #fff;
      color: var(--ink);
      font-family: Pretendard, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    button, textarea { font: inherit; }
    .shell {
      width: min(100%, 480px);
      min-height: 100vh;
      margin: 0 auto;
      padding: 24px 24px 96px;
      background:
        radial-gradient(circle at 58% 8%, #ffe4f1 0 12%, transparent 34%),
        linear-gradient(180deg, #fff8fa, var(--bg));
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 22px;
    }
    .brand {
      color: var(--deep);
      font-size: 30px;
      font-weight: 1000;
    }
    .badge {
      padding: 7px 11px;
      border-radius: 999px;
      background: var(--pink);
      color: var(--deep);
      font-size: 11px;
      font-weight: 950;
    }
    h1 {
      margin: 0;
      color: var(--deep);
      font-size: 31px;
      line-height: 1.32;
    }
    .lead {
      margin: 13px 0 22px;
      color: var(--muted);
      line-height: 1.65;
      font-weight: 700;
    }
    .panel {
      margin-top: 18px;
      padding: 18px;
      border-radius: 24px;
      background: var(--panel);
      box-shadow: 0 16px 34px rgba(127, 78, 105, 0.08);
    }
    .panel h2 {
      margin: 0 0 14px;
      color: var(--deep);
      font-size: 19px;
    }
    .group {
      margin-top: 16px;
    }
    .group-title {
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 900;
    }
    .chips {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .chip {
      position: relative;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 8px 11px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #fff;
      color: #5f4b53;
      font-size: 13px;
      font-weight: 850;
      cursor: pointer;
    }
    .chip:has(input:checked) {
      border-color: var(--deep);
      background: var(--cream);
      color: var(--deep);
    }
    .chip input { margin: 0; }
    .primary {
      width: 100%;
      min-height: 52px;
      margin-top: 18px;
      border: 0;
      border-radius: 26px;
      background: var(--cream);
      color: #5f4b53;
      font-weight: 950;
      box-shadow: 0 12px 24px rgba(127, 78, 105, 0.13);
      cursor: pointer;
    }
    .primary.dark {
      background: var(--deep);
      color: #fff;
    }
    .primary:disabled {
      opacity: 0.55;
      cursor: wait;
    }
    .status {
      margin-top: 12px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 800;
      line-height: 1.55;
    }
    .results {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    .card {
      display: grid;
      gap: 8px;
      padding: 10px;
      border: 2px solid transparent;
      border-radius: 18px;
      background: #fff;
      color: var(--ink);
      text-align: left;
      cursor: pointer;
      box-shadow: 0 10px 20px rgba(127, 78, 105, 0.08);
    }
    .card.active {
      border-color: var(--deep);
      background: #fff7fa;
    }
    .card img,
    .compare img {
      display: block;
      width: 100%;
      aspect-ratio: 1;
      border-radius: 14px;
      object-fit: cover;
      background: #f3e8eb;
    }
    .score {
      color: var(--deep);
      font-size: 15px;
      font-weight: 1000;
    }
    .small {
      color: var(--muted);
      font-size: 11px;
      font-weight: 780;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }
    .diff {
      display: grid;
      gap: 9px;
      margin: 0;
      padding: 0;
      list-style: none;
    }
    .diff li {
      display: grid;
      gap: 3px;
      padding: 11px 12px;
      border-radius: 16px;
      background: #fff7fa;
      font-size: 13px;
      font-weight: 850;
    }
    .diff span {
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
    }
    .prompt {
      margin-top: 12px;
      padding: 12px;
      border-radius: 16px;
      background: #f8fafc;
      color: #5f5559;
      font-size: 12px;
      line-height: 1.55;
      white-space: pre-wrap;
    }
    .compare {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      align-items: start;
    }
    figure { margin: 0; }
    figcaption {
      margin-top: 8px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 900;
      text-align: center;
    }
    .note {
      margin-top: 12px;
      padding: 12px;
      border-radius: 16px;
      background: var(--mint);
      color: #48645f;
      font-size: 13px;
      line-height: 1.55;
      font-weight: 800;
    }
    .hidden { display: none; }
  </style>
</head>
<body>
  <main class="shell">
    <header>
      <div class="brand">CAKEY</div>
      <div class="badge">LIVE MVP</div>
    </header>

    <h1>옵션 선택부터<br>AI 수정까지</h1>
    <p class="lead">구매자가 원하는 옵션을 고르면 비슷한 제작 사례를 추천하고, 선택한 이미지에서 다른 부분만 AI로 수정합니다.</p>

    <section class="panel">
      <h2>1. 원하는 케이크 옵션</h2>
      <div id="filters"></div>
      <button id="recommendButton" class="primary dark" type="button">비슷한 케이크 찾기</button>
      <div id="recommendStatus" class="status">옵션을 고른 뒤 추천을 실행하세요.</div>
    </section>

    <section id="recommendPanel" class="panel hidden">
      <h2>2. 추천 결과 선택</h2>
      <div id="results" class="results"></div>
    </section>

    <section id="previewPanel" class="panel hidden">
      <h2>3. 선택 옵션과 다른 부분</h2>
      <ul id="diffList" class="diff"></ul>
      <div id="promptBox" class="prompt"></div>
      <button id="generateButton" class="primary" type="button">AI로 다른 부분만 수정하기</button>
      <div id="generateStatus" class="status">실제 이미지 수정은 이 버튼을 눌렀을 때만 실행됩니다.</div>
    </section>

    <section id="comparePanel" class="panel hidden">
      <h2>4. 기존 추천 vs AI 수정</h2>
      <div class="compare">
        <figure>
          <img id="baseImage" alt="기존 추천 이미지">
          <figcaption>기존 추천</figcaption>
        </figure>
        <figure>
          <img id="generatedImage" alt="AI 수정 이미지">
          <figcaption>AI 수정 결과</figcaption>
        </figure>
      </div>
      <div class="note">이 결과는 생성된 예시 이미지입니다. 실제 서비스에서는 사용자가 승인하거나 다시 생성할 수 있게 두는 흐름이 적합합니다.</div>
    </section>
  </main>

  <script>
    const labelMap = {
      shape: "모양",
      dominant_color: "대표 색상",
      visual_style: "스타일",
      lettering_type: "레터링",
      character_type: "캐릭터"
    };
    const optionData = {
      dominant_color: ["핑크", "화이트", "블루", "옐로우", "퍼플", "그린", "브라운", "블랙"],
      visual_style: ["러블리", "심플", "캐릭터", "레터링중심", "화려함"],
      character_type: ["없음", "토끼", "개", "고양이", "곰", "사람", "기타캐릭터"],
      lettering_type: ["없음", "중앙레터링", "꽉찬레터링", "무지개레터링"],
      shape: ["원형", "하트", "사각"]
    };
    let selectedResult = null;
    let previewData = null;

    function renderFilters() {
      const root = document.getElementById("filters");
      root.innerHTML = "";
      Object.entries(optionData).forEach(([key, values]) => {
        const group = document.createElement("div");
        group.className = "group";
        group.innerHTML = `<div class="group-title">${labelMap[key]}</div>`;
        const chips = document.createElement("div");
        chips.className = "chips";
        values.forEach((value) => {
          const label = document.createElement("label");
          label.className = "chip";
          label.innerHTML = `<input type="checkbox" name="${key}" value="${value}">${value}`;
          chips.append(label);
        });
        group.append(chips);
        root.append(group);
      });
      const defaults = [
        ["dominant_color", "블루"],
        ["visual_style", "러블리"],
        ["character_type", "토끼"],
        ["lettering_type", "중앙레터링"]
      ];
      defaults.forEach(([key, value]) => {
        const input = document.querySelector(`input[name="${key}"][value="${value}"]`);
        if (input) input.checked = true;
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
      return Object.entries(tags || {})
        .map(([key, values]) => `${labelMap[key] || key}: ${values.join(", ")}`)
        .join(" · ");
    }

    function imageUrl(path) {
      return path || "";
    }

    function thumbUrl(path) {
      const fileName = path.split("/").pop();
      const stem = fileName.replace(/\\.[^.]+$/, "");
      return `/static/thumbs/crops/${encodeURIComponent(stem)}.webp`;
    }

    async function recommend() {
      const button = document.getElementById("recommendButton");
      const status = document.getElementById("recommendStatus");
      button.disabled = true;
      status.textContent = "추천 결과를 불러오는 중입니다.";
      selectedResult = null;
      previewData = null;
      document.getElementById("recommendPanel").classList.add("hidden");
      document.getElementById("previewPanel").classList.add("hidden");
      document.getElementById("comparePanel").classList.add("hidden");
      try {
        const response = await fetch("/recommend", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({ tags: selectedTags(), limit: 6 })
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        renderResults(data.results || []);
        status.textContent = `${data.results.length}개 추천 결과를 찾았습니다.`;
        document.getElementById("recommendPanel").classList.remove("hidden");
      } catch (error) {
        status.textContent = `추천 실패: ${error.message}`;
      } finally {
        button.disabled = false;
      }
    }

    function renderResults(results) {
      const root = document.getElementById("results");
      root.innerHTML = "";
      results.forEach((item, index) => {
        const card = document.createElement("button");
        card.type = "button";
        card.className = "card";
        card.innerHTML = `
          <img src="${thumbUrl(item.crop_image_url)}" alt="추천 케이크 ${index + 1}" loading="lazy">
          <div class="score">점수 ${item.score}</div>
          <div class="small">매칭: ${tagText(item.matched_tags)}</div>
        `;
        card.addEventListener("click", async () => {
          document.querySelectorAll(".card").forEach((node) => node.classList.remove("active"));
          card.classList.add("active");
          selectedResult = item;
          await loadPreview();
        });
        root.append(card);
      });
    }

    async function loadPreview() {
      const panel = document.getElementById("previewPanel");
      const diffList = document.getElementById("diffList");
      const promptBox = document.getElementById("promptBox");
      panel.classList.remove("hidden");
      diffList.innerHTML = "<li>변경사항을 계산하는 중입니다.</li>";
      promptBox.textContent = "";
      document.getElementById("comparePanel").classList.add("hidden");
      const response = await fetch("/customize/preview", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          cake_crop_id: selectedResult.cake_crop_id,
          target_tags: selectedTags()
        })
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      previewData = await response.json();
      diffList.innerHTML = "";
      Object.entries(previewData.diff_tags).forEach(([key, diff]) => {
        const item = document.createElement("li");
        item.innerHTML = `<span>${labelMap[key] || key}</span>${diff.from.join(" · ") || "없음"} → ${diff.to.join(" · ") || "없음"}`;
        diffList.append(item);
      });
      if (!diffList.children.length) {
        diffList.innerHTML = "<li>추천 이미지와 선택 옵션의 주요 태그 차이가 없습니다.</li>";
      }
      promptBox.textContent = previewData.prompt;
    }

    async function generate() {
      if (!selectedResult) return;
      const button = document.getElementById("generateButton");
      const status = document.getElementById("generateStatus");
      button.disabled = true;
      status.textContent = "AI 이미지 수정을 요청 중입니다. 30초 이상 걸릴 수 있습니다.";
      try {
        const response = await fetch("/customize/generate", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            cake_crop_id: selectedResult.cake_crop_id,
            target_tags: selectedTags(),
            model: "gpt-image-1-mini"
          })
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        if (data.status !== "ok") throw new Error(data.error || "AI 수정 실패");
        document.getElementById("baseImage").src = imageUrl(data.base_crop_image_url);
        document.getElementById("generatedImage").src = imageUrl(data.generated_image_url);
        document.getElementById("comparePanel").classList.remove("hidden");
        status.textContent = "AI 수정 결과가 생성되었습니다.";
      } catch (error) {
        status.textContent = `AI 수정 실패: ${error.message}`;
      } finally {
        button.disabled = false;
      }
    }

    document.getElementById("recommendButton").addEventListener("click", recommend);
    document.getElementById("generateButton").addEventListener("click", generate);
    renderFilters();
  </script>
</body>
</html>
        """
    )
