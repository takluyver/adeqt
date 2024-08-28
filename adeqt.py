"""An interactive Python shell plugin for PyQt & PySide applications

MIT license:

Copyright (c) 2024 Thomas Kluyver

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""
import ast
import builtins
import io
import sys
import tokenize
import traceback
from contextlib import contextmanager

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt

__version__ = "0.1.1"


def add_prompt(code: str):
    lines = code.rstrip().splitlines(keepends=True)
    return ''.join(['>>> ' + lines[0]] + ['... ' + l for l in lines[1:]]) + '\n'


class OutputStream:
    def __init__(self, shell_widget: 'AdeqtWidget'):
        self.shell_widget = shell_widget

    def write(self, text):
        self.shell_widget.write(text)
        # self.widget.append(text)

    def flush(self):
        pass


class IncompleteToken(tokenize.TokenInfo):
    pass


def tokenize_maybe_incomplete(code: str):
    gen = tokenize.generate_tokens(io.StringIO(code).readline)
    last_end = (1, 0)
    while True:
        try:
            tok: tokenize.TokenInfo = next(gen)
        except StopIteration:
            break
        except tokenize.TokenError:
            lines = [None] + code.splitlines()
            row, col = last_end
            s = lines[row][col:] + ''.join(lines[row + 1:])
            if s and not s.isspace():
                start = last_end
                end = (len(lines) - 1, len(lines[-1]))
                yield IncompleteToken(tokenize.STRING, s, start, end, lines[row])
        else:
            last_end = tok.end
            yield tok


def get_dotted_name(code: str):
    name_parts = []
    trailing_dot = False
    for token in tokenize_maybe_incomplete(code):
        if token.type == tokenize.NAME:
            trailing_dot = False
            name_parts.append(token.string)
        elif token.type in (tokenize.NEWLINE, tokenize.NL, tokenize.ENDMARKER):
            # Some combination of these is added at the end of the input
            pass
        elif token.exact_type == tokenize.DOT:
            trailing_dot = True
        else:
            trailing_dot = False
            name_parts.clear()

    if trailing_dot or not name_parts:
        name_parts.append('')
    return tuple(name_parts)


class CodeEntry(QtWidgets.QPlainTextEdit):
    # Tab completion machinery largely copied from Qt custom completer example
    # https://doc.qt.io/qt-5/qtwidgets-tools-customcompleter-example.html
    def __init__(self, namespace, parent=None):
        super().__init__(parent)
        self.namespace = namespace

        self.document().setDefaultFont(QtGui.QFont("monospace"))
        self.setPlaceholderText("Type code here, Ctrl+Return to run")

        self.completer = QtWidgets.QCompleter(["foo", "bar", "baz", "bang"], self)
        self.completer.setWidget(self)
        self.completer.activated[str].connect(self.insertCompletion)

        self._complete_attrs_key = None

    def keyPressEvent(self, e):
        k = e.key()
        if not self.completer.popup().isVisible():
            if k == Qt.Key_Tab:
                self.show_completions()
                return
            else:
                return super().keyPressEvent(e)

        # If we get here, the completion popup was already open
        if k in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Escape, Qt.Key_Tab, Qt.Key_Backtab):
            # These keys are handled by the completion popup
            e.ignore()
            return

        super().keyPressEvent(e)
        ctrl_or_shift = bool(e.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier))
        if ctrl_or_shift and not e.text():
            return  # Ctrl/Shift pressed by itself

        eow = "~!@#$%^&*()_+{}|:\"<>?,./;'[]\\-="  # End Of Word
        if (
                e.modifiers() in (Qt.NoModifier, Qt.ShiftModifier)
                and e.text()
                and e.text()[-1] not in eow
                and k != Qt.Key_Backspace
        ):
            self.show_completions()  # Added character, update completions
        else:
            self.completer.popup().hide()

    def show_completions(self):
        c = self.completer
        dotted_name = get_dotted_name(self.textToCursor())
        *attr_of, prefix = dotted_name
        if attr_of != self._complete_attrs_key:
            c.setModel(QtCore.QStringListModel(self.find_child_names(attr_of)))
            self._complete_attrs_key = attr_of

        if c.completionPrefix() != prefix:
            c.setCompletionPrefix(prefix)
            c.popup().setCurrentIndex(c.completionModel().index(0, 0))

        cr = self.cursorRect()
        cr.setWidth(c.popup().sizeHintForColumn(0)
                    + c.popup().verticalScrollBar().sizeHint().width())
        c.complete(cr)

    def insertCompletion(self, completion: str):
        tc = self.textCursor()
        tc.movePosition(QtGui.QTextCursor.Left)
        tc.movePosition(QtGui.QTextCursor.EndOfWord)
        tc.insertText(completion[len(self.completer.completionPrefix()):])
        self.setTextCursor(tc)

    def textToCursor(self):
        tc = self.textCursor()
        tc.movePosition(QtGui.QTextCursor.Start, QtGui.QTextCursor.KeepAnchor)
        return tc.selectedText()

    def textUnderCursor(self):
        tc = self.textCursor()
        tc.select(QtGui.QTextCursor.WordUnderCursor)
        return tc.selectedText()

    def find_child_names(self, name_parts):
        if not name_parts:
            return sorted(list(self.namespace) + dir(builtins))

        missing = object()
        obj = self.namespace.get(name_parts[0], missing)
        if obj is missing:
            obj = getattr(builtins, name_parts[0], missing)
        if obj is missing:
            return []

        for name in name_parts[1:]:
            obj = getattr(obj, name, missing)
            if obj is missing:
                return []

        # Sort 'name' before '_name' before '__name', and case-insensitive
        return sorted(dir(obj), key=lambda n: (len(n) - len(n.lstrip('_')), n.lower()))


class AdeqtWidget(QtWidgets.QWidget):
    def __init__(self, variables=None, parent=None):
        super().__init__(parent)
        vbox = QtWidgets.QVBoxLayout()
        self.setLayout(vbox)

        self.display = QtWidgets.QTextEdit()
        self.display.setFontFamily('monospace')
        self.display.setReadOnly(True)
        self.write_cursor = self.display.textCursor()
        vbox.addWidget(self.display, stretch=3)
        self.output_stream = OutputStream(self)

        self.namespace = {'adeqt': self}
        if variables is not None:
            self.namespace.update(variables)
        self.entry = CodeEntry(self.namespace, self)

        vbox.addWidget(self.entry)
        self.entry.setFocus()

        run_shortcut = QtWidgets.QShortcut(
            QtGui.QKeySequence(Qt.CTRL | Qt.Key_Return), self.entry
        )
        run_shortcut.activated.connect(self.run)

        self.run_button = QtWidgets.QPushButton("Run")
        self.run_button.clicked.connect(self.run)
        vbox.addWidget(self.run_button)

    def write(self, text):
        self.write_cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        self.write_cursor.insertText(text)
        vsb = self.display.verticalScrollBar()
        vsb.setValue(vsb.maximum())  # Scroll to end

    def displayhook(self, value):
        if value is None:
            return
        builtins._ = value
        self.write(repr(value) + '\n')

    @contextmanager
    def capture_output(self):
        save_stdout = sys.stdout
        save_stderr = sys.stderr
        save_displayhook = sys.displayhook
        sys.stdout = self.output_stream
        sys.stderr = self.output_stream
        sys.displayhook = self.displayhook
        try:
            yield
        finally:
            sys.stdout = save_stdout
            sys.stderr = save_stderr
            sys.displayhook = save_displayhook

    def run(self):
        code = self.entry.toPlainText()
        self.write(add_prompt(code))

        try:
            mod = ast.parse(code)
        except Exception as e:
            # Invalid syntax
            es = traceback.format_exception_only(type(e), e)
            self.write(''.join(es).rstrip() + '\n')
            return

        if not mod.body:
            # No code to execute, e.g. only comments
            self.entry.clear()
            return

        if isinstance(mod.body[-1], ast.Expr):
            expr = mod.body.pop()
            try:
                c1 = compile(mod, "<string>", "exec")
                c2 = compile(ast.Interactive([expr]), "<string>", "single")
            except Exception as e:
                es = traceback.format_exception_only(type(e), e)
                self.write(''.join(es).rstrip() + '\n')
                return
            code_objs = [c1, c2]
        else:
            try:
                code_objs = [compile(mod, "<string>", "exec")]
            except Exception as e:
                es = traceback.format_exception_only(type(e), e)
                self.write(''.join(es).rstrip() + '\n')
                return

        # At this point we've parsed & byte-compiled the entered code
        self.entry.clear()

        with self.capture_output():
            try:
                for code_obj in code_objs:
                    exec(code_obj, self.namespace)
            except Exception as e:
                es = traceback.format_exception(type(e), e, e.__traceback__)
                self.write(''.join(es).rstrip() + '\n')


class AdeqtWindow(QtWidgets.QMainWindow):
    def __init__(self, variables=None, parent=None):
        super().__init__(parent)
        self.resize(800, 600)
        self.setCentralWidget(AdeqtWidget(variables, self))
        close_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(Qt.CTRL | Qt.Key_W), self)
        close_shortcut.activated.connect(self.close)


if __name__ == "__main__":
    qapp = QtWidgets.QApplication([])
    window = AdeqtWindow({'app': qapp})
    window.show()
    qapp.exec()
