from __future__ import annotations

import os
import shutil
import sys
import tomllib
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re


ROOT_DIR = Path(__file__).resolve().parent.parent
APP_DIR = ROOT_DIR / "app"
BUILD_ROOT = ROOT_DIR / ".doc_build"
DOCS_DIR = BUILD_ROOT / "docs"
SITE_DIR = ROOT_DIR / "dist" / "html"
MKDOCS_CONFIG = ROOT_DIR / "mkdocs.yml"
THEME_OVERRIDES_DIR = ROOT_DIR / "auto_docs" / "theme_overrides"
USE_DIRECTORY_URLS = False
RELEASE_MANIFEST_NAME = "release.toml"
RELEASE_CENTER_TARGET = Path("release-center") / "index.md"
RELEASE_HISTORY_TARGET = Path("release-center") / "history" / "index.md"
RELEASE_MODULE_LOGS_DIR = Path("release-center") / "modules"
HOME_RELEASE_PLACEHOLDER = "<!-- AUTO_DOCS:RELEASE_SUMMARY -->"

IGNORED_PARTS = {
    ".doc_build",
    ".git",
    ".idea",
    ".venv",
    "__pycache__",
    "dist",
}
IGNORED_SUFFIXES = {".py", ".pyc", ".pyo"}


@dataclass(slots=True)
class ReleaseEntry:
    manifest_path: Path
    module_relative_dir: Path
    module_name: str
    module_summary: str
    owner: str
    version: str
    channel: str
    released_at: str
    release_notes: str
    architecture_style: str
    runtime: str
    entrypoints: list[str]
    interfaces: list[str]
    platforms: list[str]
    dependencies: list[str]
    architecture_notes: str
    home_target: Path | None
    home_route: str | None
    slug: str
    log_target: Path
    log_route: str
    history: list["ReleaseHistoryItem"]


@dataclass(slots=True)
class ReleaseHistoryItem:
    version: str
    channel: str
    released_at: str
    title: str
    summary: str
    changes: list[str]
    breaking_changes: list[str]
    architecture_notes: str
    is_current: bool


def _is_hidden_or_ignored(relative_path: Path) -> bool:
    for part in relative_path.parts:
        if part in IGNORED_PARTS or part.startswith("."):
            return True
    return False


def _is_release_manifest(relative_path: Path) -> bool:
    return relative_path.name.lower() == RELEASE_MANIFEST_NAME


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
        if _is_release_manifest(relative_path):
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
    if USE_DIRECTORY_URLS:
        if target_relative.name.lower() == "index.md":
            parent = target_relative.parent.as_posix()
            return "/" if parent == "." else f"/{parent}/"
        return f"/{target_relative.with_suffix('').as_posix()}/"

    html_target = target_relative.with_suffix(".html").as_posix()
    return f"/{html_target}"


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


def _as_string(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _as_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                items.append(text)
        return items
    raise SystemExit(f"Unsupported list value in {RELEASE_MANIFEST_NAME}: {value!r}")


def _as_table_list(value: object) -> list[dict[str, object]]:
    if value is None:
        return []
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return value
    raise SystemExit(
        f"Unsupported history value in {RELEASE_MANIFEST_NAME}: expected array of tables, got {value!r}"
    )


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or "release"


def _parse_release_datetime(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None

    candidates = [text]
    if text.endswith("Z"):
        candidates.append(text[:-1] + "+00:00")

    for candidate in candidates:
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    return None


def _history_sort_key(item: "ReleaseHistoryItem") -> tuple[datetime, str, str]:
    return (
        _parse_release_datetime(item.released_at) or datetime.min,
        item.version,
        item.title,
    )


def _iter_release_manifest_paths() -> list[Path]:
    manifests: list[Path] = []
    for path in APP_DIR.rglob(RELEASE_MANIFEST_NAME):
        if not path.is_file():
            continue
        relative_path = path.relative_to(APP_DIR)
        if _is_hidden_or_ignored(relative_path):
            continue
        manifests.append(path)
    return sorted(manifests)


def _resolve_release_home_source(module_dir: Path, configured_home: str) -> Path | None:
    candidates: list[Path] = []
    if configured_home:
        candidates.append(module_dir / configured_home)
    candidates.extend([module_dir / "README.md", module_dir / "index.md"])

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists() and candidate.is_file() and candidate.suffix.lower() == ".md":
            return candidate
    return None


def _relative_doc_link(from_target: Path, to_target: Path) -> str:
    start = "." if str(from_target.parent) == "." else str(from_target.parent)
    return Path(os.path.relpath(str(to_target), start=start)).as_posix()


def _format_code_list(items: list[str]) -> str:
    if not items:
        return "-"
    return ", ".join(f"`{item}`" for item in items)


def _latest_release_date(entries: list[ReleaseEntry]) -> str:
    dates = sorted(entry.released_at for entry in entries if entry.released_at)
    return dates[-1] if dates else "-"


def _latest_history_date(entries: list[ReleaseEntry]) -> str:
    dates = sorted(
        item.released_at
        for entry in entries
        for item in entry.history
        if item.released_at
    )
    return dates[-1] if dates else "-"


def _build_history_items(
    module_name: str,
    version_data: dict[str, object],
    architecture_data: dict[str, object],
    raw_history: list[dict[str, object]],
) -> list[ReleaseHistoryItem]:
    current_version = _as_string(version_data.get("current"))
    current_channel = _as_string(version_data.get("channel"), "stable")
    current_released_at = _as_string(version_data.get("released_at"))
    current_notes = _as_string(version_data.get("notes"))
    current_architecture_notes = _as_string(architecture_data.get("notes"))

    history_items: list[ReleaseHistoryItem] = []
    seen_versions: set[str] = set()

    for raw_item in raw_history:
        version = _as_string(raw_item.get("version"))
        if not version:
            raise SystemExit(
                f"Missing history.version in {RELEASE_MANIFEST_NAME} for module {module_name}"
            )
        if version in seen_versions:
            raise SystemExit(
                f"Duplicate history.version `{version}` in {RELEASE_MANIFEST_NAME} for module {module_name}"
            )
        seen_versions.add(version)

        is_current = version == current_version
        history_items.append(
            ReleaseHistoryItem(
                version=version,
                channel=_as_string(
                    raw_item.get("channel"),
                    current_channel if is_current else "stable",
                ),
                released_at=_as_string(
                    raw_item.get("released_at"),
                    current_released_at if is_current else "",
                ),
                title=_as_string(raw_item.get("title"), f"{module_name} {version}"),
                summary=_as_string(
                    raw_item.get("summary"),
                    _as_string(raw_item.get("notes"), current_notes if is_current else ""),
                ),
                changes=_as_string_list(raw_item.get("changes")),
                breaking_changes=_as_string_list(raw_item.get("breaking_changes")),
                architecture_notes=_as_string(
                    raw_item.get("architecture_notes"),
                    current_architecture_notes if is_current else "",
                ),
                is_current=is_current,
            )
        )

    if current_version and current_version not in seen_versions:
        history_items.append(
            ReleaseHistoryItem(
                version=current_version,
                channel=current_channel,
                released_at=current_released_at,
                title=f"{module_name} {current_version}",
                summary=current_notes,
                changes=[],
                breaking_changes=[],
                architecture_notes=current_architecture_notes,
                is_current=True,
            )
        )

    history_items.sort(key=_history_sort_key, reverse=True)
    return history_items


def _all_history_records(entries: list[ReleaseEntry]) -> list[tuple[ReleaseEntry, ReleaseHistoryItem]]:
    records = [(entry, item) for entry in entries for item in entry.history]
    records.sort(key=lambda pair: _history_sort_key(pair[1]), reverse=True)
    return records


def _history_count(entries: list[ReleaseEntry]) -> int:
    return sum(len(entry.history) for entry in entries)


def _collect_release_entries() -> list[ReleaseEntry]:
    entries: list[ReleaseEntry] = []
    occupied_slugs: set[str] = set()

    for manifest_path in _iter_release_manifest_paths():
        data = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        module_data = data.get("module", {})
        version_data = data.get("version", {})
        architecture_data = data.get("architecture", {})
        raw_history = _as_table_list(data.get("history"))

        module_relative_dir = manifest_path.parent.relative_to(APP_DIR)
        default_name = module_relative_dir.as_posix() if module_relative_dir != Path(".") else "app"
        module_name = _as_string(module_data.get("name"), default_name)
        version = _as_string(version_data.get("current"))
        if not version:
            raise SystemExit(
                f"Missing version.current in {manifest_path.relative_to(ROOT_DIR).as_posix()}"
            )

        home_source = _resolve_release_home_source(
            manifest_path.parent,
            _as_string(module_data.get("home")),
        )
        home_target = _target_relative_path(home_source) if home_source is not None else None
        home_route = _route_from_target(home_target) if home_target is not None else None
        slug_source = module_relative_dir.as_posix() if module_relative_dir != Path(".") else module_name
        slug = _slugify(slug_source)
        if slug in occupied_slugs:
            raise SystemExit(f"Duplicate generated release log slug `{slug}`")
        occupied_slugs.add(slug)

        log_target = RELEASE_MODULE_LOGS_DIR / f"{slug}.md"
        history = _build_history_items(module_name, version_data, architecture_data, raw_history)

        entries.append(
            ReleaseEntry(
                manifest_path=manifest_path,
                module_relative_dir=module_relative_dir,
                module_name=module_name,
                module_summary=_as_string(module_data.get("summary")),
                owner=_as_string(module_data.get("owner")),
                version=version,
                channel=_as_string(version_data.get("channel"), "stable"),
                released_at=_as_string(version_data.get("released_at")),
                release_notes=_as_string(version_data.get("notes")),
                architecture_style=_as_string(architecture_data.get("style")),
                runtime=_as_string(architecture_data.get("runtime")),
                entrypoints=_as_string_list(architecture_data.get("entrypoints")),
                interfaces=_as_string_list(architecture_data.get("interfaces")),
                platforms=_as_string_list(architecture_data.get("platforms")),
                dependencies=_as_string_list(architecture_data.get("dependencies")),
                architecture_notes=_as_string(architecture_data.get("notes")),
                home_target=home_target,
                home_route=home_route,
                slug=slug,
                log_target=log_target,
                log_route=_route_from_target(log_target),
                history=history,
            )
        )

    return entries


def _build_release_table(entries: list[ReleaseEntry], from_target: Path) -> list[str]:
    lines = [
        "| 模块 | 版本 | 通道 | 架构 | 运行时 | 发布时间 |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for entry in entries:
        module_label = entry.module_name
        if entry.home_target is not None:
            module_label = f"[{entry.module_name}]({_relative_doc_link(from_target, entry.home_target)})"

        lines.append(
            "| "
            f"{module_label} | "
            f"`{entry.version}` | "
            f"`{entry.channel}` | "
            f"{entry.architecture_style or '-'} | "
            f"{entry.runtime or '-'} | "
            f"{entry.released_at or '-'} |"
        )

    return lines


def _build_history_table(
    records: list[tuple[ReleaseEntry, ReleaseHistoryItem]],
    from_target: Path,
    *,
    limit: int | None = None,
) -> list[str]:
    lines = [
        "| 日期 | 模块 | 版本 | 通道 | 标题 |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]

    subset = records if limit is None else records[:limit]
    for entry, item in subset:
        module_label = f"[{entry.module_name}]({_relative_doc_link(from_target, entry.log_target)})"
        lines.append(
            "| "
            f"{item.released_at or '-'} | "
            f"{module_label} | "
            f"`{item.version}` | "
            f"`{item.channel}` | "
            f"{item.title or '-'} |"
        )

    return lines


def _append_history_item_details(
    lines: list[str],
    *,
    from_target: Path,
    entry: ReleaseEntry,
    item: ReleaseHistoryItem,
    heading_level: str,
) -> None:
    lines.extend(
        [
            f"{heading_level} {entry.module_name} v{item.version}",
            "",
            f"- 发布时间: `{item.released_at or '-'}`",
            f"- 发布通道: `{item.channel}`",
            f"- 模块日志: [{entry.log_route}]({_relative_doc_link(from_target, entry.log_target)})",
        ]
    )

    if entry.home_target is not None and entry.home_route is not None:
        lines.append(
            f"- 模块文档: [{entry.home_route}]({_relative_doc_link(from_target, entry.home_target)})"
        )

    if item.title:
        lines.append(f"- 标题: {item.title}")
    if item.summary:
        lines.append(f"- 摘要: {item.summary}")
    if item.architecture_notes:
        lines.append(f"- 架构备注: {item.architecture_notes}")

    if item.changes:
        lines.extend(["", "变更内容:"])
        lines.extend(f"- {change}" for change in item.changes)

    if item.breaking_changes:
        lines.extend(["", "兼容性变更:"])
        lines.extend(f"- {change}" for change in item.breaking_changes)

    lines.append("")


def _build_release_home_summary(entries: list[ReleaseEntry]) -> str:
    if not entries:
        return (
            "> 当前未发现任何 `release.toml`。在子模块目录下添加该文件后，"
            "重新运行 `uv run build-docs` 即可自动汇总。"
        )

    counts = Counter(entry.channel for entry in entries)
    history_records = _all_history_records(entries)
    lines = [
        "> 该模块由 `build-docs` 自动生成，数据来源于各子模块目录下的 `release.toml`。",
        "",
        f"- 模块总数: `{len(entries)}`",
        f"- 发布通道: `{', '.join(f'{channel}={count}' for channel, count in sorted(counts.items()))}`",
        f"- 当前版本最近发布时间: `{_latest_release_date(entries)}`",
        f"- 历史记录数: `{_history_count(entries)}`",
        f"- 历史时间线最近发布时间: `{_latest_history_date(entries)}`",
        "",
    ]
    lines.extend(["当前版本汇总:"])
    lines.append("")
    lines.extend(_build_release_table(entries, Path("index.md")))
    if history_records:
        lines.extend(["", "最近发布:",""])
        lines.extend(_build_history_table(history_records, Path("index.md"), limit=5))
    lines.extend(
        [
            "",
            "更多详情见 [release-center/index.md](release-center/index.md) 和 [release-center/history/index.md](release-center/history/index.md)。",
        ]
    )
    return "\n".join(lines)


def _build_release_center_markdown(entries: list[ReleaseEntry]) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    history_records = _all_history_records(entries)
    lines = [
        "# 版本发布中心",
        "",
        "> 该页面由 `build-docs` 自动生成，统一汇总各子模块的当前版本、发布时间、架构信息和发布日志入口。",
        "",
        f"- 生成时间: `{generated_at}`",
        f"- 模块总数: `{len(entries)}`",
        f"- 当前版本最近发布时间: `{_latest_release_date(entries)}`",
        f"- 历史记录数: `{_history_count(entries)}`",
        f"- 历史时间线最近发布时间: `{_latest_history_date(entries)}`",
        "",
    ]

    if not entries:
        lines.append("当前未发现任何 `release.toml`。")
        return "\n".join(lines)

    counts = Counter(entry.channel for entry in entries)
    lines.append(
        "- 发布通道统计: "
        + ", ".join(f"`{channel}`={count}" for channel, count in sorted(counts.items()))
    )
    lines.extend(
        [
            "",
            "## 导航",
            "",
            f"- 全局历史时间线: [release-center/history/index.md]({_relative_doc_link(RELEASE_CENTER_TARGET, RELEASE_HISTORY_TARGET)})",
        ]
    )
    lines.extend(
        f"- {entry.module_name} 发布日志: [{entry.log_route}]({_relative_doc_link(RELEASE_CENTER_TARGET, entry.log_target)})"
        for entry in entries
    )
    lines.extend(["", "## 当前版本汇总", ""])
    lines.extend(_build_release_table(entries, RELEASE_CENTER_TARGET))
    if history_records:
        lines.extend(["", "## 最近发布", ""])
        lines.extend(_build_history_table(history_records, RELEASE_CENTER_TARGET, limit=10))
    lines.extend(["", "## 模块明细", ""])

    for entry in entries:
        lines.extend(
            [
                f"### {entry.module_name}",
                "",
                f"- 模块目录: `app/{entry.module_relative_dir.as_posix()}`",
                f"- 当前版本: `{entry.version}`",
                f"- 发布通道: `{entry.channel}`",
                f"- 发布时间: `{entry.released_at or '-'}`",
                f"- 负责人: `{entry.owner or '-'}`",
                f"- 架构形态: `{entry.architecture_style or '-'}`",
                f"- 运行时: `{entry.runtime or '-'}`",
                f"- 入口脚本: {_format_code_list(entry.entrypoints)}",
                f"- 对外接口: {_format_code_list(entry.interfaces)}",
                f"- 运行平台: {_format_code_list(entry.platforms)}",
                f"- 依赖模块: {_format_code_list(entry.dependencies)}",
                f"- 发布日志: [{entry.log_route}]({_relative_doc_link(RELEASE_CENTER_TARGET, entry.log_target)})",
            ]
        )
        if entry.home_target is not None:
            lines.append(
                f"- 文档入口: [{entry.home_route}]({_relative_doc_link(RELEASE_CENTER_TARGET, entry.home_target)})"
            )
        if entry.module_summary:
            lines.append(f"- 模块说明: {entry.module_summary}")
        if entry.release_notes:
            lines.append(f"- 发布说明: {entry.release_notes}")
        if entry.architecture_notes:
            lines.append(f"- 架构说明: {entry.architecture_notes}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _build_release_history_markdown(entries: list[ReleaseEntry]) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    records = _all_history_records(entries)
    lines = [
        "# 发布历史时间线",
        "",
        "> 该页面由 `build-docs` 自动生成，按发布时间倒序汇总所有模块的版本历史。",
        "",
        f"- 生成时间: `{generated_at}`",
        f"- 历史记录数: `{len(records)}`",
        f"- 最近发布时间: `{_latest_history_date(entries)}`",
        f"- 返回版本中心: [{_route_from_target(RELEASE_CENTER_TARGET)}]({_relative_doc_link(RELEASE_HISTORY_TARGET, RELEASE_CENTER_TARGET)})",
        "",
    ]

    if not records:
        lines.append("当前没有可展示的版本历史。")
        return "\n".join(lines)

    lines.extend(["## 最近发布", ""])
    lines.extend(_build_history_table(records, RELEASE_HISTORY_TARGET, limit=20))
    lines.extend(["", "## 时间线明细", ""])

    current_date = None
    for entry, item in records:
        date_label = item.released_at or "未标注日期"
        if date_label != current_date:
            current_date = date_label
            lines.extend([f"### {date_label}", ""])
        _append_history_item_details(
            lines,
            from_target=RELEASE_HISTORY_TARGET,
            entry=entry,
            item=item,
            heading_level="####",
        )

    return "\n".join(lines).rstrip() + "\n"


def _build_module_release_log_markdown(entry: ReleaseEntry) -> str:
    lines = [
        f"# {entry.module_name} 发布日志",
        "",
        "> 该页面由 `build-docs` 自动生成，展示当前模块的版本历史、变更项和架构备注。",
        "",
        f"- 模块目录: `app/{entry.module_relative_dir.as_posix()}`",
        f"- 当前版本: `{entry.version}`",
        f"- 发布通道: `{entry.channel}`",
        f"- 当前版本发布时间: `{entry.released_at or '-'}`",
        f"- 历史记录数: `{len(entry.history)}`",
        f"- 返回版本中心: [{_route_from_target(RELEASE_CENTER_TARGET)}]({_relative_doc_link(entry.log_target, RELEASE_CENTER_TARGET)})",
        f"- 查看全局时间线: [{_route_from_target(RELEASE_HISTORY_TARGET)}]({_relative_doc_link(entry.log_target, RELEASE_HISTORY_TARGET)})",
    ]

    if entry.home_target is not None and entry.home_route is not None:
        lines.append(
            f"- 模块文档: [{entry.home_route}]({_relative_doc_link(entry.log_target, entry.home_target)})"
        )
    if entry.module_summary:
        lines.append(f"- 模块说明: {entry.module_summary}")
    lines.extend(["", "## 版本概览", ""])
    lines.extend(
        _build_history_table([(entry, item) for item in entry.history], entry.log_target)
    )
    lines.extend(["", "## 版本明细", ""])

    for item in entry.history:
        _append_history_item_details(
            lines,
            from_target=entry.log_target,
            entry=entry,
            item=item,
            heading_level="###",
        )

    return "\n".join(lines).rstrip() + "\n"


def _write_release_pages(entries: list[ReleaseEntry]) -> None:
    generated_targets = [RELEASE_CENTER_TARGET, RELEASE_HISTORY_TARGET, *[entry.log_target for entry in entries]]
    for target in generated_targets:
        target_path = DOCS_DIR / target
        if target_path.exists():
            raise SystemExit(
                "Generated release page conflicts with an existing document: "
                f"{target_path.relative_to(ROOT_DIR).as_posix()}"
            )

    center_path = DOCS_DIR / RELEASE_CENTER_TARGET
    center_path.parent.mkdir(parents=True, exist_ok=True)
    center_path.write_text(_build_release_center_markdown(entries), encoding="utf-8")

    history_path = DOCS_DIR / RELEASE_HISTORY_TARGET
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(_build_release_history_markdown(entries), encoding="utf-8")

    for entry in entries:
        module_log_path = DOCS_DIR / entry.log_target
        module_log_path.parent.mkdir(parents=True, exist_ok=True)
        module_log_path.write_text(_build_module_release_log_markdown(entry), encoding="utf-8")


def _inject_release_summary_into_home(entries: list[ReleaseEntry]) -> None:
    home_path = DOCS_DIR / "index.md"
    if not home_path.exists():
        return

    content = home_path.read_text(encoding="utf-8")
    summary = _build_release_home_summary(entries)

    if HOME_RELEASE_PLACEHOLDER in content:
        updated = content.replace(HOME_RELEASE_PLACEHOLDER, summary)
    else:
        suffix = "" if content.endswith("\n") else "\n"
        updated = content + suffix + "\n## 版本发布总览\n\n" + summary + "\n"

    home_path.write_text(updated, encoding="utf-8")


def stage_docs() -> list[tuple[Path, str]]:
    source_files, markdown_routes = _prepare_source_manifest()
    release_entries = _collect_release_entries()

    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    for source_path in source_files:
        target_relative = _target_relative_path(source_path)
        target_path = DOCS_DIR / target_relative
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)

    _write_release_pages(release_entries)
    _inject_release_summary_into_home(release_entries)

    return markdown_routes


def _patch_mkdocs_shadcn_windows_paths() -> None:
    from shadcn.plugins.mixins.markdown import MarkdownMixin

    def on_page_context(self, context, page, config, nav):
        src_path = page.file.src_path.replace("\\", "/")
        self.raw_markdown[page.file.abs_src_path] = str(Path(config.site_dir) / Path(src_path))
        context.update(
            {
                "raw_markdown_url": src_path
            }
        )
        return super(MarkdownMixin, self).on_page_context(context, page, config, nav)

    MarkdownMixin.on_page_context = on_page_context


def _patch_mkdocs_shadcn_autonumber_local_links() -> None:
    from shadcn.plugins.autonumber import AutoNumberPlugin

    def on_page_content(self, html, page, config, files):
        for match in self.reference_pattern.finditer(html):
            full_match: str = match.group(0)
            prefix: str = match.group(1)
            is_capitalized: bool = prefix[0].isupper()
            prefix = prefix.lower()

            id_: str = match.group(2)
            if id_ not in self.registry:
                continue

            entry = self.registry[id_]
            if entry.prefix != prefix:
                continue

            label = (
                self.config.prefixes[prefix].capitalize()
                if is_capitalized
                else self.config.prefixes[prefix].lower()
            )

            if entry.page.file.src_uri == page.file.src_uri:
                href = f"#{entry.anchor}"
            else:
                href = f"{entry.page.file.url_relative_to(page.file)}#{entry.anchor}"

            replacement = (
                f'<a href="{href}" class="autonumber {prefix}">'
                f"{label} {entry.number}</a>"
            )
            html = html.replace(full_match, replacement)

        return html

    AutoNumberPlugin.on_page_content = on_page_content


def build_site() -> list[tuple[Path, str]]:
    from mkdocs.commands.build import build
    from mkdocs.config import load_config

    routes = stage_docs()
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    _patch_mkdocs_shadcn_windows_paths()
    _patch_mkdocs_shadcn_autonumber_local_links()
    config = load_config(config_file_path=str(MKDOCS_CONFIG))
    overrides_dir = str(THEME_OVERRIDES_DIR.resolve())
    config.theme.dirs[:] = [overrides_dir, *[d for d in config.theme.dirs if Path(d).resolve() != Path(overrides_dir)]]
    config.use_directory_urls = USE_DIRECTORY_URLS
    config.plugins.on_startup(command="build", dirty=False)
    build(config, dirty=False)
    return routes


def _print_routes(routes: list[tuple[Path, str]]) -> None:
    for source_path, route in routes:
        print(f"{source_path.as_posix()} -> {route}")


def _print_release_entries(entries: list[ReleaseEntry]) -> None:
    for entry in entries:
        route = entry.home_route or "-"
        print(
            f"{entry.manifest_path.relative_to(ROOT_DIR).as_posix()} -> "
            f"{entry.module_name} "
            f"(v{entry.version}, {entry.channel}, {route}, history={len(entry.history)})"
        )


def build_cli() -> None:
    routes = build_site()
    release_entries = _collect_release_entries()
    print(f"Built {len(routes)} markdown pages into {SITE_DIR}")
    print(
        "Aggregated "
        f"{len(release_entries)} release manifests into "
        f"{(DOCS_DIR / RELEASE_CENTER_TARGET).relative_to(ROOT_DIR).as_posix()}"
    )
    print(
        "Generated "
        f"{_history_count(release_entries)} history entries into "
        f"{(DOCS_DIR / RELEASE_HISTORY_TARGET).relative_to(ROOT_DIR).as_posix()}"
    )
    _print_routes(routes)


def scan_cli() -> None:
    _, routes = _prepare_source_manifest()
    print(f"Discovered {len(routes)} markdown pages under {APP_DIR}")
    _print_routes(routes)


def scan_releases_cli() -> None:
    entries = _collect_release_entries()
    counts = Counter(entry.channel for entry in entries)
    print(f"Discovered {len(entries)} release manifests under {APP_DIR}")
    if counts:
        print(
            "Release channel stats: "
            + ", ".join(f"{channel}={count}" for channel, count in sorted(counts.items()))
        )
    else:
        print("Release channel stats: none")
    print(f"Release history entries: {_history_count(entries)}")
    _print_release_entries(entries)


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "build"
    if command == "build":
        build_cli()
        return
    if command == "scan":
        scan_cli()
        return
    if command == "scan-releases":
        scan_releases_cli()
        return
    raise SystemExit("Usage: python -m auto_docs.docsite [build|scan|scan-releases]")


if __name__ == "__main__":
    main()
