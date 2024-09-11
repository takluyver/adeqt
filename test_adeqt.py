from adeqt import AdeqtWindow, AdeqtWidget, CodeEntry


def test_basic(qtbot):
    window = AdeqtWindow()
    window.show()
    qtbot.addWidget(window)

    widget: AdeqtWidget = window.centralWidget()
    entry: CodeEntry = widget.entry
    entry.setPlainText("print(f'four: {2 + 2}')")
    widget.run_button.click()

    assert entry.toPlainText() == ''
    assert "four: 4" in widget.display.toPlainText()

    # Navigating into history ...
    entry.setPlainText("12 / 4")
    entry.hist_up()
    assert entry.hist_index == -1
    assert entry.toPlainText().startswith("print")
    entry.hist_up()
    assert entry.hist_index == -1

    # & back out
    entry.hist_down()
    assert entry.hist_index == 0
    assert entry.toPlainText() == "12 / 4"
    entry.hist_down()
    assert entry.hist_index == 0
