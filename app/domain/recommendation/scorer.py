from __future__ import annotations

import re

from rapidfuzz import fuzz

from app.config.matching import MatchingConfig
from app.db.models.jobs import Job
from app.domain.master_profile.entities import MasterProfile
from app.domain.recommendation.entities import MatchedDetail, ScoreBreakdown


class SimilarityScorer:
    """Compute deterministic similarity scores per category for a profile and job."""

    def __init__(self, config: MatchingConfig) -> None:
        self._config = config
        self._threshold = config.fuzz_threshold

    def score_all(self, profile: MasterProfile, job: Job) -> ScoreBreakdown:
        job_text = self._job_text(job)

        skills_score, _matched_skills, _missing_skills = self._score_skills(profile, job_text)
        tech_score, _matched_tech, _missing_tech = self._score_technologies(profile, job_text)
        edu_score = self._score_education(profile, job_text)
        exp_score = self._score_experience(profile, job_text)
        lang_score = self._score_languages(profile, job_text)
        proj_score = self._score_projects(profile, job_text)
        loc_score = self._score_location(profile, job)
        pref_score = self._score_preferences(profile, job_text)

        return ScoreBreakdown(
            skills=skills_score,
            technologies=tech_score,
            education=edu_score,
            experience=exp_score,
            languages=lang_score,
            projects=proj_score,
            location=loc_score,
            preferences=pref_score,
        )

    def match_detail(self, profile: MasterProfile, job: Job) -> MatchedDetail:
        job_text = self._job_text(job)

        _, matched_skills, missing_skills = self._score_skills(profile, job_text)
        _, matched_tech, missing_tech = self._score_technologies(profile, job_text)
        matched_prefs, unmatched_prefs = self._score_preference_items(profile, job_text)

        return MatchedDetail(
            matched_skills=tuple(sorted(matched_skills)),
            missing_skills=tuple(sorted(missing_skills)),
            matched_technologies=tuple(sorted(matched_tech)),
            missing_technologies=tuple(sorted(missing_tech)),
            matched_preferences=tuple(sorted(matched_prefs)),
            unmatched_preferences=tuple(sorted(unmatched_prefs)),
        )

    def _job_text(self, job: Job) -> str:
        parts = [job.title or "", job.description or "", job.requirements or ""]
        return " ".join(parts)

    def _in_text(self, term: str, text: str) -> bool:
        return term.lower() in text.lower()

    def _fuzzy_in_text(self, term: str, text: str) -> bool:
        if self._in_text(term, text):
            return True
        words = re.findall(r"[a-zA-Z0-9_+#.]+", text.lower())
        return any(fuzz.ratio(term.lower(), word) >= self._threshold for word in words)

    def _score_skills(
        self, profile: MasterProfile, job_text: str
    ) -> tuple[float, list[str], list[str]]:
        matched: list[str] = []
        missing: list[str] = []
        for skill in profile.skills:
            name = skill.name
            if self._fuzzy_in_text(name, job_text):
                matched.append(name)
            else:
                missing.append(name)
        for exp in profile.experience:
            for tech in exp.technologies:
                if self._fuzzy_in_text(tech, job_text) and tech not in matched:
                    matched.append(tech)
        for proj in profile.projects:
            for tech in proj.technologies:
                if self._fuzzy_in_text(tech, job_text) and tech not in matched:
                    matched.append(tech)
        exp_techs = sum(len(e.technologies) for e in profile.experience)
        proj_techs = sum(len(p.technologies) for p in profile.projects)
        total = len(profile.skills) + exp_techs + proj_techs
        score = (len(matched) / total * 100) if total > 0 else 0.0
        return score, matched, missing

    def _score_technologies(
        self, profile: MasterProfile, job_text: str
    ) -> tuple[float, list[str], list[str]]:
        all_techs: set[str] = set()
        for exp in profile.experience:
            all_techs.update(t.lower() for t in exp.technologies)
        for proj in profile.projects:
            all_techs.update(t.lower() for t in proj.technologies)
        matched: list[str] = []
        missing: list[str] = []
        for tech in sorted(all_techs):
            if self._fuzzy_in_text(tech, job_text):
                matched.append(tech)
            else:
                missing.append(tech)
        score = (len(matched) / len(all_techs) * 100) if all_techs else 0.0
        return score, matched, missing

    def _score_education(self, profile: MasterProfile, job_text: str) -> float:
        if not profile.education:
            return 0.0
        score = 0.0
        for edu in profile.education:
            if edu.field_of_study and self._fuzzy_in_text(edu.field_of_study, job_text):
                score += 40.0
            if edu.degree and self._fuzzy_in_text(edu.degree, job_text):
                score += 40.0
            if edu.institution and self._fuzzy_in_text(edu.institution, job_text):
                score += 20.0
        return min(score / len(profile.education), 100.0)

    def _score_experience(self, profile: MasterProfile, job_text: str) -> float:
        if not profile.experience:
            return 0.0
        score = 0.0
        for exp in profile.experience:
            if exp.title and self._fuzzy_in_text(exp.title, job_text):
                score += 50.0
            if exp.company and self._fuzzy_in_text(exp.company, job_text):
                score += 30.0
            if exp.description and self._in_text(exp.description[:100], job_text):
                score += 20.0
        return min(score / len(profile.experience), 100.0)

    def _score_languages(self, profile: MasterProfile, job_text: str) -> float:
        if not profile.languages:
            return 50.0
        matched = sum(1 for lang in profile.languages if self._fuzzy_in_text(lang.name, job_text))
        return (matched / len(profile.languages)) * 100.0

    def _score_projects(self, profile: MasterProfile, job_text: str) -> float:
        if not profile.projects:
            return 0.0
        score = 0.0
        for proj in profile.projects:
            if proj.name and self._fuzzy_in_text(proj.name, job_text):
                score += 50.0
            if proj.description and self._in_text(proj.description[:100], job_text):
                score += 50.0
        return min(score / len(profile.projects), 100.0)

    def _score_location(self, profile: MasterProfile, job: Job) -> float:
        job_loc = (job.location or "").lower()
        if not job_loc:
            return 50.0
        profile_loc = (profile.personal_info.location or "").lower()
        if not profile_loc:
            return 50.0
        if profile_loc in job_loc or job_loc in profile_loc:
            return 100.0
        preferred = [c.lower() for c in profile.preferences.preferred_countries]
        if preferred and any(c in job_loc for c in preferred):
            return 80.0
        preferred_cities = [c.lower() for c in profile.preferences.preferred_cities]
        if preferred_cities and any(c in job_loc for c in preferred_cities):
            return 80.0
        for part in profile_loc.split(","):
            if part.strip() and part.strip() in job_loc:
                return 60.0
        return 0.0

    def _score_preferences(self, profile: MasterProfile, job_text: str) -> float:
        prefs_text = self._preferences_flat(profile)
        if not prefs_text:
            return 100.0
        matched = sum(1 for p in prefs_text if self._fuzzy_in_text(p, job_text))
        return (matched / len(prefs_text)) * 100.0

    def _score_preference_items(
        self, profile: MasterProfile, job_text: str
    ) -> tuple[list[str], list[str]]:
        matched: list[str] = []
        unmatched: list[str] = []
        prefs_text = self._preferences_flat(profile)
        for p in prefs_text:
            if self._fuzzy_in_text(p, job_text):
                matched.append(p)
            else:
                unmatched.append(p)
        return matched, unmatched

    def _preferences_flat(self, profile: MasterProfile) -> list[str]:
        items: list[str] = []
        items.extend(profile.preferences.preferred_technologies)
        if profile.preferences.preferred_language:
            items.append(profile.preferences.preferred_language)
        return items
