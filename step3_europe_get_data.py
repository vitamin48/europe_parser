# step3_europe_get_data.py

"""
Скрипт на основе playwright считывает ссылки на товары Европа из файла product_links_for_get_data.txt,
переходит по ним, предварительно установив город и адрес магазина,
считывает информацию каждого товара, записывает результаты в файл JSON.

Помимо результирующего файла JSON, формируются дополнительные файлы:
articles_with_bad_req.txt - для ссылок, которые не удалось загрузить, либо товар из списка нежелательных
брэндов, либо другая ошибка с указанием этой ошибки
"""

import os
import time
import datetime
import json
import random
import re
import traceback
from playwright.sync_api import sync_playwright, Page, TimeoutError
from tqdm import tqdm
from colorama import init, Fore, Style

# --- НАСТРОЙКИ СКРИПТА ---
INPUT_URL_FILE = os.path.join("in", "product_links_for_get_data.txt")
OUTPUT_JSON_FILE = os.path.join("out", "data.json")
OUTPUT_FAILED_FILE = os.path.join("out", "articles_with_bad_req.txt")
DEBUG_DIR = os.path.join("out", "debug")

ADDRESS_SHOP = 'Брянск-58, ул. Горбатова, 18'
# Индекс магазина для клика в списке
SHOP_INDEX_TO_CLICK = "241001"

HEADLESS_MODE = False  # False чтобы видеть браузер
MAX_RETRIES = 3
PAUSE_BETWEEN_REQUESTS = (1.0, 2.5)
RESTART_BROWSER_EVERY_N_URLS = 100


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def send_logs_to_telegram(message):
    # Заглушка
    pass


def save_debug_info(page: Page, article_id: str):
    """Сохраняет скриншот и HTML страницы при возникновении ошибки."""
    print(f"{Fore.MAGENTA}!!! Сохраняю отладочную информацию для {article_id}...{Style.RESET_ALL}")
    os.makedirs(DEBUG_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = os.path.join(DEBUG_DIR, f"{article_id}_{timestamp}_debug.png")
    html_path = os.path.join(DEBUG_DIR, f"{article_id}_{timestamp}_debug.html")
    try:
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"{Fore.MAGENTA}  - Скриншот сохранен: {screenshot_path}{Style.RESET_ALL}")
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(page.content())
        print(f"{Fore.MAGENTA}  - HTML-код сохранен: {html_path}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}  - Не удалось сохранить отладочную информацию: {e}{Style.RESET_ALL}")


def read_urls_from_file(filepath: str) -> list[str]:
    """Читает ссылки из файла."""
    if not os.path.exists(filepath):
        print(f"{Fore.RED}Файл {filepath} не найден!{Style.RESET_ALL}")
        return []

    with open(filepath, 'r', encoding='utf-8') as f:
        urls = []
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 3:
                urls.append(parts[2])
            elif line.strip().startswith('http'):
                urls.append(line.strip())

    unique_urls = list(dict.fromkeys(urls))
    print(f"Загружено {len(unique_urls)} уникальных ссылок.")
    return unique_urls


def load_existing_data(filepath: str) -> dict:
    """Загружает уже собранные данные."""
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"В базе уже есть {Fore.GREEN}{len(data)}{Style.RESET_ALL} товаров.")
            return data
    except json.JSONDecodeError:
        return {}


def save_json_data(data: dict, filepath: str):
    """Сохраняет данные в JSON."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def log_failed_url(url: str, reason: str, filepath: str):
    """Логирует битые ссылки."""
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} | {reason} | {url}\n")


def get_article_from_url(url: str) -> str | None:
    """Извлекает артикул из URL (цифры в конце)."""
    match = re.search(r'-(\d+)$', url)
    return match.group(1) if match else None


def set_city(page):
    """Устанавливает город и магазин (Брянск)."""
    try:
        print('Устанавливаем город и адрес...')
        page.goto("https://europa-market.ru/", timeout=60000)
        # Ждем загрузки, иногда бывают модалки
        page.wait_for_load_state('domcontentloaded')

        try:
            page.get_by_role("button", name="Принять").click(timeout=5000)
        except:
            pass

        # Логика открытия окна выбора города
        try:
            page.get_by_role("button", name="Нет, выбрать другой город").click(timeout=3000)
        except:
            pass

        # Выбор Брянска
        try:
            page.get_by_text("Брянск").click(timeout=3000)
            page.get_by_role("button", name="Выбрать").click(timeout=3000)
            time.sleep(2)
        except:
            pass

            # Открываем выбор адреса
        try:
            page.get_by_text("Выберите доставка или самовывоз").nth(1).click(timeout=3000)
        except:
            # Альтернативный селектор
            page.locator(".user-address").click()

        # Выбор самовывоза
        try:
            page.get_by_role("button", name="Самовывоз").click()
            page.locator("div").filter(has_text=re.compile(r"^Нажмите, чтобы выбрать адрес$")).nth(1).click()
            page.get_by_text(SHOP_INDEX_TO_CLICK).click()
            page.get_by_role("button", name="Применить").click()
            print(f'{Fore.GREEN}Адрес установлен: {ADDRESS_SHOP}{Style.RESET_ALL}')
            time.sleep(5)
            return True
        except Exception as e:
            print(f'{Fore.RED}Ошибка при выборе конкретного магазина: {e}{Style.RESET_ALL}')
            return False

    except Exception as exp:
        print(f'{Fore.RED}Критическая ошибка при установке города: {exp}{Style.RESET_ALL}')
        return False


def parse_product_page(page, product_url: str) -> dict | None:
    """Парсит страницу товара."""

    # 1. Проверка на 404
    try:
        if page.locator(".error-page").is_visible(timeout=1500) or \
                page.get_by_role("heading", name="Страница не найдена").is_visible(timeout=500):
            print(f"{Fore.YELLOW}  - Товар не найден (404).{Style.RESET_ALL}")
            log_failed_url(product_url, "404 Not Found", OUTPUT_FAILED_FILE)
            return None
    except:
        pass

    # 2. Ожидание загрузки
    try:
        page.wait_for_selector('.product-title__name', timeout=5000)
    except TimeoutError:
        print(f"{Fore.YELLOW}  - Не дождались загрузки карточки товара.{Style.RESET_ALL}")
        log_failed_url(product_url, "Timeout loading card", OUTPUT_FAILED_FILE)
        return None

    # 3. Сбор данных
    try:
        # --- Название ---
        name = page.locator('.product-title__name').text_content().strip()

        # --- Цена ---
        try:
            # Берем только целую часть цены
            price_text = page.locator('.product-cart__price-int').first.text_content().strip()

            # Удаляем пробелы и неразрывные пробелы
            price_clean = price_text.replace(' ', '').replace('\xa0', '')

            # Конвертируем в число (целое)
            price = float(price_clean)
        except:
            price = 0.0
            print(f"{Fore.YELLOW}  - Цена не найдена (возможно, нет в наличии).{Style.RESET_ALL}")

        # --- Характеристики и Описание ---
        characteristics_dict = {}
        description = ""

        # Ищем контейнер с параметрами
        keys = page.locator('.product-info__params-name').all()
        values = page.locator('.product-info__params-value').all()

        if len(keys) == len(values):
            for k, v in zip(keys, values):
                key_text = k.text_content().strip()
                val_text = v.text_content().strip()

                if "описание" in key_text.lower():
                    description = val_text

                characteristics_dict[key_text] = val_text
        else:
            print(f"{Fore.RED}  - Ошибка сбора характеристик (несовпадение полей).{Style.RESET_ALL}")

        # --- Изображения ---
        image_links = []
        slider = page.locator('.product-image__image-slider')
        if slider.count() > 0:
            imgs = slider.locator('img').all()
            for img in imgs:
                src = img.get_attribute('src')
                if src:
                    image_links.append(src)
        # Удаляем дубликаты
        image_links = list(dict.fromkeys(image_links))

        return {
            'name': name,
            'price': price,
            'description': description,
            'characteristics': characteristics_dict,
            'img_url': image_links,
            'art_url': product_url
        }

    except Exception as e:
        print(f"{Fore.RED}  - Ошибка парсинга полей: {e}{Style.RESET_ALL}")
        # Сохраняем отладку при ошибке парсинга полей
        art = get_article_from_url(product_url) or "unknown"
        save_debug_info(page, art)
        raise e


def main():
    init(autoreset=True)
    start_time = datetime.datetime.now()
    print(f"{Fore.CYAN}🚀 Парсер запущен: {start_time.strftime('%H:%M:%S')}{Style.RESET_ALL}")

    try:
        urls_to_parse = read_urls_from_file(INPUT_URL_FILE)
        all_data = load_existing_data(OUTPUT_JSON_FILE)

        # Фильтруем уже собранные
        urls_to_process = [url for url in urls_to_parse if get_article_from_url(url) not in all_data]

        if not urls_to_process:
            print(f"{Fore.YELLOW}Все товары уже собраны.{Style.RESET_ALL}")
            return

        print(f"Осталось обработать: {Fore.CYAN}{len(urls_to_process)}{Style.RESET_ALL} товаров.")

        with sync_playwright() as p:
            browser = None
            context = None
            page = None

            def launch_browser_func():
                nonlocal browser, context, page
                if browser:
                    try:
                        browser.close()
                    except:
                        pass

                print(f"{Fore.CYAN}\n--- Запуск браузера ---{Style.RESET_ALL}")
                browser = p.chromium.launch(headless=HEADLESS_MODE, args=['--start-maximized'])
                # Указываем viewport null, чтобы окно развернулось на полный экран
                context = browser.new_context(viewport=None)
                page = context.new_page()

                page.add_init_script("Object.defineProperties(navigator, {webdriver:{get:()=>undefined}});")

                if not set_city(page):
                    print(f"{Fore.RED}Внимание! Город мог не установиться корректно.{Style.RESET_ALL}")

            # Первый запуск
            launch_browser_func()

            url_counter = 0

            with tqdm(total=len(urls_to_process), desc="Сбор данных", unit="tov") as pbar:
                for url in urls_to_process:
                    article_id = get_article_from_url(url)
                    if not article_id:
                        pbar.update(1)
                        continue

                    pbar.set_description(f"Арт: {article_id}")

                    # Рестарт браузера
                    url_counter += 1
                    if url_counter % RESTART_BROWSER_EVERY_N_URLS == 0:
                        launch_browser_func()

                    product_data = None

                    for attempt in range(MAX_RETRIES):
                        try:
                            product_data = parse_product_page(page, url)
                            if product_data is not None:
                                break
                            else:
                                break
                        except Exception as e:
                            print(f"\n{Fore.RED}Ошибка {url}: {e}{Style.RESET_ALL}")
                            if attempt < MAX_RETRIES - 1:
                                time.sleep(2)
                                try:
                                    page.reload()
                                except:
                                    launch_browser_func()
                            else:
                                log_failed_url(url, f"Exception: {e}", OUTPUT_FAILED_FILE)
                                # Сохраняем отладку при фатальной ошибке после всех попыток
                                save_debug_info(page, article_id)

                    if product_data:
                        all_data[article_id] = product_data
                        if url_counter % 10 == 0:
                            save_json_data(all_data, OUTPUT_JSON_FILE)

                    pbar.update(1)
                    time.sleep(random.uniform(*PAUSE_BETWEEN_REQUESTS))

            save_json_data(all_data, OUTPUT_JSON_FILE)
            if browser: browser.close()

        end_time = datetime.datetime.now()
        duration = end_time - start_time
        print(f"{Fore.GREEN}Готово! Обработано за {str(duration).split('.')[0]}{Style.RESET_ALL}")
        print(f"Всего товаров в базе: {len(all_data)}")

    except Exception as e:
        print(f"{Fore.RED}Критическая ошибка Main: {e}{Style.RESET_ALL}")
        traceback.print_exc()


if __name__ == '__main__':
    main()
