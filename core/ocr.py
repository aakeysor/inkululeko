import base64
import json
import logging
from google import genai
from google.genai import types
from django.conf import settings

logger = logging.getLogger(__name__)


def extract_grades_from_image(image_file):
    """
    Use Gemini's vision capability to read a South African report card photo
    and extract structured grade data.

    Returns a list of dicts:
    [{'subject': ..., 'score': ..., 'max_score': ...}, ...]
    """
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    # Read the image bytes
    image_bytes = image_file.read()

    content_type = getattr(image_file, 'content_type', 'image/jpeg')
    if content_type not in ('image/jpeg', 'image/png', 'image/webp'):
        content_type = 'image/jpeg'

    prompt = """Examine this South African school report card image carefully.

This report card may have multiple terms (Term 1, Term 2, Term 3, Final).
Extract ONLY the MOST RECENT term's "Final %" column for each subject.
If a "Final for Year" column exists, use that instead.

Return ONLY a valid JSON array with no other text, like this:
[
  {"subject": "Mathematics", "score": 75, "max_score": 100},
  {"subject": "English", "score": 82, "max_score": 100}
]

Rules:
- Use the CORE subject name only, without grade level suffixes.
  For example: "Mathematics" not "Mathematics (Gr 08)".
  "English" or "English First Additional Language" not "English First Additional Language (Gr 08)".
  "IsiXhosa" or "IsiXhosa Home Language" not "IsiXhosa Home Language (Gr 08)".
- The score is a percentage — set max_score to 100.
- If you cannot read a score clearly, skip that subject.
- Do NOT include the "Learner Total / Average" row.
- Return an empty array [] if you cannot extract any grades.
- Return ONLY the JSON array, nothing else."""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            inline_data=types.Blob(
                                mime_type=content_type,
                                data=image_bytes,
                            )
                        ),
                        types.Part(text=prompt),
                    ],
                )
            ],
        )

        raw = response.text.strip()
        logger.info(f"Gemini OCR raw response: {raw[:500]}")

        # Handle markdown code block wrapping
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[1]
            raw = raw.rsplit('```', 1)[0].strip()

        # Find the JSON array in the response
        start = raw.find('[')
        end = raw.rfind(']') + 1
        if start != -1 and end > start:
            raw = raw[start:end]

        result = json.loads(raw)
        logger.info(f"Gemini OCR extracted {len(result)} grades")
        return result

    except Exception as e:
        logger.error(f"Gemini OCR error: {e}")
        return []