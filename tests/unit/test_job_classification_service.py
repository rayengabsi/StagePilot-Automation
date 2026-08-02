from __future__ import annotations

from app.config.classification import ClassificationConfig
from app.domain.jobs.classification import JobClassification
from app.domain.jobs.entities import NormalizedJob
from app.services.job_classification_service import JobClassificationService


def _job(
    title: str,
    description: str = "",
    requirements: str = "",
    department: str | None = None,
    employment_type: str | None = None,
    remote_status: str | None = None,
    location: str | None = None,
) -> NormalizedJob:
    """Build a normalized job helper."""
    return NormalizedJob(
        external_id="1",
        url="https://example.com/jobs/1",
        title=title,
        company="Example",
        location=location,
        description=description,
        requirements=requirements,
        posted_at=None,
        department=department,
        employment_type=employment_type,
        remote_status=remote_status,
    )


def _classify(job: NormalizedJob) -> JobClassification:
    """Classify a normalized job."""
    return JobClassificationService().classify(job)


def test_backend_engineer() -> None:
    """A Backend Engineer title should classify as backend."""
    result = _classify(_job("Backend Engineer"))

    assert result.specialization == "backend"
    assert result.to_dict()["specialization"] == "backend"


def test_frontend_engineer() -> None:
    """A Frontend Engineer title should classify as frontend."""
    result = _classify(_job("Frontend Engineer"))

    assert result.specialization == "frontend"


def test_full_stack_engineer() -> None:
    """A Full Stack Engineer title should classify as full_stack."""
    result = _classify(_job("Full Stack Engineer"))

    assert result.specialization == "full_stack"


def test_mobile_engineer() -> None:
    """An Android engineer should classify as mobile."""
    result = _classify(_job("Android Engineer"))

    assert result.specialization == "mobile"


def test_devops_engineer() -> None:
    """A DevOps engineer should classify as devops."""
    result = _classify(_job("DevOps Engineer"))

    assert result.specialization == "devops"


def test_cloud_engineer() -> None:
    """A cloud engineer should classify as cloud."""
    result = _classify(_job("AWS Cloud Engineer"))

    assert result.specialization == "cloud"


def test_cybersecurity_analyst() -> None:
    """A cybersecurity analyst should classify as cybersecurity."""
    result = _classify(_job("Cybersecurity Analyst"))

    assert result.specialization == "cybersecurity"


def test_ai_ml_engineer() -> None:
    """A machine learning engineer should classify as ai_ml."""
    result = _classify(_job("Machine Learning Engineer"))

    assert result.specialization == "ai_ml"


def test_data_engineer() -> None:
    """A data engineer should classify as data_engineering."""
    result = _classify(_job("Data Engineer"))

    assert result.specialization == "data_engineering"


def test_qa_engineer() -> None:
    """A QA engineer should classify as qa."""
    result = _classify(_job("QA Engineer"))

    assert result.specialization == "qa"


def test_sre_engineer() -> None:
    """An SRE should classify as sre."""
    result = _classify(_job("Site Reliability Engineer"))

    assert result.specialization == "sre"


def test_platform_engineer() -> None:
    """A platform engineer should classify as platform."""
    result = _classify(_job("Platform Engineer"))

    assert result.specialization == "platform"


def test_embedded_engineer() -> None:
    """An embedded firmware engineer should classify as embedded."""
    result = _classify(_job("Embedded Firmware Engineer"))

    assert result.specialization == "embedded"


def test_product_manager() -> None:
    """A product manager should classify as product."""
    result = _classify(_job("Product Manager"))

    assert result.specialization == "product"


def test_unknown_specialization_is_none() -> None:
    """A generic title with no specialization signal stays None."""
    result = _classify(_job("Software Engineer"))

    assert result.specialization is None


def test_seniority_intern() -> None:
    """An internship title should classify seniority as intern."""
    result = _classify(_job("Software Engineering Intern"))

    assert result.seniority == "intern"
    assert result.employment_type == "internship"


def test_seniority_junior() -> None:
    """A junior title should classify as junior."""
    result = _classify(_job("Junior Software Engineer"))

    assert result.seniority == "junior"


def test_seniority_senior() -> None:
    """A senior title should classify as senior."""
    result = _classify(_job("Senior Backend Engineer"))

    assert result.seniority == "senior"


def test_seniority_lead() -> None:
    """A tech lead should classify as lead."""
    result = _classify(_job("Tech Lead"))

    assert result.seniority == "lead"


def test_seniority_manager_preferred_over_senior() -> None:
    """A Senior Manager should classify as manager, not senior."""
    result = _classify(_job("Senior Manager"))

    assert result.seniority == "manager"


def test_seniority_director() -> None:
    """A director title should classify as director."""
    result = _classify(_job("Director of Engineering"))

    assert result.seniority == "director"


def test_employment_type_full_time() -> None:
    """A full-time role should classify employment type as full_time."""
    result = _classify(_job("Backend Engineer", employment_type="Full-time"))

    assert result.employment_type == "full_time"


def test_employment_type_from_title() -> None:
    """A contract title should classify employment type as contract."""
    result = _classify(_job("Contract Backend Engineer"))

    assert result.employment_type == "contract"


def test_work_mode_remote() -> None:
    """A remote title should classify work mode as remote."""
    result = _classify(_job("Remote Backend Engineer"))

    assert result.work_mode == "remote"


def test_work_mode_hybrid() -> None:
    """A hybrid role should classify work mode as hybrid."""
    result = _classify(_job("Backend Engineer", location="Hybrid"))

    assert result.work_mode == "hybrid"


def test_work_mode_onsite() -> None:
    """An on-site role should classify work mode as onsite."""
    result = _classify(_job("Backend Engineer", description="On-site position in Paris."))

    assert result.work_mode == "onsite"


def test_urgency_urgent() -> None:
    """An urgent posting should classify urgency as urgent."""
    result = _classify(_job("Backend Engineer", description="Urgent hire, start immediately."))

    assert result.urgency == "urgent"


def test_no_urgency_signal() -> None:
    """A posting without urgency signals stays None."""
    result = _classify(_job("Backend Engineer"))

    assert result.urgency is None


def test_conflicting_title_and_description() -> None:
    """Title signals should outweigh description for specialization."""
    result = _classify(
        _job("Backend Engineer", description="Build React frontend UIs with TypeScript.")
    )

    assert result.specialization == "backend"


def test_conflicting_seniority_signals() -> None:
    """Most senior matching level should win."""
    result = _classify(_job("Software Engineer", description="Senior role, 5+ years experience."))

    assert result.seniority == "senior"


def test_multilingual_internship() -> None:
    """French internship variants should classify as intern."""
    result = _classify(_job("Stage Développeur Backend"))

    assert result.seniority == "intern"
    assert result.employment_type == "internship"
    assert result.specialization == "backend"


def test_multilingual_pfe() -> None:
    """French PFE / final-year variants should classify as intern."""
    result = _classify(_job("PFE Développeur Full Stack"))

    assert result.seniority == "intern"
    assert result.employment_type == "internship"
    assert result.specialization == "full_stack"


def test_multilingual_remote() -> None:
    """French remote variants should classify work mode as remote."""
    result = _classify(_job("Développeur Backend", description="Poste en télétravail."))

    assert result.work_mode == "remote"


def test_multilingual_onsite() -> None:
    """French on-site variants should classify work mode as onsite."""
    result = _classify(_job("Développeur Frontend", description="Poste sur site à Paris."))

    assert result.work_mode == "onsite"


def test_multilingual_cdi() -> None:
    """French CDI variants should classify employment type as full_time."""
    result = _classify(_job("Développeur Backend", description="CDI temps plein."))

    assert result.employment_type == "full_time"


def test_empty_job_classifies_to_none() -> None:
    """A job with no signals should produce an all-None classification."""
    result = _classify(_job("Software Engineer"))

    assert result.to_dict() == {
        "specialization": None,
        "seniority": None,
        "employment_type": None,
        "work_mode": None,
        "urgency": None,
    }


def test_classification_is_frozen_and_serializable() -> None:
    """JobClassification should be immutable and JSON-serializable."""
    import json

    result = _classify(_job("Senior Backend Engineer", remote_status="remote"))

    json.dumps(result.to_dict())
    assert result.specialization == "backend"
    assert result.seniority == "senior"
    assert result.work_mode == "remote"


def test_custom_config_overrides_defaults() -> None:
    """A custom config should drive classification without code changes."""
    config = ClassificationConfig(
        title_weight=3.0,
        body_weight=1.0,
        min_score=2.0,
        specializations={"data": ("data",)},
        seniority_levels={"senior": ("senior",)},
        employment_types={"full_time": ("full-time",)},
        work_modes={"remote": ("remote",)},
        urgency=("urgent",),
    )
    service = JobClassificationService(config=config)

    result = service.classify(_job("Senior Data Engineer", remote_status="remote"))

    assert result.specialization == "data"
    assert result.seniority == "senior"
    assert result.work_mode == "remote"
