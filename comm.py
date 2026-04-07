import socket
import json
import os
import threading
from typing import Dict, Any

class IpcClient:
    def __init__(self, port: int = 9876):
        self.port = port
        self.socket = None
        self.message_handlers = {}
        self._buffer = ''

    def connect(self):
        import time
        for attempt in range(5):
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.connect(('localhost', self.port))
                print(f"Connected to BugBlock extension on port {self.port}")
                # Start listening for messages from extension
                t = threading.Thread(target=self._listen, daemon=True)
                t.start()
                return True
            except Exception as e:
                print(f"Connection attempt {attempt + 1} failed: {e}")
                time.sleep(0.5)
        print("Warning: Not connected to VS Code extension, falling back to terminal mode")
        return False

    def _listen(self):
        """Listen for incoming messages from the extension"""
        while self.socket:
            try:
                data = self.socket.recv(4096).decode()
                if not data:
                    break
                self._buffer += data
                while '\n' in self._buffer:
                    line, self._buffer = self._buffer.split('\n', 1)
                    if line.strip():
                        message = json.loads(line.strip())
                        self._handle_message(message)
            except Exception as e:
                break

    def _handle_message(self, message):
        """Route incoming messages to registered handlers"""
        msg_type = message.get('command') or message.get('type')
        if msg_type in self.message_handlers:
            self.message_handlers[msg_type](message)

    def on(self, event: str, handler):
        """Register a handler for a message type"""
        self.message_handlers[event] = handler

    def send(self, message: Dict[str, Any]):
        if not self.socket:
            return False
        try:
            data = json.dumps(message) + '\n'
            self.socket.sendall(data.encode())
            return True
        except Exception as e:
            return False

    def send_quiz(self, error_message: str, difficulty: str, questions: list):
        return self.send({
            'type': 'quiz',
            'data': {
                'error': error_message,
                'difficulty': difficulty,
                'questions': [
                    {'text': q, 'number': i+1}
                    for i, q in enumerate(questions)
                ]
            }
        })

    def send_feedback(self, grade: str, hint: str = ""):
        return self.send({
            'type': 'feedback',
            'grade': grade,
            'hint': hint
        })

    def send_next_question(self, question, question_number: int):
        return self.send({
            'type': 'nextQuestion',
            'data': {
                'text': question,
                'number': question_number
            }
        })

    def send_results(self, xp_earned: int, bug_count: int, understood: int,
                    total_hints: int, total_xp: int, weak_spots: list = None):
        return self.send({
            'type': 'sessionComplete',
            'data': {
                'xpEarned': xp_earned,
                'bugCount': bug_count,
                'understood': understood,
                'totalHints': total_hints,
                'totalXp': total_xp,
                'weakSpots': weak_spots or []
            }
        })

    def close(self):
        if self.socket:
            self.socket.close()
            self.socket = None

ipc_client = None

def initialize_ipc():
    global ipc_client
    port = int(os.getenv('BUGBLOCK_IPC_PORT', 9876))
    ipc_client = IpcClient(port)
    if ipc_client.connect():
        return ipc_client
    return None

def get_ipc():
    return ipc_client