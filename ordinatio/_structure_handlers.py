from dataclasses import MISSING, fields, is_dataclass
from typing import Any, get_args, get_origin

from ._structure import HandlingError, Path, PredicateHandler, Structurer, StructuringError


def simple_structure(func):
    def _wrapped(structurer, structure_into, path, val):
        return func(val)

    return _wrapped


@simple_structure
def structure_none(val: Any) -> None:
    if val is not None:
        raise HandlingError("The value is not `None`")


@simple_structure
def structure_int(val: Any) -> int:
    # Handling a special case of `bool` here since in Python `bool` is an `int`,
    # and we don't want to mix them up.
    if not isinstance(val, int) or isinstance(val, bool):
        raise HandlingError("The value must be an integer")
    return val


@simple_structure
def structure_float(val: Any) -> float:
    # Allow integers as well, even though `int` is not a subclass of `float` in Python.
    if not isinstance(val, (int, float)):
        raise HandlingError("The value must be a floating-point number")
    return float(val)


@simple_structure
def structure_bool(val: Any) -> bool:
    if not isinstance(val, bool):
        raise HandlingError("The value must be a boolean")
    return val


@simple_structure
def structure_bytes(val: Any) -> bytes:
    if not isinstance(val, bytes):
        raise HandlingError("The value must be a bytestring")
    return val


@simple_structure
def structure_str(val: Any) -> str:
    if not isinstance(val, str):
        raise HandlingError("The value must be a string")
    return val


def structure_union(structurer: Structurer, structure_into: type, path: Path, val: Any) -> Any:
    exceptions = []
    args = get_args(structure_into)
    for arg in args:
        try:
            result = structurer.structure_at_path(arg, path, val)
            break
        except StructuringError as exc:
            exceptions.append(exc)
    else:
        raise StructuringError(path, f"Could not structure into any of {args}", exceptions)

    return result


def structure_tuple(structurer: Structurer, structure_into: type, path: Path, val: Any) -> Any:
    elem_types = get_args(structure_into)

    if not isinstance(val, (list, tuple)):
        raise HandlingError("Can only structure a tuple or a list into a tuple generic")

    # Tuple[()] is supposed to represent an empty tuple. Mypy knows this,
    # but in Python < 3.11 `get_args(Tuple[()])` returns `((),)` instead of `()` as it should.
    # Fixing it here.
    if elem_types == ((),):
        elem_types = ()

    # Homogeneous tuples (Tuple[some_type, ...])
    if len(elem_types) == 2 and elem_types[1] == ...:
        elem_types = [elem_types[0] for _ in range(len(val))]

    if len(val) < len(elem_types):
        raise HandlingError(
            f"Not enough elements to structure into a tuple: got {len(val)}, need {len(elem_types)}"
        )
    if len(val) > len(elem_types):
        raise HandlingError(
            f"Too many elements to structure into a tuple: got {len(val)}, need {len(elem_types)}"
        )

    result = []
    exceptions = []
    for index, (item, tp) in enumerate(zip(val, elem_types)):
        try:
            result.append(structurer.structure_at_path(tp, [*path, index], item))
        except StructuringError as exc:  # noqa: PERF203
            exceptions.append(exc)

    if exceptions:
        raise StructuringError(path, f"Could not structure into {structure_into}", exceptions)

    return tuple(result)


def structure_list(structurer: Structurer, structure_into: type, path: Path, val: Any) -> Any:
    (item_type,) = get_args(structure_into)
    if not isinstance(val, (list, tuple)):
        raise HandlingError("Can only structure a tuple or a list into a list generic")

    result = []
    exceptions = []
    for index, item in enumerate(val):
        try:
            result.append(structurer.structure_at_path(item_type, [*path, index], item))
        except StructuringError as exc:  # noqa: PERF203
            exceptions.append(exc)

    if exceptions:
        raise StructuringError(path, f"Could not structure into {structure_into}", exceptions)

    return result


def structure_dict(structurer: Structurer, structure_into: type, path: Path, val: Any) -> Any:
    key_type, value_type = get_args(structure_into)
    if not isinstance(val, dict):
        raise HandlingError("Can only structure a dict into a dict generic")

    result = {}
    exceptions = []
    for index, (key, value) in enumerate(val.items()):
        # Note that we're not using `key` for the path, since it can be anything.
        try:
            structured_key = structurer.structure_at_path(key_type, [*path, index, "<key>"], key)
        except StructuringError as exc:  # noqa: PERF203
            exceptions.append(exc)

        try:
            structured_value = structurer.structure_at_path(
                value_type, [*path, index, "<val>"], value
            )
        except StructuringError as exc:  # noqa: PERF203
            exceptions.append(exc)

        result[key] = value

    if exceptions:
        raise StructuringError(path, f"Could not structure into {structure_into}", exceptions)

    return result


class StructureDataclassFromList(PredicateHandler):
    def applies(self, structure_into, obj):
        return is_dataclass(structure_into) and isinstance(obj, list)

    def __call__(self, structurer, structure_into, path, obj):
        results = {}
        exceptions = []

        struct_fields = fields(structure_into)

        if len(obj) > len(struct_fields):
            raise StructuringError(path, f"Too many fields to serialize into {structure_into}")

        for i, field in enumerate(struct_fields):
            if i < len(obj):
                try:
                    results[field.name] = structurer.structure_at_path(
                        field.type, [*path, field.name], obj[i]
                    )
                except StructuringError as exc:
                    exceptions.append(exc)
            elif field.default is not MISSING:
                results[field.name] = field.default
            else:
                exceptions.append(StructuringError([*path, field.name], "Missing field"))

        if exceptions:
            raise StructuringError(
                path, f"Cannot structure a list into a dataclass {structure_into}", exceptions
            )

        return structure_into(**results)


class StructureDataclassFromDict(PredicateHandler):
    def __init__(self, name_converter=lambda name, metadata: name):
        self._name_converter = name_converter

    def applies(self, structure_into, obj):
        return is_dataclass(structure_into) and isinstance(obj, dict)

    def __call__(self, structurer, structure_into, path, obj):
        results = {}
        exceptions = []

        for field in fields(structure_into):
            obj_name = self._name_converter(field.name, field.metadata)
            if obj_name in obj:
                try:
                    results[field.name] = structurer.structure_at_path(
                        field.type, [*path, field.name], obj[obj_name]
                    )
                except StructuringError as exc:
                    exceptions.append(exc)
            elif field.default is not MISSING:
                results[field.name] = field.default
            else:
                if obj_name == field.name:
                    message = f"Missing field"
                else:
                    message = f"Missing field (`{obj_name}` in the input)"
                exceptions.append(StructuringError([*path, field.name], message))

        if exceptions:
            raise StructuringError(
                path, f"Cannot structure a dict into a dataclass {structure_into}", exceptions
            )

        return structure_into(**results)
