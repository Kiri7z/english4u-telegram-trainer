from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from app import app, db
from app.models import Teacher, Student, Unit, Word, Result  # Импорт всех необходимых моделей
from app.forms import LoginForm
from flask_wtf.csrf import CSRFError
from security_controls.rate_limit import SlidingWindowLimiter

login_attempts = SlidingWindowLimiter(limit=5, window_seconds=300)
login_clients = SlidingWindowLimiter(limit=30, window_seconds=300)


@app.errorhandler(CSRFError)
def csrf_error(error):
    return render_template('request_error.html',
                           message='This form expired or could not be verified. Refresh the page and try again.'), 400


def login_rate_limit_response(seconds):
    response = app.make_response((render_template('request_error.html',
        message=f'Too many sign-in attempts. Please try again in {seconds} seconds.'), 429))
    response.headers['Retry-After'] = str(seconds)
    return response

# Маршрут для логина
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        client = request.remote_addr or 'unknown'
        key = (client, form.username.data.strip().casefold())
        wait = login_clients.consume(client)
        if not wait:
            wait = login_attempts.consume(key)
        if wait:
            return login_rate_limit_response(wait)
        teacher = Teacher.query.filter_by(username=form.username.data).first()
        if teacher and check_password_hash(teacher.password, form.password.data):
            login_attempts.reset(key)
            login_user(teacher)  # Вход в систему для пользователя
            flash('Успешный вход!', 'success')
            return redirect(url_for('home'))  # Перенаправление на домашнюю страницу
        else:
            flash('Неправильный логин или пароль.', 'danger')
    
    return render_template('login.html', form=form)

# Маршрут для выхода
@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы.', 'success')
    return redirect(url_for('login'))

# Маршрут для домашней страницы
@app.route('/')
@login_required
def home():
    return render_template('home.html')  # Ссылка на шаблон home.html

# Маршрут для управления студентами (список студентов с ссылками на результаты)
@app.route('/students', methods=['GET', 'POST'])
@login_required
def students():
    if request.method == 'POST':
        name = request.form['name']
        token = request.form['token']
        new_student = Student(name=name, token=token)
        db.session.add(new_student)
        db.session.commit()
        flash('Student added successfully!')
        return redirect(url_for('students'))
    
    students = Student.query.all()
    return render_template('students.html', students=students)

# Маршрут для просмотра результатов конкретного студента
@app.route('/student/<int:student_id>')
@login_required
def student_results(student_id):
    student = Student.query.get_or_404(student_id)
    # Получаем результаты для конкретного студента, отсортированные по word_id
    results = Result.query.filter_by(student_id=student.student_id).order_by(Result.word_id).all()
    results_by_unit = {}

    for result in results:
        unit_name = Unit.query.filter_by(unit_id=result.unit_id).first().unit_name
        word = Word.query.filter_by(word_id=result.word_id).first().word
        if unit_name not in results_by_unit:
            results_by_unit[unit_name] = {}
        results_by_unit[unit_name][word] = result

    return render_template('student_results.html', student=student, results_by_unit=results_by_unit)

# Маршрут для управления словами и юнитами
@app.route('/words', methods=['GET', 'POST'])
@login_required
def words():
    if request.method == 'POST':
        unit_name = request.form['unit_name']
        words_text = request.form['words']
        new_unit = Unit(unit_name=unit_name)
        db.session.add(new_unit)
        db.session.commit()

        # Добавление слов
        words_list = words_text.splitlines()
        for word in words_list:
            english, russian = word.split(': ')
            new_word = Word(unit_id=new_unit.unit_id, word=english.strip(), translation=russian.strip())
            db.session.add(new_word)

        db.session.commit()
        flash('Unit and words added successfully!')
        return redirect(url_for('words'))
    
    # Запрос для получения всех юнитов и связанных с ними слов
    units = Unit.query.all()
    for unit in units:
        unit.words = Word.query.filter_by(unit_id=unit.unit_id).all()

    return render_template('words.html', units=units)

# Маршрут для редактирования студента
@app.route('/edit_student/<int:student_id>', methods=['GET', 'POST'])
@login_required
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)
    
    if request.method == 'POST':
        # Обновляем данные студента
        student.name = request.form['name']
        student.token = request.form['token']
        db.session.commit()
        flash('Student updated successfully!')
        return redirect(url_for('students'))
    
    return render_template('edit_student.html', student=student)

# Маршрут для удаления студента и его результатов
@app.route('/delete_student/<int:student_id>', methods=['POST'])
@login_required
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
    
    # Удаляем самого студента; связанные результаты будут удалены каскадно
    db.session.delete(student)
    db.session.commit()
    
    flash('Student and their results deleted successfully!')
    return redirect(url_for('students'))

# Маршрут для редактирования юнита и слов
@app.route('/edit_unit/<int:unit_id>', methods=['GET', 'POST'])
@login_required
def edit_unit(unit_id):
    unit = Unit.query.get_or_404(unit_id)
    words = Word.query.filter_by(unit_id=unit.unit_id).all()  # Получаем слова для юнита
    
    if request.method == 'POST':
        # Обновляем название юнита
        unit.unit_name = request.form['unit_name']
        
        # Обновляем слова юнита
        for word in words:
            word.word = request.form[f'word_{word.word_id}']
            word.translation = request.form[f'translation_{word.word_id}']
        
        db.session.commit()
        flash('Unit and words updated successfully!')
        return redirect(url_for('words'))
    
    return render_template('edit_unit.html', unit=unit, words=words)  # Передаем слова в шаблон

# Маршрут для удаления юнита и его слов
@app.route('/delete_unit/<int:unit_id>', methods=['POST'])
@login_required
def delete_unit(unit_id):
    unit = Unit.query.get_or_404(unit_id)
    
    # Удаляем сам юнит; связанные слова будут удалены каскадно
    db.session.delete(unit)
    db.session.commit()
    
    flash('Unit and its words deleted successfully!')
    return redirect(url_for('words'))
