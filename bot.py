import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

TOKEN = "8990176397:AAFeYA_iaidYzOmTfM-4x2J40Hj6vi8QKUY"
ADMIN_ID = 8569472160

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

class Form(StatesGroup):
    name = State()
    contact = State()
    text = State()

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📝 Оставить заявку")],
        [KeyboardButton(text="ℹ️ Помощь")]
    ],
    resize_keyboard=True
)

cancel_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ Отмена")]],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        "Я бот для приёма заявок.\n"
        "Нажми кнопку ниже, чтобы оставить заявку.",
        reply_markup=main_kb
    )

@dp.message(Command("help"))
@dp.message(F.text == "ℹ️ Помощь")
async def help_cmd(message: types.Message):
    await message.answer(
        "Нажми «📝 Оставить заявку» и ответь на вопросы.\n"
        "После этого заявка придёт администратору."
    )

@dp.message(F.text == "📝 Оставить заявку")
async def start_form(message: types.Message, state: FSMContext):
    await state.set_state(Form.name)
    await message.answer("Как вас зовут?", reply_markup=cancel_kb)

@dp.message(F.text == "❌ Отмена")
async def cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Заявка отменена.", reply_markup=main_kb)

@dp.message(Form.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(Form.contact)
    await message.answer("Укажите контакт (телефон или @username):")

@dp.message(Form.contact)
async def process_contact(message: types.Message, state: FSMContext):
    await state.update_data(contact=message.text)
    await state.set_state(Form.text)
    await message.answer("Опишите вашу заявку:")

@dp.message(Form.text)
async def process_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    text = (
        f"🆕 <b>Новая заявка!</b>\n\n"
        f"👤 Имя: {data['name']}\n"
        f"📞 Контакт: {data['contact']}\n"
        f"📝 Заявка: {message.text}\n\n"
        f"От: @{message.from_user.username or 'без username'}\n"
        f"ID: {message.from_user.id}"
    )

    try:
        await bot.send_message(ADMIN_ID, text, parse_mode="HTML")
        await message.answer("✅ Заявка успешно отправлена!", reply_markup=main_kb)
    except Exception as e:
        await message.answer(f"Ошибка отправки: {e}", reply_markup=main_kb)

@dp.message()
async def echo(message: types.Message):
    await message.answer("Используй кнопки меню 👇", reply_markup=main_kb)

async def main():
    print("Бот для приёма заявок запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())