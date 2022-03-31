import exceptions
import json
import logging
import os
import requests
import telegram
import time

from dotenv import load_dotenv
from http import HTTPStatus

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
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
    format='%(asctime)s, %(name)s, %(levelname)s, %(message)s',
)
logger = logging.getLogger(__name__)
handler = logging.StreamHandler(stream='sys.stdout')
logger.addHandler(handler)


def send_message(bot, message):
    """Отправляем сообщение в чат."""
    try:
        logger.info(f'Удачная отправка сообщения в Telegram: {message}.')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.TelegramError:
        logger.error(f'Cбой при отправке сообщения в Telegram: {message}.')
        raise exceptions.SendMessedge(
            f'Cбой при отправке сообщения в Telegram: {message}.'
        )


def get_api_answer(current_timestamp):
    """Получаем ответ от API Практикума."""
    logger.info('Получаем ответ от API Практикума.')
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    homework_statuses = requests.get(
        ENDPOINT, headers=HEADERS, params=params
    )
    response = homework_statuses
    if homework_statuses.status_code != HTTPStatus.OK:
        logger.error('Код ответ от сервера API не 200')
        raise exceptions.StatusCodeNot200('Код ответ от сервера API не 200')
    try:
        response = homework_statuses.json()
    except json.decoder.JSONDecodeError:
        logger.error('Не можем декодировать ответ от API в JSON')
        raise exceptions.JsonNotDecode(
            'Не можем декодировать ответ от API в JSON'
        )
    return response


def check_response(response):
    """Проверяет ответ API на корректность."""
    logger.info('Проверяем ответ API на корректность.')
    if not response:
        logger.error('Ответ от API - пустой словарь')
        raise Exception('Ответ от API - пустой словарь')
    if type(response) is not dict:
        logger.error('Ответ от API не в виде словаря')
        raise TypeError('Ответ от API не в виде словаря')
    if 'homeworks' not in response:
        logger.error('В ответе от API нет ключа homework')
        raise KeyError('В ответе API нет ключа homework')
    if not response['homeworks']:
        logger.error('В ответе от API нет значения по ключу homework')
        raise KeyError('В ответе API нет значения по ключу homework')
    if type(response['homeworks']) is not list:
        logger.error('В ответе API нет списка работ')
        raise Exception('В ответе API нет списка работ')
    homeworks = response['homeworks']
    return homeworks


def parse_status(homework):
    """Извлекаем информацию о конкретной домашней работе."""
    logger.info('Извлекаем информацию о конкретной домашней работе.')
    if 'homework_name' not in homework:
        logger.error('В homework нет ключа "homework_name"')
        raise KeyError('В homework нет ключа "homework_name"')
    if not homework['homework_name']:
        logger.error('В homework нет значения по ключу "homework_name"')
        raise KeyError('В homework нет значения по ключу "homework_name"')
    if "status" not in homework:
        logger.error('В homework нет ключа "status"')
        raise KeyError('В homework нет ключа "status"')
    if not homework['status']:
        logger.error('В homework нет значения по ключу "status"')
        raise KeyError('В homework нет значения по ключу "status"')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    try:
        verdict = HOMEWORK_STATUSES[homework_status]
    except KeyError:
        logger.error('Вердикта нет в "HOMEWORK_STATUSES"')
        raise exceptions.KeyNotInDict(
            'Статуса нет в "HOMEWORK_STATUSES"'
        )
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
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутсвуют переменные окружения')
        raise KeyError('Отсутсвуют переменные окружения')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    cache = []
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            message = parse_status(homeworks[0])
            current_timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе телеграмм-бота: {error}'
            logger.critical(
                f'Уведомление об ошибке отправлено в чат {message}'
            )
        finally:
            if message in cache:
                logger.debug('Новых статусов нет')
            else:
                cache.append(message)
                send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
