import csv
from pathlib import Path

from app.ai_tagging import TAG_CHOICES
from app.database import Base, SessionLocal, engine
from app.models import CropTag


BASE_DIR = Path(__file__).resolve().parent.parent
DRAFT_PATH = BASE_DIR / "data" / "metadata" / "crop_tags_draft.csv"


def split_values(value: str | None) -> list[str]:
    if not value:
        return []
    return [
        item.strip()
        for item in value.split("|")
        if item.strip() and item.strip() != "판단불가"
    ]


def import_tags() -> None:
    if not DRAFT_PATH.exists():
        raise FileNotFoundError(f"{DRAFT_PATH} does not exist")

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    imported = 0

    try:
        with DRAFT_PATH.open("r", encoding="utf-8-sig", newline="") as csv_file:
            rows = list(csv.DictReader(csv_file))

        crop_ids = [int(row["cake_crop_id"]) for row in rows if row.get("cake_crop_id")]
        if crop_ids:
            db.query(CropTag).filter(CropTag.cake_crop_id.in_(crop_ids)).delete(
                synchronize_session=False
            )

        for row in rows:
            cake_crop_id = int(row["cake_crop_id"])
            for tag_key, choices in TAG_CHOICES.items():
                for tag_value in split_values(row.get(tag_key)):
                    if tag_value not in choices:
                        print(f"skipped invalid tag {tag_key}={tag_value} for crop {cake_crop_id}")
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
                    imported += 1

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(f"Imported reviewed tags: {imported}")


if __name__ == "__main__":
    import_tags()
