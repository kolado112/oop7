import sys
from PyQt6.QtWidgets import QApplication
from main_window import Main
import faulthandler
faulthandler.enable()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Main()
    sys.exit(app.exec())
