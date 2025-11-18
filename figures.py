from __future__ import annotations
from math import hypot, atan2, sin, cos, pi
from typing import Any
from PyQt6.QtCore import QRect, QPoint
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QPolygon
from PyQt6.QtCore import QObject, Qt
from settings import DrawEssentials, ArrowTools
from factory import _find_class_by_name
from observer import Object, Observer, Event

class Defaults:
    ARROW_WIDTH = 2
    ARROW_COLOR = QColor(255, 151, 0)

def _ess_to_dict(ess: DrawEssentials | None) -> dict[str, any] | None:
    if not isinstance(ess, DrawEssentials):
        return None
    pc = ess.pen_color
    bc = ess.brush_color
    return {
        "pen_color": (pc.red(), pc.green(), pc.blue(), pc.alpha()),
        "brush_color": (bc.red(), bc.green(), bc.blue(), bc.alpha()),
        "pen_width": ess.pen_width,
        "radius": ess.radius
    }

def _ess_from_dict(d) -> DrawEssentials:
    if not d:
        return DrawEssentials()
    pc = d.get("pen_color", (0,0,0,255))
    bc = d.get("brush_color", (255,255,255,100))
    ess = DrawEssentials()
    ess.pen_color = QColor(pc[0], pc[1], pc[2], pc[3])
    ess.brush_color = QColor(bc[0], bc[1], bc[2], bc[3])
    ess.pen_width = int(d.get("pen_width", ess.pen_width))
    ess.radius = int(d.get("radius", ess.radius))
    return ess

class Figure(QObject, Object, Observer):
    tolerance = 5

    def __init__(self, ess: DrawEssentials | None = None):
        super().__init__()
        base = ess if isinstance(ess, DrawEssentials) else DrawEssentials()
        # (8) без deepcopy(QColor): создаём новые QColor
        self._ess = DrawEssentials(
            pen_color=QColor(base.pen_color),
            brush_color=QColor(base.brush_color),
            pen_width=base.pen_width,
            radius=base.radius
        )
        self._selected = False
        
        self._move_master = None   # type: Figure | None

    @property
    def ess(self) -> DrawEssentials:
        return self._ess
    @ess.setter
    def ess(self, value: DrawEssentials):
        if isinstance(value, DrawEssentials):
            self._ess = DrawEssentials(
                pen_color=QColor(value.pen_color),
                brush_color=QColor(value.brush_color),
                pen_width=value.pen_width,
                radius=value.radius
            )
    @property
    def pen_color(self) -> QColor:
        return self._ess.pen_color
    @pen_color.setter
    def pen_color(self, value: QColor):
        self._ess.pen_color = QColor(value)
    @property
    def brush_color(self) -> QColor:
        return self._ess.brush_color
    @brush_color.setter
    def brush_color(self, value: QColor):
        self._ess.brush_color = QColor(value)
    @property
    def pen_width(self) -> int:
        return self._ess.pen_width
    @pen_width.setter
    def pen_width(self, value: int):
        self._ess.pen_width = int(value)
    @property
    def radius(self) -> int:
        return self._ess.radius
    @radius.setter
    def radius(self, value: int):
        self._ess.radius = int(value)
    

    def draw(self, painter: QPainter): raise NotImplementedError
    def bounds(self) -> QRect: raise NotImplementedError

    def get_center(self) -> QPoint | None:
        b = self.bounds()
        if b.isNull():
            return None
        return b.center()

    def have_arrows(self) -> bool:
        if len(self.get_observers()) > 0:
            return True
        return False

    def draw_arrows(self, painter: QPainter):
        for obs in self.get_observers():
            if isinstance(obs, Figure):
                p1 = self.get_center()
                p2 = obs.get_center()
                if p1 is None or p2 is None:
                    continue
                x1, y1 = p1.x(), p1.y()
                x2, y2 = p2.x(), p2.y()
                if x1 == x2 and y1 == y1:
                    continue

                painter.save()
                pen = QPen(Defaults.ARROW_COLOR, Defaults.ARROW_WIDTH)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.setBrush(QBrush(Defaults.ARROW_COLOR))

                # основная линия между центрами
                painter.drawLine(QPoint(x1, y1), QPoint(x2, y2))

                # параметры пера для стрелок
                arrow_len = max(8, Defaults.ARROW_WIDTH * 4)
                arrow_ang = 0.5  # угол разворота кончика
                ang = atan2(y2 - y1, x2 - x1)

                def draw_head(tx: float, ty: float, angle: float):
                    p_tip = QPoint(int(tx), int(ty))
                    p_left = QPoint(int(tx - arrow_len * cos(angle - arrow_ang)),
                                    int(ty - arrow_len * sin(angle - arrow_ang)))
                    p_right = QPoint(int(tx - arrow_len * cos(angle + arrow_ang)),
                                     int(ty - arrow_len * sin(angle + arrow_ang)))
                    painter.drawPolygon(QPolygon([p_tip, p_left, p_right]))

                # стрелки на обоих концах
                draw_head(x2, y2, ang)
                # draw_head(x1, y1, ang + pi)

                painter.restore()

    # (4) Выделение не мутирует модель — только флаг
    @property
    def selected(self) -> bool: return self._selected
    @selected.setter
    def selected(self, v: bool): self._selected = bool(v)

    @staticmethod
    def is_fit_in_bounds(rect1: QRect, rect2: QRect) -> bool:
        """Проверяет, что rect1 целиком помещается внутри rect2."""
        b = rect1
        if b.isNull():
            return True
        return (b.left() >= rect2.left() and
                b.top() >= rect2.top() and
                b.right() <= rect2.right() and
                b.bottom() <= rect2.bottom())

    def hit_test(self, x: int, y: int) -> bool:
        # По умолчанию — точка в bbox (перекрываем в фигурах с геометрией)
        return QRect(self.bounds()).contains(x, y)

    # Визуализация выделения: штриховая рамка по bounds()
    def _draw_selection_overlay(self, painter: QPainter, color: QColor = QColor(Qt.GlobalColor.red)):
        if not self._selected:
            return
        pen = QPen(color, max(1, self._ess.pen_width // 2))
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.save()
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.bounds())
        painter.restore()

    def to_dict(self) -> dict:
        # Требуем явной реализации в подклассах — если вызвали базовый метод,
        # это означает, что подкласс не реализовал сериализацию.
        raise NotImplementedError(f"{self.__class__.__name__}.to_dict() must be implemented in subclass")
    
    @classmethod
    def from_dict(cls, data: dict) -> Figure:
        """Базовая сигнатура: подкласс должен вернуть новый экземпляр"""
        raise NotImplementedError(f"{cls.__name__}.from_dict(dict) must be implemented in subclass")

    def notify_move(self, dx: int, dy: int, event: Event | None = None, bounds: QRect | None = None) -> None:
        # сохраняем историю visited из входящего события, если оно есть,
        # чтобы notify мог корректно фильтровать циклические оповещения
        ev = Event(
            type="moved",
            payload={
                "dx": dx,
                "dy": dy,
                "bounds": bounds,
                "obj": self
            },
            visited=tuple(event.visited) if (event is not None and event.visited) else None
        )
        # print(f'payload packet with', ev.payload)
        self.notify(ev)

    def change_position(self, dx: int, dy: int, bounds: QRect = None, event: Event | None = None):
        """
        Базовая реализация: не меняет координаты сама.
        Подкласс должен:
          1) проверить bounds и изменить координаты,
          2) вызвать super().change_position(dx, dy, bounds, event) чтобы уведомить наблюдателей.
        """
        # уведомляем о перемещении (подкласс уже применил изменения)
        self.notify_move(dx, dy, event, bounds)

    def update(self, subject: Any, event: Event) -> None:
        # защита от циклов
        if event is not None and event.visited and id(self) in event.visited:
            return

        if event.type == "moved":
            payload = event.payload or {}
            subject_obj = payload.get("obj", None)
            if subject_obj is self or subject_obj is None:
                return

            # subject_obj – фигура, которая реально двигалась первой
            if isinstance(subject_obj, Figure):
                if self._move_master is None:
                    # Первый, кто дёрнул меня – становится хозяином
                    self._move_master = subject_obj
                elif self._move_master is not subject_obj:
                    # Это движение от другой стрелки – игнорируем
                    return
            # --------------------------------------

            print(f'Figure: {self} received move event:', payload)
            self.change_position(
                dx=payload.get("dx"),
                dy=payload.get("dy"),
                bounds=payload.get("bounds"),
                event=event
            )



class FigureGroup(Figure):
    def __init__(self, figures: list[Figure] | None = None, ess: DrawEssentials | None = None):
        super().__init__(ess)
        # Группа может содержать разные типы фигур — это и есть смысл list[Figure]
        if len(figures) < 2:
            raise ValueError("FigureGroup must contain at least two figures")
        self._figure_group: list[Figure] = list(figures) if figures else []
        # Не даём детям рисовать свои красные рамки — выделение будет на уровне группы
        for f in self._figure_group:
            f.selected = False

    @property
    def figures(self) -> list[Figure]:
        return self._figure_group

    def draw(self, painter: QPainter):
        # 1) Отрисовать всех детей как есть
        for fig in self._figure_group:
            fig.draw(painter)
        # 2) Если выделена группа — один общий оверлей по её bbox
        self._draw_selection_overlay(painter, color=QColor(Qt.GlobalColor.green))

    def bounds(self) -> QRect:
        # Корректная обработка пустой группы
        if not self._figure_group:
            return QRect()
        # Объединяем только осмысленные прямоугольники
        rect = QRect()
        has_any = False
        for fig in self._figure_group:
            b = fig.bounds()
            if not b.isNull() and b.isValid():
                rect = b if not has_any else rect.united(b)
                has_any = True
        return rect if has_any else QRect()

    def change_position(self, dx: int, dy: int, bounds: QRect = None, event: Event | None = None):
        # 1. Проверяем только bbox группы
        gb = self.bounds()
        if gb.isNull():
            return

        new_gb = QRect(gb.left() + dx, gb.top() + dy, gb.width(), gb.height())
        if not (bounds is None or self.is_fit_in_bounds(new_gb, bounds)):
            # если группа целиком не влазит — вообще никого не двигаем
            return

        # 2. Гарантированно влазит — двигаем детей БЕЗ проверки по внешним bounds
        for fig in self._figure_group:
            # будем трактовать bounds=None как "без проверки"
            try:
                fig.change_position(dx, dy, None)
            except TypeError:
                # на случай фигур с другой сигнатурой
                fig.change_position(dx, dy)

        super().change_position(dx, dy, bounds, event)

    def to_dict(self):
        ess = _ess_to_dict(self.ess)
        return {
            'ess': ess,
            'figures': [{**fig.to_dict(), "_type": fig.__class__.__name__} for fig in self._figure_group]
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> FigureGroup:
        ess_data = data.get("ess", None)
        ess = _ess_from_dict(ess_data)

        
        figs: list[Figure] = []

        figs_data = data.get("figures", [])
        for fdata in figs_data:
            t = fdata.pop("_type", None)
            if t is None:
                raise RuntimeError("Missing _type in serialized item of FigureGroup")
            
            fig_cls = _find_class_by_name(t)
            if fig_cls is None:
                raise RuntimeError(f"No registered class for type {t} in FigureGroup")
            
            cls_func = getattr(fig_cls, "from_dict", None)
            if not callable(cls_func):
                raise RuntimeError(f"{fig_cls} must implement from_dict(dict) -> instance")
            
            inst = fig_cls.from_dict(fdata)
            figs.append(inst)
        return cls(figs, ess=ess) 


class Point(Figure):
    def __init__(self, x: int, y: int, ess: DrawEssentials | None = None):
        super().__init__(ess)
        self.__x = x
        self.__y = y
    radius = 1
    pen_width = 2

    @property
    def x(self): return self.__x
    @property
    def y(self): return self.__y

    def draw(self, painter: QPainter):
        painter.save()
        pen = QPen(self._ess.pen_color, self.pen_width)
        painter.setPen(pen)
        painter.setBrush(QBrush())
        painter.drawEllipse(QPoint(self.__x, self.__y), self.radius, self.radius)
        painter.restore()
        self._draw_selection_overlay(painter)

    def bounds(self) -> QRect:
        r = max(1, self.pen_width, self.tolerance)
        return QRect(self.__x - r, self.__y - r, r * 2 + 1, r * 2 + 1)

    def change_position(self, dx: int, dy: int, bounds: QRect = None, event: Event | None = None):
        new_rect = QRect(self.__x + dx - self.tolerance,
                         self.__y + dy - self.tolerance,
                         self.tolerance * 2 + 1, self.tolerance * 2 + 1)
        if bounds is None or self.is_fit_in_bounds(new_rect, bounds):
            self.__x += dx
            self.__y += dy
        super().change_position(dx, dy, bounds, event)

    def to_dict(self):
        ess = _ess_to_dict(self.ess)
        return {
            'ess': ess,
            "x": self.__x,
            "y": self.__y
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> Point:
        ess_data = data.get("ess", None)

        ess = _ess_from_dict(ess_data)
        x = int(data.get("x", 0))
        y = int(data.get("y", 0))
        return cls(x, y, ess=ess)


class Line(Figure):
    def __init__(self, x1: int, y1: int, x2: int = None, y2: int = None, ess: DrawEssentials | None = None):
        super().__init__(ess)
        self.points = [[x1, y1], [x2, y2]]
        self.finished = not (x2 is None or y2 is None)

    def get_points(self) -> list[list[int]]:
        return self.points

    def draw(self, painter: QPainter):
        if not self.finished:
            return
        painter.save()
        painter.setPen(QPen(self._ess.pen_color, self._ess.pen_width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(QPoint(*self.points[0]), QPoint(*self.points[1]))
        painter.restore()
        self._draw_selection_overlay(painter)

    def continue_drawing_point(self, x: int, y: int):
        if self.points[1][0] is None or self.points[1][1] is None:
            self.points[1] = [x, y]
            self.finished = True

    def bounds(self) -> QRect:
        x1, y1 = self.points[0]
        x2, y2 = self.points[1]
        if x1 is None or y1 is None:
            return QRect()
        if x2 is None or y2 is None:
            r = max(self._ess.pen_width, self.tolerance)
            return QRect(x1 - r, y1 - r, r * 2 + 1, r * 2 + 1)
        left, top = min(x1, x2), min(y1, y2)
        right, bottom = max(x1, x2), max(y1, y2)
        r = max(self._ess.pen_width, self.tolerance)
        return QRect(left - r, top - r, (right - left) + 2 * r + 1, (bottom - top) + 2 * r + 1)

    # (5) Точный hit-test: расстояние до отрезка
    def hit_test(self, x: int, y: int) -> bool:
        if not self.finished:
            return False
        x1, y1 = self.points[0]
        x2, y2 = self.points[1]
        if x1 == x2 and y1 == y1:
            return hypot(x - x1, y - y1) <= (self._ess.pen_width / 2 + self.tolerance)
        # проекция
        vx, vy = x2 - x1, y2 - y1
        wx, wy = x - x1, y - y1
        seg_len2 = vx * vx + vy * vy
        t = 0 if seg_len2 == 0 else max(0.0, min(1.0, (wx * vx + wy * vy) / seg_len2))
        px, py = x1 + t * vx, y1 + t * vy
        dist = hypot(x - px, y - py)
        return dist <= (self._ess.pen_width / 2 + self.tolerance)

    def change_position(self, dx: int, dy: int, bounds: QRect = None, event: Event | None = None):
        x1, y1 = self.points[0]
        x2, y2 = self.points[1]
        nx1, ny1 = x1 + dx, y1 + dy
        nx2, ny2 = x2 + dx, y2 + dy
        new_rect = QRect(min(nx1, nx2) - self.tolerance,
                         min(ny1, ny2) - self.tolerance,
                         abs(nx2 - nx1) + 2 * self.tolerance + 1,
                         abs(ny2 - ny1) + 2 * self.tolerance + 1)
        if bounds is None or self.is_fit_in_bounds(new_rect, bounds):
            self.points[0] = [nx1, ny1]
            self.points[1] = [nx2, ny2]
        super().change_position(dx, dy, bounds, event)

    def to_dict(self):
        ess = _ess_to_dict(self.ess)
        pts = self.get_points()
        return {
            'ess': ess,
            'x1': pts[0][0],
            'y1': pts[0][1],
            'x2': pts[1][0],
            'y2': pts[1][1],
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> Line:
        ess_data = data.get("ess", None)

        ess = _ess_from_dict(ess_data)
        x1 = int(data.get("x1", 0))
        y1 = int(data.get("y1", 0))
        x2 = data.get("x2")
        y2 = data.get("y2")

        return cls(x1, y1, x2, y2, ess=ess)

class Rectangle(Figure):
    # (3) Две точки: p1 (anchor), p2 (opposite corner)
    def __init__(self, x1: int, y1: int, x2: int = None, y2: int = None, ess: DrawEssentials | None = None):
        super().__init__(ess)
        self.points = [[x1, y1], [x2, y2]]
        self.finished = not (x2 is None or y2 is None)

    def get_points(self) -> list[list[int]]:
        return self.points

    def draw(self, painter: QPainter):
        if not self.finished:
            return
        painter.save()
        pen = QPen(self._ess.pen_color, self._ess.pen_width)
        brush = QBrush(self._ess.brush_color)
        painter.setPen(pen)
        painter.setBrush(brush)
        x1, y1 = self.points[0]
        x2, y2 = self.points[1]
        left, top = min(x1, x2), min(y1, y2)
        width, height = abs(x2 - x1), abs(y2 - y1)
        painter.drawRect(left, top, width, height)
        painter.restore()
        self._draw_selection_overlay(painter)

    def continue_drawing_point(self, x: int, y: int):
        if self.points[1][0] is None or self.points[1][1] is None:
            self.points[1] = [x, y]
            self.finished = True

    def bounds(self) -> QRect:
        p = [pt for pt in self.points if pt[0] is not None and pt[1] is not None]
        if len(p) < 1:
            return QRect()
        if len(p) == 1:
            x1, y1 = p[0]
            t = max(self._ess.pen_width, self.tolerance)
            return QRect(x1 - t, y1 - t, 2 * t + 1, 2 * t + 1)
        x1, y1 = self.points[0]
        x2, y2 = self.points[1]
        left, top = min(x1, x2), min(y1, y2)
        right, bottom = max(x1, x2), max(y1, y2)
        t = max(self._ess.pen_width, self.tolerance)
        return QRect(left - t, top - t, (right - left) + 2 * t + 1, (bottom - top) + 2 * t + 1)

    # (5) hit-test: точка внутри прямоугольника с допуском t
    def hit_test(self, x: int, y: int) -> bool:
        if not self.finished:
            return False
        x1, y1 = self.points[0]
        x2, y2 = self.points[1]
        left, top = min(x1, x2), min(y1, y2)
        right, bottom = max(x1, x2), max(y1, y2)
        t = max(self._ess.pen_width / 2, self.tolerance)
        rect = QRect(int(left - t), int(top - t), int((right - left) + 2 * t), int((bottom - top) + 2 * t))
        return rect.contains(x, y)

    def change_position(self, dx: int, dy: int, bounds: QRect = None, event: Event | None = None):
        x1, y1 = self.points[0]
        x2, y2 = self.points[1] if self.points[1][0] is not None else (x1, y1)
        nx1, ny1, nx2, ny2 = x1 + dx, y1 + dy, x2 + dx, y2 + dy
        left, top = min(nx1, nx2), min(ny1, ny2)
        right, bottom = max(nx1, nx2), max(ny1, ny2)
        new_rect = QRect(left - self.tolerance, top - self.tolerance,
                         (right - left) + 2 * self.tolerance + 1,
                         (bottom - top) + 2 * self.tolerance + 1)
        if bounds is None or self.is_fit_in_bounds(new_rect, bounds):
            self.points[0] = [nx1, ny1]
            self.points[1] = [nx2, ny2]
        super().change_position(dx, dy, bounds, event)

    def to_dict(self):
        ess = _ess_to_dict(self.ess)
        pts = self.get_points()
        return {
            'ess': ess,
            'x1': pts[0][0],
            'y1': pts[0][1],
            'x2': pts[1][0],
            'y2': pts[1][1],
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> Rectangle:
        ess_data = data.get("ess", None)

        ess = _ess_from_dict(ess_data)
        x1 = int(data.get("x1", 0))
        y1 = int(data.get("y1", 0))
        x2 = data.get("x2")
        y2 = data.get("y2")

        return cls(x1, y1, x2, y2, ess=ess)

class Square(Rectangle):
    def __init__(self, x1: int, y1: int, x2: int = None, y2: int = None, ess: DrawEssentials | None = None):
        super().__init__(x1, y1, x2, y2, ess)


    # поведение построения такое же (2 точки), рисуем как квадрат по наибольшей стороне
    def draw(self, painter: QPainter):
        if not self.finished:
            return
        painter.save()
        pen = QPen(self._ess.pen_color, self._ess.pen_width)
        brush = QBrush(self._ess.brush_color)
        painter.setPen(pen)
        painter.setBrush(brush)
        x1, y1 = self.points[0]
        x2, y2 = self.points[1]
        size = max(abs(x2 - x1), abs(y2 - y1))
        left = x1 if x2 >= x1 else x1 - size
        top  = y1 if y2 >= y1 else y1 - size
        painter.drawRect(left, top, size, size)
        painter.restore()
        self._draw_selection_overlay(painter)

    def to_dict(self):
        ess = _ess_to_dict(self.ess)
        pts = self.get_points()
        return {
            'ess': ess,
            'x1': pts[0][0],
            'y1': pts[0][1],
            'x2': pts[1][0],
            'y2': pts[1][1],
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> Square:
        ess_data = data.get("ess", None)

        ess = _ess_from_dict(ess_data)
        x1 = int(data.get("x1", 0))
        y1 = int(data.get("y1", 0))
        x2 = data.get("x2")
        y2 = data.get("y2")

        return cls(x1, y1, x2, y2, ess=ess)

class Circle(Figure):
    def __init__(self, x: int, y: int, rx: int = None, ry: int = None, ess: DrawEssentials | None = None):
        super().__init__(ess)
        self.points = [[x, y], [rx, ry]]
        self.finished = not (rx is None or ry is None)

    def get_points(self) -> list[list[int]]:
        return self.points

    def draw(self, painter: QPainter):
        if not self.finished:
            return
        painter.save()
        pen = QPen(self._ess.pen_color, self._ess.pen_width)
        brush = QBrush(self._ess.brush_color)
        painter.setPen(pen)
        painter.setBrush(brush)
        cx, cy = self.points[0]
        px, py = self.points[1]
        r = max(abs(px - cx), abs(py - cy))
        painter.drawEllipse(QPoint(cx, cy), r, r)
        painter.restore()
        self._draw_selection_overlay(painter)

    def continue_drawing_point(self, x: int, y: int):
        if self.points[1][0] is None or self.points[1][1] is None:
            self.points[1] = [x, y]
            self.finished = True

    def bounds(self) -> QRect:
        cx, cy = self.points[0]
        px, py = self.points[1]
        if px is None or py is None:
            t = max(self._ess.pen_width, self.tolerance)
            return QRect(cx - t, cy - t, 2 * t + 1, 2 * t + 1)
        r0 = max(abs(px - cx), abs(py - cy))
        t = max(r0, self._ess.pen_width, self.tolerance)
        return QRect(cx - t, cy - t, 2 * t + 1, 2 * t + 1)

    # (5) hit-test круга по уравнению
    def hit_test(self, x: int, y: int) -> bool:
        if not self.finished:
            return False
        cx, cy = self.points[0]
        px, py = self.points[1]
        r = max(abs(px - cx), abs(py - cy))
        dist = hypot(x - cx, y - cy)
        return dist <= r + max(self._ess.pen_width / 2, self.tolerance)

    def change_position(self, dx: int, dy: int, bounds: QRect = None, event: Event | None = None):
        cx, cy = self.points[0]
        px, py = self.points[1]
        ncx, ncy = cx + dx, cy + dy
        npx = px + dx if px is not None else None
        npy = py + dy if py is not None else None
        r = 0 if npx is None or npy is None else max(abs(npx - ncx), abs(npy - ncy))
        new_rect = QRect(ncx - r - self.tolerance, ncy - r - self.tolerance,
                         2 * r + 2 * self.tolerance + 1, 2 * r + 2 * self.tolerance + 1)
        if bounds is None or self.is_fit_in_bounds(new_rect, bounds):
            self.points[0] = [ncx, ncy]
            if npx is not None and npy is not None:
                self.points[1] = [npx, npy]
        super().change_position(dx, dy, bounds, event)

    def to_dict(self):
        ess = _ess_to_dict(self.ess)
        pts = self.get_points()
        return {
            'ess': ess,
            'x': pts[0][0],
            'y': pts[0][1],
            'rx': pts[1][0],
            'ry': pts[1][1],
        }
    
    @property
    def radius(self) -> int:
        # читаем из базового Figure.radius (там self._ess.radius)
        return Figure.radius.fget(self)

    @radius.setter
    def radius(self, value: int):
        new_r = int(value)

        # 1) записываем в ess через базовый сеттер Figure
        Figure.radius.fset(self, new_r)

        # 2) если круг уже дорисован — двигаем вторую точку
        if self.finished:
            cx, cy = self.points[0]
            # делаем окружность с центром (cx, cy) и радиусом new_r
            self.points[1] = [cx + new_r, cy + new_r]
    
    @classmethod
    def from_dict(cls, data: dict) -> Circle:
        ess_data = data.get("ess", None)

        ess = _ess_from_dict(ess_data)
        x = int(data.get("x", 0))
        y = int(data.get("y", 0))
        rx = data.get("rx")
        ry = data.get("ry")

        return cls(x, y, rx, ry, ess=ess)

# (1) Ellipse — отдельный класс, не наследуется от Circle
class Ellipse(Figure):
    def __init__(self, x: int, y: int, rx: int = None, ry: int = None, ess: DrawEssentials | None = None):
        super().__init__(ess)
        self.points = [[x, y], [rx, ry]]
        self.finished = not (rx is None or ry is None)

    def get_points(self) -> list[list[int]]:
        return self.points

    def draw(self, painter: QPainter):
        if not self.finished:
            return
        painter.save()
        pen = QPen(self._ess.pen_color, self._ess.pen_width)
        brush = QBrush(self._ess.brush_color)
        painter.setPen(pen)
        painter.setBrush(brush)
        cx, cy = self.points[0]
        px, py = self.points[1]
        rx, ry = abs(px - cx), abs(py - cy)
        painter.drawEllipse(QRect(cx - rx, cy - ry, 2 * rx, 2 * ry))
        painter.restore()
        self._draw_selection_overlay(painter)

    def continue_drawing_point(self, x: int, y: int):
        if self.points[1][0] is None or self.points[1][1] is None:
            self.points[1] = [x, y]
            self.finished = True

    def bounds(self) -> QRect:
        cx, cy = self.points[0]
        px, py = self.points[1]
        if px is None or py is None:
            t = max(self._ess.pen_width, self.tolerance)
            return QRect(cx - t, cy - t, 2 * t + 1, 2 * t + 1)
        rx, ry = abs(px - cx), abs(py - cy)
        t = max(self._ess.pen_width, self.tolerance)
        return QRect(cx - rx - t, cy - ry - t, 2 * rx + 2 * t + 1, 2 * ry + 2 * t + 1)

    # (5) hit-test эллипса по уравнению
    def hit_test(self, x: int, y: int) -> bool:
        if not self.finished:
            return False
        cx, cy = self.points[0]
        px, py = self.points[1]
        rx, ry = abs(px - cx), abs(py - cy)
        if rx == 0 or ry == 0:
            return False
        nx = (x - cx) / rx
        ny = (y - cy) / ry
        val = nx * nx + ny * ny
        # допускаем попадание с запасом под толщину пера/толеранс
        return val <= 1.0 + (max(self._ess.pen_width / 2, self.tolerance) / max(rx, ry))

    def change_position(self, dx: int, dy: int, bounds: QRect = None, event: Event | None = None):
        cx, cy = self.points[0]
        px, py = self.points[1]
        ncx, ncy = cx + dx, cy + dy
        npx = px + dx if px is not None else None
        npy = py + dy if py is not None else None
        if npx is None or npy is None:
            t = self.tolerance
            new_rect = QRect(ncx - t, ncy - t, 2 * t + 1, 2 * t + 1)
        else:
            rx, ry = abs(npx - ncx), abs(npy - ncy)
            t = self.tolerance
            new_rect = QRect(ncx - rx - t, ncy - ry - t, 2 * rx + 2 * t + 1, 2 * ry + 2 * t + 1)
        if bounds is None or self.is_fit_in_bounds(new_rect, bounds):
            self.points[0] = [ncx, ncy]
            if npx is not None and npy is not None:
                self.points[1] = [npx, npy]
        super().change_position(dx, dy, bounds, event)

    def to_dict(self):
        ess = _ess_to_dict(self.ess)
        pts = self.get_points()
        return {
            'ess': ess,
            'x': pts[0][0],
            'y': pts[0][1],
            'rx': pts[1][0],
            'ry': pts[1][1],
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> Ellipse:
        ess_data = data.get("ess", None)

        ess = _ess_from_dict(ess_data)
        x = int(data.get("x", 0))
        y = int(data.get("y", 0))
        rx = data.get("rx")
        ry = data.get("ry")

        return cls(x, y, rx, ry, ess=ess)
    
    @property
    def radius(self) -> int:
        # читаем логическое "радиус-масштаб" из базового ess
        return Figure.radius.fget(self)

    @radius.setter
    def radius(self, value: int):
        new_r = int(value)
        # 1) сохранить в ess (для панели/сериализации)
        Figure.radius.fset(self, new_r)

        # 2) если эллипс дорисован — масштабируем вторую точку
        if not self.finished:
            return

        cx, cy = self.points[0]
        px, py = self.points[1]

        # текущие полуоси
        rx0 = abs(px - cx)
        ry0 = abs(py - cy)

        # если эллипс вырожден в точку — просто задаём круг
        if rx0 == 0 and ry0 == 0:
            self.points[1] = [cx + new_r, cy + new_r]
            return

        # берём текущий "радиус" как max полуосей и считаем коэффициент масштабирования
        r0 = max(rx0, ry0)
        k = new_r / r0 if r0 != 0 else 1.0

        rx = int(rx0 * k)
        ry = int(ry0 * k)

        # восстанавливаем точку по новым полуосям (в том же квадранте, что и была)
        sign_x = 1 if px >= cx else -1
        sign_y = 1 if py >= cy else -1
        self.points[1] = [cx + sign_x * rx, cy + sign_y * ry]

class Triangle(Figure):
    def __init__(self, x1: int, y1: int, x2: int = None, y2: int = None, x3: int = None, y3: int = None, ess: DrawEssentials | None = None):
        super().__init__(ess)
        self.points = [[x1, y1], [x2, y2], [x3, y3]]
        self.finished = False if any(p[0] is None or p[1] is None for p in self.points) else True

    def get_points(self) -> list[list[int]]:
        return self.points

    def draw(self, painter: QPainter):
        if not self.finished:
            return
        painter.save()
        pen = QPen(self._ess.pen_color, self._ess.pen_width)
        brush = QBrush(self._ess.brush_color)
        painter.setPen(pen)
        painter.setBrush(brush)
        p1 = QPoint(*self.points[0])
        p2 = QPoint(*self.points[1])
        p3 = QPoint(*self.points[2])
        # (2) корректная перегрузка: через QPolygon
        painter.drawPolygon(QPolygon([p1, p2, p3]))
        painter.restore()
        self._draw_selection_overlay(painter)

    def continue_drawing_point(self, x: int, y: int):
        for i in range(3):
            if self.points[i][0] is None or self.points[i][1] is None:
                self.points[i] = [x, y]
                if i == 2:
                    self.finished = True
                break

    def bounds(self) -> QRect:
        pts = [pt for pt in self.points if pt[0] is not None and pt[1] is not None]
        if not pts:
            return QRect()
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        left, top, right, bottom = min(xs), min(ys), max(xs), max(ys)
        t = max(self._ess.pen_width, self.tolerance)
        return QRect(left - t, top - t, (right - left) + 2 * t + 1, (bottom - top) + 2 * t + 1)

    # (5) hit-test: barycentric внутри треугольника (с лёгкой надувкой bbox)
    def hit_test(self, x: int, y: int) -> bool:
        if not self.finished:
            return False
        x1, y1 = self.points[0]
        x2, y2 = self.points[1]
        x3, y3 = self.points[2]
        denom = (y2 - y3)*(x1 - x3) + (x3 - x2)*(y1 - y3)
        if denom == 0:
            return False
        a = ((y2 - y3)*(x - x3) + (x3 - x2)*(y - y3)) / denom
        b = ((y3 - y1)*(x - x3) + (x1 - x3)*(y - y3)) / denom
        c = 1 - a - b
        if (a >= -0.02 and b >= -0.02 and c >= -0.02):
            return True
        return False

    def change_position(self, dx: int, dy: int, bounds: QRect = None, event=None):
        new_pts = []
        for x, y in self.points:
            if x is None or y is None:
                new_pts.append((x, y))
                continue
            new_pts.append((x + dx, y + dy))
        pts_to_check = [(x, y) for x, y in new_pts if x is not None and y is not None]
        if not pts_to_check:
            return
        xs = [p[0] for p in pts_to_check]
        ys = [p[1] for p in pts_to_check]
        new_rect = QRect(min(xs) - self.tolerance, min(ys) - self.tolerance,
                         max(xs) - min(xs) + self.tolerance * 2 + 1,
                         max(ys) - min(ys) + self.tolerance * 2 + 1)
        if bounds is None or self.is_fit_in_bounds(new_rect, bounds):
            for i, (x, y) in enumerate(new_pts):
                if x is not None and y is not None:
                    self.points[i][0] = x
                    self.points[i][1] = y
        super().change_position(dx, dy, bounds, event)
    
    def to_dict(self):
        ess = _ess_to_dict(self.ess)
        pts = self.get_points()
        return {
            'ess': ess,
            'x1': pts[0][0],
            'y1': pts[0][1],
            'x2': pts[1][0],
            'y2': pts[1][1],
            'x3': pts[2][0],
            'y3': pts[2][1],
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> Triangle:
        ess_data = data.get("ess", None)

        ess = _ess_from_dict(ess_data)
        x1 = int(data.get("x1", 0))
        y1 = int(data.get("y1", 0))
        x2 = data.get("x2")
        y2 = data.get("y2")
        x3 = data.get("x3")
        y3 = data.get("y3")

        return cls(x1, y1, x2, y2, x3, y3, ess=ess)
    
class Hand(Figure):
    # заглушка для инструмента "рука" (перемещение)
    def __init__(self):
        super().__init__()

    def draw(self, painter: QPainter):
        pass

    def bounds(self) -> QRect:
        return QRect()
