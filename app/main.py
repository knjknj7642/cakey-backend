import os
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.customize import router as customize_router
from app.demo import router as demo_router
from app.full_mvp import router as full_mvp_router
from app.models import CakeCrop, CakeCropReview, CropTag
from app.recommender import recommend_cakes
from app.review import router as review_router
from app.survey import router as survey_router
from app.tag_review import router as tag_review_router
from app.schemas import RecommendRequest, RecommendResponse


Base.metadata.create_all(bind=engine)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
for static_dir in [
    DATA_DIR / "originals",
    DATA_DIR / "crops",
    DATA_DIR / "thumbs" / "crops",
    DATA_DIR / "generated",
    DATA_DIR / "reference",
]:
    static_dir.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Cake Recommendation API",
    description="Tag-based custom cake image recommendation backend.",
    version="0.1.0",
)

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:5173,http://127.0.0.1:5173,"
        "https://knjknj7642.github.io",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static/originals", StaticFiles(directory=DATA_DIR / "originals"), name="originals")
app.mount("/static/crops", StaticFiles(directory=DATA_DIR / "crops"), name="crops")
app.mount("/static/thumbs/crops", StaticFiles(directory=DATA_DIR / "thumbs" / "crops"), name="crop_thumbs")
app.mount("/static/generated", StaticFiles(directory=DATA_DIR / "generated"), name="generated")
app.mount("/static/reference", StaticFiles(directory=DATA_DIR / "reference"), name="reference")
app.include_router(customize_router)
app.include_router(review_router)
app.include_router(tag_review_router)
app.include_router(demo_router)
app.include_router(full_mvp_router)
app.include_router(survey_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/tags")
def get_tags(db: Session = Depends(get_db)) -> dict[str, list[str]]:
    rows = (
        db.query(CropTag.tag_key, CropTag.tag_value)
        .join(CakeCrop)
        .join(CakeCropReview)
        .filter(CakeCropReview.status == "approved")
        .distinct()
        .order_by(CropTag.tag_key, CropTag.tag_value)
        .all()
    )

    tags: dict[str, list[str]] = {}
    for tag_key, tag_value in rows:
        tags.setdefault(tag_key, []).append(tag_value)
    return tags


@app.post("/recommend", response_model=RecommendResponse)
def recommend(
    request: RecommendRequest,
    db: Session = Depends(get_db),
) -> RecommendResponse:
    results = recommend_cakes(db, request.tags, request.limit)
    return RecommendResponse(results=results)
