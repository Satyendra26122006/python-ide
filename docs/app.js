const fileList = document.getElementById('fileList');
const codeEditor = document.getElementById('codeEditor');
const output = document.getElementById('output');
const packageOutput = document.getElementById('packageOutput');
const envOutput = document.getElementById('envOutput');
const csvPreview = document.getElementById('csvPreview');
const runtimeStatus = document.getElementById('runtimeStatus');
const outputStatus = document.getElementById('outputStatus');
const currentFileLabel = document.getElementById('currentFileLabel');

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

function openFile(filename) {
  if (!workspaceFiles[filename]) {
    workspaceFiles[filename] = '';
  }
  currentFile = filename;
  currentFileLabel.textContent = filename;
  codeEditor.value = workspaceFiles[filename];
  renderFileList();
  saveWorkspace();
}

function saveFile() {
  workspaceFiles[currentFile] = codeEditor.value;
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
  openFile(name);
}

function downloadFile() {
  const blob = new Blob([codeEditor.value], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = currentFile;
  anchor.click();
  URL.revokeObjectURL(url);
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
    const installed = await pyodide.runPythonAsync(`import sys, pkgutil\npackages = sorted([p.name for p in pkgutil.iter_modules()])\n'\n'.join(packages[:80])`);
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
          codeEditor.focus();
          codeEditor.setSelectionRange(position, position + line.length);
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

window.addEventListener('DOMContentLoaded', async () => {
  loadWorkspace();
  await initPyodide();
});
