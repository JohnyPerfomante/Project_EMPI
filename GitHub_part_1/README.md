# Освітній процес

Версія для GitHub зі збереженим функціоналом і повною документацією. [Завантаження на GitHub, запуск і перенесення поточних даних](docs/GITHUB.md).

Підсистема лінгвістичного аналізу відкритих відповідей студентів для ІПЗ і КН. Викладач публікує питання з еталонами й критеріями, студент надсилає відповідь, локальний NLP формує рекомендацію. Викладач ухвалює рішення й може затвердити формулювання для наступних перевірок.

## Запуск через Docker

Потрібні Docker Engine або Docker Desktop із Compose v2, Python 3 для допоміжного скрипта налаштування, доступ до реєстру образів і Hugging Face для першого запуску. Для робочого середовища з моделлю MPNet виділіть Docker щонайменше 6 ГБ оперативної пам’яті та близько 8 ГБ дискового простору для образів, моделі й даних.

```bash
python3 scripts/configure.py
```

Скрипт створює `.env` з випадковими паролями БД і демоакаунтів та ключем JWT. Пароль входу після seed міститься у `DEMO_PASSWORD`. Наявний `.env` не перезаписується. Альтернатива — скопіювати `.env.example` у `.env` і самостійно заповнити секрети. Вебсервіс і PostgreSQL за замовчуванням доступні лише на loopback. У Windows для скрипта можна використати `py -3`.

```bash
docker compose up -d --build
docker compose ps -a
docker compose exec -T api python -m scripts.seed_demo
```

- Вебінтерфейс — [127.0.0.1:8081](http://127.0.0.1:8081).
- REST API та інтерактивна документація — [Swagger UI](http://127.0.0.1:8081/api/docs).
- За першого запуску `models` завантажує локальні ваги в том `models`. Нормальний стан після запуску — `migrate` і `models` завершилися з кодом 0, `api`, `worker`, `web` і `db` працюють. Подання приймаються під час підготовки воркера.
- `docker compose logs -f models worker` показує прогрес моделі. Статус воркера також є в адміністративному кабінеті.
- `docker compose down` зупиняє процеси й зберігає томи. Для відновлення використайте `docker compose up -d` з тим самим `.env`.

### Демонстраційні облікові записи

| Роль | Логін |
| --- | --- |
| Адміністратор | `admin@demo.edu.ua` |
| Викладач | `teacher@demo.edu.ua` |
| Студент | `student@demo.edu.ua` |
| Другий студент | `student2@demo.edu.ua` |

Пароль для всіх облікових записів задає `DEMO_PASSWORD` під час створення. Повторний seed доповнює базу пропущеними записами та зберігає ручні рішення і паролі вже створених облікових записів. У наборі 50 питань, сім дисциплін і 25 демонстраційних подань. Демонстраційні варіації спочатку мають статус «Очікує перевірки».

Для середовища без демо заповніть `BOOTSTRAP_ADMIN_EMAIL` і `BOOTSTRAP_ADMIN_PASSWORD`, далі виконайте `docker compose exec -T api python -m scripts.bootstrap_admin`.

### Реєстрація власного облікового запису

На сторінці входу натисніть «Створити обліковий запис» або відкрийте `/register`. Вкажіть ім’я та прізвище, електронну пошту, роль студента чи викладача та двічі введіть власний пароль довжиною 12–128 символів. Після створення облікового запису система відкриє форму входу з вашою поштою.

Реєстрація одразу активує обліковий запис. Для роботи з навчальними матеріалами адміністратор призначає викладачу курси або зараховує студента до курсу та групи. Самостійна реєстрація доступна для ролей `student` і `teacher`. Адміністратор створюється через bootstrap або чинним адміністратором.

`REGISTRATION_LIMIT` задає кількість спроб за 10-хвилинне вікно для однієї пошти. Ліміт мережевого клієнта утричі більший. Початкове значення — 5.

## Розробка

Потрібні Python 3.12, Node.js 20.19+ або 22, PostgreSQL 16+ із pgvector. Для локального Python використайте `DATABASE_URL` із `.env`. `DB_PORT` у Compose і порт у `DATABASE_URL` для запуску з хоста мають збігатися. Compose складає внутрішній DSN з `POSTGRES_*`. Якщо значення містить символи URI, потрібно передати коректно закодований DSN через перевизначення Compose.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e './backend[nlp,test]'
docker compose up -d db
alembic -c backend/alembic.ini upgrade head
(cd backend && python -m scripts.prepare_models)
(cd backend && python -m scripts.seed_demo)
uvicorn app.main:app --host 127.0.0.1 --no-access-log
```

В окремих терміналах, з активованим venv для воркера:

```bash
python -m app.worker
```

```bash
cd frontend
npm ci
npm run dev
```

## Перевірки

```bash
docker compose exec -T db createdb -U empi empi_test
TEST_DATABASE_URL=postgresql+psycopg://empi:<POSTGRES_PASSWORD>@127.0.0.1:55433/empi_test \
  RUN_REAL_NLP=1 pytest -q backend/tests
npm --prefix frontend test
npm --prefix frontend run build
(cd frontend && npx playwright install chromium)
E2E_BASE_URL=http://127.0.0.1:8081 E2E_PASSWORD='<DEMO_PASSWORD>' npm --prefix frontend run e2e
```

У тестовому DSN замініть `<POSTGRES_PASSWORD>` значенням з вашого `.env`, а `<DEMO_PASSWORD>` — паролем створених демоакаунтів.

Інтеграційні тести очищають лише явно вказану тестову БД із суфіксом `_test`. Для Playwright потрібні запущена система й seed. За замовчуванням він працює через порт 8081, заданий `E2E_BASE_URL` і створює власні тестові записи. Змінні `E2E_BASE_URL` та `PLAYWRIGHT_CHROMIUM_EXECUTABLE` дозволяють указати іншу адресу й локальний браузер. CI запускає backend із тестовим NLP-провайдером. Окремий тест із `RUN_REAL_NLP=1` використовує кешовані ваги Stanza й MPNet.

Фактичні результати запуску перевірок наведено в [протоколі](docs/TESTING.md).

## Структура й документація

| Шлях | Вміст |
| --- | --- |
| `backend/app` | FastAPI, SQLAlchemy, авторизація, доступ, воркер, NLP і звітність |
| `backend/migrations` | Alembic та індекси PostgreSQL |
| `backend/scripts` | Підготовка моделей, bootstrap, демодані й оцінювання |
| `frontend/src` | React, TypeScript, україномовний інтерфейс трьох ролей |
| `database/seeds` | Демонстраційний банк та приклади відповідей |
| `frontend/e2e`, `backend/tests` | Браузерні, інтеграційні й модульні перевірки |
| `docs` | [Архітектура](docs/ARCHITECTURE.md), [БД](docs/DATABASE.md), [API](docs/API.md), [NLP](docs/NLP.md), [оцінювання](docs/NLP_EVALUATION.md), [безпека](docs/SECURITY.md), [інструкція користувача](docs/USER_GUIDE.md) |

Презентація для захисту міститься в `docs/presentation`. Повна інструкція з 111 скріншотами: [DOCX](<docs/manual/Інструкція користувача Освітній процес.docx>).

Окремі порти 8081 і 55433 та Compose-проєкт `osvitnii-protses-github` дозволяють запускати цю версію поряд із початковою. Для перенесення вже наявних акаунтів і навчальних даних використовуйте приватний дамп і процедуру з [GITHUB.md](docs/GITHUB.md).

Автономна версія надає API для подальшої інтеграції. Технічний контракт наявної університетської системи та незалежний корпус із розміткою викладачів не входили до вхідних матеріалів.
