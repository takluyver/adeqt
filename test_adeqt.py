from adeqt import AdeqtWindow, AdeqtWidget


def test_basic(qtbot):
    window = AdeqtWindow()
    window.show()
    qtbot.addWidget(window)

    widget: AdeqtWidget = window.centralWidget()
    widget.entry.setPlainText("print(f'four: {2 + 2}')")
    widget.run_button.click()

    assert widget.entry.toPlainText() == ''
    assert "four: 4" in widget.display.toPlainText()
