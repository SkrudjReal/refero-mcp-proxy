#!/usr/bin/env python3
"""
Unpack script for Refero dataset archives downloaded from Google Drive.
Safely extracts modular archives into the exact layout expected by refero-mcp-proxy,
with Zip Slip protection and structure validation.
"""

import argparse
import os
import shutil
import sys
import time
import zipfile
from pathlib import Path

DEFAULT_ARCHIVES = [
    "refero_styles_design_systems.zip",
    "refero_flows.zip",
    "refero_site_assets_and_pages.zip",
    "refero_fleet_images_00_3f.zip",
    "refero_fleet_images_40_7f.zip",
    "refero_fleet_images_80_bf.zip",
    "refero_fleet_images_c0_ff.zip",
    "refero_web_screens.zip",
    "refero_ios_screens.zip",
]


def find_source_dir(candidate_dirs):
    for d in candidate_dirs:
        if d and d.is_dir():
            zips = list(d.glob("refero_*.zip"))
            if zips:
                return d, zips
    return None, []


def _safe_extract_member(zf: zipfile.ZipFile, info: zipfile.ZipInfo, dest_dir: Path) -> None:
    """Extracts a single zip entry while blocking Zip Slip path traversal."""
    dest_resolved = dest_dir.resolve()
    target = (dest_resolved / info.filename).resolve()
    if dest_resolved != target and dest_resolved not in target.parents:
        raise ValueError(f"Unsafe zip member path rejected: {info.filename}")
    zf.extract(info, dest_resolved)


def extract_archive(zip_path: Path, dest_dir: Path):
    print(f"\n[UNPACK] {zip_path.name} ({zip_path.stat().st_size / (1024 * 1024):.1f} MB)...", flush=True)
    start_t = time.time()
    dest_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        infolist = zf.infolist()
        total_files = len(infolist)
        extracted = 0
        last_print = time.time()

        for info in infolist:
            _safe_extract_member(zf, info, dest_dir)
            extracted += 1
            if time.time() - last_print > 1.5 or extracted == total_files:
                pct = (extracted / max(total_files, 1)) * 100
                print(f"   [{pct:5.1f}%] {extracted:,}/{total_files:,} entries...", end="\r", flush=True)
                last_print = time.time()

    elapsed = time.time() - start_t
    print(f"\n   [OK] Extracted {total_files:,} entries in {elapsed:.1f}s.", flush=True)


def copy_catalogs_if_present(src_dir: Path, dest_dir: Path):
    """Copies _catalogs directory if downloaded alongside the zip archives."""
    src_cat = src_dir / "_catalogs"
    if src_cat.is_dir():
        dst_cat = dest_dir / "_catalogs"
        dst_cat.mkdir(parents=True, exist_ok=True)
        copied = 0
        for item in src_cat.iterdir():
            if item.is_file():
                shutil.copy2(item, dst_cat / item.name)
                copied += 1
        if copied:
            print(f"\n[OK] Copied {copied} catalog files into {dst_cat}", flush=True)


def verify_dataset(dest_dir: Path):
    print("\nVerifying dataset structure in:", dest_dir, flush=True)
    checks = [
        ("Fleet Images (CAS)", dest_dir / "fleet" / "images"),
        ("UX Journey Flows", dest_dir / "fleet" / "flows"),
        ("Design Systems", dest_dir / "styles"),
    ]
    all_ok = True
    for label, p in checks:
        if p.exists() and any(p.iterdir()):
            count = sum(1 for _ in p.rglob("*") if _.is_file())
            print(f"  [OK]      {label:20}: {count:,} files found ({p})")
        else:
            print(f"  [MISSING] {label:20}: Not found or empty at {p}")
            all_ok = False

    return all_ok


def main():
    parser = argparse.ArgumentParser(description="Extract Refero dataset archives for refero-mcp-proxy.")
    parser.add_argument("--src", type=str, default=None, help="Directory containing downloaded refero_*.zip files")
    parser.add_argument("--dest", type=str, default=None, help="Target destination directory (auto-detected by server)")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent

    # Determine source directory
    if args.src:
        src_dir = Path(args.src).resolve()
        zips = list(src_dir.glob("refero_*.zip")) if src_dir.is_dir() else []
    else:
        candidates = [
            Path.cwd(),
            repo_root / "downloads",
            repo_root.parent / "downloads",
            Path.home() / "Downloads",
            Path.home() / "Downloads" / "Refero",
        ]
        src_dir, zips = find_source_dir(candidates)

    if not src_dir or not zips:
        print("[ERROR] No refero_*.zip archives found!", file=sys.stderr)
        print("Download the archives from Google Drive:")
        print("  https://drive.google.com/drive/folders/1w9kEhGqLZ70K0Sui2W5IEQnTAaSxAWLT")
        print("Then run: python unpack_dataset.py --src <path_to_zips>")
        sys.exit(1)

    # Determine destination directory (all defaults are auto-detected by refero_mcp_server.py)
    if args.dest:
        dest_dir = Path(args.dest).resolve()
    else:
        sibling_outputs = (repo_root.parent / "outputs" / "refero-full-data").resolve()
        if sibling_outputs.parent.exists():
            dest_dir = sibling_outputs
        else:
            dest_dir = (repo_root / "data" / "refero-full-data").resolve()

    print("=" * 65)
    print(" Refero Dataset Unpack Tool")
    print("=" * 65)
    print(f"Source Directory:      {src_dir}")
    print(f"Found Archives:        {len(zips)} zip files")
    print(f"Destination Directory: {dest_dir}")
    print("=" * 65)

    # Extract smaller packages first, heavy image shards last
    def archive_sort_key(p: Path):
        name = p.name.lower()
        if "catalog" in name or "site" in name or "flow" in name or "style" in name:
            return (0, name)
        return (1, name)

    for zp in sorted(zips, key=archive_sort_key):
        extract_archive(zp, dest_dir)

    copy_catalogs_if_present(src_dir, dest_dir)

    print("\n" + "=" * 65)
    all_ok = verify_dataset(dest_dir)
    print("=" * 65)

    if all_ok:
        print("\nDataset unpacked and verified.")
    else:
        print("\n[NOTE] Partial dataset unpacked (missing optional packages can be added later).")
    print(f'To force offline mode with this path:')
    print(f'  export REFERO_DATA_DIR="{dest_dir}"')
    print("  export REFERO_OFFLINE=1")


if __name__ == "__main__":
    main()
