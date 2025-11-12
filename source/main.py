import pandas as pd
import re
from rapidfuzz import fuzz
import warnings
warnings.filterwarnings("ignore")

def normalize_name(name):
    """Нормализует наименование для сравнения."""
    if pd.isna(name):
        return ""
    name = str(name).lower().strip()
    
    name = re.sub(r'[^\w\s\d]', ' ', name)
    name = re.sub(r'\s+', ' ', name)
   
    name = name.replace('труба', 'тр').replace('трубы', 'тр')
    name = name.replace('обсадная', 'обс').replace('бурильная', 'бур')
    name = name.replace('лдп', 'лдп').replace('нкт', 'нкт')
    name = name.replace('tmk up', 'tmkup')
    name = name.replace('длина', 'l').replace('дл', 'l')
    name = re.sub(r'[øØ]', 'd', name)  
    name = re.sub(r'(\d+)\s*[xх]\s*(\d+)', r'\1*\2', name)  
    name = re.sub(r'(\d+)\s*,\s*(\d+)', r'\1.\2', name)  
    return name

def load_and_combine():

    df_mara = pd.read_excel('PMC MARA N13.xlsx', sheet_name=0, usecols=['Материал', 'Длинный текст материала'])
    df_mara = df_mara.rename(columns={'Материал': 'Код', 'Длинный текст материала': 'Наименование'})
    df_mara['Источник'] = 'MARA'


    df_class = pd.read_excel('PMC классификация N13.xlsx', sheet_name=0, usecols=['Материал', 'Материал(полный текст)'])
    df_class = df_class.rename(columns={'Материал': 'Код', 'Материал(полный текст)': 'Наименование'})
    df_class['Источник'] = 'Классификация'


    df = pd.concat([df_mara, df_class], ignore_index=True)
    df['Наименование_norm'] = df['Наименование'].apply(normalize_name)
    return df

def find_duplicates(df):
    duplicates = []
    seen = set()
    names = df['Наименование_norm'].tolist()
    codes = df['Код'].tolist()
    original_names = df['Наименование'].tolist()

    n = len(names)
    for i in range(n):
        if codes[i] in seen:
            continue
        group = [i]
        for j in range(i + 1, n):
            if codes[j] in seen:
                continue
            ratio = fuzz.ratio(names[i], names[j])
            if ratio >= 85:  
                group.append(j)
                seen.add(codes[j])
        if len(group) > 1:
            duplicates.append([(codes[idx], original_names[idx]) for idx in group])
            seen.add(codes[i])
    return duplicates

def save_report(duplicates, filename='duplicates_report.txt'):
    total_duplicates = sum(len(group) - 1 for group in duplicates)
    total_groups = len(duplicates)

    with open(filename, 'w', encoding='utf-8') as f:
        f.write("ОТЧЁТ ПО ДУБЛИКАТАМ\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Всего найдено групп дубликатов: {total_groups}\n")
        f.write(f"Общее количество лишних (повторяющихся) записей: {total_duplicates}\n\n")

        for i, group in enumerate(duplicates, 1):
            f.write(f"Группа {i}:\n")
            for code, name in group:
                f.write(f"  • {code}: {name}\n")
            f.write("\n")

    print(f"Отчёт сохранён в файл: {filename}")
    print(f"Найдено групп дубликатов: {total_groups}")
    print(f"Подлежит удалению (дублирующихся записей): {total_duplicates}")


if __name__ == "__main__":
    df = load_and_combine()
    duplicates = find_duplicates(df)
    save_report(duplicates)
