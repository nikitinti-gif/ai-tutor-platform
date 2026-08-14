from pathlib import Path

p = Path('tests/test_ege_diagnostics.py')
text = p.read_text(encoding='utf-8')
text = text.replace('for correct_answer in ("2", "да", "4"):', 'for correct_answer in ("2", "да", "1205"):')
p.write_text(text, encoding='utf-8')

p = Path('tests/test_probe_quality_gate.py')
text = p.read_text(encoding='utf-8')
text = text.replace('assert probe["expected_answers"] == ("1431",)', 'assert probe["expected_answers"] == ("1314",)')
text = text.replace('        assert "значимые элементы" not in prompt.lower()\n', '        assert "Педагогическая семья:" in prompt\n        assert "Пример хорошего стиля:" in prompt\n        assert "remainder_count" not in prompt\n')
p.write_text(text, encoding='utf-8')
