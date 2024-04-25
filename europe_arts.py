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

            # self.page.goto("https://europa-market.ru/")
            # # Изменить город?
            # change_sity = '//*[@id="__layout"]/div/div[1]/div/div[1]/div/button[2]/span'
            # change_sity_btn = self.page.wait_for_selector(change_sity)
            # change_sity_btn.click()
            # # Брянск
            # br_btn = ('#__layout > div > div.header-under > div > div.v--modal-overlay.scrollable > div > '
            #           'div.v--modal-box.native-modal.v--modal > div > div > div.city-wrapper__options > '
            #           'div.city-wrapper__presence > div > a:nth-child(2)')
            # accept_br_city = self.page.wait_for_selector(br_btn)
            # accept_br_city.click()
            # time.sleep(5)
            # # Изменить адрес доставки
            # addr_btn = self.page.locator('text=Адрес доставки')
            # addr_btn.wait_for(timeout=9000, state="visible")
            # addr_btn.click()
            # # Самовывоз
            # pickup = self.page.locator('text=Самовывоз')
            # pickup.wait_for(timeout=9000, state="visible")
            # pickup.click()
            # time.sleep(5)
            # # Вводим адрес и нажимаем ENTER
            # change_addr = self.page.locator('text=Выберите магазин из списка')
            # change_addr.click()


            # dropdown_button_locator = self.page.locator('#vs9__combobox > div.vs__selected-options > input')
            # dropdown_button_locator.click()
            # address_locator = self.page.locator(f"text={ADDRESS_SHOP}")
            # address_locator.click()

            #
            # input_locator_address = self.page.locator('#vs9__combobox > div.vs__selected-options > input')
            # input_locator_address.fill(ADDRESS_SHOP)
            # input_locator_address.press('Enter')
            print('time.sleep(10)')
            time.sleep(10)
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
