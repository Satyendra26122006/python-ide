import csv
import importlib
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtGui import QColor, QFont, QPainter, QSyntaxHighlighter, QTextCharFormat, QTextFormat
from PySide6.QtCore import Qt, QProcess, QRegularExpression, QSize, QRect
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFileSystemModel,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QTabWidget,
    QToolBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
    QLineEdit,
    QStatusBar,
    QTextEdit,
)

try:
    from gpt4all import GPT4All
    GPT4ALL_AVAILABLE = True
except Exception:
    GPT4ALL_AVAILABLE = False


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self):
        return QSize(self.code_editor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.code_editor.lineNumberAreaPaintEvent(event)


class CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        self.updateLineNumberAreaWidth(0)
        self.highlightCurrentLine()

    def lineNumberAreaWidth(self):
        digits = len(str(max(1, self.blockCount())))
        space = 3 + self.fontMetrics().horizontalAdvance("9") * digits
        return space

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor(240, 240, 240))
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(Qt.black)
                painter.drawText(0, top, self.line_number_area.width() - 4, self.fontMetrics().height(), Qt.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def highlightCurrentLine(self):
        extra_selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            line_color = QColor(232, 242, 254)
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        self.setExtraSelections(extra_selections)


class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent):
        super().__init__(parent)
        self.highlightingRules = []

        keywordFormat = QTextCharFormat()
        keywordFormat.setForeground(QColor("#569cd6"))
        keywordFormat.setFontWeight(QFont.Bold)

        keywords = [
            "and",
            "as",
            "assert",
            "break",
            "class",
            "continue",
            "def",
            "del",
            "elif",
            "else",
            "except",
            "finally",
            "for",
            "from",
            "global",
            "if",
            "import",
            "in",
            "is",
            "lambda",
            "nonlocal",
            "not",
            "or",
            "pass",
            "raise",
            "return",
            "try",
            "while",
            "with",
            "yield",
            "True",
            "False",
            "None",
        ]
        for word in keywords:
            pattern = QRegularExpression(r"\b" + word + r"\b")
            self.highlightingRules.append((pattern, keywordFormat))

        self.stringFormat = QTextCharFormat()
        self.stringFormat.setForeground(QColor("#d69d85"))

        self.commentFormat = QTextCharFormat()
        self.commentFormat.setForeground(QColor("#6a9955"))
        self.commentFormat.setFontItalic(True)

        self.numberFormat = QTextCharFormat()
        self.numberFormat.setForeground(QColor("#b5cea8"))

    def highlightBlock(self, text: str):
        for pattern, text_format in self.highlightingRules:
            match = pattern.match(text)
            while match.hasMatch():
                start = match.capturedStart()
                length = match.capturedLength()
                self.setFormat(start, length, text_format)
                match = pattern.match(text, start + length)

        stringPattern = QRegularExpression(r'(".*"|".*"|\'.*\'|\'.*\')')
        match = stringPattern.match(text)
        while match.hasMatch():
            self.setFormat(match.capturedStart(), match.capturedLength(), self.stringFormat)
            match = stringPattern.match(text, match.capturedEnd())

        commentPattern = QRegularExpression(r"#[^\n]*")
        match = commentPattern.match(text)
        while match.hasMatch():
            self.setFormat(match.capturedStart(), match.capturedLength(), self.commentFormat)
            match = commentPattern.match(text, match.capturedEnd())

        numberPattern = QRegularExpression(r"\b[0-9]+(\.[0-9]+)?\b")
        match = numberPattern.match(text)
        while match.hasMatch():
            self.setFormat(match.capturedStart(), match.capturedLength(), self.numberFormat)
            match = numberPattern.match(text, match.capturedEnd())


class PythonIDE(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project_root = Path(__file__).resolve().parent
        self.process = QProcess(self)
        self.python_executable = sys.executable
        self.ai_model = None
        self.ai_model_path = None

        self.setWindowTitle("Indra")
        self.resize(1450, 920)

        self._create_actions()
        self._create_layout()
        self._connect_process_signals()
        self._update_environment_panel()

    def _create_actions(self):
        toolbar = QToolBar("Main toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.open_folder_button = QPushButton("Open Folder")
        self.open_folder_button.clicked.connect(self.open_folder_dialog)
        toolbar.addWidget(self.open_folder_button)

        self.new_file_button = QPushButton("New File")
        self.new_file_button.clicked.connect(self.new_file)
        toolbar.addWidget(self.new_file_button)

        self.open_button = QPushButton("Open File")
        self.open_button.clicked.connect(self.open_file_dialog)
        toolbar.addWidget(self.open_button)

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_file)
        toolbar.addWidget(self.save_button)

        self.save_as_button = QPushButton("Save As")
        self.save_as_button.clicked.connect(self.save_file_as)
        toolbar.addWidget(self.save_as_button)

        self.run_button = QPushButton("Run")
        self.run_button.clicked.connect(self.run_python)
        toolbar.addWidget(self.run_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_python)
        toolbar.addWidget(self.stop_button)

        self.terminal_button = QPushButton("Open Terminal")
        self.terminal_button.clicked.connect(self.open_terminal)
        toolbar.addWidget(self.terminal_button)

    def _create_layout(self):
        root_widget = QWidget()
        self.setCentralWidget(root_widget)
        main_layout = QVBoxLayout(root_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        top_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(top_splitter)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(10)

        left_layout.addWidget(QLabel("Project Explorer"))
        self.tree_view = QTreeView()
        self.tree_model = QFileSystemModel()
        self.tree_model.setRootPath(str(self.project_root))
        self.tree_model.setNameFilters(["*.py", "*.txt", "*.md", "requirements*.txt", "*.csv"])
        self.tree_model.setNameFilterDisables(False)
        self.tree_view.setModel(self.tree_model)
        self.tree_view.setRootIndex(self.tree_model.index(str(self.project_root)))
        self.tree_view.doubleClicked.connect(self.on_tree_double_clicked)
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setColumnWidth(0, 260)
        left_layout.addWidget(self.tree_view, 1)

        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search project...")
        search_layout.addWidget(self.search_input)
        search_button = QPushButton("Search")
        search_button.clicked.connect(self.search_project)
        search_layout.addWidget(search_button)
        left_layout.addLayout(search_layout)

        left_layout.addWidget(QLabel("Search results"))
        self.search_results = QListWidget()
        self.search_results.itemDoubleClicked.connect(self.on_search_result_clicked)
        left_layout.addWidget(self.search_results, 1)

        top_splitter.addWidget(left_panel)

        centre_panel = QWidget()
        centre_layout = QVBoxLayout(centre_panel)
        centre_layout.setContentsMargins(10, 10, 10, 10)
        centre_layout.setSpacing(10)

        self.file_label = QLabel("No file open")
        centre_layout.addWidget(self.file_label)

        self.editor_tabs = QTabWidget()
        self.editor_tabs.setTabsClosable(True)
        self.editor_tabs.tabCloseRequested.connect(self.close_editor_tab)
        self.editor_tabs.currentChanged.connect(self.on_tab_changed)
        centre_layout.addWidget(self.editor_tabs, 1)

        self.console_tabs = QTabWidget()
        self.run_console = QPlainTextEdit()
        self.run_console.setReadOnly(True)
        self.run_console.setPlaceholderText("Run output and diagnostics appear here.")
        self.run_console.setFont(QFont("Consolas", 11))
        self.console_tabs.addTab(self.run_console, "Console")

        self.error_console = QPlainTextEdit()
        self.error_console.setReadOnly(True)
        self.error_console.setPlaceholderText("Error output appears here.")
        self.error_console.setFont(QFont("Consolas", 11))
        self.console_tabs.addTab(self.error_console, "Errors")
        centre_layout.addWidget(self.console_tabs, 0.7)

        top_splitter.addWidget(centre_panel)
        top_splitter.setStretchFactor(1, 3)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(10)

        self.right_tabs = QTabWidget()

        ai_tab = QWidget()
        ai_layout = QVBoxLayout(ai_tab)
        ai_layout.setContentsMargins(10, 10, 10, 10)
        ai_layout.setSpacing(10)
        ai_layout.addWidget(QLabel("AI Assistant"))
        self.ai_model_path_label = QLabel("No model loaded")
        ai_layout.addWidget(self.ai_model_path_label)
        load_model_button = QPushButton("Load GPT4All Model")
        load_model_button.clicked.connect(self.load_ai_model)
        ai_layout.addWidget(load_model_button)
        self.ai_prompt = QPlainTextEdit()
        self.ai_prompt.setPlaceholderText("Ask the assistant to explain code, generate a function, or fix an error.")
        self.ai_prompt.setFixedHeight(140)
        ai_layout.addWidget(self.ai_prompt)
        ask_button = QPushButton("Ask AI")
        ask_button.clicked.connect(self.ask_ai)
        ai_layout.addWidget(ask_button)
        self.ai_response = QPlainTextEdit()
        self.ai_response.setReadOnly(True)
        self.ai_response.setPlaceholderText("AI responses will appear here.")
        ai_layout.addWidget(self.ai_response, 1)
        apply_button = QPushButton("Apply AI Suggestion")
        apply_button.clicked.connect(self.apply_ai_suggestion)
        ai_layout.addWidget(apply_button)
        self.right_tabs.addTab(ai_tab, "AI")

        pkg_tab = QWidget()
        pkg_layout = QVBoxLayout(pkg_tab)
        pkg_layout.setContentsMargins(10, 10, 10, 10)
        pkg_layout.setSpacing(10)
        pkg_layout.addWidget(QLabel("Package Manager"))
        pkg_install_layout = QHBoxLayout()
        self.package_input = QLineEdit()
        self.package_input.setPlaceholderText("Enter package name, e.g. numpy")
        pkg_install_layout.addWidget(self.package_input)
        install_button = QPushButton("Install")
        install_button.clicked.connect(self.install_package)
        pkg_install_layout.addWidget(install_button)
        pkg_layout.addLayout(pkg_install_layout)
        requirements_button = QPushButton("Install requirements.txt")
        requirements_button.clicked.connect(self.install_requirements)
        pkg_layout.addWidget(requirements_button)
        ds_button = QPushButton("Install ML stack")
        ds_button.clicked.connect(self.install_ml_stack)
        pkg_layout.addWidget(ds_button)
        self.package_output = QPlainTextEdit()
        self.package_output.setReadOnly(True)
        self.package_output.setPlaceholderText("Package install logs appear here.")
        pkg_layout.addWidget(self.package_output, 1)
        self.right_tabs.addTab(pkg_tab, "Packages")

        env_tab = QWidget()
        env_layout = QVBoxLayout(env_tab)
        env_layout.setContentsMargins(10, 10, 10, 10)
        env_layout.setSpacing(10)
        env_layout.addWidget(QLabel("Python Environment"))
        self.python_path_label = QLabel()
        env_layout.addWidget(self.python_path_label)
        self.venv_status_label = QLabel()
        env_layout.addWidget(self.venv_status_label)
        self.env_info_label = QLabel()
        env_layout.addWidget(self.env_info_label)
        choose_python_button = QPushButton("Choose Python Interpreter")
        choose_python_button.clicked.connect(self.choose_python_interpreter)
        env_layout.addWidget(choose_python_button)
        self.create_venv_button = QPushButton("Create .venv")
        self.create_venv_button.clicked.connect(self.create_virtualenv)
        env_layout.addWidget(self.create_venv_button)
        launch_jupyter_button = QPushButton("Launch Jupyter Lab")
        launch_jupyter_button.clicked.connect(self.launch_jupyter_lab)
        env_layout.addWidget(launch_jupyter_button)
        refresh_env_button = QPushButton("Refresh environment")
        refresh_env_button.clicked.connect(self._update_environment_panel)
        env_layout.addWidget(refresh_env_button)
        self.right_tabs.addTab(env_tab, "Environment")

        data_tab = QWidget()
        data_layout = QVBoxLayout(data_tab)
        data_layout.setContentsMargins(10, 10, 10, 10)
        data_layout.setSpacing(10)
        data_layout.addWidget(QLabel("Dataset Preview"))
        load_csv_button = QPushButton("Load CSV preview")
        load_csv_button.clicked.connect(self.load_csv_preview)
        data_layout.addWidget(load_csv_button)
        self.dataset_info = QLabel("No dataset loaded")
        data_layout.addWidget(self.dataset_info)
        self.dataset_preview = QPlainTextEdit()
        self.dataset_preview.setReadOnly(True)
        self.dataset_preview.setPlaceholderText("Dataset preview appears here.")
        self.dataset_preview.setFont(QFont("Consolas", 11))
        data_layout.addWidget(self.dataset_preview, 1)
        self.right_tabs.addTab(data_tab, "Data")

        git_tab = QWidget()
        git_layout = QVBoxLayout(git_tab)
        git_layout.setContentsMargins(10, 10, 10, 10)
        git_layout.setSpacing(10)
        git_layout.addWidget(QLabel("Git Integration"))
        self.git_status_output = QPlainTextEdit()
        self.git_status_output.setReadOnly(True)
        self.git_status_output.setPlaceholderText("Git status output appears here.")
        self.git_status_output.setFont(QFont("Consolas", 11))
        git_layout.addWidget(self.git_status_output, 1)
        git_buttons = QHBoxLayout()
        refresh_git_button = QPushButton("Refresh Git Status")
        refresh_git_button.clicked.connect(self.update_git_status)
        git_buttons.addWidget(refresh_git_button)
        git_pull_button = QPushButton("Git Pull")
        git_pull_button.clicked.connect(self.git_pull)
        git_buttons.addWidget(git_pull_button)
        git_layout.addLayout(git_buttons)
        self.git_commit_input = QLineEdit()
        self.git_commit_input.setPlaceholderText("Commit message")
        git_layout.addWidget(self.git_commit_input)
        git_commit_button = QPushButton("Commit All Changes")
        git_commit_button.clicked.connect(self.git_commit)
        git_layout.addWidget(git_commit_button)
        self.right_tabs.addTab(git_tab, "Git")

        terminal_tab = QWidget()
        terminal_layout = QVBoxLayout(terminal_tab)
        terminal_layout.setContentsMargins(10, 10, 10, 10)
        terminal_layout.setSpacing(10)
        terminal_layout.addWidget(QLabel("Command Runner"))
        self.terminal_output = QPlainTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setPlaceholderText("Run shell commands from here.")
        self.terminal_output.setFont(QFont("Consolas", 11))
        terminal_layout.addWidget(self.terminal_output, 1)
        terminal_command_layout = QHBoxLayout()
        self.terminal_input = QLineEdit()
        self.terminal_input.setPlaceholderText("Enter shell command, e.g. python script.py")
        terminal_command_layout.addWidget(self.terminal_input)
        terminal_run_button = QPushButton("Run")
        terminal_run_button.clicked.connect(self.run_terminal_command)
        terminal_command_layout.addWidget(terminal_run_button)
        terminal_layout.addLayout(terminal_command_layout)
        terminal_clear_button = QPushButton("Clear Output")
        terminal_clear_button.clicked.connect(lambda: self.terminal_output.clear())
        terminal_layout.addWidget(terminal_clear_button)
        self.right_tabs.addTab(terminal_tab, "Terminal")

        right_layout.addWidget(self.right_tabs)
        top_splitter.addWidget(right_panel)
        top_splitter.setStretchFactor(2, 1)

        self.new_file()

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _connect_process_signals(self):
        self.process.readyReadStandardOutput.connect(self.on_process_stdout)
        self.process.readyReadStandardError.connect(self.on_process_stderr)
        self.process.finished.connect(self.on_process_finished)

    def _create_editor_tab(self, file_path: Optional[Path] = None, content: str = ""):
        editor = CodeEditor()
        editor.setFont(QFont("Consolas", 11))
        editor.setPlainText(content)
        editor.textChanged.connect(self.update_status)
        PythonHighlighter(editor.document())

        name = file_path.name if file_path else "Untitled"
        self.editor_tabs.addTab(editor, name)
        self.editor_tabs.tabBar().setTabData(self.editor_tabs.count() - 1, str(file_path) if file_path else None)
        self.editor_tabs.setCurrentWidget(editor)
        self.update_status()
        return editor

    def current_editor(self):
        return self.editor_tabs.currentWidget()

    def current_file_path(self):
        return self.editor_tabs.tabBar().tabData(self.editor_tabs.currentIndex())

    def on_tab_changed(self, index):
        file_path = self.editor_tabs.tabBar().tabData(index)
        if file_path:
            self.file_label.setText(str(Path(file_path).relative_to(self.project_root)))
        else:
            self.file_label.setText("Untitled")
        self.update_status()

    def close_editor_tab(self, index):
        self.editor_tabs.removeTab(index)
        if self.editor_tabs.count() == 0:
            self.new_file()

    def new_file(self):
        self._create_editor_tab()
        self.file_label.setText("Untitled")
        self.setWindowTitle("Indra - New File")
        self.console_clear()

    def open_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Open Project Folder",
            str(self.project_root),
        )
        if folder:
            self.project_root = Path(folder)
            self.tree_model.setRootPath(str(self.project_root))
            self.tree_view.setRootIndex(self.tree_model.index(str(self.project_root)))
            self.console_append(f"Opened folder: {self.project_root}")
            self._update_environment_panel()

    def open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Python File",
            str(self.project_root),
            "Python Files (*.py);;All Files (*)",
        )
        if file_path:
            self.open_file(Path(file_path))

    def open_file(self, file_path: Path):
        for index in range(self.editor_tabs.count()):
            if self.editor_tabs.tabBar().tabData(index) == str(file_path):
                self.editor_tabs.setCurrentIndex(index)
                return
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()
            self._create_editor_tab(file_path, content)
            self.setWindowTitle(f"Indra - {file_path.name}")
            self.console_append(f"Opened {file_path}")
        except Exception as exc:
            QMessageBox.critical(self, "Open Error", str(exc))

    def save_file(self):
        editor = self.current_editor()
        if editor is None:
            return
        file_path = self.current_file_path()
        if file_path is None:
            return self.save_file_as()
        self._write_file(Path(file_path), editor)

    def save_file_as(self):
        editor = self.current_editor()
        if editor is None:
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Python File",
            str(self.project_root / "untitled.py"),
            "Python Files (*.py);;All Files (*)",
        )
        if file_path:
            path = Path(file_path)
            self._write_file(path, editor)
            index = self.editor_tabs.currentIndex()
            self.editor_tabs.setTabText(index, path.name)
            self.editor_tabs.tabBar().setTabData(index, str(path))
            self.file_label.setText(str(path.relative_to(self.project_root)))
            self.setWindowTitle(f"Indra - {path.name}")

    def _write_file(self, path: Path, editor: QPlainTextEdit):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as file:
                file.write(editor.toPlainText())
            self.console_append(f"Saved {path}")
            self.tree_model.refresh(self.tree_model.index(str(self.project_root)))
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", str(exc))

    def on_tree_double_clicked(self, index):
        path = Path(self.tree_model.filePath(index))
        if path.is_file():
            self.open_file(path)

    def console_clear(self):
        if hasattr(self, 'run_console') and self.run_console is not None:
            self.run_console.clear()
        if hasattr(self, 'error_console') and self.error_console is not None:
            self.error_console.clear()

    def console_append(self, text: str):
        if hasattr(self, 'run_console') and self.run_console is not None:
            self.run_console.appendPlainText(text)
        if hasattr(self, 'status_bar') and self.status_bar is not None:
            self.status_bar.showMessage(text, 5000)

    def error_append(self, text: str):
        if hasattr(self, 'error_console') and self.error_console is not None:
            self.error_console.appendPlainText(text)
        if hasattr(self, 'status_bar') and self.status_bar is not None:
            self.status_bar.showMessage("Error reported", 5000)

    def run_python(self):
        editor = self.current_editor()
        if editor is None:
            QMessageBox.warning(self, "Run Warning", "Save or open a Python file before running.")
            return
        file_path = self.current_file_path()
        if file_path is None:
            QMessageBox.warning(self, "Run Warning", "Save the file before running.")
            return
        if self.process.state() != QProcess.NotRunning:
            QMessageBox.warning(self, "Run Warning", "A process is already running.")
            return

        self.save_file()
        self.console_clear()
        self.console_append(f"Running: {self.python_executable} {file_path}")

        self.process.setProgram(self.python_executable)
        self.process.setArguments([str(file_path)])
        self.process.setWorkingDirectory(str(Path(file_path).parent))
        self.process.start()

    def stop_python(self):
        if self.process.state() != QProcess.NotRunning:
            self.process.kill()
            self.console_append("Process stopped by user.")

    def on_process_stdout(self):
        data = self.process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        if data:
            self.console_append(data.rstrip())

    def on_process_stderr(self):
        data = self.process.readAllStandardError().data().decode("utf-8", errors="replace")
        if data:
            self.error_append(data.rstrip())

    def on_process_finished(self, exit_code, exit_status):
        self.console_append(f"Process finished with exit code {exit_code}.")

    def search_project(self):
        term = self.search_input.text().strip()
        self.search_results.clear()
        if not term:
            return

        matches = []
        for path in sorted(self.project_root.rglob("*")):
            if path.is_file() and path.suffix in {".py", ".txt", ".md", ".csv"}:
                try:
                    content = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                for number, line in enumerate(content.splitlines(), start=1):
                    if term.lower() in line.lower():
                        item = QListWidgetItem(f"{path.relative_to(self.project_root)}:{number}: {line.strip()}")
                        item.setData(Qt.UserRole, str(path))
                        matches.append(item)
        if matches:
            for item in matches:
                self.search_results.addItem(item)
            self.console_append(f"Found {len(matches)} result(s) for '{term}'")
        else:
            self.console_append(f"No results found for '{term}'")

    def on_search_result_clicked(self, item: QListWidgetItem):
        file_path = Path(item.data(Qt.UserRole))
        if file_path.exists():
            self.open_file(file_path)

    def install_package(self):
        package_name = self.package_input.text().strip()
        if not package_name:
            QMessageBox.warning(self, "Package Warning", "Enter a package name before installing.")
            return
        self.package_output.clear()
        self.package_output.appendPlainText(f"Installing {package_name}...")
        self._run_subprocess([self.python_executable, "-m", "pip", "install", package_name], self.package_output)

    def install_requirements(self):
        requirements_path = self.project_root / "requirements.txt"
        if not requirements_path.exists():
            QMessageBox.warning(self, "Requirements Missing", "No requirements.txt found in the project folder.")
            return
        self.package_output.clear()
        self.package_output.appendPlainText("Installing requirements.txt...")
        self._run_subprocess([self.python_executable, "-m", "pip", "install", "-r", str(requirements_path)], self.package_output)

    def install_ml_stack(self):
        requirements_path = self.project_root / "requirements-ds.txt"
        if not requirements_path.exists():
            QMessageBox.warning(self, "Requirements Missing", "No requirements-ds.txt found in the project folder.")
            return
        self.package_output.clear()
        self.package_output.appendPlainText("Installing ML/data-science stack...")
        self._run_subprocess([self.python_executable, "-m", "pip", "install", "-r", str(requirements_path)], self.package_output)

    def choose_python_interpreter(self):
        python_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Python Interpreter",
            str(self.project_root),
            "Python Executable (python.exe);;All Files (*)",
        )
        if python_path:
            self.python_executable = python_path
            self._update_environment_panel()
            self.console_append(f"Switched interpreter to {python_path}")

    def create_virtualenv(self):
        self.package_output.clear()
        self.package_output.appendPlainText("Creating virtual environment .venv...")
        self._run_subprocess([self.python_executable, "-m", "venv", str(self.project_root / ".venv")], self.package_output)
        self._update_environment_panel()

    def open_terminal(self):
        try:
            subprocess.Popen(["cmd.exe", "/K", f"cd /d {self.project_root}"], shell=False)
            self.console_append("Opened Windows terminal in project folder.")
        except Exception as exc:
            QMessageBox.critical(self, "Terminal Error", str(exc))

    def load_csv_preview(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open CSV file",
            str(self.project_root),
            "CSV Files (*.csv);;All Files (*)",
        )
        if not file_path:
            return
        try:
            preview_lines = []
            with open(file_path, "r", encoding="utf-8", errors="ignore") as csvfile:
                reader = csv.reader(csvfile)
                for index, row in enumerate(reader, start=1):
                    preview_lines.append(", ".join(row[:10]))
                    if index >= 20:
                        break
            self.dataset_info.setText(f"Previewing {Path(file_path).name} ({len(preview_lines)} rows shown)")
            self.dataset_preview.setPlainText("\n".join(preview_lines))
        except Exception as exc:
            QMessageBox.critical(self, "CSV Preview Error", str(exc))

    def launch_jupyter_lab(self):
        try:
            subprocess.Popen(
                [self.python_executable, "-m", "jupyter", "lab"],
                cwd=str(self.project_root),
                shell=False,
            )
            self.console_append("Launching Jupyter Lab in the default browser.")
        except Exception as exc:
            QMessageBox.critical(self, "Launch Error", str(exc))

    def update_git_status(self):
        self.git_status_output.clear()
        if (self.project_root / ".git").exists():
            self._run_subprocess(["git", "status", "--short"], self.git_status_output)
        else:
            self.git_status_output.appendPlainText("Git is not initialized in this folder.")

    def git_pull(self):
        if not (self.project_root / ".git").exists():
            QMessageBox.warning(self, "Git Warning", "This project is not a Git repository.")
            return
        self.git_status_output.appendPlainText("Pulling latest changes...")
        self._run_subprocess(["git", "pull"], self.git_status_output)

    def git_commit(self):
        message = self.git_commit_input.text().strip()
        if not message:
            QMessageBox.warning(self, "Git Warning", "Enter a commit message before committing.")
            return
        self.git_status_output.appendPlainText(f"Committing changes: {message}")
        self._run_subprocess(["git", "add", "-A"], self.git_status_output)
        self._run_subprocess(["git", "commit", "-m", message], self.git_status_output)

    def run_terminal_command(self):
        command = self.terminal_input.text().strip()
        if not command:
            QMessageBox.warning(self, "Terminal Warning", "Enter a command to run.")
            return
        self.terminal_output.appendPlainText(f"> {command}")
        self._run_subprocess(["cmd.exe", "/c", command], self.terminal_output)

    def load_ai_model(self):
        if not GPT4ALL_AVAILABLE:
            QMessageBox.warning(
                self,
                "AI Backend Missing",
                "GPT4All is not installed. Install requirements-ai.txt and restart the IDE.",
            )
            return

        model_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select GPT4All Model File",
            str(self.project_root),
            "Model Files (*.bin *.gguf *.bin.*);;All Files (*)",
        )
        if not model_path:
            return

        self.ai_model_path = Path(model_path)
        self.ai_model_path_label.setText(f"Model: {self.ai_model_path.name}")
        try:
            self.ai_model = GPT4All(model=str(self.ai_model_path))
            self.console_append(f"Loaded AI model {self.ai_model_path.name}")
        except Exception as exc:
            QMessageBox.critical(self, "Model Load Error", str(exc))
            self.ai_model = None
            self.ai_model_path = None
            self.ai_model_path_label.setText("No model loaded")

    def ask_ai(self):
        prompt = self.ai_prompt.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "AI Warning", "Type a request for the AI assistant first.")
            return
        if not GPT4ALL_AVAILABLE:
            self.ai_response.setPlainText(
                "GPT4All package is not installed.\n"
                "Install the AI requirements from requirements-ai.txt and restart the IDE."
            )
            return
        if self.ai_model is None:
            QMessageBox.warning(self, "AI Warning", "Load a GPT4All model file before asking the assistant.")
            return

        editor = self.current_editor()
        code_text = editor.toPlainText().strip() if editor else ""
        file_name = Path(self.current_file_path()).name if self.current_file_path() else "unsaved.py"
        source_snippet = code_text[:2500]
        system_prompt = (
            "You are a Python code-only assistant for machine learning and data science projects. "
            "Answer with code examples, suggestions, or fixes only."
        )
        full_prompt = (
            f"{system_prompt}\n\n"
            f"Current file: {file_name}\n"
            f"Current code:\n{source_snippet}\n\n"
            f"Request:\n{prompt}\n"
        )

        try:
            response = self.ai_model.generate(
                full_prompt,
                max_tokens=512,
                temperature=0.2,
            )
            self.ai_response.setPlainText(str(response).strip())
        except Exception as exc:
            self.ai_response.setPlainText(f"AI generation failed: {exc}")

    def apply_ai_suggestion(self):
        applied_text = self.ai_response.toPlainText().strip()
        if not applied_text:
            QMessageBox.warning(self, "AI Warning", "There is no AI suggestion to apply.")
            return
        editor = self.current_editor()
        if editor is None:
            QMessageBox.warning(self, "AI Warning", "Open or create a file before applying AI output.")
            return
        editor.setPlainText(applied_text)
        self.console_append("Applied AI suggestion to the current editor.")

    def _run_subprocess(self, arguments, output_widget):
        process = QProcess(self)
        process.setProgram(arguments[0])
        process.setArguments(arguments[1:])
        process.setWorkingDirectory(str(self.project_root))

        def on_stdout():
            data = process.readAllStandardOutput().data().decode("utf-8", errors="replace")
            if data:
                output_widget.appendPlainText(data.rstrip())

        def on_stderr():
            data = process.readAllStandardError().data().decode("utf-8", errors="replace")
            if data:
                output_widget.appendPlainText(data.rstrip())

        def on_finished(code, status):
            output_widget.appendPlainText(f"Finished with exit code {code}.")
            self._update_environment_panel()

        process.readyReadStandardOutput.connect(on_stdout)
        process.readyReadStandardError.connect(on_stderr)
        process.finished.connect(on_finished)
        process.start()

    def _update_environment_panel(self):
        self.python_path_label.setText(f"Python: {self.python_executable}")
        venv_folder = self.project_root / ".venv"
        if venv_folder.exists() and any(venv_folder.iterdir()):
            self.venv_status_label.setText("Virtual environment: .venv exists")
        else:
            self.venv_status_label.setText("Virtual environment: .venv not found")

        ml_support = []
        try:
            if importlib.util.find_spec("torch"):
                import torch

                ml_support.append("PyTorch")
                if torch.cuda.is_available():
                    ml_support.append("CUDA available")
            if importlib.util.find_spec("tensorflow"):
                ml_support.append("TensorFlow")
            if importlib.util.find_spec("pandas"):
                ml_support.append("pandas")
        except Exception:
            pass

        if ml_support:
            self.env_info_label.setText("ML libs detected: " + ", ".join(ml_support))
        else:
            self.env_info_label.setText("ML libs detected: none or not installed")

    def update_status(self):
        editor = self.current_editor()
        if editor is None or not hasattr(self, 'status_bar') or self.status_bar is None:
            return
        cursor = editor.textCursor()
        line = cursor.blockNumber() + 1
        column = cursor.columnNumber() + 1
        self.status_bar.showMessage(f"Line {line}, Column {column}")


def main():
    app = QApplication(sys.argv)
    window = PythonIDE()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
