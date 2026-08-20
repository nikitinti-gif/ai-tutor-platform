# КЕГЭ 2026 — матрица исполняемого обучения

Дата аудита: 2026-08-19. Baseline после PR #9: **READY 3 / PARTIAL 10 /
PENDING 14**. После coverage sprint: **READY 8 / PARTIAL 14 / PENDING 5**.
READY означает, что *каждый* обязательный global skill номера имеет
детерминированный module, transfer и независимый exam_transfer. Для file-based
задач module без проверки attachment не повышает весь номер до READY.

|task|mode|global skills|diagnostic|learning|practice|exam_transfer|validator|attachment|status|blocking_missing_skills|
|---:|---|---|---|---|---|---|---|---|---|---|
|1|reasoning|graphs.adjacency_mapping|yes|none|none|none|exact|—|PENDING|graphs.adjacency_mapping|
|2|reasoning|logic.operations; logic.truth_tables|yes|operations|2 deterministic|yes|Python exact|—|PARTIAL|logic.truth_tables|
|3|application|data.relational_tables|yes|none|none|none|diagnostic|1_3.ods|PENDING|data.relational_tables|
|4|reasoning|coding.prefix_code|yes|none|none|none|diagnostic|—|PENDING|coding.prefix_code|
|5|reasoning|7 atomic skills|yes|shared base/tracing|shared transfer|partial|Python|—|PARTIAL|4 legacy atomics; binary_arithmetic|
|6|reasoning|algorithms.tracing|yes|6 checkpoints|transfer + exam|yes|exact|—|READY|—|
|7|reasoning|units_conversion; audio_volume|yes|units|2 deterministic|partial|exact|—|PARTIAL|information.audio_volume|
|8|reasoning|number_systems.base_conversion|yes|6 checkpoints|transfer + exam|yes|exact|—|READY|—|
|9|application|spreadsheets; logic.operations|yes|logic only|logic transfer|partial|mixed|1_9.ods|PARTIAL|data.spreadsheets|
|10|application|programming.strings|yes|structured safe module|2 deterministic|yes|exact snippets|1_10.odt|PARTIAL|attachment evidence|
|11|reasoning|units_conversion; identifier_volume|yes|units|2 deterministic|partial|exact|—|PARTIAL|information.identifier_volume|
|12|reasoning|tracing; base_conversion; binary_arithmetic|yes|2 shared modules|shared transfer|partial|exact|—|PARTIAL|binary_arithmetic|
|13|reasoning|base_conversion; binary_arithmetic; ip_addressing|yes|base|shared transfer|partial|exact|—|PARTIAL|binary_arithmetic; ip_addressing|
|14|reasoning|5 number-system skills|yes|reference 8-step path|Task Bank ≥2|yes|Python solvers|—|READY|—|
|15|reasoning|logic.operations; set_intervals|yes|logic|2 deterministic|partial|exact|—|PARTIAL|logic.set_intervals|
|16|reasoning|algorithms.recursion|yes|6 checkpoints|transfer + exam|yes|exact|—|READY|—|
|17|programming|programming.sequences|yes|safe structured module|2 deterministic|yes|exact snippets|1_17.txt|PARTIAL|attachment evidence|
|18|application|spreadsheets; dynamic_programming|yes|DP exists but blocked by spreadsheet|DP transfer|partial|mixed|1_18.ods|PENDING|data.spreadsheets workflow|
|19|reasoning|algorithms.game_strategy|yes|one shared module|transfer + exam|yes|exact|—|READY|—|
|20|reasoning|algorithms.game_strategy|yes|same global module|transfer + exam|yes|exact|—|READY|—|
|21|reasoning|algorithms.game_strategy|yes|same global module|transfer + exam|yes|exact|—|READY|—|
|22|application|critical_path; spreadsheets|yes|none|none|none|diagnostic|1_22.ods|PENDING|both application workflows|
|23|reasoning|recursion; dynamic_programming|yes|both deterministic|2 per skill|yes|exact|—|PARTIAL|DP prerequisite spreadsheet|
|24|programming|programming.strings|yes|safe structured module|2 deterministic|yes|exact snippets|1_24.txt|PARTIAL|attachment evidence|
|25|programming|strings; masks|yes|two safe modules|2 per skill|yes|exact snippets|—|READY|—|
|26|programming|sequences; grouping|yes|two safe modules|2 per skill|yes|exact snippets|1_26.txt|PARTIAL|attachment evidence|
|27|programming|5 cluster skills|yes|checkpoint pipeline|controlled probes|partial|Python checkpoints|1_27_A/B.txt|PARTIAL|full safe programming path|

## Product and pedagogy gates

* There are **35 unique global skills**. New executable global modules:
  `algorithms.recursion`, `algorithms.dynamic_programming`,
  `algorithms.game_strategy`, `programming.strings`, `programming.sequences`,
  `programming.masks`, and `programming.grouping`.
* №19–21 deliberately share one game module. №16/23 share recursion;
  №10/24/25 share strings; №17/26 share sequences.
* Programming uses curated snippets, expected outputs and algorithm checkpoints;
  arbitrary learner code is never passed to `subprocess`.
* A generated course deduplicates skills, inserts unmet prerequisite gaps, skips
  mastered nodes, reports estimates as coarse 6 steps / about 15 minutes, and
  can skip a PENDING item to find an unrelated available READY item.
* Mastery requires all six levels, a first-attempt independent `transfer`, a
  first-attempt independent `exam_transfer`, and exact matching `skill_id`.
  Hinted-only success cannot master a node.
* Atomicity audit keeps legacy IDs. `base_conversion` is reusable capability;
  decimal/binary and remainder are documented children; digit-property and
  preserve-digit-count retain independent evidence. Parent mastery never
  propagates automatically to children.

## Simulated students and E2E

Personas A–I cover strong, number systems, logic, recursion/DP, games,
spreadsheet/application, strings, sequences, and mixed gaps. Regression tests
exercise prerequisite insertion, distinct first modules, deduplication of
№19–21, complete mastery, retry fallback, and rejection of hinted/cross-skill
evidence. Restart remains serialization-based: `LearningPath.current_index`,
history, attempt count and status survive round-trip between every stage.

## Точный manual Telegram test

1. Запустить bot штатной командой окружения; `/start` → `📝 Пробный КЕГЭ 2026`.
2. Ввести 27 ответов, намеренно неверные для №8, №16, №19, №24 и №26;
   остальные взять из тестового варианта.
3. Завершить probes и открыть `🧬 Моя карта знаний`: увидеть разные global gaps
   base conversion, recursion, one shared game strategy, strings, sequences и
   grouping; №24/26 остаются PARTIAL как номера, даже если один node зелёный.
4. Нажать `🎓 Начать обучение`. Пройти первый READY prerequisite/module; на
   одном обычном шаге проверить hint ladder неверными ответами.
5. Transfer и exam_transfer выполнить с первой попытки. После mastery открыть
   dashboard: меняется ровно один global node, затем доступен следующий skill.
6. Перезапустить bot между transfer и exam_transfer, а затем сразу после
   mastery: повторное `🎓 Начать обучение` продолжает сохранённый шаг или
   открывает следующий доступный READY node, не застревая на PENDING.

## Если ученик ошибётся во всех №1–27

Tutor сохранит evidence для всех ошибок и построит один дедуплицированный курс,
а не 27 копий. Поведение по номерам: **1 PENDING** — покажет gap; **2 PARTIAL** —
обучит operations; **3 PENDING** — сохранит file gap; **4 PENDING** — сохранит
gap; **5 PARTIAL** — даст base/tracing; **6 READY** — полный tracing; **7
PARTIAL** — units; **8 READY** — base conversion; **9 PARTIAL** — logic, затем
честный spreadsheet blocker; **10 PARTIAL** — safe strings без ложного file
mastery; **11 PARTIAL** — units; **12 PARTIAL** — base/tracing; **13 PARTIAL** —
base и blockers; **14 READY** — reference path + Task Bank; **15 PARTIAL** —
logic; **16 READY** — recursion; **17 PARTIAL** — sequences без file mastery;
**18 PENDING** — spreadsheet blocker, DP остаётся заблокирован prerequisite;
**19/20/21 READY** — один общий game module; **22 PENDING** — оба application
gэпа; **23 PARTIAL** — recursion, DP после spreadsheet; **24 PARTIAL** — strings
checkpoints; **25 READY** — strings и masks; **26 PARTIAL** — sequences/grouping
без file mastery; **27 PARTIAL** — существующий controlled checkpoint pipeline.
Ни один PENDING/PARTIAL номер не станет визуально «освоенным» из-за одного
зелёного shared skill.
