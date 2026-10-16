from typing import Any
from src.modules.discovery.base import RawJobData
from src.modules.sources.models import Source
from src.modules.jobs.normalizer import GreenhouseNormalizer
from src.modules.jobs.schemas import (
    NormalizedJob,
    RemoteType,
    EmploymentType,
)


class AshbyNormalizer:
    """Normalizes raw Ashby job payloads into canonical NormalizedJob models."""

    @classmethod
    def extract_locations(cls, payload: dict[str, Any]) -> list[str]:
        locations: list[str] = []
        primary = payload.get("location")
        if primary and isinstance(primary, str):
            clean = primary.strip()
            if clean:
                locations.append(clean)

        for sec in payload.get("secondaryLocations", []):
            if isinstance(sec, dict):
                loc = sec.get("location")
                if loc and isinstance(loc, str):
                    clean = loc.strip()
                    if clean and clean not in locations:
                        locations.append(clean)

        return locations

    @classmethod
    def normalize(cls, raw_job: RawJobData, source: Source) -> NormalizedJob:
        payload = raw_job.payload
        title = payload.get("title", "").strip()
        if not title:
            raise ValueError(f"Job {raw_job.external_id} has empty title")

        company = source.config.get("company_name") or source.name
        locations = cls.extract_locations(payload)

        # Content can be HTML or plain
        description_raw = payload.get("descriptionHtml") or payload.get("descriptionPlain", "")
        description = GreenhouseNormalizer.clean_html(description_raw)

        apply_url = payload.get("jobUrl") or f"https://jobs.ashbyhq.com/{source.config.get('board_token')}/{raw_job.external_id}"
        posted_at = GreenhouseNormalizer.parse_posted_at(payload.get("publishedAt"))

        # Remote check: Ashby explicitly provides isRemote boolean!
        if payload.get("isRemote"):
            remote_type = RemoteType.REMOTE
        else:
            remote_type = GreenhouseNormalizer.classify_remote_type(title, locations, description)

        seniority = GreenhouseNormalizer.classify_seniority(title)

        # Employment type mapping
        emp_raw = str(payload.get("employmentType", "")).lower()
        if "full" in emp_raw:
            employment_type = EmploymentType.FULL_TIME
        elif "part" in emp_raw:
            employment_type = EmploymentType.PART_TIME
        elif "contract" in emp_raw:
            employment_type = EmploymentType.CONTRACT
        elif "intern" in emp_raw:
            employment_type = EmploymentType.INTERNSHIP
        else:
            employment_type = GreenhouseNormalizer.classify_employment_type(payload, title)

        return NormalizedJob(
            external_id=raw_job.external_id,
            title=title,
            company=company,
            locations=locations,
            remote_type=remote_type,
            seniority=seniority,
            employment_type=employment_type,
            description=description,
            apply_url=apply_url,
            posted_at=posted_at,
        )
