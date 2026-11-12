"""Run the slowest tests first so parallel workers do not end on one long test.

Durations from the previous run live in pytest's cache (absent on a cold checkout or with
`-p no:cacheprovider`, where the order is unchanged). The order only affects scheduling.
"""

from collections import defaultdict

CACHE_KEY = "logo_maker/test_durations"
_measured: dict[str, float] = defaultdict(float)


def pytest_collection_modifyitems(config, items):
    cache = getattr(config, "cache", None)
    if cache is None:
        return
    known = cache.get(CACHE_KEY, {})
    items.sort(key=lambda item: -known.get(item.nodeid, 0.0))


def pytest_runtest_logreport(report):
    _measured[report.nodeid] += report.duration


def pytest_sessionfinish(session):
    config = session.config
    cache = getattr(config, "cache", None)
    if cache is None or hasattr(config, "workerinput") or not _measured:
        return
    cache.set(CACHE_KEY, {**cache.get(CACHE_KEY, {}), **_measured})
