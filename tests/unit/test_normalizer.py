from src.modules.discovery.base import RawJobData
from src.modules.sources.models import Source
from src.modules.jobs.normalizer import GreenhouseNormalizer
from src.modules.jobs.schemas import RemoteType, Seniority, EmploymentType


def test_clean_html():
    raw_html = "&lt;p&gt;Hello &amp;amp; Welcome!&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Skill A&lt;/li&gt;&lt;li&gt;Skill B&lt;/li&gt;&lt;/ul&gt;"
    cleaned = GreenhouseNormalizer.clean_html(raw_html)
    assert "Hello & Welcome!" in cleaned
    assert "• Skill A" in cleaned
    assert "• Skill B" in cleaned
    assert "<" not in cleaned
    assert "&lt;" not in cleaned


def test_extract_locations():
    payload = {
        "location": {"name": "San Francisco, CA; Remote - US"},
        "offices": [
            {"location": "San Francisco, CA"},
            {"location": "Dublin, Ireland"},
        ],
    }
    locations = GreenhouseNormalizer.extract_locations(payload)
    assert "San Francisco, CA" in locations
    assert "Remote - US" in locations
    assert "Dublin, Ireland" in locations
    # No duplicate San Francisco, CA
    assert locations.count("San Francisco, CA") == 1


def test_classify_remote_type():
    assert GreenhouseNormalizer.classify_remote_type("Staff Engineer - Remote", ["US"], "") == RemoteType.REMOTE
    assert GreenhouseNormalizer.classify_remote_type("Backend Engineer", ["Remote - North America"], "") == RemoteType.REMOTE
    assert GreenhouseNormalizer.classify_remote_type("Product Manager - Hybrid", ["New York, NY"], "") == RemoteType.HYBRID
    assert GreenhouseNormalizer.classify_remote_type("Site Reliability Engineer", ["London, UK"], "") == RemoteType.ONSITE
    assert GreenhouseNormalizer.classify_remote_type("Data Scientist", [], "") == RemoteType.UNKNOWN


def test_classify_seniority():
    assert GreenhouseNormalizer.classify_seniority("Software Engineering Intern") == Seniority.INTERN
    assert GreenhouseNormalizer.classify_seniority("Junior Python Developer") == Seniority.ENTRY
    assert GreenhouseNormalizer.classify_seniority("Associate Cloud Architect") == Seniority.ENTRY
    assert GreenhouseNormalizer.classify_seniority("Senior Backend Engineer") == Seniority.SENIOR
    assert GreenhouseNormalizer.classify_seniority("Lead Data Engineer") == Seniority.LEAD
    assert GreenhouseNormalizer.classify_seniority("Staff Infrastructure Engineer") == Seniority.STAFF
    assert GreenhouseNormalizer.classify_seniority("VP of Engineering") == Seniority.EXECUTIVE
    assert GreenhouseNormalizer.classify_seniority("Head of Product") == Seniority.EXECUTIVE
    assert GreenhouseNormalizer.classify_seniority("Full Stack Developer") == Seniority.UNSPECIFIED


def test_classify_employment_type():
    assert GreenhouseNormalizer.classify_employment_type({}, "Software Engineering Intern") == EmploymentType.INTERNSHIP
    assert GreenhouseNormalizer.classify_employment_type({}, "Contract Backend Developer") == EmploymentType.CONTRACT
    assert GreenhouseNormalizer.classify_employment_type({}, "Part-Time QA Tester") == EmploymentType.PART_TIME
    assert GreenhouseNormalizer.classify_employment_type({}, "Full Stack Engineer") == EmploymentType.FULL_TIME


def test_normalize_full_job():
    source = Source(
        id="src-1",
        name="Stripe",
        connector_type="greenhouse",
        config={"board_token": "stripe", "company_name": "Stripe, Inc."},
    )
    raw_job = RawJobData(
        external_id="12345",
        payload={
            "id": 12345,
            "title": "Senior Distributed Systems Engineer - Remote",
            "updated_at": "2026-10-15T12:00:00Z",
            "absolute_url": "https://boards.greenhouse.io/stripe/jobs/12345",
            "location": {"name": "San Francisco, CA; Remote"},
            "content": "&lt;p&gt;Work on payment pipelines.&lt;/p&gt;",
        },
    )

    normalized = GreenhouseNormalizer.normalize(raw_job, source)

    assert normalized.external_id == "12345"
    assert normalized.title == "Senior Distributed Systems Engineer - Remote"
    assert normalized.company == "Stripe, Inc."
    assert normalized.remote_type == RemoteType.REMOTE
    assert normalized.seniority == Seniority.SENIOR
    assert normalized.employment_type == EmploymentType.FULL_TIME
    assert "Work on payment pipelines." in normalized.description
    assert normalized.apply_url == "https://boards.greenhouse.io/stripe/jobs/12345"
    assert normalized.posted_at is not None
