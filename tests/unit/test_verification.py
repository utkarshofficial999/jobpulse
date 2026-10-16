from unittest.mock import MagicMock
import httpx
from src.modules.verification.checker import JobLinkChecker


def test_verification_404_closed():
    mock_client = MagicMock()
    mock_client.get.return_value = httpx.Response(status_code=404, request=httpx.Request("GET", "https://example.com/job/1"))

    checker = JobLinkChecker(client=mock_client)
    res = checker.check("https://example.com/job/1")

    assert res.is_active is False
    assert res.status == "verified_closed"
    assert "404" in res.error


def test_verification_active_page():
    mock_client = MagicMock()
    mock_client.get.return_value = httpx.Response(
        status_code=200,
        text="<html><body><h1>Senior Engineer</h1><button>Apply Now</button></body></html>",
        request=httpx.Request("GET", "https://example.com/job/2"),
    )

    checker = JobLinkChecker(client=mock_client)
    res = checker.check("https://example.com/job/2")

    assert res.is_active is True
    assert res.status == "verified_active"
    assert res.error is None


def test_verification_closed_phrase_detection():
    mock_client = MagicMock()
    mock_client.get.return_value = httpx.Response(
        status_code=200,
        text="<html><body><div>We appreciate your interest. This position has been filled.</div></body></html>",
        request=httpx.Request("GET", "https://example.com/job/3"),
    )

    checker = JobLinkChecker(client=mock_client)
    res = checker.check("https://example.com/job/3")

    assert res.is_active is False
    assert res.status == "verified_closed"
    assert "position has been filled" in res.error


def test_verification_server_error_stays_unknown():
    mock_client = MagicMock()
    mock_client.get.return_value = httpx.Response(status_code=500, request=httpx.Request("GET", "https://example.com/job/4"))

    checker = JobLinkChecker(client=mock_client)
    res = checker.check("https://example.com/job/4")

    # 500 should not mark the job as permanently closed
    assert res.status == "unknown"
    assert res.is_active is True
