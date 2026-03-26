from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
session_bugs = []


def ask_ai(error_message):
    prompt = """
A beginner coder got this error:

""" + error_message + """

Explain in 2-3 simple sentences what this error means and why it happens.
Imagine you are explaining it to a curious 15 year old who has never seen this before.
Be warm, clear, and specific to this exact error.
No emojis. No bullet points. Just plain conversational explanation.
"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


def evaluate_answer(question, answer, question_number=1):
    if question_number == 3:
        extra_rule = """
This is a fill in the blank question. The student may use any valid text in the blank.
Mark YES if they filled it in with something syntactically correct AND explained why it works.
Mark NO if they gave no explanation or their completion would cause an error.
Do not penalise them for using different text than expected.
"""
    else:
        extra_rule = """
Mark YES if the answer shows genuine understanding even if not perfectly worded.
Mark YES if a short answer is factually correct and shows they understood.
Mark NO if the answer is wrong, vague with no substance, or just rephrases the question.
Mark NO if they only say what to do without explaining why.
"""

    prompt = """
A student was asked this question about a coding error:

""" + question + """

They answered:

""" + answer + """

""" + extra_rule + """

Reply with only YES or NO.
"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip().upper()


def get_hint(question, answer, error_message, attempt_number, question_number=1):
    if question_number == 3:
        context = "This is a fill in the blank question. Hint about what goes in the blank and why, not the original error."
    elif question_number == 2:
        context = "This is a code snippet question. Hint about what is wrong in that specific snippet, not the original error."
    else:
        context = "This is about the original error. Hint about the cause and how to think about fixing it."

    prompt = """
A student got this coding error:

""" + error_message + """

They were asked:

""" + question + """

They answered:

""" + answer + """

Context: """ + context + """

This is hint number """ + str(attempt_number) + """.

If attempt 1: Give a directional clue, point them toward what area to think about without saying what is wrong.
If attempt 2: Be more specific, point at the exact part of the code or concept they are missing without giving the answer.
If attempt 3: Get very close, describe what is missing or wrong in plain terms, just make them say the final word themselves.

Critical rules:
- NEVER restate or rephrase the question
- NEVER reveal the full answer
- NEVER say generic things like "look at the code carefully" or "think about what Python expects"
- Be specific to this exact question and the answer the student gave
- Warm but direct tone
- No emojis. 1-2 sentences only.
"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()


def get_difficulty(error_message):
    prompt = """
A beginner coder got this error:

""" + error_message + """

How complex is this error for a beginner to understand?
Reply with only one word: EASY, MEDIUM, or HARD.

EASY = simple syntax mistakes like missing brackets, quotes, colons
MEDIUM = logic errors, wrong variable types, name errors, index errors
HARD = recursion errors, memory issues, complex runtime errors, async issues
"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip().upper()


def get_questions(error_message, difficulty):
    prompt = """
A beginner coder got this error:

""" + error_message + """

Overall difficulty level: """ + difficulty + """

Generate exactly 3 quiz questions with a clear gradual increase in difficulty.

Question 1 (easiest): Ask them to walk through their thinking about what went wrong and how they would approach fixing it. Do not describe the error, name what is missing, or hint at the fix. Just ask them to explain their reasoning.

Question 2 (medium): Show a short code snippet with a sneaky non-obvious version of the same type of error that looks almost correct at first glance. Ask what Python would do when it runs it and why. Do not describe or hint at what is wrong in the snippet. Make it genuinely tricky. If EASY: slightly harder than original. If MEDIUM: subtle twist. If HARD: looks completely valid but breaks at runtime.

Question 3 (hardest): Show an incomplete line of code with a blank marked as _____. Ask them to fill in the blank and explain why their answer is correct. Do not hint at what should go there. If EASY: blank requires solid understanding. If MEDIUM: blank requires type or logic reasoning. If HARD: blank requires understanding Python internals.

SELF CHECK: Before returning, re-read every question. If any question contains the answer, the fix, what is missing, or what is wrong, rewrite it until it does not. Questions must make students think, not hand them the answer.

Non negotiable rules:
- NEVER mention what is missing, wrong, broken, or needs fixing in the question
- NEVER include the answer or solution in the question
- NEVER ask yes/no questions
- Q3 must be noticeably harder than Q1
- 2 sentences max per question
- Specific to this exact error, not generic
- No emojis, no numbering, no labels like Question 1
- Separate each question with a blank line
- Return only the 3 questions, nothing else
"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    questions = response.choices[0].message.content.strip().split("\n\n")
    return [q.strip() for q in questions if q.strip()]


def is_nonsense(answer):
    prompt = """
A student was asked a question about a coding error and gave this answer:

""" + answer + """

Decide if this is a genuine attempt or not.

Mark GENUINE if:
- They say "I don't know", "not sure", "no idea", "do not know" — genuinely stuck
- They attempt any real explanation even if completely wrong
- They write a sentence showing they actually tried

Mark NONSENSE if:
- They type random letters like "asdfgh"
- They type something completely unrelated like "pizza" or "banana"
- They are clearly mashing keys to skip the question

Reply with only GENUINE or NONSENSE.
"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    return "NONSENSE" in response.choices[0].message.content.strip().upper()


def question_user(error_message):
    print("\nBugBlock detected a bug!")
    print("You cannot proceed until you understand it.\n")

    difficulty = get_difficulty(error_message)
    print("Difficulty: " + difficulty + "\n")

    questions = get_questions(error_message, difficulty)
    needed_hints = False

    for i, question in enumerate(questions):
        question_number = i + 1
        attempt = 0
        while True:
            print("\n" + question)
            answer = input("\nYour answer: ").strip()

            if len(answer.strip()) < 1 or is_nonsense(answer):
                print("\nThat is not a real answer. Take a moment and try again.")
                continue

            result = evaluate_answer(question, answer, question_number)

            if "YES" in result:
                if attempt == 0:
                    print("\nGood understanding. Moving on.")
                else:
                    print("\nGood, you got there. Moving on.")
                break
            else:
                attempt += 1
                needed_hints = True

                if attempt > 3:
                    print("\nHere is the answer:")
                    final = ask_ai("In exactly 2 simple sentences, explain the answer to this question with no fluff: " + question)
                    print(final)
                    print("\nMoving to next question.")
                    break
                else:
                    hint = get_hint(question, answer, error_message, attempt, question_number)
                    print("\nNot quite. " + hint)
                    print("\nTry again.")

    print("\n--- What you just learned ---")
    explanation = ask_ai(error_message)
    print(explanation)
    print("\nNow go fix that bug.")

    error_type = error_message.strip().split("\n")[-1].split(":")[0].strip()
    status = "NEEDED HINTS" if needed_hints else "UNDERSTOOD"
    session_bugs.append({"error_type": error_type, "status": status})


def session_summary():
    if len(session_bugs) == 0:
        print("\nNo bugs hit this session. Get coding!")
        return

    print("\n--- Session Summary ---")
    print("Bugs you hit today: " + str(len(session_bugs)) + "\n")

    for i, bug in enumerate(session_bugs):
        print(str(i + 1) + ". " + bug["error_type"] + " — " + bug["status"])

    understood = [b for b in session_bugs if b["status"] == "UNDERSTOOD"]
    needed_help = [b for b in session_bugs if b["status"] == "NEEDED HINTS"]

    print("\n" + str(len(understood)) + " understood independently.")
    print(str(len(needed_help)) + " needed hints.")
    print("\nKeep going. Every bug makes you sharper.")