import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from core.engine_service import find_stockfish
from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    path = find_stockfish()
    if not path:
        QMessageBox.critical(None, "Falta Stockfish",
                             "No se encontró Stockfish.\nColoca el ejecutable en assets/engines/, "
                             "define STOCKFISH_PATH o agrégalo al PATH.\nDescarga: https://stockfishchess.org/download/")
        return 1
    window = MainWindow(path)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
