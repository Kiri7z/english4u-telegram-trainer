# Roadmap

Vocabulary management, student authorization, translation practice and saved results already work. The items below are planned work, not release-date promises.

## Next

- Improve validation and useful errors when editing existing vocabulary.
- Improve the teacher's overview of units and student progress.
- Add end-to-end checks against temporary PostgreSQL alongside fast SQLite tests.

## Later

- Support several valid translations and more flexible answer checking.
- Review spaced repetition and revisiting mastered words.
- Make backup and restore easier to verify.
- Add shared rate-limit storage if the project grows beyond a single instance.

## Recent work: October 2026

- Moved secrets out of code and separated database permissions.
- Removed database port exposure and student codes from sample data.
- Updated the Telegram library while preserving mastery rules and /words.
- Added global CSRF protection, protected logout, authentication limits and configurable HTTPS sessions.
- Added regression tests, security checks and documentation with real app screenshots.
- Validated complete vocabulary imports before saving, preserved input on errors, and saved units and words in one transaction.
- Cleared active games and selected units on authorization reset, while preserving student records, learning results and attempt limits.
- Used Web Crypto for new student access codes, preserving existing codes and bindings.

Track the next task in a focused GitHub issue, implement it on a branch and describe the resulting behavior and checks in a pull request.
