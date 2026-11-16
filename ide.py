import sys
import os
import re
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPlainTextEdit, QPushButton, QSplitter, 
                             QFileDialog, QMessageBox)
from PyQt6.QtGui import (QFont, QColor, QSyntaxHighlighter, QTextCharFormat, 
                         QPainter, QTextCursor, QKeySequence, QShortcut)
from PyQt6.QtCore import Qt, QRect, QSize, QProcess, QProcessEnvironment

# ==========================================
# 1. ПОДСВЕТКА СИНТАКСИСА p0P
# ==========================================
class P0PHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rules = []

        # Ключевые слова (синий)
        kw_format = QTextCharFormat()
        kw_format.setForeground(QColor("#569cd6"))
        kw_format.setFontWeight(QFont.Weight.Bold)
        keywords = ["let", "var", "if", "else", "while", "for", "in", "loop", 
                    "break", "continue", "return", "say", "show", "push", 
                    "true", "false", "nil", "and", "or", "not", "import", "delete", "fn"]
        for word in keywords:
            self.rules.append((rf"\b{word}\b", kw_format))

        # Встроенные функции (желтый)
        builtin_format = QTextCharFormat()
        builtin_format.setForeground(QColor("#dcdcaa"))
        for func in ["ask", "num", "str", "len", "append", "range", "type", "upper", "lower"]:
            self.rules.append((rf"\b{func}\b", builtin_format))

        # Строки (оранжевый)
        str_format = QTextCharFormat()
        str_format.setForeground(QColor("#ce9178"))
        self.rules.append((r'"[^"\\]*(\\.[^"\\]*)*"', str_format))
        self.rules.append((r"'[^'\\]*(\\.[^'\\]*)*'", str_format))

        # Числа (зелёный)
        num_format = QTextCharFormat()
        num_format.setForeground(QColor("#b5cea8"))
        self.rules.append((r"\b\d+(\.\d+)?\b", num_format))

        # Комментарии (серый)
        com_format = QTextCharFormat()
        com_format.setForeground(QColor("#6a9955"))
        self.rules.append((r"~[^\n]*", com_format))

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            for match in re.finditer(pattern, text):
                start, end = match.span()
                self.setFormat(start, end - start, fmt)

# ==========================================
# 2. РЕДАКТОР С НУМЕРАЦИЕЙ СТРОК
# ==========================================
class CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_number_area = LineNumberArea(self)
        
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.update_line_number_area_width(0)

        font = QFont("Consolas", 12)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.setTabStopDistance(40)

    def line_number_area_width(self):
        digits = 1
        max_val = max(1, self.blockCount())
        while max_val >= 10:
            max_val //= 10
            digits += 1
        space = 10 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#1e1e1e"))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor("#858585"))
                painter.drawText(0, int(top), self.line_number_area.width() - 5, 
                                 self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    def highlight_current_line(self):
        extra_selections = []
        if not self.isReadOnly():
            selection = QTextCharFormat()
            selection.setBackground(QColor("#2a2d2e"))
            selection.setProperty(QTextCharFormat.Property.FullWidthSelection, True)
            cursor = self.textCursor()
            cursor.clearSelection()
            
            from PyQt6.QtWidgets import QTextEdit
            sel = QTextEdit.ExtraSelection()
            sel.format = selection
            sel.cursor = cursor
            extra_selections.append(sel)
            
        self.setExtraSelections(extra_selections)

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor
    def sizeHint(self):
        return QSize(self.codeEditor.line_number_area_width(), 0)
    def paintEvent(self, event):
        self.codeEditor.line_number_area_paint_event(event)

# ==========================================
# 3. ГЛАВНОЕ ОКНО IDE
# ==========================================
class P0PStudio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("p0P Studio (DDK) — [Без имени.p]")
        self.resize(1000, 700)

        # Темная тема интерфейса
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; }
            QWidget { color: #d4d4d4; font-family: 'Segoe UI'; font-size: 10pt; }
            QPushButton { background-color: #333333; border: 1px solid #3c3c3c; padding: 6px 12px; border-radius: 3px; }
            QPushButton:hover { background-color: #444444; }
            QPushButton#runBtn { background-color: #0e639c; border: none; }
            QPushButton#runBtn:hover { background-color: #1177bb; }
            QPlainTextEdit { background-color: #1e1e1e; color: #d4d4d4; border: none; selection-background-color: #264f78; }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Тулбар
        toolbar = QWidget()
        toolbar.setStyleSheet("background-color: #252526; border-bottom: 1px solid #3c3c3c;")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(10, 5, 10, 5)

        self.btn_run = QPushButton("▶ Запустить (F5)")
        self.btn_run.setObjectName("runBtn")
        self.btn_run.clicked.connect(self.run_code)

        self.btn_save = QPushButton("Сохранить (Ctrl+S)")
        self.btn_save.clicked.connect(self.save_file)

        self.btn_open = QPushButton("Открыть")
        self.btn_open.clicked.connect(self.open_file)

        toolbar_layout.addWidget(self.btn_run)
        toolbar_layout.addWidget(self.btn_save)
        toolbar_layout.addWidget(self.btn_open)
        toolbar_layout.addStretch()
        layout.addWidget(toolbar)

        # Сплиттер (Редактор + Терминал)
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        self.editor = CodeEditor()
        self.highlighter = P0PHighlighter(self.editor.document())
        splitter.addWidget(self.editor)

        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Consolas", 10))
        self.console.setStyleSheet("background-color: #111111; color: #0f0; border-top: 1px solid #3c3c3c;")
        self.console.setPlaceholderText("Здесь будет вывод программы...")
        splitter.addWidget(self.console)

        splitter.setSizes([500, 200])
        layout.addWidget(splitter)

        self.current_file = None
        self.temp_file = "temp_ide.p"

        # Процесс для запуска (Дебаггер)
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)

        # Горячие клавиши
        QShortcut(QKeySequence("F5"), self, self.run_code)
        QShortcut(QKeySequence("Ctrl+S"), self, self.save_file)
        QShortcut(QKeySequence("Ctrl+O"), self, self.open_file)

    def run_code(self):
        code = self.editor.toPlainText()
        if not code.strip(): return

        with open(self.temp_file, "w", encoding="utf-8") as f:
            f.write(code)

        self.console.clear()
        self.console.appendPlainText(">>> Запуск интерпретатора p0P...\n")
        
        # Запускаем CLI в фоне
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8") # Чтобы русские буквы не ломались
        self.process.setProcessEnvironment(env)
        
        cli_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cli.py")
        self.process.start(sys.executable, [cli_path, self.temp_file])

    def handle_stdout(self):
        data = self.process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        self.console.moveCursor(QTextCursor.MoveOperation.End)
        self.console.insertPlainText(data)
        self.console.moveCursor(QTextCursor.MoveOperation.End)

    def handle_stderr(self):
        data = self.process.readAllStandardError().data().decode("utf-8", errors="replace")
        self.console.moveCursor(QTextCursor.MoveOperation.End)
        self.console.insertPlainText(data)
        self.console.moveCursor(QTextCursor.MoveOperation.End)

    def save_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить скрипт", "", "p0P Scripts (*.p)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.editor.toPlainText())
            self.current_file = path
            self.setWindowTitle(f"p0P Studio (DDK) — [{os.path.basename(path)}]")

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Открыть скрипт", "", "p0P Scripts (*.p)")
        if path:
            with open(path, "r", encoding="utf-8") as f:
                self.editor.setPlainText(f.read())
            self.current_file = path
            self.setWindowTitle(f"p0P Studio (DDK) — [{os.path.basename(path)}]")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    window = P0PStudio()
    window.show()
    sys.exit(app.exec())