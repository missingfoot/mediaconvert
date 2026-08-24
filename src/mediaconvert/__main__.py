"""mediaconvert entry point."""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from mediaconvert.ui import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    initial_paths = [Path(p) for p in sys.argv[1:]] if len(sys.argv) > 1 else None
    window = MainWindow(initial_paths=initial_paths)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
