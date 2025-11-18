from commands import CommandManager
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QScrollArea, QButtonGroup, QApplication, QLabel, QVBoxLayout

class CommandHistory(QWidget):
    def __init__(self, cmd_manager: CommandManager):
        super().__init__()
        self.cmd_manager = cmd_manager
        self.setWindowTitle("История команд")
        self.resize(1000, 200)

        # главный вертикальный лэйаут
        main_layout = QVBoxLayout(self)
        self.info_label = QLabel("", self)
        main_layout.addWidget(self.info_label)

        # scroll area для горизонтального ряда кнопок
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        main_layout.addWidget(self.scroll)

        self.container = QWidget()
        self.hlay = QHBoxLayout(self.container)
        self.hlay.setContentsMargins(4, 4, 4, 4)
        self.hlay.setSpacing(6)
        self.scroll.setWidget(self.container)

        # группа кнопок — эксклюзивный выбор
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)

        # слоты обновления при изменении менеджера команд
        self.cmd_manager.undo_count_changed.connect(self.refresh)
        self.cmd_manager.redo_count_changed.connect(self.refresh)

        self.refresh()

    def refresh(self, *_):
        # очистка старых кнопок
        while self.hlay.count():
            item = self.hlay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)

        undo = list(self.cmd_manager.get_undo())
        redo = list(self.cmd_manager.get_redo())
        history = [*undo, *redo]
        total = len(history)
        n_undo = len(undo)
        current_idx = -1 if n_undo == 0 else n_undo - 1

        # инфо
        self.info_label.setText(f"Undo: {n_undo}, Redo: {len(redo)}")

        if total == 0:
            lbl = QLabel("История пуста", self.container)
            self.hlay.addWidget(lbl)
            return

        for i, cmd in enumerate(history):
            name = getattr(cmd, "__class__", None)
            text = cmd.__class__.__name__ if name else str(cmd)
            btn = QPushButton(text, self.container)
            btn.setCheckable(True)
            # простой визуальный раздел: команды из redo — светлее
            if i >= n_undo:
                btn.setStyleSheet("background-color: #f2f2f2;")
            else:
                btn.setStyleSheet("")
            if i == current_idx:
                btn.setChecked(True)
                btn.setStyleSheet(btn.styleSheet() + "border: 2px solid #1976d2;")
            # привязка индекса
            btn.clicked.connect(lambda checked, idx=i: self.navigate_to(idx))
            self.btn_group.addButton(btn)
            self.hlay.addWidget(btn)

        # добавим растягивающий элемент
        self.hlay.addStretch()

    def navigate_to(self, index: int):
        # целевое количество выполненных команд = index + 1
        desired = index + 1
        current = self.cmd_manager.undo_count()
        delta = desired - current
        # выполняем нужное число undo/redo
        if delta > 0:
            for _ in range(delta):
                self.cmd_manager.redo()
                QApplication.processEvents()
        elif delta < 0:
            for _ in range(-delta):
                self.cmd_manager.undo()
                QApplication.processEvents()
        # обновляем визуально
        self.refresh()
