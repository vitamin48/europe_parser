import asyncio
from playwright.async_api import async_playwright, TimeoutError
from tqdm import tqdm


async def main():
    """
    Основная асинхронная функция для парсинга ссылок на товары.
    """
    input_file = "in/arts_for_get_product_links.txt"
    output_file = "out/product_links_from_arts.txt"
    base_url = "https://europa-market.ru"

    print("Запуск парсера...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # Установите headless=False, чтобы видеть окно браузера
        page = await browser.new_page()

        try:
            with open(input_file, "r", encoding="utf-8") as articles_file:
                articles = articles_file.readlines()
        except FileNotFoundError:
            print(f"Ошибка: Файл '{input_file}' не найден. Пожалуйста, создайте его и добавьте артикулы.")
            await browser.close()
            return

        with open(output_file, "a", encoding="utf-8") as results_file:
            for article in tqdm(articles):
                article_clean = article.strip()
                if not article_clean:
                    continue

                search_url = f"{base_url}/catalog?search={article_clean}"
                print(f"Обрабатывается артикул: {article_clean} -> {search_url}")

                try:
                    await page.goto(search_url, wait_until="networkidle", timeout=30000)

                    # Проверяем, есть ли сообщение о том, что товар не найден
                    not_found_locator = page.locator('text="Нет подходящих товаров"')

                    if await not_found_locator.is_visible(timeout=7000):
                        print(f"Товар с артикулом {article_clean} не найден.")
                        results_file.write(f"{article_clean}\tНе найден\n")
                    else:
                        # Ищем ссылку на карточку товара
                        product_link_locator = page.locator("div.product-card a").first

                        try:
                            href = await product_link_locator.get_attribute("href", timeout=7000)
                            full_url = f"{base_url}{href}"
                            print(f"Найдена ссылка: {full_url}")
                            results_file.write(f"{article_clean}\t{full_url}\n")
                        except TimeoutError:
                            print(f"Не удалось найти ссылку для артикула {article_clean} на странице.")
                            results_file.write(f"{article_clean}\tСсылка не найдена\n")

                except TimeoutError:
                    print(f"Ошибка: не удалось загрузить страницу для артикула {article_clean}. Пропускаем.")
                    results_file.write(f"{article_clean}\tОшибка загрузки страницы\n")
                except Exception as e:
                    print(f"Произошла непредвиденная ошибка для артикула {article_clean}: {e}")
                    results_file.write(f"{article_clean}\tОшибка\n")

        await browser.close()
        print(f"Работа завершена. Результаты сохранены в файл '{output_file}'.")


if __name__ == "__main__":
    asyncio.run(main())
