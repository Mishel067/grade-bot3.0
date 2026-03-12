import telebot
import csv
import matplotlib
import io
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
import pandas as pd
import sqlite3
from io import BytesIO
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import PIL
load_dotenv()
TOKEN = os.getenv
valid = {'математика', 'русский', 'английский', 'физика', 'химия', 'биология', 'история', 'география', 'информатика', 'литература', 'обж', 'физкультура', 'музыка', 'рисование', 'технология'}
bot = telebot.TeleBot(TOKEN)
DB_PATH = 'grades.db'
def init_db():
  if not os.path.exists(DB_PATH):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE grades (
    user_id INTEGER,
    subject TEXT,
    grade INTEGER,
    timestamp TEXT
    )
    ''')
    conn.commit()
    conn.close()
init_db()
# === КОМАНДА /add ===
@bot.message_handler(commands=['add'])
def add_command(message):
  text = message.text.split()
  if len(text) < 3:
    bot.reply_to(message, "Пример: /add математика 5 4 3")
    return
  chat_id = message.chat.id
  subject = text[1]
  if subject.lower() not in valid:
    bot.reply_to(message, 'Разрешены: математика, русский, английский, физика, химия, биология, история, география, информатика, литература, обж, физкультура, музыка, рисование, технология')
    return
  try:
    grades = [int(x) for x in text[2:] if x.isdigit() and 1 <= int(x) <= 5]
    if not grades:
      bot.reply_to(message, "Нет оценок от 1 до 5")
      return
    with sqlite3.connect(DB_PATH) as conn:
      cursor = conn.cursor()
      now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
      for g in grades:
        cursor.execute(
        'INSERT INTO grades (user_id, subject, grade, timestamp) VALUES (?, ?, ?, ?)',(chat_id, subject, g, now))
      bot.reply_to(message, f"✅ Добавлено {len(grades)} оценок по '{subject}'")
  except Exception as e:
    bot.reply_to(message, f"❌ Ошибка: {e}")
# === КОМАНДА /stats ===
@bot.message_handler(commands=['stats'])
def stats_command(message):
  chat_id = message.chat.id
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  cursor.execute("SELECT COUNT(*), AVG(grade) FROM grades WHERE user_id = ?", (chat_id,))
  row = cursor.fetchone()  # ← УБРАТЬ fetchall()!

  if row is None or row[0] == 0:
    bot.reply_to(message, 'Нет оценок')
    conn.close()
    return
  total, avg = row
  avg = round(avg, 2) if avg else 0.0
  df = pd.read_sql('SELECT * FROM grades', conn)
  df['date'] = pd.to_datetime(df['timestamp'])
  df['month'] = df['date'].dt.to_period('M')
  monthly_avg = df.groupby('month')['grade'].mean().round(2)
  today = datetime.now().strftime('%Y-%m-%d')
  if total == 0:
    bot.reply_to(message, "Нет оценок. Сначала добавь через /add")
    conn.close()
    return
  cursor.execute("""
  SELECT subject, COUNT(*), AVG(grade)
  FROM grades
  WHERE user_id = ?
  GROUP BY subject
  ORDER BY subject
  """, (chat_id,))
  subjects = cursor.fetchall()
  conn.close()
  if df.empty:
    bot.reply_to(message, 'Нет данных для анализа.')
    return
  plt.figure(figsize=(8, 4))
  monthly_avg.plot(kind='bar', color='skyblue')
  plt.title("Средний балл по месяцам")
  plt.ylabel('Балл')
  plt.xticks(rotation=45)
  plt.tight_layout()
  buf = BytesIO()
  plt.savefig(buf, format='png')
  buf.seek(0)
  bot.send_photo(chat_id, buf)
  buf.close()
  plt.close()
  msg = f"📊 Статистика:\nВсего оценок: {total}\nСредний балл: {avg:.2f}\n\nПо предметам:\n"
  for subj, cnt, s_avg in subjects:
    msg += f"• ✅ {subj}: {s_avg:.2f} ({cnt} оценок)\n"
  msg += '\n📊 Средний балл по месяцам:\n'
  for month, avg in monthly_avg.items():
    msg += f'• ✅ {month}: {avg}\n'
  bot.send_message(chat_id, msg) # ← ВАЖНО: не reply_to, а send_message
@bot.message_handler(commands=['start'])
def start_command(message):
  bot.reply_to(message, '👋 Привет! Я GradeBot - твой школьный помощник по оценкам.\n\n Команды: \n•/insight - твои инсайты\n •/import - выгрузить оценки в базу\n• /add предмет оценка - добавить оценку\n• /stats - показать средний балл\n• /export - скачать CSV файл\n•/graph - присылает график твоих оценок\n•/help или /about - помощь с GradeBot\n\nУдачи в учёбе!💯')
@bot.message_handler(commands=['export'])
def export_command(message):
  chat_id = message.chat.id
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  cursor.execute("SELECT subject, grade, timestamp FROM grades WHERE user_id = ?", (chat_id,))
  rows = cursor.fetchall()
  conn.close()
  if not rows:
    bot.reply_to(message,'📎 У тебя пока нет оценок для экспорта.')
    return
  output = io.StringIO()
  writer = csv.writer(output)
  writer.writerow(['subject', 'grade', 'timestamp'])
  writer.writerows(rows)
  output.seek(0)
  csv_data = output.getvalue().encode('utf-8-sig')
  bot.send_document(
      message.chat.id,
      io.BytesIO(csv_data),
      caption='📤 Твои оценки (CSV)',
      visible_file_name ='оценки.csv'
  )
@bot.message_handler(commands=['help', 'about'])
def help_command(message):
  bot.reply_to(message,'❓🤖 Помощь по GradeBot\n\n/insight\n→ Твои инсайты\n/add предмет оценка\n→ Добавить одну или несколько оценок.\nПример: /add математика 5 или: /add русский 4 5 3\n\n/today\n→ Показать оценки по дням\n\n/stats\n→ Показать средний балл по всем предметам.\n\n/import - затем присылай csv и все оценки выгрузятся в базу\n\n/export\n→ Получить файл с оценками (CSV).\n\n/graph\n→ Присылает график твоих оценок\n\n⚠️ Советы:\n• Предмет пиши строчными буквами (без заглавных).\n• Оценки - только цифры от 1 до 5.\n• Бот не работает ночью - как и ты! 😴')
@bot.message_handler(commands=['graph'])
def graph_command(message):
  chat_id = message.chat.id
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  cursor.execute('SELECT grade  FROM grades WHERE user_id = ? ORDER BY timestamp', (chat_id,))
  rows = cursor.fetchall()
  conn.close()
  if not rows:
    bot.reply_to(message,'📎 У тебя пока нет оценок для графика.')
    return
  grades = [row[0] for row in rows]
  x = list(range(1, len(grades) + 1))
  y = grades
  plt.figure(figsize=(6,4))
  plt.plot(x, y, 'o-', color='b')
  plt.title("Твои оценки", fontsize=14)
  plt.xlabel("№ оценки")
  plt.ylabel("Балл")
  plt.ylim(0,5.5)
  plt.yticks([1,2,3,4,5])
  plt.grid(True)
  buf = BytesIO()
  plt.savefig(buf, format='png', bbox_inches='tight')
  buf.seek(0)
  plt.close()
  bot.send_photo(chat_id, buf, caption="График 📈")
@bot.message_handler(commands=['import'])
def import_command(message):
  bot.reply_to(message, 'Пришлите CSV-файл с колонками: subject, grade, timestamp')
@bot.message_handler(content_types=['document'])
def document_command(message):
  if not message.document:
    bot.reply_to(message, '❌ Не получилось прочитать файл. Пришлите .csv напрямую.')
  if not message.document.file_name.endswith('.csv'):
    bot.reply_to(message,'❌ Нужен файл .csv' )
    return
  try:
    file_info = bot.get_file(message.document.file_id)
    download_file = bot.download_file(file_info.file_path)
    csv_data = download_file.decode("utf-8")
    df = pd.read_csv(io.StringIO(csv_data), skipinitialspace=True)
    if 'subject' not in df.columns or 'grade' not in df.columns or 'timestamp' not in df.columns:
      bot.reply_to(message, 'В CSV должны быть колонки: subject, grade, timestamp')
      return
    df = df[['subject', 'grade', 'timestamp']]
    df = df[pd.to_numeric(df['grade'], errors='coerce').between(1, 5)]
    df = df.dropna(subset=['grade'])
    if df.empty:
      bot.reply_to(message, 'Нет корректных данных для импорта')
      return
    chat_id = message.chat.id
    conn = sqlite3.connect('grades.db')
    cursor = conn.cursor()
    for _, row in df.iterrows():
      cursor.execute(
        'INSERT INTO grades (user_id, subject, grade, timestamp) VALUES (?, ?, ?, ?)',
        (chat_id, str(row['subject']), int(row['grade']), row['timestamp'])
      )
    conn.commit()
    conn.close()
    bot.reply_to(message, f'✅ Импортировано {len(df)} оценок')
  except Exception as e:
    bot.reply_to(message, f'❌ Ошибка при импорте: {e}')

def todas(message):
  chat_id = message.chat.id
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  today = datetime.now().strftime("%Y-%m-%d")
  cursor.execute("""
  SELECT subject, grade
  FROM grades
  WHERE user_id = ?
  AND timestamp IS NOT NULL
  AND strftime('%Y-%m-%d', timestamp) = ?
  """, (chat_id, today))
  rows = cursor.fetchall()
  conn.close()
  return rows
@bot.message_handler(commands=['today'])
def send_today_stats(message):
  grades = todas(message)
  if not grades:
    bot.reply_to(message, 'Сегодня еще нет оценок.')
  else:
    text = '📚 Сегодня:\n'
    for subj, gr in grades:
      text += f'• {subj}: {gr}\n'
    bot.reply_to(message, text)
@bot.message_handler(commands=['insight'])
def insight(message):
  chat_id = message.chat.id
  try:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql('SELECT * FROM grades', conn)
    conn.close()

    if df.empty:
      bot.reply_to(message, 'Нет данных для анализа.')
      return

# Подготовка данных
    df['date'] = pd.to_datetime(df['timestamp'])
    df = df.dropna(subset=['date'])

# Анализ по дням недели
    df['weekday'] = df['date'].dt.dayofweek
    weekday_names = {0: 'Понедельник', 1: 'Вторник', 2: 'Среда',
3: 'Четверг', 4: 'Пятница', 5: 'Суббота', 6: 'Воскресенье'}
    df['weekday_name'] = df['weekday'].map(weekday_names)

    weekday_avg = df.groupby('weekday_name')['grade'].mean().round(2).dropna()

# Определяем лучший и худший день
    if len(weekday_avg) > 0:
      if len(weekday_avg) == 1:
        best = worst = weekday_avg.index[0]
        bestv = worstv = float(weekday_avg.iloc[0])
      else:
        best = weekday_avg.idxmax()
        worst = weekday_avg.idxmin()
        bestv = float(weekday_avg[best])
        worstv = float(weekday_avg[worst])

# Анализ по месяцам
    df['month'] = df['date'].dt.to_period('M')
    monthly_avg = df.groupby('month')['grade'].mean().round(2)

# Анализ по предметам
    subject_stats = df.groupby('subject')['grade'].agg(mean='mean', std='std', count='count').round(2)
    subject_stats = subject_stats.sort_values('std')

# Анализ по неделям
    df['week'] = df['date'].dt.isocalendar().week
    weekly_avg = df.groupby('week')['grade'].mean().round(2)

# График стабильности по предметам
    weeks = weekly_avg.index.astype(int).tolist()
    values = weekly_avg.values.tolist()

    plt.figure(figsize=(8, 4))
    subjects = subject_stats.index.astype(str).tolist()
    stds = subject_stats['std'].fillna(0).round(2).tolist()
    plt.bar(subjects, stds, color='lightgray')
    plt.title('Стабильность оценок по предметам')
    plt.ylabel('Стандартное отклонение (σ)')
    plt.xticks(rotation=45)
    plt.tight_layout()

    buf1 = BytesIO()
    plt.savefig(buf1, format='png')
    buf1.seek(0)
    plt.close()

# График динамики по неделям
    plt.figure(figsize=(8, 4))
    plt.plot(weeks, values, marker='o', color='darkgreen')
    plt.xticks(weeks)
    plt.title('Динамика среднего балла по неделям')
    plt.xlabel('Неделя года')
    plt.ylabel('Средний балл')
    plt.grid(True)
    plt.tight_layout()

    buf2 = BytesIO()
    plt.savefig(buf2, format='png')
    buf2.seek(0)
    plt.close()

# Формирование текстового отчета
    growth = ''
    if len(monthly_avg) >= 2:
      last = monthly_avg.iloc[-1]
      prev = monthly_avg.iloc[-2]
      if prev > 0:
        growth = f' ({round((last - prev)/prev*100, 1)}%)'

    text = f"📊 Инсайт по успеваемости:\n\n"
    text += f"📈 Лучший день: {best} (средний балл {bestv})\n"
    text += f"📉 Худший день: {worst} (средний балл {worstv})\n"
    text += f"📅 Текущий месяц: {monthly_avg.iloc[-1]}{growth}\n"
    text += f"📚 Всего оценок: {len(df)}"

# Отправка результатов
    bot.send_photo(chat_id, buf1)
    bot.send_photo(chat_id, buf2)
    bot.reply_to(message, text)

  except Exception as e:
    bot.reply_to(message, f'Ошибка: {str(e)}')
import sqlite3

conn = sqlite3.connect('grades.db')
cur = conn.cursor()

# Найдём все записи с "026", "027", "028" в timestamp
cur.execute("SELECT rowid, timestamp FROM grades WHERE timestamp LIKE '02%' OR timestamp LIKE '026%'")
rows = cur.fetchall()
print("Удалить эти записи:")
for r in rows:
  print(r)

conn.close()


conn = sqlite3.connect('grades.db')
cur = conn.cursor()

bot.polling(none_stop=True)