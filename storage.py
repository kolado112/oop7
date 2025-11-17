from __future__ import annotations
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QApplication
import factory
from settings import DrawSettings, DrawEssentials, ArrowTools
from figures import Figure, FigureGroup, Hand
from observer import Object, Event

class FigureStorage(QObject, Object):
    canvas_updated = pyqtSignal()

    def __init__(self, settings: DrawSettings | None = None, cmd_manager=None):
        super().__init__()
        self.__figures = []
        self.settings = settings if isinstance(settings, DrawSettings) else DrawSettings()

        # ссылка на менеджер команд для удобства создания команд изнутри хранилища
        self.cmd_manager = cmd_manager

        self.settings.penWidthChanged.connect(self._on_pen_width_changed)
        self.settings.brushColorChanged.connect(self._on_brush_color_changed)
        self.settings.penColorChanged.connect(self._on_pen_color_changed)
        self.settings.radiusChanged.connect(self._on_radius_changed)
        self.settings.frameArrowsTriggered.connect(self._on_frame_arrows)

        # при любом canvas_updated уведомляем также наблюдателей через Observer
        # теперь передаём корректный Event — чтобы Observer.update мог читать event.type и payload
        self.canvas_updated.connect(lambda: self.notify(Event(type="canvas_updated", payload=None)))

    def _on_pen_width_changed(self, w: int):
        for f in self.get_selected():
            f.ess.pen_width = w
        self.canvas_updated.emit()

    def _on_brush_color_changed(self, c):
        for f in self.get_selected():
            f.ess.brush_color = c
        self.canvas_updated.emit()

    def _on_pen_color_changed(self, c):
        for f in self.get_selected():
            f.ess.pen_color = c
        self.canvas_updated.emit()

    def _on_radius_changed(self, r: int):
        for f in self.get_selected():
            if hasattr(f, 'radius'):
                try:
                    f.radius = r
                except Exception:
                    pass
        self.canvas_updated.emit()

    # (7) НЕ пишем обратно в settings.* при хоткеях
    def adjust_size_selected(self, delta: int):
        changed = False
        for f in self.get_selected():
            if hasattr(f, 'ess') and isinstance(f.ess, DrawEssentials):
                f.ess.pen_width = max(1, f.ess.pen_width + delta)
                changed = True
            if hasattr(f, 'radius'):
                try:
                    f.radius = max(1, f.radius + delta)
                    changed = True
                except Exception:
                    pass
        if changed:
            self.canvas_updated.emit()

    def add(self, figure):
        incomplete = self.get_incomplete()
        if incomplete and type(incomplete) == type(figure):
            incomplete.continue_drawing_point(figure.points[0][0], figure.points[0][1])
            self.canvas_updated.emit()
            return
        elif incomplete:
            # silently drop unfinished of another type (или можно подсказать пользователю)
            self.delete(incomplete)
        if isinstance(figure, Hand):
            return
        self.__figures.append(figure)
        self.canvas_updated.emit()

    def get_all(self): return self.__figures

    def select_figure(self, figure, state: bool = True):
        if figure in self.get_all():
            figure.selected = state
            self.canvas_updated.emit()

    def get_incomplete(self):
        for fig in self.__figures:
            if getattr(fig, "finished", True) is False:
                return fig
        return None

    def get_selected(self):
        return [f for f in self.__figures if getattr(f, "selected", False)]

    def deselect_all(self):
        changed = False
        for f in self.__figures:
            if getattr(f, "selected", False):
                f.selected = False
                changed = True
        if changed:
            self.canvas_updated.emit()

    def delete(self, figure):
        if figure in self.__figures:
            self.__figures.remove(figure)
            self.canvas_updated.emit()

    def delete_selected(self):
        before = len(self.__figures)
        self.__figures = [f for f in self.__figures if not getattr(f, "selected", False)]
        if len(self.__figures) != before:
            self.canvas_updated.emit()

    def clear_all(self):
        self.__figures.clear()
        self.canvas_updated.emit()

    def create_group(self, settings: DrawEssentials):
        selected = self.get_selected()
        if len(selected) < 2:
            print("Need at least two figures to create a group.")
            return

        group_figure = FigureGroup(figures=selected, ess=settings)
        for f in selected:
            self.delete(f)
        self.add(group_figure)

    def destroy_group(self):
        selected = self.get_selected()
        if len(selected) != 1:
            print("Must be exactly one selected figure to ungroup.")
            return

        if isinstance(selected[0], FigureGroup):
            for child in selected[0].figures:
                self.add(child)
            self.delete(selected[0])

    def _on_frame_arrows(self, arrow_tool: ArrowTools):
        """Обработать действие arrow-tool над выделенными фигурами."""
        print("Frame arrows action:", arrow_tool)

        selected = self.get_selected()

        if len(selected) != 2:
            print("Need exactly two selected figures to apply frame arrows.")
            return
        
        fig1, fig2 = selected

        # Снимаем/ставим связи в зависимости от режима
        if arrow_tool == ArrowTools.SINGLE:
            # односторонняя связь: при движении fig1 — будет обновляться fig2
            fig1.add_observer(fig2)
            # удаляем обратную связь
            try:
                fig2.remove_observer(fig1)
            except Exception:
                pass
        elif arrow_tool == ArrowTools.DOUBLE:
            # двусторонняя — обе фигуры наблюдают друг за другом
            fig1.add_observer(fig2)
            fig2.add_observer(fig1)
        elif arrow_tool == ArrowTools.NONE:
            # снимаем любые связи между двумя фигурами
            try:
                fig1.remove_observer(fig2)
            except Exception:
                pass
            try:
                fig2.remove_observer(fig1)
            except Exception:
                pass
        self.canvas_updated.emit()

    def paint_arrows(self, painter: QPainter):
        for fig in self.get_all():
            if fig.have_arrows():
                fig.draw_arrows(painter)

    def copy_selected_to_clipboard(self):
        # копируем элементы в буфер
        selected = self.get_selected()
        if not selected:
            return

        # сериализуем выбранные фигуры в JSON через фабрику
        try:
            if len(selected) > 1:
                # объединяем в группу и передаём в to_json как список
                figure = FigureGroup(figures=selected)
            else:
                # to_json ожидает итерируемый объект (список)
                figure = selected[0]

            data = factory.to_json([figure])
        except Exception as e:
            print("Copy error:", e)
            return

        # кладём в системный буфер обмена
        try:
            QApplication.clipboard().setText(data)
            print("Copied to clipboard:", data)
        except Exception as e:
            print("Clipboard error:", e)
            return

    def cut_selected_to_clipboard(self):
        self.copy_selected_to_clipboard()
        self.delete_selected()


    def move(self, figures: list[Figure], dx, dy, bounds=None):
        for fig in figures:
            fig.change_position(dx, dy, bounds)
        self.canvas_updated.emit()