#!/usr/bin/env python3
"""Run the CHARLS preparation and GBD–CHARLS comparison."""

import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
CODE = ROOT / "analysis" / "code"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data" / "raw", help="Raw input root (see data/raw/README.md).")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results", help="Separate directory for all generated outputs.")
    parser.add_argument("--panel", type=Path, help="Use an existing processed panel and skip raw CHARLS preparation.")
    parser.add_argument("--prepare-only", action="store_true", help="Build the CHARLS panel without fitting analyses.")
    parser.add_argument("--with-charls-export", action="store_true", help="Also export CHARLS microdata summaries and sample flow.")
    args = parser.parse_args()
    if args.panel and (args.prepare_only or args.with_charls_export):
        parser.error("--panel cannot be combined with --prepare-only or --with-charls-export; exports require panel-build metadata.")
    os.environ["CHINAMDD_DATA_DIR"] = str(args.data_dir.expanduser().resolve())
    os.environ["CHINAMDD_OUTPUT_DIR"] = str(args.output_dir.expanduser().resolve())
    os.environ.pop("CHINAMDD_PANEL", None)
    if args.panel:
        os.environ["CHINAMDD_PANEL"] = str(args.panel.expanduser().resolve())
    sys.path.insert(0, str(CODE))
    try:
        from settings import DATA_DIR, PANEL, CROSSWALK, charls_files, require_files
        inputs = [PANEL, CROSSWALK] if args.panel else charls_files(DATA_DIR / "CHARLS")
        if not args.prepare_only:
            inputs += [DATA_DIR / "GBD2023" / "China_mental_disorders_GBD2023_1990_2023.csv",
                       DATA_DIR / "WPP2024" / "WPP2024_PopulationByAge5GroupSex_Medium.csv.gz"]
        require_files(inputs)
        scripts = [] if args.panel else ["00_build_charls_panel.py"]
        if not args.prepare_only:
            scripts.append("01_run_analysis.py")
        if args.with_charls_export:
            scripts += ["03_export_charls_folder.py", "04_charls_flow_diagram.py"]
        for script in scripts:
            subprocess.run([sys.executable, str(CODE / script)], cwd=ROOT, check=True)
    except (ValueError, FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
