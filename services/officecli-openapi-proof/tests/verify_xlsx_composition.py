"""Compare private source-*.xlsx files with a composed workbook; prints counts only."""
import argparse
import json
from pathlib import Path
from officecli_openapi_proof.xlsx_verification import verify

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("sources", type=Path)
    parser.add_argument("result", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(sorted(args.sources.glob("source-*.xlsx")), args.result)))
