import sys
from ai_engine_webview import question_user_webview
from comm import initialize_ipc

if __name__ == "__main__":
    error_text = sys.stdin.read().strip()
    if error_text:
        initialize_ipc()
        question_user_webview(error_text)