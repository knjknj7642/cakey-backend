from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OriginalImage(Base):
    __tablename__ = "original_images"

    original_image_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    shop_name: Mapped[str] = mapped_column(String, nullable=False)
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    crops: Mapped[list["CakeCrop"]] = relationship(
        back_populates="original_image",
        cascade="all, delete-orphan",
    )


class CakeCrop(Base):
    __tablename__ = "cake_crops"

    cake_crop_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    original_image_id: Mapped[int] = mapped_column(
        ForeignKey("original_images.original_image_id"),
        nullable=False,
        index=True,
    )
    crop_file_name: Mapped[str] = mapped_column(String, nullable=False)
    crop_file_path: Mapped[str] = mapped_column(String, nullable=False)
    x_min: Mapped[int] = mapped_column(Integer, nullable=False)
    y_min: Mapped[int] = mapped_column(Integer, nullable=False)
    x_max: Mapped[int] = mapped_column(Integer, nullable=False)
    y_max: Mapped[int] = mapped_column(Integer, nullable=False)
    detection_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    original_image: Mapped[OriginalImage] = relationship(back_populates="crops")
    tags: Mapped[list["CropTag"]] = relationship(
        back_populates="cake_crop",
        cascade="all, delete-orphan",
    )
    review: Mapped["CakeCropReview | None"] = relationship(
        back_populates="cake_crop",
        cascade="all, delete-orphan",
        uselist=False,
    )


class CropTag(Base):
    __tablename__ = "crop_tags"

    crop_tag_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cake_crop_id: Mapped[int] = mapped_column(
        ForeignKey("cake_crops.cake_crop_id"),
        nullable=False,
        index=True,
    )
    tag_key: Mapped[str] = mapped_column(String, nullable=False, index=True)
    tag_value: Mapped[str] = mapped_column(String, nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    cake_crop: Mapped[CakeCrop] = relationship(back_populates="tags")


class CakeCropReview(Base):
    __tablename__ = "cake_crop_reviews"

    cake_crop_review_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cake_crop_id: Mapped[int] = mapped_column(
        ForeignKey("cake_crops.cake_crop_id"),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending", index=True)
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    cake_crop: Mapped[CakeCrop] = relationship(back_populates="review")
