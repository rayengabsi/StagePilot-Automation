from __future__ import annotations

import re

from app.config.classification import ClassificationConfig, get_classification_config
from app.domain.jobs.classification import JobClassification
from app.domain.jobs.entities import NormalizedJob


class JobClassificationService:
    """Derive structured intelligence from a normalized job.

    Specialization, seniority, employment type, work mode, and urgency are
    detected using configurable keyword dictionaries and scoring rules in
    ``app/config/classification.toml``. The service is provider-agnostic and
    needs no code changes to support new labels.
    """

    def __init__(self, config: ClassificationConfig | None = None) -> None:
        """Initialize the service with classification dictionaries."""
        self._config = config or get_classification_config()
        self._specializations = _compile(self._config.specializations)
        self._seniority = _compile(self._config.seniority_levels)
        self._employment_types = _compile(self._config.employment_types)
        self._work_modes = _compile(self._config.work_modes)
        self._urgency_patterns = _compile_patterns(self._config.urgency)

    def classify(self, job: NormalizedJob) -> JobClassification:
        """Classify a normalized job into structured intelligence fields."""
        title = (job.title or "").lower()
        body = _body_text(job)

        specialization = self._detect(
            self._specializations, self._config.specializations, title, body
        )
        seniority = self._detect_seniority(title, body)
        employment_type = self._detect(
            self._employment_types, self._config.employment_types, title, body
        )
        work_mode = self._detect_work_mode(title, body)
        urgency = "urgent" if _any_match(self._urgency_patterns, title + " " + body) else None

        return JobClassification(
            specialization=specialization,
            seniority=seniority,
            employment_type=employment_type,
            work_mode=work_mode,
            urgency=urgency,
        )

    def _detect(
        self,
        patterns: dict[str, tuple[re.Pattern[str], ...]],
        labels: dict[str, tuple[str, ...]],
        title: str,
        body: str,
    ) -> str | None:
        """Return the best-matching label for a scored dictionary, or None.

        The winner is the label with the highest weighted keyword score, with
        ties resolved by dictionary order (first listed wins). A label must
        exceed ``min_score`` to be assigned.
        """
        best_label: str | None = None
        best_score = self._config.min_score
        for label in labels:
            score = _score(patterns[label], title, self._config.title_weight)
            score += _score(patterns[label], body, self._config.body_weight)
            if score > best_score:
                best_label = label
                best_score = score
        return best_label

    def _detect_seniority(self, title: str, body: str) -> str | None:
        """Detect seniority preferring the most senior matching level.

        Levels are checked from most senior (e.g. director) down to intern, so
        "Senior Manager" is classified as manager, not senior.
        """
        levels = list(self._config.seniority_levels)
        for level in reversed(levels):
            patterns = self._seniority[level]
            if _any_match(patterns, title) or _any_match(patterns, body):
                return level
        return None

    def _detect_work_mode(self, title: str, body: str) -> str | None:
        """Detect work mode from explicit mode keywords.

        Remote, hybrid, and on-site keywords are disjoint, so the first
        matching mode in dictionary order wins without a scoring conflict.
        """
        for mode in self._config.work_modes:
            if _any_match(self._work_modes[mode], title) or _any_match(
                self._work_modes[mode], body
            ):
                return mode
        return None


def _body_text(job: NormalizedJob) -> str:
    """Combine description, requirements, and original metadata into searchable text."""
    parts = [
        job.description or "",
        job.requirements or "",
        job.department or "",
        job.employment_type or "",
        job.remote_status or "",
        job.location or "",
    ]
    return " ".join(parts).lower()


def _compile(
    labels: dict[str, tuple[str, ...]],
) -> dict[str, tuple[re.Pattern[str], ...]]:
    """Compile keyword patterns for a label dictionary."""
    return {label: _compile_patterns(keywords) for label, keywords in labels.items()}


def _compile_patterns(keywords: tuple[str, ...]) -> tuple[re.Pattern[str], ...]:
    """Compile word-boundary, case-insensitive patterns for keywords."""
    return tuple(
        re.compile(r"(?<![a-z])" + re.escape(keyword.lower()) + r"(?![a-z])")
        for keyword in keywords
    )


def _any_match(patterns: tuple[re.Pattern[str], ...], text: str) -> bool:
    """Return True when any pattern matches the text."""
    return any(pattern.search(text) is not None for pattern in patterns)


def _score(patterns: tuple[re.Pattern[str], ...], text: str, weight: float) -> float:
    """Count keyword occurrences in text scaled by a weight."""
    hits = sum(len(pattern.findall(text)) for pattern in patterns)
    return hits * weight
