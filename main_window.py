from PyQt6 import uic
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *
# from command_history import CommandHistoryw
from figures import FigureGroup
from properties_panel import PropertiesPanel
from settings import DrawSettings
from storage import FigureStorage
from canvas_widget import Canvas
import factory
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from tree_view import TreeView
from commands import CommandManager, GroupCommand, UngroupCommand

class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("main.ui", self)
        self.setWindowTitle("Paint")

        # ---- Инициализация компонентов приложения ----
        self.settings = DrawSettings()
        self.cmd_manager = CommandManager()
        self.storage = FigureStorage(self.settings, cmd_manager=self.cmd_manager)

        # ==== settings -> UI ====
        self.settings.penColorChanged.connect(
            lambda c: self.outlinecolor.setStyleSheet(f"background-color: {c.name()}"))
        self.settings.brushColorChanged.connect(
            lambda c: self.innercolor.setStyleSheet(f"background-color: {c.name()}"))
        self.settings.penWidthChanged.connect(self.pen_width.setValue)
        self.settings.toolChanged.connect(lambda name: getattr(self, name).setChecked(True)
                                          if hasattr(self, name) and name else None)
        self.settings.radiusChanged.connect(self.spinBox_radius.setValue)
        self.cmd_manager.undo_count_changed.connect(lambda count: (self.Undo.setEnabled(count > 0), self.Undo.setText(f"Undo ({count})")))
        self.cmd_manager.redo_count_changed.connect(lambda count: (self.Redo.setEnabled(count > 0), self.Redo.setText(f"Redo ({count})")))
        self.settings.broadcast()
        self.cmd_manager.broadcast()

        # ==== UI -> settings ====
        # figure settings
        self.pen_width.valueChanged.connect(lambda v: setattr(self.settings, "pen_width", v))
        self.pushButton_outlinecolor.clicked.connect(
            lambda: setattr(self.settings, "pen_color",
                            QColorDialog.getColor(self.settings.pen_color, self)))
        self.pushButton_innercolor.clicked.connect(
            lambda: setattr(self.settings, "brush_color",
                            QColorDialog.getColor(self.settings.brush_color, self)))
        self.spinBox_radius.valueChanged.connect(lambda v: setattr(self.settings, "radius", v))
        # group/ungroup
        self.Group_pushButton.clicked.connect(lambda: self.cmd_manager.do(GroupCommand(self.storage, self.storage.get_selected(), self.settings.ess)))
        self.UnGroup_pushButton.clicked.connect(lambda: self.cmd_manager.do(UngroupCommand(self.storage, self.storage.get_selected()[0])) if (len(self.storage.get_selected()) == 1 and isinstance(self.storage.get_selected()[0], FigureGroup)) else None)
        # tool buttons
        for name in factory.list_tools():
            btn = getattr(self, name, None)
            if btn:
                btn.clicked.connect(lambda checked, n=name: setattr(self.settings, "tool", n))
        # save/load
        save_action = getattr(self, "actionSave", None)
        load_action = getattr(self, "actionLoad", None)
        if save_action:
            save_action.triggered.connect(self._on_save)
        if load_action:
            load_action.triggered.connect(self._on_load)
        #arrows
        self.single_arrow.clicked.connect(lambda: self.settings.arrow_tool('single_arrow'))
        self.double_arrow.clicked.connect(lambda: self.settings.arrow_tool('double_arrow'))
        self.delete_arrow.clicked.connect(lambda: self.settings.arrow_tool('none_arrow'))
        self.Undo.triggered.connect(lambda: self.cmd_manager.undo())
        self.Redo.triggered.connect(lambda: self.cmd_manager.redo())
        # self.actionHistory.triggered.connect(self.open_settings)


        # ---- Подменяем placeholder на Canvas (учёт QGridLayout) ----
        placeholder = getattr(self, "canvas", None)
        self.canvas = Canvas(self.settings, self.storage, parent=self.centralwidget)

        if placeholder is not None and placeholder is not self.canvas:
            lay = placeholder.parentWidget().layout() if placeholder.parentWidget() else None
            if lay:
                idx = lay.indexOf(placeholder)

                # взять позицию, убрать старый, вставить новый в те же координаты
                r, c, rs, cs = lay.getItemPosition(idx)
                lay.removeWidget(placeholder)
                placeholder.setParent(None)
                lay.addWidget(self.canvas, r, c, rs, cs)

        # --- Ставим TreeView на место treeView в MainWindow ---
        placeholder = getattr(self, "treeView", None)
        self.treeView = TreeView(self.storage, parent=self.centralwidget)

        if placeholder is not None and placeholder is not self.treeView:
            lay = placeholder.parentWidget().layout() if placeholder.parentWidget() else None
            if lay:
                idx = lay.indexOf(placeholder)

                # взять позицию, убрать старый, вставить новый в те же координаты
                r, c, rs, cs = lay.getItemPosition(idx)
                lay.removeWidget(placeholder)
                placeholder.setParent(None)
                lay.addWidget(self.treeView, r, c, rs, cs)

                # --- вставка PropertiesPanel ---
                self.propertiesPanel = PropertiesPanel(self.storage, parent=self.dockWidgetContents)
                lay.addWidget(self.propertiesPanel, r + 1, c, rs, cs)

        

        # == старт отрисовки ==
        self.show()

    
    # --- диалоги сохранения/загрузки ---
    def _on_save(self):
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить", filter="JSON Files (*.json);;All Files (*)")
        if not path:
            return
        try:
            factory.save(self.storage.get_all(), path)
            QMessageBox.information(self, "Сохранено", f"Фигуры сохранены в {path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить: {e}")

    def _on_load(self):
        path, _ = QFileDialog.getOpenFileName(self, "Загрузить", filter="JSON Files (*.json);;All Files (*)")
        if not path:
            return
        try:
            figs = factory.load(path)
            self.storage.clear_all()
            for f in figs:
                self.storage.add(f)
            QMessageBox.information(self, "Загружено", f"Фигуры загружены из {path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить: {e}")

    # def open_settings(self):
    #     command_history = CommandHistory(self.cmd_manager)
    #     command_history.show()