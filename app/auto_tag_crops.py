import csv
import shutil
import argparse
from datetime import datetime
from pathlib import Path

from app.ai_tagging import TAG_CHOICES, auto_tag_crop
from app.database import Base, SessionLocal, engine
from app.models import CakeCrop, CakeCropReview


BASE_DIR = Path(__file__).resolve().parent.parent
CROPS_DIR = BASE_DIR / "data" / "crops"
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


def join_values(values) -> str:
    if isinstance(values, list):
        return "|".join(str(value) for value in values)
    return str(values or "")


def backup_existing_draft() -> None:
    if not DRAFT_PATH.exists():
        return
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = DRAFT_PATH.with_name(f"crop_tags_draft.{timestamp}.bak.csv")
    shutil.copy2(DRAFT_PATH, backup_path)
    print(f"Backed up existing draft to {backup_path}")


def read_existing_rows() -> list[dict[str, str]]:
    if not DRAFT_PATH.exists():
        return []
    with DRAFT_PATH.open("r", encoding="utf-8-sig", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def auto_tag_crops(
    approved_only: bool = False,
    limit: int | None = None,
    resume: bool = False,
) -> None:
    Base.metadata.create_all(bind=engine)
    DRAFT_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing_rows = read_existing_rows() if resume else []
    existing_crop_ids = {
        int(row["cake_crop_id"])
        for row in existing_rows
        if row.get("cake_crop_id")
    }
    backup_existing_draft()

    db = SessionLocal()
    processed = 0
    failures = []

    try:
        crops_query = db.query(CakeCrop).order_by(CakeCrop.cake_crop_id)
        if approved_only:
            crops_query = (
                crops_query.join(CakeCropReview)
                .filter(CakeCropReview.status == "approved")
            )
        if limit is not None:
            crops_query = crops_query.limit(limit)
        crops = [
            crop
            for crop in crops_query.all()
            if crop.cake_crop_id not in existing_crop_ids
        ]
        with DRAFT_PATH.open("w", encoding="utf-8-sig", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=FIELDNAMES)
            writer.writeheader()
            for row in existing_rows:
                writer.writerow(row)

            total = len(crops)
            for index, crop in enumerate(crops, start=1):
                crop_path = CROPS_DIR / crop.crop_file_name
                if not crop_path.exists():
                    failures.append(f"{crop.crop_file_name}: file not found")
                    continue

                processed += 1
                print(f"tagging {index}/{total}: {crop.crop_file_name}", flush=True)
                try:
                    tags = auto_tag_crop(str(crop_path))
                except Exception as exc:
                    failures.append(f"{crop.crop_file_name}: {exc}")
                    tags = {key: ["판단불가"] for key in TAG_CHOICES}
                    tags["memo"] = "자동 태깅 실패"

                row = {
                    "cake_crop_id": crop.cake_crop_id,
                    "crop_file_name": crop.crop_file_name,
                    "memo": tags.get("memo", ""),
                }
                for tag_key in TAG_CHOICES:
                    row[tag_key] = join_values(tags.get(tag_key, ["판단불가"]))
                writer.writerow(row)
                csv_file.flush()
    finally:
        db.close()

    print(f"Processed crops: {processed}")
    print(f"Failures: {failures}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--approved-only", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    auto_tag_crops(
        approved_only=args.approved_only,
        limit=args.limit,
        resume=args.resume,
    )
