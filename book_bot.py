import logging
import random
from typing import Dict, List
from dataclasses import dataclass, asdict
import json
import os
import sys
import asyncio
import html

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler
)
from telegram.error import TimedOut, BadRequest

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = "7968778030:AAGOCRvTo65Mb_H5Fbsv39V_0ZVC_plYdYk"
ADMIN_ID = 7744826474

# Состояния для ConversationHandler
NAME, BOOK, COMMENT, CONFIRM = range(4)

# Файл для хранения данных
DATA_FILE = "participants.json"

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== МОДЕЛИ ДАННЫХ ====================
@dataclass
class Participant:
    user_id: int
    username: str
    name: str
    desired_book: str
    comment: str
    assigned_to: int = None  # ID участника, которому нужно дарить

class BotData:
    def __init__(self, data_file: str = DATA_FILE):
        self.data_file = data_file
        self.participants: Dict[int, Participant] = self.load_data()
    
    def save_data(self):
        """Сохраняет данные в JSON файл"""
        data = {
            str(pid): asdict(p) 
            for pid, p in self.participants.items()
        }
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def load_data(self) -> Dict[int, Participant]:
        """Загружает данные из JSON файла"""
        if not os.path.exists(self.data_file):
            return {}
        
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            participants = {}
            for pid_str, p_data in data.items():
                # Конвертируем user_id из строки в int
                p_data['user_id'] = int(p_data['user_id'])
                if 'assigned_to' in p_data and p_data['assigned_to']:
                    p_data['assigned_to'] = int(p_data['assigned_to'])
                participants[int(pid_str)] = Participant(**p_data)
            
            return participants
        except Exception as e:
            logger.error(f"Ошибка загрузки данных: {e}")
            return {}
    
    def add_participant(self, user_id: int, username: str, name: str, 
                       desired_book: str, comment: str = "") -> Participant:
        """Добавляет нового участника"""
        participant = Participant(
            user_id=user_id,
            username=username or "",
            name=name,
            desired_book=desired_book,
            comment=comment
        )
        self.participants[user_id] = participant
        self.save_data()
        return participant
    
    def clear_user_data(self, user_id: int) -> bool:
        """Удаляет данные пользователя"""
        if user_id in self.participants:
            del self.participants[user_id]
            self.save_data()
            return True
        return False
    
    def get_all_participants(self) -> List[Participant]:
        """Возвращает список всех участников"""
        return list(self.participants.values())
    
    def clear_all_data(self):
        """Очищает все данные"""
        self.participants.clear()
        self.save_data()

# Инициализация хранилища данных
bot_data = BotData()

def escape_markdown(text: str) -> str:
    """Экранирует спецсимволы Markdown"""
    if not text:
        return ""
    # Экранируем символы Markdown
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

# ==================== КОМАНДЫ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /start"""
    try:
        user = update.effective_user
        
        welcome_text = (
            "«Кітап-гәп»-қа қош келдіңіз!📚\n"
            "Деректерді толтырыңыз.\n\n"
            "Сіздің есіміңіз:"
        )
        
        # Проверяем, есть ли уже данные пользователя
        if user.id in bot_data.participants:
            keyboard = [
                [InlineKeyboardButton("✏️ Заполнить заново", callback_data="restart")],
                [InlineKeyboardButton("✅ Мои данные верны", callback_data="keep")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "У вас уже есть сохраненные данные. Что вы хотите сделать?",
                reply_markup=reply_markup
            )
            return CONFIRM
        
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
        return NAME
    except TimedOut:
        logger.warning("Таймаут при отправке сообщения /start")
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Ошибка в команде /start: {e}")
        return ConversationHandler.END

async def handle_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка имени пользователя"""
    try:
        name = update.message.text.strip()
        
        if len(name) < 2:
            await update.message.reply_text("Пожалуйста, введите имя (минимум 2 символа)")
            return NAME
        
        context.user_data['name'] = name
        
        await update.message.reply_text(
            "Қандай кітапты сыйға қалайсыз?",
            parse_mode='Markdown'
        )
        return BOOK
    except Exception as e:
        logger.error(f"Ошибка при обработке имени: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте снова /start")
        return ConversationHandler.END

async def handle_book(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка желаемой книги"""
    try:
        book = update.message.text.strip()
        
        if len(book) < 3:
            await update.message.reply_text("Пожалуйста, укажите название книги (минимум 3 символа)")
            return BOOK
        
        context.user_data['desired_book'] = book
        
        keyboard = [
            [InlineKeyboardButton("Пропустить", callback_data="skip_comment")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Пікір қалдыра аласыз:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return COMMENT
    except Exception as e:
        logger.error(f"Ошибка при обработке книги: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте снова /start")
        return ConversationHandler.END

async def handle_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка комментария"""
    try:
        comment = update.message.text.strip()
        context.user_data['comment'] = comment
        
        await show_summary(update, context)
        return CONFIRM
    except Exception as e:
        logger.error(f"Ошибка при обработке комментария: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте снова /start")
        return ConversationHandler.END

async def skip_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пропуск комментария"""
    try:
        query = update.callback_query
        await query.answer()
        
        context.user_data['comment'] = ""
        
        # Передаем query напрямую в show_summary
        await show_summary(query, context, is_callback=True)
        return CONFIRM
    except Exception as e:
        logger.error(f"Ошибка при пропуске комментария: {e}")
        return ConversationHandler.END

async def show_summary(update, context: ContextTypes.DEFAULT_TYPE, is_callback: bool = False):
    """Показывает сводку данных"""
    try:
        user_data = context.user_data
        
        name = escape_markdown(user_data.get('name', 'Не указано'))
        book = escape_markdown(user_data.get('desired_book', 'Не указано'))
        comment = escape_markdown(user_data.get('comment', 'Не указано'))
        
        summary_text = (
            "📋 **Сіздің деректеріңіз:**\n\n"
            f"👤 **Есіміңіз:** {name}\n"
            f"📚 **Сіз қалайтын кітап:** {book}\n"
            f"💬 **Пікіріңіз:** {comment}\n\n"
            "Деректерді жіберу үшін **/send** батырмасын басыңыз."
        )
        
        if is_callback:
            # Для callback_query используем update.callback_query
            await update.edit_message_text(
                text=summary_text,
                parse_mode='Markdown'
            )
        else:
            # Для обычного сообщения используем update.message
            await update.message.reply_text(
                text=summary_text,
                parse_mode='Markdown'
            )
    except BadRequest as e:
        logger.error(f"Ошибка форматирования Markdown: {e}")
        # Отправляем без форматирования
        if is_callback:
            await update.edit_message_text(
                text="📋 Сіздің деректеріңіз:\n\n"
                     f"👤 Есіміңіз: {user_data.get('name', 'Не указано')}\n"
                     f"📚 Сіз қалайтын кітап: {user_data.get('desired_book', 'Не указано')}\n"
                     f"💬 Пікіріңіз: {user_data.get('comment', 'Не указано')}\n\n"
                     "Деректерді жіберу үшін /send батырмасын басыңыз."
            )
        else:
            await update.message.reply_text(
                text="📋 Сіздің деректеріңіз:\n\n"
                     f"👤 Есіміңіз: {user_data.get('name', 'Не указано')}\n"
                     f"📚 Сіз қалайтын кітап: {user_data.get('desired_book', 'Не указано')}\n"
                     f"💬 Пікіріңіз: {user_data.get('comment', 'Не указано')}\n\n"
                     "Деректерді жіберу үшін /send батырмасын басыңыз."
            )
    except Exception as e:
        logger.error(f"Ошибка при показе сводки: {e}")

async def submit_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /send (жіберу)"""
    try:
        user = update.effective_user
        user_data = context.user_data
        
        # Проверяем, есть ли все необходимые данные
        required_fields = ['name', 'desired_book']
        missing_fields = [field for field in required_fields if field not in user_data]
        
        if missing_fields:
            await update.message.reply_text(
                "Пожалуйста, сначала заполните все данные через /start"
            )
            return
        
        # Сохраняем данные
        participant = bot_data.add_participant(
            user_id=user.id,
            username=user.username,
            name=user_data['name'],
            desired_book=user_data['desired_book'],
            comment=user_data.get('comment', '')
        )
        
        # Очищаем временные данные
        context.user_data.clear()
        
        await update.message.reply_text(
            "Спасибо! Ваши данные сохранены ✅\n"
            "Ожидайте проведения жеребе."
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке данных: {e}")
        await update.message.reply_text("Произошла ошибка при сохранении данных")

async def lottery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /lottery (жеребе) (только для админа)"""
    try:
        user = update.effective_user
        
        if user.id != ADMIN_ID:
            await update.message.reply_text("Эта команда доступна только администратору")
            return
        
        participants = bot_data.get_all_participants()
        
        if len(participants) < 2:
            await update.message.reply_text(
                f"Жеребе тастауға қатысушылар жеткіліксіз. "
                f"Қатысушылар саны: {len(participants)}"
            )
            return
        
        # Проверяем, была ли уже жеребьевка
        assigned_count = sum(1 for p in participants if p.assigned_to)
        if assigned_count > 0:
            keyboard = [
                [InlineKeyboardButton("🔄 Қайтадан өткізу", callback_data="relottery")],
                [InlineKeyboardButton("✖️ Жою", callback_data="cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "Жеребе қазір өткізілді. Қайтадан өткізу керек пе?",
                reply_markup=reply_markup
            )
            return
        
        # Проводим жеребьевку
        result = perform_lottery(participants)
        
        if not result:
            await update.message.reply_text("Ошибка при проведении жеребьевки")
            return
        
        # Отправляем результаты каждому участнику
        sent_count = 0
        for participant in participants:
            try:
                assigned_participant = bot_data.participants[participant.assigned_to]
                
                name_escaped = escape_markdown(assigned_participant.name)
                book_escaped = escape_markdown(assigned_participant.desired_book)
                comment_escaped = escape_markdown(assigned_participant.comment) if assigned_participant.comment else ""
                
                message_text = (
                    "🎲 **Жеребе нәтижесі!**\n\n"
                    f"Сізге осы оқырман түсті **{name_escaped}**\n\n"
                    f"📖 **Оқырман қалайтын кітап:**\n"
                    f"_{book_escaped}_\n\n"
                )
                
                if assigned_participant.comment:
                    message_text += f"💬 **Пікір:**\n_{comment_escaped}_"
                
                await context.bot.send_message(
                    chat_id=participant.user_id,
                    text=message_text,
                    parse_mode='Markdown'
                )
                sent_count += 1
                
            except BadRequest as e:
                logger.error(f"Ошибка Markdown при отправке сообщения пользователю {participant.user_id}: {e}")
                # Отправляем без форматирования
                await context.bot.send_message(
                    chat_id=participant.user_id,
                    text=f"🎲 Жеребе нәтижесі!\n\n"
                         f"Сізге осы оқырман түсті: {assigned_participant.name}\n\n"
                         f"📖 Ол алғысы келетін кітап:\n"
                         f"{assigned_participant.desired_book}\n\n" +
                         (f"💬 Пікір:\n{assigned_participant.comment}" if assigned_participant.comment else "")
                )
                sent_count += 1
                
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение пользователю {participant.user_id}: {e}")
        
        bot_data.save_data()
        
        await update.message.reply_text(
            f"Жеребе аяқталды!\n"
            f"Қатысушылар саны: {len(participants)}\n"
            f"Хабарлар жіберілді: {sent_count}"
        )
    except Exception as e:
        logger.error(f"Ошибка при проведении жеребьевки: {e}")
        await update.message.reply_text("Произошла ошибка при проведении жеребьевки")

def perform_lottery(participants: List[Participant]) -> bool:
    """Проводит жеребьевку"""
    try:
        # Создаем список ID участников
        participant_ids = [p.user_id for p in participants]
        
        # Перемешиваем список
        shuffled_ids = participant_ids.copy()
        random.shuffle(shuffled_ids)
        
        # Создаем пары (каждый дарит следующему)
        assignments = {}
        n = len(shuffled_ids)
        
        for i in range(n):
            giver_id = shuffled_ids[i]
            receiver_id = shuffled_ids[(i + 1) % n]
            assignments[giver_id] = receiver_id
        
        # Назначаем пары
        for giver_id, receiver_id in assignments.items():
            bot_data.participants[giver_id].assigned_to = receiver_id
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при жеребьевке: {e}")
        return False

async def list_participants(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /list (тізім) (только для админа)"""
    try:
        user = update.effective_user
        
        if user.id != ADMIN_ID:
            await update.message.reply_text("Эта команда доступна только администратору")
            return
        
        participants = bot_data.get_all_participants()
        
        if not participants:
            await update.message.reply_text("Участников пока нет")
            return
        
        # Формируем список участников БЕЗ Markdown
        message_lines = ["📋 Қатысушылар тізімі:\n"]
        
        for i, participant in enumerate(participants, 1):
            assigned_info = ""
            if participant.assigned_to and participant.assigned_to in bot_data.participants:
                assigned_to_participant = bot_data.participants[participant.assigned_to]
                assigned_info = f" → 🎁 сыйлайды: {assigned_to_participant.name}"
            
            username = participant.username or "нет"
            book_title = participant.desired_book.replace('_', '\\_').replace('*', '\\*').replace('`', '\\`')
            
            message_lines.append(
                f"{i}. {participant.name} (@{username})"
                f"{assigned_info}\n"
                f"   📖: {book_title}\n"
            )
        
        # Разбиваем сообщение если слишком длинное
        message_text = "\n".join(message_lines)
        
        try:
            # Пробуем отправить с Markdown
            await update.message.reply_text(
                message_text,
                parse_mode='Markdown'
            )
        except BadRequest:
            # Если не получается, отправляем без форматирования
            await update.message.reply_text(
                "📋 Қатысушылар тізімі:\n" + "\n".join([
                    f"{i}. {p.name} (@{p.username or 'нет'})" + 
                    (f" → 🎁 сыйлайды: {bot_data.participants[p.assigned_to].name}" if p.assigned_to and p.assigned_to in bot_data.participants else "") + 
                    f"\n   📖: {p.desired_book}\n"
                    for i, p in enumerate(participants, 1)
                ])
            )
            
    except Exception as e:
        logger.error(f"Қатысушылар тізімін көрсету кезінде қате: {e}")
        await update.message.reply_text("Қатысушылар тізімін алу кезінде қате пайда болды")

async def clear_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команданы өңдеуші /clear (қайта)"""
    try:
        user = update.effective_user
        
        if user.id in bot_data.participants:
            keyboard = [
                [InlineKeyboardButton("🗑️ Менің деректерімді тазалау", callback_data="clear_my_data")],
                [InlineKeyboardButton("✖️ Болдырмау", callback_data="cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "Сіз сенімдісіз бе? Сіздің деректеріңізді тазалау керек пе?",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text("Сізде сақталған деректер жоқ")
    except Exception as e:
        logger.error(f"Деректерді тазалау кезінде қате: {e}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий кнопок"""
    try:
        query = update.callback_query
        await query.answer()
        
        user = query.from_user
        data = query.data
        
        if data == "restart":
            # Начинаем заполнение заново
            await query.edit_message_text(
                "Есіміңіз:",
                parse_mode='Markdown'
            )
            context.user_data.clear()
            return NAME
        
        elif data == "keep":
            # Оставляем существующие данные
            await query.edit_message_text(
                "Ваши данные сохранены. Используйте /send для подтверждения."
            )
            return ConversationHandler.END
        
        elif data == "skip_comment":
            return await skip_comment(update, context)
        
        elif data == "clear_my_data":
            if bot_data.clear_user_data(user.id):
                await query.edit_message_text("Деректеріңіз жойылды✅ Қайта бастау үшін /start пайдаланыңыз.")
            else:
                await query.edit_message_text("Деректерді өшіру мүмкін болмады")
        
        elif data == "relottery":
            # Очищаем предыдущие назначения
            for participant in bot_data.participants.values():
                participant.assigned_to = None
            
            # Проводим жеребьевку заново
            participants = bot_data.get_all_participants()
            if perform_lottery(participants):
                # Отправляем результаты
                sent_count = 0
                for participant in participants:
                    try:
                        assigned_participant = bot_data.participants[participant.assigned_to]
                        
                        name_escaped = escape_markdown(assigned_participant.name)
                        book_escaped = escape_markdown(assigned_participant.desired_book)
                        comment_escaped = escape_markdown(assigned_participant.comment) if assigned_participant.comment else ""
                        
                        message_text = (
                            "🔄 **Жеребе қайтадан өткізілді!**\n\n"
                            f"Сізге келесі оқырман түсті: **{name_escaped}**\n\n"
                            f"📖 **Оқырман қалайтын келетін кітап:**\n"
                            f"_{book_escaped}_\n\n"
                        )
                        
                        if assigned_participant.comment:
                            message_text += f"💬 **Пікірі:**\n_{comment_escaped}_"
                        
                        await context.bot.send_message(
                            chat_id=participant.user_id,
                            text=message_text,
                            parse_mode='Markdown'
                        )
                        sent_count += 1
                        
                    except BadRequest as e:
                        logger.error(f"Ошибка Markdown при отправке сообщения: {e}")
                        # Отправляем без форматирования
                        await context.bot.send_message(
                            chat_id=participant.user_id,
                            text=f"🔄 Жеребе қайтадан өткізілді!\n\n"
                                 f"Сізге келесі оқырман түсті: {assigned_participant.name}\n\n"
                                 f"📖 Оқырман қалайтын келетін кітап:\n"
                                 f"{assigned_participant.desired_book}\n\n" +
                                 (f"💬 Пікірі:\n{assigned_participant.comment}" if assigned_participant.comment else "")
                        )
                        sent_count += 1
                        
                    except Exception as e:
                        logger.error(f"Не удалось отправить сообщение: {e}")
                
                bot_data.save_data()
                await query.edit_message_text(
                    f"Жеребе қайтадан өткізілді!\n"
                    f"Хабарлама жіберілді: {sent_count}/{len(participants)}"
                )
        
        elif data == "cancel":
            await query.edit_message_text("Действие отменено")
    
    except Exception as e:
        logger.error(f"Ошибка в обработчике кнопок: {e}")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена диалога"""
    try:
        await update.message.reply_text(
            "Заполнение данных отменено. "
            "Используйте /start чтобы начать заново."
        )
        context.user_data.clear()
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Ошибка при отмене: {e}")
        return ConversationHandler.END

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик ошибок"""
    logger.error(f"Ошибка при обработке обновления: {context.error}", exc_info=context.error)
    
    if isinstance(context.error, TimedOut):
        logger.warning("Таймаут при подключении к Telegram")
    elif isinstance(context.error, BadRequest):
        logger.error(f"Ошибка запроса Telegram: {context.error}")
    else:
        logger.error(f"Необработанная ошибка: {context.error}")

# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================
def main():
    """Запуск бота"""
    # Создаем Application с настройками таймаута
    application = Application.builder() \
        .token(BOT_TOKEN) \
        .connect_timeout(30.0) \
        .read_timeout(30.0) \
        .write_timeout(30.0) \
        .pool_timeout(30.0) \
        .get_updates_connect_timeout(10.0) \
        .get_updates_read_timeout(10.0) \
        .get_updates_write_timeout(10.0) \
        .get_updates_pool_timeout(10.0) \
        .build()
    
    # Добавляем обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Создаем ConversationHandler для /start
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_name)],
            BOOK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_book)],
            COMMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_comment),
                CommandHandler("start", start)
            ],
            CONFIRM: [
                CommandHandler("send", submit_data),
                CommandHandler("start", start)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    # Добавляем обработчики
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("send", submit_data))
    application.add_handler(CommandHandler("lottery", lottery))
    application.add_handler(CommandHandler("list", list_participants))
    application.add_handler(CommandHandler("clear", clear_data))
    
    # Обработчик кнопок (CallbackQueryHandler)
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Запускаем бота
    print("Бот запущен...")
    
    # Для Python 3.14
    if sys.version_info >= (3, 14):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(application.run_polling(
                allowed_updates=Update.ALL_TYPES
            ))
        finally:
            loop.close()
    else:
        application.run_polling(
            allowed_updates=Update.ALL_TYPES
        )

if __name__ == "__main__":
    main()