import time
import os
import requests
import logging

from http import HTTPStatus

import telegram

from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 60
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.INFO,
    filename='main.log',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)
handler = logging.StreamHandler(stream='sys.stdout')
logger.addHandler(handler)


def send_message(bot, message):
    """Отправляем сообщение в чат."""
    try:
        logger.info(f'Удачная отправка сообщения в Telegram: {message}.')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception:
        logger.error(f'Cбой при отправке сообщения в Telegram: {message}.')
        raise Exception(f'Cбой при отправке сообщения в Telegram: {message}.')


def get_api_answer(current_timestamp):
    """Получаем ответ от API Практикума."""
    logger.info('Получаем ответ от API Практикума.')
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    homework_statuses = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if homework_statuses.status_code == HTTPStatus.OK:
        response = homework_statuses.json()
        return response
    else:
        logger.error(f'При запросе к API возникла ошибка'
                     f'{homework_statuses.status_code}.')
        raise Exception(f'При запросе к API возникла ошибка'
                        f'{homework_statuses.status_code}.')


def check_response(response):
    """Проверяет ответ API на корректность."""
    logger.info('Проверяем ответ API на корректность.')
    if not response:
        logger.error('Ответ от API - пустой словарь')
        raise Exception('Ответ от API - пустой словарь')
    if not response['homeworks']:
        logger.error('В ответе от API нет ключа homework')
        raise KeyError('В ответе API нет ключа homework')
    if type(response) is not dict:
        logger.error('Ответ от API не в виде словаря')
        raise KeyError('Ответ от API не в виде словаря')
    list_homework = response.get('homeworks')
    if type(list_homework) is not list:
        logger.error('В ответе API нет списка работ')
        raise Exception('В ответе API нет списка работ')
    else:
        homework = list_homework
    return homework


def parse_status(homework):
    """Извлекает информацию о конкретной домашней работе."""
    homework_name = homework.get('homework_name', None)
    homework_status = homework.get('status', None)
    if 'homework_name' not in homework:
        logger.error('Ключа "homework_name" нет в ответе API')
        raise KeyError('Ключа "homework_name" нет в ответе API')
    if 'status' not in homework:
        logger.error(
            'Недокументированный статус работы, обнаруженный в ответе API'
        )
        raise KeyError(
            'Недокументированный статус работы, обнаруженный в ответе API'
        )
    verdict = HOMEWORK_STATUSES[homework_status]
    if homework_status not in HOMEWORK_STATUSES:
        logger.error('Неизвестный статус')
        raise Exception('Неизвестный статус')
    logger.info(
        f'Изменился статус проверки работы "{homework_name}". {verdict}'
    )
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def get_current_timestamp():
    """Обновляет временную метку."""
    current_timestamp = int(time.time() - RETRY_TIME)
    return current_timestamp


def check_tokens():
    """Проверяем доступность переменных окружения."""
    logger.info('Проверяем доступность переменных окружения.')
    try:
        return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))
    except Exception:
        logger.critical('Одна из переменных окружения недоступна. Стоп!')
        exit()


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())  # 1646095005
    errors = True
    while True:
        try:
            response = get_api_answer(current_timestamp)
            if not response.get('homeworks'):
                time.sleep(RETRY_TIME)
            homework = check_response(response)
            message = parse_status(homework[0])
            send_message(bot, message)
            current_timestamp = response.get('current_date')
            time.sleep(RETRY_TIME)
            get_current_timestamp()
        except Exception as error:
            message = f'Сбой в работе телеграмм-бота: {error}'
            logging.critical(
                f'Уведомление об ошибке отправлено в чат {message}'
            )
            if errors:
                errors = False
                send_message(bot, message)
            current_timestamp = response.get('current_date')
            time.sleep(RETRY_TIME)
            get_current_timestamp()


if __name__ == '__main__':
    main()
