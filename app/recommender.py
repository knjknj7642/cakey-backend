from collections import defaultdict

from sqlalchemy.orm import Session, joinedload

from app.models import CakeCrop, CakeCropReview


TAG_WEIGHTS = {
    "character_type": 4,
    "dominant_color": 3,
    "visual_style": 3,
    "border_type": 2,
    "lettering_type": 2,
    "cream_decoration": 2,
    "topping_decoration": 1,
    "shape": 1,
    "board_lettering": 1,
    "text_presence": 1,
}


def build_static_url(file_path: str, prefix: str) -> str:
    if file_path.startswith(f"/static/{prefix}/"):
        return file_path
    file_name = file_path.replace("\\", "/").split("/")[-1]
    return f"/static/{prefix}/{file_name}"


def group_tags(tags: list) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for tag in tags:
        if tag.tag_value not in grouped[tag.tag_key]:
            grouped[tag.tag_key].append(tag.tag_value)
    return dict(grouped)


def recommend_cakes(
    db: Session,
    requested_tags: dict[str, list[str]],
    limit: int = 5,
) -> list[dict]:
    normalized_request = {
        key: set(values)
        for key, values in requested_tags.items()
        if values
    }

    crops = (
        db.query(CakeCrop)
        .options(joinedload(CakeCrop.original_image), joinedload(CakeCrop.tags))
        .join(CakeCropReview)
        .filter(CakeCropReview.status == "approved")
        .all()
    )

    results = []
    for crop in crops:
        all_tags = group_tags(crop.tags)
        matched_tags: dict[str, list[str]] = {}
        score = 0

        for tag_key, wanted_values in normalized_request.items():
            crop_values = set(all_tags.get(tag_key, []))
            matched_values = sorted(crop_values & wanted_values)
            if matched_values:
                score += TAG_WEIGHTS.get(tag_key, 1)
                matched_tags[tag_key] = matched_values

        if score == 0:
            continue

        results.append(
            {
                "cake_crop_id": crop.cake_crop_id,
                "original_image_id": crop.original_image_id,
                "shop_name": crop.original_image.shop_name,
                "crop_image_url": build_static_url(crop.crop_file_path, "crops"),
                "original_image_url": build_static_url(
                    crop.original_image.file_path,
                    "originals",
                ),
                "score": score,
                "matched_tags": matched_tags,
                "all_tags": all_tags,
            }
        )

    results.sort(key=lambda item: (-item["score"], item["cake_crop_id"]))
    return results[:limit]
