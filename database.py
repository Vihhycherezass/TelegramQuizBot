import aiosqlite
from consts import DB_NAME

async def create_table():
  async with aiosqlite.connect(DB_NAME) as db:
    await db.execute('''CREATE TABLE IF NOT EXISTS quiz_state (user_id INTEGER PRIMARY KEY, question_index INTEGER)''')
    await db.execute('''CREATE TABLE IF NOT EXISTS quiz_stats (user_id INTEGER, username TEXT, total_questions INTEGER, correct_answers INTEGER, score INTEGER, completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    await db.commit()

async def get_quiz_index(user_id):
  async with aiosqlite.connect(DB_NAME) as db:
    async with db.execute('SELECT question_index FROM quiz_state WHERE user_id = (?)', (user_id, )) as cursor:
      results = await cursor.fetchone()
      if results is not None:
        return results[0]
      else: 
        return 0

async def update_quiz_index(user_id, index):
  async with aiosqlite.connect(DB_NAME) as db:
    await db.execute('INSERT OR REPLACE INTO quiz_state (user_id, question_index) VALUES (?, ?)', (user_id, index))
    await db.commit()

async def save_quiz_result(user_id: int, username: str, total_questions: int, correct_answers: int):
  score = int((correct_answers / total_questions) * 100) if total_questions > 0 else 0

  async with aiosqlite.connect(DB_NAME) as db:
    await db.execute('DELETE FROM quiz_stats WHERE user_id = ?', (user_id,))
    await db.execute('''INSERT INTO quiz_stats (user_id, username, total_questions, correct_answers, score) VALUES (?, ?, ?, ?, ?)''', (user_id, username, total_questions, correct_answers, score))
    await db.commit()

async def get_user_stats(user_id: int):
  async with aiosqlite.connect(DB_NAME) as db:
    async with db.execute('''SELECT total_questions, correct_answers, score, completed_at FROM quiz_stats WHERE user_id = ?''', (user_id,)) as cursor:
      result = await cursor.fetchone()
      if result:
        return {
          'total_questions': result[0],
          'correct_answers': result[1],
          'score': result[2],
          'completed_at': result[3]
        }
      
      return None
    
async def get_leaderboard(limit: int = 10):
  async with aiosqlite.connect(DB_NAME) as db:
    async with db.execute('''SELECT username, total_questions, correct_answers, score, completed_at FROM quiz_stats ORDER BY score DESC, completed_at DESC LIMIT ?''', (limit,)) as cursor:
      results = await cursor.fetchall()
      return [{
        'username': row[0],
        'total_questions': row[1],
        'correct_answers': row[2],
        'score': row[3],
        'completed_at': row[4]
      } for row in results]