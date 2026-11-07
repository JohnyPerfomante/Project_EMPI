# REST API

Базовий шлях `/api/v1`. У Swagger UI на `/api/docs` доступні типи запиту й відповіді. Машиночитний контракт доступний на `/api/openapi.json`. Доступ до навчальних об’єктів залежить від ролі, курсу та власності подання.

| Розділ | Маршрути відносно `/api/v1` |
| --- | --- |
| Реєстрація, вхід і сесія | `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me` |
| Користувачі | `GET, POST /users`, `GET, PATCH /users/{id}`, `PATCH /users/{id}/role` |
| Довідники | `GET, POST /specialties`, `/subjects`, `/student-groups`. Редагування через `PUT /{довідник}/{id}`. |
| Курси | `GET, POST /courses`, `GET, PATCH /courses/{id}`, `GET /courses/{id}/groups`, `GET, PUT /courses/{id}/memberships` і `/teachers` |
| Питання | `GET, POST /questions`, `GET, PATCH /questions/{id}`, `POST /questions/{id}/archive` |
| Еталони | `GET, POST /questions/{id}/reference-answers`, `PATCH /reference-answers/{id}` |
| Варіації | `GET, POST /variations`, `GET /variations/{id}`, `POST /variations/{id}/{approve, reject, archive, reopen}` |
| Подання | `GET, POST /submissions`, `GET /submissions/summary`, `GET /submissions/{id}` і `/{id}/{result, history, reviews}`, `POST /submissions/{id}/{analyze, reanalyze}` |
| Рішення | `GET /reviews/pending`, `POST /reviews/{analysis_id}/{approve, reject, partial}` |
| Звіти | `GET /reports/summary`, `/reports/courses`, `/reports/submissions` |
| Система | `GET, PATCH /settings`, `GET /audit-log`, `GET /health`, `GET /health/worker` |

Списки повертають `items`, `total`, `offset`, `limit`. Типові фільтри мають назви `q`, `course_id`, `subject_id`, `group_id`, `status`, `category`, `date_from`, `date_to`. Точний набір залежить від маршруту. Дати передаються як `YYYY-MM-DD` і трактуються у часовій зоні Києва.

## Реєстрація

`POST /api/v1/auth/register` створює активного користувача з роллю `student` або `teacher` та повертає `UserView` зі статусом 201. Поля запиту мають назви `full_name`, `email`, `role`, `password`, `password_confirmation`. Паролі мають збігатися й містити 12–128 символів. Пошта нормалізується до нижнього регістру, дублікати повертають 409 з кодом `email_already_registered`. Реєстрація фіксується в аудиті. Для входу після реєстрації клієнт викликає `/auth/login`.

Ліміти реєстрації зберігаються в БД окремо від лімітів входу. За перевищення повертається 429. Приклад тіла запиту:

```json
{"full_name":"Олена Коваленко","email":"olena@example.org","role":"teacher","password":"<ваш пароль від 12 символів>","password_confirmation":"<ваш пароль від 12 символів>"}
```

## Запит студента

Заголовок `X-EMPI-Request: 1` обов’язковий для операцій зі зміною стану. Вхід і оновлення сесії встановлюють HttpOnly cookie.

```bash
base=http://127.0.0.1:8080/api/v1
curl -sS -c cookies.txt -H 'X-EMPI-Request: 1' -H 'Content-Type: application/json' \
  -d '{"email":"student@demo.edu.ua","password":"<DEMO_PASSWORD>"}' "$base/auth/login"
curl -sS -b cookies.txt "$base/questions?limit=5"
curl -sS -b cookies.txt -H 'X-EMPI-Request: 1' -H 'Content-Type: application/json' \
  -d '{"question_id":1,"answer_text":"У відсортованому масиві перевіряють середину.","request_id":"82c5c60e-3966-4c88-8df0-39e753e3482d"}' \
  "$base/submissions"
```

Клієнт використовує `id` із відповіді 201 для опитування `/submissions/{id}/result`. `request_id` дозволяє безпечно повторити надсилання того самого запиту. Приклад структури до завершення аналізу:

```json
{"status":"queued","visibility":"automatic","review_status":"pending","analysis":null,"review":null}
```

Викладач отримує детальні метрики, попередження й знімок матеріалів. Студент отримує дозволені категорію, показник та пояснення. Для режиму `reviewed` видимість нового аналізу з’являється після рішення щодо цієї версії.

## Помилки

```json
{"error":{"code":"invalid_answer","message":"Відповідь має містити від 5 до 1800 символів."}}
```

`401` вимагає входу або оновлення сесії. `403` означає відсутність прав на дію. `404` охоплює недоступні об’єкти. `409` фіксує конфлікт або недопустимий перехід. `422` позначає помилку даних. `429` обмежує спроби входу. `503` означає тимчасову недоступність БД.
