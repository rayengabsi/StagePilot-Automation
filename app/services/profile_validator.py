from __future__ import annotations

import re

from app.domain.master_profile.entities import MasterProfile, ProfileCompleteness
from app.domain.master_profile.errors import ValidationError


class ProfileValidator:
    """Validate a normalized MasterProfile and compute a completeness score.

    Validation is deterministic. No AI is used.
    """

    EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    URL_RE = re.compile(r"^https?://[^\s]+$")
    PHONE_RE = re.compile(
        r"^\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,4}$"
    )

    def validate(self, profile: MasterProfile) -> list[ValidationError]:
        """Validate a MasterProfile and return a list of validation errors.

        Returns an empty list if the profile is valid.
        """
        errors: list[ValidationError] = []
        self._validate_personal_info(profile, errors)
        self._validate_education(profile, errors)
        self._validate_experience(profile, errors)
        self._validate_skills(profile, errors)
        self._validate_certifications(profile, errors)
        self._validate_projects(profile, errors)
        self._validate_languages(profile, errors)
        self._validate_awards(profile, errors)
        self._validate_publications(profile, errors)
        return errors

    def _validate_personal_info(
        self, profile: MasterProfile, errors: list[ValidationError]
    ) -> None:
        pi = profile.personal_info
        if not pi.full_name or not pi.full_name.strip():
            errors.append(
                ValidationError(field="personal_info.full_name", message="Full name is required.")
            )
        if pi.email and not self.EMAIL_RE.match(pi.email):
            errors.append(
                ValidationError(
                    field="personal_info.email",
                    message="Invalid email format.",
                    value=pi.email,
                )
            )
        if pi.linkedin_url and not self.URL_RE.match(pi.linkedin_url):
            errors.append(
                ValidationError(
                    field="personal_info.linkedin_url",
                    message="Invalid URL format.",
                    value=pi.linkedin_url,
                )
            )
        if pi.github_url and not self.URL_RE.match(pi.github_url):
            errors.append(
                ValidationError(
                    field="personal_info.github_url",
                    message="Invalid URL format.",
                    value=pi.github_url,
                )
            )
        if pi.portfolio_url and not self.URL_RE.match(pi.portfolio_url):
            errors.append(
                ValidationError(
                    field="personal_info.portfolio_url",
                    message="Invalid URL format.",
                    value=pi.portfolio_url,
                )
            )
        if pi.phone and not self.PHONE_RE.match(pi.phone):
            errors.append(
                ValidationError(
                    field="personal_info.phone",
                    message="Invalid phone number format.",
                    value=pi.phone,
                )
            )

    def _validate_education(self, profile: MasterProfile, errors: list[ValidationError]) -> None:
        seen: set[str] = set()
        for i, edu in enumerate(profile.education):
            if not edu.institution or not edu.institution.strip():
                errors.append(
                    ValidationError(
                        field=f"education[{i}].institution",
                        message="Institution name is required.",
                    )
                )
            key = f"{edu.institution}|{edu.degree}|{edu.field_of_study}".lower()
            if key in seen:
                errors.append(
                    ValidationError(
                        field=f"education[{i}]",
                        message="Duplicate education entry.",
                        value=edu.institution,
                    )
                )
            seen.add(key)
            if edu.start_date and edu.end_date and edu.start_date > edu.end_date:
                errors.append(
                    ValidationError(
                        field=f"education[{i}]",
                        message="Start date is after end date.",
                        value=f"{edu.start_date} > {edu.end_date}",
                    )
                )

    def _validate_experience(self, profile: MasterProfile, errors: list[ValidationError]) -> None:
        seen: set[str] = set()
        for i, exp in enumerate(profile.experience):
            if not exp.company or not exp.company.strip():
                errors.append(
                    ValidationError(
                        field=f"experience[{i}].company",
                        message="Company name is required.",
                    )
                )
            key = f"{exp.company}|{exp.title}".lower()
            if key in seen:
                errors.append(
                    ValidationError(
                        field=f"experience[{i}]",
                        message="Duplicate experience entry.",
                        value=exp.company,
                    )
                )
            seen.add(key)
            if (
                exp.start_date
                and exp.end_date
                and exp.start_date > exp.end_date
                and not exp.is_current
            ):
                errors.append(
                    ValidationError(
                        field=f"experience[{i}]",
                        message="Start date is after end date.",
                        value=f"{exp.start_date} > {exp.end_date}",
                    )
                )

    def _validate_skills(self, profile: MasterProfile, errors: list[ValidationError]) -> None:
        seen: set[str] = set()
        for i, skill in enumerate(profile.skills):
            if not skill.name or not skill.name.strip():
                errors.append(
                    ValidationError(field=f"skills[{i}]", message="Skill name is required.")
                )
            lower = skill.name.lower().strip()
            if lower in seen:
                errors.append(
                    ValidationError(
                        field=f"skills[{i}]",
                        message="Duplicate skill.",
                        value=skill.name,
                    )
                )
            seen.add(lower)

    def _validate_certifications(
        self, profile: MasterProfile, errors: list[ValidationError]
    ) -> None:
        seen: set[str] = set()
        for i, cert in enumerate(profile.certifications):
            if not cert.name or not cert.name.strip():
                errors.append(
                    ValidationError(
                        field=f"certifications[{i}]", message="Certification name is required."
                    )
                )
            lower = cert.name.lower().strip()
            if lower in seen:
                errors.append(
                    ValidationError(
                        field=f"certifications[{i}]",
                        message="Duplicate certification.",
                        value=cert.name,
                    )
                )
            seen.add(lower)

    def _validate_projects(self, profile: MasterProfile, errors: list[ValidationError]) -> None:
        seen: set[str] = set()
        for i, proj in enumerate(profile.projects):
            if not proj.name or not proj.name.strip():
                errors.append(
                    ValidationError(field=f"projects[{i}]", message="Project name is required.")
                )
            lower = proj.name.lower().strip()
            if lower in seen:
                errors.append(
                    ValidationError(
                        field=f"projects[{i}]",
                        message="Duplicate project.",
                        value=proj.name,
                    )
                )
            seen.add(lower)
            if proj.url and not self.URL_RE.match(proj.url):
                errors.append(
                    ValidationError(
                        field=f"projects[{i}].url",
                        message="Invalid URL format.",
                        value=proj.url,
                    )
                )

    def _validate_languages(self, profile: MasterProfile, errors: list[ValidationError]) -> None:
        seen: set[str] = set()
        for i, lang in enumerate(profile.languages):
            if not lang.name or not lang.name.strip():
                errors.append(
                    ValidationError(field=f"languages[{i}]", message="Language name is required.")
                )
            lower = lang.name.lower().strip()
            if lower in seen:
                errors.append(
                    ValidationError(
                        field=f"languages[{i}]",
                        message="Duplicate language.",
                        value=lang.name,
                    )
                )
            seen.add(lower)

    def _validate_awards(
        self, profile: MasterProfile, errors: list[ValidationError]
    ) -> None:
        seen: set[str] = set()
        for i, award in enumerate(profile.awards):
            if not award.name or not award.name.strip():
                errors.append(
                    ValidationError(field=f"awards[{i}]", message="Award name is required.")
                )
            lower = award.name.lower().strip()
            if lower in seen:
                errors.append(
                    ValidationError(
                        field=f"awards[{i}]",
                        message="Duplicate award.",
                        value=award.name,
                    )
                )
            seen.add(lower)

    def _validate_publications(
        self, profile: MasterProfile, errors: list[ValidationError]
    ) -> None:
        seen: set[str] = set()
        for i, pub in enumerate(profile.publications):
            if not pub.title or not pub.title.strip():
                errors.append(
                    ValidationError(
                        field=f"publications[{i}]", message="Publication title is required."
                    )
                )
            lower = pub.title.lower().strip()
            if lower in seen:
                errors.append(
                    ValidationError(
                        field=f"publications[{i}]",
                        message="Duplicate publication.",
                        value=pub.title,
                    )
                )
            seen.add(lower)

    def compute_completeness(self, profile: MasterProfile) -> ProfileCompleteness:
        """Compute a completeness score (0-100) for the profile.

        Weights:
          - Personal information: 20%
          - Education: 20%
          - Skills: 20%
          - Experience: 20%
          - Projects / Certifications / Languages: 20%
        """
        breakdown: dict[str, float] = {}
        missing: list[str] = []

        # Personal info: 20%
        pi_score = 0.0
        pi_fields = [
            ("full_name", profile.personal_info.full_name),
            ("email", profile.personal_info.email),
            ("phone", profile.personal_info.phone),
            ("linkedin_url", profile.personal_info.linkedin_url),
            ("github_url", profile.personal_info.github_url),
            ("portfolio_url", profile.personal_info.portfolio_url),
        ]
        pi_max = len(pi_fields)
        for field_name, value in pi_fields:
            if value and value.strip():
                pi_score += 1.0
            else:
                missing.append(field_name)
        pi_pct = (pi_score / pi_max) * 100.0 if pi_max > 0 else 0.0
        breakdown["personal_info"] = round(pi_pct, 1)

        # Education: 20%
        edu_pct = 100.0 if profile.education else 0.0
        breakdown["education"] = edu_pct
        if not profile.education:
            missing.append("education")

        # Skills: 20%
        skills_pct = min(100.0, len(profile.skills) * 10.0) if profile.skills else 0.0
        breakdown["skills"] = round(skills_pct, 1)
        if not profile.skills:
            missing.append("skills")

        # Experience: 20%
        exp_pct = 100.0 if profile.experience else 0.0
        breakdown["experience"] = exp_pct
        if not profile.experience:
            missing.append("experience")

        # Projects / Certifications / Languages / Awards / Publications: 20%
        extra_score = 0.0
        extra_max = 5.0
        if profile.projects:
            extra_score += 1.0
        else:
            missing.append("projects")
        if profile.certifications:
            extra_score += 1.0
        else:
            missing.append("certifications")
        if profile.languages:
            extra_score += 1.0
        else:
            missing.append("languages")
        if profile.awards:
            extra_score += 1.0
        else:
            missing.append("awards")
        if profile.publications:
            extra_score += 1.0
        else:
            missing.append("publications")
        extra_pct = (extra_score / extra_max) * 100.0 if extra_max > 0 else 0.0
        breakdown["extras"] = round(extra_pct, 1)

        total = (
            pi_pct * 0.20 + edu_pct * 0.20 + skills_pct * 0.20 + exp_pct * 0.20 + extra_pct * 0.20
        )
        return ProfileCompleteness(
            score=round(total, 1),
            breakdown=breakdown,
            missing_fields=tuple(sorted(set(missing))),
        )
