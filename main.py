"""
main.py
───────
Entrypoint for Version 2 Parser.
Executes document parsing for FRDs and Manual Test Cases,
generating enriched structured JSON outputs.
"""

import sys
import argparse
from pathlib import Path
from agents.doc_parser import parse_documents
from core.constants import (
    DIR_OUTPUT,
    DIR_MODULES_INPUT
)

def main():
    parser = argparse.ArgumentParser(description="Baxter Version 2 Parser")
    parser.add_argument(
        "--modules-dir",
        type=str,
        default=str(DIR_MODULES_INPUT),
        help="Path to the directory containing module subfolders",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=str(DIR_OUTPUT),
        help="Output directory for generated master JSON",
    )
    parser.add_argument(
        "--project",
        type=str,
        default="ShopSphere",
        help="Optional project name",
    )
    parser.add_argument(
        "--skip-types",
        nargs="*",
        default=[],
        help="Test case types to skip (e.g. Non-Functional Performance)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print(" Baxter Version 2 - Document Parser Engine (Modules) ")
    print("=" * 60)

    output_files = parse_documents(
        modules_dir=args.modules_dir,
        out_dir=args.out,
        project=args.project,
        skip_types=args.skip_types,
    )

    if output_files:
        print("\n[DONE] Successfully generated individual module JSON files:")
        for f in output_files:
            print(f"  - {f}")
        print()
    else:
        print(f"\n[FAILED] Document parsing did not complete.\n")

if __name__ == "__main__":
    main()
