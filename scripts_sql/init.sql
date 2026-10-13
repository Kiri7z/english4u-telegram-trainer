-- Устанавливаем расширение для хеширования паролей
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Таблица студентов
CREATE TABLE students (
    student_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    token VARCHAR(20) UNIQUE NOT NULL,  -- Оставлено без изменений
    telegram_user_id BIGINT UNIQUE  -- Добавлено для хранения Telegram User ID
);

-- Таблица уроков (units)
CREATE TABLE units (
    unit_id SERIAL PRIMARY KEY,
    unit_name VARCHAR(50) NOT NULL
);

-- Таблица слов
CREATE TABLE words (
    word_id SERIAL PRIMARY KEY,
    unit_id INTEGER REFERENCES units(unit_id) ON DELETE CASCADE,
    word VARCHAR(50) NOT NULL,
    translation VARCHAR(50) NOT NULL
);

-- Таблица результатов
CREATE TABLE results (
    result_id SERIAL PRIMARY KEY,
    student_id INTEGER REFERENCES students(student_id) ON DELETE CASCADE,
    unit_id INTEGER REFERENCES units(unit_id) ON DELETE CASCADE,
    word_id INTEGER REFERENCES words(word_id) ON DELETE CASCADE,
    requests INTEGER DEFAULT 0 NOT NULL,
    answers INTEGER DEFAULT 0 NOT NULL,
    UNIQUE(student_id, unit_id, word_id) -- Добавлено уникальное ограничение
);

-- Представление для расчета поля score
CREATE VIEW results_view AS
SELECT
    result_id,
    student_id,
    unit_id,
    word_id,
    requests,
    answers,
    CASE
        WHEN requests = 0 THEN 0
        ELSE ROUND((answers::numeric / requests), 2)
    END AS score
FROM
    results;

-- Таблица учителей
CREATE TABLE teachers (
    teacher_id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL -- Оставлено VARCHAR(255) для хешированных паролей
);
