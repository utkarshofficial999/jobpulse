import io
import re
from typing import Optional
from pypdf import PdfReader

from src.core.logging import logger
from src.modules.embeddings.service import get_embedding_provider

# Curated high-precision tech skills taxonomy
COMMON_TECH_SKILLS = [
    # Languages
    "python", "go", "golang", "rust", "java", "c++", "c#", "typescript", "javascript",
    "sql", "ruby", "scala", "kotlin", "swift", "php", "bash", "r",
    # Frameworks & Libraries
    "fastapi", "django", "flask", "react", "next.js", "nextjs", "vue", "angular",
    "node.js", "nodejs", "express", "spring boot", "spring", "pytorch", "tensorflow",
    "keras", "scikit-learn", "pandas", "numpy", "graphql", "tailwind",
    # Data & Storage
    "postgresql", "postgres", "mysql", "redis", "mongodb", "cassandra", "clickhouse",
    "dynamodb", "elasticsearch", "kafka", "rabbitmq", "celery", "snowflake", "bigquery",
    # DevOps & Infrastructure
    "docker", "kubernetes", "k8s", "aws", "gcp", "azure", "terraform", "ansible",
    "ci/cd", "github actions", "gitlab", "linux", "distributed systems", "microservices",
    "system design", "rest api", "grpc", "pgvector", "llm", "langchain",
]

_SKILL_PATTERNS = [
    (skill, re.compile(rf"\b{re.escape(skill)}\b", re.IGNORECASE))
    for skill in COMMON_TECH_SKILLS
]


class ResumeParser:
    """Parses plaintext or PDF resumes, extracts tech skills, and generates candidate embeddings."""

    @staticmethod
    def extract_text_from_pdf(pdf_bytes: bytes) -> str:
        """Extracts text content from PDF binary stream."""
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            text_parts = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            return "\n".join(text_parts).strip()
        except Exception as e:
            logger.error("Failed to parse PDF resume", error=str(e))
            raise ValueError(f"Could not read PDF resume: {str(e)}")

    @staticmethod
    def extract_text_from_docx(docx_bytes: bytes) -> str:
        """Extracts text content from DOCX binary stream."""
        try:
            import docx
            doc = docx.Document(io.BytesIO(docx_bytes))
            text_parts = [p.text for p in doc.paragraphs if p.text]
            return "\n".join(text_parts).strip()
        except Exception as e:
            logger.error("Failed to parse DOCX resume", error=str(e))
            raise ValueError(f"Could not read DOCX resume: {str(e)}")

    @classmethod
    def extract_text(cls, filename: str, content: bytes) -> str:
        """Dispatches extraction based on file extension."""
        name_lower = filename.lower()
        if name_lower.endswith(".pdf"):
            return cls.extract_text_from_pdf(content)
        elif name_lower.endswith(".docx"):
            return cls.extract_text_from_docx(content)
        else:
            return content.decode("utf-8", errors="ignore").strip()

    @classmethod
    def extract_skills(cls, text: str) -> list[str]:
        """Extracts recognized technical skills from resume text using regex word-boundaries and Gemini LLM."""
        matched_skills: list[str] = []
        text_lower = text.lower()

        for skill, pattern in _SKILL_PATTERNS:
            if pattern.search(text_lower):
                # Canonical display name
                display_name = skill.capitalize()
                if skill in ["sql", "aws", "gcp", "llm", "api", "k8s", "ci/cd"]:
                    display_name = skill.upper()
                elif skill in ["postgresql", "fastapi", "pytorch", "tensorflow", "nextjs", "nodejs", "mongodb"]:
                    display_name = skill
                matched_skills.append(display_name)

        # Enhance with Gemini LLM extraction if available
        try:
            from src.modules.llm.gemini import GeminiService
            if GeminiService.is_available():
                parsed = GeminiService.parse_resume(text)
                if parsed and "skills" in parsed and isinstance(parsed["skills"], list):
                    for sk in parsed["skills"]:
                        if isinstance(sk, str) and len(sk) <= 30:
                            matched_skills.append(sk.strip())
        except Exception as e:
            logger.debug("Gemini skill extraction skipped", error=str(e))

        return sorted(list(set(matched_skills)))

    @classmethod
    def extract_experience_years(cls, text: str) -> Optional[int]:
        """Heuristically extracts stated years of experience."""
        match = re.search(r"(\d+)\+?\s*years?\s*(?:of)?\s*experience", text, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        return None

    @classmethod
    def extract_metadata(cls, text: str) -> dict:
        """Extracts comprehensive candidate profile details from resume text."""
        skills = cls.extract_skills(text)
        exp_years = cls.extract_experience_years(text)
        
        # Heuristic seniority
        seniority = "mid"
        text_lower = text.lower()
        if "staff" in text_lower or "principal" in text_lower:
            seniority = "staff"
        elif "lead" in text_lower or "architect" in text_lower:
            seniority = "lead"
        elif "senior" in text_lower or (exp_years and exp_years >= 5):
            seniority = "senior"
        elif "intern" in text_lower:
            seniority = "intern"
        elif "junior" in text_lower or (exp_years and exp_years <= 2):
            seniority = "entry"

        # Heuristic suggested roles
        suggested_roles = []
        role_keywords = [
            ("Senior Backend Engineer", ["backend", "server", "distributed", "fastapi", "django", "microservices"]),
            ("Staff Software Engineer", ["staff", "principal", "architect"]),
            ("Fullstack Engineer", ["fullstack", "full-stack", "react", "next.js", "frontend and backend"]),
            ("AI / ML Engineer", ["machine learning", "ml", "ai", "pytorch", "tensorflow", "llm"]),
            ("Platform & DevOps", ["devops", "platform", "sre", "infrastructure", "kubernetes", "docker", "terraform"]),
            ("Product Engineer", ["product engineer", "ux", "web"]),
            ("Data Engineer", ["data engineer", "etl", "pipeline", "spark", "snowflake", "bigquery"])
        ]
        for role_name, kws in role_keywords:
            if any(kw in text_lower for kw in kws):
                suggested_roles.append(role_name)

        summary = ""
        # Try Gemini LLM extraction first
        try:
            from src.modules.llm.gemini import GeminiService
            if GeminiService.is_available():
                parsed = GeminiService.parse_resume(text)
                if parsed:
                    if parsed.get("skills"):
                        for sk in parsed["skills"]:
                            if sk and sk not in skills:
                                skills.append(sk)
                    if parsed.get("experience_years"):
                        exp_years = parsed["experience_years"]
                    if parsed.get("seniority"):
                        seniority = parsed["seniority"]
                    if parsed.get("summary"):
                        summary = parsed["summary"]
        except Exception:
            pass

        if not summary:
            first_lines = [l.strip() for l in text.split("\n") if l.strip() and len(l.strip()) > 20]
            summary = " ".join(first_lines[:2]) if first_lines else "Experienced Software Professional"

        return {
            "skills": sorted(list(set(skills))),
            "experience_years": exp_years,
            "seniority": seniority,
            "target_roles": suggested_roles[:3] or ["Software Engineer"],
            "summary": summary
        }

    @classmethod
    def format_profile_for_embedding(
        cls,
        target_roles: list[str],
        target_seniorities: list[str],
        preferred_remote_types: list[str],
        skills: list[str],
        resume_text: Optional[str] = None,
    ) -> str:
        """Creates dense text summarizing candidate intent and background for reverse matching."""
        roles_str = ", ".join(target_roles) if target_roles else "Software Engineer"
        seniority_str = ", ".join(target_seniorities) if target_seniorities else "Any Seniority"
        remote_str = ", ".join(preferred_remote_types) if preferred_remote_types else "Any Workplace"
        skills_str = ", ".join(skills) if skills else "General Software Development"

        resume_snippet = ""
        if resume_text:
            cleaned_resume = " ".join(resume_text.split()[:200])  # approx 200 words
            resume_snippet = f"\nCandidate Background: {cleaned_resume}"

        return (
            f"Target Roles: {roles_str}\n"
            f"Seniority Level: {seniority_str}\n"
            f"Workplace Preference: {remote_str}\n"
            f"Core Competencies: {skills_str}"
            f"{resume_snippet}"
        )

    @classmethod
    def generate_profile_embedding(cls, profile_text: str) -> list[float]:
        """Generates 384-dimensional dense vector for the candidate profile."""
        provider = get_embedding_provider()
        vectors = provider.embed_texts([profile_text])
        return vectors[0]
