"""Скрипт на основе playwright считывает каталоги europa-market.ru из файла catalogs.txt и собирает ссылки со всех
имеющихся страниц в файл out/europa_articles.txt с учетом цены или без. Остатки приблизительны.
Особенность: исключить брэнд Собственное производство"""

import time
import datetime
from playwright.sync_api import Playwright, sync_playwright, expect
import traceback
from tqdm import tqdm

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


def add_to_txt_file_url_product(urls):
    with open('out/url_list_product.txt', 'a') as output:
        print('Добавляю в файл out/url_list_product.txt')
        for row in urls:
            output.write(str(f'{row}') + '\n')


class Europa:
    playwright = None
    browser = None
    page = None
    context = None

    def __init__(self, playwright):
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

    def view60(self):
        """Делаем вывод товаров по 60 шт на странице"""
        self.page.get_by_role("button", name="Выводить по").click()
        time.sleep(10)
        self.page.get_by_role("button", name="Выводить по 60").click()
        time.sleep(5)

    def check_ddos(self, title):
        """Проверяем, сработала ли DDOS защита, т.е. смотрим текст, что в заголовке"""
        if title == 'DDoS-Guard':
            return True
        else:
            return False

    def get_urls_from_page(self):
        # Извлечение ссылок на товары
        products = self.page.query_selector_all('.card-product-content__title')
        # Сохранение ссылок в списке
        links = [link.get_attribute('href') for link in products]
        # Сохранение имен в списке
        names = [name.text_content() for name in products]
        if len(links) != len(names):
            input('ОШИБКА! Количество имен и ссылок на странице не совпадают')
        # Объединение имен и ссылок с табуляцией
        combined_data = [f"{name.strip()}\thttps://europa-market.ru{link}" for name, link in zip(names, links)]
        add_to_txt_file_url_product(combined_data)
        return len(links)

    def paginator(self):
        """Пролистываем страницы, пока на странице не будет менее 60 товаров."""
        len_links = self.get_urls_from_page()
        if len_links < 60:
            return
        else:
            self.page.locator(".ui-pagination__pagination > div:nth-child(3) > .icon").click()
            time.sleep(10)
            self.paginator()

    def get_arts_from_catalogs(self):
        for catalog in tqdm(self.catalogs):
            print(f'Работаю с каталогом: {catalog}')
            self.page.goto(catalog)
            time.sleep(10)
            if self.check_ddos(title=self.page.title()):
                print(f'{bcolors.FAIL}DDOS. Ждем 60 с{bcolors.ENDC}')
                time.sleep(60)
                self.page.goto(catalog)
            # self.view60()
            self.paginator()

    def start(self):
        self.set_city()
        self.page.goto('https://europa-market.ru/catalog/sobstvennaya-torgovaya-marka-3')
        self.view60()
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
        print(traceback.format_exc())
        # send_logs_to_telegram(message=f'Произошла ошибка!\n\n\n{exp}')
    t2 = datetime.datetime.now()
    print(f'Finish: {t2}, TIME: {t2 - t1}')
    # send_logs_to_telegram(message=f'Finish: {t2}, TIME: {t2 - t1}')


if __name__ == '__main__':
    main()
