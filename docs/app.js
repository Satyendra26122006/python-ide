const fileList = document.getElementById('fileList');
const codeTextarea = document.getElementById('codeEditor');
const output = document.getElementById('output');
const packageOutput = document.getElementById('packageOutput');
const envOutput = document.getElementById('envOutput');
const csvPreview = document.getElementById('csvPreview');
const runtimeStatus = document.getElementById('runtimeStatus');
const outputStatus = document.getElementById('outputStatus');
const currentFileLabel = document.getElementById('currentFileLabel');
const tabBar = document.getElementById('tabBar');
const aiKeyInput = document.getElementById('aiKeyInput');
const saveAiKeyButton = document.getElementById('saveAiKeyButton');
const aiPrompt = document.getElementById('aiPrompt');
const askAiButton = document.getElementById('askAiButton');
const aiResponse = document.getElementById('aiResponse');
const applyAiButton = document.getElementById('applyAiButton');

const runButton = document.getElementById('runButton');
const saveButton = document.getElementById('saveButton');
const newFileButton = document.getElementById('newFileButton');
const downloadButton = document.getElementById('downloadButton');
const loadExampleButton = document.getElementById('loadExampleButton');
const clearOutputButton = document.getElementById('clearOutputButton');
const loadFilesButton = document.getElementById('loadFilesButton');
const fileLoader = document.getElementById('fileLoader');
const installPackageButton = document.getElementById('installPackageButton');
const packageInput = document.getElementById('packageInput');
const refreshEnvironmentButton = document.getElementById('refreshEnvironmentButton');
const searchInput = document.getElementById('searchInput');
const searchButton = document.getElementById('searchButton');
const searchResults = document.getElementById('searchResults');
const loadCsvButton = document.getElementById('loadCsvButton');
const csvLoader = document.getElementById('csvLoader');
const terminalInput = document.getElementById('terminalInput');
const terminalRunButton = document.getElementById('terminalRunButton');
const terminalOutput = document.getElementById('terminalOutput');

let pyodide = null;
let editor = null;
let workspaceFiles = {};
let currentFile = 'main.py';
const defaultExample = `print("Hello from the browser-based Python IDE")\nfor i in range(3):\n    print(i)\n`;

function appendOutput(text) {
  output.textContent += text;
}

function appendTerminal(text) {
  terminalOutput.textContent += text;
}

function updateStatus(text) {
  runtimeStatus.textContent = text;
}

function updateOutputStatus(text) {
  outputStatus.textContent = text;
}

function getAiApiKey() {
  return localStorage.getItem('python-ide-openai-key') || '';
}

function saveAiKey() {
  const key = aiKeyInput.value.trim();
  localStorage.setItem('python-ide-openai-key', key);
  aiResponse.textContent = key ? 'OpenAI key saved locally.' : 'Removed saved OpenAI key.';
}

async function askAi() {
  const key = getAiApiKey();
  const prompt = aiPrompt.value.trim();
  if (!key) {
    aiResponse.textContent = 'Please enter an OpenAI API key to use the AI assistant.';
    return;
  }
  if (!prompt) {
    aiResponse.textContent = 'Enter a prompt for the AI assistant.';
    return;
  }

  aiResponse.textContent = 'Asking AI...';
  try {
    const response = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${key}`,
      },
      body: JSON.stringify({
        model: 'gpt-4o-mini',
        messages: [
          { role: 'system', content: 'You are a helpful programming assistant.' },
          { role: 'user', content: prompt },
        ],
        max_tokens: 600,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      aiResponse.textContent = `AI request failed: ${response.status} ${errorText}`;
      return;
    }

    const data = await response.json();
    const text = data.choices?.[0]?.message?.content?.trim() || 'No response from AI.';
    aiResponse.textContent = text;
  } catch (error) {
    aiResponse.textContent = `AI request error: ${error}`;
  }
}

function applyAiSuggestion() {
  const suggestion = aiResponse.textContent.trim();
  if (!suggestion) {
    return;
  }

  const doc = editor.getDoc();
  const selection = doc.getSelection();
  if (selection) {
    doc.replaceSelection(suggestion);
  } else {
    const cursor = doc.getCursor();
    doc.replaceRange(`\n# AI suggestion:\n${suggestion}\n`, cursor);
  }
}

function saveWorkspace() {
  const payload = {
    files: workspaceFiles,
    current: currentFile,
  };
  localStorage.setItem('python-ide-workspace', JSON.stringify(payload));
}

function loadWorkspace() {
  const saved = localStorage.getItem('python-ide-workspace');
  if (saved) {
    try {
      const payload = JSON.parse(saved);
      workspaceFiles = payload.files || {};
      currentFile = payload.current || 'main.py';
    } catch (error) {
      console.warn('Unable to parse saved workspace.', error);
    }
  }

  if (!Object.keys(workspaceFiles).length) {
    workspaceFiles = {
      'main.py': defaultExample,
      'README.md': '# Python IDE in Browser\nUse the explorer to add files, run code, and preview CSV data.',
    };
    currentFile = 'main.py';
  }

  renderFileList();
  renderTabBar();
  openFile(currentFile);
}

function renderFileList() {
  fileList.innerHTML = '';
  Object.keys(workspaceFiles).forEach((filename) => {
    const item = document.createElement('li');
    item.textContent = filename;
    item.className = filename === currentFile ? 'active' : '';
    item.addEventListener('click', () => openFile(filename));
    fileList.appendChild(item);
  });
}

function renderTabBar() {
  tabBar.innerHTML = '';
  Object.keys(workspaceFiles).forEach((filename) => {
    const tab = document.createElement('div');
    tab.textContent = filename;
    tab.className = `tab${filename === currentFile ? ' active' : ''}`;
    tab.addEventListener('click', () => openFile(filename));
    tabBar.appendChild(tab);
  });
}

function openFile(filename) {
  if (!workspaceFiles[filename]) {
    workspaceFiles[filename] = '';
  }
  currentFile = filename;
  currentFileLabel.textContent = filename;
  editor.setValue(workspaceFiles[filename]);
  renderFileList();
  renderTabBar();
  saveWorkspace();
}

function saveFile() {
  workspaceFiles[currentFile] = editor.getValue();
  saveWorkspace();
  updateOutputStatus('File saved');
}

function createNewFile() {
  const name = prompt('New file name (include extension):', 'script.py');
  if (!name) {
    return;
  }
  if (workspaceFiles[name]) {
    alert('A file with that name already exists.');
    return;
  }
  workspaceFiles[name] = '# New file\n';
  currentFile = name;
  renderFileList();
  renderTabBar();
  openFile(name);
}

function downloadFile() {
  const blob = new Blob([editor.getValue()], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = currentFile;
  anchor.click();
  URL.revokeObjectURL(url);
}

function initEditor() {
  editor = CodeMirror.fromTextArea(codeTextarea, {
    mode: 'python',
    lineNumbers: true,
    indentUnit: 4,
    theme: 'default',
    autofocus: true,
    viewportMargin: Infinity,
  });
  editor.on('change', () => {
    workspaceFiles[currentFile] = editor.getValue();
  });
}

async function initPyodide() {
  updateStatus('Loading Python runtime...');
  pyodide = await loadPyodide({ indexURL: 'https://cdn.jsdelivr.net/pyodide/v0.26.2/full/' });
  await pyodide.loadPackage(['micropip']);
  await pyodide.runPythonAsync('import micropip');
  updateStatus('Python runtime ready');
  refreshEnvironment();
}

async function runCode() {
  if (!pyodide) {
    await initPyodide();
  }

  saveFile();
  output.textContent = '';
  updateOutputStatus('Running...');

  try {
    const code = workspaceFiles[currentFile];
    await pyodide.runPythonAsync(code);
    updateOutputStatus('Finished');
  } catch (error) {
    output.textContent = `Error: ${error}`;
    updateOutputStatus('Execution failed');
  }
}

async function installPackage() {
  if (!pyodide) {
    await initPyodide();
  }

  const packageName = packageInput.value.trim();
  if (!packageName) {
    packageOutput.textContent = 'Enter a package name to install.';
    return;
  }

  packageOutput.textContent = `Installing ${packageName}...`;
  try {
    await pyodide.runPythonAsync(`import micropip\nawait micropip.install('${packageName}')`);
    packageOutput.textContent = `Installed ${packageName}`;
    refreshEnvironment();
  } catch (error) {
    packageOutput.textContent = `Install failed: ${error}`;
  }
}

async function refreshEnvironment() {
  if (!pyodide) {
    envOutput.textContent = 'Runtime not loaded yet.';
    return;
  }

  try {
    const installed = await pyodide.runPythonAsync(`import pkgutil\npackages = sorted([p.name for p in pkgutil.iter_modules()])\n'\n'.join(packages[:80])`);
    envOutput.textContent = `Available Python modules:\n${installed}`;
  } catch (error) {
    envOutput.textContent = `Unable to refresh environment: ${error}`;
  }
}

function loadExample() {
  workspaceFiles['main.py'] = defaultExample;
  openFile('main.py');
  updateOutputStatus('Loaded example');
}

function clearOutput() {
  output.textContent = '';
  updateOutputStatus('Ready');
}

function handleSearch() {
  const term = searchInput.value.trim().toLowerCase();
  searchResults.innerHTML = '';
  if (!term) {
    return;
  }

  Object.entries(workspaceFiles).forEach(([name, content]) => {
    const lines = content.split('\n');
    lines.forEach((line, index) => {
      if (line.toLowerCase().includes(term)) {
        const resultItem = document.createElement('li');
        resultItem.textContent = `${name} : ${index + 1} → ${line.trim()}`;
        resultItem.addEventListener('click', () => {
          openFile(name);
          const position = content.split('\n').slice(0, index).join('\n').length;
          editor.focus();
          editor.setSelection({ line: index, ch: 0 }, { line: index, ch: line.length });
        });
        searchResults.appendChild(resultItem);
      }
    });
  });
}

function loadLocalFiles(files) {
  if (!files.length) {
    return;
  }

  Array.from(files).forEach((file) => {
    const reader = new FileReader();
    reader.onload = () => {
      workspaceFiles[file.name] = reader.result;
      renderFileList();
      renderTabBar();
      saveWorkspace();
    };
    reader.readAsText(file);
  });
}

function startLoadFiles() {
  fileLoader.click();
}

function loadCsvFile() {
  csvLoader.click();
}

function handleCsvChange(event) {
  const file = event.target.files[0];
  if (!file) {
    return;
  }

  const reader = new FileReader();
  reader.onload = () => {
    const text = reader.result;
    const rows = text.split(/\r?\n/).slice(0, 20);
    csvPreview.textContent = rows.join('\n');
  };
  reader.readAsText(file);
}

async function runTerminalCommand() {
  if (!pyodide) {
    await initPyodide();
  }

  const command = terminalInput.value.trim();
  if (!command) {
    terminalOutput.textContent = 'Enter a Python command or expression.';
    return;
  }

  appendTerminal(`>>> ${command}\n`);
  try {
    const result = await pyodide.runPythonAsync(command);
    appendTerminal(String(result) + '\n');
  } catch (error) {
    appendTerminal(`Error: ${error}\n`);
  }
}

runButton.addEventListener('click', runCode);
saveButton.addEventListener('click', saveFile);
newFileButton.addEventListener('click', createNewFile);
downloadButton.addEventListener('click', downloadFile);
loadExampleButton.addEventListener('click', loadExample);
clearOutputButton.addEventListener('click', clearOutput);
loadFilesButton.addEventListener('click', startLoadFiles);
fileLoader.addEventListener('change', (event) => loadLocalFiles(event.target.files));
installPackageButton.addEventListener('click', installPackage);
refreshEnvironmentButton.addEventListener('click', refreshEnvironment);
searchButton.addEventListener('click', handleSearch);
loadCsvButton.addEventListener('click', loadCsvFile);
csvLoader.addEventListener('change', handleCsvChange);
terminalRunButton.addEventListener('click', runTerminalCommand);
saveAiKeyButton.addEventListener('click', saveAiKey);
askAiButton.addEventListener('click', askAi);
applyAiButton.addEventListener('click', applyAiSuggestion);

window.addEventListener('DOMContentLoaded', async () => {
  initEditor();
  loadWorkspace();
  aiKeyInput.value = getAiApiKey();
  await initPyodide();
});
