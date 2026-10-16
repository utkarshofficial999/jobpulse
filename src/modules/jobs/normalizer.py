import html
import re
from datetime import datetime, timezone
from typing import Optional, Any
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from src.core.logging import logger
from src.modules.discovery.base import RawJobData
from src.modules.sources.models import Source
from src.modules.jobs.schemas import (
    NormalizedJob,
    RemoteType,
    Seniority,
    EmploymentType,
)


class NormalizationError(Exception):
    pass


class GreenhouseNormalizer:
    """Normalizes raw Greenhouse job payloads into canonical NormalizedJob models."""

    SENIORITY_PATTERNS = [
        (Seniority.INTERN, re.compile(r"\b(intern|internship|co-?op|working student)\b", re.IGNORECASE)),
        (Seniority.ENTRY, re.compile(r"\b(junior|jr\.?|associate|entry level|entry|grad|graduate|level 1|l1)\b", re.IGNORECASE)),
        (Seniority.EXECUTIVE, re.compile(r"\b(director|vp|vice president|head of|chief|c-level|cto|ceo|cio|ciso)\b", re.IGNORECASE)),
        (Seniority.STAFF, re.compile(r"\b(staff|principal|distinguished)\b", re.IGNORECASE)),
        (Seniority.LEAD, re.compile(r"\b(lead|team lead|tech lead)\b", re.IGNORECASE)),
        (Seniority.SENIOR, re.compile(r"\b(senior|sr\.?|level 3|l3|iii)\b", re.IGNORECASE)),
        (Seniority.MID, re.compile(r"\b(mid|intermediate|level 2|l2|ii)\b", re.IGNORECASE)),
    ]

    REMOTE_KEYWORDS = ["remote", "anywhere", "work from home", "wfh", "distributed", "telecommute"]
    HYBRID_KEYWORDS = ["hybrid", "flexible work", "partial remote"]

    @classmethod
    def clean_html(cls, raw_html: Optional[str]) -> str:
        """Decodes HTML entities and converts tags into clean readable text."""
        if not raw_html:
            return ""

        # Unescape HTML entities (e.g., &lt;p&gt; -> <p>)
        unescaped = html.unescape(raw_html)

        # Parse with BeautifulSoup
        soup = BeautifulSoup(unescaped, "html.parser")

        # Remove script and style elements
        for element in soup(["script", "style", "noscript"]):
            element.decompose()

        # Replace break tags and list items with newlines
        for br in soup.find_all("br"):
            br.replace_with("\n")
        for li in soup.find_all("li"):
            li_text = li.get_text().strip()
            li.replace_with(f"\n• {li_text}\n")

        text = soup.get_text(separator="\n")

        # Normalize redundant blank lines
        lines = [line.strip() for line in text.splitlines()]
        cleaned = "\n".join(line for line in lines if line)
        return cleaned

    @classmethod
    def extract_locations(cls, payload: dict[str, Any]) -> list[str]:
        """Extracts and normalizes locations from Greenhouse location or offices."""
        locations: list[str] = []

        # 1. location.name
        location_obj = payload.get("location")
        if isinstance(location_obj, dict):
            loc_name = location_obj.get("name")
            if loc_name and isinstance(loc_name, str):
                # Greenhouse sometimes joins multiple locations with ';'
                for part in loc_name.split(";"):
                    cleaned = part.strip()
                    if cleaned and cleaned not in locations:
                        locations.append(cleaned)

        # 2. offices array
        offices = payload.get("offices", [])
        if isinstance(offices, list):
            for office in offices:
                if isinstance(office, dict):
                    loc = office.get("location") or office.get("name")
                    if loc and isinstance(loc, str):
                        cleaned = loc.strip()
                        if cleaned and cleaned not in locations:
                            locations.append(cleaned)

        return locations

    @classmethod
    def classify_remote_type(cls, title: str, locations: list[str], description: str) -> RemoteType:
        """Determines if a job is remote, hybrid, onsite, or unknown."""
        search_text = f"{title} {' '.join(locations)}".lower()

        # 1. Check title/locations first (strongest indicator)
        for kw in cls.HYBRID_KEYWORDS:
            if kw in search_text:
                return RemoteType.HYBRID

        for kw in cls.REMOTE_KEYWORDS:
            if kw in search_text:
                return RemoteType.REMOTE

        # 2. Check description if title/location is inconclusive
        desc_sample = description[:1000].lower()
        if "hybrid" in desc_sample:
            return RemoteType.HYBRID
        if any(kw in desc_sample for kw in ["100% remote", "fully remote", "remote eligible"]):
            return RemoteType.REMOTE

        # 3. If specific physical locations exist, classify as onsite
        if locations:
            return RemoteType.ONSITE

        return RemoteType.UNKNOWN

    @classmethod
    def classify_seniority(cls, title: str) -> Seniority:
        """Classifies seniority from job title using precedence regex matching."""
        for seniority, pattern in cls.SENIORITY_PATTERNS:
            if pattern.search(title):
                return seniority

        return Seniority.UNSPECIFIED

    @classmethod
    def classify_employment_type(cls, payload: dict[str, Any], title: str) -> EmploymentType:
        """Extracts employment type from metadata or title."""
        title_lower = title.lower()

        if any(k in title_lower for k in ["intern", "internship", "co-op"]):
            return EmploymentType.INTERNSHIP
        if any(k in title_lower for k in ["contract", "contractor", "freelance"]):
            return EmploymentType.CONTRACT
        if any(k in title_lower for k in ["part-time", "part time"]):
            return EmploymentType.PART_TIME
        if any(k in title_lower for k in ["temporary", "temp"]):
            return EmploymentType.TEMPORARY

        # Check greenhouse custom metadata if present
        for meta in payload.get("metadata", []):
            if isinstance(meta, dict):
                name = str(meta.get("name", "")).lower()
                value = str(meta.get("value", "")).lower()
                if "employment" in name or "type" in name:
                    if "full" in value:
                        return EmploymentType.FULL_TIME
                    if "part" in value:
                        return EmploymentType.PART_TIME
                    if "contract" in value:
                        return EmploymentType.CONTRACT

        return EmploymentType.FULL_TIME  # Standard default for salaried roles

    @classmethod
    def parse_posted_at(cls, raw_date: Optional[str]) -> Optional[datetime]:
        """Parses ISO timestamp string into UTC datetime."""
        if not raw_date:
            return None
        try:
            dt = date_parser.parse(raw_date)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt
        except Exception:
            return None

    @classmethod
    def normalize(cls, raw_job: RawJobData, source: Source) -> NormalizedJob:
        """Maps a single Greenhouse RawJobData into a canonical NormalizedJob."""
        payload = raw_job.payload
        title = payload.get("title", "").strip()
        if not title:
            raise NormalizationError(f"Job {raw_job.external_id} has empty title")

        company = source.config.get("company_name") or source.name
        locations = cls.extract_locations(payload)
        description = cls.clean_html(payload.get("content"))
        apply_url = payload.get("absolute_url") or f"https://boards.greenhouse.io/{source.config.get('board_token')}/jobs/{raw_job.external_id}"
        posted_at = cls.parse_posted_at(payload.get("updated_at"))

        remote_type = cls.classify_remote_type(title, locations, description)
        seniority = cls.classify_seniority(title)
        employment_type = cls.classify_employment_type(payload, title)

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
