# Cake Recommendation API Spec

## 개요

이 API는 주문제작 케이크 추천용 FastAPI 백엔드입니다. 프론트엔드는 사용자가 고른 케이크 옵션 태그를 백엔드로 보내고, 백엔드는 해당 태그와 가장 유사한 승인된 cake crop 이미지를 반환합니다.

추천 단위는 원본 이미지가 아니라 `cake_crop_id` 기준의 crop 이미지입니다.

## Base URL

로컬 개발:

```text
http://127.0.0.1:8000
```

프론트 개발 서버 예시:

```text
http://localhost:3000
http://localhost:5173
```

프론트가 다른 origin에서 실행되면 백엔드 `.env`의 `CORS_ORIGINS`에 해당 주소를 추가해야 합니다.

## Static Image URL

응답의 이미지 URL은 상대 경로입니다.

```text
/static/crops/{file_name}
/static/originals/{file_name}
```

프론트에서는 API base URL을 붙여 사용합니다.

예:

```ts
const imageUrl = `${API_BASE_URL}${result.crop_image_url}`;
```

## GET /health

서버 상태 확인용 API입니다.

### Response

```json
{
  "status": "ok"
}
```

## GET /tags

현재 추천에 사용할 수 있는 태그 선택지를 반환합니다. 프론트는 이 응답을 기반으로 옵션 UI를 렌더링할 수 있습니다.

현재 백엔드는 사람이 승인한 crop과 DB에 저장된 태그를 기준으로 선택지를 반환합니다.

### Response Example

```json
{
  "shape": ["사각", "원형", "하트"],
  "dominant_color": ["그린", "믹스", "브라운", "블랙", "블루", "옐로우", "퍼플", "핑크", "화이트"],
  "visual_style": ["러블리", "레터링중심", "심플", "캐릭터", "화려함"],
  "character_type": ["개", "고양이", "곰", "기타동물", "기타캐릭터", "사람", "없음", "이모티콘", "토끼"]
}
```

### 주요 tag_key

| tag_key | 의미 |
| --- | --- |
| `shape` | 케이크 모양 |
| `dominant_color` | 대표 색상 |
| `visual_style` | 시각 스타일 |
| `character_type` | 캐릭터 종류 |
| `lettering_type` | 레터링 형태 |
| `border_type` | 테두리 장식 |
| `cream_decoration` | 크림 장식 |
| `topping_decoration` | 토핑 장식 |
| `board_lettering` | 케이크 판 위 글씨 여부 |
| `text_presence` | 케이크 위 문구 여부 |

## POST /recommend

사용자가 선택한 태그와 유사한 cake crop 이미지를 추천합니다.

### Request Body

```json
{
  "tags": {
    "dominant_color": ["핑크"],
    "visual_style": ["러블리"],
    "character_type": ["개"],
    "lettering_type": ["중앙레터링"]
  },
  "limit": 12
}
```

### Request Fields

| field | type | required | description |
| --- | --- | --- | --- |
| `tags` | object | yes | tag_key별 선택한 tag_value 배열 |
| `limit` | number | no | 반환 개수. 기본 5, 최소 1, 최대 100 |

여러 값을 선택할 수 있습니다.

```json
{
  "tags": {
    "dominant_color": ["핑크", "화이트"],
    "shape": ["하트", "원형"]
  },
  "limit": 12
}
```

### Response Body

```json
{
  "results": [
    {
      "cake_crop_id": 10,
      "original_image_id": 34,
      "shop_name": "unknown",
      "crop_image_url": "/static/crops/_onyourday_1667820802_2966218341714537793_12861674625_cake_1.jpg",
      "original_image_url": "/static/originals/_onyourday_1667820802_2966218341714537793_12861674625.jpg",
      "score": 6,
      "matched_tags": {
        "dominant_color": ["핑크"],
        "visual_style": ["러블리"]
      },
      "all_tags": {
        "shape": ["하트"],
        "dominant_color": ["핑크"],
        "visual_style": ["러블리"],
        "lettering_type": ["중앙레터링"],
        "board_lettering": ["없음"],
        "border_type": ["없음"],
        "cream_decoration": ["없음"],
        "topping_decoration": ["진주"],
        "character_type": ["없음"],
        "text_presence": ["있음"]
      }
    }
  ]
}
```

### Response Fields

| field | type | description |
| --- | --- | --- |
| `cake_crop_id` | number | 추천 단위인 crop ID |
| `original_image_id` | number | 원본 이미지 ID |
| `shop_name` | string | 가게명. 없으면 `unknown` |
| `crop_image_url` | string | 프론트 카드에 주로 표시할 crop 이미지 |
| `original_image_url` | string | 상세 보기 등에 사용할 원본 이미지 |
| `score` | number | 태그 가중치 기반 추천 점수 |
| `matched_tags` | object | 요청 태그 중 실제 매칭된 태그 |
| `all_tags` | object | 해당 crop이 가진 전체 태그 |

## 추천 점수 기준

프론트 요청 태그와 crop 태그가 일치하면 아래 가중치를 더합니다. 같은 tag_key 안에서 여러 값이 있어도 하나 이상 일치하면 해당 tag_key 가중치를 한 번 더합니다.

| tag_key | weight |
| --- | ---: |
| `character_type` | 4 |
| `dominant_color` | 3 |
| `visual_style` | 3 |
| `border_type` | 2 |
| `lettering_type` | 2 |
| `cream_decoration` | 2 |
| `topping_decoration` | 1 |
| `shape` | 1 |
| `board_lettering` | 1 |
| `text_presence` | 1 |

`score`가 0인 이미지는 반환하지 않습니다.

## Frontend Flow

1. 앱 최초 진입 시 `GET /tags` 호출
2. 응답으로 옵션 UI 생성
3. 사용자가 옵션 선택
4. 선택된 값을 `POST /recommend`로 전송
5. 응답의 `results` 배열을 카드 형태로 렌더링
6. 카드 메인 이미지는 `crop_image_url` 사용
7. 상세 화면 또는 원본 보기에는 `original_image_url` 사용

## TypeScript 예시

```ts
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export type TagsResponse = Record<string, string[]>;

export type RecommendRequest = {
  tags: Record<string, string[]>;
  limit?: number;
};

export type RecommendResult = {
  cake_crop_id: number;
  original_image_id: number;
  shop_name: string;
  crop_image_url: string;
  original_image_url: string;
  score: number;
  matched_tags: Record<string, string[]>;
  all_tags: Record<string, string[]>;
};

export async function fetchTags(): Promise<TagsResponse> {
  const response = await fetch(`${API_BASE_URL}/tags`);
  if (!response.ok) throw new Error("Failed to fetch tags");
  return response.json();
}

export async function recommendCakes(
  body: RecommendRequest,
): Promise<RecommendResult[]> {
  const response = await fetch(`${API_BASE_URL}/recommend`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error("Failed to recommend cakes");
  const data = await response.json();
  return data.results;
}

export function imageUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}
```

## 빈 결과 처리

`results`가 빈 배열이면 프론트에서 아래처럼 처리하면 됩니다.

```text
선택한 조건과 일치하는 케이크가 없습니다.
조건을 줄이거나 다른 옵션을 선택해 주세요.
```

## 현재 제공되는 백엔드 데모

구매자용 MVP 데모:

```text
http://127.0.0.1:8000/demo
```

검수용 페이지:

```text
http://127.0.0.1:8000/review/crops
http://127.0.0.1:8000/review/tags
```
