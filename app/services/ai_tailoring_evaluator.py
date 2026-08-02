from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.config.ai_config import TailoringQualityConfig, get_ai_config
from app.domain.ai.quality import (
    QualityCategory,
    QualityIssue,
    QualityReport,
    QualitySeverity,
)

# Category weights used to combine per-category scores into the overall score.
_CATEGORY_WEIGHTS: dict[str, float] = {
    QualityCategory.HALLUCINATION.value: 25.0,
    QualityCategory.KEYWORD_COVERAGE.value: 20.0,
    QualityCategory.FACTUAL_PRESERVATION.value: 20.0,
    QualityCategory.SECTION_COMPLETENESS.value: 15.0,
    QualityCategory.ATS_KEYWORD_DENSITY.value: 10.0,
    QualityCategory.GRAMMAR_FORMAT.value: 10.0,
}

# Levels assigned from the overall score.
_LEVEL_EXCELLENT = 85.0
_LEVEL_GOOD = 70.0
_LEVEL_ACCEPTABLE = 60.0

_MIN_SECTION_LENGTH = 10
_MIN_COVER_LETTER_BODY_LENGTH = 100
_MIN_WORDS_FOR_DENSITY = 30
_IDEAL_ATS_DENSITY = 0.03
_MAX_ATS_DENSITY = 0.08
_HALLUCINATION_PENALTY = 25.0

_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "for",
        "with",
        "at",
        "of",
        "to",
        "in",
        "on",
        "by",
        "as",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "can",
        "could",
        "should",
        "shall",
        "may",
        "might",
        "must",
        "i",
        "me",
        "my",
        "we",
        "our",
        "you",
        "your",
        "he",
        "she",
        "it",
        "this",
        "that",
        "these",
        "those",
        "am",
        "about",
        "into",
        "over",
        "under",
        "from",
        "up",
        "down",
        "out",
        "off",
        "then",
        "than",
        "so",
        "not",
        "no",
        "if",
        "which",
        "who",
        "whom",
        "whose",
        "what",
        "when",
        "where",
        "why",
        "how",
        "all",
        "any",
        "both",
        "each",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "own",
        "same",
        "too",
        "very",
        "just",
        "also",
        "inc",
        "co",
        "ltd",
        "llc",
        "experience",
        "experienced",
        "year",
        "years",
        "senior",
        "junior",
        "role",
        "position",
        "work",
        "working",
        "worked",
        "team",
        "teams",
        "company",
        "companies",
        "strong",
        "good",
        "excellent",
        "proven",
    }
)

# Recognized technical/professional skills used to spot skill mentions in text.
# Skills that appear in a document but are neither in the profile, the job
# description, nor the matched-skills set are flagged as potential inventions.
# Only unambiguous technical terms are listed to avoid common-English collisions.
_SKILLS_LEXICON: frozenset[str] = frozenset(
    {
        "python",
        "fastapi",
        "django",
        "flask",
        "pandas",
        "numpy",
        "scipy",
        "pytest",
        "sql",
        "postgresql",
        "postgres",
        "mysql",
        "sqlite",
        "mongodb",
        "redis",
        "kafka",
        "elasticsearch",
        "graphql",
        "docker",
        "kubernetes",
        "k8s",
        "terraform",
        "ansible",
        "jenkins",
        "github",
        "gitlab",
        "git",
        "aws",
        "azure",
        "gcp",
        "serverless",
        "lambda",
        "s3",
        "ec2",
        "react",
        "reactjs",
        "angular",
        "vue",
        "vuejs",
        "svelte",
        "javascript",
        "typescript",
        "node",
        "nodejs",
        "express",
        "nextjs",
        "webpack",
        "html",
        "css",
        "scss",
        "sass",
        "tailwind",
        "java",
        "spring",
        "springboot",
        "kotlin",
        "scala",
        "groovy",
        "golang",
        "rust",
        "cpp",
        "csharp",
        "dotnet",
        "php",
        "laravel",
        "ruby",
        "rails",
        "swift",
        "objectivec",
        "flutter",
        "dart",
        "android",
        "ios",
        "matlab",
        "tableau",
        "powerbi",
        "spark",
        "pyspark",
        "hadoop",
        "airflow",
        "dbt",
        "snowflake",
        "bigquery",
        "databricks",
        "tensorflow",
        "pytorch",
        "keras",
        "opencv",
        "scikitlearn",
        "xgboost",
        "selenium",
        "playwright",
        "cypress",
        "junit",
        "apache",
        "nginx",
        "linux",
        "unix",
        "bash",
        "powershell",
        "postman",
        "jira",
        "confluence",
        "slack",
        "notion",
        "figma",
        "photoshop",
        "wordpress",
        "shopify",
        "woocommerce",
        "stripe",
        "paypal",
        "bitbucket",
    }
)

_DEGREE_PATTERN = re.compile(
    r"\b(BSc|B\.?Sc\.?|BA|B\.?A\.?|MSc|M\.?Sc\.?|MA|M\.?A\.?|MBA|PhD|Ph\.?D\.?|"
    r"Bachelor(?:'s)?|Master(?:'s)?|Doctorate|Postgraduate|Engineer(?:'s)? Degree)\b",
    re.IGNORECASE,
)

_CERT_MARKER_PATTERN = re.compile(
    r"(?:certified|certification|certificate|licensed)\b", re.IGNORECASE
)

# Employer-like mentions appear right after these prepositions/verbs.
_COMPANY_NAME = r"[A-Z][A-Za-z0-9&'-]+"
_EMPLOYER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bat\s+(" + _COMPANY_NAME + r"(?:\s+" + _COMPANY_NAME + r")?)\b(?!\.)"),
    re.compile(
        r"(?:worked|working|work|employed|intern)\s+at\s+"
        r"(" + _COMPANY_NAME + r"(?:\s+" + _COMPANY_NAME + r")?)\b(?!\.)"
    ),
    re.compile(
        r"(?:joined|co-founded)\s+(" + _COMPANY_NAME + r"(?:\s+" + _COMPANY_NAME + r")?)\b(?!\.)"
    ),
)

_PLACEHOLDER_PATTERN = re.compile(
    r"\b(TODO|FIXME|XXX|TBD|lorem ipsum|placeholder|sample text)\b|\[insert", re.IGNORECASE
)

_RESUME_SECTIONS: tuple[str, ...] = ("summary", "skills", "experience", "projects")

_GREETING_PATTERN = re.compile(r"\b(dear|hi|hello|to whom it may concern)\b", re.IGNORECASE)
_CLOSING_PATTERN = re.compile(
    r"\b(sincerely|best regards|regards|kind regards|thank you|thanks)\b", re.IGNORECASE
)


def _tokenize(text: str) -> list[str]:
    """Lowercase word tokens; keeps letters, digits and +/# so C++/C# survive."""
    return re.findall(r"[a-z0-9][a-z0-9+#.&'-]*", text.lower())


class AITailoringEvaluator:
    """Deterministic post-generation quality checks for AI-tailored documents.

    Every check is rule-based and free of any AI/ML involvement. It produces a
    structured :class:`QualityReport` with per-category scores, an overall
    tailoring quality score, detected issues, and actionable suggestions.
    """

    def __init__(self, config: TailoringQualityConfig | None = None) -> None:
        self._config = config or get_ai_config().tailoring_quality

    # ── Public API ──────────────────────────────────────────────────────

    def evaluate_resume(
        self,
        sections: Mapping[str, str],
        profile: Any | None = None,  # noqa: ANN401
        job_description: str = "",
        matched_skills: Sequence[str] = (),
    ) -> QualityReport:
        """Evaluate a tailored resume's section dict."""
        return self._evaluate(
            document_type="resume",
            sections=dict(sections),
            text="\n".join(str(v) for v in sections.values() if v),
            profile=profile,
            job_description=job_description,
            keywords=tuple(matched_skills),
            company="",
        )

    def evaluate_cover_letter(
        self,
        body: str,
        profile: Any | None = None,  # noqa: ANN401
        job_description: str = "",
        keywords: Sequence[str] = (),
        company: str = "",
    ) -> QualityReport:
        """Evaluate a cover letter body."""
        return self._evaluate(
            document_type="cover_letter",
            sections={},
            text=body,
            profile=profile,
            job_description=job_description,
            keywords=tuple(keywords),
            company=company,
        )

    # ── Orchestration ───────────────────────────────────────────────────

    def _evaluate(
        self,
        document_type: str,
        sections: dict[str, str],
        text: str,
        profile: Any | None,  # noqa: ANN401
        job_description: str,
        keywords: tuple[str, ...],
        company: str,
    ) -> QualityReport:
        if not self._config.enabled:
            return QualityReport(
                document_type=document_type,
                category_scores={},
                overall_score=100.0,
                overall_quality="excellent",
                needs_revision=False,
                issues=(),
                suggestions=(),
            )

        text = text or ""
        tokens = _tokenize(text)
        profile_skills = self._skill_names(profile)
        profile_employers = self._employer_names(profile)
        profile_institutions = self._institution_names(profile)
        profile_certifications = self._certification_names(profile)
        has_education = bool(getattr(profile, "education", ()))
        full_name = self._full_name(profile)

        job_keywords = self._job_keywords(job_description, profile_skills, keywords)

        scores: dict[str, float] = {}
        issues: list[QualityIssue] = []
        suggestions: list[str] = []

        coverage_score, missing = self._keyword_coverage(tokens, job_keywords)
        scores[QualityCategory.KEYWORD_COVERAGE.value] = coverage_score
        if missing:
            top = ", ".join(sorted(missing)[:5])
            issues.append(
                QualityIssue(
                    category=QualityCategory.KEYWORD_COVERAGE,
                    severity=QualitySeverity.WARNING,
                    message=f"Job keywords missing from the document: {top}",
                )
            )
            suggestions.append(f"Mention the required keyword(s): {top}.")

        factual_score, factual_notes = self._factual_preservation(
            tokens, profile_skills, profile_employers, full_name, document_type
        )
        scores[QualityCategory.FACTUAL_PRESERVATION.value] = factual_score
        for note in factual_notes:
            issues.append(
                QualityIssue(
                    category=QualityCategory.FACTUAL_PRESERVATION,
                    severity=QualitySeverity.WARNING,
                    message=note,
                )
            )

        hallucination_score, hall_issues = self._hallucination(
            text,
            tokens,
            profile_skills,
            profile_employers,
            profile_institutions,
            profile_certifications,
            has_education,
            job_keywords,
            company,
            full_name,
            job_description,
        )
        scores[QualityCategory.HALLUCINATION.value] = hallucination_score
        for issue in hall_issues:
            issues.append(issue)
            suggestions.append(f"Verify or remove possibly invented fact: '{issue.message}'.")

        grammar_score, grammar_issues = self._grammar_format(text, tokens)
        scores[QualityCategory.GRAMMAR_FORMAT.value] = grammar_score
        issues.extend(grammar_issues)

        completeness_score, completeness_issues = self._section_completeness(
            sections, text, document_type
        )
        scores[QualityCategory.SECTION_COMPLETENESS.value] = completeness_score
        issues.extend(completeness_issues)

        density_score, density_issues = self._ats_density(tokens, job_keywords)
        scores[QualityCategory.ATS_KEYWORD_DENSITY.value] = density_score
        issues.extend(density_issues)

        overall = self._overall_score(scores)
        level, needs_revision = self._level_and_gate(overall)

        if needs_revision:
            suggestions.append(
                "Quality is below the configured threshold; regenerate or revise "
                "the document before approval."
            )

        return QualityReport(
            document_type=document_type,
            category_scores=scores,
            overall_score=overall,
            overall_quality=level,
            needs_revision=needs_revision,
            issues=tuple(issues),
            suggestions=tuple(suggestions),
        )

    # ── Profile fact extraction ─────────────────────────────────────────

    @staticmethod
    def _names(profile: Any | None, attr: str, item_attr: str) -> list[str]:  # noqa: ANN401
        """Collect values of `item_attr` from `profile.<attr>` defensively."""
        if profile is None:
            return []
        return [
            str(value)
            for item in getattr(profile, attr, ()) or ()
            if (value := getattr(item, item_attr, None))
        ]

    @classmethod
    def _skill_names(cls, profile: Any | None) -> list[str]:  # noqa: ANN401
        return cls._names(profile, "skills", "name")

    @classmethod
    def _employer_names(cls, profile: Any | None) -> list[str]:  # noqa: ANN401
        return cls._names(profile, "experience", "company")

    @classmethod
    def _institution_names(cls, profile: Any | None) -> list[str]:  # noqa: ANN401
        return cls._names(profile, "education", "institution")

    @classmethod
    def _certification_names(cls, profile: Any | None) -> list[str]:  # noqa: ANN401
        return cls._names(profile, "certifications", "name")

    @staticmethod
    def _full_name(profile: Any | None) -> str:  # noqa: ANN401
        if profile is None:
            return ""
        personal = getattr(profile, "personal_info", None)
        return getattr(personal, "full_name", "") or ""

    # ── Individual category checks ──────────────────────────────────────

    def _job_keywords(
        self,
        job_description: str,
        profile_skills: list[str],
        matched_skills: Sequence[str],
    ) -> set[str]:
        """Skill-like terms a tailored document should reflect."""
        keywords: set[str] = set()
        for token in _tokenize(job_description):
            if token in _SKILLS_LEXICON or token in {s.lower() for s in profile_skills}:
                keywords.add(token)
        for skill in matched_skills:
            norm = skill.strip().lower()
            if norm:
                keywords.add(norm)
        return {k for k in keywords if k not in _STOPWORDS}

    def _keyword_coverage(self, tokens: list[str], keywords: set[str]) -> tuple[float, set[str]]:
        if not keywords:
            return 100.0, set()
        token_set = set(tokens)
        present = {k for k in keywords if k in token_set}
        missing = keywords - present
        if not keywords:
            return 100.0, missing
        score = round((len(present) / len(keywords)) * 100, 1)
        return score, missing

    def _factual_preservation(
        self,
        tokens: list[str],
        skills: list[str],
        employers: list[str],
        full_name: str,
        document_type: str,
    ) -> tuple[float, list[str]]:
        """Fraction of profile facts the document should reflect.

        The tailored resume only contains summary/skills/experience/projects
        sections, so only skills and employers are required facts. Education,
        certifications and the candidate name must never be invented, but are
        not required to appear.
        """
        text = " ".join(tokens)
        notes: list[str] = []
        name_penalty = 10.0
        if document_type == "cover_letter" and full_name and full_name.lower() not in text:
            notes.append("Candidate name missing from the cover letter body")
        else:
            name_penalty = 0.0
        facts = [f.lower() for f in skills + employers if f]
        if not facts:
            score = max(0.0, 100.0 - name_penalty)
            return score, notes
        found = sum(1 for f in facts if f in text)
        score = round(max(0.0, (found / len(facts)) * 100 - name_penalty), 1)
        if found < len(facts):
            missing = ", ".join(sorted({f for f in facts if f not in text})[:5])
            notes.append(f"Profile facts missing from the document: {missing}")
        return score, notes

    def _hallucination(
        self,
        text: str,
        tokens: list[str],
        skills: list[str],
        employers: list[str],
        institutions: list[str],
        certifications: list[str],
        has_education: bool,
        job_keywords: set[str],
        company: str,
        full_name: str,
        job_description: str,
    ) -> tuple[float, list[QualityIssue]]:
        issues: list[QualityIssue] = []
        token_set = set(tokens)
        skill_lower = {s.lower() for s in skills}

        allowed_skills = skill_lower | job_keywords
        mentioned_skills = {t for t in token_set if t in _SKILLS_LEXICON}
        invented_skills = mentioned_skills - allowed_skills
        for skill in sorted(invented_skills):
            issues.append(
                QualityIssue(
                    category=QualityCategory.HALLUCINATION,
                    severity=QualitySeverity.ERROR,
                    message=f"Skill not in profile or job description: '{skill}'",
                )
            )

        allowed_employers = (
            {e.lower() for e in employers + institutions if e}
            | {company.lower()}
            | {full_name.lower() if full_name else ""}
        )
        for mention in self._employer_mentions(text):
            if mention not in allowed_employers:
                issues.append(
                    QualityIssue(
                        category=QualityCategory.HALLUCINATION,
                        severity=QualitySeverity.ERROR,
                        message=f"Employer not in profile: '{mention}'",
                    )
                )

        has_degree = bool(_DEGREE_PATTERN.search(text))
        institutions_lower = {i.lower() for i in institutions if i}
        if has_degree and not has_education:
            issues.append(
                QualityIssue(
                    category=QualityCategory.HALLUCINATION,
                    severity=QualitySeverity.ERROR,
                    message="Education degree mentioned but profile has no education",
                )
            )
        elif (
            has_degree
            and institutions_lower
            and not any(inst in " ".join(tokens) for inst in institutions_lower)
        ):
            issues.append(
                QualityIssue(
                    category=QualityCategory.HALLUCINATION,
                    severity=QualitySeverity.WARNING,
                    message=("Degree mentioned but no profile institution appears in the document"),
                )
            )

        cert_lower = {c.lower() for c in certifications if c}
        job_text = (job_description or "").lower()
        for cert in self._certification_mentions(text):
            aligned = cert in cert_lower or any(c in cert or cert in c for c in cert_lower)
            if aligned or cert in job_text:
                continue
            issues.append(
                QualityIssue(
                    category=QualityCategory.HALLUCINATION,
                    severity=QualitySeverity.ERROR,
                    message=f"Certification not in profile or job description: '{cert}'",
                )
            )

        errors = [i for i in issues if i.severity == QualitySeverity.ERROR]
        score = max(0.0, 100.0 - (_HALLUCINATION_PENALTY * len(errors)))
        return score, issues

    def _employer_mentions(self, text: str) -> set[str]:
        mentions: set[str] = set()
        for pattern in _EMPLOYER_PATTERNS:
            for match in pattern.finditer(text):
                mentions.add(match.group(1).strip().lower())
        return mentions

    def _certification_mentions(self, text: str) -> set[str]:
        mentions: set[str] = set()
        for match in _CERT_MARKER_PATTERN.finditer(text):
            start = match.end()
            window = text[start : start + 40]
            words = re.findall(r"[A-Za-z0-9&.'-]+", window)[:2]
            phrase = " ".join(words).strip().lower()
            if phrase:
                mentions.add(phrase)
        return mentions

    def _grammar_format(self, text: str, tokens: list[str]) -> tuple[float, list[QualityIssue]]:
        score = 100.0
        issues: list[QualityIssue] = []

        match = _PLACEHOLDER_PATTERN.search(text)
        if match:
            score -= 20.0
            issues.append(
                QualityIssue(
                    category=QualityCategory.GRAMMAR_FORMAT,
                    severity=QualitySeverity.ERROR,
                    message=f"Placeholder text detected: '{match.group().strip()[:40]}'",
                )
            )

        if any(ord(ch) < 32 and ch not in "\n\t" for ch in text):
            score -= 20.0
            issues.append(
                QualityIssue(
                    category=QualityCategory.GRAMMAR_FORMAT,
                    severity=QualitySeverity.ERROR,
                    message="Document contains control characters",
                )
            )

        if tokens:
            sentences = [s for s in re.split(r"[.!?]+\s+", text.strip()) if s.strip()]
            avg = len(tokens) / max(1, len(sentences))
            if avg < 4:
                score -= 30.0
                issues.append(
                    QualityIssue(
                        category=QualityCategory.GRAMMAR_FORMAT,
                        severity=QualitySeverity.WARNING,
                        message="Text is too terse; sentences are unusually short",
                    )
                )
            elif avg > 50:
                score -= 30.0
                issues.append(
                    QualityIssue(
                        category=QualityCategory.GRAMMAR_FORMAT,
                        severity=QualitySeverity.WARNING,
                        message="Text contains overly long run-on sentences",
                    )
                )

        if re.search(r" {2,}", text):
            score -= 10.0
            issues.append(
                QualityIssue(
                    category=QualityCategory.GRAMMAR_FORMAT,
                    severity=QualitySeverity.WARNING,
                    message="Document contains double spaces",
                )
            )

        return max(0.0, score), issues

    def _section_completeness(
        self, sections: dict[str, str], text: str, document_type: str
    ) -> tuple[float, list[QualityIssue]]:
        issues: list[QualityIssue] = []
        if document_type == "resume":
            present = 0
            total = len(_RESUME_SECTIONS)
            for name in _RESUME_SECTIONS:
                value = (sections.get(name) or "").strip()
                if len(value) >= _MIN_SECTION_LENGTH:
                    present += 1
                else:
                    issues.append(
                        QualityIssue(
                            category=QualityCategory.SECTION_COMPLETENESS,
                            severity=QualitySeverity.WARNING,
                            message=f"Resume section '{name}' is missing or too short",
                        )
                    )
            score = round((present / total) * 100, 1) if total else 100.0
            return score, issues

        checks = 0
        passes = 0
        if _GREETING_PATTERN.search(text):
            passes += 1
        else:
            issues.append(
                QualityIssue(
                    category=QualityCategory.SECTION_COMPLETENESS,
                    severity=QualitySeverity.WARNING,
                    message="Cover letter has no greeting (e.g. 'Dear Hiring Manager')",
                )
            )
        checks += 1
        if len(text.strip()) >= _MIN_COVER_LETTER_BODY_LENGTH:
            passes += 1
        else:
            issues.append(
                QualityIssue(
                    category=QualityCategory.SECTION_COMPLETENESS,
                    severity=QualitySeverity.WARNING,
                    message="Cover letter body is too short",
                )
            )
        checks += 1
        if _CLOSING_PATTERN.search(text):
            passes += 1
        else:
            issues.append(
                QualityIssue(
                    category=QualityCategory.SECTION_COMPLETENESS,
                    severity=QualitySeverity.WARNING,
                    message="Cover letter has no closing or signature",
                )
            )
        checks += 1
        score = round((passes / checks) * 100, 1) if checks else 100.0
        return score, issues

    def _ats_density(
        self, tokens: list[str], keywords: set[str]
    ) -> tuple[float, list[QualityIssue]]:
        issues: list[QualityIssue] = []
        if not keywords or len(tokens) < _MIN_WORDS_FOR_DENSITY:
            return 100.0, issues
        occurrences = sum(tokens.count(k) for k in keywords)
        density = occurrences / len(tokens)
        if density < _IDEAL_ATS_DENSITY:
            score = 60.0
            issues.append(
                QualityIssue(
                    category=QualityCategory.ATS_KEYWORD_DENSITY,
                    severity=QualitySeverity.WARNING,
                    message="Keyword density is too low for ATS scanning",
                )
            )
        elif density > _MAX_ATS_DENSITY:
            score = 60.0
            issues.append(
                QualityIssue(
                    category=QualityCategory.ATS_KEYWORD_DENSITY,
                    severity=QualitySeverity.WARNING,
                    message="Keyword density is too high; possible keyword stuffing",
                )
            )
        else:
            score = 100.0
        return score, issues

    # ── Aggregation ─────────────────────────────────────────────────────

    def _overall_score(self, scores: dict[str, float]) -> float:
        total_weight = sum(_CATEGORY_WEIGHTS.values())
        weighted = sum(scores.get(cat, 0.0) * w for cat, w in _CATEGORY_WEIGHTS.items())
        if not total_weight:
            return 100.0
        return round(weighted / total_weight, 1)

    def _level_and_gate(self, overall: float) -> tuple[str, bool]:
        needs_revision = overall < self._config.minimum_quality_score
        if overall >= _LEVEL_EXCELLENT:
            return "excellent", needs_revision
        if overall >= _LEVEL_GOOD:
            return "good", needs_revision
        if overall >= _LEVEL_ACCEPTABLE:
            return "acceptable", needs_revision
        return "needs_revision", needs_revision
