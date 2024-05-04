"""
Скрипт считывает файл JSON с товарами Фермера и записывает данные в Excel.
"""
import json
import pandas as pd

from openpyxl.utils import get_column_letter

FILE_NAME_JSON = 'data_261558_28171.json'  # out/FILE_NAME_JSON


def read_json():
    with open(f'out/{FILE_NAME_JSON}', 'r', encoding='utf-8') as json_file:
        data = json.load(json_file)
        return data


def create_df_by_dict(data_dict):
    """Создание DF из словаря"""
    pd.options.mode.copy_on_write = True
    """Из-за вложенности словарей преобразуем словарь к списку (df_list)"""
    df_list = []
    for art_id, data in data_dict.items():
        "Удаляем блок характеристики из data и превращаем его в отдельный словарь"
        characteristics = data.pop("characteristics", {})
        "Создаем словарь с Артикулами (row_data)"
        row_data = {"Артикул": art_id}
        "Обновляем словарь row_data другим словарем data, в котором все, кроме артикула и характеристик"
        row_data.update(data)
        "Обновляем словарь характеристиками (characteristics)"
        row_data.update(characteristics)
        "Добавляем результирующий словарь в список (df_list)"
        df_list.append(row_data)
    "Создаем DF на основе списка df_list"
    df = pd.DataFrame(df_list)
    print()


if __name__ == '__main__':
    data_json = read_json()
    create_df_by_dict(data_dict=data_json)
