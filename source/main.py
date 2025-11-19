import pandas as pd
from rapidfuzz import fuzz
import warnings
warnings.filterwarnings("ignore")

# Настройки для поиска дубликатов
SIMILARITY_THRESHOLD = 90  # Порог схожести для текстовых полей (0-100)
IGNORE_COLUMNS = ['Материал']  # Колонки, которые игнорируются при сравнении


def normalize_text(text):
    """Нормализует текст для сравнения."""
    if pd.isna(text):
        return ""
    return str(text).lower().strip()


def are_values_similar(val1, val2, column_name):
    """
    Проверяет, являются ли два значения похожими.
    Для текстовых полей использует нечёткое сравнение.
    Для остальных - точное сравнение.
    """
    # Если оба значения пустые (NaN), считаем их одинаковыми
    if pd.isna(val1) and pd.isna(val2):
        return True
    
    # Если одно пустое, а другое нет - не похожи
    if pd.isna(val1) or pd.isna(val2):
        return False
    
    # Преобразуем в строки
    str1 = str(val1)
    str2 = str(val2)
    
    # Для текстовых колонок (обычно содержащих описания)
    text_columns = ['Краткий текст материала', 'Длинный текст материала']
    
    if column_name in text_columns:
        # Нечёткое сравнение с нормализацией
        norm1 = normalize_text(str1)
        norm2 = normalize_text(str2)
        
        if not norm1 or not norm2:  # Если одна из строк пустая после нормализации
            return norm1 == norm2
        
        similarity = fuzz.ratio(norm1, norm2)
        return similarity >= SIMILARITY_THRESHOLD
    else:
        # Точное сравнение для других полей
        return str1 == str2


def load_data():
    """Загружает данные из CSV файла."""
    df_mara = pd.read_csv('PMC MARA N13.csv', sep=';', encoding='utf-8')
    return df_mara


def find_duplicates(df):
    """
    Находит дубликаты внутри файла MARA.
    Дубликаты - это записи с разными кодами материалов, но похожими описаниями
    (отличаются только опечатками, лишними пробелами и т.д.).
    """
    duplicates = []
    
    # Колонки для сравнения (все кроме игнорируемых)
    columns_to_compare = [col for col in df.columns if col not in IGNORE_COLUMNS]
    
    # Разделяем колонки на текстовые и нетекстовые
    text_columns = ['Краткий текст материала', 'Длинный текст материала']
    exact_columns = [col for col in columns_to_compare if col not in text_columns]
    
    total = len(df)
    print(f"Начинаем поиск дубликатов среди {total} записей...")
    print(f"  Шаг 1: Группировка по точным полям...")
    
    # Сначала группируем по нетекстовым полям (быстро)
    if exact_columns:
        grouped = df.groupby(exact_columns, dropna=False)
    else:
        # Если нет точных полей, создаём одну группу
        grouped = [(None, df)]
    
    print(f"  Шаг 2: Поиск похожих записей внутри групп...")
    
    group_count = 0
    for name, group in grouped:
        group_count += 1
        if group_count % 100 == 0:
            print(f"    Обработано групп: {group_count}")
        
        if len(group) <= 1:
            continue
        
        # Внутри каждой группы ищем записи с похожими текстовыми полями
        processed = set()
        group_indices = group.index.tolist()
        
        for i, idx_i in enumerate(group_indices):
            if idx_i in processed:
                continue
            
            similar_group = [idx_i]
            row_i = df.loc[idx_i]
            
            # Сравниваем с остальными записями в группе
            for idx_j in group_indices[i + 1:]:
                if idx_j in processed:
                    continue
                
                row_j = df.loc[idx_j]
                
                # Проверяем текстовые поля на схожесть
                is_similar = True
                for col in text_columns:
                    if col in df.columns:
                        if not are_values_similar(row_i[col], row_j[col], col):
                            is_similar = False
                            break
                
                if is_similar:
                    similar_group.append(idx_j)
                    processed.add(idx_j)
            
            # Если нашли похожие записи (дубликаты)
            if len(similar_group) > 1:
                group_info = []
                for idx in similar_group:
                    row = df.loc[idx]
                    material = str(row['Материал'])
                    description = row.get('Краткий текст материала', row.get('Длинный текст материала', ''))
                    row_dict = row.to_dict()
                    group_info.append((material, description, row_dict))
                
                duplicates.append(group_info)
                processed.add(idx_i)
    
    print(f"    Обработано групп: {group_count}")
    return duplicates


def save_report(duplicates, filename='duplicates_report.txt'):
    """Сохраняет отчёт о найденных дубликатах."""
    total_duplicates = sum(len(group) - 1 for group in duplicates)
    total_groups = len(duplicates)

    with open(filename, 'w', encoding='utf-8') as f:
        f.write("ОТЧЁТ ПО ДУБЛИКАТАМ В ФАЙЛЕ MARA\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Порог схожести текстовых полей: {SIMILARITY_THRESHOLD}%\n")
        f.write(f"Всего найдено групп дубликатов: {total_groups}\n")
        f.write(f"Общее количество дублирующихся записей: {total_duplicates}\n\n")
        f.write("Логика поиска: записи считаются дубликатами, если:\n")
        f.write("  - Имеют разные коды материалов\n")
        f.write("  - Все остальные поля идентичны или лексографически близки\n")
        f.write("  - Текстовые поля похожи на {0}% и более (опечатки, лишние пробелы)\n\n".format(SIMILARITY_THRESHOLD))
        f.write("=" * 80 + "\n\n")

        for i, group in enumerate(duplicates, 1):
            f.write(f"Группа дубликатов #{i} ({len(group)} записей):\n")
            f.write("-" * 80 + "\n")
            
            # Показываем все записи в группе с их отличиями
            for j, (material, description, full_row) in enumerate(group, 1):
                f.write(f"  [{j}] Материал: {material}\n")
                f.write(f"      Краткий текст: {full_row.get('Краткий текст материала', 'N/A')}\n")
                f.write(f"      Длинный текст: {full_row.get('Длинный текст материала', 'N/A')}\n")
                f.write("\n")
            
            # Показываем сходство между первой и остальными записями
            if len(group) > 1:
                f.write(f"  Сходство текстов:\n")
                first_short = normalize_text(group[0][2].get('Краткий текст материала', ''))
                first_long = normalize_text(group[0][2].get('Длинный текст материала', ''))
                
                for j in range(1, len(group)):
                    curr_short = normalize_text(group[j][2].get('Краткий текст материала', ''))
                    curr_long = normalize_text(group[j][2].get('Длинный текст материала', ''))
                    
                    if first_short and curr_short:
                        sim_short = fuzz.ratio(first_short, curr_short)
                        f.write(f"    [1] ↔ [{j+1}] Краткий текст: {sim_short}%\n")
                    
                    if first_long and curr_long:
                        sim_long = fuzz.ratio(first_long, curr_long)
                        f.write(f"    [1] ↔ [{j+1}] Длинный текст: {sim_long}%\n")
                f.write("\n")
            
            # Выводим общие поля (без текстовых, т.к. они могут отличаться)
            f.write(f"  Общие поля для группы:\n")
            first_record = group[0][2]
            for key, value in first_record.items():
                if key not in IGNORE_COLUMNS and key not in ['Краткий текст материала', 'Длинный текст материала']:
                    f.write(f"    {key}: {value}\n")
            
            f.write("\n" + "=" * 80 + "\n\n")

    print(f"\nОтчёт сохранён в файл: {filename}")
    print(f"Найдено групп дубликатов: {total_groups}")
    print(f"Всего дублирующихся записей (кандидаты на удаление): {total_duplicates}")


if __name__ == "__main__":
    print("Загрузка данных из файла MARA...")
    df_mara = load_data()
    print(f"Загружено записей: {len(df_mara)}")
    print(f"Колонки: {', '.join(df_mara.columns.tolist())}\n")
    
    duplicates = find_duplicates(df_mara)
    
    print(f"\nНайдено групп дубликатов: {len(duplicates)}")
    
    save_report(duplicates)
