import random
import time
from typing import Optional
from urllib.parse import urlparse
import httpx

from src.config import settings
from src.core.logging import logger
from src.core.rate_limiter import rate_limiter
from src.modules.discovery.base import BaseConnector, RawJobData
from src.modules.sources.models import Source


class GreenhouseConnectorError(Exception):
    """Raised when Greenhouse API request fails after retries."""
    pass


class GreenhouseConnector(BaseConnector):
    """
    Connector for Greenhouse public job board JSON API.
    Endpoint: https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true
    """

    BASE_URL = "https://boards-api.greenhouse.io/v1/boards"

    def __init__(
        self,
        client: Optional[httpx.Client] = None,
        max_retries: int = settings.MAX_CRAWL_RETRIES,
        rate_limit_per_sec: float = settings.DEFAULT_DOMAIN_RATE_LIMIT,
    ):
        self.max_retries = max_retries
        self.rate_limit_per_sec = rate_limit_per_sec
        self.client = client or httpx.Client(
            timeout=httpx.Timeout(
                connect=settings.DEFAULT_TIMEOUT_CONNECT,
                read=settings.DEFAULT_TIMEOUT_READ,
                write=5.0,
                pool=10.0,
            ),
            headers={
                "User-Agent": "PulseAI-JobCrawler/1.0 (+https://pulseai.internal/bot)",
                "Accept": "application/json",
            },
            follow_redirects=True,
        )

    def fetch(self, source: Source) -> list[RawJobData]:
        board_token = source.config.get("board_token")
        if not board_token:
            raise GreenhouseConnectorError(
                f"Source '{source.name}' (id={source.id}) missing required config 'board_token'"
            )

        url = f"{self.BASE_URL}/{board_token}/jobs?content=true"
        domain = urlparse(url).netloc

        attempt = 0
        backoff = 1.0

        while attempt < self.max_retries:
            attempt += 1

            # 1. Domain rate limit check (token bucket)
            rate_limiter.acquire(domain, rate=self.rate_limit_per_sec, wait=True)

            logger.debug(
                "Fetching Greenhouse job board",
                board_token=board_token,
                url=url,
                attempt=attempt,
            )

            try:
                response = self.client.get(url)

                # 2. Check for 429 Too Many Requests
                if response.status_code == 429:
                    retry_after_header = response.headers.get("Retry-After")
                    sleep_time = float(retry_after_header) if retry_after_header else backoff
                    sleep_time += random.uniform(0.5, 1.5)
                    logger.warning(
                        "Greenhouse rate limited (429)",
                        board_token=board_token,
                        retry_after=sleep_time,
                        attempt=attempt,
                    )
                    time.sleep(sleep_time)
                    backoff = min(backoff * 2, 60.0)
                    continue

                # 3. Check for 5xx server errors
                if response.status_code >= 500:
                    logger.warning(
                        "Greenhouse server error",
                        status_code=response.status_code,
                        board_token=board_token,
                        attempt=attempt,
                    )
                    if attempt < self.max_retries:
                        sleep_time = backoff + random.uniform(0.1, 0.5)
                        time.sleep(sleep_time)
                        backoff = min(backoff * 2, 30.0)
                        continue
                    response.raise_for_status()

                # Raise for 4xx client errors (e.g. 404 board not found)
                response.raise_for_status()

                payload = response.json()
                jobs_data = payload.get("jobs", [])

                raw_jobs: list[RawJobData] = []
                for job in jobs_data:
                    external_id = str(job.get("id"))
                    if not external_id:
                        continue
                    raw_jobs.append(RawJobData(external_id=external_id, payload=job))

                logger.info(
                    "Successfully fetched Greenhouse jobs",
                    source_name=source.name,
                    board_token=board_token,
                    job_count=len(raw_jobs),
                )
                return raw_jobs

            except (httpx.TimeoutException, httpx.NetworkError) as e:
                logger.warning(
                    "Network error during Greenhouse fetch",
                    board_token=board_token,
                    error=str(e),
                    attempt=attempt,
                )
                if attempt < self.max_retries:
                    sleep_time = backoff + random.uniform(0.2, 0.8)
                    time.sleep(sleep_time)
                    backoff = min(backoff * 2, 30.0)
                else:
                    raise GreenhouseConnectorError(
                        f"Failed to fetch Greenhouse board '{board_token}' after {self.max_retries} attempts: {e}"
                    ) from e

            except httpx.HTTPStatusError as e:
                logger.error(
                    "HTTP status error during Greenhouse fetch",
                    board_token=board_token,
                    status_code=e.response.status_code,
                    error=str(e),
                )
                raise GreenhouseConnectorError(
                    f"HTTP {e.response.status_code} for board '{board_token}': {e}"
                ) from e

        raise GreenhouseConnectorError(
            f"Failed to fetch Greenhouse board '{board_token}' after {self.max_retries} attempts"
        )
