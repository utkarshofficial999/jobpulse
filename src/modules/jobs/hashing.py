import hashlib
import json
from src.modules.jobs.schemas import NormalizedJob


def compute_content_hash(job: NormalizedJob) -> str:
    """
    Computes a deterministic SHA-256 digest over normalized canonical fields.
    Does NOT include volatile fields like timestamps or view counters.
    """
    payload = {
        "title": job.title.strip().lower(),
        "company": job.company.strip().lower(),
        "locations": sorted([loc.strip().lower() for loc in job.locations if loc.strip()]),
        "remote_type": job.remote_type.value,
        "seniority": job.seniority.value,
        "employment_type": job.employment_type.value,
        "description": " ".join(job.description.split()),  # normalize whitespaces
        "apply_url": job.apply_url.strip(),
    }

    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
