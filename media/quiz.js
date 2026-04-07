const vscode = acquireVsCodeApi();

let currentQuestionIndex = 0;
let currentQuiz = null;
let hintsUsed = 0;
let currentErrorText = '';

window.addEventListener('load', () => {
    vscode.postMessage({ command: 'ready' });
});

window.addEventListener('message', (event) => {
    const message = event.data;

    switch (message.type) {
        case 'startQuiz':
            currentErrorText = message.data.error || '';
            showState('error-state');
            displayError(message.data);
            setTimeout(() => {
                showState('quiz-state');
                displayQuestion(message.data.questions[0], 1);
            }, 1800);
            break;

        case 'feedback':
            handleFeedback(message.grade, message.hint);
            break;

        case 'nextQuestion':
            displayQuestion(message.data, message.data.number);
            break;

        case 'sessionComplete':
            showState('results-state');
            displayResults(message.data);
            break;

        case 'error':
            alert('Error: ' + message.message);
            break;
    }
});

function showState(stateName) {
    document.querySelectorAll('.state').forEach(s => s.classList.add('hidden'));
    document.getElementById(stateName).classList.remove('hidden');
}

function displayError(data) {
    document.getElementById('error-message').textContent = data.error;
    const badge = document.getElementById('error-difficulty');
    const diff = (data.difficulty || 'medium').toLowerCase();
    const icons = { easy: '🟢', medium: '🟡', hard: '🔴' };
    badge.textContent = (icons[diff] || '⚪') + ' ' + diff.toUpperCase();
    badge.className = `badge ${diff}`;
}

function displayQuestion(question, questionNumber) {
    currentQuestionIndex = questionNumber - 1;
    currentQuiz = question;
    hintsUsed = 0;

    // Mini error bar
    document.getElementById('quiz-error-mini').textContent = currentErrorText;

    // Step dots
    [1, 2, 3].forEach(n => {
        const dot = document.getElementById('step-' + n);
        if (n < questionNumber) {
            dot.className = 'step-dot complete';
        } else if (n === questionNumber) {
            dot.className = 'step-dot active';
        } else {
            dot.className = 'step-dot';
        }
    });

    document.getElementById('progress-label').textContent = `Q${questionNumber} of 3`;
    document.getElementById('question-text').textContent = question.text;
    document.getElementById('answer-input').value = '';
    document.getElementById('answer-input').focus();

    document.getElementById('feedback').classList.add('hidden');
    document.getElementById('hint-area').classList.add('hidden');
    document.getElementById('hint-btn').classList.add('hidden');
    document.getElementById('submit-btn').disabled = false;
    document.getElementById('submit-btn').textContent = 'Submit';
}

document.getElementById('submit-btn').addEventListener('click', () => {
    const answer = document.getElementById('answer-input').value.trim();
    if (!answer) {
        showFeedback('Please type an answer before submitting.', 'bad');
        return;
    }
    vscode.postMessage({
        command: 'submitAnswer',
        questionNumber: currentQuestionIndex + 1,
        answer: answer,
        hintsUsed: hintsUsed
    });
    document.getElementById('submit-btn').disabled = true;
});

document.getElementById('hint-btn').addEventListener('click', () => {
    hintsUsed++;
    document.getElementById('hint-btn').disabled = true;
    vscode.postMessage({
        command: 'getHint',
        questionNumber: currentQuestionIndex + 1,
        hintsRequested: hintsUsed
    });
});


document.getElementById('close-btn').addEventListener('click', () => {
    vscode.postMessage({ command: 'close' });
});

function handleFeedback(grade, hint) {
    if (grade === 'GOOD') {
        showFeedback('✓  Solid answer — you got it.', 'good');
        document.getElementById('submit-btn').disabled = true;
    } else if (grade === 'SKIP') {
        showFeedback('Answer: ' + hint, 'partial');
        document.getElementById('submit-btn').disabled = true;
    } else if (grade === 'PARTIAL') {
        showFeedback("⚡ You're on the right track. Read the hint and try again.", 'partial');
        if (hint) showHint(hint);
        document.getElementById('submit-btn').disabled = false;
    } else {
        showFeedback('✗  Not quite. Check the hint and try again.', 'bad');
        if (hint) showHint(hint);
        document.getElementById('submit-btn').disabled = false;
    }
}

function showFeedback(text, type) {
    const fb = document.getElementById('feedback');
    fb.textContent = text;
    fb.className = `feedback-box ${type}`;
    fb.classList.remove('hidden');
}

function showHint(hintText) {
    document.getElementById('hint-text').textContent = hintText;
    document.getElementById('hint-area').classList.remove('hidden');
    document.getElementById('submit-btn').disabled = false;
}

function displayResults(data) {
    document.getElementById('xp-earned').innerHTML = '+' + data.xpEarned + ' <span>XP</span>';
    document.getElementById('bugs-hit').textContent = data.bugCount;
    document.getElementById('understood').textContent = data.understood;
    document.getElementById('hints-used').textContent = data.totalHints;
    document.getElementById('total-xp').textContent = data.totalXp;

    if (data.weakSpots && data.weakSpots.length > 0) {
        const list = document.getElementById('weak-list');
        list.innerHTML = '';
        data.weakSpots.forEach(spot => {
            const li = document.createElement('li');
            li.textContent = spot.errorType + ' — ' + spot.hints + ' hints';
            list.appendChild(li);
        });
        document.getElementById('weak-spots').classList.remove('hidden');
    }
}
