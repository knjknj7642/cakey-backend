# Cake Recommendation Backend

주문제작 케이크 이미지 추천 API 백엔드 MVP입니다. 프론트엔드에서 선택한 케이크 태그를 받아 SQLite에 저장된 crop 이미지 태그와 비교하고, 가장 유사한 케이크 crop 이미지와 원본 이미지 URL을 함께 반환합니다.

추천과 태그 추출의 기준은 원본 이미지가 아니라 케이크 crop 이미지입니다. 한 원본 사진에 케이크가 여러 개 있을 수 있으므로 DB와 추천 결과도 crop 단위로 관리합니다. 가게 정보는 파일명이 아니라 `original_images.shop_name` 메타데이터로 관리합니다.

## 폴더 구조

```text
app/
  main.py
  database.py
  models.py
  schemas.py
  recommender.py
  seed.py
  import_images.py
  ai_crop.py
  auto_crop.py
  ai_tagging.py
  auto_tag_crops.py
  import_tags.py
data/
  originals/
  crops/
  metadata/
    original_images.csv
    cake_crops.csv
    crop_tags.csv
    crop_tags_draft.csv
static/
  originals/
  crops/
requirements.txt
.env.example
README.md
```

`/static/originals/{file_name}` URL은 실제 `data/originals` 파일을 제공하고, `/static/crops/{file_name}` URL은 실제 `data/crops` 파일을 제공합니다.

## 설치

```bash
pip install -r requirements.txt
```

OpenAI Vision API를 쓰려면 `.env`를 만들고 API 키를 설정합니다.

```bash
OPENAI_API_KEY=your_api_key_here
```

API 키가 없으면 import와 FastAPI 실행은 정상 동작하지만, 자동 crop은 탐지 결과 없이 skip되고 자동 태깅은 `판단불가`로 draft를 생성합니다. 현재 OpenAI SDK의 Chat Completions vision 입력을 사용하며, 모델은 기본 `gpt-4.1-mini`입니다. 필요하면 `.env`에 `OPENAI_VISION_MODEL`을 추가해 바꿀 수 있습니다.

## 샘플 DB Seed

샘플 CSV로 빠르게 추천 API를 테스트하려면 아래 명령을 실행합니다.

```bash
python -m app.seed
```

## 실제 이미지 등록 순서

권장 실행 순서:

```bash
pip install -r requirements.txt
python -m app.import_images
python -m app.auto_crop
python -m app.auto_tag_crops
# 사람이 data/metadata/crop_tags_draft.csv 수정
python -m app.import_tags
uvicorn app.main:app --reload
```

## 원본 이미지 메타데이터

원본 이미지는 `data/originals`에 넣습니다. 지원 확장자는 `jpg`, `jpeg`, `png`, `webp`입니다.

`data/metadata/original_images.csv`는 아래 컬럼을 사용합니다.

```csv
file_name,shop_name,source_url,memo
IMG_3912.jpg,케이크샵 이름,https://example.com/source,메모
```

`python -m app.import_images`는 `data/originals`를 스캔해 `original_images` 테이블에 등록합니다. 이미 등록된 `file_name`은 중복 등록하지 않습니다. CSV가 없거나 `shop_name`이 비어 있으면 `unknown`으로 저장합니다.

## 자동 Crop

```bash
python -m app.auto_crop
```

`original_images` 테이블에 등록된 원본 이미지를 읽고, 실제 파일은 `data/originals/{file_name}`에서 찾습니다. OpenAI Vision API로 케이크 본체 bounding box를 추정한 뒤 PIL로 crop하고 `data/crops`에 저장합니다.

crop 파일명은 원본 파일 stem 기준입니다.

```text
IMG_3912.jpg -> IMG_3912_cake_1.jpg
```

DB의 `cake_crops.crop_file_path`는 `/static/crops/{file_name}` 형태로 저장합니다.

## Fallback Crop

Vision API가 실패하거나 box가 없을 때 임시로 중앙 70% crop을 만들려면 옵션을 사용합니다.

```bash
python -m app.auto_crop --fallback-center
```

fallback crop의 `detection_confidence`는 `0.1`이며, 로그에 `source=fallback`으로 출력됩니다.

## 자동 태깅

```bash
python -m app.auto_tag_crops
```

`cake_crops` 테이블에 등록된 crop 이미지를 읽고, 실제 파일은 `data/crops/{crop_file_name}`에서 찾습니다. OpenAI Vision API로 서비스 태그 체계에 맞는 예상 태그를 생성해 `data/metadata/crop_tags_draft.csv`에 저장합니다.

여러 값은 `|`로 연결됩니다.

```csv
cake_crop_id,crop_file_name,shape,dominant_color,visual_style,lettering_type,board_lettering,border_type,cream_decoration,topping_decoration,character_type,text_presence,memo
1,IMG_3912_cake_1.jpg,원형,핑크|화이트,러블리,중앙레터링,없음,크림테두리,하트,진주,개,있음,핑크와 화이트 중심의 강아지 캐릭터 케이크
```

기존 `crop_tags_draft.csv`가 있으면 덮어쓰기 전에 timestamp가 붙은 `.bak.csv` 백업 파일을 만듭니다.

## 사람이 태그 수정

`data/metadata/crop_tags_draft.csv`를 열어 잘못된 태그를 수정합니다. 태그 값은 코드의 선택지 안에서만 사용해야 합니다. 값이 여러 개면 `핑크|화이트`처럼 `|`로 연결합니다.

`판단불가`와 빈 값은 DB 반영 시 저장하지 않습니다.

## 수정 태그 DB 반영

```bash
python -m app.import_tags
```

`crop_tags_draft.csv`를 읽어 `crop_tags` 테이블에 저장합니다. 같은 `cake_crop_id`의 기존 태그는 삭제한 뒤 다시 저장합니다. 저장되는 태그의 `confidence`는 `1.0`, `source_type`은 `reviewed`입니다.

## 서버 실행

```bash
uvicorn app.main:app --reload
```

서버 기본 주소는 `http://127.0.0.1:8000`입니다.

## API 테스트

### GET /health

```bash
curl http://127.0.0.1:8000/health
```

### GET /tags

```bash
curl http://127.0.0.1:8000/tags
```

### POST /recommend

```bash
curl -X POST http://127.0.0.1:8000/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "tags": {
      "dominant_color": ["핑크"],
      "visual_style": ["러블리"],
      "character_type": ["개"],
      "lettering_type": ["중앙레터링"]
    },
    "limit": 5
  }'
```

응답에는 `crop_image_url`, `original_image_url`, `shop_name`, `score`, `matched_tags`, `all_tags`가 포함됩니다.

## 추천 점수 기준

프론트 요청 태그와 crop 태그가 일치하면 tag_key별 가중치를 한 번 더합니다. 같은 tag_key에 여러 값이 있어도 하나 이상 일치하면 해당 가중치를 한 번만 더합니다. 점수가 0인 이미지는 제외합니다.

```text
character_type: 4
dominant_color: 3
visual_style: 3
border_type: 2
lettering_type: 2
cream_decoration: 2
topping_decoration: 1
shape: 1
board_lettering: 1
text_presence: 1
```
