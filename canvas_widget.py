from PyQt6.QtCore import QRect, Qt, QEvent, QSize, QPoint
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QWidget, QMessageBox, QApplication
from settings import DrawSettings
from storage import FigureStorage
import factory
from commands import AddCommand, DeleteCommand, MoveCommand  # <- потребуется импорт

class Canvas(QWidget):
    def __init__(self, settings: DrawSettings, storage: FigureStorage, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: white;")
        # обязательно, чтобы stylesheet фон отрисовывался
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.settings = settings
        self.storage = storage
        self._last_mouse_pos = None
        self._last_mouse_drag = None
        self.storage.canvas_updated.connect(self.update)

    # Клавиатура
    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.storage.cmd_manager.do(DeleteCommand(self.storage, self.storage.get_selected()))
            event.accept(); return
        if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.storage.adjust_size_selected(1)
            event.accept(); return
        if key in (Qt.Key.Key_Minus, Qt.Key.Key_Underscore):
            self.storage.adjust_size_selected(-1)
            event.accept(); return
        if key == Qt.Key.Key_Escape:
            self.storage.deselect_all()
            event.accept(); return
        if key == Qt.Key.Key_C and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.storage.copy_selected_to_clipboard()
            event.accept(); return
        if key == Qt.Key.Key_X and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.storage.cut_selected_to_clipboard()
        if key == Qt.Key.Key_V and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if self._last_mouse_pos:
                pos = self._last_mouse_pos
            else:
                pos = QPoint(self.settings.csize.width() // 2, self.settings.csize.height() // 2)
            self.paste_selected_from_clipboard(pos, QRect(0, 0, self.settings.csize.width(), self.settings.csize.height()))
            event.accept(); return
        super().keyPressEvent(event)
        if key == Qt.Key.Key_Z and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.storage.cmd_manager.undo()
            event.accept(); return

    # Мышь
    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        if event.buttons() & Qt.MouseButton.LeftButton:
            # вычисление move на разнице между last pos и текущей позицией
            if self._last_mouse_pos is None:
                self._last_mouse_pos = pos
            dx = pos.x() - self._last_mouse_pos.x()
            dy = pos.y() - self._last_mouse_pos.y()
            self._last_mouse_pos = pos

            figs = self.storage.get_selected()
            self.storage.move(figs, dx, dy, bounds=QRect(0, 0, self.settings.csize.width(), self.settings.csize.height()))
        else:
            # только для отображения курсора (нет функциональности)
            if any(fig.hit_test(pos.x(), pos.y()) for fig in self.storage.get_all()):
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        
        pos = event.position().toPoint()
        self._last_mouse_drag = pos
        self._last_mouse_pos = pos 
        self.setFocus(Qt.FocusReason.MouseFocusReason)

        mods = event.modifiers()
        # выбор
        for fig in reversed(self.storage.get_all()):
            if fig.hit_test(pos.x(), pos.y()):
                if mods & Qt.KeyboardModifier.ControlModifier:
                    self.storage.select_figure(fig)
                else:
                    # only selected figure
                    self.storage.deselect_all()
                    self.storage.select_figure(fig, state=True)
                self.update()
                return
        if not (mods & Qt.KeyboardModifier.ControlModifier):
            self.storage.deselect_all()

        # создание
        tool_name = self.settings.tool
        if tool_name:
            try:
                figure = factory.create(tool_name, pos.x(), pos.y(), ess=self.settings.ess)
            except ValueError:
                QMessageBox.information(self, "info", f"Unknown tool: {tool_name}")
                return
            except TypeError:
                # если инструмент не требует координат (например Hand) — игнорируем создание
                return
            self.storage.cmd_manager.do(AddCommand(self.storage, figure))


    def mouseReleaseEvent(self, event):
        # Фиксируем завершение перетаскивания: если был сдвиг — создаём команду MoveCommand
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._last_mouse_drag is None:
            return
        

        curr_pos = event.position().toPoint()
        dx = curr_pos.x() - self._last_mouse_drag.x()
        dy = curr_pos.y() - self._last_mouse_drag.y()
        if dx != 0 or dy != 0:
            figs = self.storage.get_selected()
            bounds = QRect(0, 0, self.settings.csize.width(), self.settings.csize.height())
            self.storage.cmd_manager.do(MoveCommand(self.storage, [(fig, dx, dy) for fig in figs], bounds=bounds), execute=False)

        self._last_mouse_drag = None
        self._last_mouse_pos = None


    # Отрисовка
    def paintEvent(self, _):
        painter = QPainter(self)
        #отрисовка фигур
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        print(f'{__name__} - paintEvent: всего фигур: {len(self.storage.get_all())}')
        for fig in self.storage.get_all():
            fig.draw(painter)
        #отрисовка стрелок
        self.storage.paint_arrows(painter)

        painter.end()

    # ресайз: запрет уменьшения, если не помещаются
    def resizeEvent(self, event):
        new_size: QSize = event.size()
        w, h = new_size.width(), new_size.height()
        fits = True
        for fig in self.storage.get_all():
            if getattr(fig, "finished", True) is False:
                continue
            if not fig.is_fit_in_bounds(QRect(fig.bounds()), QRect(0, 0, w, h)):
                fits = False
                break
        if not fits:
            # откатываем размер
            self.resize(event.oldSize())
            QMessageBox.information(self, "Размер", "Нельзя уменьшить окно: фигуры не помещаются.")
            return
        self.settings.csize = new_size
        super().resizeEvent(event)


    def paste_selected_from_clipboard(self, to_where: QPoint, bounds: QRect):
        # получаем текст из системного буфера обмена
        try:
            data = QApplication.clipboard().text()
            figure = factory.from_json(data)[0]

            if not figure:
                print("No figure found in clipboard data.")
                return

            fig_center = figure.get_center()
            dx = to_where.x() - fig_center.x()
            dy = to_where.y() - fig_center.y()

            # позиционируем фигуру по указанным координатам
            figure.change_position(dx, dy, bounds)
            self.storage.add(figure)
            self.update()

            print("Pasted from clipboard:", data)
        except Exception as e:
            print("Clipboard error:", e)