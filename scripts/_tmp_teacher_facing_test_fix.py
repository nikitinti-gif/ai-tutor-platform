from pathlib import Path
p = Path('scripts/_tmp_teacher_facing_diagnostics.py')
text = p.read_text(encoding='utf-8')
text = text.replace('    summary = diagnostic_summary(attempt)\n', '    summary = ege_exam_service.diagnostic_summary(attempt)\n')
p.write_text(text, encoding='utf-8')
