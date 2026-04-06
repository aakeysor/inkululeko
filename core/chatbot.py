import ollama
from django.conf import settings

def get_chat_response(user_message, user_role, conversation_history=None):
    """
    Send a message to the local Ollama model and get a support response.
    The bot is aware of the site's features and the user's role.
    """
    system_prompt = f"""You are a helpful support assistant for the Inkululeko
Database, an after-school support program application used in Makhanda,
South Africa. The program partners with three schools: Andrew Moyakhe, 
Nathaniel Nyaluza High School, Ntsika Secondary School

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

Grades follow the South African scale:
- 1: 0.00-29.99
- 2: 30.00-39.00
- 3: 40.00-49.99
- 4: 50.00-59.99
- 5: 60.00-69.99
- 6: 70.00-79.99
- 7: 80.00-100.00

Keep your answers short, friendly, and specific to what the user's role
can actually do. If someone asks about a feature they don't have access to,
let them know which role has that capability. If you don't know the answer,
say so and suggest they contact the program administrators."""

    messages = [{"role": "system", "content": system_prompt}]

    # Include recent conversation history for context
    if conversation_history:
        for entry in conversation_history[-5:]:
            messages.append({"role": "user", "content": entry['message']})
            messages.append({"role": "assistant", "content": entry['response']})

    messages.append({"role": "user", "content": user_message})

    try:
        client = ollama.Client(host=settings.OLLAMA_BASE_URL)
        reponse = client.chat(
            model = settings.OLLAMA_CHAT_MODEL,
            messages = messages
        )
        return response['message']['content']
    except Exception as e:
        return (
            "I'm sorry, I'm having trouble connecting right."
            "Please make sure Ollama is running, or contact the program "
            "administrators directly for help."
        )
