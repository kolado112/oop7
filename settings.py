from dataclasses import dataclass, field
from PyQt6.QtCore import QObject, pyqtSignal, QSize
from PyQt6.QtGui import QColor
from enum import Enum

@dataclass
class DrawEssentials:
    pen_color: QColor = field(default_factory=lambda: QColor(1, 1, 1))
    brush_color: QColor = field(default_factory=lambda: QColor(255, 255, 255, 100))
    pen_width: int = 2
    radius: int = 5

class ArrowTools(Enum):
    NONE = 'none_arrow'
    SINGLE = 'single_arrow'
    DOUBLE = 'double_arrow'

class DrawSettings(QObject):
    penColorChanged   = pyqtSignal(QColor)
    brushColorChanged = pyqtSignal(QColor)
    penWidthChanged   = pyqtSignal(int)
    toolChanged       = pyqtSignal(str)
    radiusChanged     = pyqtSignal(int)
    frameArrowsTriggered = pyqtSignal(object)


    def __init__(self, ess: DrawEssentials | None = None):
        super().__init__()
        self._ess = ess if ess else DrawEssentials()
        self.__tool: str | None = None
        self.__csize = QSize(0, 0)

    @property
    def ess(self): return self._ess

    @property
    def pen_color(self): return self._ess.pen_color
    @pen_color.setter
    def pen_color(self, color: QColor):
        if isinstance(color, QColor) and color.isValid() and color != self._ess.pen_color:
            self._ess.pen_color = color
            self.penColorChanged.emit(color)

    @property
    def brush_color(self): return self._ess.brush_color
    @brush_color.setter
    def brush_color(self, color: QColor):
        if isinstance(color, QColor) and color.isValid() and color != self._ess.brush_color:
            self._ess.brush_color = color
            self.brushColorChanged.emit(color)

    @property
    def pen_width(self): return self._ess.pen_width
    @pen_width.setter
    def pen_width(self, width: int):
        if width != self._ess.pen_width:
            self._ess.pen_width = width
            self.penWidthChanged.emit(width)

    @property
    def radius(self): return self._ess.radius
    @radius.setter
    def radius(self, r: int):
        if r != self._ess.radius:
            self._ess.radius = r
            self.radiusChanged.emit(r)

    @property
    def tool(self): return self.__tool
    @tool.setter
    def tool(self, t: str):
        if t != self.__tool:
            self.__tool = t
            self.toolChanged.emit(t)

    @property
    def csize(self): return self.__csize
    @csize.setter
    def csize(self, csize):
        if isinstance(csize, QSize):
            new_size = csize
        elif isinstance(csize, (tuple, list)) and len(csize) == 2:
            new_size = QSize(int(csize[0]), int(csize[1]))
        else:
            return
        if new_size != self.__csize:
            self.__csize = new_size

    def arrow_tool(self, tool_name: str):
        try:
            arrow_type = ArrowTools(tool_name)
        except ValueError:
            # игнорировать неизвестные значения
            return
        self.frameArrowsTriggered.emit(arrow_type)

    def broadcast(self):
        self.penColorChanged.emit(self._ess.pen_color)
        self.brushColorChanged.emit(self._ess.brush_color)
        self.penWidthChanged.emit(self._ess.pen_width)
        self.toolChanged.emit(self.__tool or "")
        self.radiusChanged.emit(self._ess.radius)
