"""
Скрипт считывает файл JSON с товарами Фермера и записывает данные в Excel.
"""
import json
import pandas as pd

from openpyxl.utils import get_column_letter

FILE_NAME_JSON = 'result_merge_data.json'  # out/FILE_NAME_JSON


def read_json():
    with open(f'out/{FILE_NAME_JSON}', 'r', encoding='utf-8') as json_file:
        data = json.load(json_file)
        return data


def read_bad_brand():
    """Считывает и возвращает список нежелательных брендов"""
    with open('in/bad_brand.txt', 'r', encoding='utf-8') as file:
        brands = [line.strip().lower() for line in file if line.strip()]
    return set(brands)


def create_df_by_dict(data_dict):
    rows = []

    # Проходим по каждому ключу в словаре
    for key, value in data_dict.items():
        # Обработка характеристик
        characteristics = value.get("characteristics", {})
        brand = characteristics.get("Бренд", characteristics.get("Торговая марка", "NoName"))
        country = characteristics.get("Страна изготовитель", "Китай")
        # Обработка ВхШхГ
        dimensions = characteristics.get("ВхШхГ", "0.0х0.0х0.0")
        height, width, length = map(lambda x: round(float(x) * 10), dimensions.split("х"))
        # Обработка img_url
        img_urls = value.get("img_url", [])
        if len(img_urls) > 0:  # Извлечение первой ссылки и всех остальных
            img_url1 = img_urls[0]
            img_url2 = img_urls[1:]  # Все остальные ссылки
            # Преобразуем список ссылок в строку, разделенную запятой, или оставляем как есть.
            img_url2 = ", ".join(img_url2) if len(img_url2) > 0 else "-"
        else:
            img_url1 = "-"
            img_url2 = "-"
        # Подготовка строки
        row = {
            "Артикул": key,
            "Название": value.get("name", ""),
            "Цена": value.get("price", ""),
            "Остатки": value.get("stock", ""),
            "Описание": value.get("description", ""),
            "img_url1": img_url1,
            "img_url2": img_url2,
            "art_url": value.get("art_url", ""),
            "Бренд": brand,
            "Страна": country,
            "Ширина, мм": width,
            "Высота, мм": height,
            "Длина, мм": length,
            "Характеристики": str(characteristics)
        }
        rows.append(row)
    # Создание DataFrame из списка строк
    df = pd.DataFrame(rows)
    # Используем контекстный менеджер для установки опции и последующей инференции типов данных
    with pd.option_context("future.no_silent_downcasting", True):
        df["Остатки"] = df["Остатки"].replace("--", 5).infer_objects(copy=False)
    # Удаляем нежелательные бренды
    excluded_brands = read_bad_brand()
    df["Бренд_нижний_регистр"] = df["Бренд"].str.lower().str.strip()
    df_filtered = df[~df["Бренд_нижний_регистр"].isin(excluded_brands)].copy()
    df_filtered.drop(columns=["Бренд_нижний_регистр"], inplace=True)
    print()


if __name__ == '__main__':
    data_json = read_json()
    create_df_by_dict(data_dict=data_json)
