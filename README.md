# Simple Python IDE

A lightweight but full-featured Python IDE with a code editor, project explorer, run/stop controls, search, package installation, environment tools, CSV preview, Git integration, terminal access, and AI assistance.

## Run it

Install the base dependencies:

```bash
python -m pip install -r requirements.txt
```

For the AI assistant features, also install:

```bash
python -m pip install -r requirements-ai.txt
```

Start the app:

```bash
python launch.py
```

On Windows, you can also double-click the launcher:

```powershell
.\run-ide.bat
```

## Included files

- app.py: main application with all IDE features
- launch.py: simple startup entry point
- run-ide.bat: Windows launcher
- requirements.txt: base UI/runtime dependencies
- requirements-ai.txt: optional AI backend dependency
