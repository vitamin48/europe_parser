"""Скрипт на основе playwright считывает каталоги europa-market.ru из файла catalogs_for_get_links.txt и собирает
ссылки со всех имеющихся страниц в файл out/url_list_product.txt с учетом цены или без.
Остатки приблизительны. Количество товаров может зависеть от адреса магазина до 2 раз.
Особенность: исключить брэнд Собственное производство

**************************************************
Как получить список новых товаров для выгрузки?
1. Получаем список всех товаров из магазина Ozon
2. Выбираем желаемые категории для парса и собираем ссылки.
3. Собираем в одном месте все ссылки на товары с нежелательным брендом.
4. Собираем в одном месте все ссылки на товары, которые не стали грузить (например, хлеб)
5. Вы читаем из п.2 ссылки из пунктов 1, 3 и 4.

ДОРАБОТКА:
- Если в каталоге 60 товаров, то будет ошибка, т.к. не перейдет на 2 страницу (наверное)
"""

import time
import re
import datetime
from playwright.sync_api import sync_playwright
import traceback
from tqdm import tqdm

from config import send_logs_to_telegram, bcolors

ADDRESS_SHOP = 'Брянск-58, ул. Горбатова, 18'


def read_catalogs_from_txt():
    """Считывает и возвращает список каталогов из файла"""
    with open('in/catalogs_for_get_links.txt', 'r', encoding='utf-8') as file:
        catalogs = [f'{line}'.rstrip() for line in file]
    return catalogs


def add_to_txt_file_url_product(urls):
    with open('out/url_list_product.txt', 'a', encoding='utf-8') as output:
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
        self.click = 1

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
            print('Устанавливаем город и адрес...')
            self.page.goto("https://europa-market.ru/", timeout=60000)
            # Ждем загрузки, иногда бывают модалки
            self.page.wait_for_load_state('domcontentloaded')

            try:
                self.page.get_by_role("button", name="Принять").click(timeout=5000)
            except:
                pass

            self.page.get_by_role("button", name="Нет, выбрать другой город").click()
            self.page.get_by_text("Брянск").click()
            self.page.get_by_role("button", name="Выбрать").click()
            time.sleep(2)

            # Открываем выбор адреса (клик по шапке адреса)
            try:
                self.page.get_by_text("Выберите доставка или самовывоз").nth(1).click()
            except:
                # Альтернативный селектор
                self.page.locator(".user-address").click()

            self.page.get_by_role("button", name="Самовывоз").click()
            self.page.locator("div").filter(has_text=re.compile(r"^Нажмите, чтобы выбрать адрес$")).nth(1).click()
            self.page.get_by_text("241001").click()  # Индекс магазина на Горбатова
            self.page.get_by_role("button", name="Применить").click()

            print(f'{bcolors.OKGREEN}Адрес установлен: {ADDRESS_SHOP}{bcolors.ENDC}')
            time.sleep(5)
        except Exception as exp:
            print(f'{bcolors.FAIL}Критическая ошибка при установке города:{bcolors.ENDC} {exp}')

    def check_ddos(self, title):
        if title == 'DDoS-Guard':
            return True
        return False

    def check_error_page(self):
        """Проверяет, не попали ли мы на страницу 'Страница не найдена' (конец пагинации)"""
        try:
            # Проверка по классу из твоего HTML
            if self.page.locator(".error-page").is_visible(timeout=2000):
                return True
            # Проверка по тексту заголовка
            if self.page.get_by_role("heading", name="Страница не найдена").is_visible(timeout=1000):
                return True
        except:
            pass
        return False

    def get_urls_from_page(self):
        # Ждем появления сетки товаров
        try:
            self.page.wait_for_selector('.category-products-list', timeout=10000)
        except:
            pass

        # ! ВАЖНОЕ ИЗМЕНЕНИЕ: ищем товары ТОЛЬКО внутри блока каталога .category-products-list
        # Это исключит товары из слайдеров "Вы смотрели" и "Популярное" внизу страницы
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

        add_to_txt_file_url_product(combined_data)
        return count

    def paginator(self):
        """Проходим по страницам"""
        while True:
            # 1. Проверка на конец каталога (страница 404 внутри сайта)
            if self.check_error_page():
                print(f'  -> {bcolors.WARNING}Конец каталога (стр {self.click} не существует).{bcolors.ENDC}')
                break

            # 2. Сбор данных
            count = self.get_urls_from_page()
            print(f'  -> Страница {self.click}: собрано {count} товаров.')

            if count == 0:
                # Если товаров 0 и это не ошибка, возможно пустая категория
                print('  -> Товаров нет, идем дальше.')
                break

            # 3. Переход на следующую страницу
            # Ищем кнопку "Вперёд" по тексту внутри span
            next_btn = self.page.locator("a.pagination__page:has(span.pagination__page-text:text('Вперёд'))")

            if next_btn.count() > 0 and next_btn.is_visible():
                self.click += 1
                # Скроллим к кнопке, чтобы футер не перекрывал
                next_btn.scroll_into_view_if_needed()
                try:
                    next_btn.click()
                    # Пауза, чтобы Vue/Nuxt успел подгрузить новый контент
                    time.sleep(5)
                    self.page.wait_for_load_state('domcontentloaded')
                except Exception as e:
                    print(f"Ошибка при переходе на следующую страницу: {e}")
                    break
            else:
                print('  -> Кнопка "Вперёд" не найдена. Это последняя страница.')
                break

    def get_arts_from_catalogs(self):
        for catalog in tqdm(self.catalogs, desc="Обработка каталогов"):
            print(f'\nКаталог: {catalog}')
            try:
                self.page.goto(catalog, timeout=60000)
                self.page.wait_for_load_state('domcontentloaded')

                if self.check_ddos(title=self.page.title()):
                    print(f'{bcolors.FAIL}DDOS. Ждем 60 с{bcolors.ENDC}')
                    time.sleep(60)
                    self.page.goto(catalog)

                self.click = 1
                self.paginator()
            except Exception as e:
                print(f"Ошибка в каталоге {catalog}: {e}")
                continue

    def start(self):
        self.set_city()
        self.get_arts_from_catalogs()


def main():
    t1 = datetime.datetime.now()
    print(f'Start: {t1}')
    # Очистим файл перед стартом, чтобы не дублировать при перезапусках
    # open('out/url_list_product.txt', 'w').close()

    try:
        with sync_playwright() as playwright:
            Europa(playwright=playwright).start()
        print(f'Успешно.')
    except Exception as exp:
        print(traceback.format_exc())
        send_logs_to_telegram(message=f'Ошибка step2:\n{exp}')
    t2 = datetime.datetime.now()
    print(f'Finish: {t2}, TIME: {t2 - t1}')
    # send_logs_to_telegram(message=f'Step 2 Finish: {t2}, TIME: {t2 - t1}')


if __name__ == '__main__':
    main()
