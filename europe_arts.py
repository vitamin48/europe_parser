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
            # Изменить город?
            change_sity = '//*[@id="__layout"]/div/div[1]/div/div[1]/div/button[2]/span'
            change_sity_btn = self.page.wait_for_selector(change_sity)
            change_sity_btn.click()
            # Брянск
            br_btn = ('#__layout > div > div.header-under > div > div.v--modal-overlay.scrollable > div > '
                   'div.v--modal-box.native-modal.v--modal > div > div > div.city-wrapper__options > '
                   'div.city-wrapper__presence > div > a:nth-child(2)')
            accept_br_city = self.page.wait_for_selector(br_btn)
            accept_br_city.click()
            # Изменить адрес доставки
            address_btn = '//*[@id="__layout"]/div/div[1]/div/div[1]/button[2]'
            wait_address_btn = self.page.wait_for_selector(address_btn)
            time.sleep(5)
            wait_address_btn.click()
            samovuzov_btn = ('#modals-container > div > div > div.v--modal-box.v--modal > '
                             'div > div.cartography-modal__header > div.cartography-modal__header-text > '
                             'div.cartography-modal__header-button.cartography-modal__header-button--active')

            print('time.sleep(30)')
            time.sleep(30)
        except Exception as exp:
            print(exp)
            print(traceback.format_exc())

    def get_arts_from_catalogs(self):
        for catalog in self.catalogs:
            print(f'Работаю с каталогом: {catalog}')

    def start(self):
        self.set_city()


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
