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


def transform_price(x):
    result = x * 5 if x < 200 else (
        x * 4.5 if 200 <= x < 500 else (
            x * 4 if 500 <= x < 1000 else (
                x * 3.5 if 1000 <= x < 5000 else (
                    x * 3 if 5000 <= x < 10000 else (
                        x * 2.5 if 10000 <= x < 20000 else (x * 2))))))
    # Убеждаемся, что значение после преобразований не меньше 490
    result = max(result, 490)
    # Округление до целого числа
    return round(result)


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
            "ArtNumber": key,
            "Название": value.get("name", ""),
            "Цена Европы": value.get("price", ""),
            "Остатки": value.get("stock", ""),
            "Описание": value.get("description", ""),
            "Ссылка на главное фото товара": img_url1,
            "Ссылки на другие фото товара": img_url2,
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
    df_filtered["Артикул"] = df_filtered["ArtNumber"].apply(lambda art: f'e_{art}')
    # Добавляем столбец Цена для OZON
    df_filtered['Цена для OZON'] = df_filtered['Цена Европы'].apply(transform_price)
    # Добавляем столбец Цена до скидки
    df_filtered['Цена до скидки'] = df_filtered['Цена для OZON'].apply(lambda x: int(round(x * 1.3)))
    # Добавляем столбец НДС Не облагается
    df_filtered["НДС"] = "Не облагается"
    # Задаем порядок столбцов
    desired_order = ['Артикул', 'Название', 'Цена для OZON', 'Цена до скидки', 'НДС', 'Цена Европы', 'Ширина, мм',
                     'Высота, мм', 'Длина, мм', 'Ссылка на главное фото товара', 'Ссылки на другие фото товара',
                     'Бренд', 'ArtNumber', 'Описание', 'Страна', 'art_url']
    result_df = df_filtered[desired_order]
    return result_df


def create_xls(df):
    file_name = f'out\\Europe.xlsx'
    # Сохранение DataFrame в Excel с использованием Styler
    with pd.ExcelWriter(file_name, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='OZON', index=False, na_rep='NaN')
        # Установка ширины столбцов
        worksheet_ozon = writer.sheets['OZON']
        for column in df:
            column_width = max(df[column].astype(str).map(len).max(), len(column)) + 2
            col_letter = get_column_letter(df.columns.get_loc(column) + 1)
            worksheet_ozon.column_dimensions[col_letter].width = column_width
        # Закрепите первую строку
        worksheet_ozon.freeze_panes = 'A2'
        # Корректировка ширины столбцов
        worksheet_ozon.column_dimensions[get_column_letter(df.columns.get_loc('Название') + 1)].width = 30
        worksheet_ozon.column_dimensions[get_column_letter(df.columns.get_loc('Описание') + 1)].width = 30
        worksheet_ozon.column_dimensions[
            get_column_letter(df.columns.get_loc('Ссылка на главное фото товара') + 1)].width = 30
        worksheet_ozon.column_dimensions[
            get_column_letter(df.columns.get_loc('Ссылки на другие фото товара') + 1)].width = 30
        worksheet_ozon.column_dimensions[
            get_column_letter(df.columns.get_loc('art_url') + 1)].width = 20


if __name__ == '__main__':
    data_json = read_json()
    df = create_df_by_dict(data_dict=data_json)
    create_xls(df)
