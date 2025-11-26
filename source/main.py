import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from rapidfuzz import fuzz
import warnings
warnings.filterwarnings("ignore")

# Настройки для поиска дубликатов
SIMILARITY_THRESHOLD = 98.5  # Порог схожести для любых полей (0-100)
MAX_WORKERS = max(1, min(32, (os.cpu_count() or 1)))
PARALLEL_CHUNK_SIZE = 150  # Количество записей в одном блоке сравнения
IGNORE_COLUMNS = ['Материал']  # Колонки, которые игнорируются при сравнении


def normalize_text(text):
    """Нормализует значение для сравнения (общая логика для любых полей)."""
    if pd.isna(text):
        return ""
    normalized = str(text).lower().strip()
    return normalized


def normalized_similarity(norm1, norm2):
    """Сравнивает уже нормализованные строки с порогом схожести."""
    if not norm1 and not norm2:
        return True
    if not norm1 or not norm2:
        return False
    if norm1 == norm2:
        return True
    similarity = fuzz.ratio(norm1, norm2)
    return similarity >= SIMILARITY_THRESHOLD


def are_values_similar(val1, val2, column_name):
    """Проверяет схожесть любых полей (не только текстовых)."""
    if pd.isna(val1) and pd.isna(val2):
        return True
    
    if pd.isna(val1) or pd.isna(val2):
        return False

    norm1 = normalize_text(val1)
    norm2 = normalize_text(val2)

    return normalized_similarity(norm1, norm2)


def load_data():
    """Загружает данные из CSV файла."""
    df = pd.read_csv('PMC MARA N13.csv', sep=';', encoding='utf-8')
    return df


def find_duplicates(df):
    """
    Находит дубликаты внутри файла MARA.
    Дубликаты - это записи с разными кодами материалов, но похожими значениями
    по всем полям (опечатки и лишние пробелы допускаются в любых колонках).
    """
    duplicates = []
    
    # Колонки для сравнения (все кроме игнорируемых)
    columns_to_compare = [col for col in df.columns if col not in IGNORE_COLUMNS]

    if not columns_to_compare:
        print("Нет колонок для сравнения после применения IGNORE_COLUMNS.")
        return duplicates

    print(f"Начинаем поиск дубликатов среди {len(df)} записей...")
    print(f"  Шаг 1: Предобработка и параллельные сравнения ({len(columns_to_compare)} колонок)...")

    indices = df.index.tolist()
    total = len(indices)

    if total <= 1:
        return duplicates

    # Предобрабатываем нормализованные значения, чтобы не пересчитывать их в потоках
    normalized_rows = {}
    for idx in indices:
        row = df.loc[idx]
        normalized_rows[idx] = {col: normalize_text(row[col]) for col in columns_to_compare}
        normalized_rows[idx]['Материал'] = normalize_text(row.get('Материал', ''))

    # Структуры для объединения похожих записей
    parent = {idx: idx for idx in indices}

    def find(idx):
        while parent[idx] != idx:
            parent[idx] = parent[parent[idx]]
            idx = parent[idx]
        return idx

    def union(idx_a, idx_b):
        root_a = find(idx_a)
        root_b = find(idx_b)
        if root_a == root_b:
            return
        parent[root_b] = root_a

    def rows_are_similar(idx_a, idx_b):
        norm_a = normalized_rows[idx_a]
        norm_b = normalized_rows[idx_b]

        material_a = norm_a.get('Материал', '')
        material_b = norm_b.get('Материал', '')
        if material_a == material_b:
            return False

        for col in columns_to_compare:
            if not normalized_similarity(norm_a[col], norm_b[col]):
                return False
        return True

    def process_chunk(start_idx, end_idx):
        chunk_pairs = []
        chunk_comparisons = 0
        for pos in range(start_idx, end_idx):
            idx_a = indices[pos]
            for pos_b in range(pos + 1, total):
                idx_b = indices[pos_b]
                chunk_comparisons += 1
                if rows_are_similar(idx_a, idx_b):
                    chunk_pairs.append((idx_a, idx_b))
        return chunk_pairs, chunk_comparisons

    chunks = [
        (start, min(start + PARALLEL_CHUNK_SIZE, total))
        for start in range(0, total, PARALLEL_CHUNK_SIZE)
    ]

    similar_pairs = []
    comparisons = 0
    processed = 0
    max_workers = min(MAX_WORKERS, len(chunks))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_chunk = {
            executor.submit(process_chunk, start, end): (start, end)
            for start, end in chunks
        }
        for future in as_completed(future_to_chunk):
            chunk_pairs, chunk_comparisons = future.result()
            similar_pairs.extend(chunk_pairs)
            comparisons += chunk_comparisons
            start, end = future_to_chunk[future]
            processed += end - start
            print(f"    Обработано записей: {processed} / {total}")

    for idx_a, idx_b in similar_pairs:
        union(idx_a, idx_b)

    print(f"  Шаг 2: Формирование групп на основе {comparisons} сравнений...")

    groups = {}
    for idx in indices:
        root = find(idx)
        groups.setdefault(root, []).append(idx)

    for group_indices in groups.values():
        if len(group_indices) <= 1:
            continue
        group_info = []
        for idx in group_indices:
            row = df.loc[idx]
            material = str(row.get('Материал', ''))
            description = row.get('Краткий текст материала', row.get('Длинный текст материала', ''))
            group_info.append((material, description, row.to_dict()))
        duplicates.append(group_info)

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
        f.write("  - Все поля (кроме игнорируемых) совпадают дословно или схожи по метрике RapidFuzz\n")
        f.write("  - Порог сходства для любого поля: {0}% и более \n\n".format(SIMILARITY_THRESHOLD))
        f.write("=" * 80 + "\n\n")

        for i, group in enumerate(duplicates, 1):
            f.write(f"Группа дубликатов #{i} ({len(group)} записей):\n")
            f.write("-" * 80 + "\n")
            
            # Показываем все записи в группе с их отличиями
            for j, (material, description, full_row) in enumerate(group, 1):
                f.write(f"  [{j}] Материал: {material}\n")
                f.write(f"      Краткий текст: {full_row.get('Краткий текст материала', 'N/A')}\n")
                f.write(f"      Длинный текст: {full_row.get('Длинный текст материала', 'N/A')}\n")
                f.write(f"      Поля записи:\n")
                for key, value in full_row.items():
                    f.write(f"        {key}: {value}\n")
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
                
                other_columns = [
                    key for key in group[0][2].keys()
                    if key not in IGNORE_COLUMNS and key not in ['Краткий текст материала', 'Длинный текст материала']
                ]
                other_diffs_found = False
                for col in other_columns:
                    base_val = group[0][2].get(col, '')
                    base_norm = normalize_text(base_val)
                    for j in range(1, len(group)):
                        curr_val = group[j][2].get(col, '')
                        curr_norm = normalize_text(curr_val)
                        if not base_norm and not curr_norm:
                            continue
                        if base_norm == curr_norm:
                            continue
                        other_diffs_found = True
                        similarity = fuzz.ratio(base_norm, curr_norm)
                        f.write(
                            f"    {col}: [1]={base_val} ↔ [{j+1}]={curr_val} ({similarity}%)\n"
                        )
                if other_diffs_found:
                    f.write("\n")
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
    print("Загрузка данных из файла...")
    df = load_data()
    print(f"Загружено записей: {len(df)}")
    print(f"Колонки: {', '.join(df.columns.tolist())}\n")
    
    duplicates = find_duplicates(df)
    
    print(f"\nНайдено групп дубликатов: {len(duplicates)}")
    
    save_report(duplicates)
