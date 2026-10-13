import argparse
from getpass import getpass
from app import app, db
from app.models import Teacher
from werkzeug.security import generate_password_hash

def create_teacher(username, password):
    # Используем правильный метод для хеширования пароля
    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
    new_teacher = Teacher(username=username, password=hashed_password)
    db.session.add(new_teacher)
    db.session.commit()
    print(f"Учитель {username} успешно добавлен.")

if __name__ == "__main__":
    # Создаем парсер аргументов командной строки
    parser = argparse.ArgumentParser(description="Создание нового учителя в системе")
    parser.add_argument("username", type=str, help="Имя пользователя учителя")
    parser.add_argument("password", nargs="?", help="Пароль учителя (лучше вводить по запросу)")

    # Парсим аргументы
    args = parser.parse_args()

    # Создаем контекст приложения
    with app.app_context():
        # Используем функцию для добавления учителя с аргументами
        create_teacher(args.username, args.password or getpass("Teacher password: "))
