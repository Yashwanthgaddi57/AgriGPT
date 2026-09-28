"""Disease detection service using Claude Vision."""
import base64
import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.ai.claude_client import get_claude
from app.ai.prompts import DISEASE_DETECTION_SYSTEM
from app.core.config import settings
from app.core.exceptions import AIError, ValidationError
from app.models.disease_report import DiseaseReport
from app.schemas.ai_features import DiseaseReportResponse

logger = logging.getLogger("app.services.disease")

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024

# Magic bytes for image format detection
IMAGE_MAGIC = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"RIFF": "image/webp",  # WebP starts with RIFF....WEBP
    b"\x00\x00\x00\x1cftypheic": "image/heic",
    b"\x00\x00\x00\x20ftypheic": "image/heic",
}

def detect_image_type(image_bytes: bytes) -> Optional[str]:
    """Detect actual image type from magic bytes."""
    for magic, mime in IMAGE_MAGIC.items():
        if image_bytes.startswith(magic):
            # Special case for WebP - check for WEBP signature
            if mime == "image/webp" and b"WEBP" not in image_bytes[:16]:
                continue
            return mime
    return None


class DiseaseService:
    def __init__(self, db: Session):
        self.db = db

    async def analyze(
        self,
        user_id: str,
        crop: str,
        image_bytes: bytes,
        media_type: str,
        farm_id: str | None = None,
    ) -> DiseaseReport:
        # Detect actual image type from magic bytes
        detected_type = detect_image_type(image_bytes)
        if detected_type is None:
            # Fall back to provided media_type if detection fails
            detected_type = media_type
        
        if detected_type not in ALLOWED_IMAGE_TYPES:
            raise ValidationError(f"Unsupported image type: {detected_type}")
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise ValidationError("Image exceeds 10MB limit")

        # 1) Persist to Supabase Storage
        image_url = None
        try:
            from app.core.supabase_client import upload_disease_image

            ext = detected_type.split("/")[-1].replace("jpeg", "jpg")
            image_url = await upload_disease_image(
                user_id, f"{uuid.uuid4().hex}.{ext}", image_bytes
            )
        except Exception as e:
            logger.warning("Image upload failed, continuing analysis: %s", e)

        # 2) Claude Vision analysis
        claude = get_claude()
        image_b64 = base64.b64encode(image_bytes).decode()
        prompt = f"Analyze this crop image. Farmer says the crop is: {crop}."
        try:
            data = claude.vision_json(
                system=DISEASE_DETECTION_SYSTEM,
                prompt=prompt,
                image_b64=image_b64,
                media_type=detected_type,
            )
        except Exception as e:
            logger.exception("Vision analysis failed")
            raise AIError(f"Disease detection failed: {e}") from e

        report = DiseaseReport(
            user_id=uuid.UUID(user_id),
            farm_id=uuid.UUID(farm_id) if farm_id else None,
            crop=data.get("crop", crop),
            image_path=None,
            image_url=image_url,
            disease_name=data.get("disease_name", "Unknown"),
            is_healthy=bool(data.get("is_healthy", False)),
            confidence=float(data.get("confidence", 0)),
            severity=data.get("severity", "low"),
            severity_score=float(data.get("severity_score", 0)),
            symptoms=data.get("symptoms"),
            cause=data.get("cause"),
            treatment=data.get("treatment"),
            prevention=data.get("prevention"),
            spread_risk=data.get("spread_risk"),
            alternatives=data.get("alternative_explanations") or data.get("alternatives"),
            followup_status="open" if not data.get("is_healthy") else None,
            model=settings.ANTHROPIC_MODEL,
        )
        self.db.add(report)
        self.db.flush()
        return report

    def update_followup(
        self,
        user_id: str,
        report_id: str,
        followup_status: str | None = None,
        notes: str | None = None,
    ) -> DiseaseReport:
        """Farmer-owned follow-up updates (Crop Health workflow)."""
        report = (
            self.db.query(DiseaseReport)
            .filter(
                DiseaseReport.id == uuid.UUID(report_id),
                DiseaseReport.user_id == uuid.UUID(user_id),
            )
            .first()
        )
        if not report:
            from app.core.exceptions import NotFoundError

            raise NotFoundError("Report not found")
        if followup_status is not None:
            report.followup_status = followup_status
        if notes is not None:
            report.notes = notes
        self.db.add(report)
        self.db.flush()
        return report
