# Схема даних PostgreSQL

```mermaid
erDiagram
    SPECIALTIES ||--o{ SUBJECTS : містить
    SPECIALTIES ||--o{ STUDENT_GROUPS : містить
    SUBJECTS ||--o{ COURSES : має
    COURSES ||--o{ COURSE_MEMBERSHIPS : зараховує
    STUDENT_GROUPS ||--o{ COURSE_MEMBERSHIPS : групує
    USERS ||--o{ COURSE_MEMBERSHIPS : навчається
    USERS ||--o{ TEACHER_COURSES : викладає
    COURSES ||--o{ TEACHER_COURSES : призначає
    COURSES ||--o{ QUESTIONS : містить
    QUESTIONS ||--|{ REFERENCE_ANSWERS : визначає
    REFERENCE_ANSWERS ||--o{ REFERENCE_CONCEPTS : описує
    REFERENCE_ANSWERS ||--o{ ANSWER_VARIATIONS : має
    QUESTIONS ||--o{ SUBMISSIONS : приймає
    USERS ||--o{ SUBMISSIONS : надсилає
    SUBMISSIONS ||--o{ ANALYSIS_RESULTS : аналізується
    MODEL_VERSIONS ||--o{ EMBEDDINGS : створює
    MODEL_VERSIONS ||--o{ ANALYSIS_RESULTS : версія
    EMBEDDINGS ||--o{ ANALYSIS_RESULTS : вектор
    ANALYSIS_RESULTS ||--o{ TEACHER_REVIEWS : перевіряється
    USERS ||--o{ TEACHER_REVIEWS : ухвалює
    USERS ||--o{ AUTH_SESSIONS : входить
```

| Таблиці | Вміст та інваріанти |
| --- | --- |
| `users`, `auth_sessions`, `login_throttle` | Унікальна нормалізована пошта, Argon2id, роль і активність. Refresh-токени зберігаються як хеші. Ліміти входу зберігаються між процесами. |
| `specialties`, `subjects`, `courses`, `student_groups` | Довідники, рік, статус, видимість результатів і пороги курсу. Унікальні код спеціальності й складені ключі дисципліни, групи та курсу. |
| `teacher_courses`, `course_memberships` | Унікальні пари викладач–курс і студент–курс, належність до групи й прапорець доступу. |
| `questions`, `reference_answers`, `reference_concepts` | Статуси питання, один або кілька еталонів, поняття, ваги, синоніми та змістові правила. Публікація перевіряє наявність еталона. |
| `answer_variations` | Прив’язка до еталона, хеш нормалізованого формулювання, статус, автор, дати й викладач. Унікальний хеш у межах еталона. |
| `submissions` | Оригінальний текст, знімок питання, група на час надсилання, ключ повторного запиту й стан черги з орендою. |
| `analysis_results`, `teacher_reviews` | Новий рядок для кожного завершеного аналізу й рішення. Результат містить знімок параметрів та найближчого навчального матеріалу. |
| `model_versions`, `embeddings`, `embedding_jobs` | Версія і розмірність, pgvector-вектори за хешем тексту та черга попереднього обчислення для еталонів і затверджених варіацій. |
| `system_settings`, `audit_log` | Глобальні параметри, сигнал воркера й журнал змін. |

Міграції Alembic послідовно додають розширення `vector`, реляційну схему, індекси й чергу векторизації. B-tree покриває зв’язки курсу, студента, статусів, дати та останніх аналізів. HNSW-індекси за cosine призначені для 384 і 768 вимірів. Аналіз конкретного питання обчислює точну відстань через pgvector для всіх дозволених кандидатів. Це зберігає повноту порівняння після фільтрації за питанням і статусом.

```bash
alembic -c backend/alembic.ini current
alembic -c backend/alembic.ini upgrade head
```

Архівні питання та формулювання зберігають зовнішні ключі й історію. Відновлення даних описано в [SECURITY.md](SECURITY.md).
