from google import genai
import json
from django.conf import settings


def extract_grades_from_image(image_file):
    """
    Use Gemini's vision capability to read a report card photo
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

    prompt = """Examine this report card image carefully.
Extract every subject name and its corresponding score.

Return ONLY a valid JSON array with no other text, like this:
[
  {"subject": "Mathematics", "score": 75, "max_score": 100},
  {"subject": "English", "score": 82, "max_score": 100}
]

Rules:
- Use the full subject name as written on the report.
- If the score is a percentage, set max_score to 100.
- If the score is out of a different total (e.g. 45/50), use that total.
- If you cannot read a score clearly, skip that subject.
- Return an empty array [] if you cannot extract any grades.
- Return ONLY the JSON array, nothing else."""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                {
                    "inline_data": {
                        "mime_type": content_type,
                        "data": image_bytes,
                    }
                },
                prompt,
            ],
        )

        raw = response.text.strip()

        # Handle markdown code block wrapping
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[1]
            raw = raw.rsplit('```', 1)[0].strip()

        # Find the JSON array in the response
        start = raw.find('[')
        end = raw.rfind(']') + 1
        if start != -1 and end > start:
            raw = raw[start:end]

        return json.loads(raw)

    except Exception as e:
        return []