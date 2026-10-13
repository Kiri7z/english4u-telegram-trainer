-- Demonstration vocabulary only: no students, access tokens, or results.
-- Добавляем unit
INSERT INTO units (unit_name) VALUES 
('unit1'),
('unit2');

-- Добавляем слова для unit1
INSERT INTO words (unit_id, word, translation) VALUES 
(1, 'Appearance', 'Внешность'),
(1, 'Get on well with', 'Ладить с (кем-то)'),
(1, 'Go on a date', 'Идти на свидание'),
(1, 'Personality', 'Характер'),
(1, 'Pregnant', 'Беременная'),
(1, 'Relationship', 'Отношения'),
(1, 'Get divorced', 'Развестись'),
(1, 'Separated', 'Разделённый, разведенный'),
(1, 'Sociable', 'Общительный'),
(1, 'What does she look like?', 'Как она выглядит?'),
(1, 'What is she like?', 'Какая она? (о характере)');

-- Добавляем слова для unit2
INSERT INTO words (unit_id, word, translation) VALUES 
(2, 'Suddenly', 'Неожиданно'),
(2, 'Sunbathe', 'Загорать'),
(2, 'Argue', 'Ссориться'),
(2, 'Awful', 'Ужасный'),
(2, 'Break up', 'Расстаться(о паре)'),
(2, 'Disaster', 'Катастрофа'),
(2, 'Election', 'Выборы'),
(2, 'Fall in love', 'Влюбиться'),
(2, 'Horrible', 'Ужасный_2'),
(2, 'In a hurry', 'В спешке'),
(2, 'Rebel', 'Бунтарь'),
(2, 'Royal', 'Королевский'),
(2, 'Politics', 'Политика'),
(2, 'Shoulders', 'Плечи'),
(2, 'Something else', 'Что-то еще'),
(2, 'Each other', 'Друг друга'),
(2, 'Invite', 'Пригласить'),
(2, 'Leave house', 'Уйти из дома');
