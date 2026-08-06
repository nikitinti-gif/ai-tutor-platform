"""Session helpers for the 27-task KЕГЭ open variant flow."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from src.ai_engine.ege_open_variant_2026 import OPEN_VARIANT_2026, EgeTask, OFFICIAL_FILES_URL, OFFICIAL_PDF_URL
from src.ai_engine.verification_engine import VerificationResult, verify_answer

@dataclass(slots=True)
class ExamAttempt:
    current_task:int=1
    answers:dict[int,str]=field(default_factory=dict)
    results:dict[int,bool]=field(default_factory=dict)
    skipped:list[int]=field(default_factory=list)
    @property
    def finished(self): return self.current_task>27
    @property
    def correct_count(self): return sum(self.results.values())
    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls,data):
        data=data or {}
        return cls(int(data.get('current_task',1)),{int(k):str(v) for k,v in data.get('answers',{}).items()},{int(k):bool(v) for k,v in data.get('results',{}).items()},[int(x) for x in data.get('skipped',[])])

def get_task(number:int)->EgeTask: return OPEN_VARIANT_2026[number]

def render_task(number:int)->str:
    t=get_task(number)
    links=f"\n\n📄 Полный PDF (стр. {t.pdf_page}): {OFFICIAL_PDF_URL}"
    if t.attachment_required:
        links += f"\n📎 Файлы варианта: {OFFICIAL_FILES_URL}"
    return (f"📝 КЕГЭ 2026 · задание {number}/27\nТема: {t.title}\n\n{t.statement}\n\n"
            f"✍️ {t.prompt}{links}\n\nКоманды: /skip_ege — пропустить, /finish_ege — завершить, /cancel_ege — отменить.")

def submit_answer(attempt:ExamAttempt,answer:str)->VerificationResult:
    if attempt.finished: raise ValueError('Экзамен уже завершён.')
    n=attempt.current_task; r=verify_answer(n,answer)
    attempt.answers[n]=answer; attempt.results[n]=r.is_correct; attempt.current_task+=1
    return r

def skip_task(attempt:ExamAttempt)->int:
    if attempt.finished: raise ValueError('Экзамен уже завершён.')
    n=attempt.current_task
    if n not in attempt.skipped: attempt.skipped.append(n)
    attempt.results[n]=False; attempt.current_task+=1
    return n

def render_summary(attempt:ExamAttempt)->str:
    checked=sorted(attempt.results)
    wrong=[str(n) for n in checked if not attempt.results.get(n,False) and n not in attempt.skipped]
    skipped=', '.join(map(str,attempt.skipped)) if attempt.skipped else 'нет'
    return ("🏁 Вариант завершён\n\n"f"Верных: {attempt.correct_count}\nПроверено: {len(checked)} из 27\n"
            f"Неверные: {', '.join(wrong) if wrong else 'нет'}\nПропущенные: {skipped}\n\nAI и Vision не использовались.")
