import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # no display needed

import pytest


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])
