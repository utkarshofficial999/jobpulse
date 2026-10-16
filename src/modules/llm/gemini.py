import json
from typing import Optional, Any
import httpx

from src.config import settings
from src.core.logging import logger

GEMINI_MODEL = "gemini-3.5-flash"
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiService:
    """Provides LLM capabilities via Google Gemini API."""

    @classmethod
    def is_available(cls) -> bool:
        return bool(settings.GEMINI_API_KEY)

    @classmethod
    def parse_resume(cls, text: str) -> Optional[dict[str, Any]]:
        """
        Extracts structured candidate data from raw resume text using Gemini 3.5 Flash.
        Returns a dict with 'skills', 'experience_years', 'seniority', and 'summary'.
        """
        if not cls.is_available() or not text:
            return None

        prompt = (
            "You are an expert technical recruiter analyzing a candidate's resume.\n"
            "Analyze the following resume text and return ONLY a valid JSON object with the following keys:\n"
            "- \"skills\": list of technical skills, programming languages, databases, cloud tools, and frameworks (e.g. [\"Python\", \"PostgreSQL\", \"Redis\"]).\n"
            "- \"experience_years\": integer number of years of professional experience (or null if unknown).\n"
            "- \"seniority\": estimated seniority level, strictly one of: \"intern\", \"entry\", \"mid\", \"senior\", \"lead\", \"staff\".\n"
            "- \"summary\": concise 1-2 sentence executive summary of the candidate's core specialization.\n\n"
            f"Resume Text:\n{text[:4000]}\n\n"
            "Respond ONLY with the JSON object. Do not include markdown code blocks or additional text."
        )

        url = f"{GEMINI_ENDPOINT}/{GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                content = data["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(content)
        except Exception as e:
            logger.warning("Gemini resume parsing failed, falling back to local heuristics", error=str(e))
            return None

    @classmethod
    def generate_match_pitch(
        cls,
        job_title: str,
        company: str,
        job_description: str,
        candidate_skills: list[str],
        candidate_role: str,
    ) -> str:
        """
        Generates a concise, high-impact 1-sentence explanation of why this job is a fit for the candidate.
        """
        if not cls.is_available():
            matched = ", ".join(candidate_skills[:3])
            return f"Matches target role '{candidate_role}' with overlapping skills in {matched}."

        prompt = (
            f"Write a single sentence explaining why this job is a strong match for this candidate.\n"
            f"Candidate Target: {candidate_role}\n"
            f"Candidate Skills: {', '.join(candidate_skills[:8])}\n"
            f"Job: {job_title} at {company}\n"
            f"Job Description: {job_description[:600]}\n"
            "Format: 1 punchy sentence, no greeting, no quotes, starting with a verb or direct benefit."
        )

        url = f"{GEMINI_ENDPOINT}/{GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 150}
        }

        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        pitch = parts[0]["text"].strip()
                        if pitch:
                            return pitch
                matched = ", ".join(candidate_skills[:3])
                return f"Direct match for {candidate_role} leveraging your background in {matched}."
        except Exception as e:
            logger.debug("Gemini match pitch generation fallback", error=str(e))
            matched = ", ".join(candidate_skills[:3])
            return f"Direct match for {candidate_role} leveraging your background in {matched}."
