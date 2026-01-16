# -*- coding: utf-8 -*-
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from hydrogram.enums import ChatType

from sqlalchemy import create_engine, Engine, desc
from sqlalchemy.orm import Session

from hydrogram import Client, filters, idle
from hydrogram.types import Message

from db_models import Base, FilesData

WRONG_FILENAME_CHARS = '\\/*?:\'"'

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tmp')
Path(DATA_DIR).mkdir(parents=True, exist_ok=True)

engine: Engine = create_engine(
    f'sqlite:///{os.path.join(DATA_DIR, "files_data.sqlite")}')
Base.metadata.create_all(engine)

load_dotenv()
if os.environ.get('API_HASH', '') == '':
    print('\nERROR: API_HASH or ".env" file NOT FOUND !!!')
    exit(1)

bot = Client("stats",
             int(os.environ.get('API_ID', 0)),
             os.environ.get('API_HASH', ''),
             in_memory=True,
             session_string=os.environ.get('API_SESSION', ''),
             phone_number=os.environ.get('API_PHONE', ''))


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


def get_short_file_name(message: Message) -> str:
    short_file_name = ' - '.join([str(x).strip() for x in [
        message.audio.performer,
        message.audio.title,
        message.audio.file_name] if x])

    if short_file_name == '':
        short_file_name = str(message.audio.file_unique_id).strip() + '.mp3'

    short_file_name = clear_filename_chars(short_file_name)
    print(short_file_name)
    return short_file_name


async def progress(current, total,file_name):
    print(f"{file_name}: {current * 100 / total:.1f}%")

async def save_file_if_not_exists(short_file_name: str, message: Message) -> None:
    user_folder = get_user_folder(message)
    Path(user_folder).mkdir(parents=True, exist_ok=True)

    full_file_name = os.path.join(user_folder, short_file_name)
    if not os.path.exists(full_file_name):
        await bot.download_media(message=message, file_name=full_file_name, progress=progress, progress_args=(short_file_name,))
        print(f"{short_file_name}: SAVED")


@bot.on_message(filters.incoming & filters.private & filters.audio)
async def _(_, message: Message):
    await save_if_audio(message)


async def save_if_audio(message: Message):
    try:
        if not ((not message.outgoing)
                and bool(message.chat and message.chat.type == ChatType.PRIVATE)
                and bool(message.audio)):
            return

        if message.chat.full_name != 'Ivan G':
            print(f'WRONG CHAT {message.chat.full_name}')
            return

        with Session(autoflush=False, bind=engine) as db:
            file_data = db.query(FilesData).filter(
                FilesData.file_unique_id == message.audio.file_unique_id,
                FilesData.user_id == message.from_user.id).first()
            if file_data is not None:
                await save_file_if_not_exists(file_data.short_file_name, message)
                # await message.reply('exists', quote=True)
            else:
                short_file_name = get_short_file_name(message)
                if db.query(FilesData).filter(
                        FilesData.short_file_name == short_file_name,
                        FilesData.user_id == message.from_user.id).first() is not None:
                    short_file_name = clear_filename_chars(
                        # есть дубль, добавить префикс
                        message.audio.file_unique_id) + '_' + short_file_name

                now = datetime.now()
                lst = [str(x).strip() for x in
                       [f'{now.hour}:{now.minute}:{now.second}',
                        'START SAVING',
                        message.from_user.id,
                        message.audio.file_name,
                        message.audio.mime_type,
                        message.audio.duration,
                        message.audio.file_size,
                        short_file_name] if x]
                print('|'.join(lst))

                await save_file_if_not_exists(short_file_name, message)

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
                await message.reply(f'saved: "{short_file_name}"', quote=True)

    except Exception as e:
        print(e)
        s=f'ERROR\n{e}'
        await message.reply(s, quote=True)
        await bot.send_message("me", s)


# @bot.on_message(filters.incoming & filters.private & (filters.command("info") | filters.text))
# async def _(_, message: Message):
#     if not (bool(message.text) and message.text.lower() in ['/info', 'info']):
#         print(f'message.text="{message.text}" : {message.chat.full_name}')
#         return

#     with (Session(autoflush=False, bind=engine) as db):
#         if message.chat.full_name != 'Ivan G':
#             print(f'WRONG CHAT {message.chat.full_name}')
#             return

#         records = db.query(FilesData.short_file_name) \
#             .where(FilesData.user_id == message.from_user.id) \
#             .order_by(desc(FilesData.created_at))

#         files = [r.short_file_name for r in records]
#         if not files:
#             await message.reply("No files", quote=True)
#         else:
#             large_text = f'Files ({len(files)}):\n{"\n".join(files)}'
#             await message.reply(large_text[:3000], quote=True)


async def check_all_audio_data_chats_history():
    user_id = 0
    try:
        with (Session(autoflush=False, bind=engine) as db):
            user_ids = [r.user_id for r in db.query(
                FilesData.user_id).distinct().all()]

        for user_id in user_ids:
            async for m in bot.get_chat_history(user_id):
                await save_if_audio(m)
            print(f'chat_history checked: {user_id}')
    except Exception as e:
        print(f'chat_history error: {user_id}: {e}')


async def main():
    await bot.start()
    # s = bot.export_session_string()
    # print(f"\n{s}\n")
    await bot.send_message("me", "Started. UserBot")
    print('\n(Press Ctrl+C to stop this)')
    await check_all_audio_data_chats_history()
    print ('IDLE')
    await idle()
    await bot.stop()


bot.run(main())
