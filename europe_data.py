"""
Скрипт на основе playwright считывает ссылки на товары Европа из файла product_list_for_get_data.txt,
переходит по ним, предварительно установив город и адрес магазина из константы ADDRESS_SHOP,
считывает информацию и остатки каждого товара, если брэнда товара нет в файле bad_brand.txt,
записывает результаты в файл JSON.

Помимо результирующего файла JSON, формируются дополнительные файлы:
articles_with_bad_req.txt - для ссылок, которые не удалось загрузить, либо товар из списка нежелательных
брэндов, либо другая ошибка с указанием этой ошибки
"""

import requests
import datetime
import time
import re
from tqdm import tqdm
from pathlib import Path
import json
import traceback
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from europe_arts import bcolors

ADDRESS_SHOP = 'Брянск-58, ул. Горбатова, 18'


def read_product_list_from_txt():
    """Считывает и возвращает список ссылок на товары из файла"""
    with open('in/product_list_for_get_data.txt', 'r', encoding='utf-8') as file:
        product_list = [f'{line}'.rstrip() for line in file]
    return product_list


def add_bad_req(art, error=''):
    with open('out/articles_with_bad_req.txt', 'a') as output:
        if error == '':
            output.write(f'{art}\n')
        else:
            output.write(f'{error}\t{art}\n')


def write_json(res_dict):
    with open('out/data.json', 'w', encoding='utf-8') as json_file:
        json.dump(res_dict, json_file, indent=2, ensure_ascii=False)


def send_logs_to_telegram(message):
    import platform
    import socket
    import os

    platform = platform.system()
    hostname = socket.gethostname()
    user = os.getlogin()

    bot_token = '6456958617:AAF8thQveHkyLLtWtD02Rq1UqYuhfT4LoTc'
    chat_id = '128592002'

    url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
    data = {"chat_id": chat_id, "text": message + f'\n\n{platform}\n{hostname}\n{user}'}
    response = requests.post(url, data=data)
    return response.json()


class EuropaParser:
    playwright = None
    browser = None
    page = None
    context = None

    def __init__(self, playwright):
        self.res_list = []
        self.res_dict = {}
        self.product_list = read_product_list_from_txt()
        self.set_playwright_config(playwright=playwright)

    def set_playwright_config(self, playwright):
        js = """
        Object.defineProperties(navigator, {webdriver:{get:()=>undefined}});
        """
        self.playwright = playwright
        self.browser = playwright.chromium.launch(headless=False, args=['--blink-settings=imagesEnabled=false'])
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.page.add_init_script(js)

    def check_ddos(self, title):
        """Проверяем, сработала ли DDOS защита, т.е. смотрим текст, что в заголовке"""
        if title == 'DDoS-Guard':
            return True
        else:
            return False
            # send_logs_to_telegram(message=f'Обнаружена защита от DDOS! Скрипт на паузе.')
            # input(f'{bcolors.BOLD}Обнаружена защита от DDOS!{bcolors.ENDC} {datetime.datetime.now()}')

    def set_city(self):
        try:
            print('Устанавливаем город')
            self.page.goto("https://europa-market.ru/")
            self.page.get_by_role("button", name="Нет, выбрать другой").click()
            self.page.get_by_role("link", name="Брянск").click()
            time.sleep(10)
            self.page.get_by_role("button", name="Адрес доставки").click()
            self.page.get_by_text("Самовывоз").click()
            self.page.get_by_placeholder("Выберите магазин из списка").click()
            self.page.get_by_role("option", name="Брянск-58, ул. Горбатова,").click()
            self.page.get_by_role("button", name="Готово").click()
            print(f'Успешно установлен адрес: {ADDRESS_SHOP}')
            time.sleep(10)
        except Exception as exp:
            print(exp)
            print(traceback.format_exc())

    def get_data_by_page(self, product):
        print(product)
        soup = BeautifulSoup(self.page.content(), 'lxml')
        # Цена и наличие
        price_tag = soup.find('span', itemprop='price')
        if price_tag:
            price = round(float(price_tag.text.strip()))
        else:
            absent_tag = soup.find('div', class_='product-overview__price')
            if absent_tag and absent_tag.find('h2', class_='product-overview__absent'):
                print(f'{bcolors.WARNING}Нет в наличии{bcolors.ENDC}')
                add_bad_req(art=product, error='Нет_в_наличии')
                return
            else:
                print(f'{bcolors.FAIL}Информация о наличии или цене товара не найдена. ВООЗМОЖНА ЗАЩИТА{bcolors.ENDC}')
                add_bad_req(art=product, error='Информация_о_наличии_или_цене_не_найдена_вероятно_DDOS')
                input()
                return
        # Код
        code = product.split('-')[-1]
        # Имя
        name = soup.find('h1', class_='product-overview__title').text.strip()
        # Остатки
        pack_block = soup.find('div', class_='product-overview__pack')
        if pack_block:
            count_element = pack_block.find('span', class_='product-overview__count')
            if count_element:
                stock = count_element.text.strip()
                stock = int(re.search(r'\d+', stock).group())
            else:
                stock = '-'
        else:
            stock = '--'
            add_bad_req(art=product, error='Не_найден_блок_с_остатками')
        # Описание
        description_element = soup.find('div', class_='product-page__description-text')
        if description_element:
            description = description_element.text.strip()
            if description == '':
                description = '-'
                # print("Описание товара не найдено, но блок с описанием найден")
                # add_bad_req(art=product, error='Описание_товара_не_найдено_но_блок_с_описанием_найден')
        else:
            description = '-'
            print("Описание товара не найдено.")
            add_bad_req(art=product, error='Описание_товара_не_найдено')
        # Находим блок с характеристиками
        characteristics_dict = {}
        characteristics_block = soup.find('div', class_='product-description-list')
        if characteristics_block:
            characteristics_lines = characteristics_block.find_all('div', class_='product-description-list__line')
            for line in characteristics_lines:
                left_side = line.find(class_='product-description-list__side--side-left').text.strip()
                right_side = line.find(class_='product-description-list__side--side-right').text.strip()
                characteristics_dict[left_side] = right_side
        else:
            print("Характеристики товара не найдены.")
            add_bad_req(art=product, error='characteristics_not_found')
        # Находим блок с изображениями
        image_block = soup.find('div', class_='product-image-slider__preview')
        image_links = []
        if image_block:
            image_elements = image_block.find_all('img')
            for image_element in image_elements:
                image_src = image_element.get('src')
                if image_src:
                    image_links.append(image_src)
        image_links = [x.split('?v=')[0] for x in image_links]
        "Формируем результирующий словарь с данными"
        self.res_dict[code] = {'name': name, 'price': price, 'stock': stock, 'description': description,
                               'characteristics': characteristics_dict,
                               'img_url': image_links, 'art_url': product}
        write_json(res_dict=self.res_dict)

        # print()

    def get_data_from_catalogs(self):
        """Перебор по ссылкам на товары, получение данных"""
        for product in tqdm(self.product_list):
            retry_count = 0  # Количество попыток загрузки страницы
            max_retries = 4  # Количество попыток для DDOS
            while retry_count < max_retries:
                try:
                    # Переход к странице товара
                    self.page.goto(product, timeout=30000)
                    # Проверка на наличие блокировки DDOS
                    if self.check_ddos(title=self.page.title()):
                        # Определение времени ожидания в зависимости от retry_count
                        if retry_count == 0:
                            print('DDOS. Ждем 60 с')
                            time.sleep(60)
                        elif retry_count == 1:
                            print('DDOS. Ждем 500 с')
                            time.sleep(500)
                        elif retry_count == 2:
                            print('DDOS. Ждем 3000 с')
                            time.sleep(3000)
                        else:
                            # В четвертый раз просим ввод от пользователя
                            send_logs_to_telegram(message=f'Обнаружена защита от DDOS! Скрипт на паузе.')
                            input(f'{bcolors.BOLD}Обнаружена защита от DDOS!{bcolors.ENDC} {datetime.datetime.now()}')
                        retry_count += 1
                        continue
                    # Если нет блокировки, обрабатываем данные страницы
                    self.get_data_by_page(product)
                    break
                except Exception as exp:
                    # Обработка исключений при загрузке страницы
                    traceback_str = traceback.format_exc()
                    print(f'Ошибка при загрузке страницы {product}:\n{exp}\n{traceback_str}')
                    # Уменьшаем retry_count на 1
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f'Повторная попытка загрузки ({max_retries - retry_count} осталось)')
                    else:
                        # Если превышено количество попыток
                        print(f'Превышено количество попыток для товара, в файл добавлено: {product}')
                        add_bad_req(product, error='Превышено_количество_попыток_для_товара')
                        break

    def start(self):
        self.set_city()
        self.get_data_from_catalogs()


def main():
    t1 = datetime.datetime.now()
    print(f'Start: {t1}')
    try:
        with sync_playwright() as playwright:
            EuropaParser(playwright=playwright).start()
        print(f'{bcolors.OKGREEN}Успешно{bcolors.ENDC}')
    except Exception as exp:
        print(exp)
        traceback_str = traceback.format_exc()
        print(traceback_str)
        send_logs_to_telegram(message=f'Произошла ошибка!\n\n\n{exp}\n\n{traceback_str}')
    t2 = datetime.datetime.now()
    print(f'Finish: {t2}, TIME: {t2 - t1}')
    # send_logs_to_telegram(message=f'Finish: {t2}, TIME: {t2 - t1}')


if __name__ == '__main__':
    main()
