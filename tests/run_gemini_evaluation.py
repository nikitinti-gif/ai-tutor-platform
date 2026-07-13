import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ai_engine.evaluation import (
    SYNTHETIC_CASES,
    evaluate_synthetic_case,
)


def main():
    matched = 0
    failed = 0

    for index, case in enumerate(SYNTHETIC_CASES, start=1):
        print(f"\n[{index}/{len(SYNTHETIC_CASES)}] {case['id']}")

        try:
            evaluation = evaluate_synthetic_case(case)
        except Exception as error:
            failed += 1
            print(f"API ERROR: {type(error).__name__}: {error}")
            time.sleep(2)
            continue

        matched += int(evaluation["match"])
        print(
            json.dumps(
                evaluation,
                ensure_ascii=False,
                indent=2,
            )
        )
        time.sleep(2)

    print("\n=== SUMMARY ===")
    print(f"Cases: {len(SYNTHETIC_CASES)}")
    print(f"Matched expected status: {matched}")
    print(f"API errors: {failed}")


if __name__ == "__main__":
    main()
