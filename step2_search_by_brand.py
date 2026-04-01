"""
Скрипт считывает бренды из in/target_brands.txt, вбивает их в поиск на сайте,
собирает все ссылки из выдачи (с учетом пагинации) и сохраняет в in/product_links_for_get_data.txt
"""

import time
import re
import urllib.parse
import datetime
from playwright.sync_api import sync_playwright
import traceback
from tqdm import tqdm

from config import bcolors

ADDRESS_SHOP = 'Брянск-58, ул. Горбатова, 18'
TARGET_BRANDS_FILE = 'in/target_brands.txt'
OUTPUT_LINKS_FILE = 'in/product_links_for_get_data.txt'


def read_brands_from_txt():
    """Считывает список брендов из файла"""
    try:
        with open(TARGET_BRANDS_FILE, 'r', encoding='utf-8') as file:
            brands = [line.strip() for line in file if line.strip()]
        return brands
    except FileNotFoundError:
        print(f"{bcolors.FAIL}Ошибка: Файл {TARGET_BRANDS_FILE} не найден!{bcolors.ENDC}")
        return []


def add_to_txt_file_url_product(urls):
    """Добавляет собранные ссылки в файл"""
    with open(OUTPUT_LINKS_FILE, 'a', encoding='utf-8') as output:
        for row in urls:
            output.write(str(f'{row}') + '\n')


class EuropaSearch:
    def __init__(self, playwright):
        self.brands = read_brands_from_txt()
        self.click = 1
        # Настройка Playwright
        js = "Object.defineProperties(navigator, {webdriver:{get:()=>undefined}});"
        self.browser = playwright.chromium.launch(headless=False, args=['--blink-settings=imagesEnabled=false'])
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.page.add_init_script(js)

    def set_city(self):
        try:
            print('Устанавливаем город и адрес...')
            self.page.goto("https://europa-market.ru/", timeout=60000)
            self.page.wait_for_load_state('domcontentloaded')

            try:
                self.page.get_by_role("button", name="Принять").click(timeout=5000)
            except:
                pass

            self.page.get_by_role("button", name="Нет, выбрать другой город").click()
            self.page.get_by_text("Брянск").click()
            self.page.get_by_role("button", name="Выбрать").click()
            time.sleep(2)

            try:
                self.page.get_by_text("Выберите доставка или самовывоз").nth(1).click()
            except:
                self.page.locator(".user-address").click()

            self.page.get_by_role("button", name="Самовывоз").click()
            self.page.locator("div").filter(has_text=re.compile(r"^Нажмите, чтобы выбрать адрес$")).nth(1).click()
            self.page.get_by_text("241001").click()
            self.page.get_by_role("button", name="Применить").click()

            print(f'{bcolors.OKGREEN}Адрес установлен: {ADDRESS_SHOP}{bcolors.ENDC}')
            time.sleep(5)
        except Exception as exp:
            print(f'{bcolors.FAIL}Ошибка при установке города:{bcolors.ENDC} {exp}')

    def check_error_page(self):
        try:
            if self.page.locator(".error-page").is_visible(timeout=2000): return True
            if self.page.get_by_role("heading", name="Страница не найдена").is_visible(timeout=1000): return True
        except:
            pass
        return False

    def get_urls_from_page(self):
        try:
            self.page.wait_for_selector('.category-products-list', timeout=10000)
        except:
            pass

        product_elements = self.page.query_selector_all('.category-products-list a.product-card__content')
        combined_data = []
        count = 0

        for element in product_elements:
            try:
                link = element.get_attribute('href')
                name_el = element.query_selector('.product-card__title')
                name = name_el.text_content().strip() if name_el else "No Name"

                if link:
                    code = link.split('-')[-1]
                    full_url = f"https://europa-market.ru{link}"
                    combined_data.append(f"e_{code}\t{name}\t{full_url}")
                    count += 1
            except Exception:
                continue

        if combined_data:
            add_to_txt_file_url_product(combined_data)
        return count

    def paginator(self):
        while True:
            if self.check_error_page():
                print(f'  -> {bcolors.WARNING}Конец выдачи.{bcolors.ENDC}')
                break

            count = self.get_urls_from_page()
            print(f'  -> Страница {self.click}: собрано {count} товаров.')

            if count == 0:
                break

            next_btn = self.page.locator("a.pagination__page:has(span.pagination__page-text:text('Вперёд'))")
            if next_btn.count() > 0 and next_btn.is_visible():
                self.click += 1
                next_btn.scroll_into_view_if_needed()
                try:
                    next_btn.click()
                    time.sleep(5)
                    self.page.wait_for_load_state('domcontentloaded')
                except:
                    break
            else:
                break

    def get_arts_from_search(self):
        if not self.brands:
            return

        for brand in tqdm(self.brands, desc="Поиск брендов"):
            print(f'\nПоиск бренда: {brand}')
            search_url = f"https://europa-market.ru/catalog?search={urllib.parse.quote(brand)}"

            try:
                self.page.goto(search_url, timeout=60000)
                self.page.wait_for_load_state('domcontentloaded')

                # Проверяем, есть ли результаты
                if self.page.locator('text="Нет подходящих товаров"').is_visible(timeout=3000):
                    print(f'{bcolors.WARNING}По запросу "{brand}" товары не найдены.{bcolors.ENDC}')
                    continue

                self.click = 1
                self.paginator()
            except Exception as e:
                print(f"Ошибка при поиске {brand}: {e}")
                continue

    def start(self):
        self.set_city()
        self.get_arts_from_search()
        self.browser.close()


def main():
    t1 = datetime.datetime.now()
    print(f'Start: {t1}')

    # Очищаем файл перед новым сбором, чтобы не было старых ссылок
    open(OUTPUT_LINKS_FILE, 'w', encoding='utf-8').close()

    try:
        with sync_playwright() as playwright:
            EuropaSearch(playwright=playwright).start()
        print(f'Сбор ссылок успешно завершен.')
    except Exception as exp:
        print(traceback.format_exc())

    t2 = datetime.datetime.now()
    print(f'Finish: {t2}, TIME: {t2 - t1}')


if __name__ == '__main__':
    main()
