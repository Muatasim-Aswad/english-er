#!/usr/bin/env python3
"""Check application layers, feature APIs, and cross-feature dependency cycles."""

import argparse
import ast
import re
from pathlib import Path

BACKEND_ALLOWED = {
    "entrypoints": {"entrypoints", "modules", "platform", "infra", "config", "shared"},
    "modules": {"modules", "platform", "infra", "config", "shared"},
    "platform": {"platform", "infra", "config", "shared"},
    "infra": {"infra", "config", "shared"},
    "config": {"shared"},
    "shared": {"shared"},
}
WEB_ALLOWED = {
    "app": {"app", "features", "infra", "shared", "config"},
    "features": {"features", "infra", "shared", "config"},
    "infra": {"infra", "shared", "config"},
    "config": {"shared"},
    "shared": {"shared"},
}


def area(parts: tuple[str, ...] | list[str]) -> str:
    return parts[0].split(".")[0]


def feature(parts: tuple[str, ...] | list[str], folder: str) -> str | None:
    return parts[1] if len(parts) > 1 and parts[0] == folder else None


def detect_cycles(graph: dict[str, set[str]], label: str) -> list[str]:
    errors: list[str] = []
    active: set[str] = set()
    done: set[str] = set()

    def visit(node: str, path: list[str]) -> None:
        if node in active:
            errors.append(f"{label}: dependency cycle: {' -> '.join([*path, node])}")
            return
        if node in done:
            return
        active.add(node)
        for target in sorted(graph.get(node, ())):
            visit(target, [*path, node])
        active.remove(node)
        done.add(node)

    for node in sorted(graph):
        visit(node, [])
    return errors


def check_backend(root: Path) -> list[str]:
    source = root / "apps/backend/src/english_er"
    errors: list[str] = []
    graph: dict[str, set[str]] = {}
    for path in sorted(source.rglob("*.py")):
        owner_parts = path.relative_to(source).parts
        owner = area(owner_parts)
        if owner not in BACKEND_ALLOWED:
            if path.name != "__init__.py":
                errors.append(f"{path.relative_to(root)}: unknown application area")
            continue
        owner_feature = feature(owner_parts, "modules")
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                imports = [node.module or ""]
                if node.module and node.module.startswith("english_er"):
                    base = source.joinpath(*node.module.split(".")[1:])
                    imports = [
                        f"{node.module}.{item.name}"
                        if (base / item.name).is_dir()
                        or (base / item.name).with_suffix(".py").is_file()
                        else node.module
                        for item in node.names
                    ]
                if node.level:
                    errors.append(
                        f"{path.relative_to(root)}:{node.lineno}: use absolute backend imports"
                    )
            elif isinstance(node, ast.Import):
                imports = [item.name for item in node.names]
            else:
                continue
            for name in imports:
                if not name.startswith("english_er."):
                    if (
                        owner == "modules"
                        and name.startswith(("fastapi", "starlette"))
                        and path.stem not in {"http", "dependencies"}
                    ):
                        errors.append(
                            f"{path.relative_to(root)}:{node.lineno}: transport import outside HTTP boundary"
                        )
                    continue
                target_parts = name.split(".")[1:]
                target = area(target_parts)
                if target not in BACKEND_ALLOWED[owner]:
                    errors.append(
                        f"{path.relative_to(root)}:{node.lineno}: {owner} cannot import {target}"
                    )
                if (
                    owner == "modules"
                    and target == "platform"
                    and path.stem not in {"http", "dependencies"}
                ):
                    errors.append(
                        f"{path.relative_to(root)}:{node.lineno}: only inbound adapters may import platform"
                    )
                if (
                    owner == "modules"
                    and target == "infra"
                    and path.stem
                    not in {
                        "models",
                        "repository",
                        "review_repository",
                        "processing_repository",
                        "provider",
                        "storage",
                        "transactions",
                    }
                ):
                    errors.append(
                        f"{path.relative_to(root)}:{node.lineno}: only outbound adapters may import infra"
                    )
                target_feature = feature(target_parts, "modules")
                if owner_feature and target_feature and owner_feature != target_feature:
                    graph.setdefault(owner_feature, set()).add(target_feature)
                    if len(target_parts) > 2:
                        errors.append(
                            f"{path.relative_to(root)}:{node.lineno}: use {target_feature}'s public API"
                        )
    return errors + detect_cycles(graph, "backend features")


def check_web(root: Path) -> list[str]:
    source = root / "apps/web/src"
    errors: list[str] = []
    graph: dict[str, set[str]] = {}
    for path in sorted(source.rglob("*")):
        if path.suffix not in {".ts", ".tsx"} or path.name.endswith(
            (".test.ts", ".test.tsx", ".d.ts")
        ):
            continue
        owner_parts = path.relative_to(source).parts
        owner = area(owner_parts)
        if path.name == "main.tsx":
            continue
        if owner not in WEB_ALLOWED:
            errors.append(f"{path.relative_to(root)}: unknown application area")
            continue
        owner_feature = feature(owner_parts, "features")
        for match in re.finditer(
            r'(?:from\s*|import\s*\(|import\s*)["\'](\.[^"\']+)["\']', path.read_text()
        ):
            target_path = (path.parent / match.group(1)).resolve()
            try:
                target_parts = target_path.relative_to(source.resolve()).parts
            except ValueError:
                errors.append(f"{path.relative_to(root)}: import leaves application source")
                continue
            target = area(target_parts)
            if target not in WEB_ALLOWED[owner]:
                errors.append(f"{path.relative_to(root)}: {owner} cannot import {target}")
            target_feature = feature(target_parts, "features")
            if owner_feature and target_feature and owner_feature != target_feature:
                graph.setdefault(owner_feature, set()).add(target_feature)
            if target_feature and owner_feature != target_feature and len(target_parts) > 2:
                errors.append(f"{path.relative_to(root)}: use {target_feature}'s public index")
    return errors + detect_cycles(graph, "web features")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    root = parser.parse_args().root
    errors = check_backend(root) + check_web(root)
    if errors:
        print("\n".join(errors))
        return 1
    print("Application boundaries are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
