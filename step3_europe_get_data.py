"""
Скрипт на основе playwright считывает ссылки на товары Европа из файла product_links_for_get_data.txt,
переходит по ним, предварительно установив город и адрес магазина из константы ADDRESS_SHOP,
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
import requests
import platform
import socket
import traceback
from playwright.sync_api import sync_playwright, Page, TimeoutError
from tqdm import tqdm
from colorama import init, Fore, Style

# --- НАСТРОЙКИ СКРИПТА ---
INPUT_URL_FILE = os.path.join("in", "product_links_for_get_data.txt")
OUTPUT_JSON_FILE = os.path.join("out", "data.json")
OUTPUT_FAILED_FILE = os.path.join("out", "articles_with_bad_req.txt")
DEBUG_DIR = os.path.join("out", "debug")

# Настройки подключения к Telegram (если есть)
try:
    from config import BOT_TOKEN, CHAT_ID
except ImportError:
    BOT_TOKEN, CHAT_ID = None, None

# Настройки парсера
# ВАЖНО: Код ниже жестко привязан к выбору магазина по индексу "241001",
# который соответствует этому адресу.
ADDRESS_SHOP = 'Брянск-58, ул. Горбатова, 18'
SHOP_INDEX_TO_CLICK = "241001"

HEADLESS_MODE = False
TIMEOUT = 45000
MAX_RETRIES = 3
PAUSE_BETWEEN_REQUESTS = (3, 7)
RESTART_BROWSER_EVERY_N_URLS = 100
CRASH_RECOVERY_WAIT_SECONDS = 300


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def send_logs_to_telegram(message: str):
    if not BOT_TOKEN or not CHAT_ID:
        print(Fore.YELLOW + "ПРЕДУПРЕЖДЕНИЕ: BOT_TOKEN или CHAT_ID не заданы. Уведомление не отправлено.")
        return
    try:
        platform_info = platform.system()
        hostname = socket.gethostname()
        user = os.getlogin()
        full_message = message + f'\n\n---\n🖥️ {platform_info}\n👤 {hostname}\\{user}'
        url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
        data = {"chat_id": CHAT_ID, "text": full_message}
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(Fore.RED + f"Критическая ошибка при отправке в Telegram: {e}")


def save_debug_info(page: Page, article_id: str):
    print(Fore.MAGENTA + f"!!! Сохраняю отладочную информацию для {article_id}...")
    os.makedirs(DEBUG_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = os.path.join(DEBUG_DIR, f"{article_id}_{timestamp}_debug.png")
    html_path = os.path.join(DEBUG_DIR, f"{article_id}_{timestamp}_debug.html")
    try:
        page.screenshot(path=screenshot_path, full_page=True)
        print(Fore.MAGENTA + f"  - Скриншот сохранен: {screenshot_path}")
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(page.content())
        print(Fore.MAGENTA + f"  - HTML-код сохранен: {html_path}")
    except Exception as e:
        print(Fore.RED + f"  - Не удалось сохранить отладочную информацию: {e}")


def read_urls_from_file(filepath: str) -> list[str]:
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    if not os.path.exists(filepath):
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('')
        print(Fore.YELLOW + f"Файл {filepath} не найден, создан пустой файл.")
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip().startswith('http')]
    unique_urls = list(dict.fromkeys(urls))
    print(f"Загружено {Fore.GREEN}{len(unique_urls)}{Style.RESET_ALL} уникальных ссылок из {filepath}.")
    return unique_urls


def load_existing_data(filepath: str) -> dict:
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    if not os.path.exists(filepath): return {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"Загружено {Fore.GREEN}{len(data)}{Style.RESET_ALL} уже собранных товаров из JSON.")
            return data
    except (json.JSONDecodeError, FileNotFoundError):
        print(Fore.YELLOW + f"ПРЕДУПРЕЖДЕНИЕ: JSON-файл {filepath} не найден или поврежден. Начинаем с нуля.")
        return {}


def save_json_data(data: dict, filepath: str):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def log_failed_url(url: str, reason: str, filepath: str):
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} | {reason} | {url}\n")


def get_article_from_url(url: str) -> str | None:
    match = re.search(r'-(\d+)$', url)
    return match.group(1) if match else None


def set_city(page: Page):
    try:
        print('Автоматическая установка города и магазина...')
        page.goto("https://europa-market.ru/", timeout=60000)

        print("1. Ждем окно выбора города и нажимаем 'Нет, выбрать другой'")
        page.get_by_role("button", name="Нет, выбрать другой").click(timeout=15000)
        time.sleep(2)

        print("2. Выбираем 'Брянск'")
        page.get_by_text("Брянск").click()
        time.sleep(2)

        if page.get_by_role("button", name="Выбрать").is_visible(timeout=3000):
            print("3. Нажимаем 'Выбрать'")
            page.get_by_role("button", name="Выбрать").click()
            time.sleep(3)

        print("4. Открываем меню выбора адреса/самовывоза")
        page.locator(".user-address--default").click()
        time.sleep(2)

        print("5. Переключаемся на вкладку 'Самовывоз'")
        page.get_by_role("button", name="Самовывоз").click()
        time.sleep(2)

        print("6. Открываем список магазинов")
        page.locator("div").filter(has_text=re.compile(r"^Нажмите, чтобы выбрать адрес$")).nth(1).click()
        time.sleep(2)

        print(f"7. Выбираем магазин по индексу '{SHOP_INDEX_TO_CLICK}'")
        page.get_by_text(SHOP_INDEX_TO_CLICK).click()
        time.sleep(2)

        print("8. Нажимаем 'Применить'")
        page.get_by_role("button", name="Применить").click()

        print(Fore.GREEN + f'Успешно установлен адрес: {ADDRESS_SHOP}')
        time.sleep(5)
        return True
    except Exception:
        print(Fore.RED + "Произошла ошибка при автоматической установке города.")
        print(traceback.format_exc())
        send_logs_to_telegram("🔴 ОШИБКА АВТОУСТАНОВКИ ГОРОДА!")
        return False


# ##################################################################
# ИЗМЕНЕННАЯ ФУНКЦИЯ ПАРСИНГА СТРАНИЦЫ
# ##################################################################
def parse_product_page(page: Page, product_url: str) -> dict | None:
    # ПРОВЕРКА №1: Проверяем, не является ли эта страница сообщением "Товар не найден"
    # Это самый надежный способ избежать ошибок на несуществующих страницах.
    try:
        # Ищем заголовок h1 с текстом "Товар не найден"
        not_found_heading = page.get_by_role("heading", name="Товар не найден")
        # Даем ему короткий таймаут. Если он есть - он появится быстро.
        if not_found_heading.is_visible(timeout=2500):
            print(Fore.YELLOW + f"  - Товар не найден (страница 404).")
            # Логируем и выходим из функции, возвращая None
            log_failed_url(product_url, "Товар не найден (404-style page)", OUTPUT_FAILED_FILE)
            return None
    except TimeoutError:
        # Это нормальная ситуация для валидной страницы, просто продолжаем
        pass
    except Exception as e:
        print(Fore.RED + f"  - Ошибка при проверке на 'Товар не найден': {e}")
        # В случае другой ошибки, лучше продолжить и дать основному блоку обработать ее
        pass

    # ПРОВЕРКА №2: Основной блок парсинга с проверкой на наличие блока с ценой
    # (для случаев, когда товар просто "не в наличии", но страница существует)
    try:
        cart_block = page.locator('.product-cart')
        cart_block.wait_for(timeout=7000)

        price_int_loc = cart_block.locator('.product-cart__price-int')
        price_frac_loc = cart_block.locator('.product-cart__price-frac span').first

        price_int = price_int_loc.text_content() if price_int_loc.count() > 0 else '0'
        price_frac = price_frac_loc.text_content() if price_frac_loc.count() > 0 else '00'
        price = float(f"{price_int}.{price_frac}")

    except TimeoutError:
        # Если блок с ценой не найден, это тоже неудача. Логируем и возвращаем None.
        print(Fore.YELLOW + f"  - Товар отсутствует в наличии (не найден блок с ценой).")
        log_failed_url(product_url, "Товар отсутствует (нет блока цены)", OUTPUT_FAILED_FILE)
        article_id = get_article_from_url(product_url) or "unknown"
        save_debug_info(page, f"{article_id}_no_price_block")
        return None
    except Exception as e:
        # Если произошла другая ошибка при получении цены, считаем это полноценной ошибкой
        # и пробрасываем ее выше, чтобы сработал механизм повторных попыток.
        raise ValueError(f"Не удалось получить цену: {e}")

    # --- Если прошли проверки, начинаем сбор остальных данных ---

    code_loc = page.locator('.product-info__sku')
    code = (re.search(r'\d+', code_loc.text_content()).group()
            if code_loc.count() > 0 and re.search(r'\d+', code_loc.text_content())
            else get_article_from_url(product_url))

    name_loc = page.locator('.product-title__name')
    name = name_loc.text_content().strip() if name_loc.count() > 0 else '-'

    stock = "В наличии"
    description = '-'
    characteristics_dict = {}

    nutrition_items = page.locator('.product-info__nutrition-item').all()
    for item in nutrition_items:
        key = item.locator('.product-info__nutrition-name').text_content().strip()
        value = item.locator('.product-info__nutrition-value').text_content().strip()
        characteristics_dict[key] = value

    params_container = page.locator('.product-info__params')
    if params_container.count() > 0:
        all_top_level_blocks = params_container.locator('> div').all()
        for block in all_top_level_blocks:
            block_class = block.get_attribute('class') or ''
            if 'product-info__params-block--columns' in block_class:
                inner_items = block.locator('.product-info__params-item').all()
                for inner_item in inner_items:
                    key_loc = inner_item.locator('.product-info__params-name')
                    value_loc = inner_item.locator('.product-info__params-value')
                    if key_loc.count() > 0 and value_loc.count() > 0:
                        characteristics_dict[key_loc.text_content().strip()] = value_loc.text_content().strip()
            else:
                key_loc = block.locator('.product-info__params-name')
                value_loc = block.locator('.product-info__params-value')
                if key_loc.count() > 0 and value_loc.count() > 0:
                    key = key_loc.text_content().strip()
                    value = value_loc.text_content().strip()
                    if 'описание' in key.lower():
                        description = value
                    else:
                        characteristics_dict[key] = value

    if not characteristics_dict and description == '-':
        log_failed_url(product_url, 'Блок описания/характеристик не найден', OUTPUT_FAILED_FILE)

    image_locators = page.locator('.product-image__image-slider img').all()
    image_links = [loc.get_attribute('src').split('?')[0] for loc in image_locators if loc.get_attribute('src')]
    if not image_links:
        log_failed_url(product_url, 'Блок с изображениями не найден', OUTPUT_FAILED_FILE)

    return {
        'name': name, 'price': price, 'stock': stock, 'description': description,
        'characteristics': characteristics_dict, 'img_url': image_links, 'art_url': product_url
    }


# ##################################################################

def main():
    init(autoreset=True)
    start_time = datetime.datetime.now()
    start_message = f"🚀 Парсер Europa-Market запущен в {start_time.strftime('%H:%M:%S')}"
    print(Fore.CYAN + start_message)
    send_logs_to_telegram(start_message)

    try:
        urls_to_parse = read_urls_from_file(INPUT_URL_FILE)
        all_data = load_existing_data(OUTPUT_JSON_FILE)
        initial_data_count = len(all_data)

        urls_to_process = [url for url in urls_to_parse if get_article_from_url(url) not in all_data]

        if not urls_to_process:
            print(Fore.YELLOW + "Все товары из списка уже обработаны. Завершение работы.")
            send_logs_to_telegram("✅ Все товары уже обработаны. Новых ссылок нет.")
            return

        print(f"К обработке {Fore.CYAN}{len(urls_to_process)}{Style.RESET_ALL} новых ссылок.")

        with sync_playwright() as p:
            browser = None
            context = None
            page = None

            def launch_browser():
                nonlocal browser, context, page
                if browser:
                    try:
                        browser.close()
                    except Exception as e:
                        print(Fore.YELLOW + f"Не удалось корректно закрыть браузер: {e}")

                print(Fore.CYAN + "\n--- Запускаю новый экземпляр браузера ---")
                browser = p.chromium.launch(headless=HEADLESS_MODE)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36")
                context.set_default_timeout(TIMEOUT)
                page = context.new_page()

                if not set_city(page):
                    raise RuntimeError("Не удалось установить город, дальнейшая работа невозможна.")

            launch_browser()

            for i, url in enumerate(tqdm(urls_to_process, desc="Сбор данных")):
                if i > 0 and i % RESTART_BROWSER_EVERY_N_URLS == 0:
                    print(Fore.CYAN + f"\nОбработано {i} ссылок. Плановый перезапуск браузера...")
                    launch_browser()

                product_data = None
                article_id = get_article_from_url(url)
                if not article_id:
                    log_failed_url(url, "Некорректный URL", OUTPUT_FAILED_FILE)
                    continue

                for attempt in range(MAX_RETRIES):
                    try:
                        page.goto(url, wait_until="domcontentloaded")

                        title = page.title()
                        if "ddos" in title.lower():
                            raise ValueError("Обнаружена DDOS-защита")

                        # Функция теперь сама обрабатывает страницы "не найдено" и возвращает None
                        product_data = parse_product_page(page, url)
                        # Если данные получены (не None), выходим из цикла попыток
                        if product_data:
                            break
                        # Если parse_product_page вернула None, это значит товар не найден или не в наличии.
                        # Это не ошибка, которую нужно повторять, а констатация факта. Поэтому тоже выходим.
                        else:
                            break  # Выходим из цикла for attempt, т.к. повторять нет смысла

                    except Exception as e:
                        error_text = str(e)
                        print(Fore.RED + f"\n  [Попытка {attempt + 1}] ОШИБКА: {error_text[:200]}")

                        if "crashed" in error_text.lower():
                            print(Fore.RED + Style.BRIGHT + "!!! ОБНАРУЖЕНО ПАДЕНИЕ СТРАНИЦЫ !!!")
                            send_logs_to_telegram(
                                f"🟡 ВНИМАНИЕ: Страница упала (crashed). Перезапускаю браузер через {CRASH_RECOVERY_WAIT_SECONDS} сек.")
                            time.sleep(CRASH_RECOVERY_WAIT_SECONDS)
                            launch_browser()
                            continue

                        debug_id = f"{article_id}_attempt_{attempt + 1}"
                        save_debug_info(page, debug_id)
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(10)

                # Сохраняем данные только если они были успешно собраны
                if product_data:
                    all_data[article_id] = product_data
                    save_json_data(all_data, OUTPUT_JSON_FILE)
                # Если product_data это None после всех попыток (или после одной, если товар не найден)
                elif attempt == MAX_RETRIES - 1:  # Логируем окончательную неудачу только если это была реальная ошибка
                    print(Fore.RED + Style.BRIGHT + f"!!! НЕ УДАЛОСЬ обработать {url} после {MAX_RETRIES} попыток.")
                    log_failed_url(url, "Не удалось спарсить после всех попыток", OUTPUT_FAILED_FILE)

                time.sleep(random.uniform(*PAUSE_BETWEEN_REQUESTS))

            if browser: browser.close()

        end_time = datetime.datetime.now()
        duration = end_time - start_time
        newly_added_count = len(all_data) - initial_data_count

        finish_message = (
            f"✅ Парсер Europa-Market успешно завершил работу.\n\n"
            f"👍 Добавлено новых товаров: {newly_added_count}\n"
            f"💾 Всего товаров в базе: {len(all_data)}\n"
            f"🕒 Время выполнения: {str(duration).split('.')[0]}"
        )
        print("-" * 50)
        print(Fore.CYAN + finish_message)
        send_logs_to_telegram(finish_message)

    except Exception as e:
        error_message = f"❌ КРИТИЧЕСКАЯ ОШИБКА в парсере!\n\nСкрипт аварийно завершился.\n\nОшибка:\n{traceback.format_exc()}"
        print(Fore.RED + Style.BRIGHT + error_message)
        send_logs_to_telegram(error_message)


if __name__ == '__main__':
    main()
