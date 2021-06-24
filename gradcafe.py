from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters,
                              ConversationHandler, PicklePersistence)
from telegram.error import Unauthorized as TelegramUnauthorizedException

import requests
from bs4 import BeautifulSoup
import logging
from random import randint

#LOGGING
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

# SECURITY CONSTANTS
BOT_TOKEN = 'your token from botfather'

#Job time intervals
MONITOR_POLL_INVERVAL = 100

# Telegram BOT states
SET_MONITOR_LIST, IDLE = range(2)


def get_last_entry(monitor_element):
    page = requests.get(f"https://www.thegradcafe.com/survey/index.php?q={monitor_element.replace(' ', '+')}")
    soup = BeautifulSoup(page.content, 'html.parser')
    last_entry = soup.find(class_='row0')

    elem_dict = { elem.attrs['class'][0]:elem.get_text().replace("\n", "").replace("\t", "").strip() for elem in soup.find('thead').find('tr').find_all('th') }

    last_elem_dict = { elem_dict[class_name] : last_entry.find(class_=class_name).get_text() for class_name in elem_dict }
    string = ''
    for elem in last_elem_dict:
        string += f'{elem}: {last_elem_dict[elem]}\n'
    return string

def job_monitor(context):
    chat_data = context.job.context
    bot = context.bot

    monitor_list = chat_data['monitor_list']
    last_update = chat_data['last_update'] if 'last_update' in chat_data else {m_elem:'' for m_elem in monitor_list}

    for m_elem in monitor_list:
        last_entry = get_last_entry(m_elem)
        if last_update[m_elem] != last_entry:
            last_update[m_elem] = last_entry
            try:
                bot.send_message(chat_id=chat_data['chat_id'],
                                text=last_entry)
            except TelegramUnauthorizedException as e :
                #if e.message == 'Forbidden: bot was blocked by the user':
                #   remove_jobs_after_exception(context,e)
                #TODO
                pass
    chat_data['last_update'] = last_update            

def start(update, context):
    chat_data = context.chat_data
    chat_data['chat_id'] = str(update.message.chat_id)

    update.message.reply_text("Enter the entries you want to monitor separated by comas (,)")
    return SET_MONITOR_LIST

def set_monitor_list(update, context):
    chat_data = context.chat_data
    job_queue = context.job_queue
    try:
        monitor_list = update.message.text.split(',')
        chat_data['monitor_list'] = [entry.strip() for entry in monitor_list]

    except Exception as e:
        update.message.reply_text(str(e))
        return ConversationHandler.END
    update.message.reply_text(f"The following entries will be monitored \n{chat_data['monitor_list']}")
    job_queue.run_repeating(job_monitor, interval=MONITOR_POLL_INVERVAL, first=0, context=chat_data)
    return IDLE

def cancel(update, context):
    return ConversationHandler.END

def error_handler(update, context) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    return IDLE

def restore_jobs(job_queue,chat_data_dict):
    for _, chat_data in chat_data_dict.items():
        job_queue.run_repeating(job_monitor, interval=MONITOR_POLL_INVERVAL, first=randint(0,20), context=chat_data)
        logger.info(msg=f"{chat_data['chat_id']} job restarted")

def main():
    pp = PicklePersistence(filename='gradcafebotdata')
    updater = Updater(token=BOT_TOKEN, persistence=pp, use_context=True)
    dispatcher = updater.dispatcher

    handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={

            SET_MONITOR_LIST: [MessageHandler(Filters.text, set_monitor_list)],
            IDLE: [ ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        name='ConversationHandler')
    dispatcher.add_handler(handler)
    dispatcher.add_error_handler(error_handler)
    restore_jobs(updater.job_queue, pp.get_chat_data())
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()