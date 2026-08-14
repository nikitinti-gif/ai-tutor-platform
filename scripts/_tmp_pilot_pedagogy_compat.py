from pathlib import Path

p = Path('src/ai_engine/diagnostics.py')
text = p.read_text(encoding='utf-8')
needle = '}\n\n\ndef _gap_for_operation(task_number: int, operation_index: int) -> dict | None:\n    return PILOT_GAPS.get((task_number, operation_index))\n'
alias = '}\n\n# Temporary public alias retained for existing tests/callers while the generic\n# pilot gap registry becomes the single source of truth.\nTASK14_GAPS = {operation: gap for (task, operation), gap in PILOT_GAPS.items() if task == 14}\n\n\ndef _gap_for_operation(task_number: int, operation_index: int) -> dict | None:\n    return PILOT_GAPS.get((task_number, operation_index))\n'
if needle not in text:
    raise SystemExit('generic pilot gap block not found')
text = text.replace(needle, alias, 1)
p.write_text(text, encoding='utf-8')
