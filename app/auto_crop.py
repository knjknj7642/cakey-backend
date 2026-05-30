import argparse
import time
from pathlib import Path

from PIL import Image

from app.ai_crop import detect_cake_boxes_with_vision_api
from app.database import Base, SessionLocal, engine
from app.models import CakeCrop, OriginalImage


BASE_DIR = Path(__file__).resolve().parent.parent
ORIGINALS_DIR = BASE_DIR / "data" / "originals"
CROPS_DIR = BASE_DIR / "data" / "crops"
VISION_BOX_PADDING_RATIO = 0.08


def is_valid_box(box: dict, width: int, height: int) -> bool:
    try:
        x_min = int(box["x_min"])
        y_min = int(box["y_min"])
        x_max = int(box["x_max"])
        y_max = int(box["y_max"])
    except (KeyError, TypeError, ValueError):
        return False

    if x_min < 0 or y_min < 0 or x_max > width or y_max > height:
        return False
    if x_max <= x_min or y_max <= y_min:
        return False
    if x_max - x_min < 10 or y_max - y_min < 10:
        return False
    return True


def center_fallback_box(width: int, height: int) -> dict:
    margin_x = int(width * 0.15)
    margin_y = int(height * 0.15)
    return {
        "x_min": margin_x,
        "y_min": margin_y,
        "x_max": width - margin_x,
        "y_max": height - margin_y,
        "confidence": 0.1,
        "reason": "fallback center crop",
    }


def expand_box(box: dict, width: int, height: int, padding_ratio: float = VISION_BOX_PADDING_RATIO) -> dict:
    box_width = int(box["x_max"]) - int(box["x_min"])
    box_height = int(box["y_max"]) - int(box["y_min"])
    padding_x = int(box_width * padding_ratio)
    padding_y = int(box_height * padding_ratio)

    return {
        **box,
        "x_min": max(0, int(box["x_min"]) - padding_x),
        "y_min": max(0, int(box["y_min"]) - padding_y),
        "x_max": min(width, int(box["x_max"]) + padding_x),
        "y_max": min(height, int(box["y_max"]) + padding_y),
    }


def box_area(box: dict) -> int:
    return max(0, int(box["x_max"]) - int(box["x_min"])) * max(
        0, int(box["y_max"]) - int(box["y_min"])
    )


def intersection_area(a: dict, b: dict) -> int:
    x_min = max(int(a["x_min"]), int(b["x_min"]))
    y_min = max(int(a["y_min"]), int(b["y_min"]))
    x_max = min(int(a["x_max"]), int(b["x_max"]))
    y_max = min(int(a["y_max"]), int(b["y_max"]))
    return max(0, x_max - x_min) * max(0, y_max - y_min)


def iou(a: dict, b: dict) -> float:
    intersection = intersection_area(a, b)
    if intersection == 0:
        return 0.0
    union = box_area(a) + box_area(b) - intersection
    return intersection / union if union else 0.0


def smaller_box_coverage(a: dict, b: dict) -> float:
    smaller_area = min(box_area(a), box_area(b))
    return intersection_area(a, b) / smaller_area if smaller_area else 0.0


def box_center_inside(inner: dict, outer: dict) -> bool:
    center_x = (int(inner["x_min"]) + int(inner["x_max"])) / 2
    center_y = (int(inner["y_min"]) + int(inner["y_max"])) / 2
    return (
        int(outer["x_min"]) <= center_x <= int(outer["x_max"])
        and int(outer["y_min"]) <= center_y <= int(outer["y_max"])
    )


def filter_vision_boxes(boxes: list[dict]) -> list[dict]:
    # Keep the most complete box when the model returns overlapping partial duplicates.
    ordered = sorted(
        boxes,
        key=lambda box: (float(box.get("confidence", 0.0)), box_area(box)),
        reverse=True,
    )
    deduped = []
    for box in ordered:
        if any(iou(box, kept) >= 0.5 or smaller_box_coverage(box, kept) >= 0.8 for kept in deduped):
            continue
        deduped.append(box)

    # If the model returns both individual cakes and one large union box, drop the union box.
    filtered = []
    for box in deduped:
        contained = [
            other
            for other in deduped
            if other is not box
            and box_center_inside(other, box)
            and box_area(other) < box_area(box) * 0.7
        ]
        if len(contained) >= 2:
            continue
        filtered.append(box)
    return filtered


def save_crop(image: Image.Image, box: dict, output_path: Path) -> None:
    crop = image.crop((box["x_min"], box["y_min"], box["x_max"], box["y_max"]))
    crop.convert("RGB").save(output_path, format="JPEG", quality=95)


def auto_crop(fallback_center: bool = False) -> None:
    Base.metadata.create_all(bind=engine)
    CROPS_DIR.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    processed = 0
    created = 0
    skipped = []

    try:
        existing_db_crops = db.query(CakeCrop).all()
        existing_db_crop_file_names = {crop.crop_file_name for crop in existing_db_crops}
        existing_crop_file_names = set(existing_db_crop_file_names)
        existing_crop_file_names.update(
            path.name
            for path in CROPS_DIR.iterdir()
            if path.is_file()
        )
        existing_db_crop_stems = {
            crop.crop_file_name.rsplit("_cake_", 1)[0]
            for crop in existing_db_crops
            if "_cake_" in crop.crop_file_name
        }
        originals = db.query(OriginalImage).order_by(OriginalImage.original_image_id).all()

        for original in originals:
            processed += 1
            original_path = ORIGINALS_DIR / original.file_name
            if original_path.stem in existing_db_crop_stems:
                print(f"skipped {original.file_name}: crop already exists")
                continue

            if not original_path.exists():
                skipped.append(f"{original.file_name}: file not found")
                print(f"skipped {original.file_name}: file not found")
                continue

            with Image.open(original_path) as image:
                width, height = image.size
                if fallback_center:
                    boxes = [center_fallback_box(width, height)]
                    source = "fallback"
                    print(f"fallback crop used for {original.file_name}")
                else:
                    boxes = filter_vision_boxes(detect_cake_boxes_with_vision_api(str(original_path)))
                    source = "vision"

                if not boxes:
                    skipped.append(f"{original.file_name}: no boxes")
                    print(f"skipped {original.file_name}: no boxes")
                    continue

                for index, box in enumerate(boxes, start=1):
                    if source == "vision":
                        box = expand_box(box, width, height)
                    while True:
                        crop_file_name = f"{original_path.stem}_cake_{index}.jpg"
                        if crop_file_name not in existing_crop_file_names:
                            break
                        index += 1

                    if not is_valid_box(box, width, height):
                        skipped.append(f"{original.file_name}: invalid box {index}")
                        print(f"skipped {original.file_name}: invalid box {index}")
                        continue

                    output_path = CROPS_DIR / crop_file_name
                    save_crop(image, box, output_path)
                    db.add(
                        CakeCrop(
                            original_image_id=original.original_image_id,
                            crop_file_name=crop_file_name,
                            crop_file_path=f"/static/crops/{crop_file_name}",
                            x_min=int(box["x_min"]),
                            y_min=int(box["y_min"]),
                            x_max=int(box["x_max"]),
                            y_max=int(box["y_max"]),
                            detection_confidence=float(box.get("confidence", 0.0)),
                        )
                    )
                    existing_crop_file_names.add(crop_file_name)
                    existing_db_crop_stems.add(original_path.stem)
                    created += 1
                    print(f"created {crop_file_name} source={source}")

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(f"Processed originals: {processed}")
    print(f"Created crops: {created}")
    print(f"Skipped: {skipped}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fallback-center", action="store_true")
    parser.add_argument("--replace-fallback", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--delay-seconds", type=float, default=7.0)
    parser.add_argument("--min-crop-id", type=int)
    parser.add_argument("--max-crop-id", type=int)
    args = parser.parse_args()
    if args.replace_fallback:
        replace_fallback_crops(
            limit=args.limit,
            delay_seconds=args.delay_seconds,
            min_crop_id=args.min_crop_id,
            max_crop_id=args.max_crop_id,
        )
    else:
        auto_crop(fallback_center=args.fallback_center)


def replace_fallback_crops(
    limit: int | None = None,
    delay_seconds: float = 7.0,
    min_crop_id: int | None = None,
    max_crop_id: int | None = None,
) -> None:
    Base.metadata.create_all(bind=engine)
    CROPS_DIR.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    processed = 0
    replaced = 0
    skipped = []

    try:
        fallback_crops = (
            db.query(CakeCrop)
            .filter(CakeCrop.detection_confidence == 0.1)
            .order_by(CakeCrop.cake_crop_id)
        )
        if min_crop_id is not None:
            fallback_crops = fallback_crops.filter(CakeCrop.cake_crop_id >= min_crop_id)
        if max_crop_id is not None:
            fallback_crops = fallback_crops.filter(CakeCrop.cake_crop_id <= max_crop_id)
        if limit is not None:
            fallback_crops = fallback_crops.limit(limit)
        fallback_crops = fallback_crops.all()

        for crop in fallback_crops:
            processed += 1
            original = crop.original_image
            original_path = ORIGINALS_DIR / original.file_name
            if not original_path.exists():
                skipped.append(f"{original.file_name}: file not found")
                continue

            boxes = detect_cake_boxes_with_vision_api(str(original_path))
            if not boxes:
                skipped.append(f"{original.file_name}: no boxes")
                continue

            with Image.open(original_path) as image:
                width, height = image.size
                valid_boxes = [box for box in boxes if is_valid_box(box, width, height)]
                if not valid_boxes:
                    skipped.append(f"{original.file_name}: invalid boxes")
                    continue

                expanded_boxes = filter_vision_boxes(
                    [expand_box(box, width, height) for box in valid_boxes]
                )
                existing_crop_names = {
                    item.crop_file_name
                    for item in db.query(CakeCrop)
                    .filter(CakeCrop.original_image_id == original.original_image_id)
                    .all()
                }

                for index, box in enumerate(expanded_boxes, start=1):
                    if index == 1:
                        target_crop = crop
                        crop_file_name = crop.crop_file_name
                    else:
                        crop_file_name = f"{original_path.stem}_cake_{index}.jpg"
                        while crop_file_name in existing_crop_names:
                            index += 1
                            crop_file_name = f"{original_path.stem}_cake_{index}.jpg"
                        target_crop = CakeCrop(
                            original_image_id=original.original_image_id,
                            crop_file_name=crop_file_name,
                            crop_file_path=f"/static/crops/{crop_file_name}",
                        )
                        db.add(target_crop)
                        existing_crop_names.add(crop_file_name)

                    output_path = CROPS_DIR / crop_file_name
                    save_crop(image, box, output_path)
                    target_crop.x_min = int(box["x_min"])
                    target_crop.y_min = int(box["y_min"])
                    target_crop.x_max = int(box["x_max"])
                    target_crop.y_max = int(box["y_max"])
                    target_crop.detection_confidence = float(box.get("confidence", 0.0))
                    replaced += 1
                    action = "replaced" if index == 1 else "created"
                    print(f"{action} {crop_file_name} source=vision")

                db.commit()

            if delay_seconds > 0:
                time.sleep(delay_seconds)

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(f"Processed fallback crops: {processed}")
    print(f"Replaced with vision crops: {replaced}")
    print(f"Skipped: {skipped}")


if __name__ == "__main__":
    main()
