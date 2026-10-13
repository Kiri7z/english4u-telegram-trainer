# telegram_bot/models.py

from sqlalchemy import Column, Integer, String, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
from db_config import Base

class Teacher(Base):
    __tablename__ = 'teachers'
    teacher_id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)

class Student(Base):
    __tablename__ = 'students'
    student_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    token = Column(String(20), unique=True, nullable=False)
    telegram_user_id = Column(BigInteger, unique=True)

class Unit(Base):
    __tablename__ = 'units'
    unit_id = Column(Integer, primary_key=True)
    unit_name = Column(String(50), nullable=False)
    words = relationship('Word', backref='unit', lazy=True)

class Word(Base):
    __tablename__ = 'words'
    word_id = Column(Integer, primary_key=True)
    unit_id = Column(Integer, ForeignKey('units.unit_id'), nullable=False)
    word = Column(String(50), nullable=False)
    translation = Column(String(50), nullable=False)

class Result(Base):
    __tablename__ = 'results'
    result_id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey('students.student_id'), nullable=False)
    unit_id = Column(Integer, ForeignKey('units.unit_id'), nullable=False)
    word_id = Column(Integer, ForeignKey('words.word_id'), nullable=False)
    requests = Column(Integer, nullable=False, default=0)
    answers = Column(Integer, nullable=False, default=0)
