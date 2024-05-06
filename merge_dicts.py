"""Скрипт объединяет все словари с товарами из файлов JSON и сохраняет в отдельный JSON:
merge_dictionaries\\result_merge\\data.json"""
import os
import json

# Получаем текущий путь к скрипту
current_directory = os.path.dirname(os.path.realpath(__file__))
# Путь к папке с JSON файлами (может потребоваться изменить в соответствии с вашей структурой папок)
json_folder_path = os.path.join(current_directory, 'out')
# Общий словарь, в который будут объединяться данные
merged_dict = {}
# Проходим по всем файлам в папке
for filename in os.listdir(json_folder_path):
    # Проверяем, является ли файл JSON
    if filename.endswith('.json'):
        # Формируем полный путь к файлу
        filepath = os.path.join(json_folder_path, filename)

        # Читаем содержимое файла JSON
        with open(filepath, 'r', encoding='utf-8') as file:
            json_content = json.load(file)

        # Объединяем данные из текущего файла в общий словарь
        merged_dict.update(json_content)

with open('out\\result_merge_data.json', 'w', encoding='utf-8') as json_file:
    json.dump(merged_dict, json_file, indent=2, ensure_ascii=False)

print('Успешно!')