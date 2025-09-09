"""Query execution helper for SynthBio Researcher.

Centralizes GraphRAG global search invocation, run selection, and citation
extraction so both the CLI script and Flask API can share identical logic.

Rules (see Plan.md Live Technical Notes & copilot-instructions):
 - No mock pathways.
 - Select latest run directory automatically (timestamped or default `output`).
 - Community-level citations only (top 5 by rank) for speed.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import sys

# Ensure local graphrag package is importable when running from repo root
try:  # pragma: no cover - best-effort path fix for ad-hoc runs
    import graphrag.api as api  # type: ignore
    from graphrag.callbacks.noop_query_callbacks import NoopQueryCallbacks  # type: ignore
    from graphrag.config.load_config import load_config  # type: ignore
    from graphrag.config.models.graph_rag_config import (  # type: ignore
        GraphRagConfig,
    )
    from graphrag.utils.api import create_storage_from_config  # type: ignore
    from graphrag.utils.storage import load_table_from_storage  # type: ignore
except Exception:  # pragma: no cover
    sys.path.append(str(Path(__file__).parent / "graphrag"))
    import graphrag.api as api  # type: ignore
    from graphrag.callbacks.noop_query_callbacks import NoopQueryCallbacks  # type: ignore
    from graphrag.config.load_config import load_config  # type: ignore
    from graphrag.config.models.graph_rag_config import (  # type: ignore
        GraphRagConfig,
    )
    from graphrag.utils.api import create_storage_from_config  # type: ignore
    from graphrag.utils.storage import load_table_from_storage  # type: ignore


# -----------------------------
# Utilities
# -----------------------------


def _find_root_dir(start: Path | str) -> Path:
    """Find the repository root by searching upward for a settings.yaml file."""
    cur = Path(start).resolve()
    for p in [cur, *cur.parents]:
        if (p / "settings.yaml").exists() or (p / "settings.yml").exists():
            return p
    # Fallback to given dir
    return cur


def _looks_like_timestamp_dir(name: str) -> bool:
    # Accept a few common patterns without being too strict
    # e.g. 2025-09-08_14-53-13, 20250908-145313, 2025-09-08-145313
    digits = [c for c in name if c.isdigit()]
    return len(digits) >= 8 and any(sep in name for sep in ("-", "_"))


def _select_latest_run_dir(root: Path, config: GraphRagConfig) -> Path:
    """Select the latest run directory.

    Prefers the configured output.base_dir; if that directory does not contain
    the expected tables, scans under `output/` for the most recent subdir that does.
    """
    # Single-index only: favor config.output
    out_cfg = getattr(config, "output", None)
    if out_cfg is not None and getattr(out_cfg, "base_dir", None):
        base = root / out_cfg.base_dir
        if _dir_has_minimum_tables(base):
            return base

    # Fallback: scan root/output/*
    output_root = root / "output"
    if not output_root.exists():
        return output_root  # likely a new run or custom path; return as-is

    candidates: list[tuple[float, Path]] = []
    for child in output_root.iterdir():
        if child.is_dir() and (_looks_like_timestamp_dir(child.name) or True):
            if _dir_has_minimum_tables(child):
                candidates.append((child.stat().st_mtime, child))
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    # Nothing matched; return configured base or output_root
    return out_cfg.base_dir if out_cfg is not None else output_root


def _dir_has_minimum_tables(path: Path) -> bool:
    # Check for at least the required Parquet files for global search
    required = {"entities.parquet", "communities.parquet", "community_reports.parquet"}
    try:
        present = {p.name for p in path.iterdir() if p.is_file()}
    except FileNotFoundError:
        return False
    return required.issubset(present)


async def _load_global_tables(config: GraphRagConfig) -> dict[str, pd.DataFrame]:
    """Load the minimal set of tables for global search via configured storage."""
    storage = create_storage_from_config(config.output)
    names = ["entities", "communities", "community_reports"]
    dfs: dict[str, pd.DataFrame] = {}
    for n in names:
        dfs[n] = await load_table_from_storage(name=n, storage=storage)
    return dfs


def _top5_reports_only(context_data: dict[str, Any]) -> dict[str, Any]:
    """Return only top-5 community report citations from context_data."""
    reports = context_data.get("reports")

    # Normalize to DataFrame
    if reports is None:
        return {"reports": []}
    if isinstance(reports, pd.DataFrame):
        df = reports
    else:
        df = pd.DataFrame(reports)

    # Sort by rank ascending (best first) if available
    if "rank" in df.columns:
        df_sorted = df.sort_values(by=["rank", "id"], ascending=[True, True])
    else:
        df_sorted = df

    # Keep a concise set of useful columns if present
    preferred_cols = [
        c
        for c in ["id", "title", "summary", "rank", "community", "human_readable_id"]
        if c in df_sorted.columns
    ]
    df_final = df_sorted[preferred_cols] if preferred_cols else df_sorted
    return {"reports": df_final.head(5).to_dict(orient="records")}  # type: ignore[arg-type]


# -----------------------------
# Public Runner
# -----------------------------


@dataclass
class QueryResult:
    query: str
    answer: str
    citations: dict[str, Any]
    run_dir: str


def run_global_query(
    query: str,
    root: Optional[str | Path] = None,
    community_level: Optional[int] = None,
    dynamic_community_selection: bool = True,
    response_type: str = "multiple_paragraphs",
    verbose: bool = False,
) -> QueryResult:
    """Execute a global search against the latest run and return trimmed citations."""
    root_dir = _find_root_dir(root or Path.cwd())

    # Load base config
    base_config = load_config(root_dir=root_dir)

    # Select latest run dir and (if different) override output.base_dir
    run_dir = _select_latest_run_dir(root_dir, base_config)
    overrides: dict[str, Any] = {}
    if getattr(base_config.output, "base_dir", None):
        abs_base = (root_dir / base_config.output.base_dir).resolve()
        if abs_base != Path(run_dir).resolve():
            overrides["output.base_dir"] = str(run_dir)

    config = load_config(root_dir=root_dir, cli_overrides=overrides or None)

    # Load minimal tables
    dfs = asyncio.run(_load_global_tables(config))

    # Capture context via callbacks
    full_response = ""
    context_data: dict[str, Any] = {}

    def on_context(ctx: Any) -> None:
        nonlocal context_data
        context_data = ctx

    callbacks = NoopQueryCallbacks()
    callbacks.on_context = on_context

    # Execute search (non-streaming for simplicity)
    answer, _ctx = asyncio.run(
        api.global_search(
            config=config,
            entities=dfs["entities"],
            communities=dfs["communities"],
            community_reports=dfs["community_reports"],
            community_level=community_level,
            dynamic_community_selection=dynamic_community_selection,
            response_type=response_type,
            query=query,
            callbacks=[callbacks],
            verbose=verbose,
        )
    )
    full_response = answer

    # Trim citations: community reports only, top-5 by rank
    citations = _top5_reports_only(context_data)

    return QueryResult(
        query=query,
        answer=full_response,
        citations=citations,
        run_dir=str(run_dir),
    )


# -----------------------------
# CLI entry (smoke-friendly)
# -----------------------------


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="GraphRAG query runner (global search)")
    p.add_argument("--query", required=True, help="Query text")
    p.add_argument("--root", default=None, help="Root dir (contains settings.yaml)")
    p.add_argument(
        "--community-level",
        type=int,
        default=None,
        help="Optional fixed community level cap",
    )
    p.add_argument(
        "--no-dynamic",
        action="store_true",
        help="Disable dynamic community selection",
    )
    p.add_argument(
        "--response-type",
        default="multiple_paragraphs",
        help="Response type (default: multiple_paragraphs)",
    )
    p.add_argument("--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_argparser().parse_args(argv)
    result = run_global_query(
        query=args.query,
        root=args.root,
        community_level=args.community_level,
        dynamic_community_selection=not args.no_dynamic,
        response_type=args.response_type,
        verbose=args.verbose,
    )

    # Minimal smoke-style printout
    print("=== Answer ===\n" + result.answer.strip() + "\n")
    print(f"Run dir: {result.run_dir}")
    reports = result.citations.get("reports", [])
    print(f"Citations (community reports): {len(reports)} shown (top-5)")
    for r in reports:
        rid = r.get("id", "?")
        title = r.get("title") or r.get("label") or "(no title)"
        rank = r.get("rank", "?")
        print(f" - [{rid}] rank={rank} :: {title}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
