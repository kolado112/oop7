from typing import List, Tuple, Any
from PyQt6.QtCore import QObject, pyqtSignal

class Command:
    """Базовый интерфейс команды."""
    def execute(self) -> None:
        raise NotImplementedError

    def undo(self) -> None:
        raise NotImplementedError

class CommandManager(QObject):
    def __init__(self, limit: int = 100):
        self._undo: List[Command] = []
        self._redo: List[Command] = []
        self._limit = limit
        super().__init__()
    
    undo_count_changed = pyqtSignal(int)
    redo_count_changed = pyqtSignal(int)

    def do(self, cmd: Command, execute: bool = True):
        if execute:
            cmd.execute()

        # если новая команда — MoveCommand и предыдущая тоже MoveCommand -> сливаем
        # if self._undo and isinstance(cmd, MoveCommand) and isinstance(self._undo[-1], MoveCommand):
        #     self._undo[-1].merge(cmd)
        #     return

        # обычный путь
        self._undo.append(cmd)
        self._redo.clear()
        if len(self._undo) > self._limit:
            self._undo.pop(0)

        self.undo_count_changed.emit(self.undo_count())
        self.redo_count_changed.emit(self.redo_count())

    def undo(self):
        if not self._undo:
            return
        cmd = self._undo.pop()
        cmd.undo()
        self._redo.append(cmd)

        self.undo_count_changed.emit(self.undo_count())
        self.redo_count_changed.emit(self.redo_count())

    def redo(self):
        if not self._redo:
            return
        cmd = self._redo.pop()
        cmd.execute()
        self._undo.append(cmd)

        self.undo_count_changed.emit(self.undo_count())
        self.redo_count_changed.emit(self.redo_count())

    # read-only accessors — возвращают кортеж, чтобы предотвратить внешнюю мутацию
    def get_undo(self) -> Tuple[Command, ...]:
        return tuple(self._undo)
    def get_redo(self) -> Tuple[Command, ...]:
        return tuple(self._redo)

    def undo_count(self) -> int:
        return len(self._undo)
    def redo_count(self) -> int:
        return len(self._redo)
    
    def broadcast(self):
        self.undo_count_changed.emit(self.undo_count())
        self.redo_count_changed.emit(self.redo_count())

# --- Concrete commands ---
class AddCommand(Command):
    def __init__(self, storage, figure):
        self.storage = storage
        self.figure = figure

    def execute(self):
        print(f'выполняется команда {self.__class__.__name__}')
        self.storage.add(self.figure)

    def undo(self):
        print(f'отменяется команда {self.__class__.__name__}')
        self.storage.delete(self.figure)

class DeleteCommand(Command):
    def __init__(self, storage, figure):
        self.storage = storage
        # normalize to list
        if isinstance(figure, (list, tuple)):
            self.figures = list(figure)
        else:
            self.figures = [figure]
        # save original indices for undo
        self.indices = []
        for f in self.figures:
            try:
                self.indices.append(self.storage.get_all().index(f))
            except ValueError:
                self.indices.append(None)

    def execute(self):
        print(f'выполняется команда {self.__class__.__name__}')
        for f in list(self.figures):
            try:
                self.storage.delete(f)
            except Exception:
                pass

    def undo(self):
        print(f'отменяется команда {self.__class__.__name__}')
        # вставляем обратно в сохранённые позиции (если возможно), иначе в конец
        figs = self.storage.get_all()
        for idx, f in sorted(zip(self.indices, self.figures), key=lambda x: (x[0] is None, x[0] if x[0] is not None else 0)):
            if f is None:
                continue
            if idx is None or idx > len(figs):
                figs.append(f)
            else:
                figs.insert(idx, f)
        try:
            self.storage.canvas_updated.emit()
        except Exception:
            pass

class MoveCommand(Command):
    def __init__(self, storage, moves: List[Tuple[Any, int, int]], bounds=None):
        self.storage = storage
        self.moves = moves
        self.bounds = bounds

    def execute(self):
        print(f'выполняется команда {self.__class__.__name__}')
        for fig, dx, dy in self.moves:
            self.storage.move([fig], dx, dy, self.bounds)
        
    def undo(self):
        print(f'отменяется команда {self.__class__.__name__}')
        for fig, dx, dy in self.moves:
            self.storage.move([fig], -dx, -dy, self.bounds)

    # def merge(self, other: "MoveCommand"):
    #     # суммируем dx/dy по тем же фигурам
    #     new_moves = []
    #     for (fig, dx1, dy1), (_, dx2, dy2) in zip(self.moves, other.moves):
    #         new_moves.append((fig, dx1 + dx2, dy1 + dy2))
    #     self.moves = new_moves



class GroupCommand(Command):
    def __init__(self, storage, figures: list, ess):
        if len(figures) < 2:
            raise ValueError("Нельзя группировать менее двух фигур")
        self.storage = storage
        self.figures = list(figures)
        self.ess = ess
        self.group = None
        # сохранить индексы порядка
        self.indices = [self.storage.get_all().index(f) for f in self.figures]

    def execute(self):
        print(f'выполняется команда {self.__class__.__name__}')
        from figures import FigureGroup
        # удаляем фигуры и добавляем группу
        for f in self.figures:
            try:
                # удаляем наблюдателей, чтобы не было утечек
                observers = f.get_observers()
                for obs in observers:
                    f.remove_observer(obs)
                self.storage.get_all().remove(f)
            except ValueError:
                pass
        self.group = FigureGroup(figures=self.figures, ess=self.ess)
        self.storage.get_all().append(self.group)
        try:
            self.storage.canvas_updated.emit()
        except Exception:
            pass

    def undo(self):
        print(f'отменяется команда {self.__class__.__name__}')
        if self.group and self.group in self.storage.get_all():
            self.storage.get_all().remove(self.group)
        # вставляем детей обратно в прежние позиции (ориентируемся на saved indices)
        figs = self.storage.get_all()
        for idx, f in sorted(zip(self.indices, self.figures), key=lambda x: x[0]):
            if idx is None or idx > len(figs):
                figs.append(f)
            else:
                figs.insert(idx, f)
        try:
            self.storage.canvas_updated.emit()
        except Exception:
            pass

class UngroupCommand(Command):
    def __init__(self, storage, group):
        self.storage = storage
        self.group = group
        self.children = list(group.figures) if hasattr(group, "figures") else []
        try:
            self.index = self.storage.get_all().index(group)
        except ValueError:
            self.index = None

    def execute(self):
        print(f'выполняется команда {self.__class__.__name__}')
        if self.group in self.storage.get_all():
            self.storage.get_all().remove(self.group)
            # вставляем детей на место группы
            base_idx = self.index if self.index is not None else len(self.storage.get_all())
            for i, c in enumerate(self.children):
                self.storage.get_all().insert(base_idx + i, c)
        try:
            self.storage.canvas_updated.emit()
        except Exception:
            pass

    def undo(self):
        print(f'отменяется команда {self.__class__.__name__}')
        # убрать детей и вернуть группу
        for c in self.children:
            try:
                self.storage.get_all().remove(c)
            except ValueError:
                pass
        if self.index is None:
            self.storage.get_all().append(self.group)
        else:
            self.storage.get_all().insert(self.index, self.group)
        try:
            self.storage.canvas_updated.emit()
        except Exception:
            pass

