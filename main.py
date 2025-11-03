import asyncio
import logging
from datetime import datetime
from aiogram import F
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from quiz_data import quiz_data
from consts import API_TOKEN
from database import get_quiz_index, update_quiz_index, create_table, save_quiz_result, get_leaderboard, get_user_stats

logging.basicConfig(level=logging.INFO)

user_answers = {}
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

async def generate_option_keyboard(answer_options, right_answer):
  builder = InlineKeyboardBuilder()
  for option in answer_options:
    builder.add(types.InlineKeyboardButton(
        text=option,
        callback_data='right_answer' if option == right_answer else 'wrong_answer'
    ))

  builder.adjust(1)
  return builder.as_markup()

@dp.callback_query(F.data == "right_answer")
async def right_answer(callback: types.CallbackQuery):
  await remove_buttons(callback)
  user_id = callback.from_user.id
  if user_id not in user_answers:
    user_answers[user_id] = {'correct': 0, 'total': 0}
  user_answers[user_id]['correct'] += 1
  user_answers[user_id]['total'] += 1
  button_text = await get_clicked_button_text(callback)
  await callback.message.answer(f"Верно! Вы выбрали: {button_text}")
  current_question_index = await get_quiz_index(callback.from_user.id)
  current_question_index += 1
  await update_quiz_index(callback.from_user.id, current_question_index)
  await check_for_end(current_question_index, callback)

@dp.callback_query(F.data == "wrong_answer")
async def wrong_answer(callback: types.CallbackQuery):
  await remove_buttons(callback)
  user_id = callback.from_user.id
  if user_id not in user_answers:
    user_answers[user_id] = {'correct': 0, 'total': 0}
  user_answers[user_id]['total'] += 1
  button_text = await get_clicked_button_text(callback)
  current_question_index = await get_quiz_index(callback.from_user.id)
  correct_option_index = quiz_data[current_question_index]['correct_option']
  correct_answer = quiz_data[current_question_index]['options'][correct_option_index]
  await callback.message.answer(f"Неправильно. Вы выбрали: {button_text}\n Правильный ответ: {correct_answer}")
  current_question_index += 1
  await update_quiz_index(callback.from_user.id, current_question_index)
  await check_for_end(current_question_index, callback)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
  builder = ReplyKeyboardBuilder()
  builder.add(types.KeyboardButton(text="🎮 Начать игру"))
  builder.add(types.KeyboardButton(text="📊 Моя статистика"))
  builder.add(types.KeyboardButton(text="🏆 Таблица лидеров"))
  builder.adjust(2)
  await message.answer("Добро пожаловать в квиз!\n" "Проверьте свои знания Python и посоревнуйтесь с другими!", reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(F.text.in_(['Начать игру', '🎮 Начать новый квиз', "🎮 Начать игру"]))
@dp.message(Command('quiz'))
async def cmd_quiz(message: types.Message):
  await message.answer("Давай начнем квиз!")
  await new_quiz(message)

@dp.message(F.text == '📊 Моя статистика')
async def show_my_stats(message: types.Message):
  user_id = message.from_user.id
  stats = await get_user_stats(user_id)
  if stats:
    result_message = (
      f"📊 Ваша статистика:\n"
      f"✅ Правильных ответов: {stats['correct_answers']}/{stats['total_questions']}\n"
      f"🏆 Процент правильных: {stats['score']}%\n"
      f"⭐ Оценка: {get_grade(stats['score'])}\n"
      f"📅 Последняя попытка: {stats['completed_at'][:16]}"
    )
  else:
    result_message = "У вас еще нет результатов квиза. Пройдите квиз сначала!"
  await message.answer(result_message)

@dp.message(F.text == "🏆 Таблица лидеров")
async def show_leaderboard(message: types.Message):
  leaderboard = await get_leaderboard(limit = 10)
  if leaderboard:
    leaderboard_text = "🏆 Таблица лидеров:\n\n"
    for i, player in enumerate(leaderboard, 1):
      medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
      leaderboard_text += (
        f"{medal} {player['username']} - {player['score']}% "
        f"({player['correct_answers']} / {player['total_questions']})\n"   
      )
  else:
    leaderboard_text = "🏆 Пока никто не прошел квиз. Будьте первым!"

  await message.answer(leaderboard_text)

async def remove_buttons(callback):
  await callback.bot.edit_message_reply_markup(
      chat_id = callback.from_user.id,
      message_id = callback.message.message_id,
      reply_markup = None
  )

async def get_clicked_button_text(callback: types.CallbackQuery):
  try: 
    message = callback.message
    if message.reply_markup and message.reply_markup.inline_keyboard:
      for row in message.reply_markup.inline_keyboard:
        for button in row:
          if button.callback_data == callback.data:
            return button.text
  except Exception as e:
    print(f'Ошибка при получении текста кнопки: {e}')
  return "вариант"

async def check_for_end(current_question_index, callback):
  if current_question_index < len(quiz_data):
    await get_question(callback.message, callback.from_user.id)
  else:
    user_id = callback.from_user.id
    username = callback.from_user.username or callback.from_user.first_name
    user_stats = user_answers.get(user_id, {'correct': 0, 'total': 0})
    correct_answers = user_stats['correct']
    total_questions = len(quiz_data)

    await save_quiz_result(user_id, username, total_questions, correct_answers)
    score = int((correct_answers / total_questions) * 100)
    result_message = (
      f"🎉 Квиз завершен!\n"
      f"📊 Ваш результат:\n"
      f"✅ Правильных ответов: {correct_answers}/{total_questions}\n"
      f"🏆 Процент правильных: {score}%\n"
      f"⭐ Оценка: {get_grade(score)}"
    )

    await callback.message.answer(result_message)
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="📊 Моя статистика"))
    builder.add(types.KeyboardButton(text="🏆 Таблица лидеров"))
    builder.add(types.KeyboardButton(text="🎮 Начать новый квиз"))
    builder.adjust(2)

    await callback.message.answer("Что хотите делать дальше?", reply_markup=builder.as_markup(resize_keyboard=True))
    if user_id in user_answers:
      del user_answers[user_id]

    await update_quiz_index(callback.from_user.id, 0)

def get_grade(score):
  if score >= 90:
      return "Отлично! 🎯"
  elif score >= 70:
      return "Хорошо! 👍"
  elif score >= 50:
      return "Удовлетворительно 👌"
  else:
      return "Нужно подтянуть знания 📚"

async def get_question(message, user_id):
  current_question_index = await get_quiz_index(user_id)
  if current_question_index >= len(quiz_data):
    await message.answer("Квиз завершен!")
    return
    
  correct_index = quiz_data[current_question_index]['correct_option']
  opts = quiz_data[current_question_index]['options']
  kb = await generate_option_keyboard(opts, opts[correct_index])
  await message.answer(f"{quiz_data[current_question_index]['question']}", reply_markup=kb)

async def new_quiz(message):
  user_id = message.from_user.id
  current_question_index = 0
  await update_quiz_index(user_id, current_question_index)
  if user_id in user_answers:
    del user_answers[user_id]

  await get_question(message, user_id)

async def main():
  await create_table()
  await dp.start_polling(bot)

if __name__ == "__main__":
  asyncio.run(main())