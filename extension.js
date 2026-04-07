const vscode = require('vscode');
const { spawn } = require('child_process');
const path = require('path');
const net = require('net');
const fs = require('fs');

let bugblockProcess = null;
let quizPanel = null;
let ipcSocket = null;
let ipcServer = null;
let focusTrap = null;
let editBlocker = null;
let statusBarItem = null;
let isUndoing = false;
const IPC_PORT = 9876;

function loadEnvKey(workspaceFolder) {
    if (!workspaceFolder) return null;
    const envPath = path.join(workspaceFolder.uri.fsPath, '.env');
    if (!fs.existsSync(envPath)) return null;
    const content = fs.readFileSync(envPath, 'utf8');
    const match = content.match(/^\s*GROQ_API_KEY\s*=\s*(.+?)\s*$/m);
    if (!match) return null;
    return match[1].trim().replace(/^['"]|['"]$/g, '');
}

async function getApiKey(workspaceFolder) {
    const config = vscode.workspace.getConfiguration('bugblock');
    let apiKey = config.get('groqApiKey');
    if (!apiKey) {
        apiKey = loadEnvKey(workspaceFolder);
        if (apiKey) {
            await config.update('groqApiKey', apiKey, vscode.ConfigurationTarget.Global);
            vscode.window.showInformationMessage('Groq API key loaded from .env and saved to settings.');
        }
    }
    return apiKey;
}

const PYTHON_ERRORS = [
    'SyntaxError', 'NameError', 'TypeError', 'ValueError', 'IndentationError',
    'AttributeError', 'ImportError', 'KeyError', 'IndexError', 'ZeroDivisionError',
    'RuntimeError', 'FileNotFoundError', 'ModuleNotFoundError', 'RecursionError',
    'OverflowError', 'StopIteration', 'UnboundLocalError', 'PermissionError',
    'AssertionError', 'OSError', 'IOError', 'UnicodeDecodeError', 'UnicodeEncodeError',
].join('|');

const ERROR_RE = new RegExp(`(${PYTHON_ERRORS}):\\s*.+`);

// Run the saved Python file silently and parse any error from stderr
function runAndCatchError(filePath) {
    return new Promise((resolve) => {
        const pythonPath = process.platform === 'win32' ? 'python' : 'python3';
        const child = spawn(pythonPath, [filePath], { stdio: ['ignore', 'ignore', 'pipe'] });

        let stderr = '';
        child.stderr.on('data', d => stderr += d.toString());
        child.on('close', () => {
            if (!stderr.trim()) return resolve(null);

            const lines = stderr.replace(/\r\n/g, '\n').split('\n');

            // Full traceback
            const tbIdx = lines.findIndex(l => l.includes('Traceback (most recent call last):'));
            if (tbIdx !== -1) {
                const relevant = lines.slice(tbIdx).filter(l => l.trim());
                if (relevant.length > 1) return resolve(relevant.slice(0, 15).join('\n'));
            }

            // SyntaxError (no traceback header)
            const fileIdx = lines.findIndex(l => /^\s*File ".+", line \d+/.test(l));
            const errIdx  = lines.findIndex(l => ERROR_RE.test(l.trim()));
            if (errIdx !== -1) {
                const start = fileIdx !== -1 && fileIdx < errIdx ? fileIdx : errIdx;
                return resolve(lines.slice(start, errIdx + 1).filter(l => l.trim()).join('\n').trim());
            }

            resolve(null);
        });
    });
}

function setupSaveWatcher(context, apiKey) {
    console.log('BugBlock save watcher registered');

    const watcher = vscode.workspace.onDidSaveTextDocument(async (doc) => {
        if (doc.languageId !== 'python') return;
        if (bugblockProcess || quizPanel) return;

        const error = await runAndCatchError(doc.uri.fsPath);
        if (error) {
            if (!ipcServer) ipcServer = setupIpcServer(context);
            triggerQuiz(apiKey, context, error);
        }
    });

    context.subscriptions.push(watcher);
}

function activate(context) {
    console.log('BugBlock extension activated');
    vscode.window.showInformationMessage('BugBlock activated');

    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];

    getApiKey(workspaceFolder)
        .then((apiKey) => {
            if (apiKey) {
                setupSaveWatcher(context, apiKey);
                vscode.window.showInformationMessage('BugBlock is watching for errors. Save a Python file to trigger.');
            } else {
                vscode.window.showWarningMessage(
                    'BugBlock: No API key found. Set it now?',
                    'Set API Key'
                ).then(choice => {
                    if (choice === 'Set API Key') {
                        vscode.commands.executeCommand('bugblock.setApiKey');
                    }
                });
            }
        })
        .catch((err) => {
            console.error('BugBlock activation error:', err);
            vscode.window.showErrorMessage('BugBlock failed to start: ' + err.message);
        });

    let setApiKeyCommand = vscode.commands.registerCommand('bugblock.setApiKey', async () => {
        const config = vscode.workspace.getConfiguration('bugblock');
        const apiKey = await vscode.window.showInputBox({
            prompt: 'Enter your Groq API Key',
            password: true,
            value: config.get('groqApiKey') || ''
        });
        if (apiKey) {
            await config.update('groqApiKey', apiKey, vscode.ConfigurationTarget.Global);
            vscode.window.showInformationMessage('Groq API Key saved!');
        }
    });

    let startCommand = vscode.commands.registerCommand('bugblock.start', async () => {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        const apiKey = await getApiKey(workspaceFolder);
        if (!apiKey) {
            const response = await vscode.window.showWarningMessage(
                'Groq API Key not set. Set it now?', 'Yes', 'Cancel'
            );
            if (response === 'Yes') vscode.commands.executeCommand('bugblock.setApiKey');
            return;
        }
        vscode.window.showInformationMessage('BugBlock is watching your terminal. Run a Python file to trigger a quiz on any error.');
    });

    let stopCommand = vscode.commands.registerCommand('bugblock.stop', () => {
        stopBugBlock();
        vscode.window.showInformationMessage('BugBlock stopped.');
    });

    context.subscriptions.push(setApiKeyCommand, startCommand, stopCommand);
}

function triggerQuiz(apiKey, context, errorText) {
    const pythonPath = process.platform === 'win32' ? 'python' : 'python3';

    if (!ipcSocket) {
        setTimeout(() => spawnQuizProcess(pythonPath, context, apiKey, errorText), 500);
    } else {
        spawnQuizProcess(pythonPath, context, apiKey, errorText);
    }

    vscode.window.showInformationMessage('BugBlock detected an error! Opening quiz...');
}

function spawnQuizProcess(pythonPath, context, apiKey, errorText) {
    bugblockProcess = spawn(pythonPath, ['quiz_runner.py'], {
        cwd: context.extensionPath,
        env: {
            ...process.env,
            GROQ_API_KEY: apiKey,
            BUGBLOCK_IPC_PORT: IPC_PORT.toString()
        },
        stdio: ['pipe', 'pipe', 'pipe']
    });

    bugblockProcess.stdin.write(errorText);
    bugblockProcess.stdin.end();

    bugblockProcess.stdout.on('data', d => console.log('[BugBlock]', d.toString()));
    bugblockProcess.stderr.on('data', d => console.error('[BugBlock Error]', d.toString()));
    bugblockProcess.on('close', () => { bugblockProcess = null; });
}

function stopBugBlock() {
    if (focusTrap)    { focusTrap.dispose();    focusTrap = null; }
    if (editBlocker)  { editBlocker.dispose();  editBlocker = null; }
    if (statusBarItem){ statusBarItem.dispose(); statusBarItem = null; }
    if (bugblockProcess) { bugblockProcess.kill(); bugblockProcess = null; }
    if (ipcSocket)    { ipcSocket.destroy();    ipcSocket = null; }
    if (quizPanel)    { quizPanel.dispose();    quizPanel = null; }
}

function setupIpcServer(context) {
    const server = net.createServer((socket) => {
        ipcSocket = socket;

        let buffer = '';
        socket.on('data', (data) => {
            buffer += data.toString();
            const lines = buffer.split('\n');
            buffer = lines.pop(); // keep incomplete last fragment
            for (const line of lines) {
                const trimmed = line.trim();
                if (!trimmed) continue;
                try {
                    const message = JSON.parse(trimmed);
                    handlePythonMessage(message, context);
                } catch (e) {
                    console.error('Failed to parse IPC message:', e);
                }
            }
        });

        socket.on('end', () => { ipcSocket = null; });
        socket.on('error', (err) => console.error('IPC Socket error:', err));
    });

    server.on('error', (err) => {
        console.error('BugBlock IPC server error:', err);
        if (err.code === 'EADDRINUSE') {
            vscode.window.showErrorMessage(`BugBlock: Port ${IPC_PORT} is already in use. Restart VS Code to clear it.`);
        }
    });

    server.listen(IPC_PORT, 'localhost', () => {
        console.log(`BugBlock IPC server listening on port ${IPC_PORT}`);
    });

    context.subscriptions.push({ dispose: () => server.close() });
    return server;
}

function handlePythonMessage(message, context) {
    console.log('Message from Python:', message.type);

    if (message.type === 'quiz') {
        showQuizPanel(message.data, context);
    } else if (['feedback', 'nextQuestion', 'sessionComplete'].includes(message.type)) {
        if (quizPanel) {
            quizPanel.webview.postMessage(message);
        }
        // Once session is complete, release the focus trap and update status bar
        if (message.type === 'sessionComplete') {
            if (focusTrap)   { focusTrap.dispose();   focusTrap = null; }
            if (editBlocker) { editBlocker.dispose();  editBlocker = null; }
            if (statusBarItem) {
                statusBarItem.text = '$(check) BugBlock: Session complete!';
                statusBarItem.backgroundColor = undefined;
                statusBarItem.color = undefined;
            }
        }
    }
}

function showQuizPanel(quizData, context) {
    if (!quizPanel) {
        quizPanel = vscode.window.createWebviewPanel(
            'bugblockQuiz',
            '🪲 BugBlock',
            vscode.ViewColumn.Beside,
            {
                enableScripts: true,
                localResourceRoots: [vscode.Uri.file(path.join(context.extensionPath, 'media'))]
            }
        );

        // Status bar item — persistent reminder while quiz is active
        statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 1000);
        statusBarItem.text = '$(bug) BugBlock: Answer all 3 questions to continue';
        statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
        statusBarItem.color = new vscode.ThemeColor('statusBarItem.warningForeground');
        statusBarItem.show();

        // Focus trap — steal focus back when user clicks into any text editor
        focusTrap = vscode.window.onDidChangeActiveTextEditor((editor) => {
            if (editor && quizPanel) {
                quizPanel.reveal(vscode.ViewColumn.Beside, false);
            }
        });

        // Edit blocker — undo any keystroke the user makes in a code file
        editBlocker = vscode.workspace.onDidChangeTextDocument(async (event) => {
            if (!quizPanel || isUndoing) return;
            if (event.document.uri.scheme !== 'file') return;
            if (event.contentChanges.length === 0) return;

            isUndoing = true;
            try {
                await vscode.commands.executeCommand('undo');
                quizPanel.reveal(vscode.ViewColumn.Beside, false);
            } finally {
                isUndoing = false;
            }
        });

        quizPanel.onDidDispose(() => {
            quizPanel = null;
            if (focusTrap)    { focusTrap.dispose();    focusTrap = null; }
            if (editBlocker)  { editBlocker.dispose();  editBlocker = null; }
            if (statusBarItem){ statusBarItem.dispose(); statusBarItem = null; }
            if (bugblockProcess) { bugblockProcess.kill(); bugblockProcess = null; }
        });

        quizPanel.webview.onDidReceiveMessage((message) => {
            handleWebviewMessage(message);
        });
    }

    const quizHtmlPath = path.join(context.extensionPath, 'media', 'quiz.html');
    const scriptUri = quizPanel.webview.asWebviewUri(
        vscode.Uri.file(path.join(context.extensionPath, 'media', 'quiz.js'))
    );
    let html = fs.readFileSync(quizHtmlPath, 'utf-8');
    html = html.replace('src="quiz.js"', `src="${scriptUri}"`);

    quizPanel.webview.html = html;
    quizPanel.webview.postMessage({ type: 'startQuiz', data: quizData });
    quizPanel.reveal(vscode.ViewColumn.Beside, false);
}

function handleWebviewMessage(message) {
    console.log('Message from webview:', message.command);

    // Handle close: tear down the session entirely
    if (message.command === 'close') {
        if (bugblockProcess) {
            bugblockProcess.kill();
            bugblockProcess = null;
        }
        if (ipcSocket) {
            ipcSocket.destroy();
            ipcSocket = null;
        }
        if (quizPanel) {
            quizPanel.dispose(); // triggers onDidDispose → sets quizPanel = null
        }
        return;
    }

    // Forward all other messages to Python
    if (ipcSocket) {
        ipcSocket.write(JSON.stringify(message) + '\n');
    }
}

function deactivate() {
    stopBugBlock();
}

module.exports = { activate, deactivate };
