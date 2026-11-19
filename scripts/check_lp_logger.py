"""
Require literal messages at lp_logger call sites, including imported aliases.
"""

import ast
import sys
from pathlib import Path

LOGGER = "litigant_portal.lp_logger.lp_logger"


def _name(node: ast.expr, imports: dict[str, str]) -> str:
    if isinstance(node, ast.Name):
        return imports.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        return f"{_name(node.value, imports)}.{node.attr}"
    return ""


def violations(source: str) -> list[tuple[int, str]]:
    tree = ast.parse(source)
    imports = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name.split(".")[0]
                imports[name] = alias.name if alias.asname else name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                imports[alias.asname or alias.name] = (
                    f"{node.module}.{alias.name}"
                )

    errors = []
    for node in ast.walk(tree):
        if (
            not isinstance(node, ast.Call)
            or _name(node.func, imports) != LOGGER
        ):
            continue
        if node.args or any(keyword.arg is None for keyword in node.keywords):
            errors.append(
                (node.lineno, "lp_logger requires explicit keyword arguments")
            )
        for keyword in node.keywords:
            if keyword.arg != "msg":
                continue
            value = keyword.value
            if not (
                isinstance(value, ast.Constant)
                and (isinstance(value.value, str) or value.value is None)
            ):
                errors.append(
                    (
                        node.lineno,
                        "lp_logger msg must be a literal string or None",
                    )
                )
    return errors


def main() -> int:
    failed = False
    for filename in sys.argv[1:]:
        try:
            errors = violations(Path(filename).read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeError, OSError) as error:
            print(
                f"{filename}: unable to check Python source ({error.__class__.__name__})"
            )
            failed = True
            continue
        for line, message in errors:
            print(f"{filename}:{line}: {message}")
            failed = True
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
