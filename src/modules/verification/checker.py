from dataclasses import dataclass
from typing import Optional
import httpx

CLOSED_KEYWORDS = [
    "no longer accepting applications",
    "this job has expired",
    "this job is no longer available",
    "position has been filled",
    "this position has been closed",
    "this posting has closed",
    "the job you are looking for is closed",
    "job posting has been removed",
    "job is no longer open",
    "this role has been closed",
]


@dataclass
class VerificationResult:
    is_active: bool
    status: str  # 'verified_active', 'verified_closed', 'unknown'
    error: Optional[str] = None
    http_code: Optional[int] = None


class JobLinkChecker:
    """Verifies whether a job apply URL is still active and accepting applications."""

    def __init__(self, client: Optional[httpx.Client] = None):
        self.client = client or httpx.Client(
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/json",
            },
            follow_redirects=True,
        )

    def check(self, url: str) -> VerificationResult:
        if not url:
            return VerificationResult(is_active=False, status="verified_closed", error="Empty apply URL")

        try:
            response = self.client.get(url)

            # 1. Direct not found / gone status codes
            if response.status_code in [404, 410]:
                return VerificationResult(
                    is_active=False,
                    status="verified_closed",
                    http_code=response.status_code,
                    error=f"HTTP {response.status_code}",
                )

            # 2. Server errors or other client errors
            if response.status_code >= 400:
                return VerificationResult(
                    is_active=True,  # Don't aggressively close on temporary 500s or 403s
                    status="unknown",
                    http_code=response.status_code,
                    error=f"HTTP {response.status_code}",
                )

            # 3. Content inspection for ATS closure phrases
            text_sample = response.text[:15000].lower()
            for phrase in CLOSED_KEYWORDS:
                if phrase in text_sample:
                    return VerificationResult(
                        is_active=False,
                        status="verified_closed",
                        http_code=response.status_code,
                        error=f"Found closure text: '{phrase}'",
                    )

            return VerificationResult(
                is_active=True,
                status="verified_active",
                http_code=response.status_code,
            )

        except httpx.TimeoutException:
            return VerificationResult(is_active=True, status="unknown", error="Connection timeout")
        except httpx.NetworkError as e:
            return VerificationResult(is_active=True, status="unknown", error=f"Network error: {str(e)}")
        except Exception as e:
            return VerificationResult(is_active=True, status="unknown", error=str(e))
