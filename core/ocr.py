import ollama
import base64
import json
from django.conf import settings


def extract_grades_from_image(image_file):
    """
    Use LLaVA (a local vision model) to read a report card photo
    and extract structured grade data.
    
    Returns a list of dicts:
    [{'subject': ..., 'score': ..., 'max_score':...}, ...]
    """

    # Read and encode the uploaded image
    image_data = base64.standard_b64encode(image_file.read()).decode('utf-8')

    prompt = """Examine this report card image very carefully.
    Extract every subject name and its corresponding score.
    Return ONLY a valid JSON array with no other text.
    
    Below is a demonstration of the formatting.
    [
        {"subject": "Mathematics", "score": 75, "max_score": 100},
        {"subject": "English", "score": 82, "max_score": 100}
    ]
    
    Your output must follow these rules:
    - Use the full subject name, as written on the report.
    - If the score is a percentage, set max_score to 100.
    - If the score is out of a different total (e.g. 45/50), use that total.
    - If you cannot read a score clearly, skip that subject.
    - Return an empty array [] if you cannot extract any grades.
    - Return ONLY the JSON array. NOTHING ELSE."""

    try:
        client = ollama.Client(host=settings.OLLAMA_BASE_URL)
        repsonse = client.chat(
            model+settings.OLLAMA_VISION_MODEL,
            messages = [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_data],
                }
            ]
        )

        raw = response['messages']['content'].strip()

        # Handle the scenario where model formats response in markdown code block
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[1]
            raw = raw.rawrsplit()

