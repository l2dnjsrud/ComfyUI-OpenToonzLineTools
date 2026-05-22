from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

PIPELINE_ROOT = Path("/Users/iwongyeong/AI/ComfyUI/tools/manga_color_pipeline")
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from manga_color_pipeline.comfy_client import ComfyClient, load_workflow
from opentoonz_line_tools.autoclose import AutoCloseSettings, autoclose_gaps, mask_to_rgb
from opentoonz_line_tools.cleanup import BlueCleanupSettings, cleanup_blue_lines
from opentoonz_line_tools.regions import RegionSettings, label_fill_regions, labels_to_preview


POSITIVE_PROMPT = (
    "fully colored anime manga action panel, clean cel shading, preserve the exact manga line art, "
    "consistent warm skin tones, dark hair, muted cloth colors, readable shadows, dramatic action lighting, "
    "professional webtoon color finish"
)
NEGATIVE_PROMPT = (
    "blue pencil only, monochrome, grayscale, uncolored, changed pose, changed composition, changed line art, "
    "extra fingers, missing hands, distorted face, watermark, logo, text artifacts, blurry, muddy colors"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare raw, cleaned, and gap-closed panel colorization.")
    parser.add_argument("--panel-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--comfy-root", default=Path("/Users/iwongyeong/AI/ComfyUI"), type=Path)
    parser.add_argument("--server", default="http://127.0.0.1:8188")
    parser.add_argument(
        "--workflow",
        default=Path("/Users/iwongyeong/AI/ComfyUI/user/default/workflows/blue_lineart_controlnet_api.json"),
        type=Path,
    )
    parser.add_argument("--checkpoint", default="Anything-v5.0-PRT.safetensors")
    parser.add_argument("--controlnet", default="control_v11p_sd15s2_lineart_anime_fp16.safetensors")
    parser.add_argument("--panels", nargs="*", default=["panel_002.png", "panel_003.png", "panel_004.png", "panel_005.png", "panel_006.png"])
    parser.add_argument("--max-side", default=768, type=int)
    parser.add_argument("--steps", default=20, type=int)
    parser.add_argument("--cfg", default=6.0, type=float)
    parser.add_argument("--strength", default=0.75, type=float)
    parser.add_argument("--sampler", default="dpmpp_2m")
    parser.add_argument("--scheduler", default="karras")
    parser.add_argument("--seed-base", default=2026052201, type=int)
    parser.add_argument("--thumb-width", default=190, type=int)
    return parser.parse_args()


def rounded(value: int) -> int:
    return max(64, int(round(value / 8)) * 8)


def fit_for_generation(image: Image.Image, max_side: int) -> Image.Image:
    scale = min(1.0, max_side / max(image.size))
    width = rounded(image.width * scale)
    height = rounded(image.height * scale)
    return image.resize((width, height), Image.Resampling.LANCZOS).convert("RGB")


def patch_controlnet_workflow(
    base: dict[str, Any],
    *,
    image_name: str,
    checkpoint: str,
    controlnet: str,
    width: int,
    height: int,
    seed: int,
    steps: int,
    cfg: float,
    strength: float,
    sampler: str,
    scheduler: str,
    prefix: str,
) -> dict[str, Any]:
    workflow = copy.deepcopy(base)
    by_class = nodes_by_class(workflow)
    set_first_input(by_class, "LoadImage", "image", image_name)
    set_first_input(by_class, "CheckpointLoaderSimple", "ckpt_name", checkpoint)
    set_first_input(by_class, "ControlNetLoader", "control_net_name", controlnet)
    set_indexed_prompt(by_class, 0, POSITIVE_PROMPT)
    set_indexed_prompt(by_class, 1, NEGATIVE_PROMPT)
    set_first_input(by_class, "ControlNetApplyAdvanced", "strength", strength)
    set_first_input(by_class, "EmptyLatentImage", "width", width)
    set_first_input(by_class, "EmptyLatentImage", "height", height)
    set_first_input(by_class, "KSampler", "seed", seed)
    set_first_input(by_class, "KSampler", "steps", steps)
    set_first_input(by_class, "KSampler", "cfg", cfg)
    set_first_input(by_class, "KSampler", "sampler_name", sampler)
    set_first_input(by_class, "KSampler", "scheduler", scheduler)
    set_first_input(by_class, "SaveImage", "filename_prefix", prefix)
    return workflow


def nodes_by_class(workflow: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for key in sorted(workflow, key=lambda value: int(value) if str(value).isdigit() else str(value)):
        node = workflow[key]
        if isinstance(node, dict):
            result.setdefault(str(node.get("class_type")), []).append(node)
    return result


def set_first_input(by_class: dict[str, list[dict[str, Any]]], class_type: str, key: str, value: Any) -> None:
    nodes = by_class.get(class_type, [])
    if not nodes:
        return
    inputs = nodes[0].setdefault("inputs", {})
    if isinstance(inputs, dict):
        inputs[key] = value


def set_indexed_prompt(by_class: dict[str, list[dict[str, Any]]], index: int, value: str) -> None:
    nodes = by_class.get("CLIPTextEncode", [])
    if index >= len(nodes):
        return
    inputs = nodes[index].setdefault("inputs", {})
    if isinstance(inputs, dict):
        inputs["text"] = value


def save_input(image: Image.Image, path: Path, comfy_input: Path, relative_name: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    comfy_target = comfy_input / relative_name
    comfy_target.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    image.save(comfy_target)
    return relative_name


def blue_ratio(image: Image.Image) -> float:
    rgb = np.asarray(image.convert("RGB"))
    result = cleanup_blue_lines(rgb, BlueCleanupSettings(despeckle_px=0, close_px=0))
    return float(result["line_mask"].mean())


def colorfulness(image: Image.Image) -> float:
    rgb = np.asarray(image.convert("RGB")).astype(np.float32)
    return float(np.mean(np.std(rgb, axis=(0, 1))))


def make_contact_sheet(rows: list[dict[str, Any]], output_path: Path, thumb_width: int) -> None:
    columns = ["source", "clean_line", "closed_line", "region_preview", "raw_color", "clean_color", "closed_color"]
    thumbs: list[list[Image.Image]] = []
    for row in rows:
        row_thumbs = []
        for key in columns:
            image = Image.open(row["paths"][key]).convert("RGB")
            height = max(1, round(image.height * thumb_width / image.width))
            row_thumbs.append(image.resize((thumb_width, height), Image.Resampling.LANCZOS))
        thumbs.append(row_thumbs)

    header_h = 30
    label_h = 34
    row_heights = [max(image.height for image in row) + label_h for row in thumbs]
    sheet = Image.new("RGB", (thumb_width * len(columns), header_h + sum(row_heights)), "white")
    draw = ImageDraw.Draw(sheet)
    for col, title in enumerate(columns):
        draw.text((col * thumb_width + 4, 8), title, fill=(0, 0, 0))
    y = header_h
    for row_data, row_images, row_h in zip(rows, thumbs, row_heights):
        draw.text((4, y + 6), f"{row_data['panel']} regions={row_data['region_count']}", fill=(0, 0, 0))
        for col, image in enumerate(row_images):
            sheet.paste(image, (col * thumb_width, y + label_h))
        y += row_h
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, quality=92)


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir
    variant_dir = output_dir / "inputs"
    generated_dir = output_dir / "generated"
    comfy_input = args.comfy_root / "input"
    base_workflow = load_workflow(args.workflow)
    client = ComfyClient(args.server, timeout=60)

    cleanup_settings = BlueCleanupSettings()
    autoclose_settings = AutoCloseSettings(max_endpoints=1200)
    region_settings = RegionSettings(min_area=256, max_regions=256, ignore_border_regions=True)

    rows: list[dict[str, Any]] = []
    for panel_index, panel_name in enumerate(args.panels):
        panel_path = args.panel_root / panel_name
        source = fit_for_generation(Image.open(panel_path).convert("RGB"), args.max_side)
        source_np = np.asarray(source)

        clean = cleanup_blue_lines(source_np, cleanup_settings)
        closed = autoclose_gaps(clean["line_mask"], autoclose_settings)
        regions = label_fill_regions(closed["closed_mask"], region_settings)

        stem = Path(panel_name).stem
        paths = {
            "source": variant_dir / f"{stem}_source.png",
            "clean_line": variant_dir / f"{stem}_clean_line.png",
            "closed_line": variant_dir / f"{stem}_closed_line.png",
            "region_preview": variant_dir / f"{stem}_region_preview.png",
        }
        rel_base = f"opentoonz_color_compare/{output_dir.name}"
        input_names = {
            "raw": save_input(source, paths["source"], comfy_input, f"{rel_base}/{stem}_raw.png"),
            "clean": save_input(Image.fromarray(clean["line_rgb"]), paths["clean_line"], comfy_input, f"{rel_base}/{stem}_clean.png"),
            "closed": save_input(Image.fromarray(mask_to_rgb(closed["closed_mask"])), paths["closed_line"], comfy_input, f"{rel_base}/{stem}_closed.png"),
        }
        Image.fromarray(labels_to_preview(regions["label_map"], closed["closed_mask"])).save(paths["region_preview"])

        color_paths: dict[str, Path] = {}
        seed = args.seed_base + panel_index * 100
        for variant in ("raw", "clean", "closed"):
            prefix = f"opentoonz_color_compare/{output_dir.name}/{stem}_{variant}"
            workflow = patch_controlnet_workflow(
                base_workflow,
                image_name=input_names[variant],
                checkpoint=args.checkpoint,
                controlnet=args.controlnet,
                width=source.width,
                height=source.height,
                seed=seed,
                steps=args.steps,
                cfg=args.cfg,
                strength=args.strength,
                sampler=args.sampler,
                scheduler=args.scheduler,
                prefix=prefix,
            )
            output_path = generated_dir / f"{stem}_{variant}.png"
            print(f"queue {stem} {variant} {source.width}x{source.height} seed={seed}", flush=True)
            client.run_workflow_image(workflow, output_path, timeout=900)
            color_paths[f"{variant}_color"] = output_path

        row = {
            "panel": panel_name,
            "width": source.width,
            "height": source.height,
            "line_ratio": round(float(clean["line_mask"].mean()), 6),
            "closure_segments": len(closed["segments"]),
            "region_count": len(regions["regions"]),
            "paths": {**{key: str(value) for key, value in paths.items()}, **{key: str(value) for key, value in color_paths.items()}},
            "generated_metrics": {
                key: {
                    "blue_ratio": round(blue_ratio(Image.open(path)), 6),
                    "colorfulness": round(colorfulness(Image.open(path)), 3),
                }
                for key, path in color_paths.items()
            },
        }
        rows.append(row)

    metrics = {
        "panel_root": str(args.panel_root),
        "output_dir": str(output_dir),
        "workflow": str(args.workflow),
        "settings": {
            "max_side": args.max_side,
            "steps": args.steps,
            "cfg": args.cfg,
            "strength": args.strength,
            "sampler": args.sampler,
            "scheduler": args.scheduler,
            "seed_base": args.seed_base,
            "checkpoint": args.checkpoint,
            "controlnet": args.controlnet,
        },
        "rows": rows,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    write_summary(metrics, output_dir / "summary.md")
    make_contact_sheet(rows, output_dir / "contact_sheet.jpg", args.thumb_width)
    print(f"wrote {output_dir}", flush=True)


def write_summary(metrics: dict[str, Any], path: Path) -> None:
    lines = [
        "# Panel Colorization Comparison",
        "",
        f"Panel root: `{metrics['panel_root']}`",
        f"Workflow: `{metrics['workflow']}`",
        "",
        "| panel | size | line ratio | closure segments | regions | raw blue | clean blue | closed blue |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in metrics["rows"]:
        generated = row["generated_metrics"]
        lines.append(
            f"| {row['panel']} | {row['width']}x{row['height']} | {row['line_ratio']} | "
            f"{row['closure_segments']} | {row['region_count']} | "
            f"{generated['raw_color']['blue_ratio']} | {generated['clean_color']['blue_ratio']} | "
            f"{generated['closed_color']['blue_ratio']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
