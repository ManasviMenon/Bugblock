from groq import Groq
import os
import json
import threading
import time
from database import log_bug, add_xp, get_xp_for_bug, get_user, get_weak_spots
from comm import get_ipc

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
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return "I could not explain this error right now because the AI call failed."


def explain_question_answer(question, error_message):
    prompt = """
A beginner coder got this Python error:

""" + error_message + """

They were asked this learning question:

""" + question + """

Give the direct answer to the question in 2-3 simple sentences.
Be specific, correct, and concise.
If the question is fill-in-the-blank, explicitly state what should replace the blank and why.
If more than one answer could be correct, say that clearly and give one valid example instead of pretending there is only one exact answer.
Do not talk generally about the error unless it helps answer the question.
Answer the question itself, not the original error.
"""
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return "I could not generate the answer right now because the AI call failed."


def evaluate_answer(question, answer, question_number=1):
    if question_number == 3:
        extra_rule = """
This is a fill in the blank question. The student may use any valid text in the blank.
Mark GOOD if:
- They filled in the blank with anything syntactically valid AND gave any explanation
- Their explanation shows they understand why their answer works even if brief
- Their completion is different from the expected answer but still correct

Mark PARTIAL if:
- They gave a valid completion but explanation is weak or unclear
- They explained correctly but their completion has a minor issue

Mark BAD if:
- They gave no completion at all
- Their completion would cause a Python error
- They gave zero explanation

Be lenient. There are many valid ways to fill in a blank. Do not penalise for using different text than expected. A one sentence explanation is enough to pass.
"""
    else:
        extra_rule = """
Mark GOOD if the answer shows genuine understanding even if not perfectly worded.
Mark GOOD if a short answer is factually correct and shows they understood.
Mark PARTIAL if the answer shows some understanding but is incomplete, slightly vague, or missing the why.
Mark BAD if the answer is wrong, vague with no substance, or just rephrases the question.
Mark BAD if they only say what to do without explaining why.
"""

    prompt = """
A student was asked this question about a coding error:

""" + question + """

They answered:

""" + answer + """

""" + extra_rule + """

Reply with only one word: GOOD, PARTIAL, or BAD.
"""
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        result = response.choices[0].message.content.strip().upper()

        if "GOOD" in result:
            return "GOOD"
        elif "PARTIAL" in result:
            return "PARTIAL"
        else:
            return "BAD"
    except Exception as e:
        return "BAD"


def validate_q3(question, error_message):
    prompt = """
A quiz question was generated for a beginner coder who got this error:

""" + error_message + """

The question is:

""" + question + """

Does this question meet ALL of these criteria:
- Is it clearly readable and not confusing
- Does it have a clean blank marked as _____ 
- Is it directly related to the error type above
- Does it not contain broken code or garbled text
- Would a beginner understand what is being asked

Reply with only YES or NO.
"""
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        return "YES" in response.choices[0].message.content.strip().upper()
    except:
        return False


def get_hint(question, answer, error_message, attempt_number, question_number=1, grade="BAD"):
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

Their grade was: """ + grade + """

Context: """ + context + """

This is hint number """ + str(attempt_number) + """.

If the grade is PARTIAL:
- Acknowledge they are somewhat on the right track
- Give a lighter nudge toward what they are missing
- Do not start from zero

If the grade is BAD:
- Give a more foundational hint
- Redirect them toward the right concept or code area

If attempt 1:
- Give a directional clue, point them toward what area to think about without saying what is wrong

If attempt 2:
- Be more specific, point at the exact part of the code or concept they are missing without giving the answer

If attempt 3:
- Get very close, describe what is missing or wrong in plain terms, just make them say the final word themselves

Critical rules:
- NEVER restate or rephrase the question
- NEVER reveal the full answer
- NEVER say generic things like "look at the code carefully" or "think about what Python expects"
- Be specific to this exact question and the answer the student gave
- Warm but direct tone
- No emojis. 1-2 sentences only.
"""
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return "I could not generate a hint right now because the AI call failed."


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
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip().lower()
    except Exception as e:
        return "medium"


def get_questions(error_message, difficulty):
    prompt = """
A beginner coder got this error:

""" + error_message + """

Overall difficulty level: """ + difficulty + """

Generate exactly 3 quiz questions with a clear gradual increase in difficulty.

Question 1 (easiest): Ask them to walk through their thinking about what went wrong and how they would approach fixing it. Do not describe the error, name what is missing, or hint at the fix. Just ask them to explain their reasoning.

Question 2 (medium): Show a short code snippet with a sneaky non-obvious version of the same type of error that looks almost correct at first glance. Ask what Python would do when it runs it and why. Do not describe or hint at what is wrong in the snippet. Make it genuinely tricky. If EASY: slightly harder than original. If MEDIUM: subtle twist. If HARD: looks completely valid but breaks at runtime.

Question 3 (hardest): Show a syntactically valid Python line with ONE clearly missing part replaced by _____.

Rules for this question:
- The code must be realistic and runnable after filling the blank
- Do NOT break function structure (e.g., never do print_____(hello))
- The blank should replace a value, argument, or expression — not punctuation or structure
- The student should be able to fill it with multiple valid answers
- The blank must directly test understanding of the original error
- Ask them to fill in the blank and explain why their answer works
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
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        questions = response.choices[0].message.content.strip().split("\n\n")
        questions = [q.strip() for q in questions if q.strip()]

        if len(questions) >= 3:
            attempts = 0
            while not validate_q3(questions[2], error_message) and attempts < 3:
                attempts += 1
                regen = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": """
Generate ONE fill in the blank question for a beginner coder who got this error:

""" + error_message + """

Rules:
- Show a short incomplete line of code with a blank marked as _____
- The blank must test understanding of this specific error
- Ask them to fill in the blank and explain why
- No broken code, no garbled text, keep it clean and readable
- 2 sentences max
- Return only the question, nothing else
"""}]
                )
                questions[2] = regen.choices[0].message.content.strip()

        return questions[:3]
    except Exception as e:
        return ["What went wrong?", "How would you fix it?", "What does this code do? print_____()"]


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
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        return "NONSENSE" in response.choices[0].message.content.strip().upper()
    except Exception as e:
        return False


def question_user_webview(error_message):
    ipc = get_ipc()
    if not ipc:
        print("Warning: Not connected to VS Code extension, falling back to terminal mode")
        question_user(error_message)
        return

    print("BugBlock detected a bug! Opening quiz in VS Code...\n")

    difficulty = get_difficulty(error_message)
    questions = get_questions(error_message, difficulty)

    ipc.send_quiz(error_message, difficulty, questions)

    # State tracking
    total_hints_used = 0
    total_dont_know = 0
    question_results = []
    needed_hints = False
    attempt_count = [0]
    dont_know_count = [0]
    done = threading.Event()

    def handle_submit(message):
        nonlocal total_hints_used, needed_hints, total_dont_know
        q_num = message.get('questionNumber', 1)
        answer = message.get('answer', '')
        question = questions[q_num - 1]

        lowered = answer.lower().strip()
        if lowered in ["i don't know", "i dont know", "dont know", "do not know", "not sure", "no idea"]:
            total_dont_know += 1
            needed_hints = True
            total_hints_used += 1
            hint = get_hint(question, answer, error_message, 1, q_num, 'BAD')
            ipc.send_feedback('BAD', hint)
            return

        if is_nonsense(answer):
            ipc.send_feedback('BAD', 'That is not a real answer. Take a moment and try again.')
            return

        result = evaluate_answer(question, answer, q_num)
        attempt_count[0] += 1

        if result == 'GOOD':
            question_results.append('GOOD')
            dont_know_count[0] = 0
            attempt_count[0] = 0
            ipc.send_feedback('GOOD', '')
            next_q = q_num + 1
            if next_q <= len(questions):
                time.sleep(1.5)
                ipc.send_next_question(questions[next_q - 1], next_q)
            else:
                finish()

        elif result == 'PARTIAL':
            needed_hints = True
            total_hints_used += 1
            hint = get_hint(question, answer, error_message, attempt_count[0], q_num, 'PARTIAL')
            ipc.send_feedback('PARTIAL', hint)

        else:
            needed_hints = True
            total_hints_used += 1
            hint = get_hint(question, answer, error_message, attempt_count[0], q_num, 'BAD')
            ipc.send_feedback('BAD', hint)

    def handle_skip(message):
        nonlocal needed_hints
        needed_hints = True
        q_num = message.get('questionNumber', 1)
        question = questions[q_num - 1]
        question_results.append('BAD')
        explanation = explain_question_answer(question, error_message)
        ipc.send_feedback('SKIP', explanation)
        dont_know_count[0] = 0
        move_next_or_finish(q_num)

    def move_next_or_finish(q_num):
        dont_know_count[0] = 0
        attempt_count[0] = 0
        next_q = q_num + 1
        if next_q <= len(questions):
            time.sleep(1.5)
            ipc.send_next_question(questions[next_q - 1], next_q)
        else:
            finish()

    def finish():
        error_type = error_message.strip().split("\n")[-1].split(":")[0].strip()
        status = "NEEDED HINTS" if needed_hints else "UNDERSTOOD"
        understood = 0 if needed_hints else 1
        xp_earned = get_xp_for_bug(total_hints_used, understood)

        log_bug(error_type, total_hints_used, understood)
        add_xp(xp_earned)

        session_bugs.append({
            "error_type": error_type,
            "status": status,
            "hints_used": total_hints_used,
            "xp_earned": xp_earned
        })

        user = get_user()
        weak_spots = get_weak_spots()
        weak_spots_data = [
            {"errorType": spot["error_type"], "hints": spot["total_hints"]}
            for spot in weak_spots
        ]

        ipc.send_results(
            xp_earned=xp_earned,
            bug_count=len(session_bugs),
            understood=len([b for b in session_bugs if b["status"] == "UNDERSTOOD"]),
            total_hints=total_hints_used,
            total_xp=user["xp"] if user else 0,
            weak_spots=weak_spots_data
        )
        done.set()

    ipc.on('submitAnswer', handle_submit)
    ipc.on('skipQuestion', handle_skip)

    done.wait()

    def handle_close(message):
        print("Received close signal")
        done.set()

    ipc.on('close', handle_close)


    def question_user(error_message):
        print("\nBugBlock detected a bug!")
        print("You cannot proceed until you understand it.\n")

    difficulty = get_difficulty(error_message)
    print("Difficulty: " + difficulty + "\n")

    questions = get_questions(error_message, difficulty)
    needed_hints = False
    total_hints_used = 0
    total_dont_know = 0
    question_results = []

    for i, question in enumerate(questions):
        question_number = i + 1
        attempt = 0
        dont_know_count = 0

        while True:
            print("\n" + question)
            answer = input("\nYour answer: ").strip()

            lowered = answer.lower().strip()
            if lowered in ["i don't know", "i dont know", "dont know", "do not know", "not sure", "no idea"]:
                dont_know_count += 1
                total_dont_know += 1

                if dont_know_count == 1:
                    total_hints_used += 1
                    hint = get_hint(question, answer, error_message, 1, question_number, "BAD")
                    print("\nNot sure? Here's a clue. " + hint)
                    print("\nTry once more.")
                    needed_hints = True
                    continue
                else:
                    question_results.append("BAD")
                    print("\nHere is the answer:")
                    final = explain_question_answer(question, error_message)
                    print(final)
                    print("\nMoving to next question.")
                    needed_hints = True
                    break

            if len(answer.strip()) < 1 or is_nonsense(answer):
                print("\nThat is not a real answer. Take a moment and try again.")
                continue

            result = evaluate_answer(question, answer, question_number)

            if "GOOD" in result:
                question_results.append("GOOD")
                if attempt == 0:
                    print("\nGood understanding. Moving on.")
                else:
                    print("\nGood, you got there. Moving on.")
                break

            elif "PARTIAL" in result:
                attempt += 1
                needed_hints = True

                if attempt > 3:
                    question_results.append("PARTIAL")
                    print("\nHere is the answer:")
                    final = explain_question_answer(question, error_message)
                    print(final)
                    print("\nMoving to next question.")
                    break
                else:
                    total_hints_used += 1
                    hint = get_hint(question, answer, error_message, attempt, question_number, result)
                    print("\nPartly right. " + hint)
                    print("\nTry again.")

            else:
                attempt += 1
                needed_hints = True

                if attempt > 3:
                    question_results.append("BAD")
                    print("\nHere is the answer:")
                    final = explain_question_answer(question, error_message)
                    print(final)
                    print("\nMoving to next question.")
                    break
                else:
                    total_hints_used += 1
                    hint = get_hint(question, answer, error_message, attempt, question_number)
                    print("\nNot quite. " + hint)
                    print("\nTry again.")

    print("\n What you just learned")
    explanation = ask_ai(error_message)
    print(explanation)
    print("\nNow go fix that bug.")

    error_type = error_message.strip().split("\n")[-1].split(":")[0].strip()
    status = "NEEDED HINTS" if needed_hints else "UNDERSTOOD"
    understood = 0 if needed_hints else 1
    xp_earned = get_xp_for_bug(total_hints_used, understood)

    log_bug(error_type, total_hints_used, understood)
    add_xp(xp_earned)

    print("\nXP earned: +" + str(xp_earned))

    session_bugs.append({
        "error_type": error_type,
        "status": status,
        "hints_used": total_hints_used,
        "dont_know_count": total_dont_know,
        "question_results": question_results,
        "xp_earned": xp_earned
    })


def session_summary():
    from database import get_user, get_weak_spots

    if len(session_bugs) == 0:
        print("\nNo bugs hit this session. Get coding!")
        return

    user = get_user()

    print("\n--- Session Summary ---")
    if user:
        print("Total XP: " + str(user["xp"]) + " | Streak: " + str(user["streak"]) + " days\n")

    print("Bugs hit today: " + str(len(session_bugs)) + "\n")

    for i, bug in enumerate(session_bugs):
        print(str(i + 1) + ". " + bug["error_type"]
            + " — " + bug["status"]
            + " | +" + str(bug["xp_earned"]) + " XP"
            + " | hints: " + str(bug["hints_used"]))

    understood = [b for b in session_bugs if b["status"] == "UNDERSTOOD"]
    needed_help = [b for b in session_bugs if b["status"] == "NEEDED HINTS"]

    print("\n" + str(len(understood)) + " understood independently.")
    print(str(len(needed_help)) + " needed hints.")

    weak_spots = get_weak_spots()
    if weak_spots:
        print("\nYour weak spots:")
        for spot in weak_spots:
            print("- " + spot["error_type"] + " (" + str(spot["total_hints"]) + " hints used across " + str(spot["total_bugs"]) + " bugs)")
        print("\nBugBlock will bring these back as daily challenges.")

    print("\nKeep going. Every bug makes you sharper.")