# BugBlock 🪲

A VS Code extension that turns your Python errors into learning moments. When you save a buggy Python file, BugBlock catches the error, generates a 3-question quiz powered by Groq AI, and locks your editor until you answer — so you actually understand what went wrong.

---

## How it works

1. You save a Python file that has an error
2. BugBlock silently runs the file in the background and catches the error
3. A quiz panel opens beside your editor with 3 questions about the error
4. Your editor is locked — you can't type until you answer all 3 questions
5. Once done, you get an XP summary and your editor unlocks

---

## Installation

### Option A — Install from VSIX (recommended)

1. Download `bugblock-dev-1.0.0.vsix` from the releases
2. Open VS Code → Extensions sidebar → `...` menu → **Install from VSIX...**
3. Select the downloaded file

Or via terminal:
```bash
code --install-extension bugblock-dev-1.0.0.vsix
```

### Option B — Build from source

```bash
git clone https://github.com/your-username/bugblock
cd bugblock
npm install -g @vscode/vsce
vsce package --allow-missing-repository
code --install-extension bugblock-dev-1.0.0.vsix
```

---

## Setup

BugBlock uses the [Groq API](https://console.groq.com) for AI — it's free (14,400 requests/day).

**Set your API key** — one of two ways:

**Option 1:** Create a `.env` file in your workspace root:
```
GROQ_API_KEY=your_key_here
```

**Option 2:** Command palette → `BugBlock: Set Groq API Key`

---

## Requirements

- VS Code 1.75+
- Python 3.8+ installed and accessible as `python` (Windows) or `python3` (Mac/Linux)
- A free Groq API key from [console.groq.com](https://console.groq.com)

---

## Commands

| Command | Description |
|---|---|
| `BugBlock: Set Groq API Key` | Save your Groq API key |
| `BugBlock: Start Learning` | Confirm BugBlock is active |
| `BugBlock: Stop` | Stop BugBlock for the session |

---

## How the quiz works

- **3 questions** per error, each building on the last
- **Hints** available if you're stuck — but they cost XP
- **No skipping** — you must answer each question to move on
- Typing "I don't know" gives you a hint instead of letting you skip
- After 3 questions, you see your XP earned, hints used, and weak spots

---

## Tech stack

| Layer | Tech |
|---|---|
| VS Code Extension | Node.js (extension.js) |
| AI Engine | Python + Groq API (llama-3.3-70b) |
| Extension ↔ Python | TCP IPC on localhost:9876 |
| UI | VS Code Webview (HTML/CSS/JS) |
| Progress tracking | SQLite (database.py) |

---

## Project structure

```
bugblock/
├── extension.js          # VS Code extension entry point
├── package.json          # Extension manifest
├── quiz_runner.py        # Python subprocess entry point
├── ai_engine_webview.py  # Quiz logic + Groq API calls
├── comm.py               # IPC client (Python ↔ extension)
├── database.py           # SQLite XP and progress tracking
├── media/
│   ├── quiz.html         # Webview UI
│   ├── quiz.js           # Webview interactivity
│   └── style.css         # Styles (unused, inlined in quiz.html)
└── requirements.txt      # Python dependencies
```

---

## Python dependencies

```bash
pip install -r requirements.txt
```

---

## License

MIT
