from PyQt6.QtWidgets import QWidget, QFormLayout, QSpinBox, QDoubleSpinBox, QLineEdit, QCheckBox, QPushButton, QLabel, QColorDialog, QVBoxLayout
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt
import inspect
from settings import DrawEssentials

SIMPLE_INT_RANGE = (-1000, 1000)
ignoring_attrs_names = ('ess',)

class PropertiesPanel(QWidget):
    def __init__(self, storage, parent=None):
        super().__init__(parent)

        self.storage = storage

        self.layout = QVBoxLayout(self)
        self.info_label = QLabel("No selection")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("font-weight: bold;")
        self.layout.addWidget(self.info_label)
        self.form = QFormLayout()
        self.layout.addLayout(self.form)

        self._editors = {}
        # обновляем при изменении canvas / selection
        self.storage.canvas_updated.connect(self.rebuild)
        self.rebuild()

    def clear_form(self):
        # удалить виджеты из form и очистить хранилище редакторов
        while self.form.rowCount() > 0:
            self.form.removeRow(0)
        self._editors.clear()

    def rebuild(self):
        self.clear_form()
        selected = self.storage.get_selected()
        if not selected:
            self.info_label.setText("Нет выбранных объектов")
            return
        if len(selected) > 1:
            self.info_label.setText("Выбрано несколько объектов — свойства недоступны")
            return
        # получение объекта и установка заголовка
        obj = selected[0]
        self.info_label.setText(f"{obj.__class__.__name__}")


        # получить списком пар (name, value) только публичные атрибуты (property)
        changable_attrs = []
        for name, prop in inspect.getmembers(type(obj), lambda x: isinstance(x, property)):
            if name.startswith("_"):
                continue
            # пропускаем read-only property
            if prop.fset is None:
                continue
            try:
                val = getattr(obj, name)
                changable_attrs.append((name, val))
            except Exception as e:
                print(f'error in changable_attrs: {e}')


        # атрибута для просмотра через obj.__dict__
        view_only_attrs = []
        for name, val in obj.__dict__.items():
            if name.startswith("_"):
                continue
            view_only_attrs.append((name, val))

        # фильтрация запрещенных
        changable_attrs = [(name, val) for name, val in changable_attrs if name not in ignoring_attrs_names]
        view_only_attrs = [(name, val) for name, val in view_only_attrs if name not in ignoring_attrs_names]

        # сначала editable properties (property), затем простые поля (read-only)
        if changable_attrs:
            self.proceed_attributes(obj, changable_attrs, editable=True)
        if view_only_attrs:
            self.proceed_attributes(obj, view_only_attrs, editable=False)

    
    def proceed_attributes(self, obj, attrs, editable=True):
        """
        Обработать список (name, value). editable=True — подключаем обработчики изменений,
        иначе показываем только для чтения.
        """
        from functools import partial

        # Особое разворачивание поля ess
        # Сначала обычные атрибуты
        for name, val in attrs:
            print(f"Processing attribute: {name}, value: {val}")

            editor = self._make_editor(obj, name, val, editable=editable)
            if editor is not None:
                label = name
                self.form.addRow(label, editor)
                self._editors[name] = editor

    def _make_editor(self, obj, name, value, editable=True):
        """Создаёт виджет-редактор для значения."""

        # bool
        if isinstance(value, bool):
            cb = QCheckBox()
            cb.setChecked(value)
            if editable:
                cb.stateChanged.connect(lambda st, o=obj, n=name: self._apply(o, n, bool(st == Qt.CheckState.Checked)))
            else:
                cb.setEnabled(False)
            return cb
        # int
        if isinstance(value, int):
            spin = QSpinBox()
            spin.setRange(SIMPLE_INT_RANGE[0], SIMPLE_INT_RANGE[1])
            spin.setValue(value)
            if editable:
                spin.valueChanged.connect(lambda v, o=obj, n=name: self._apply(o, n, int(v)))
            else:
                spin.setEnabled(False)
            return spin
        # str
        if isinstance(value, str):
            le = QLineEdit()
            le.setText(value)
            if editable:
                le.editingFinished.connect(lambda o=obj, n=name, w=le: self._apply(o, n, w.text()))
            else:
                le.setReadOnly(True)
            return le
        # QColor
        if isinstance(value, QColor):
            btn = QPushButton()
            try:
                btn.setStyleSheet(f"background-color: {value.name()}")
            except Exception:
                pass

            if editable:
                def on_click(_, o=obj, n=name, b=btn):
                    cur = getattr(o, n, value)
                    if not isinstance(cur, QColor):
                        cur = QColor()
                    c = QColorDialog.getColor(cur, self)
                    if c.isValid():
                        b.setStyleSheet(f"background-color: {c.name()}")
                        self._apply(o, n, c)

                btn.clicked.connect(on_click)
            else:
                btn.setEnabled(False)
            return btn
        # for lists/tuples show read-only summary
        if isinstance(value, (list, tuple)):
            lbl = QLabel(str(value))
            lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            return lbl
        

        # # остальное
        lbl = QLabel(repr(value))
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return lbl

    def _apply(self, obj, name, value):
        try:
            setattr(obj, name, value)
        except Exception as e:
            print(f"_apply error for {name}: {e}")
            return
        try:
            self.storage.canvas_updated.emit()
        except Exception:
            pass
