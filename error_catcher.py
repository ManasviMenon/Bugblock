import subprocess
import sys

def run_code(filename):
    result = subprocess.run(
        [sys.executable, filename],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print("Bug detected!")
        print(result.stderr)
    else:
        print("Code ran fine!")

run_code("main.py")