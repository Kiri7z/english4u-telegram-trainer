\set ON_ERROR_STOP on
\getenv web_password WEB_DB_PASSWORD
\getenv bot_password BOT_DB_PASSWORD

SELECT 'CREATE ROLE english4u_web LOGIN' WHERE NOT EXISTS
  (SELECT FROM pg_roles WHERE rolname = 'english4u_web') \gexec
SELECT 'CREATE ROLE english4u_bot LOGIN' WHERE NOT EXISTS
  (SELECT FROM pg_roles WHERE rolname = 'english4u_bot') \gexec
SELECT format('ALTER ROLE english4u_web PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', :'web_password') \gexec
SELECT format('ALTER ROLE english4u_bot PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', :'bot_password') \gexec

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE CONNECT, TEMPORARY ON DATABASE :"DBNAME" FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM english4u_web, english4u_bot;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM english4u_web, english4u_bot;
GRANT CONNECT ON DATABASE :"DBNAME" TO english4u_web, english4u_bot;
GRANT USAGE ON SCHEMA public TO english4u_web, english4u_bot;

-- Web panel and create_teacher.py: no schema changes or superuser access.
GRANT SELECT ON teachers, students, units, words, results TO english4u_web;
GRANT INSERT ON teachers TO english4u_web;
GRANT INSERT, UPDATE, DELETE ON students, units, words TO english4u_web;
GRANT USAGE ON SEQUENCE teachers_teacher_id_seq, students_student_id_seq,
  units_unit_id_seq, words_word_id_seq TO english4u_web;

-- Bot: vocabulary reads, student binding, and answer counters only.
GRANT SELECT ON students, units, words, results, results_view TO english4u_bot;
GRANT UPDATE (telegram_user_id) ON students TO english4u_bot;
GRANT INSERT ON results TO english4u_bot;
GRANT UPDATE (requests, answers) ON results TO english4u_bot;
GRANT USAGE ON SEQUENCE results_result_id_seq TO english4u_bot;
