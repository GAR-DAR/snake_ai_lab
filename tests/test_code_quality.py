"""Guards for the type-hint and docstring cleanup, so it doesn't quietly regress."""

import inspect

import pytest

import snake as game_module


def own_callables():
    """Yield (name, function) for every function and method defined in snake.py."""
    for name, obj in vars(game_module).items():
        if getattr(obj, "__module__", None) != game_module.__name__:
            continue
        if inspect.isfunction(obj):
            yield name, obj
        elif inspect.isclass(obj):
            for member_name, raw_member in vars(obj).items():
                member = (
                    raw_member.fget if isinstance(raw_member, property) else raw_member
                )
                if isinstance(member, (staticmethod, classmethod)):
                    member = member.__func__
                # skip what Enum/Protocol inject (__new__, ...): not our source
                if (
                    inspect.isfunction(member)
                    and member.__code__.co_filename == game_module.__file__
                ):
                    yield f"{name}.{member_name}", member


CALLABLES = list(own_callables())


def test_the_helper_finds_the_code():
    assert len(CALLABLES) >= 55  # everything defined in snake.py (currently 60)


@pytest.mark.parametrize(
    "name,function", CALLABLES, ids=[name for name, _ in CALLABLES]
)
def test_every_parameter_and_return_value_is_annotated(name, function):
    signature = inspect.signature(function)
    for parameter in signature.parameters.values():
        if parameter.name in ("self", "cls"):
            continue
        assert (
            parameter.annotation is not inspect.Parameter.empty
        ), f"{name}({parameter.name})"
    assert signature.return_annotation is not inspect.Signature.empty, f"{name} return"


@pytest.mark.parametrize(
    "name,function", CALLABLES, ids=[name for name, _ in CALLABLES]
)
def test_every_function_has_a_docstring(name, function):
    if name.endswith(".__init__"):
        pytest.skip("constructors are described by the class docstring")
    # __doc__, not inspect.getdoc(): getdoc would inherit one from a base class
    assert function.__doc__, name


@pytest.mark.parametrize(
    "cls",
    [
        obj
        for obj in vars(game_module).values()
        if inspect.isclass(obj) and obj.__module__ == game_module.__name__
    ],
    ids=lambda cls: cls.__name__,
)
def test_every_class_has_a_docstring(cls):
    assert inspect.getdoc(cls)


def test_module_has_a_docstring():
    assert game_module.__doc__
