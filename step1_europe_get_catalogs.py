"""
Скрипт загружает HTML https://europa-market.ru/ и извлекает все каталоги в файл, кроме тех, что в in/bad_catalogs.txt
"""

import requests
from bs4 import BeautifulSoup

with open('in/bad_catalogs.txt', 'r', encoding='utf-8') as file:
    bad_catalogs = [f'{line}'.rstrip() for line in file]


def extract_catalog_links(url, output_file):
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Ошибка при загрузке страницы: {response.status_code}")
        return
    print(f'Страница загружена {response.status_code}')
    soup = BeautifulSoup(response.text, 'html.parser')
    catalog_div = soup.find('div', class_='catalog-list-wrapper')
    if not catalog_div:
        print("Блок catalog-list-wrapper не найден")
        return

    links = ['https://europa-market.ru' + a['href'] for a in catalog_div.find_all('a', href=True) if
             'https://europa-market.ru' + a['href'] not in bad_catalogs]

    with open(output_file, 'w', encoding='utf-8') as file:
        file.write('\n'.join(links))

    print(f"Ссылки сохранены в {output_file}")


# Пример использования
url = "https://europa-market.ru/"  # Замените на нужный URL
output_file = "out/catalog_links.txt"
extract_catalog_links(url, output_file)
