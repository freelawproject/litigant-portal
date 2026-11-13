import os
from pathlib import Path

import pytest

TRACE_PROPERTY = "playwright_trace"
TRACE_VIEWER_URL = "https://trace.playwright.dev"


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter, config: pytest.Config
) -> None:
    traces = find_traces(terminalreporter.stats)
    if not traces:
        return
    failed_nodeids = find_failed_nodeids(terminalreporter.stats)
    failed_paths = [
        path for nodeid, path in traces if nodeid in failed_nodeids
    ]
    example_path = (failed_paths or [path for _, path in traces])[0]
    write = terminalreporter.write_line
    terminalreporter.write_sep("-", "Playwright traces")
    if failed_paths:
        write("Traces of failed tests:")
        for path in failed_paths:
            write(f"  {path}")
    output_dir = config.getoption("--output")
    write(f"{len(traces)} traces saved in {output_dir}/. Open one with:")
    write(f"  {format_show_trace_command(config)} {example_path}")
    write(f"or drop it onto {TRACE_VIEWER_URL}")


def find_traces(stats: dict[str, list]) -> list[tuple[str, str]]:
    # pytest-playwright attaches each attempt's traces to its teardown report.
    return [
        (report.nodeid, path)
        for reports in stats.values()
        for report in reports
        if isinstance(report, pytest.TestReport)
        for name, path in report.user_properties
        if name == TRACE_PROPERTY
    ]


def find_failed_nodeids(stats: dict[str, list]) -> set[str]:
    return {
        report.nodeid
        for report in [*stats.get("failed", []), *stats.get("error", [])]
    }


def format_show_trace_command(config: pytest.Config) -> str:
    project = os.path.relpath(
        Path(__file__).parent, config.invocation_params.dir
    )
    return f"env -u VIRTUAL_ENV uv run --project {project} --locked playwright show-trace"
