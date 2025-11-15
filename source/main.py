import pandas as pd
import warnings
warnings.filterwarnings("ignore")


def load_data():
    """Загружает данные из CSV файла."""
    df = pd.read_csv('PMC MARA N13.csv', sep=';', encoding='utf-8')
    return df


def find_duplicates(df):
    """
    Находит дубликаты где все поля идентичны, кроме поля 'Материал'.
    Поле 'Материал' должно быть уникальным у каждой записи.
    """
    duplicates = []
    
    # Получаем список всех колонок кроме 'Материал'
    columns_to_compare = [col for col in df.columns if col != 'Материал']
    
    # Группируем по всем колонкам кроме 'Материал'
    grouped = df.groupby(columns_to_compare, dropna=False)
    
    # Находим группы с более чем одной записью
    for name, group in grouped:
        if len(group) > 1:
            # Собираем информацию о дубликатах в группе
            group_info = []
            for idx, row in group.iterrows():
                material = row['Материал']
                # Берем краткий или длинный текст для отображения
                description = row.get('Краткий текст материала', row.get('Длинный текст материала', ''))
                group_info.append((material, description, row.to_dict()))
            
            duplicates.append(group_info)
    
    return duplicates


def save_report(duplicates, filename='duplicates_report.txt'):
    """Сохраняет отчёт о найденных дубликатах."""
    total_duplicates = sum(len(group) - 1 for group in duplicates)
    total_groups = len(duplicates)

    with open(filename, 'w', encoding='utf-8') as f:
        f.write("ОТЧЁТ ПО ДУБЛИКАТАМ\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Всего найдено групп дубликатов: {total_groups}\n")
        f.write(f"Общее количество лишних (повторяющихся) записей: {total_duplicates}\n\n")
        f.write("Логика поиска: записи считаются дубликатами, если все их поля идентичны,\n")
        f.write("кроме поля 'Материал' (которое уникально для каждой записи).\n\n")
        f.write("=" * 80 + "\n\n")

        for i, group in enumerate(duplicates, 1):
            f.write(f"Группа дубликатов #{i} ({len(group)} записей):\n")
            f.write("-" * 80 + "\n")
            
            for material, description, full_row in group:
                f.write(f"  Материал: {material}\n")
                f.write(f"  Описание: {description}\n")
                
                # Выводим все поля для первой записи в группе
                if group.index((material, description, full_row)) == 0:
                    f.write(f"\n  Общие поля для всех записей в группе:\n")
                    for key, value in full_row.items():
                        if key != 'Материал':
                            f.write(f"    {key}: {value}\n")
                
                f.write("\n")
            
            f.write("=" * 80 + "\n\n")

    print(f"\nОтчёт сохранён в файл: {filename}")
    print(f"Найдено групп дубликатов: {total_groups}")
    print(f"Подлежит удалению (дублирующихся записей): {total_duplicates}")


if __name__ == "__main__":
    print("Загрузка данных из CSV файла...")
    df = load_data()
    print(f"Загружено записей: {len(df)}")
    print(f"Колонки в файле: {', '.join(df.columns.tolist())}\n")
    
    print("Поиск дубликатов...")
    duplicates = find_duplicates(df)
    
    print(f"\nНайдено групп дубликатов: {len(duplicates)}")
    
    save_report(duplicates)
