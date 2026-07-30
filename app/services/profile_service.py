from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.profile import (
    AwardRecord,
    CertificationRecord,
    EducationRecord,
    ExperienceRecord,
    LanguageRecord,
    PreferenceRecord,
    Profile,
    ProfileVersionRecord,
    ProjectRecord,
    PublicationRecord,
    SkillRecord,
)
from app.domain.master_profile.entities import (
    Award,
    Certification,
    Education,
    Experience,
    Language,
    MasterProfile,
    PersonalInfo,
    Preference,
    ProfileCompleteness,
    ProfileVersion,
    Project,
    Publication,
    Skill,
)
from app.domain.master_profile.enums import InternshipDuration, ProficiencyLevel, RemotePreference
from app.domain.master_profile.errors import ProfileNotFoundError
from app.infrastructure.parsers.abstract import ProfileParser
from app.services.profile_normalizer import ProfileNormalizer
from app.services.profile_validator import ProfileValidator


class ProfileService:
    """Manage the master profile: import, export, versioning, activate, list, delete, edit."""

    def __init__(
        self,
        session: Session,
        parser: ProfileParser,
        normalizer: ProfileNormalizer,
        validator: ProfileValidator,
    ) -> None:
        self._session = session
        self._parser = parser
        self._normalizer = normalizer
        self._validator = validator

    def import_resume(self, file_path: Path, description: str | None = None) -> MasterProfile:
        raw_text = self._parser.parse(file_path)
        profile = self._normalizer.normalize(raw_text, _source_path=file_path)
        errors = self._validator.validate(profile)
        if errors:
            from app.domain.master_profile.errors import ProfileValidationError

            raise ProfileValidationError(errors)
        completeness = self._validator.compute_completeness(profile)
        self._persist(profile, completeness, description or f"Imported from {file_path.name}")
        return profile

    def _persist(
        self,
        profile: MasterProfile,
        completeness: ProfileCompleteness,
        description: str,
    ) -> None:
        profile_row = self._session.scalar(select(Profile).limit(1))
        if profile_row is None:
            profile_row = Profile(active=True)
            self._session.add(profile_row)
            self._session.flush()

        self._replace_education(profile_row.id, profile.education)
        self._replace_experience(profile_row.id, profile.experience)
        self._replace_projects(profile_row.id, profile.projects)
        self._replace_skills(profile_row.id, profile.skills)
        self._replace_languages(profile_row.id, profile.languages)
        self._replace_certifications(profile_row.id, profile.certifications)
        self._replace_awards(profile_row.id, profile.awards)
        self._replace_publications(profile_row.id, profile.publications)
        self._replace_preferences(profile_row.id, profile.preferences)

        version_number = self._next_version_number(profile_row.id)
        version = ProfileVersionRecord(
            profile_id=profile_row.id,
            version_number=version_number,
            snapshot_json=profile.to_dict(),
            completeness_score=completeness.score,
            change_description=description,
        )
        self._session.add(version)
        self._session.commit()

    def _replace_education(self, profile_id: int, entries: tuple[Education, ...]) -> None:
        self._session.query(EducationRecord).filter_by(profile_id=profile_id).delete()
        for e in entries:
            self._session.add(
                EducationRecord(
                    profile_id=profile_id,
                    institution=e.institution,
                    degree=e.degree,
                    field_of_study=e.field_of_study,
                    start_date=e.start_date,
                    end_date=e.end_date,
                    gpa=e.gpa,
                    description=e.description,
                )
            )

    def _replace_experience(self, profile_id: int, entries: tuple[Experience, ...]) -> None:
        self._session.query(ExperienceRecord).filter_by(profile_id=profile_id).delete()
        for e in entries:
            self._session.add(
                ExperienceRecord(
                    profile_id=profile_id,
                    company=e.company,
                    title=e.title,
                    location=e.location,
                    start_date=e.start_date,
                    end_date=e.end_date,
                    is_current=e.is_current,
                    description=e.description,
                    technologies_json=list(e.technologies) if e.technologies else None,
                )
            )

    def _replace_projects(self, profile_id: int, entries: tuple[Project, ...]) -> None:
        self._session.query(ProjectRecord).filter_by(profile_id=profile_id).delete()
        for p in entries:
            self._session.add(
                ProjectRecord(
                    profile_id=profile_id,
                    name=p.name,
                    description=p.description,
                    url=p.url,
                    technologies_json=list(p.technologies) if p.technologies else None,
                    start_date=p.start_date,
                    end_date=p.end_date,
                )
            )

    def _replace_skills(self, profile_id: int, entries: tuple[Skill, ...]) -> None:
        self._session.query(SkillRecord).filter_by(profile_id=profile_id).delete()
        for s in entries:
            self._session.add(
                SkillRecord(
                    profile_id=profile_id,
                    name=s.name,
                    category=s.category,
                    proficiency=s.proficiency.value if s.proficiency else None,
                )
            )

    def _replace_languages(self, profile_id: int, entries: tuple[Language, ...]) -> None:
        self._session.query(LanguageRecord).filter_by(profile_id=profile_id).delete()
        for l in entries:
            self._session.add(
                LanguageRecord(
                    profile_id=profile_id,
                    name=l.name,
                    proficiency=l.proficiency.value if l.proficiency else None,
                )
            )

    def _replace_certifications(self, profile_id: int, entries: tuple[Certification, ...]) -> None:
        self._session.query(CertificationRecord).filter_by(profile_id=profile_id).delete()
        for c in entries:
            self._session.add(
                CertificationRecord(
                    profile_id=profile_id, name=c.name, issuer=c.issuer, date=c.date, url=c.url
                )
            )

    def _replace_awards(self, profile_id: int, entries: tuple[Award, ...]) -> None:
        self._session.query(AwardRecord).filter_by(profile_id=profile_id).delete()
        for a in entries:
            self._session.add(
                AwardRecord(
                    profile_id=profile_id,
                    name=a.name,
                    issuer=a.issuer,
                    date=a.date,
                    description=a.description,
                )
            )

    def _replace_publications(self, profile_id: int, entries: tuple[Publication, ...]) -> None:
        self._session.query(PublicationRecord).filter_by(profile_id=profile_id).delete()
        for p in entries:
            self._session.add(
                PublicationRecord(
                    profile_id=profile_id,
                    title=p.title,
                    publisher=p.publisher,
                    date=p.date,
                    url=p.url,
                    description=p.description,
                )
            )

    def _replace_preferences(self, profile_id: int, pref: Preference) -> None:
        existing = self._session.query(PreferenceRecord).filter_by(profile_id=profile_id).first()
        if existing:
            self._session.delete(existing)
            self._session.flush()
        self._session.add(
            PreferenceRecord(
                profile_id=profile_id,
                preferred_countries_json=list(pref.preferred_countries)
                if pref.preferred_countries
                else None,
                preferred_cities_json=list(pref.preferred_cities)
                if pref.preferred_cities
                else None,
                remote_preference=pref.remote_preference.value,
                internship_duration=pref.internship_duration.value,
                preferred_technologies_json=list(pref.preferred_technologies)
                if pref.preferred_technologies
                else None,
                preferred_industries_json=list(pref.preferred_industries)
                if pref.preferred_industries
                else None,
                preferred_company_size=pref.preferred_company_size,
                preferred_language=pref.preferred_language,
                salary_expectation=pref.salary_expectation,
            )
        )

    def _next_version_number(self, profile_id: int) -> int:
        max_version = self._session.scalar(
            select(func.max(ProfileVersionRecord.version_number)).where(
                ProfileVersionRecord.profile_id == profile_id
            )
        )
        return (max_version or 0) + 1

    def get_current_profile(self) -> MasterProfile:
        profile_row = self._session.scalar(
            select(Profile).where(Profile.active.is_(True)).limit(1)
        )
        if profile_row is None:
            raise ProfileNotFoundError("No active profile found.")
        return self._db_to_domain(profile_row)

    def get_profile_by_id(self, profile_id: int) -> MasterProfile:
        profile_row = self._session.get(Profile, profile_id)
        if profile_row is None:
            raise ProfileNotFoundError(f"Profile {profile_id} not found.")
        return self._db_to_domain(profile_row)

    def _db_to_domain(self, profile_row: Profile) -> MasterProfile:
        latest_version = self._session.scalar(
            select(ProfileVersionRecord)
            .where(ProfileVersionRecord.profile_id == profile_row.id)
            .order_by(ProfileVersionRecord.version_number.desc())
            .limit(1)
        )
        personal_info = PersonalInfo(full_name="")
        if latest_version is not None:
            snap = latest_version.snapshot_json
            pi = snap.get("personal_info", {})
            personal_info = PersonalInfo(
                full_name=pi.get("full_name", ""),
                email=pi.get("email"),
                phone=pi.get("phone"),
                location=pi.get("location"),
                nationality=pi.get("nationality"),
                linkedin_url=pi.get("linkedin_url"),
                github_url=pi.get("github_url"),
                portfolio_url=pi.get("portfolio_url"),
                summary=pi.get("summary"),
            )
        edu = tuple(
            Education(
                institution=e.institution,
                degree=e.degree,
                field_of_study=e.field_of_study,
                start_date=e.start_date,
                end_date=e.end_date,
                gpa=e.gpa,
                description=e.description,
            )
            for e in profile_row.education_collection
        )
        exp = tuple(
            Experience(
                company=e.company,
                title=e.title,
                location=e.location,
                start_date=e.start_date,
                end_date=e.end_date,
                is_current=e.is_current,
                description=e.description,
                technologies=tuple(e.technologies_json) if e.technologies_json else (),
            )
            for e in profile_row.experience_collection
        )
        proj = tuple(
            Project(
                name=p.name,
                description=p.description,
                url=p.url,
                technologies=tuple(p.technologies_json) if p.technologies_json else (),
                start_date=p.start_date,
                end_date=p.end_date,
            )
            for p in profile_row.projects_collection
        )

        def _to_proficiency(val: str | None) -> ProficiencyLevel | None:
            if val is None:
                return None
            try:
                return ProficiencyLevel(val)
            except ValueError:
                return None

        skills = tuple(
            Skill(name=s.name, category=s.category, proficiency=_to_proficiency(s.proficiency))
            for s in profile_row.skills_collection
        )
        langs = tuple(
            Language(name=l.name, proficiency=_to_proficiency(l.proficiency))
            for l in profile_row.languages_collection
        )
        certs = tuple(
            Certification(name=c.name, issuer=c.issuer, date=c.date, url=c.url)
            for c in profile_row.certifications_collection
        )
        awards = tuple(
            Award(name=a.name, issuer=a.issuer, date=a.date, description=a.description)
            for a in profile_row.awards_collection
        )
        pubs = tuple(
            Publication(
                title=p.title,
                publisher=p.publisher,
                date=p.date,
                url=p.url,
                description=p.description,
            )
            for p in profile_row.publications_collection
        )
        pref_row = profile_row.preference
        pref = Preference()
        if pref_row:
            pref = Preference(
                preferred_countries=tuple(pref_row.preferred_countries_json or ()),
                preferred_cities=tuple(pref_row.preferred_cities_json or ()),
                remote_preference=RemotePreference(pref_row.remote_preference)
                if pref_row.remote_preference
                else RemotePreference.ANY,
                internship_duration=InternshipDuration(pref_row.internship_duration)
                if pref_row.internship_duration
                else InternshipDuration.ANY,
                preferred_technologies=tuple(pref_row.preferred_technologies_json or ()),
                preferred_industries=tuple(pref_row.preferred_industries_json or ()),
                preferred_company_size=pref_row.preferred_company_size,
                preferred_language=pref_row.preferred_language,
                salary_expectation=pref_row.salary_expectation,
            )
        return MasterProfile(
            personal_info=personal_info,
            education=edu,
            experience=exp,
            projects=proj,
            skills=skills,
            languages=langs,
            certifications=certs,
            awards=awards,
            publications=pubs,
            preferences=pref,
        )

    def export_profile(self, file_path: Path) -> None:
        profile = self.get_current_profile()
        profile_row = self._session.scalar(select(Profile).where(Profile.active.is_(True)).limit(1))
        data = profile.to_dict()
        if profile_row is not None:
            data["name"] = profile_row.name
            completeness = self._validator.compute_completeness(profile)
            data["completeness_score"] = completeness.score
            data["completeness_breakdown"] = completeness.breakdown
            data["missing_fields"] = list(completeness.missing_fields)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def list_versions(self) -> tuple[ProfileVersion, ...]:
        profile_row = self._session.scalar(select(Profile).limit(1))
        if profile_row is None:
            raise ProfileNotFoundError("No profile has been imported yet.")
        version_rows = self._session.scalars(
            select(ProfileVersionRecord)
            .where(ProfileVersionRecord.profile_id == profile_row.id)
            .order_by(ProfileVersionRecord.version_number.desc())
        ).all()
        versions: list[ProfileVersion] = []
        for vr in version_rows:
            profile = self._dict_to_profile(vr.snapshot_json)
            versions.append(
                ProfileVersion(
                    version_number=vr.version_number,
                    profile=profile,
                    change_description=vr.change_description or "",
                    completeness_score=vr.completeness_score,
                    created_at=vr.created_at.isoformat() if vr.created_at else "",
                )
            )
        return tuple(versions)

    def list_profiles(self) -> tuple[dict[str, Any], ...]:
        rows = self._session.scalars(
            select(Profile).order_by(Profile.created_at.desc())
        ).all()
        result: list[dict[str, Any]] = []
        for row in rows:
            try:
                profile = self._db_to_domain(row)
            except Exception:  # noqa: S112
                continue
            c = self._validator.compute_completeness(profile)
            result.append({
                "id": row.id,
                "name": row.name or profile.personal_info.full_name or f"Profile #{row.id}",
                "active": row.active,
                "full_name": profile.personal_info.full_name,
                "email": profile.personal_info.email,
                "completeness_score": c.score,
                "created_at": row.created_at.isoformat() if row.created_at else "",
            })
        return tuple(result)

    def activate_profile(self, profile_id: int) -> str:
        row = self._session.get(Profile, profile_id)
        if row is None:
            raise ProfileNotFoundError(f"Profile {profile_id} not found.")
        name = row.name or f"Profile #{row.id}"
        self._session.query(Profile).update({"active": False})
        row.active = True
        self._session.commit()
        return name

    def delete_profile(self, profile_id: int) -> None:
        row = self._session.get(Profile, profile_id)
        if row is None:
            raise ProfileNotFoundError(f"Profile {profile_id} not found.")
        self._session.delete(row)
        self._session.commit()

    def edit_profile(
        self,
        profile_id: int,
        name: str | None = None,
        summary: str | None = None,
    ) -> None:
        row = self._session.get(Profile, profile_id)
        if row is None:
            raise ProfileNotFoundError(f"Profile {profile_id} not found.")
        if name is not None:
            row.name = name
        if summary is not None:
            profile = self._db_to_domain(row)
            pi = PersonalInfo(
                full_name=profile.personal_info.full_name,
                email=profile.personal_info.email,
                phone=profile.personal_info.phone,
                location=profile.personal_info.location,
                nationality=profile.personal_info.nationality,
                linkedin_url=profile.personal_info.linkedin_url,
                github_url=profile.personal_info.github_url,
                portfolio_url=profile.personal_info.portfolio_url,
                summary=summary,
            )
            completeness = self._validator.compute_completeness(profile)
            new_profile = MasterProfile(
                personal_info=pi,
                education=profile.education,
                experience=profile.experience,
                projects=profile.projects,
                skills=profile.skills,
                languages=profile.languages,
                certifications=profile.certifications,
                awards=profile.awards,
                publications=profile.publications,
                preferences=profile.preferences,
            )
            self._replace_education(row.id, new_profile.education)
            self._replace_experience(row.id, new_profile.experience)
            self._replace_projects(row.id, new_profile.projects)
            self._replace_skills(row.id, new_profile.skills)
            self._replace_languages(row.id, new_profile.languages)
            self._replace_certifications(row.id, new_profile.certifications)
            self._replace_awards(row.id, new_profile.awards)
            self._replace_publications(row.id, new_profile.publications)
            self._replace_preferences(row.id, new_profile.preferences)
            vn = self._next_version_number(row.id)
            version = ProfileVersionRecord(
                profile_id=row.id,
                version_number=vn,
                snapshot_json=new_profile.to_dict(),
                completeness_score=completeness.score,
                change_description="Edited summary",
            )
            self._session.add(version)
        self._session.commit()

    def validate_profile(self, profile_id: int | None = None) -> list[Any]:
        if profile_id is not None:
            profile = self.get_profile_by_id(profile_id)
        else:
            profile = self.get_current_profile()
        return self._validator.validate(profile)

    def _dict_to_profile(self, data: dict[str, Any]) -> MasterProfile:
        pi_data = data.get("personal_info", {})
        pi = PersonalInfo(
            full_name=pi_data.get("full_name", ""),
            email=pi_data.get("email"),
            phone=pi_data.get("phone"),
            location=pi_data.get("location"),
            nationality=pi_data.get("nationality"),
            linkedin_url=pi_data.get("linkedin_url"),
            github_url=pi_data.get("github_url"),
            portfolio_url=pi_data.get("portfolio_url"),
            summary=pi_data.get("summary"),
        )
        edu = tuple(
            Education(
                institution=e.get("institution", ""),
                degree=e.get("degree"),
                field_of_study=e.get("field_of_study"),
                gpa=e.get("gpa"),
                description=e.get("description"),
            )
            for e in data.get("education", [])
        )
        exp = tuple(
            Experience(
                company=e.get("company", ""),
                title=e.get("title"),
                location=e.get("location"),
                is_current=e.get("is_current", False),
                description=e.get("description"),
                technologies=tuple(e.get("technologies", [])),
            )
            for e in data.get("experience", [])
        )
        proj = tuple(
            Project(
                name=p.get("name", ""),
                description=p.get("description"),
                url=p.get("url"),
                technologies=tuple(p.get("technologies", [])),
            )
            for p in data.get("projects", [])
        )
        skills = tuple(
            Skill(
                name=s.get("name", ""),
                category=s.get("category"),
                proficiency=s.get("proficiency"),
            )
            for s in data.get("skills", [])
        )
        langs = tuple(
            Language(name=l.get("name", ""), proficiency=l.get("proficiency"))
            for l in data.get("languages", [])
        )
        certs = tuple(
            Certification(
                name=c.get("name", ""),
                issuer=c.get("issuer"),
                date=c.get("date"),
                url=c.get("url"),
            )
            for c in data.get("certifications", [])
        )
        awards = tuple(
            Award(
                name=a.get("name", ""),
                issuer=a.get("issuer"),
                date=a.get("date"),
                description=a.get("description"),
            )
            for a in data.get("awards", [])
        )
        pubs = tuple(
            Publication(
                title=p.get("title", ""),
                publisher=p.get("publisher"),
                date=p.get("date"),
                url=p.get("url"),
                description=p.get("description"),
            )
            for p in data.get("publications", [])
        )
        pref_data = data.get("preferences", {})
        pref = Preference(
            preferred_countries=tuple(pref_data.get("preferred_countries", [])),
            preferred_cities=tuple(pref_data.get("preferred_cities", [])),
            remote_preference=RemotePreference(pref_data.get("remote_preference", "any")),
            internship_duration=InternshipDuration(pref_data.get("internship_duration", "any")),
            preferred_technologies=tuple(pref_data.get("preferred_technologies", [])),
            preferred_industries=tuple(pref_data.get("preferred_industries", [])),
            preferred_company_size=pref_data.get("preferred_company_size"),
            preferred_language=pref_data.get("preferred_language"),
            salary_expectation=pref_data.get("salary_expectation"),
        )
        return MasterProfile(
            personal_info=pi,
            education=edu,
            experience=exp,
            projects=proj,
            skills=skills,
            languages=langs,
            certifications=certs,
            awards=awards,
            publications=pubs,
            preferences=pref,
        )

    def get_completeness(self) -> ProfileCompleteness:
        profile = self.get_current_profile()
        return self._validator.compute_completeness(profile)
