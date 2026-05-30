import csv
from pathlib import Path

from app.database import Base, SessionLocal, engine
from app.models import OriginalImage


BASE_DIR = Path(__file__).resolve().parent.parent
ORIGINALS_DIR = BASE_DIR / "data" / "originals"
METADATA_PATH = BASE_DIR / "data" / "metadata" / "original_images.csv"
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def load_original_metadata() -> dict[str, dict[str, str]]:
    if not METADATA_PATH.exists():
        return {}

    with METADATA_PATH.open("r", encoding="utf-8-sig", newline="") as csv_file:
        rows = csv.DictReader(csv_file)
        return {
            row["file_name"]: row
            for row in rows
            if row.get("file_name")
        }


def iter_original_files() -> list[Path]:
    if not ORIGINALS_DIR.exists():
        return []
    return sorted(
        path
        for path in ORIGINALS_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def import_images() -> None:
    Base.metadata.create_all(bind=engine)
    metadata = load_original_metadata()
    db = SessionLocal()

    created = 0
    skipped = []
    try:
        existing_file_names = {
            row[0]
            for row in db.query(OriginalImage.file_name).all()
        }

        for image_path in iter_original_files():
            if image_path.name in existing_file_names:
                skipped.append(image_path.name)
                continue

            row = metadata.get(image_path.name, {})
            shop_name = row.get("shop_name") or "unknown"
            source_url = row.get("source_url") or None

            db.add(
                OriginalImage(
                    shop_name=shop_name,
                    file_name=image_path.name,
                    file_path=f"/static/originals/{image_path.name}",
                    source_url=source_url,
                )
            )
            created += 1

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(f"Processed: {created + len(skipped)}")
    print(f"Imported: {created}")
    print(f"Skipped duplicates: {skipped}")


if __name__ == "__main__":
    import_images()
