from PyQt6.QtWidgets import QWidget, QFormLayout, QSpinBox, QDoubleSpinBox, QLineEdit, QCheckBox, QPushButton, QLabel, QColorDialog, QVBoxLayout
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt
import inspect
from settings import DrawEssentials

SIMPLE_INT_RANGE = (-100000, 100000)

class PropertiesPanel(QWidget):
    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.layout = QVBoxLayout(self)
        self.form = QFormLayout()
        self.layout.addLayout(self.form)
        self.info_label = QLabel("No selection")
        self.layout.addWidget(self.info_label)
        self._editors = {}
        # обновляем при изменении canvas / selection
        try:
            self.storage.canvas_updated.connect(self.rebuild)
        except Exception:
            pass
        self.rebuild()

    def clear_form(self):
        # удалить виджеты из формы
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

        obj = selected[0]
        self.info_label.setText(f"{obj.__class__.__name__}")
        # получить списком пар (name, value) только публичные атрибуты
        members = []
        for name, _ in inspect.getmembers(type(obj), lambda x: isinstance(x, property)):
            # properties класса — читать через getattr
            try:
                val = getattr(obj, name)
                members.append((name, val))
            except Exception:
                continue

        # дополнительно базовые атрибуты — через obj.__dict__
        for name, val in obj.__dict__.items():
            if name.startswith("_"):
                continue
            members.append((name, val))

        # уникализировать по имени, сохранить порядок
        seen = set()
        filtered = []
        for n, v in members:
            if n in seen:
                continue
            seen.add(n)
            filtered.append((n, v))

        for name, val in filtered:
            # игнорировать служебные поля типа finished, selected если нужно — но показываем selected как флаг
            if name in ("points", "get_center", "notify_move"):
                continue

            editor = self._make_editor(obj, name, val)
            if editor is not None:
                label = name
                self.form.addRow(label, editor)
                self._editors[name] = editor

        # специально: если у объекта есть поле ess (DrawEssentials) — развернуть
        ess = getattr(obj, "ess", None)
        if isinstance(ess, DrawEssentials):
            # заголовок
            self.form.addRow(QLabel("<b>ess</b>"), QLabel(""))
            # pen_color
            btn_pen = QPushButton()
            btn_pen.setStyleSheet(f"background-color: {ess.pen_color.name()}")
            btn_pen.clicked.connect(lambda _, o=obj: self._choose_color(o, "ess.pen_color"))
            self.form.addRow("pen_color", btn_pen)
            # brush_color
            btn_br = QPushButton()
            btn_br.setStyleSheet(f"background-color: {ess.brush_color.name()}")
            btn_br.clicked.connect(lambda _, o=obj: self._choose_color(o, "ess.brush_color"))
            self.form.addRow("brush_color", btn_br)
            # pen_width
            spin_pw = QSpinBox()
            spin_pw.setRange(SIMPLE_INT_RANGE[0], SIMPLE_INT_RANGE[1])
            spin_pw.setValue(ess.pen_width)
            spin_pw.valueChanged.connect(lambda v, o=obj: self._set_nested(o, "ess.pen_width", int(v)))
            self.form.addRow("pen_width", spin_pw)
            # radius
            spin_r = QSpinBox()
            spin_r.setRange(1, SIMPLE_INT_RANGE[1])
            spin_r.setValue(ess.radius)
            spin_r.valueChanged.connect(lambda v, o=obj: self._set_nested(o, "ess.radius", int(v)))
            self.form.addRow("radius", spin_r)

    def _make_editor(self, obj, name, value):
        # int
        if isinstance(value, int):
            spin = QSpinBox()
            spin.setRange(SIMPLE_INT_RANGE[0], SIMPLE_INT_RANGE[1])
            spin.setValue(value)
            spin.valueChanged.connect(lambda v, o=obj, n=name: self._apply(o, n, int(v)))
            return spin
        # float
        if isinstance(value, float):
            dsp = QDoubleSpinBox()
            dsp.setRange(-1e9, 1e9)
            dsp.setDecimals(6)
            dsp.setValue(value)
            dsp.valueChanged.connect(lambda v, o=obj, n=name: self._apply(o, n, float(v)))
            return dsp
        # bool
        if isinstance(value, bool):
            cb = QCheckBox()
            cb.setChecked(value)
            cb.stateChanged.connect(lambda st, o=obj, n=name: self._apply(o, n, bool(st == Qt.CheckState.Checked)))
            return cb
        # str
        if isinstance(value, str):
            le = QLineEdit()
            le.setText(value)
            le.editingFinished.connect(lambda o=obj, n=name, w=le: self._apply(o, n, w.text()))
            return le
        # QColor
        if isinstance(value, QColor):
            btn = QPushButton()
            btn.setStyleSheet(f"background-color: {value.name()}")
            btn.clicked.connect(lambda _, o=obj, n=name: self._choose_color(o, n))
            return btn
        # for lists/tuples show read-only summary
        if isinstance(value, (list, tuple)):
            lbl = QLabel(str(value))
            lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            return lbl
        # fallback: show repr read-only
        lbl = QLabel(repr(value))
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return lbl

    def _choose_color(self, obj, attr_path: str):
        # attr_path can be "ess.pen_color" or "pen_color"
        parts = attr_path.split(".")
        try:
            if len(parts) == 1:
                cur = getattr(obj, parts[0])
                c = QColorDialog.getColor(cur, self)
                if c.isValid():
                    self._apply(obj, parts[0], c)
            else:
                base = getattr(obj, parts[0])
                cur = getattr(base, parts[1])
                c = QColorDialog.getColor(cur, self)
                if c.isValid():
                    setattr(base, parts[1], c)
                    try:
                        self.storage.canvas_updated.emit()
                    except Exception:
                        pass
                    # обновить кнопки/виджеты
                    self.rebuild()
        except Exception:
            pass

    def _set_nested(self, obj, path: str, value):
        parts = path.split(".")
        if len(parts) != 2:
            return
        base = getattr(obj, parts[0], None)
        if base is None:
            return
        try:
            setattr(base, parts[1], value)
            try:
                self.storage.canvas_updated.emit()
            except Exception:
                pass
        except Exception:
            pass

    def _apply(self, obj, name, value):
        try:
            setattr(obj, name, value)
            try:
                self.storage.canvas_updated.emit()
            except Exception:
                pass
        except Exception:
            # если напрямую не удалось — попытаться через свойства (property setter)
            try:
                prop = getattr(type(obj), name, None)
                if isinstance(prop, property):
                    setattr(obj, name, value)
                    try:
                        self.storage.canvas_updated.emit()
                    except Exception:
                        pass
            except Exception:
                pass