#!/usr/bin/env python3
"""Package the NX809J AnyKernel zip while preserving Unix executable modes.

This intentionally reuses the upstream AnyKernel zip as the metadata template.
Windows zip tools often drop Unix permissions, which can make update-binary or
AnyKernel tools non-executable for flash apps.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import stat
import zipfile
from pathlib import Path


EXECUTABLES = {
    "Image",
    "anykernel.sh",
    "META-INF/com/google/android/update-binary",
    "tools/ak3-core.sh",
    "tools/busybox",
    "tools/fec",
    "tools/httools_static",
    "tools/lptools_static",
    "tools/magiskboot",
    "tools/magiskpolicy",
    "tools/snapshotupdater_static",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def make_info(name: str, source: zipfile.ZipInfo | None, executable: bool) -> zipfile.ZipInfo:
    if source is not None:
        info = zipfile.ZipInfo(name, date_time=source.date_time)
        info.comment = source.comment
        info.extra = source.extra
        info.internal_attr = source.internal_attr
    else:
        info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.create_system = 3
    if name.endswith("/"):
        mode = stat.S_IFDIR | 0o755
    else:
        mode = stat.S_IFREG | (0o755 if executable else 0o644)
    info.external_attr = (mode & 0xFFFF) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template-zip", required=True, type=Path)
    parser.add_argument("--ak3-tree", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    replacements = {
        "anykernel.sh": args.ak3_tree / "anykernel.sh",
        "Image": args.ak3_tree / "Image",
        "OP15_OOS16.txt": args.ak3_tree / "OP15_OOS16.txt",
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    with zipfile.ZipFile(args.template_zip, "r") as zin, zipfile.ZipFile(
        args.output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as zout:
        for source_info in zin.infolist():
            name = source_info.filename.replace("\\", "/")
            seen.add(name)
            data = replacements[name].read_bytes() if name in replacements else zin.read(source_info.filename)
            zout.writestr(make_info(name, source_info, name in EXECUTABLES or name.startswith("tools/")), data)

        for root, _dirs, files in os.walk(args.ak3_tree):
            for filename in sorted(files):
                full = Path(root) / filename
                rel = full.relative_to(args.ak3_tree).as_posix()
                if rel in seen:
                    continue
                zout.writestr(make_info(rel, None, rel in EXECUTABLES or rel.startswith("tools/")), full.read_bytes())

    print(f"zip={args.output}")
    print(f"zip_size={args.output.stat().st_size}")
    print(f"zip_sha256={sha256(args.output)}")
    print(f"image_sha256={sha256(args.ak3_tree / 'Image')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
