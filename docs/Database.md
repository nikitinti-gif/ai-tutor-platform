# Database Model — AI Tutor Platform

## Главная идея

Система хранит не просто учеников и домашние задания, а полную историю обучения:

- кто ученик;
- кто родитель;
- какой предмет;
- какие темы изучены;
- какие ошибки повторяются;
- какие ДЗ сданы;
- что проверил ИИ;
- что проверил учитель;
- какой прогресс видят родители.

---

# Google Sheets MVP

На первом этапе используем Google Sheets как базу данных.

## 1. students

| column | description |
|---|---|
| student_id | уникальный ID ученика |
| full_name | имя ученика |
| telegram_id | Telegram ID ученика |
| grade | класс |
| exam_type | ОГЭ / ЕГЭ |
| subject | предмет |
| start_date | дата старта |
| status | active / paused / archived |
| goal_score | желаемый балл |
| teacher_id | ID преподавателя |

---

## 2. parents

| column | description |
|---|---|
| parent_id | уникальный ID родителя |
| student_id | связь с учеником |
| full_name | имя родителя |
| telegram_id | Telegram ID родителя |
| phone | телефон |
| report_format | short / full |
| status | active / inactive |

---

## 3. teachers

| column | description |
|---|---|
| teacher_id | уникальный ID преподавателя |
| full_name | имя |
| telegram_id | Telegram ID |
| subject | предмет |
| role | teacher / admin |

---

## 4. topics

| column | description |
|---|---|
| topic_id | ID темы |
| subject | предмет |
| exam_type | ОГЭ / ЕГЭ |
| topic_name | название темы |
| parent_topic | большая тема |
| difficulty | 1–5 |
| order_index | порядок изучения |

---

## 5. lessons

| column | description |
|---|---|
| lesson_id | ID занятия |
| teacher_id | преподаватель |
| subject | предмет |
| topic_id | тема |
| lesson_date | дата |
| group_name | группа |
| homework_id | связанное ДЗ |
| notes | заметки |

---

## 6. homework

| column | description |
|---|---|
| homework_id | ID домашки |
| student_id | ученик |
| lesson_id | занятие |
| topic_id | тема |
| task_text | текст задания |
| deadline | дедлайн |
| status | assigned / submitted / checked / overdue |
| created_at | дата выдачи |

---

## 7. homework_submissions

| column | description |
|---|---|
| submission_id | ID сдачи |
| homework_id | ID домашки |
| student_id | ученик |
| submitted_at | дата сдачи |
| file_url | ссылка на фото/файл |
| text_answer | текстовый ответ |
| status | new / ai_checked / teacher_checked / unclear |

---

## 8. ai_checks

| column | description |
|---|---|
| ai_check_id | ID проверки |
| submission_id | ID сдачи |
| student_id | ученик |
| topic_id | тема |
| ai_status | correct / has_error / unclear |
| ai_feedback | ответ ИИ ученику |
| error_type | тип ошибки |
| confidence | уверенность ИИ |
| needs_teacher_review | yes / no |
| created_at | дата проверки |

---

## 9. teacher_reviews

| column | description |
|---|---|
| review_id | ID ручной проверки |
| ai_check_id | ID AI проверки |
| teacher_id | преподаватель |
| final_status | correct / has_error / unclear |
| teacher_comment | комментарий |
| reviewed_at | дата проверки |

---

## 10. diagnostics

| column | description |
|---|---|
| diagnostic_id | ID диагностики |
| student_id | ученик |
| subject | предмет |
| exam_type | ОГЭ / ЕГЭ |
| test_date | дата |
| total_score | общий балл |
| weak_topics | слабые темы |
| strong_topics | сильные темы |
| ai_plan | план от ИИ |

---

## 11. progress

| column | description |
|---|---|
| progress_id | ID записи |
| student_id | ученик |
| topic_id | тема |
| week_start | начало недели |
| score_percent | процент |
| status | red / yellow / green |
| trend | up / down / stable |

---

## 12. ai_memory

| column | description |
|---|---|
| memory_id | ID памяти |
| student_id | ученик |
| topic_id | тема |
| error_type | тип ошибки |
| pattern | повторяющийся паттерн |
| helpful_hint | какая подсказка помогла |
| repeat_count | сколько раз повторилось |
| last_seen_at | последняя дата |
| teacher_note | заметка учителя |

---

## 13. parent_reports

| column | description |
|---|---|
| report_id | ID отчёта |
| student_id | ученик |
| parent_id | родитель |
| week_start | неделя |
| attendance_count | посещения |
| homework_done | ДЗ сдано |
| homework_total | всего ДЗ |
| progress_summary | краткий прогресс |
| weak_topics | слабые темы |
| next_focus | фокус следующей недели |
| pdf_url | ссылка на PDF |
| sent_at | дата отправки |

---

## 14. ai_logs

| column | description |
|---|---|
| log_id | ID лога |
| student_id | ученик |
| action_type | homework_check / diagnostics / report / task_generation |
| prompt | промпт |
| ai_response | ответ ИИ |
| status | success / error |
| created_at | дата |

---

# Главные связи

student → parents  
student → homework  
student → homework_submissions  
submission → ai_checks  
ai_check → teacher_reviews  
student → diagnostics  
student → progress  
student → ai_memory  
student → parent_reports  
teacher → lessons  
lesson → homework  
topic → homework  
topic → progress  
topic → ai_memory  

---

# MVP Priority

В первой версии обязательно нужны:

1. students
2. parents
3. teachers
4. topics
5. homework
6. homework_submissions
7. ai_checks
8. ai_memory
9. parent_reports
10. ai_logs

Остальное можно добавить позже.