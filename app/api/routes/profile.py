"""GET /api/profile — current master profile."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.api.errors import APIError
from app.api.schemas import ProfileResponse
from app.services.profile_service import ProfileService

router = APIRouter()


def _build_profile_service(session: Session) -> ProfileService:
    from app.infrastructure.parsers.pdf_parser import PDFParser
    from app.services.profile_normalizer import ProfileNormalizer
    from app.services.profile_validator import ProfileValidator

    return ProfileService(
        session=session,
        parser=PDFParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )


@router.get("/api/profile", response_model=ProfileResponse, tags=["profile"])
def get_profile(session: Session = Depends(get_db)) -> ProfileResponse:  # noqa: B008
    """Return the active master profile.

    Raises 404 if no profile exists.
    """
    service = _build_profile_service(session)
    try:
        profile = service.get_current_profile()
    except APIError:
        raise
    except Exception as exc:
        raise APIError(
            "profile_not_found",
            "Failed to load profile.",
            status=404,
        ) from exc

    data = profile.to_dict()
    completeness = service.get_completeness()

    return ProfileResponse(
        personal_info=data.get("personal_info", {}),
        education=data.get("education", []),
        experience=data.get("experience", []),
        projects=data.get("projects", []),
        skills=data.get("skills", []),
        languages=data.get("languages", []),
        certifications=data.get("certifications", []),
        awards=data.get("awards", []),
        publications=data.get("publications", []),
        preferences=data.get("preferences", {}),
        completeness={
            "score": completeness.score,
            "breakdown": completeness.breakdown,
            "missing_fields": list(completeness.missing_fields),
        },
    )
