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
import pandas as pd
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


class EuropaParser:
    playwright = None
    browser = None
    page = None
    context = None

    def __init__(self, playwright):
        self.res_list = []
        self.res_dict = {'name': None, 'url': None}
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

    def set_city(self):
        try:
            print('Устанавливаем город')
            self.page.goto("https://europa-market.ru/")
            self.page.get_by_role("button", name="Нет, выбрать другой").click()
            self.page.get_by_role("link", name="Брянск").click()
            time.sleep(5)
            self.page.get_by_role("button", name="Адрес доставки").click()
            self.page.get_by_text("Самовывоз").click()
            self.page.get_by_placeholder("Выберите магазин из списка").click()
            self.page.get_by_role("option", name="Брянск-58, ул. Горбатова,").click()
            self.page.get_by_role("button", name="Готово").click()
            print(f'Успешно установлен адрес: {ADDRESS_SHOP}')
            time.sleep(5)
        except Exception as exp:
            print(exp)
            print(traceback.format_exc())

    def get_data_by_page(self, product):
        soup = BeautifulSoup(self.page.content(), 'lxml')
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
                stock = 0
        else:
            stock = 0
        # Цена
        price = round(float(soup.find('span', itemprop='price').text.strip()))
        print()


    def get_data_from_catalogs(self):
        """Перебор по ссылкам на товары, получение данных"""
        for product in tqdm(self.product_list):
            retry_count = 3
            while retry_count > 0:
                try:
                    self.page.goto(product, timeout=30000)
                    self.get_data_by_page(product)
                    break
                except Exception as exp:
                    traceback_str = traceback.format_exc()
                    print(f'{bcolors.WARNING}Ошибка при загрузке страницы {product}: {bcolors.ENDC}\n{str(exp)}\n\n'
                          f'{traceback_str}')
                    retry_count -= 1
                    if retry_count > 0:
                        print(f'Повторная попытка ({retry_count} осталось)')
                    else:
                        print(f'{bcolors.FAIL}Превышено количество попыток для товара, в файл добавлено:{bcolors.ENDC}'
                              f'\n{product}')
                        add_bad_req(product, error='Превышено количество попыток для товара')
                        break

    def start(self):
        # self.set_city()
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
        # send_logs_to_telegram(message=f'Произошла ошибка!\n\n\n{exp}\n\n{traceback_str}')
    t2 = datetime.datetime.now()
    print(f'Finish: {t2}, TIME: {t2 - t1}')
    # send_logs_to_telegram(message=f'Finish: {t2}, TIME: {t2 - t1}')


if __name__ == '__main__':
    main()
