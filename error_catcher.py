import subprocess
import sys
from ai_engine import question_user, session_summary

def run_code(filename):
    result = subprocess.run(
        [sys.executable, filename],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        question_user(result.stderr)
    else:
        print("Code ran fine!")

run_code("main.py")
session_summary()