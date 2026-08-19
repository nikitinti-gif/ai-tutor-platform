# КЕГЭ 2026 — честная матрица исполняемого обучения

Дата аудита: 2026-08-19. **READY** означает диагностику, исполняемую лестницу,
детерминированную проверку, независимый перенос и обновление глобального mastery.
Baseline: **READY 1 / PARTIAL 2 / PENDING 24** (№14 / №5,27 / остальные).
После спринта: **READY 3 / PARTIAL 10 / PENDING 14**. В карте 35 уникальных
глобальных skills; mastery имеет ключ `(student_id, skill_id)`, а номер задания
остаётся контекстом evidence.

| № | mode | global skills (кратко) | diagnosis | learning / practice / exam-transfer | validator | attachment | status |
|---:|---|---|---|---|---|---|---|
|1|reasoning|graphs.adjacency_mapping|есть|нет / нет / нет|diagnostic exact|—|PENDING|
|2|reasoning|logic.operations; logic.truth_tables|есть|operations: 6 шагов / transfer / exam_transfer|exact Python|—|PARTIAL|
|3|application|data.relational_tables|есть|нет исполняемой работы с таблицей|diagnostic|1_3.ods|PENDING|
|4|reasoning|coding.prefix_code|есть|нет / нет / нет|diagnostic|—|PENDING|
|5|reasoning|7 skills, включая base_conversion и tracing|есть|2 shared-модуля + legacy remediation; не все skills|Python|—|PARTIAL|
|6|reasoning|algorithms.tracing|есть|6 шагов / независимый transfer / exam_transfer|exact Python|—|READY|
|7|reasoning|units_conversion; audio_volume|есть|units готов; audio нет|exact Python|—|PARTIAL|
|8|reasoning|number_systems.base_conversion|есть|6 шагов / независимый transfer / exam_transfer|exact Python|—|READY|
|9|application|spreadsheets; logic.operations|есть|logic готов; spreadsheet workflow нет|mixed|1_9.ods|PARTIAL|
|10|application|programming.strings|есть|нет работы с документом|diagnostic|1_10.odt|PENDING|
|11|reasoning|units_conversion; identifier_volume|есть|units готов; identifier нет|exact Python|—|PARTIAL|
|12|reasoning|tracing; base_conversion; binary_arithmetic|есть|2 shared-модуля; arithmetic нет|exact Python|—|PARTIAL|
|13|reasoning|base_conversion; binary_arithmetic; ip_addressing|есть|base готов; остальные нет|exact Python|—|PARTIAL|
|14|reasoning|5 global number-system skills|есть|8 шагов + 2 bank evidences + exam transfer|Python solvers|—|READY|
|15|reasoning|logic.operations; set_intervals|есть|logic готов; intervals нет|exact Python|—|PARTIAL|
|16|reasoning|algorithms.recursion|есть|нет / нет / нет|diagnostic|—|PENDING|
|17|programming|programming.sequences|есть|checkpoint only; полного курса нет|diagnostic|1_17.txt|PENDING|
|18|application|spreadsheets; dynamic_programming|есть|нет полноценной работы с ODS|diagnostic|1_18.ods|PENDING|
|19|reasoning|algorithms.game_strategy|есть|нет / нет / нет|diagnostic|—|PENDING|
|20|reasoning|algorithms.game_strategy|есть|нет / нет / нет|diagnostic|—|PENDING|
|21|reasoning|algorithms.game_strategy|есть|нет / нет / нет|diagnostic|—|PENDING|
|22|application|critical_path; spreadsheets|есть|нет полноценной работы с ODS|diagnostic|1_22.ods|PENDING|
|23|reasoning|recursion; dynamic_programming|есть|нет / нет / нет|diagnostic|—|PENDING|
|24|programming|programming.strings|есть|checkpoint only; полного курса нет|diagnostic|1_24.txt|PENDING|
|25|programming|strings; masks|есть|нет code-structure курса|diagnostic|—|PENDING|
|26|programming|sequences; grouping|есть|нет code-structure курса|diagnostic|1_26.txt|PENDING|
|27|programming|5 cluster skills|есть|checkpoint remediation, но нет полного safe programming path|Python checkpoints|1_27_A/B.txt|PARTIAL|

## Реализованные и переиспользуемые модули

* `number_systems.base_conversion`: №5, 8, 12, 13, 14.
* `logic.operations`: №2, 9, 15.
* `algorithms.tracing`: №5, 6, 12.
* `information.units_conversion`: №7, 11.
* Reference-модуль `number_systems.large_number_digits`: №14.
* Curated Task Bank пока только для №14: три локально решаемых элемента, два
  независимых успеха обязательны перед mastery.

Остальные skills оставлены PENDING/PARTIAL намеренно: для application нужны
реальные attachments и операции приложения, а для programming — безопасные
checkpoint/code-structure проверки. Подмена их арифметическим ответом ухудшила
бы педагогическую валидность.

## Что Tutor сделает завтра после ошибки №1–27

Для №6 и №8 — запустит полный курс skill-first. Для №14 — полный reference path
и Task Bank. Для №2,5,7,9,11,12,13,15 — обучит готовой подтверждённой части,
но честно не объявит весь номер освоенным. Для №27 — проведёт существующую
checkpoint-диагностику и partial remediation. Для №1,3,4,10,16–26 (кроме 27)
— сохранит evidence, покажет global gap и курс со статусом «модуль готовится»;
mastery не сфабрикует.

## Manual Telegram product gate

1. Запустить bot process штатной командой окружения и открыть бот.
2. Нажать `/start`, затем кнопку `📝 Пробный КЕГЭ 2026` (или команду `/ege2026`).
3. Ответить на №1–27; для пропуска нажимать `⏭ Пропустить`.
4. После результата пройти диагностические probes.
5. Нажать `🧬 Моя карта знаний`: проверить красные/жёлтые/зелёные/синие узлы.
6. Нажать `🎓 Начать обучение`.
7. Пройти шесть шагов первого READY skill. Для проверки ladder четыре раза
   отправить неверный ответ: Tutor вернёт к более простому checkpoint.
8. Завершить transfer и exam_transfer: карта обновится, затем Tutor автоматически
   откроет следующий доступный global skill.
9. Перезапустить bot между любыми двумя ответами и снова нажать
   `🎓 Начать обучение`: сохранённый шаг должен продолжиться.
