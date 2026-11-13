"""Scheduling changes order only, even when workers outnumber selected tests."""

from types import SimpleNamespace

import conftest as scheduling
import pytest


@pytest.mark.parametrize(("count", "workers"), [(0, 3), (1, 3), (7, 3), (11, 3), (524, 18)])
def test_balancing_preserves_every_item_once_and_is_deterministic(count, workers):
    items = [SimpleNamespace(nodeid=str(i)) for i in range(count)]
    known = {item.nodeid: float(count - i) for i, item in enumerate(items)}
    known["removed-test"] = 10000.0
    ordered = scheduling.balanced_order(items, known, workers)
    assert sorted(map(id, ordered)) == sorted(map(id, items))
    assert ordered == scheduling.balanced_order(items, known, workers)
    assert items == sorted(items, key=lambda item: int(item.nodeid))


def test_balancing_avoids_adding_medium_tests_to_the_longest_worker():
    durations = [18, 17, 9, 8, 7, 6] + [0.01] * 12
    items = [SimpleNamespace(nodeid=str(i)) for i in range(len(durations))]
    known = {item.nodeid: duration for item, duration in zip(items, durations, strict=True)}
    ordered = scheduling.balanced_order(items, known, 3)
    # xdist initially hands out six items per worker. Round-robin dealing puts
    # the 18 s and 8 s cases on one worker; there is room to keep it below 25 s.
    loads = [sum(known[item.nodeid] for item in ordered[i : i + 6]) for i in (0, 6, 12)]
    assert max(loads) < 25


def test_unknown_timings_still_preserve_all_items():
    items = [SimpleNamespace(nodeid=str(i)) for i in range(11)]
    assert sorted(map(id, scheduling.balanced_order(items, {}, 3))) == sorted(map(id, items))


def test_disabled_cache_preserves_collection_order():
    items = [SimpleNamespace(nodeid=str(i)) for i in range(11)]
    original = items.copy()
    manager = pytest.PytestPluginManager()
    manager.register(scheduling)
    manager.hook.pytest_collection_modifyitems(
        session=None, config=SimpleNamespace(cache=None), items=items
    )
    assert items == original


@pytest.mark.parametrize("dist", ["worksteal", "load"])
def test_controller_passes_scheduler_choice_to_workers(dist):
    node = SimpleNamespace(config=SimpleNamespace(getoption=lambda name: dist), workerinput={})
    scheduling.pytest_configure_node(node)
    assert node.workerinput["logo_maker_worksteal"] == (dist == "worksteal")
