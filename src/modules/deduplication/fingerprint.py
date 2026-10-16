import hashlib
import re
from typing import Sequence

CORPORATE_SUFFIXES = [
    r"\binc\.?\b",
    r"\bincorporated\b",
    r"\bllc\.?\b",
    r"\bcorp\.?\b",
    r"\bcorporation\b",
    r"\bltd\.?\b",
    r"\blimited\b",
    r"\btechnologies\b",
    r"\btechnology\b",
    r"\bco\.?\b",
    r"\bcompany\b",
]

_COMPANY_REGEX = re.compile(
    "|".join(CORPORATE_SUFFIXES),
    re.IGNORECASE,
)


def normalize_company_name(name: str) -> str:
    """
    Normalizes company names by lowercasing, stripping punctuation,
    and removing corporate suffixes like Inc, LLC, Corp.
    E.g. 'Stripe, Inc.' -> 'stripe'
    """
    cleaned = _COMPANY_REGEX.sub("", name)
    cleaned = re.sub(r"[^\w\s]", "", cleaned)
    return " ".join(cleaned.lower().split())


def normalize_job_title(title: str) -> str:
    """
    Normalizes job titles by removing parenthetical metadata,
    special characters, and normalizing whitespace.
    E.g. 'Senior Backend Engineer (Remote - US)' -> 'senior backend engineer'
    """
    # Remove text in parentheses, brackets, or braces
    cleaned = re.sub(r"[\(\[\{].*?[\)\]\}]", "", title)
    # Remove hyphens or pipes with trailing location / department info
    cleaned = re.sub(r"\s+[-|/]\s+.*$", "", cleaned)
    cleaned = re.sub(r"[^\w\s]", "", cleaned)
    return " ".join(cleaned.lower().split())


def extract_primary_region(locations: Sequence[str], remote_type: str = "unknown") -> str:
    """
    Normalizes location to a region indicator to avoid splitting identical jobs
    across different micro-locations if remote or global.
    """
    if remote_type == "remote" or any("remote" in str(loc).lower() for loc in locations):
        return "remote"

    if not locations:
        return "unknown"

    first_loc = str(locations[0]).lower()
    # Normalize common country / region patterns
    if any(k in first_loc for k in ["united states", "usa", "us", "san francisco", "new york", "seattle"]):
        return "us"
    if any(k in first_loc for k in ["united kingdom", "uk", "london"]):
        return "uk"
    if any(k in first_loc for k in ["canada", "toronto", "vancouver"]):
        return "ca"
    if any(k in first_loc for k in ["germany", "berlin", "munich"]):
        return "de"
    if any(k in first_loc for k in ["india", "bangalore", "delhi"]):
        return "in"

    return " ".join(re.sub(r"[^\w\s]", "", first_loc).split()[:2])


def compute_dedup_fingerprint(
    company: str,
    title: str,
    locations: Sequence[str],
    remote_type: str = "unknown",
) -> tuple[str, str, str]:
    """
    Computes (company_normalized, title_normalized, dedup_fingerprint).
    """
    norm_company = normalize_company_name(company)
    norm_title = normalize_job_title(title)
    region = extract_primary_region(locations, remote_type)

    token = f"{norm_company}::{norm_title}::{region}".encode("utf-8")
    fingerprint = hashlib.sha256(token).hexdigest()
    return norm_company, norm_title, fingerprint
