"""Скрипт на основе playwright считывает каталоги europa-market.ru из файла catalogs.txt и собирает ссылки со всех
имеющихся страниц в файл out/europa_articles.txt с учетом цены или без. Остатки приблизительны.
Особенность: исключить брэнд Собственное производство"""
import time

from tqdm import tqdm
import datetime
import requests
from pathlib import Path
from playwright.sync_api import Playwright, sync_playwright, expect
import json
from bs4 import BeautifulSoup
import traceback

ADDRESS_SHOP = 'Брянск-58, ул. Горбатова, 18'


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def read_catalogs_from_txt():
    """Считывает и возвращает список каталогов из файла"""
    with open('in/catalogs.txt', 'r', encoding='utf-8') as file:
        catalogs = [f'{line}'.rstrip() for line in file]
    return catalogs


class Europa:
    playwright = None
    browser = None
    page = None
    context = None

    def __init__(self, playwright):
        self.res_list = []
        self.res_dict = {'name': None, 'url': None}
        self.catalogs = read_catalogs_from_txt()
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
        except Exception as exp:
            print(exp)
            print(traceback.format_exc())

    def get_arts_from_catalogs(self):
        for catalog in self.catalogs:
            print(f'Работаю с каталогом: {catalog}')
            self.page.goto(catalog)

    def start(self):
        self.set_city()
        self.get_arts_from_catalogs()


def main():
    t1 = datetime.datetime.now()
    print(f'Start: {t1}')
    try:
        with sync_playwright() as playwright:
            Europa(playwright=playwright).start()
        print(f'Успешно')
    except Exception as exp:
        print(exp)
        # send_logs_to_telegram(message=f'Произошла ошибка!\n\n\n{exp}')
    t2 = datetime.datetime.now()
    print(f'Finish: {t2}, TIME: {t2 - t1}')
    # send_logs_to_telegram(message=f'Finish: {t2}, TIME: {t2 - t1}')


if __name__ == '__main__':
    main()
