"""CV Extraction Agent: unstructured CV text -> structured CVProfile."""

from app.llm.provider import LLMProvider
from app.models import CVProfile

SYSTEM_PROMPT = """\
You are a precise CV information extraction system. Extract structured workforce
information from the CV text you are given.

Rules:
- Extract entity names exactly as written in the CV (do NOT normalize or expand
  abbreviations; a later pipeline stage handles that).
- Skills are capabilities (e.g. Python, Machine Learning, API design); technologies
  are concrete tools/frameworks/platforms (e.g. FastAPI, Docker, PostgreSQL).
- For every skill, technology and project, include a short verbatim quote from the
  CV as evidence.
- Only extract what is actually stated in the CV. Never invent or infer entities
  that are not supported by the text.
- Domains are broad fields of experience (e.g. Artificial Intelligence, Backend
  Development, DevOps).
"""


def extract_profile(cv_text: str, provider: LLMProvider, use_cache: bool = True) -> CVProfile:
    return provider.parse(
        system=SYSTEM_PROMPT,
        user=f"Extract the structured profile from this CV:\n\n{cv_text}",
        schema=CVProfile,
        use_cache=use_cache,
    )
