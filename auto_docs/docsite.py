from __future__ import annotations

import shutil
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
APP_DIR = ROOT_DIR / "app"
BUILD_ROOT = ROOT_DIR / ".doc_build"
DOCS_DIR = BUILD_ROOT / "docs"
SITE_DIR = ROOT_DIR / "dist" / "html"
MKDOCS_CONFIG = ROOT_DIR / "mkdocs.yml"

IGNORED_PARTS = {
    ".doc_build",
    ".git",
    ".idea",
    ".venv",
    "__pycache__",
    "dist",
}
IGNORED_SUFFIXES = {".py", ".pyc", ".pyo"}


def _is_hidden_or_ignored(relative_path: Path) -> bool:
    for part in relative_path.parts:
        if part in IGNORED_PARTS or part.startswith("."):
            return True
    return False


def _iter_source_files() -> list[Path]:
    if not APP_DIR.exists():
        raise SystemExit(f"Missing app directory: {APP_DIR}")

    files: list[Path] = []
    for path in APP_DIR.rglob("*"):
        if not path.is_file():
            continue
        relative_path = path.relative_to(APP_DIR)
        if _is_hidden_or_ignored(relative_path):
            continue
        if path.suffix.lower() in IGNORED_SUFFIXES:
            continue
        files.append(path)
    return sorted(files)


def _target_relative_path(source_path: Path) -> Path:
    relative_path = source_path.relative_to(APP_DIR)
    if relative_path.name.lower() == "readme.md":
        return relative_path.with_name("index.md")
    if relative_path.name.lower() == "index.md":
        return relative_path.with_suffix("") / "index.md"
    return relative_path


def _route_from_target(target_relative: Path) -> str:
    if target_relative.name.lower() == "index.md":
        parent = target_relative.parent.as_posix()
        return "/" if parent == "." else f"/{parent}/"
    return f"/{target_relative.with_suffix('').as_posix()}/"


def _raise_target_collision(existing_source: Path, source_path: Path, target_relative: Path) -> None:
    raise SystemExit(
        "Target path collision detected between "
        f"{existing_source.relative_to(ROOT_DIR)} and {source_path.relative_to(ROOT_DIR)} "
        f"-> {target_relative.as_posix()}"
    )


def _raise_route_collision(existing_source: Path, source_path: Path, route: str) -> None:
    raise SystemExit(
        "Route collision detected between "
        f"{existing_source.relative_to(ROOT_DIR)} and {source_path.relative_to(ROOT_DIR)} "
        f"-> {route}"
    )


def _prepare_source_manifest() -> tuple[list[Path], list[tuple[Path, str]]]:
    occupied_targets: dict[Path, Path] = {}
    occupied_routes: dict[str, Path] = {}
    for source_path in _iter_source_files():
        target_relative = _target_relative_path(source_path)
        existing_source = occupied_targets.get(target_relative)
        if existing_source is not None:
            _raise_target_collision(existing_source, source_path, target_relative)
        occupied_targets[target_relative] = source_path

        if source_path.suffix.lower() == ".md":
            route = _route_from_target(target_relative)
            existing_route = occupied_routes.get(route)
            if existing_route is not None:
                _raise_route_collision(existing_route, source_path, route)
            occupied_routes[route] = source_path

    source_files = sorted(occupied_targets.values())
    markdown_routes: list[tuple[Path, str]] = []
    for source_path in source_files:
        if source_path.suffix.lower() != ".md":
            continue
        target_relative = _target_relative_path(source_path)
        markdown_routes.append((source_path.relative_to(ROOT_DIR), _route_from_target(target_relative)))

    if not markdown_routes:
        raise SystemExit(f"No Markdown files found under {APP_DIR}")

    return source_files, markdown_routes


def stage_docs() -> list[tuple[Path, str]]:
    source_files, markdown_routes = _prepare_source_manifest()

    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    for source_path in source_files:
        target_relative = _target_relative_path(source_path)
        target_path = DOCS_DIR / target_relative
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)

    return markdown_routes


def _patch_mkdocs_shadcn_windows_paths() -> None:
    from urllib.parse import urljoin

    from shadcn.plugins.mixins.markdown import MarkdownMixin

    def on_page_context(self, context, page, config, nav):
        src_path = page.file.src_path.replace("\\", "/")
        self.raw_markdown[page.file.abs_src_path] = str(Path(config.site_dir) / Path(src_path))
        context.update(
            {
                "raw_markdown_url": urljoin(
                    config.site_url or "/",
                    src_path,
                )
            }
        )
        return super(MarkdownMixin, self).on_page_context(context, page, config, nav)

    MarkdownMixin.on_page_context = on_page_context


def build_site() -> list[tuple[Path, str]]:
    from mkdocs.commands.build import build
    from mkdocs.config import load_config

    routes = stage_docs()
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    _patch_mkdocs_shadcn_windows_paths()
    config = load_config(config_file_path=str(MKDOCS_CONFIG))
    config.plugins.on_startup(command="build", dirty=False)
    build(config, dirty=False)
    return routes


def _print_routes(routes: list[tuple[Path, str]]) -> None:
    for source_path, route in routes:
        print(f"{source_path.as_posix()} -> {route}")


def build_cli() -> None:
    routes = build_site()
    print(f"Built {len(routes)} markdown pages into {SITE_DIR}")
    _print_routes(routes)


def scan_cli() -> None:
    _, routes = _prepare_source_manifest()
    print(f"Discovered {len(routes)} markdown pages under {APP_DIR}")
    _print_routes(routes)


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "build"
    if command == "build":
        build_cli()
        return
    if command == "scan":
        scan_cli()
        return
    raise SystemExit("Usage: python -m auto_docs.docsite [build|scan]")


if __name__ == "__main__":
    main()
