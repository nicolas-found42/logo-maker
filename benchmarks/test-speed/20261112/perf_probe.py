import json
import os
import time
from pathlib import Path

started = time.monotonic()
events = {}
reports = []
collections = {}


def pytest_configure(config):
    events["configured"] = time.monotonic() - started


def pytest_sessionstart(session):
    events["session_start"] = time.monotonic() - started


def pytest_xdist_node_collection_finished(node, ids):
    collections[node.gateway.id] = ids
    events.setdefault("first_collection", time.monotonic() - started)
    events["last_collection"] = time.monotonic() - started


def pytest_runtest_logstart(nodeid, location):
    events.setdefault("first_test", time.monotonic() - started)


def pytest_runtest_logreport(report):
    reports.append(
        {
            "nodeid": report.nodeid,
            "when": report.when,
            "outcome": report.outcome,
            "duration": report.duration,
        }
    )
    events["last_report"] = time.monotonic() - started


def pytest_sessionfinish(session, exitstatus):
    events["session_finish"] = time.monotonic() - started
    if not hasattr(session.config, "workerinput"):
        Path(os.environ["PERF_OUTPUT"]).write_text(
            json.dumps(
                {
                    "events": events,
                    "reports": reports,
                    "collections": collections,
                    "exitstatus": int(exitstatus),
                },
                indent=2,
            )
            + "\n"
        )
