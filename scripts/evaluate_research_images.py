from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from opentoonz_line_tools.autoclose import AutoCloseSettings, autoclose_gaps, closure_overlay
from opentoonz_line_tools.cleanup import BlueCleanupSettings, cleanup_blue_lines
from opentoonz_line_tools.regions import RegionSettings, label_fill_regions, labels_to_preview

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate OpenToonz Line Tools on research image sets.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--dataset-root", type=Path, help="Dataset root containing images/train and images/val.")
    source.add_argument("--image-root", type=Path, help="Directory containing images directly or recursively.")
    parser.add_argument("--output-dir", required=True, type=Path, help="Directory for metrics and contact sheet outputs.")
    parser.add_argument("--image-glob", default="panel*.*", help="Glob used with --image-root. Default: panel*.*")
    parser.add_argument("--region-min-area", default=256, type=int)
    parser.add_argument("--max-regions", default=128, type=int)
    parser.add_argument("--max-endpoints", default=600, type=int)
    parser.add_argument("--thumb-width", default=220, type=int)
    return parser.parse_args()


def dataset_image_paths(dataset_root: Path) -> list[Path]:
    image_root = dataset_root / "images"
    return [
        path
        for path in sorted(image_root.glob("*/*.*"))
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    ]


def root_image_paths(image_root: Path, image_glob: str) -> list[Path]:
    return [
        path
        for path in sorted(image_root.rglob(image_glob))
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    ]


def label_count(dataset_root: Path, image_path: Path) -> int:
    rel = image_path.relative_to(dataset_root)
    label_path = dataset_root / "labels" / rel.parent.name / f"{image_path.stem}.txt"
    if not label_path.exists():
        return 0
    return sum(1 for line in label_path.read_text(encoding="utf-8").splitlines() if line.strip())


def fit(image: Image.Image, width: int) -> Image.Image:
    height = max(1, round(image.height * width / image.width))
    return image.resize((width, height), Image.Resampling.LANCZOS)


def make_contact_row(
    *,
    index: int,
    rel: Path,
    label_count_value: int,
    line_ratio: float,
    skipped: str,
    region_count: int,
    images: list[Image.Image],
    thumb_width: int,
) -> Image.Image:
    thumbs = [fit(image, thumb_width) for image in images]
    label_h = 42
    row_h = max(thumb.height for thumb in thumbs) + label_h
    strip = Image.new("RGB", (thumb_width * len(thumbs), row_h), "white")
    draw = ImageDraw.Draw(strip)
    title = f"{index:02d} {rel.name} labels={label_count_value} line={line_ratio:.3f} regions={region_count}"
    draw.text((4, 4), title, fill=(0, 0, 0))
    if skipped:
        draw.text((4, 20), skipped[:90], fill=(180, 0, 0))
    for column, thumb in enumerate(thumbs):
        strip.paste(thumb, (column * thumb_width, label_h))
    return strip


def write_contact_sheet(rows: list[Image.Image], path: Path) -> None:
    width = max(row.width for row in rows)
    height = sum(row.height for row in rows)
    contact = Image.new("RGB", (width, height), "white")
    y = 0
    for row in rows:
        contact.paste(row, (0, y))
        y += row.height
    contact.save(path, quality=90)


def write_summary(summary: dict[str, Any], path: Path) -> None:
    rows = summary["rows"]
    max_regions = summary["settings"]["regions"]["max_regions"]
    lines = [
        f"# {summary['title']}",
        "",
        f"Dataset: `{summary['dataset']}`",
        "",
        "## Summary",
        "",
        f"- Images: {summary['image_count']}",
        f"- Avg blue line ratio: {summary['averages']['line_ratio']}",
        f"- Avg cleanup sec: {summary['averages']['cleanup_sec']}",
        f"- Avg autoclose sec: {summary['averages']['autoclose_sec']}",
        f"- Autoclose skipped: {summary['counts']['autoclose_skipped']}/{summary['image_count']}",
        f"- Avg region count: {summary['averages']['region_count']}",
        f"- Region capped at {max_regions}: {summary['counts']['region_capped']}/{summary['image_count']}",
        "",
        "## Rows",
        "",
        "| file | split | labels | line ratio | skip | regions |",
        "|---|---:|---:|---:|---|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['file']} | {row['split']} | {row['label_count']} | {row['line_ratio']} | "
            f"{row['autoclose_skipped']} | {row['region_count']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.dataset_root:
        source_root = args.dataset_root
        paths = dataset_image_paths(source_root)
        title = "MC/MS Research Image Evaluation"
        source_kind = "dataset"
    else:
        source_root = args.image_root
        paths = root_image_paths(source_root, args.image_glob)
        title = "Panel Crop Image Evaluation"
        source_kind = "image_root"
    if not paths:
        raise SystemExit(f"No images found under {source_root} with the selected input mode.")
    cleanup_settings = BlueCleanupSettings()
    autoclose_settings = AutoCloseSettings(max_endpoints=args.max_endpoints)
    region_settings = RegionSettings(
        min_area=args.region_min_area,
        max_regions=args.max_regions,
        ignore_border_regions=True,
    )

    rows: list[dict[str, Any]] = []
    contact_rows: list[Image.Image] = []
    for index, path in enumerate(paths, 1):
        rel = path.relative_to(source_root)
        source_pil = Image.open(path).convert("RGB")
        source = np.asarray(source_pil)
        labels = label_count(source_root, path) if args.dataset_root else 0

        start = time.perf_counter()
        clean = cleanup_blue_lines(source, cleanup_settings)
        cleanup_sec = time.perf_counter() - start

        start = time.perf_counter()
        closed = autoclose_gaps(clean["line_mask"], autoclose_settings)
        autoclose_sec = time.perf_counter() - start

        start = time.perf_counter()
        regions = label_fill_regions(closed["closed_mask"], region_settings)
        region_sec = time.perf_counter() - start

        line_ratio = float(clean["line_mask"].mean())
        row = {
            "index": index,
            "split": rel.parts[1] if args.dataset_root and len(rel.parts) > 1 else rel.parent.as_posix() or ".",
            "file": rel.name,
            "relative_path": str(rel),
            "width": int(source.shape[1]),
            "height": int(source.shape[0]),
            "label_count": labels,
            "line_ratio": round(line_ratio, 6),
            "cleanup_sec": round(cleanup_sec, 3),
            "autoclose_sec": round(autoclose_sec, 3),
            "segments": len(closed["segments"]),
            "autoclose_skipped": closed["skipped"],
            "region_sec": round(region_sec, 3),
            "region_count": len(regions["regions"]),
            "region_capped": len(regions["regions"]) >= region_settings.max_regions,
        }
        rows.append(row)

        contact_rows.append(
            make_contact_row(
                index=index,
                rel=rel,
                label_count_value=labels,
                line_ratio=line_ratio,
                skipped=closed["skipped"],
                region_count=len(regions["regions"]),
                images=[
                    source_pil,
                    Image.fromarray(clean["line_rgb"]),
                    Image.fromarray(closure_overlay(clean["line_mask"], closed["closed_mask"])),
                    Image.fromarray(labels_to_preview(regions["label_map"], closed["closed_mask"])),
                ],
                thumb_width=args.thumb_width,
            )
        )
        print(
            f"{index:02d}/{len(paths)} {rel} "
            f"line={line_ratio:.4f} skip={closed['skipped'] or '-'} regions={len(regions['regions'])}"
        )

    summary = {
        "title": title,
        "dataset": str(source_root),
        "source_kind": source_kind,
        "image_glob": args.image_glob if args.image_root else None,
        "image_count": len(rows),
        "settings": {
            "cleanup": cleanup_settings.__dict__,
            "autoclose": autoclose_settings.__dict__,
            "regions": region_settings.__dict__,
        },
        "averages": {
            "line_ratio": round(sum(row["line_ratio"] for row in rows) / max(1, len(rows)), 6),
            "cleanup_sec": round(sum(row["cleanup_sec"] for row in rows) / max(1, len(rows)), 3),
            "autoclose_sec": round(sum(row["autoclose_sec"] for row in rows) / max(1, len(rows)), 3),
            "region_sec": round(sum(row["region_sec"] for row in rows) / max(1, len(rows)), 3),
            "region_count": round(sum(row["region_count"] for row in rows) / max(1, len(rows)), 2),
        },
        "counts": {
            "autoclose_skipped": sum(1 for row in rows if row["autoclose_skipped"]),
            "region_capped": sum(1 for row in rows if row["region_capped"]),
            "low_blue_signal_lt_0_03": sum(1 for row in rows if row["line_ratio"] < 0.03),
        },
        "rows": rows,
    }
    (args.output_dir / "metrics.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_summary(summary, args.output_dir / "summary.md")
    write_contact_sheet(contact_rows, args.output_dir / "contact_sheet.jpg")
    print(f"wrote {args.output_dir}")


if __name__ == "__main__":
    main()
