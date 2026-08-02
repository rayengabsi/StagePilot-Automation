"""Benchmark resume fixtures with expected extraction ground truth.

Each fixture is a generic, fictional resume plus the fields a high-quality
normalizer should extract. No fixture contains real personal data; all names,
companies, and contact details are invented so the fixtures stay safe to share.

The ground truth mirrors the shape produced by ``ProfileNormalizer`` so the
quality report can compare extracted values directly.
"""

from __future__ import annotations

from typing import Any, TypedDict


class ExpectedEntry(TypedDict, total=False):
    institution: str
    degree: str
    company: str
    title: str
    name: str


class Expected(TypedDict, total=False):
    full_name: str
    email: str
    phone: str
    location: str
    nationality: str
    linkedin_url: str
    github_url: str
    portfolio_url: str
    summary_contains: str
    education: list[ExpectedEntry]
    experience: list[ExpectedEntry]
    projects: list[ExpectedEntry]
    education_count: int
    experience_count: int
    projects_count: int
    skills_min: int
    languages_count: int
    certifications_count: int
    awards_count: int
    publications_count: int


class Fixture(TypedDict):
    name: str
    title: str
    text: str
    expected: Expected


ATS_US_TEXT = """John Carter
Senior Software Engineer
Seattle, WA
Email: john.carter@example.com
Phone: +1 (206) 555-0199
LinkedIn: linkedin.com/in/johncarter
GitHub: github.com/johncarter
Portfolio: https://johncarter.dev

Summary
Senior software engineer with 10 years of experience building distributed
backend systems for e-commerce and fintech platforms.

Experience
Senior Software Engineer | Acme Corp | Seattle, WA
Full-Time
March 2019 - Present
- Led migration of a monolith to Kubernetes, cutting deployment time by 60%.
- Designed event-driven services in Python and Django.
Python
Django
Kubernetes

Software Engineer | Globex Inc
2015 - 2019
- Built REST APIs consumed by 2M+ daily users.
Java
Spring Boot
PostgreSQL

Education
University of Washington
B.S. in Computer Science
GPA: 3.7/4.0
2011 - 2015

Skills
Python, Django, Kubernetes, Java, Spring Boot, PostgreSQL, Docker, AWS

Languages
English (Native), Spanish (Intermediate)

Certifications
AWS Certified Solutions Architect (2020)

Awards
Employee of the Year 2019 - Acme Corp
"""

MODERN_TEXT = """Ava Thompson
ava.thompson@example.com
+1 (415) 555-0132
San Francisco, CA
linkedin.com/in/avathompson
github.com/avathompson
https://avathompson.dev

Full-stack developer focused on React, TypeScript, and Node.js with a strong
background in building accessible, high-performance web applications.

Experience
Senior Frontend Engineer | Bright Labs
Remote
January 2021 - Present
- Rebuilt the design system in React and TypeScript.
- Improved Core Web Vitals, raising Lighthouse scores to 98.
React
TypeScript
Next.js

Frontend Developer | Pixelworks
2018 - 2021
- Shipped 12+ customer-facing features with Vue and GraphQL.
Vue.js
GraphQL

Education
Stanford University
BS Computer Science
2014 - 2018

Projects
Resume Analyzer | React, TypeScript
https://github.com/avathompson/resume-analyzer
Scans resumes and highlights missing keywords.

Dev Notes | Next.js, Tailwind
https://avathompson.dev/dev-notes
A note-taking app with offline-first storage.

Skills
React, TypeScript, Next.js, Node.js, GraphQL, Tailwind CSS, Jest, Cypress

Languages
English (Native), Japanese (N2)

Certifications
Google Cloud Professional Cloud Developer (2022)
"""

EUROPASS_FR_TEXT = """Marie Dupont
ingénieure logiciel
Paris, France
marie.dupont@example.com
+33 6 12 34 56 78

Expérience professionnelle
Ingénieure Logiciel | Tech Solutions
Janvier 2019 - Présent
Développement de microservices en Python et Java.

Développeuse | Startup Labs
2016 - 2019
Applications web full-stack avec Django et React.

Formation
Université de Paris
Master en Informatique
2014 - 2016

École d'ingénieurs
Licence en Génie Logiciel
2011 - 2014

Compétences
Python, Java, Django, React, PostgreSQL, Docker

Langues
Français (natif), Anglais (C1), Espagnol (B2)
"""

ACADEMIC_TEXT = """Dr. Elena Petrova
Associate Professor
elena.petrova@university.edu
+44 20 7946 0958
Oxford, UK
https://orcid.org/0000-0002-1234-5678

Summary
Computational linguist with 15 years of research experience in natural language
processing and 80+ peer-reviewed publications.

Education
University of Cambridge
PhD in Computational Linguistics
2005 - 2009

University of Edinburgh
M.Sc. in Artificial Intelligence
2003 - 2004

Experience
Associate Professor | University of Oxford
2015 - Present
- Lead a lab of 12 researchers working on multilingual NLP.

Research Fellow | University of Cambridge
2010 - 2015
- Developed coreference resolution models.

""" + (
    "Publications\n"
    "Petrova, E. and Zhang, L. (2021). Low-resource machine translation. "
    "Journal of Computational Linguistics.\n"
    "Smith, J. (2019). Attention mechanisms. Conference on Empirical Methods in NLP.\n"
    "\n"
    "Awards\n"
    "Best Paper Award 2021 - ACL\n"
    "Marie Curie Fellowship 2010 - European Commission\n"
    "\n"
    "Languages\n"
    "English (Native), Russian (Native), French (B2)\n"
    "\n"
    "Skills\n"
    "Python, PyTorch, TensorFlow, scikit-learn, Transformers\n"
)

FULLSTACK_TEXT = """Lucas Meyer
Backend Engineer
lucas.meyer@example.com
+49 151 12345678
Berlin, Germany
linkedin.com/in/lucasmeier
github.com/lucasmeier

Backend engineer with 8 years of experience designing resilient APIs and data
pipelines, passionate about Go, PostgreSQL, and clean architecture.

Experience
Senior Backend Engineer | Cloudnetic
Berlin, Germany
Full-Time | Remote
April 2020 - Present
- Architected a multi-tenant billing platform handling 50M events/day.
Go
PostgreSQL
Kafka

Backend Engineer | Datawize
2017 - 2020
Java, Spring Boot, Redis
- Built ETL pipelines processing streaming telemetry.

Education
TU München
B.Sc. in Computer Science
2013 - 2017

Projects
Event Sourcing Playground | Go, PostgreSQL
https://github.com/lucasmeier/event-sourcing
A reference implementation of event-sourced aggregates.

gRPC Gateway | Go, gRPC
https://github.com/lucasmeier/grpc-gateway
Translates REST calls to gRPC.

Skills
Go, PostgreSQL, Kafka, Redis, Java, Spring Boot, Docker, Kubernetes, gRPC

Languages
German (Native), English (C2), French (B1)

Certifications
Certified Kubernetes Administrator (2021)
Linux Foundation

Publications
Meyer, L. (2022). Scaling gRPC services. Go Journal.
"""

CONTACT_MIN_TEXT = """Samira Benali
samira.benali@example.com
+216 53 852 323
Tunis, Tunisia

Skills
Python, SQL, Docker
"""

FIXTURES: list[Fixture] = [
    {
        "name": "ats_us",
        "title": "Classic single-page US ATS resume",
        "text": ATS_US_TEXT,
        "expected": {
            "full_name": "John Carter",
            "email": "john.carter@example.com",
            "phone": "+1 (206) 555-0199",
            "location": "Seattle, WA",
            "linkedin_url": "https://linkedin.com/in/johncarter",
            "github_url": "https://github.com/johncarter",
            "portfolio_url": "https://johncarter.dev",
            "summary_contains": "10 years",
            "education": [
                {"institution": "University of Washington", "degree": "Bachelor of Science"},
            ],
            "experience": [
                {"company": "Acme Corp", "title": "Senior Software Engineer"},
                {"company": "Globex Inc", "title": "Software Engineer"},
            ],
            "education_count": 1,
            "experience_count": 2,
            "projects_count": 0,
            "skills_min": 6,
            "languages_count": 2,
            "certifications_count": 1,
            "awards_count": 1,
            "publications_count": 0,
        },
    },
    {
        "name": "modern",
        "title": "Modern tech resume with portfolio and projects",
        "text": MODERN_TEXT,
        "expected": {
            "full_name": "Ava Thompson",
            "email": "ava.thompson@example.com",
            "phone": "+1 (415) 555-0132",
            "location": "San Francisco, CA",
            "linkedin_url": "https://linkedin.com/in/avathompson",
            "github_url": "https://github.com/avathompson",
            "portfolio_url": "https://avathompson.dev",
            "summary_contains": "Full-stack developer",
            "education": [
                {"institution": "Stanford University", "degree": "Bachelor of Science"},
            ],
            "experience": [
                {"company": "Bright Labs", "title": "Senior Frontend Engineer"},
                {"company": "Pixelworks", "title": "Frontend Developer"},
            ],
            "education_count": 1,
            "experience_count": 2,
            "projects_count": 2,
            "skills_min": 6,
            "languages_count": 2,
            "certifications_count": 1,
            "awards_count": 0,
            "publications_count": 0,
        },
    },
    {
        "name": "europass_fr",
        "title": "French Europass-style resume",
        "text": EUROPASS_FR_TEXT,
        "expected": {
            "full_name": "Marie Dupont",
            "email": "marie.dupont@example.com",
            "phone": "+33 6 12 34 56 78",
            "location": "Paris, France",
            "education": [
                {"institution": "Université de Paris", "degree": "Master"},
                {"institution": "École d'ingénieurs", "degree": "Licence"},
            ],
            "experience": [
                {"company": "Tech Solutions", "title": "Ingénieure Logiciel"},
                {"company": "Startup Labs", "title": "Développeuse"},
            ],
            "education_count": 2,
            "experience_count": 2,
            "projects_count": 0,
            "skills_min": 5,
            "languages_count": 3,
            "certifications_count": 0,
            "awards_count": 0,
            "publications_count": 0,
        },
    },
    {
        "name": "academic",
        "title": "Academic CV with publications and awards",
        "text": ACADEMIC_TEXT,
        "expected": {
            "full_name": "Dr. Elena Petrova",
            "email": "elena.petrova@university.edu",
            "phone": "+44 20 7946 0958",
            "location": "Oxford, UK",
            "summary_contains": "Computational linguist",
            "education": [
                {"institution": "University of Cambridge", "degree": "PhD"},
                {"institution": "University of Edinburgh", "degree": "Master of Science"},
            ],
            "experience": [
                {"company": "University of Oxford", "title": "Associate Professor"},
                {"company": "University of Cambridge", "title": "Research Fellow"},
            ],
            "education_count": 2,
            "experience_count": 2,
            "projects_count": 0,
            "skills_min": 4,
            "languages_count": 3,
            "certifications_count": 0,
            "awards_count": 2,
            "publications_count": 2,
        },
    },
    {
        "name": "fullstack",
        "title": "Comprehensive full-stack resume (DE)",
        "text": FULLSTACK_TEXT,
        "expected": {
            "full_name": "Lucas Meyer",
            "email": "lucas.meyer@example.com",
            "phone": "+49 151 12345678",
            "location": "Berlin, Germany",
            "linkedin_url": "https://linkedin.com/in/lucasmeier",
            "github_url": "https://github.com/lucasmeier",
            "summary_contains": "Backend engineer",
            "education": [
                {"institution": "TU München", "degree": "Bachelor of Science"},
            ],
            "experience": [
                {"company": "Cloudnetic", "title": "Senior Backend Engineer"},
                {"company": "Datawize", "title": "Backend Engineer"},
            ],
            "education_count": 1,
            "experience_count": 2,
            "projects_count": 2,
            "skills_min": 7,
            "languages_count": 3,
            "certifications_count": 1,
            "awards_count": 0,
            "publications_count": 1,
        },
    },
    {
        "name": "contact_min",
        "title": "Sparse contact-only resume",
        "text": CONTACT_MIN_TEXT,
        "expected": {
            "full_name": "Samira Benali",
            "email": "samira.benali@example.com",
            "phone": "+216 53 852 323",
            "location": "Tunis, Tunisia",
            "education_count": 0,
            "experience_count": 0,
            "projects_count": 0,
            "skills_min": 3,
            "languages_count": 0,
            "certifications_count": 0,
            "awards_count": 0,
            "publications_count": 0,
        },
    },
]


def load_fixtures() -> list[Fixture]:
    """Return all benchmark fixtures (a fresh copy each call)."""
    return [dict(f, text=f["text"], expected=dict(f["expected"])) for f in FIXTURES]


def to_jsonable(fixture: Fixture) -> dict[str, Any]:
    return {
        "name": fixture["name"],
        "title": fixture["title"],
        "text": fixture["text"],
        "expected": fixture["expected"],
    }
