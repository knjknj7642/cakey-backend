import csv
from datetime import datetime
from pathlib import Path

from app.database import Base, SessionLocal, engine
from app.models import CakeCrop, CropTag, OriginalImage


BASE_DIR = Path(__file__).resolve().parent.parent
METADATA_DIR = BASE_DIR / "data" / "metadata"


def parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.utcnow()
    return datetime.fromisoformat(value)


def read_csv(file_name: str) -> list[dict[str, str]]:
    path = METADATA_DIR / file_name
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def reset_tables() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def seed_original_images(db) -> None:
    rows = read_csv("original_images.csv")
    for index, row in enumerate(rows, start=1):
        file_name = row["file_name"]
        db.add(
            OriginalImage(
                original_image_id=int(row.get("original_image_id") or index),
                shop_name=row.get("shop_name") or "unknown",
                file_name=file_name,
                file_path=row.get("file_path") or f"/static/originals/{file_name}",
                source_url=row.get("source_url") or None,
                created_at=parse_datetime(row.get("created_at")),
            )
        )


def seed_cake_crops(db) -> None:
    rows = read_csv("cake_crops.csv")
    for row in rows:
        db.add(
            CakeCrop(
                cake_crop_id=int(row["cake_crop_id"]),
                original_image_id=int(row["original_image_id"]),
                crop_file_name=row["crop_file_name"],
                crop_file_path=row["crop_file_path"],
                x_min=int(row["x_min"]),
                y_min=int(row["y_min"]),
                x_max=int(row["x_max"]),
                y_max=int(row["y_max"]),
                detection_confidence=float(row["detection_confidence"]),
                created_at=parse_datetime(row.get("created_at")),
            )
        )


def seed_crop_tags(db) -> None:
    rows = read_csv("crop_tags.csv")
    for row in rows:
        db.add(
            CropTag(
                crop_tag_id=int(row["crop_tag_id"]),
                cake_crop_id=int(row["cake_crop_id"]),
                tag_key=row["tag_key"],
                tag_value=row["tag_value"],
                confidence=float(row["confidence"]),
                source_type=row["source_type"],
                created_at=parse_datetime(row.get("created_at")),
            )
        )


def seed() -> None:
    reset_tables()
    db = SessionLocal()
    try:
        seed_original_images(db)
        seed_cake_crops(db)
        seed_crop_tags(db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
    print("Seed completed.")
