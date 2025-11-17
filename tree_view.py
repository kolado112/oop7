from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem
from PyQt6.QtCore import Qt
from observer import Observer
from figures import FigureGroup, Figure
from commands import DeleteCommand


class TreeView(QTreeWidget, Observer):
    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.setHeaderLabels(["TreeView"])
        self.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)

        self._updating = False

        self.storage.add_observer(self)
        self.itemSelectionChanged.connect(self._on_item_selection_changed)

        self._rebuild()

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.storage.cmd_manager.do(DeleteCommand(self.storage, self.storage.get_selected()))
            event.accept(); return

    # === update от storage ===
    def update(self, subject, event) -> None:
        if subject is self.storage and not self._updating:
            self._rebuild()

    # === служебные методы ===
    @staticmethod
    def _make_item(parent, item: Figure, selectable: bool) -> QTreeWidgetItem | None:
        # Если у фигуры есть метод/атрибут finished, считаем её допустимой только если:
        # - атрибут/метод отсутствует (тогда работаем), или
        # - атрибут есть и равно True, или
        # - атрибут — callable и возвращает True.
        finished = getattr(item, "finished", None)
        if callable(finished):
            if not finished():
                return None
        elif finished is False:
            return None

        it = QTreeWidgetItem(parent, [item.__class__.__name__])
        it.setData(0, Qt.ItemDataRole.UserRole, item)

        # настраиваем флаги
        flags = it.flags()
        if not selectable:
            flags &= ~Qt.ItemFlag.ItemIsSelectable
            print(Qt.ItemFlag.ItemIsSelectable)
        it.setFlags(flags)


        if selectable and getattr(item, "selected", False):
            it.setSelected(True)

        return it

    def _rebuild(self):
        self._updating = True
        self.clear()

        for fig in self.storage.get_all():
            if isinstance(fig, FigureGroup):
                # саму группу можно выделять
                parent_item = self._make_item(self, fig, selectable=True)
                # детей группы — нельзя
                for child in fig.figures:
                    self._make_item(parent_item, child, selectable=False)
            else:
                # одиночные фигуры на верхнем уровне — можно
                self._make_item(self, fig, selectable=True)

        self._updating = False

    def _on_item_selection_changed(self):
        if self._updating:
            return

        self._updating = True

        selected_figs = set()
        for it in self.selectedItems():
            fig = it.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(fig, Figure):
                selected_figs.add(fig)

        self.storage.deselect_all()
        for fig in selected_figs:
            if fig in self.storage.get_all():
                self.storage.select_figure(fig, state=True)
            else:
                setattr(fig, "selected", True)

        self.storage.canvas_updated.emit()

        self._updating = False
