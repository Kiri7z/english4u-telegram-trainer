from app import db, login_manager
from flask_login import UserMixin

@login_manager.user_loader
def load_user(user_id):
    return Teacher.query.get(int(user_id))

class Teacher(UserMixin, db.Model):  # Наследуем UserMixin
    __tablename__ = 'teachers'
    teacher_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

    # Явное определение get_id(), чтобы гарантировать корректное возвращение идентификатора
    def get_id(self):
        return str(self.teacher_id)  # Важно вернуть строку, так как get_id() требует строку

class Student(db.Model):
    __tablename__ = 'students'
    student_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    token = db.Column(db.String(20), unique=True, nullable=False)  # Используем token вместо phone_number

class Unit(db.Model):
    __tablename__ = 'units'
    unit_id = db.Column(db.Integer, primary_key=True)
    unit_name = db.Column(db.String(50), nullable=False)
    words = db.relationship('Word', backref='unit', lazy=True, passive_deletes=True)

class Word(db.Model):
    __tablename__ = 'words'
    word_id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey('units.unit_id'), nullable=False)
    word = db.Column(db.String(50), nullable=False)
    translation = db.Column(db.String(50), nullable=False)

class Result(db.Model):
    __tablename__ = 'results'
    result_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.student_id'), nullable=False)
    unit_id = db.Column(db.Integer, db.ForeignKey('units.unit_id'), nullable=False)
    word_id = db.Column(db.Integer, db.ForeignKey('words.word_id'), nullable=False)
    requests = db.Column(db.Integer, nullable=False, default=0)
    answers = db.Column(db.Integer, nullable=False, default=0)

    # Представление score рассчитывается на основе значения запросов и ответов
    @property
    def score(self):
        return round(self.answers / self.requests, 2) if self.requests > 0 else 0

    @property
    def is_mastered(self):
        return self.answers >= 10 and self.answers * 3 >= self.requests * 2
