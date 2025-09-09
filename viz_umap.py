from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd


def find_project_root(start: Path | str) -> Path:
    cur = Path(start).resolve()
    for p in [cur, *cur.parents]:
        if (p / "settings.yaml").exists() or (p / "settings.yml").exists():
            return p
    return cur


def load_entities(output_dir: Path) -> pd.DataFrame:
    entities_path = output_dir / "entities.parquet"
    if not entities_path.exists():
        raise FileNotFoundError(f"Missing {entities_path}. Re-run indexing first.")
    return pd.read_parquet(entities_path)


def resolve_xy_columns(df: pd.DataFrame) -> tuple[str, str]:
    candidates = [("x", "y"), ("umap_x", "umap_y"), ("umapX", "umapY")]
    for x_col, y_col in candidates:
        if x_col in df.columns and y_col in df.columns:
            return x_col, y_col
    raise KeyError(
        "UMAP columns not found. Expected one of: x/y, umap_x/umap_y, umapX/umapY. "
        "Ensure settings.yaml has embed_graph.enabled: true and umap.enabled: true, then re-index."
    )


def plot_umap(df: pd.DataFrame, x_col: str, y_col: str, output_file: Path, label_top: int = 0) -> None:
    import matplotlib.pyplot as plt  # lazy import

    plt.figure(figsize=(8, 6), dpi=150)
    plt.scatter(df[x_col], df[y_col], s=8, c="#2563eb", alpha=0.6, linewidths=0)
    plt.title("GraphRAG UMAP (entities)")
    plt.xlabel(x_col)
    plt.ylabel(y_col)
    plt.tight_layout()

    # Optional labeling of top-N by degree/count if present
    if label_top > 0:
        score_col = None
        for c in ("degree", "count", "rank"):
            if c in df.columns:
                score_col = c
                break
        if score_col is not None:
            top = df.sort_values(by=score_col, ascending=False).head(label_top)
            for _, row in top.iterrows():
                label = str(row.get("title") or row.get("name") or row.get("id"))
                plt.text(row[x_col], row[y_col], label, fontsize=6, alpha=0.8)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_file)
    # Do not plt.show() by default to keep it non-blocking


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Render a 2D UMAP scatter from GraphRAG entities")
    p.add_argument("--root", default=None, help="Project root (contains settings.yaml). Default: auto-detect")
    p.add_argument("--output", default=None, help="Explicit output dir (default: <root>/output)")
    p.add_argument("--png", default=None, help="Path to save PNG (default: <output>/umap_scatter.png)")
    p.add_argument("--label-top", type=int, default=0, help="Label top-N entities by degree/count")
    args = p.parse_args(argv)

    root = find_project_root(args.root or Path.cwd())
    out_dir = Path(args.output) if args.output else (root / "output")
    png_path = Path(args.png) if args.png else (out_dir / "umap_scatter.png")

    df = load_entities(out_dir)
    x_col, y_col = resolve_xy_columns(df)
    plot_umap(df, x_col, y_col, png_path, label_top=args.label_top)
    print(f"Saved: {png_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
