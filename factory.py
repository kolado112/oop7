import json
import importlib
from importlib import util, machinery
from pathlib import Path
from typing import Any
import enum

# Не импортируем figures на уровне модуля — чтобы избежать цикличного импорта.
_registry: dict[str, type] | None = None

def _ensure_registry():
    """Инициализация реестра при первом обращении (ленивая загрузка figures)."""
    global _registry
    if _registry is None:
        import figures  # локальный импорт — избегаем циклической зависимости
        TOOLS = {
            "point": figures.Point,
            "line": figures.Line,
            "rectangle": figures.Rectangle,
            "square": figures.Square,
            "circle": figures.Circle,
            "ellipse": figures.Ellipse,
            "triangle": figures.Triangle,
            "hand": figures.Hand,  # заглушка для инструмента "рука" (перемещение)
            'FigureGroup': figures.FigureGroup,
        }
        _registry = dict(TOOLS)

def create(tool_name: str, x: int = None, y: int = None, *args: Any, ess=None, **kwargs: Any):
    _ensure_registry()
    cls = _registry.get(tool_name)
    if cls is None:
        raise ValueError(f"Unknown tool: {tool_name}")
    return cls(x, y, *args, ess=ess, **kwargs)

def register(name: str, cls: type):
    _ensure_registry()
    _registry[name] = cls

def unregister(name: str):
    _ensure_registry()
    _registry.pop(name, None)

def list_tools():
    _ensure_registry()
    return list(_registry.keys())

def to_json(figures_list: list) -> json:
    _ensure_registry()
    data = []
    for f in figures_list:
        # пропускаем незаконченные фигуры
        if getattr(f, "finished", True) is False:
            continue

        ser = getattr(f, "to_dict", None)
        if not callable(ser):
            raise RuntimeError(f"Figure {f!r} must implement to_dict()")

        item = {**ser(), "_type": f.__class__.__name__}
        data.append(item)

    return json.dumps(data, indent=4, ensure_ascii=False)

def from_json(json_string: str) -> list:
    _ensure_registry()
    data = json.loads(json_string)
    result = []
    for item in data:
        t = item.pop("_type", None)
        if t is None:
            raise RuntimeError("Missing _type in serialized item")

        cls = _find_class_by_name(t)
        if cls is None:
            raise RuntimeError(f"No registered class for type {t}")

        cls_func = getattr(cls, "from_dict", None)
        if not callable(cls_func):
            raise RuntimeError(f"{cls} must implement from_dict(dict) -> instance")
        inst = cls.from_dict(item)
        result.append(inst)
    return result

def save(figures_list: list, path: str) -> None:
    _ensure_registry()
    data = to_json(figures_list)

    tmp = Path(path + ".tmp")
    if tmp.parent and not tmp.parent.exists():
        tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(data, encoding="utf-8")
    tmp.replace(Path(path))

def load(path: str) -> list:
    _ensure_registry()
    text = Path(path).read_text(encoding="utf-8")
    figures = from_json(text)
    
    return figures

def _find_class_by_name(name: str):
    _ensure_registry()
    # ищем по имени класса в реестре
    for cls in _registry.values():
        if cls.__name__ == name:
            return cls
    return None


# def load_plugins(folder: str):
#     p = Path(folder)
#     if not p.exists():
#         return
#     for file in p.iterdir():
#         if file.suffix == ".py":
#             name = f"plugins.{file.stem}"
#             try:
#                 importlib.import_module(name)
#             except Exception:
#                 pass
#         elif file.suffix in (".pyd", ".dll"):
#             # попытка импортировать как python-extension module (.pyd/.dll)
#             try:
#                 spec = machinery.ExtensionFileLoader(file.stem, str(file))
#                 mod = types.ModuleType(file.stem)
#                 spec.exec_module(mod)
#             except Exception:
#                 # можно также использовать ctypes для загрузки нативных библиотек,
#                 # которые предоставляют функцию регистрации типов. Требует соглашения по API.
#                 pass

# Вызов (например) при инициализации реестра (опционально)
# добавить в _ensure_registry() после импорта figures:
# load_plugins(str(Path(__file__).parent / "plugins"))
# Плагины должны внутри себя вызывать factory.register("name", Class)