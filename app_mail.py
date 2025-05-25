import threading
import datetime
import os
import json
import time  # NEW
from flask import Flask, request, render_template, redirect, url_for, flash, jsonify
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# NEW for multiple attachments:
from email.mime.base import MIMEBase
from email import encoders
from accounts import bp as accounts_bp
from streams import bp as streams_bp

app = Flask(__name__)
app.secret_key = 'your-secret-key'
app.register_blueprint(accounts_bp, url_prefix="/accounts")
app.register_blueprint(streams_bp, url_prefix="/streams")

# Максимальный размер лог файла в байтах (10 МБ)
MAX_LOG_FILE_SIZE = 10 * 1024 * 1024

# Файлы для хранения настроек и логов
CONFIG_FILE = "config.json"
LOGS_FILE = "logs.json"

# Дефолтные настройки SMTP
EMAIL_CONFIGS = {
    'mail.ru': {
        'smtp_server': 'smtp.mail.ru',
        'smtp_port': 465,
        'email': 'your_email@mail.ru',
        'password': 'your_password'
    },
    'yandex': {
        'smtp_server': 'smtp.yandex.ru',
        'smtp_port': 465,
        'email': 'your_email@yandex.ru',
        'password': 'your_password'
    }
}

# Глобальные переменные
active_email_config = {}  # данные из админки
email_logs = []  # логи отправки
progress_info = {}  # статус рассылки


# ============== Функции работы с файлами ==============

def load_config():
    """Считывает JSON-конфигурацию из файла CONFIG_FILE."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}


def save_config(data):
    """Сохраняет настройки в JSON-файл CONFIG_FILE."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def load_logs():
    """Загружает список логов из LOGS_FILE, если он существует."""
    if os.path.exists(LOGS_FILE):
        with open(LOGS_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return []
    return []


def rotate_logs():
    """Если размер файла с логами превышает MAX_LOG_FILE_SIZE, переименовывает его с добавлением временной метки."""
    if os.path.exists(LOGS_FILE) and os.path.getsize(LOGS_FILE) >= MAX_LOG_FILE_SIZE:
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        new_name = f"logs_{timestamp}.json"
        os.rename(LOGS_FILE, new_name)
        print(f"Логи архивированы: {new_name}")


def save_logs(log_list):
    """Сохраняет список логов в LOGS_FILE с предварительной проверкой размера файла."""
    rotate_logs()
    with open(LOGS_FILE, "w", encoding="utf-8") as f:
        json.dump(log_list, f, ensure_ascii=False, indent=4)


# Загружаем сохранённые данные при старте приложения
active_email_config = load_config()
email_logs = load_logs()


# ============== Остальной функционал приложения ==============

def col_letter_to_index(col_letter):
    """
    Преобразует буквенное обозначение столбца (например, 'A' или 'b' или 'AA') в числовой индекс (0-индексация).
    """
    col_letter = col_letter.strip().upper()
    index = 0
    for char in col_letter:
        if 'A' <= char <= 'Z':
            index = index * 26 + (ord(char) - ord('A') + 1)
        else:
            raise ValueError("Некорректный символ в обозначении столбца")
    return index - 1


def send_email(smtp_config, recipient, subject, body, attachments=None):
    """
    Отправка одного письма, attachments — это список (filename, data).
    """
    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_config['email']
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))

        # NEW: прикрепляем все файлы из списка
        if attachments:
            for (filename, file_data) in attachments:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(file_data)
                encoders.encode_base64(part)
                part.add_header('Content-Disposition',
                                f'attachment; filename="{filename}"')
                msg.attach(part)

        with smtplib.SMTP_SSL(smtp_config['smtp_server'], smtp_config['smtp_port']) as server:
            server.login(smtp_config['email'], smtp_config['password'])
            server.send_message(msg)
        return True, "Sent successfully"
    except Exception as e:
        return False, str(e)


def send_emails_in_background(df, email_col, name_col, start_row, end_row,
                              subject, template, smtp_config, pause_seconds=0.0,
                              attachments=None):
    """
    Фоновая отправка писем, с задержкой pause_seconds и
    списком вложений attachments (каждый файл прикрепляется к письму).
    """
    total = end_row - start_row
    progress_info['total'] = total
    progress_info['sent'] = 0

    for idx in range(start_row, end_row):
        recipient = df.iat[idx, email_col]
        full_name = str(df.iat[idx, name_col]).strip()  # убеждаемся, что это строка

        # Замена плейсхолдеров:
        body = template
        if "{FIO}" in body:
            body = body.replace("{FIO}", full_name)
        if "{IO}" in body:
            words = full_name.split()
            if len(words) >= 3:
                io = words[0] + " " + words[2]
            else:
                io = full_name
            body = body.replace("{IO}", io)

        success, message = send_email(
            smtp_config,
            recipient,
            subject,
            body,
            attachments=attachments
        )

        log_entry = {
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'recipient': recipient,
            'status': 'Успешно' if success else 'Ошибка',
            'message': message
        }
        email_logs.append(log_entry)
        save_logs(email_logs)  # можно сохранять логи раз в несколько отправок для производительности
        progress_info['sent'] += 1

        # NEW: задержка между отправками
        if pause_seconds > 0 and idx < end_row - 1:
            time.sleep(pause_seconds)


@app.route("/", methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        provider = request.form.get('provider')
        try:
            # Получаем буквенное обозначение столбцов и преобразуем в индекс
            email_col = col_letter_to_index(request.form.get('email_col'))
            name_col = col_letter_to_index(request.form.get('name_col'))
            start_row = int(request.form.get('start_row')) - 1  # переводим в 0-индексацию
            num_emails = int(request.form.get('num_emails'))
        except Exception as e:
            flash("Неверный формат данных: " + str(e), "danger")
            return redirect(url_for('index'))

        # NEW: считываем паузу (секунды)
        try:
            pause_seconds = float(request.form.get('pause_seconds', 0))
        except:
            pause_seconds = 0

        subject = request.form.get('subject')
        template = request.form.get('template')

        # NEW: получаем все выбранные файлы
        attachment_files = request.files.getlist('attachment_files')
        attachments = []
        for f in attachment_files:
            if f and f.filename:  # пользователь действительно выбрал файл
                file_data = f.read()
                filename = f.filename
                attachments.append((filename, file_data))

        # Файл Excel
        excel_file = request.files.get('excel_file')
        if not excel_file:
            flash("Файл не выбран", "danger")
            return redirect(url_for('index'))

        try:
            df = pd.read_excel(excel_file)
        except Exception as e:
            flash("Ошибка при загрузке файла: " + str(e), "danger")
            return redirect(url_for('index'))

        if df.shape[1] <= max(email_col, name_col):
            flash("В указанных столбцах недостаточно данных", "danger")
            return redirect(url_for('index'))

        # Используем настройки из админки, если они заданы, иначе дефолт по провайдеру
        if active_email_config:
            smtp_config = active_email_config
        else:
            smtp_config = EMAIL_CONFIGS.get(provider)

        if smtp_config is None:
            flash("Неверный почтовый провайдер", "danger")
            return redirect(url_for('index'))

        total_rows = df.shape[0]
        end_row = min(start_row + num_emails, total_rows)
        if start_row >= total_rows:
            flash("Начальная строка больше общего числа строк в файле", "danger")
            return redirect(url_for('index'))

        # Запуск рассылки в отдельном потоке
        thread = threading.Thread(target=send_emails_in_background, args=(
            df, email_col, name_col, start_row, end_row, subject, template, smtp_config,
            pause_seconds,  # NEW
            attachments  # NEW
        ))
        thread.start()
        return redirect(url_for('progress_page'))
    return render_template("index.html")


@app.route("/progress")
def progress():
    # Возвращаем текущий статус рассылки в формате JSON
    return jsonify(progress_info)


@app.route("/progress_page")
def progress_page():
    return render_template("progress.html")


@app.route("/logs")
def logs():
    # Отображаем логи (последние записи первыми)
    return render_template("mail_logs.html", logs=list(reversed(email_logs)))


@app.route("/admin", methods=['GET', 'POST'])
def admin():
    global active_email_config
    if request.method == "POST":
        provider = request.form.get('provider')
        email = request.form.get('email')
        password = request.form.get('password')

        # Проверяем, есть ли такой провайдер в EMAIL_CONFIGS
        if provider in EMAIL_CONFIGS:
            active_email_config = EMAIL_CONFIGS[provider].copy()
            active_email_config['provider'] = provider  # сохраняем выбранный провайдер
            active_email_config['email'] = email
            active_email_config['password'] = password
            save_config(active_email_config)
            flash("Настройки обновлены и сохранены", "success")
        else:
            flash("Неверный провайдер", "danger")

        return redirect(url_for('admin'))

    # Если GET-запрос, рендерим шаблон
    return render_template("admin.html.jinja2", config=active_email_config)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
