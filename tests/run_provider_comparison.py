import json
import os
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
from src.ai_engine.provider_clients import SUPPORTED_TEXT_PROVIDERS


def selected_providers() -> list[str]:
    raw = os.getenv(
        "EVALUATION_PROVIDERS",
        ",".join(SUPPORTED_TEXT_PROVIDERS),
    )
    providers = [item.strip().lower() for item in raw.split(",")]
    return [item for item in providers if item]


def main() -> None:
    summaries = []

    for provider_name in selected_providers():
        matched = 0
        failed = 0
        mismatches = []
        print(f"\n=== {provider_name.upper()} ===")

        for index, case in enumerate(SYNTHETIC_CASES, start=1):
            print(f"[{index}/{len(SYNTHETIC_CASES)}] {case['id']}")
            try:
                result = evaluate_synthetic_case(
                    case,
                    provider_name=provider_name,
                )
            except Exception as error:
                failed += 1
                mismatches.append(
                    f"{case['id']}: API {type(error).__name__}"
                )
                print(f"API ERROR: {type(error).__name__}: {error}")
            else:
                matched += int(result["match"])
                if not result["match"]:
                    mismatches.append(
                        f"{case['id']}: {result['expected']} -> "
                        f"{result['actual']} ({result['confidence']:.2f})"
                    )
                print(json.dumps(result, ensure_ascii=False))
            time.sleep(1)

        summaries.append(
            {
                "provider": provider_name,
                "cases": len(SYNTHETIC_CASES),
                "matched": matched,
                "api_errors": failed,
                "mismatches": mismatches,
            }
        )

    print("\n=== COMPARISON SUMMARY ===")
    print(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
