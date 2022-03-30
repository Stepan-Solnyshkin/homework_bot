import exceptions
import logging
import os
import requests
import json
import telegram
import time

from dotenv import load_dotenv
from http import HTTPStatus

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 10
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
    try:
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params=params
        )
        if homework_statuses.status_code != HTTPStatus.OK:
            logger.error('Код ответ от сервера API не 200')
            raise Exception('Код ответ от сервера API не 200')
        try:
            response = homework_statuses.json()
        except json.decoder.JSONDecodeError:
            print("Не можем декодировать ответ от API в JSON")
        return response
    except exceptions.UnavailableUrl:
        logger.error(f'При запросе к API возникла ошибка'
                     f'{homework_statuses.status_code}.')
        raise exceptions.UnavailableUrl(f'При запросе к API возникла ошибка'
                                        f'{homework_statuses.status_code}.')


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
    homework = response['homeworks']
    if type(homework) is not list:
        logger.error('В ответе API нет списка работ')
        raise Exception('В ответе API нет списка работ')
    return homework


def parse_status(homework):
    """Извлекаем информацию о конкретной домашней работе."""
    logger.info('Извлекаем информацию о конкретной домашней работе.')
    try:
        homework_name = homework.get('homework_name')
    except exceptions.KeyNotInDict:
        logger.error('Ключа "homework_name" нет в ответе API')
        raise exceptions.KeyNotInDict('Ключа "homework_name" нет в ответе API')
    try:
        homework_status = homework.get('status')
    except exceptions.KeyNotInDict:
        logger.error('Ключа "status" нет в ответе API')
        raise exceptions.KeyNotInDict('Ключа "status" нет в ответе API')
    try:
        verdict = HOMEWORK_STATUSES[homework_status]
    except exceptions.KeyNotInDict:
        logger.error('Ключа "homework_status" нет в "HOMEWORK_STATUSES"')
        raise exceptions.KeyNotInDict(
            'Ключа "homework_status" нет в "HOMEWORK_STATUSES"'
        )
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
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Отсутсвуют переменные окружения')
        raise KeyError('Отсутсвуют переменные окружения')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    cache = []
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            message = parse_status(homework[0])
            current_timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе телеграмм-бота: {error}'
            logging.critical(
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
