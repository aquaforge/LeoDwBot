# -*- coding: utf-8 -*-
# https://pytba.readthedocs.io/en/latest/
import os
import string
from datetime import datetime
from pathlib import Path
from time import time
from dotenv import load_dotenv

# pip install sqlalchemy
from sqlalchemy import create_engine, Engine, desc
from sqlalchemy.orm import Session

# pip install pyTelegramBotAPI
from telebot import TeleBot, util
from telebot.types import Message, Voice, ReplyKeyboardMarkup, KeyboardButton, File

from db_models import Base, FilesData

WRONG_FILENAME_CHARS = '\\/*?:\'"'

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tmp')
Path(DATA_DIR).mkdir(parents=True, exist_ok=True)

engine: Engine = create_engine(f'sqlite:///{os.path.join(DATA_DIR, "files_data.sqlite")}')
Base.metadata.create_all(engine)

load_dotenv()
TELEBOT_TOKEN = os.environ.get('TELEBOT_TOKEN', '')
if TELEBOT_TOKEN == '':
    print('\nERROR: TELEBOT_TOKEN or ".env" file NOT FOUND !!!')
    exit(1)

bot: TeleBot = TeleBot(TELEBOT_TOKEN)

markup = ReplyKeyboardMarkup(resize_keyboard=True)
markup.add(KeyboardButton('/list'))


def get_user_folder(message: Message) -> str:
    return os.path.join(DATA_DIR, f'u{message.from_user.id}')


def print_message(message: Message):
    print('\n--------------------\n')
    print(message)
    print('\n--------------------\n')


def clear_filename_chars(filename: str) -> str:
    s = filename.replace('  ', ' ')
    for character in WRONG_FILENAME_CHARS:
        s = s.replace(character, '')
    return s


def get_short_file_name(message: Message, suffix: str = '') -> str:
    short_file_name = ' - '.join([message.audio.performer.strip(), message.audio.title.strip()])

    suffix = suffix.strip()
    if suffix != '': short_file_name += '_' + suffix

    short_file_name = clear_filename_chars(short_file_name)

    if short_file_name == '':
        short_file_name = clear_filename_chars(message.audio.file_unique_id)
    short_file_name += '.' + message.audio.file_name.split('.')[-1]
    return short_file_name


@bot.message_handler(content_types=['audio'])
def _(message: Message):
    try:
        # print_message(message)
        with Session(autoflush=False, bind=engine) as db:
            file_data = db.query(FilesData).filter(
                FilesData.file_unique_id == message.audio.file_unique_id,
                FilesData.user_id == message.from_user.id).first()
            if file_data is not None:
                save_file_if_not_exists(file_data.short_file_name, message)
                # bot.send_message(message.chat.id, 'exists',
                #                  reply_markup=markup, reply_to_message_id=message.id)
            else:
                short_file_name = get_short_file_name(message)
                if db.query(FilesData).filter(
                        FilesData.short_file_name == short_file_name,
                        FilesData.user_id == message.from_user.id).first() is not None:
                    short_file_name = get_short_file_name(message, message.audio.file_unique_id)

                now = datetime.now()
                print('|'.join([f'{now.hour}:{now.minute}:{now.second}',
                                'saving',
                                str(message.from_user.id),
                                message.audio.file_name,
                                message.audio.mime_type,
                                str(message.audio.duration),
                                str(message.audio.file_size),
                                short_file_name]))
                save_file_if_not_exists(short_file_name, message)

                file_data = FilesData()
                file_data.user_id = message.from_user.id
                file_data.file_unique_id = message.audio.file_unique_id
                file_data.performer = message.audio.performer
                file_data.title = message.audio.title
                file_data.file_name = message.audio.file_name
                file_data.mime_type = message.audio.mime_type
                file_data.short_file_name = short_file_name
                db.add(file_data)
                db.commit()

                bot.send_message(message.chat.id, 'saved',
                                 reply_markup=markup, reply_to_message_id=message.id)

    except Exception as e:
        print(e)
        bot.send_message(message.chat.id, f'ERROR\n{e}',
                         reply_markup=markup, reply_to_message_id=message.id)


def save_file_if_not_exists(short_file_name: str, message: Message) -> None:
    # try:
    user_folder = get_user_folder(message)
    Path(user_folder).mkdir(parents=True, exist_ok=True)
    full_file_name = os.path.join(user_folder, short_file_name)

    if not os.path.exists(full_file_name):
        tg_file: File = bot.get_file(message.audio.file_id)
        tg_file_path: str = tg_file.file_path or ''
        if tg_file_path != '':
            with open(full_file_name, 'wb') as new_file:
                new_file.write(bot.download_file(tg_file_path))
    # except IOError as e:
    #     print(e)
    #     bot.send_message(message.chat.id, f'IO ERROR\n{e}',
    #                      reply_markup=markup, reply_to_message_id=message.id)


@bot.message_handler(commands=['start'])
def _(message: Message):
    bot.send_message(message.chat.id, "start message", reply_markup=markup)


@bot.message_handler(commands=['list'])
def _(message: Message):
    with (Session(autoflush=False, bind=engine) as db):
        records = db.query(FilesData.short_file_name) \
            .where(FilesData.user_id == message.from_user.id) \
            .order_by(desc(FilesData.created_at))

        files = [r.short_file_name for r in records]
        if not files:
            bot.send_message(message.chat.id, "No files",
                             reply_markup=markup, reply_to_message_id=message.id)
        else:
            large_text = f'Files ({len(files)}):\n{"\n".join(files)}'
            for text in util.smart_split(large_text, chars_per_string=3000):
                bot.send_message(message.chat.id, text,
                                 reply_markup=markup, reply_to_message_id=message.id)


@bot.message_handler()
def _(message: Message):
    print_message(message)


if __name__ == "__main__":
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(e)
