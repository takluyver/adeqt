# Console plugin for Python Qt applications

Adeqt gives you a Python shell inside your Qt applications using PyQt or PySide.
You can use this for simple debugging or as a 'power user' feature.

## How to use

Install the adeqt package: `pip install adeqt`.

If you don't want to add any dependencies, you can copy `adeqt.py` into your own
project instead. You might also want to change the imports to use your chosen
Python Qt package directly (it normally uses the
[QtPy](https://pypi.org/project/QtPy/) compatibility layer).

Connect up a menu entry or a keyboard shortcut to open the Adeqt window like
this:

```python
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QAction, QMainWindow, QShortcut


class MainWindow(QMainWindow):

    def __init__(self, parent=None):
        super().__init__(parent)

        # ... Other application setup ...

        # Menu entry
        adeqt_action = QAction("Python console", self)
        adeqt_action.triggered.connect(self.show_adeqt)
        some_menu.addAction(adeqt_action)

        # Keyboard shortcut (here F12)
        adeqt_shortcut = QShortcut(QKeySequence(Qt.Key_F12), self)
        adeqt_shortcut.activated.connect(self.show_adeqt)

    adeqt_window = None

    def show_adeqt(self):
        # Change to 'from .adeqt ...' if you copy adeqt into your application
        from adeqt import AdeqtWindow
        if self.adeqt_window is None:
            self.adeqt_window = AdeqtWindow({'window': self}, parent=self)
        self.adeqt_window.show()
```

The dictionary you pass to `AdeqtWindow` defines variables that will be
available in the console. This will normally have at least the main
window/application object, and any other objects you want convenient access to.

When using the console window:

- Ctrl-Enter executes the existing code
- Tab shows available completions
- Ctrl-W closes the console window

## Design & limitations

- Adeqt is deliberately **simple**, providing a basic console experience. It's
meant to be easy to copy into your project and easy to modify as required.

- It **doesn't protect anything from malicious users**. Users running a Python
application can probably do anything anyway, but Adeqt makes it very easy.
If you need to restrict what users can do, think about security at other levels.

- **User code runs in the main thread**. This makes it easy to safely call Qt
methods, but if you run something slow from the console, the GUI locks up until
it finishes.

## Alternatives

The [Jupyter Qt Console](https://github.com/jupyter/qtconsole) can be [embedded
in an application](https://qtconsole.readthedocs.io/en/stable/#embedding-the-qtconsole-in-a-qt-application).
This is a much more featureful console - with rich output, syntax highlighting,
better tab completions, etc. - but it's designed to run code in a separate
'kernel' process. Running the code in the same process as the console
('inprocess') is possible, but not well supported. It also needs quite a few
dependencies.

Debuggers can pause your code during execution and give you a place to run
commands and explore the stack. Some modern debuggers can also 'attach' to a
process which wasn't started in a debugger. A good debugger is strictly more
powerful than Adeqt, but that power also makes it trickier to use.
