import csv
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple
from datasets import load_dataset
from PIL import Image

def map_labels(CLASSES: Dict[str, int]) -> Tuple[Dict[int, str], List[str], Set[int]]:
    """
    Build stable mappings and class order from the given CLASSES dict (name -> Food101 id).
    Returns:
      id_to_name: {int_id: food101_name}
      target_names: list of class names in the order of CLASSES keys
      target_ids: set of selected ids
    """
    label_names = load_dataset("ethz/food101", split="train").features["label"].names
    id_to_name = {i: n for i, n in enumerate(label_names)}
    # keep order of CLASSES keys
    target_pairs = [(id_to_name[food101_id], food101_id) for _, food101_id in CLASSES.items()]
    target_names = [n for n, _ in target_pairs]
    target_ids = {i for _, i in target_pairs}
    return id_to_name, target_names, target_ids

def ensure_dirs(root: Path, target_names: Iterable[str], SPLIT_MAP: Dict[str, str]) -> None:
    for split_food101, split_yolo in SPLIT_MAP.items():
        for cls in target_names:
            (root / split_yolo / cls).mkdir(parents=True, exist_ok=True)

def build_split(
    split_food101: str,
    out_root: Path,
    target_names: Iterable[str],
    target_ids: Set[int],
    id_to_name: Dict[int, str],
    N_SPLIT: Dict[str, int],
    MAKE_CSV: bool,
    SPLIT_MAP: Dict[str, str],
) -> None:
    """
    Download images for the given Food-101 split and save in YOLO classification layout:
      out_root/<train|val>/<class_name>/image.jpg
    Optionally writes a labels.csv at split root (filename,label).
    """
    split_yolo = SPLIT_MAP[split_food101]
    split_dir = out_root / split_yolo
    split_dir.mkdir(parents=True, exist_ok=True)

    saved_counts = {cls: 0 for cls in target_names}
    target_per_class = N_SPLIT[split_food101]

    ds = load_dataset("ethz/food101", split=split_food101)
    rows = []  # optional CSV

    for idx, ex in enumerate(ds):
        lid = ex["label"]
        if lid not in target_ids:
            continue

        cls_name = id_to_name[lid]
        if saved_counts[cls_name] >= target_per_class:
            continue

        fname = f"{idx:06d}_{lid:02d}_{cls_name}.jpg"
        out_path = split_dir / cls_name / fname
        ex["image"].save(out_path)
        saved_counts[cls_name] += 1
        if MAKE_CSV:
            rows.append([f"{cls_name}/{fname}", cls_name])

        if all(saved_counts[c] >= target_per_class for c in saved_counts):
            break

    if MAKE_CSV:
        with open(split_dir / "labels.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["filename", "label"])
            w.writerows(rows)

    print(f"[{split_food101}] saved counts:", saved_counts)

def write_dataset_yaml(root: Path, target_names: Iterable[str]) -> Path:
    """
    Create dataset.yaml for YOLO classification training.
    Returns the path to dataset.yaml.
    """
    names_block = "\n".join([f"  - {n}" for n in target_names])
    yaml_text = f"""# YOLO classification dataset generated from Food-101
path: {root.resolve()}
train: train
val: val
names:
{names_block}
"""
    p = root / "dataset.yaml"
    p.write_text(yaml_text)
    print(f"dataset.yaml written to: {p}")
    print("Class order:", list(target_names))
    return p

def prepare_dataset(
    CLASSES: Dict[str, int],
    N_SPLIT: Dict[str, int],
    OUT_ROOT: Path,
    MAKE_CSV: bool,
    SPLIT_MAP: Dict[str, str],
) -> Path:
    """
    Full preparation pipeline. Returns absolute path to dataset.yaml.
    """
    id_to_name, target_names, target_ids = map_labels(CLASSES)
    ensure_dirs(OUT_ROOT, target_names, SPLIT_MAP)
    for split in ["train", "validation"]:
        build_split(
            split_food101=split,
            out_root=OUT_ROOT,
            target_names=target_names,
            target_ids=target_ids,
            id_to_name=id_to_name,
            N_SPLIT=N_SPLIT,
            MAKE_CSV=MAKE_CSV,
            SPLIT_MAP=SPLIT_MAP,
        )
    return write_dataset_yaml(OUT_ROOT, target_names)

def resize_max_side(img: Image.Image, max_side: int = 512) -> Image.Image:
    """
    Resize an image so that its longest side is <= max_side, preserving aspect ratio.
    """
    w, h = img.size
    if max(w, h) <= max_side:
        return img
    scale = max_side / float(max(w, h))
    new = (int(w * scale), int(h * scale))
    return img.resize(new, Image.LANCZOS)

def resize_folder(src: Path, dst: Path, max_side: int = 512,
                  exts={".jpg", ".jpeg", ".png", ".bmp", ".webp"}) -> None:
    """
    Resize all images in `src` (recursively) and save to `dst`, preserving subfolder structure.
    Only resizes if the largest side exceeds `max_side`.
    """
    src, dst = Path(src), Path(dst)
    for f in src.rglob("*"):
        if f.suffix.lower() in exts:
            out = dst / f.relative_to(src)
            out.parent.mkdir(parents=True, exist_ok=True)
            try:
                img = Image.open(f)
                resize_max_side(img, max_side).save(out, quality=95)
                print("📏", out)
            except Exception as e:
                print(f"❌ Failed to process {f}: {e}")
