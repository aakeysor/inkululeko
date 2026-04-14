from google import genai
from google.genai import types
from django.conf import settings


def get_chat_response(user_message, user_role, conversation_history=None):
    """
    Send a message to Google Gemini and get a support response.
    """
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    system_prompt = f"""You are a helpful support assistant for the Inkululeko
Database, an after-school support program application used in Makhanda,
South Africa. The program partners with three schools: Ntsika Secondary,
Nombulelo Secondary, and Graeme College.

The user you are speaking with has the role: {user_role}.

Here is what each role can do in the application:

- Admin: View all data, manage users (create/edit), mark attendance,
  record grades, upload report cards, and view any learner's progress.
- Classroom Assistant: Mark attendance for their assigned school's subjects,
  record grades, upload report cards for grade extraction.
- Learner: View their own attendance history, grades, average scores,
  and enrolled subjects.
- Mentor: View their assigned mentees' attendance rates, average scores,
  and detailed progress pages.

The site tracks nine subjects: Mathematics, Physical Science, Life Sciences,
English, Afrikaans, isiXhosa, Geography, History, and Accounting.

Grades follow the South African scale: A (80-100%), B (70-79%), C (60-69%),
D (50-59%), E (40-49%), F (0-39%).

Keep your answers short, friendly, and specific to what the user's role
can actually do. If someone asks about a feature they don't have access to,
let them know which role has that capability. If you don't know the answer,
say so and suggest they contact the program administrators.

Respond in 2-3 sentences maximum."""

    contents = []

    if conversation_history:
        for entry in conversation_history[-5:]:
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part(text=entry['message'])],
                )
            )
            contents.append(
                types.Content(
                    role="model",
                    parts=[types.Part(text=entry['response'])],
                )
            )

    contents.append(
        types.Content(
            role="user",
            parts=[types.Part(text=user_message)],
        )
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
            ),
        )
        return response.text
    except Exception as e:
        return (
            f"DEBUG ERROR: {type(e).__name__}: {e}"
        )