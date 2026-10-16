from src.modules.users.resume_parser import ResumeParser


def test_extract_skills():
    resume_text = """
    Software Engineer with 4 years of experience building web applications.
    Core proficiencies include Python, FastAPI, PostgreSQL, Redis, Docker, and Kubernetes.
    Familiar with AWS (S3, ECS), Git, and CI/CD automation pipelines.
    """
    skills = ResumeParser.extract_skills(resume_text)

    assert "Python" in skills
    assert "Fastapi" in skills or "fastapi" in skills
    assert "Postgresql" in skills or "postgresql" in skills
    assert "Redis" in skills
    assert "Docker" in skills
    assert "Kubernetes" in skills
    assert "AWS" in skills
    assert "CI/CD" in skills


def test_extract_experience_years():
    assert ResumeParser.extract_experience_years("Senior Engineer with 5+ years of experience in distributed systems.") == 5
    assert ResumeParser.extract_experience_years("Developer having 3 years experience with Go and Rust.") == 3
    assert ResumeParser.extract_experience_years("New graduate seeking junior software role.") is None


def test_format_profile_for_embedding():
    profile_text = ResumeParser.format_profile_for_embedding(
        target_roles=["Backend Engineer", "Platform Engineer"],
        target_seniorities=["mid", "senior"],
        preferred_remote_types=["remote"],
        skills=["Python", "Go", "Docker", "PostgreSQL"],
        resume_text="Extensive experience scaling transactional databases.",
    )

    assert "Target Roles: Backend Engineer, Platform Engineer" in profile_text
    assert "Seniority Level: mid, senior" in profile_text
    assert "Workplace Preference: remote" in profile_text
    assert "Core Competencies: Python, Go, Docker, PostgreSQL" in profile_text
    assert "Extensive experience scaling transactional databases" in profile_text
