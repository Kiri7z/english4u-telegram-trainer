# Roadmap

Vocabulary management, student authorization, translation practice and saved results already work. The items below are planned work, not release-date promises.

## Next: practice and progress

Items still planned below require agreement on their behavior and explicit confirmation from the owner before implementation. Review dates are for design discussions, not automatic releases. Implementation, tests, server deployment and publication follow only after that confirmation.

### 1. Avoid consecutive repeated words

Completed after approval: **19 October 2026**.

- Each remaining word appears once per shuffled round. A fresh round avoids repeating the previous word when alternatives exist.
- Mastered words leave future rounds; a single remaining word can repeat until mastered.
- The queue belongs to the current in-memory game. A new `/run` replaces it, while `/stop`, `/reset` and game completion remove it. Saved results and mastery rules stay unchanged; `/words` preserves the question and queue.
- Abandoned games retain their existing lifetime until stopped, reset or the bot restarts; automatic expiration is a separate, unimplemented feature.

### 2. Show unit progress in the unit list

Completed after approval: **22 October 2026**.

- Unit buttons show personal progress: 🟢 completed, 🟡 started but incomplete, ⚪ unstarted. Empty units show ⚪ with an `(empty)` suffix.
- Completion means every word in a nonempty unit is mastered, rather than 100% answer accuracy. A unit is started once the student has attempted at least one word, including an incorrect answer.
- Statuses are calculated from the signed-in student's saved results when opening `/units` or returning with Back. Adding unmastered vocabulary updates a completed unit to 🟡; opening the list preserves the active game and results.
- Authorization is required. The existing mastery rule remains at least 10 correct answers with at least 2/3 accuracy; no new tables or persisted status fields are needed.

### 3. Simplify word statistics

Completed after approval: **24 October 2026**.

- Stats displays `word — correct/attempts · marker · accuracy%`, with accuracy rounded to a whole percent.
- Markers use exact accuracy: 🟥 below 50%, 🟨🟨 from 50% to below 75%, 🟩🟩🟩 from 75%. Mastered words show ✅ instead of cubes; no attempts shows `No attempts`.
- Accuracy and mastery remain separate: 1/1 is 100% accuracy but not mastered. The mastery rule stays at least 10 correct answers and at least 2/3 accuracy. Existing counters and learning behavior are unchanged.

### 4. Separate Words and Stats

Completed after approval: **24 October 2026**. Statistics formatting is documented in item 3.

- Words shows only English words and translations. Stats shows English words and accuracy and mastery markers without translations.
- Added a full-width 📊 Stats button above ⬅️ Back and ▶️ Run in one row, plus `/stats` and `/words`; commands use the active or selected unit. Opening either view preserves the current question, queue and results.

## Other planned work

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
- Served practice words in shuffled rounds without consecutive repeats while alternatives remain.
- Added personal unit progress markers based on saved learning results.
- Accepted unaccented Latin answers while preserving the original vocabulary spelling.
- Separated vocabulary and statistics views, and shortened command descriptions.

Track the next task in a focused GitHub issue, implement it on a branch and describe the resulting behavior and checks in a pull request.
