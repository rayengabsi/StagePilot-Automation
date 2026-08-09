"""Deterministic normalization helpers for extracted profile values.

These helpers normalize raw strings into canonical forms (URLs, emails,
technology names, company names, degree labels). They are pure functions with
no dependencies outside the standard library.
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit

# Technology aliases -> canonical display name.
TECHNOLOGY_ALIASES: dict[str, str] = {
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "node js": "Node.js",
    "reactjs": "React",
    "react.js": "React",
    "react js": "React",
    "react-native": "React Native",
    "reactnative": "React Native",
    "vuejs": "Vue.js",
    "vue.js": "Vue.js",
    "angularjs": "Angular",
    "angular.js": "Angular",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "golang": "Go",
    "go": "Go",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "postgre sql": "PostgreSQL",
    "mssql": "SQL Server",
    "sqlserver": "SQL Server",
    "mysql": "MySQL",
    "redis": "Redis",
    "mongodb": "MongoDB",
    "mongo db": "MongoDB",
    "elasticsearch": "Elasticsearch",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "aws": "AWS",
    "amazon web services": "AWS",
    "azure": "Azure",
    "microsoft azure": "Azure",
    "gcp": "Google Cloud",
    "google cloud": "Google Cloud",
    "google cloud platform": "Google Cloud",
    "firebase": "Firebase",
    "graphql": "GraphQL",
    "rest api": "REST API",
    "restful api": "REST API",
    "html": "HTML",
    "html5": "HTML5",
    "css": "CSS",
    "css3": "CSS3",
    "scss": "SCSS",
    "sass": "Sass",
    "tailwind": "Tailwind CSS",
    "tailwindcss": "Tailwind CSS",
    "bootstrap": "Bootstrap",
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "spring": "Spring",
    "spring boot": "Spring Boot",
    "springboot": "Spring Boot",
    "express": "Express",
    "expressjs": "Express.js",
    "express.js": "Express.js",
    "nextjs": "Next.js",
    "next.js": "Next.js",
    "nestjs": "NestJS",
    "nest.js": "NestJS",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "keras": "Keras",
    "scikit-learn": "scikit-learn",
    "sklearn": "scikit-learn",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "git": "Git",
    "github": "GitHub",
    "gitlab": "GitLab",
    "bitbucket": "Bitbucket",
    "jenkins": "Jenkins",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "terraform": "Terraform",
    "ansible": "Ansible",
    "pytest": "pytest",
    "junit": "JUnit",
    "selenium": "Selenium",
    "cypress": "Cypress",
    "jest": "Jest",
    "mocha": "Mocha",
    "vscode": "VS Code",
    "visual studio code": "VS Code",
    "intellij": "IntelliJ IDEA",
    "webpack": "Webpack",
    "vite": "Vite",
    "redux": "Redux",
    "restful": "RESTful",
}

# Collapse whitespace before matching aliases.
_ALIAS_KEY = re.compile(r"\s+")


def _alias_key(value: str) -> str:
    return _ALIAS_KEY.sub(" ", value.strip().lower().replace("_", " "))


def canonical_technology(name: str) -> str:
    """Return a canonical technology display name, or the input unchanged."""
    key = _alias_key(name)
    return TECHNOLOGY_ALIASES.get(key, name.strip())


def normalize_email(email: str) -> str:
    """Lowercase and trim an email address."""
    return email.strip().lower()


def normalize_url(raw: str) -> str | None:
    """Normalize a URL into a canonical ``https://host/path`` form.

    Adds a scheme when missing (``www...`` or bare domains), lowercases the
    host, strips a trailing slash, and drops fragment/query noise.
    """
    value = raw.strip().rstrip(".,;").strip()
    if not value:
        return None
    value = value.replace(" ", "")
    if not re.search(r"^[a-z][a-z0-9+.-]*://", value, re.IGNORECASE):
        value = f"https://{value}"
    try:
        parts = urlsplit(value)
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    if not host:
        return None
    if parts.scheme not in {"http", "https"}:
        return None
    path = parts.path.rstrip("/")
    result = f"{parts.scheme}://{host}{path}"
    if parts.port:
        result = f"{parts.scheme}://{host}:{parts.port}{path}"
    return result


# Common real-world TLDs (generic + 2-letter country codes). This allowlist
# prevents tech suffixes like ``Node.js`` / ``Next.js`` from being mistaken
# for bare URLs while still accepting domains such as ``myportfolio.io``.
KNOWN_TLDS = frozenset(
    {
        "com",
        "net",
        "org",
        "edu",
        "gov",
        "mil",
        "int",
        "ac",
        "biz",
        "info",
        "io",
        "co",
        "ai",
        "app",
        "dev",
        "me",
        "tech",
        "xyz",
        "online",
        "site",
        "web",
        "cloud",
        "team",
        "world",
        "media",
        "blog",
        "space",
        "live",
        "eu",
        "fr",
        "de",
        "uk",
        "us",
        "ca",
        "au",
        "nz",
        "in",
        "jp",
        "cn",
        "kr",
        "br",
        "mx",
        "ar",
        "cl",
        "ru",
        "ch",
        "se",
        "no",
        "fi",
        "nl",
        "be",
        "at",
        "it",
        "es",
        "pt",
        "pl",
        "ie",
        "dk",
        "cz",
        "gr",
        "hu",
        "ro",
        "bg",
        "hr",
        "si",
        "sk",
        "lt",
        "lv",
        "ee",
        "is",
        "lu",
        "mt",
        "tr",
        "il",
        "ae",
        "sa",
        "qa",
        "eg",
        "ma",
        "tn",
        "za",
        "ng",
        "ke",
        "gh",
        "sg",
        "my",
        "th",
        "id",
        "ph",
        "vn",
        "pk",
        "bd",
        "lk",
        "np",
        "ly",
        "to",
        "tv",
        "fm",
        "gg",
        "je",
        "im",
        "so",
        "sh",
        "cc",
        "ws",
        "la",
        "li",
        "md",
        "mc",
        "cy",
    }
)


def is_plausible_url(raw: str) -> bool:
    """Return True when ``raw`` is a plausible web URL.

    Full ``http(s)://`` URLs and ``www.``-prefixed hosts are always accepted.
    Bare domains are accepted only when their last label is a known TLD, which
    excludes tech artifacts such as ``Node.js`` or ``Next.js``.
    """
    value = raw.strip().rstrip(".,;")
    if not value:
        return False
    if re.match(r"^https?://", value, re.IGNORECASE):
        return True
    if value.lower().startswith("www."):
        return True
    match = re.match(
        r"^(?:[a-z0-9-]{2,}\.)+([a-z]{2,})(?:/.*)?$",
        value,
        re.IGNORECASE,
    )
    if not match:
        return False
    return match.group(1).lower() in KNOWN_TLDS


# Words that indicate a line is a job title rather than a company or location.
ROLE_KEYWORDS = (
    "engineer",
    "developer",
    "designer",
    "manager",
    "analyst",
    "scientist",
    "consultant",
    "architect",
    "specialist",
    "coordinator",
    "director",
    "officer",
    "associate",
    "administrator",
    "operator",
    "intern",
    "internship",
    "fellow",
    "lead",
    "head",
    "supervisor",
    "researcher",
    "instructor",
    "teacher",
    "professor",
    "assistant",
    "support",
    "qa",
    "quality",
    "tester",
    "devops",
    "sre",
    "site reliability",
    "product",
    "program",
    "project",
    "scrum",
    "agile",
    "sales",
    "marketing",
    "finance",
    "hr",
    "human resources",
    "accountant",
    "attorney",
    "lawyer",
    "nurse",
    "physician",
    "driver",
    "technician",
    "trainee",
    "apprentice",
    "freelancer",
    "contractor",
    "principal",
    "staff",
    "senior",
    "junior",
    "mid",
    "ingénieur",
    "ingenieur",
    "ingénieure",
    "développeur",
    "developpeur",
    "développeuse",
    "stagiaire",
    "alternance",
    "chef de projet",
    "chef de projets",
    "chef de produit",
    "responsable",
    "analyste",
    "architecte",
    "technicien",
    "technicienne",
    "assistant",
    "chargé",
    "charge",
    "consultant",
    "encadrant",
)

ROLE_KEYWORDS_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(k) for k in ROLE_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


def looks_like_role(value: str) -> bool:
    """Return True when a line looks like a job title."""
    return ROLE_KEYWORDS_PATTERN.search(value) is not None


EMPLOYMENT_TYPES = (
    "full-time",
    "full time",
    "part-time",
    "part time",
    "contract",
    "freelance",
    "internship",
    "temporary",
    "permanent",
    "volunteer",
)

EMPLOYMENT_TYPE_PATTERN = re.compile(
    r"^(?:\b(?:" + "|".join(re.escape(k) for k in EMPLOYMENT_TYPES) + r")\b)",
    re.IGNORECASE,
)

WORK_MODES = ("remote", "hybrid", "on-site", "onsite", "in-office", "in office")

WORK_MODE_PATTERN = re.compile(
    r"^(?:\b(?:" + "|".join(re.escape(k) for k in WORK_MODES) + r")\b)",
    re.IGNORECASE,
)


def is_employment_type(value: str) -> bool:
    """Return True when a line is only an employment type."""
    return bool(
        re.fullmatch(
            r"(?:\b(?:" + "|".join(re.escape(k) for k in EMPLOYMENT_TYPES) + r")\b)",
            value.strip(),
            re.IGNORECASE,
        )
    )


def is_work_mode(value: str) -> bool:
    """Return True when a line is only a work mode (remote/hybrid/onsite)."""
    return bool(
        re.fullmatch(
            r"(?:\b(?:" + "|".join(re.escape(k) for k in WORK_MODES) + r")\b)",
            value.strip(),
            re.IGNORECASE,
        )
    )


# Degree level keywords ordered so more specific terms are checked first.
DEGREE_KEYWORDS = (
    "bachelor of science",
    "bachelor of arts",
    "bachelor of engineering",
    "bachelor of technology",
    "bachelor",
    "master of science",
    "master of arts",
    "master of engineering",
    "master of business administration",
    "master",
    "phd",
    "doctor of philosophy",
    "doctorate",
    "m.d.",
    "associate degree",
    "associate",
    "licence",
    "licentiate",
    "baccalaureate",
    "diploma",
    "bootcamp",
    "certificate",
    "certification",
    "hnd",
    "b.sc",
    "m.sc",
    "b.eng",
    "m.eng",
    "b.a.",
    "m.a.",
    "b.s.",
    "m.s.",
    "b.tech",
    "engineer's degree",
    "engineering degree",
    "baccalaureat",
)

# Abbreviated degree forms (matched after stripping periods) -> canonical keyword.
DEGREE_ABBREVIATIONS: dict[str, str] = {
    "bsc": "b.sc",
    "msc": "m.sc",
    "bs": "b.s.",
    "ms": "m.s.",
    "ba": "b.a.",
    "ma": "m.a.",
    "beng": "b.eng",
    "meng": "m.eng",
    "btech": "b.tech",
    "mba": "master of business administration",
    "phd": "phd",
    "dphil": "phd",
    "md": "m.d.",
    "hnd": "hnd",
}

DEGREE_KEYWORDS_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(k) for k in DEGREE_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

# Matches a degree label phrase (full or abbreviated) so it can be stripped
# from a line to isolate the field of study.
_DEGREE_LABEL_TOKENS = (
    "bachelor(?: of (?:science|arts|engineering|technology))?",
    "master(?: of (?:science|arts|engineering|technology|business administration))?",
    "doctor(?:ate)? of philosophy",
    "ph\\.?d\\.?",
    "m\\.?b\\.?a\\.?",
    "b\\.?s\\.?(?:c\\.?)?",
    "m\\.?s\\.?(?:c\\.?)?",
    "b\\.?a\\.?",
    "m\\.?a\\.?",
    "b\\.?eng\\.?",
    "m\\.?eng\\.?",
    "b\\.?tech\\.?",
    "m\\.?d\\.?",
    "associate(?: degree)?",
    "licence",
    "licentiate",
    "baccalaureate",
    "diploma",
    "bootcamp",
    "certificate",
    "hnd",
    "engineering degree",
    "engineer's degree",
)

DEGREE_LABEL_RE = re.compile(
    r"\b(?:" + "|".join(_DEGREE_LABEL_TOKENS) + r")(?![a-z0-9])",
    re.IGNORECASE,
)


def detect_degree(degree: str) -> str | None:
    """Return the degree level keyword present in ``degree``, or None.

    Handles both full names (``Bachelor of Science``) and abbreviations such as
    ``B.S.``, ``BSc``, ``M.Sc.`` and ``MBA``.
    """
    lower = degree.lower()
    lower = re.sub(r"[\u00b4`]+", "", lower)
    lower = unicodedata.normalize("NFKD", lower)
    lower = "".join(ch for ch in lower if not unicodedata.combining(ch))
    no_dots = lower.replace(".", "")
    for abbreviation in sorted(DEGREE_ABBREVIATIONS, key=len, reverse=True):
        if re.search(rf"(?<![a-z0-9]){re.escape(abbreviation)}(?![a-z0-9])", no_dots):
            return DEGREE_ABBREVIATIONS[abbreviation]
    for keyword in DEGREE_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", lower):
            return keyword
    return None


# Field-of-study keywords.
FIELD_KEYWORDS = (
    "computer science",
    "software engineering",
    "information technology",
    "information systems",
    "computer engineering",
    "data science",
    "data engineering",
    "artificial intelligence",
    "machine learning",
    "cybersecurity",
    "electrical engineering",
    "mechanical engineering",
    "civil engineering",
    "chemical engineering",
    "mathematics",
    "statistics",
    "physics",
    "chemistry",
    "biology",
    "economics",
    "finance",
    "accounting",
    "marketing",
    "business administration",
    "business",
    "management",
    "law",
    "psychology",
    "medicine",
    "nursing",
    "architecture",
    "design",
    "engineering",
    "informatique",
    "genie logiciel",
    "genie informatique",
    "génie logiciel",
    "génie informatique",
    "science",
    "computer",
    "technologies",
    "telecommunications",
    "networks",
)

FIELD_KEYWORDS_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(k) for k in FIELD_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


def clean_company_name(value: str) -> str:
    """Trim a company name and strip trailing separators/punctuation."""
    value = re.sub(r"[,|/\\;]+$", "", value.strip())
    return re.sub(r"\s+", " ", value).strip()
