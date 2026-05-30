# Windows Handoff

## 목표

1. Windows 데스크탑의 GTX 3060 Ti로 케이크 crop detector 미니 모델 학습
2. 승인된 crop과 태그 데이터를 기반으로 태그 분류 모델 학습 가능성 검토
3. 현재 진행 내용을 바탕으로 11주차 기술과창업 주간보고서 작성

## 현재 프로젝트 상태

- FastAPI 기반 케이크 이미지 추천 API MVP 구현
- 원본 이미지 저장 위치: `data/originals`
- crop 이미지 저장 위치: `data/crops`
- SQLite DB: `cake_recommendation.db`
- crop 검수 페이지: `/review/crops`
- 태그 검수 페이지: `/review/tags`
- 구매자용 추천 MVP 페이지: `/demo`

## 현재 데이터 상태

- 실제 Vision crop 중 사람이 검수한 결과:
  - `approved`: 263개
  - `partial`: 127개
  - `rejected`: 21개
  - `duplicate`: 1개
- 승인 crop 263개에 대해 AI 태그 초안 생성 완료
- 태그 초안 CSV: `data/metadata/crop_tags_draft.csv`
- 태그는 `python -m app.import_tags`로 DB `crop_tags`에 반영 가능

## Mac에서 진행된 주요 기능

- 이미지 import: `python -m app.import_images`
- fallback crop 생성 및 Vision crop 교체
- crop 검수 DB 테이블 추가: `cake_crop_reviews`
- OpenAI 기반 태그 초안 생성
- 태그 검수 화면 추가
- 승인 crop만 추천에 사용하도록 추천 로직 제한
- 구매자용 옵션 선택 데모 `/demo` 추가

## Windows에서 먼저 확인할 것

```powershell
python --version
nvidia-smi
```

NVIDIA 드라이버가 정상이고 `nvidia-smi`에서 GTX 3060 Ti가 보여야 한다.

## Windows 설치 예상 명령

```powershell
pip install -r requirements.txt
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install ultralytics
```

## 서버 실행

```powershell
uvicorn app.main:app --reload
```

브라우저에서 확인:

- API 상태: `http://127.0.0.1:8000/health`
- 구매자 데모: `http://127.0.0.1:8000/demo`
- crop 검수: `http://127.0.0.1:8000/review/crops`
- 태그 검수: `http://127.0.0.1:8000/review/tags`

## 다음 구현 후보

1. `approved` crop과 bbox를 YOLO 학습 포맷으로 export
2. `data/originals` + 승인 bbox로 detector 학습 데이터 구성
3. YOLO nano 또는 small 모델 fine-tuning
4. 학습 결과를 원본 이미지에 적용해 자동 crop 성능 확인
5. 승인 crop + 검수 태그를 image classification/multi-label 학습 포맷으로 export
6. 11주차 보고서 작성

## 주의

- `.env`는 zip에 포함하지 않는다.
- API key는 새 환경에서 다시 설정한다.
- 현재 crop/태그 데이터는 실험용 MVP 데이터이며, 학습 전 품질 검수 결과를 기준으로 사용한다.
