"""Balance estimated test time across work-stealing workers without selecting tests.

Durations from the previous run live in pytest's cache. Unknown tests have zero estimated
cost; `-p no:cacheprovider` leaves the order unchanged. The order only affects scheduling.
xdist's `--dist worksteal` gives each worker one contiguous block of the collected items.
Fill those exact block sizes, assigning each next test to the least-loaded available block.
"""

from collections import defaultdict

import pytest

CACHE_KEY = "logo_maker/test_durations"
_measured: dict[str, float] = defaultdict(float)


def balanced_order(items, known, workers):
    """Match worksteal's floor division, including uneven and undersized collections."""
    blocks = [[] for _ in range(workers)]
    sizes = []
    remaining = len(items)
    for nodes in range(workers, 0, -1):
        size = remaining // nodes
        sizes.append(size)
        remaining -= size
    loads = [0.0] * workers
    for item in items:
        target = min(
            (i for i in range(workers) if len(blocks[i]) < sizes[i]),
            key=lambda i: (loads[i], len(blocks[i]), i),
        )
        blocks[target].append(item)
        loads[target] += known.get(item.nodeid, 0.0)
    return [item for block in blocks for item in block]


@pytest.hookimpl(optionalhook=True)
def pytest_configure_node(node):
    node.workerinput["logo_maker_worksteal"] = node.config.getoption("dist") == "worksteal"


@pytest.hookimpl(wrapper=True)
def pytest_collection_modifyitems(config, items):
    cache = getattr(config, "cache", None)
    known = cache.get(CACHE_KEY, {}) if cache is not None else None
    workers = getattr(config, "workerinput", {}).get("workercount", 1)
    parallel = workers > 1 and config.workerinput.get("logo_maker_worksteal", False)
    if parallel and known == {}:
        # Keep the original cold-cache deal before deselection. With no timings,
        # changing its order only moved the deadline tests later in measurements.
        items[:] = [item for start in range(workers) for item in items[start::workers]]
    result = yield
    if known:
        # Other hooks have now removed unselected items; sizes must reflect the
        # collection xdist will actually distribute, not render/live exclusions.
        items.sort(key=lambda item: -known.get(item.nodeid, 0.0))
        if parallel:
            items[:] = balanced_order(items, known, workers)
    return result


def pytest_runtest_logreport(report):
    _measured[report.nodeid] += report.duration


def pytest_sessionfinish(session):
    config = session.config
    cache = getattr(config, "cache", None)
    if cache is None or hasattr(config, "workerinput") or not _measured:
        return
    cache.set(CACHE_KEY, {**cache.get(CACHE_KEY, {}), **_measured})
