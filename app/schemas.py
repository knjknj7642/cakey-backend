from pydantic import BaseModel, Field


class RecommendRequest(BaseModel):
    tags: dict[str, list[str]] = Field(default_factory=dict)
    limit: int = Field(default=5, ge=1, le=100)


class RecommendResult(BaseModel):
    cake_crop_id: int
    original_image_id: int
    shop_name: str
    crop_image_url: str
    original_image_url: str
    score: int
    matched_tags: dict[str, list[str]]
    all_tags: dict[str, list[str]]


class RecommendResponse(BaseModel):
    results: list[RecommendResult]


class CustomizePreviewRequest(BaseModel):
    cake_crop_id: int
    target_tags: dict[str, list[str]] = Field(default_factory=dict)
    lettering_text: str | None = None
    extra_request: str | None = None
    character_description: str | None = None
    character_reference_image_url: str | None = None


class CustomizePreviewResponse(BaseModel):
    cake_crop_id: int
    base_crop_image_url: str
    original_image_url: str
    diff_tags: dict[str, dict[str, list[str]]]
    prompt: str


class CustomizeGenerateRequest(CustomizePreviewRequest):
    model: str = "gpt-image-1-mini"


class CustomizeGenerateResponse(CustomizePreviewResponse):
    status: str
    generated_image_url: str | None = None
    error: str | None = None
