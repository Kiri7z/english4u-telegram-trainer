"""Validate a complete vocabulary import before any database writes."""


def parse_vocabulary(unit_name, words_text):
    name = unit_name.strip()
    if not name:
        raise ValueError('Enter a unit name.')
    if len(name) > 50:
        raise ValueError('The unit name must be at most 50 characters.')

    entries = []
    for number, line in enumerate(words_text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        if ':' not in line:
            raise ValueError(f'Line {number}: use Word: Translation.')
        english, translation = (part.strip() for part in line.split(':', 1))
        if not english or not translation:
            raise ValueError(f'Line {number}: both the word and translation are required.')
        if len(english) > 50 or len(translation) > 50:
            raise ValueError(f'Line {number}: the word and translation must each be at most 50 characters.')
        entries.append((english, translation))

    if not entries:
        raise ValueError('Enter at least one word and translation.')
    return name, entries
