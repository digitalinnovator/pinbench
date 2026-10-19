import pytest

from deps import CycleError, install_order, remove_order


def test_dependency_is_installed_first():
    assert install_order({"app": ["lib"], "lib": []}) == ["lib", "app"]


def test_dependency_is_removed_last():
    assert remove_order({"app": ["lib"], "lib": []}) == ["app", "lib"]


def test_cycle_is_reported():
    with pytest.raises(CycleError) as excinfo:
        install_order({"a": ["b"], "b": ["a"]})
    assert excinfo.value.cycle == ["a", "b"]
