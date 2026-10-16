# Roadmap

Vocabulary management, student authorization, translation practice and saved results already work. The items below are planned work, not release-date promises.

## Next: practice and progress

These four improvements are proposals. Before implementing each item, agree on its behavior with the owner and obtain explicit confirmation. The first two dates below are design reviews, not automatic releases. Implementation, tests, server deployment and publication follow only after that confirmation.

### 1. Avoid consecutive repeated words

Design review: **19 October 2026**.

- Prevent the same word appearing several times in a row when at least two words still need practice.
- Review a shuffled rotation of the remaining words, compared with simply excluding the previous word. A rotation would show every eligible word before starting another round and avoid a repeat across round boundaries when possible.
- Handle the single remaining word explicitly: repetition is unavoidable until it is mastered.
- Preserve saved results, mastery rules, and the current question when viewing vocabulary. Agree on the algorithm before changing the game.

### 2. Show unit progress in the unit list

Design review: **21 October 2026**.

- Add a personal status marker to each unit: 🟢 for completed, 🟡 for started but incomplete, and a neutral marker or no marker for unstarted units, to be agreed.
- Define completion as every word in a nonempty unit being mastered, rather than 100% answer accuracy. A unit is started once the student has attempted at least one word.
- Use the signed-in student's saved progress only. Empty units must not appear completed, and adding new unmastered vocabulary should update the status.
- Keep the existing mastery rule unless a separate change is approved: at least 10 correct answers with at least 2/3 accuracy.

### 3. Simplify word statistics

Not scheduled; agree on the display separately.

- Replace decimal scores and `(A-6)` with a short, understandable counter and status, for example `on time — 🟡 6 correct`; the wording (`correct`, `answers`, or `points`) remains undecided. Do not introduce a new scoring system implicitly.
- Review red/yellow/green bands around 50% and 75%. First decide whether the percentage means answer accuracy or progress towards the required correct-answer count; these are different measurements. Agree on the exact boundaries, including 50%, and the display before any attempts.
- Keep ✅ for mastered words. Distinguish presentation thresholds from the existing mastery rule; do not change learning rules without explicit approval.
- Use emoji markers such as 🔴 🟡 🟢 rather than promising arbitrary text colors in standard Telegram messages; see [Telegram formatting options](https://core.telegram.org/bots/api#html-style).

### 4. Separate Words and Stats

Not scheduled; depends on agreeing the statistics display in item 3.

- Keep Words focused on vocabulary only: `firmly: крепко`, `on time: вовремя`, `be prepared: быть готовым`.
- Add a separate Stats view containing the English word and its progress, without translations: for example `firmly — ✅`, `on time — 🟡 6 correct`. Examples are provisional.
- Agree on the buttons and whether to add `/stats`; keep `/words` for vocabulary. Switching views must not count an answer, advance the game or lose its current question.

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

Track the next task in a focused GitHub issue, implement it on a branch and describe the resulting behavior and checks in a pull request.
