const codeEditor = document.getElementById('codeEditor');
const output = document.getElementById('output');
const status = document.getElementById('status');
const runButton = document.getElementById('runButton');
const clearButton = document.getElementById('clearButton');
const exampleButton = document.getElementById('exampleButton');

let pyodide = null;

const defaultExample = `print("Hello from the browser-based Python IDE")
for i in range(3):
    print(i)
`;

function appendOutput(text, isError = false) {
  output.textContent += text;
  if (isError) {
    output.textContent += '\n';
  }
}

async function initPyodide() {
  status.textContent = 'Loading Python runtime...';
  pyodide = await loadPyodide({ indexURL: 'https://cdn.jsdelivr.net/pyodide/v0.26.2/full/' });
  pyodide.setStdout({ batched: (text) => appendOutput(text) });
  pyodide.setStderr({ batched: (text) => appendOutput(text, true) });
  status.textContent = 'Python runtime ready';
}

async function runCode() {
  if (!pyodide) {
    await initPyodide();
  }

  output.textContent = '';
  status.textContent = 'Running...';

  try {
    await pyodide.runPythonAsync(codeEditor.value);
    status.textContent = 'Finished';
  } catch (error) {
    output.textContent += `Error: ${error}\n`;
    status.textContent = 'Execution failed';
  }
}

function clearOutput() {
  output.textContent = '';
  status.textContent = 'Ready';
}

function loadExample() {
  codeEditor.value = defaultExample;
  clearOutput();
}

runButton.addEventListener('click', runCode);
clearButton.addEventListener('click', clearOutput);
exampleButton.addEventListener('click', loadExample);

window.addEventListener('DOMContentLoaded', initPyodide);
