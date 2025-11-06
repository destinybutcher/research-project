"""Добавление skill points сотрудников в shiftDetails CSV файл с вариациями."""

from __future__ import annotations

import random
import pandas as pd
from pathlib import Path

from scheduler.domain.db import get_session
from scheduler.domain.repositories import EmployeeRepository


def clamp_value(value: float, min_val: int = 20, max_val: int = 100) -> int:
    """
    Ограничивает значение в диапазоне [min_val, max_val] и округляет до целого.
    
    Args:
        value: Исходное значение
        min_val: Минимальное значение (по умолчанию 20)
        max_val: Максимальное значение (по умолчанию 100)
    
    Returns:
        Целое число в диапазоне [min_val, max_val]
    """
    return int(max(min_val, min(max_val, round(value))))


def calculate_skill_variation(base_value: float) -> int:
    """
    Вычисляет изменение для skill point, пропорциональное базовому значению.
    Изменения могут быть как положительными, так и отрицательными, но логичными.
    
    Для низких значений (20-40) чаще делаем положительные изменения,
    чтобы избежать большого количества значений = 20.
    
    Args:
        base_value: Базовое значение
    
    Returns:
        Изменение (может быть отрицательным)
    """
    # Для низких значений увеличиваем вероятность улучшения
    if base_value <= 40:
        # Для низких значений: 70% шанс улучшения, 30% ухудшения
        is_improvement = random.random() < 0.7
    elif base_value <= 60:
        # Для средних значений: 50/50
        is_improvement = random.random() < 0.5
    else:
        # Для высоких значений: 30% улучшения, 70% ухудшения (но не сильно)
        is_improvement = random.random() < 0.3
    
    # Определяем тип изменения (30% значительное, 70% обычное)
    is_significant = random.random() < 0.3
    
    # Вычисляем максимально возможное изменение, чтобы не упасть ниже 20
    max_negative_change = base_value - 20  # Максимум, сколько можно вычесть
    
    if is_significant:
        # Значительное изменение
        if is_improvement:
            # Положительное изменение: от 15 до 30
            change = random.randint(15, 30)
        else:
            # Отрицательное изменение: от 10 до 70% от максимально возможного
            # но минимум 5, максимум 25
            if max_negative_change <= 5:
                change = 0  # Не трогаем, если слишком мало места
            else:
                max_change = max(5, min(25, int(max_negative_change * 0.7)))
                change = -random.randint(5, max_change)
    else:
        # Обычное изменение
        if is_improvement:
            # Положительное изменение: от 5 до 15
            change = random.randint(5, 15)
        else:
            # Отрицательное изменение: от 3 до 50% от максимально возможного
            # но минимум 3, максимум 12
            if max_negative_change <= 3:
                change = 0  # Не трогаем, если слишком мало места
            else:
                max_change = max(3, min(12, int(max_negative_change * 0.5)))
                change = -random.randint(3, max_change)
    
    return change


def add_skills_to_shiftdetails(
    shiftdetails_csv: str = "data/shiftDetails_full_12w_v2.csv",
    employees_csv: str = "data/employees_new_12w_v2.csv",
    db_url: str = "sqlite:///scheduler_full.db",
    output_csv: str | None = None,
    seed: int | None = None,
):
    """
    Добавляет skill points сотрудников в shiftDetails CSV файл с вариациями.
    
    Для каждого сотрудника определяется один раз набор изменений (положительных или 
    отрицательных) для каждого навыка, затем эти изменения применяются ко всем его сменам.
    Значения будут в диапазоне 20-100 (целые числа).
    
    Args:
        shiftdetails_csv: Путь к CSV файлу shiftDetails
        employees_csv: Путь к CSV файлу со сотрудниками (для базовых значений)
        db_url: URL базы данных со сотрудниками (альтернативный источник)
        output_csv: Путь для сохранения результата (если None, перезапишет исходный файл)
        seed: Seed для random (для воспроизводимости результатов)
    """
    if seed is not None:
        random.seed(seed)
        print(f"Установлен random seed: {seed}")
    
    print("=" * 60)
    print("ДОБАВЛЕНИЕ SKILL POINTS В SHIFTDETAILS (С ВАРИАЦИЯМИ)")
    print("=" * 60)
    
    # Читаем shiftDetails CSV
    print(f"\n[1/6] Чтение shiftDetails CSV: {shiftdetails_csv}...")
    df = pd.read_csv(shiftdetails_csv)
    print(f"Найдено {len(df)} записей")
    
    # Читаем базовые значения из CSV или базы данных
    print(f"\n[2/6] Загрузка базовых skill points...")
    
    # Пробуем сначала из CSV файла
    base_skills_dict = {}
    
    try:
        employees_df = pd.read_csv(employees_csv)
        employees_df.columns = employees_df.columns.str.lower().str.strip()
        
        for _, row in employees_df.iterrows():
            emp_id = int(row['employee_id'])
            role = str(row['primary_role']).upper()
            
            # В CSV файле колонки называются: coffee_rating, sandwich_rating, customer_service_rating, speed_rating
            # Проверяем каждое значение более тщательно
            def safe_float(value, col_name):
                if pd.isna(value):
                    return None
                try:
                    val_str = str(value).strip()
                    if val_str == '' or val_str.lower() == 'nan':
                        return None
                    return float(val_str)
                except (ValueError, TypeError):
                    return None
            
            coffee_val = safe_float(row.get('coffee_rating'), 'coffee_rating')
            sandwich_val = safe_float(row.get('sandwich_rating'), 'sandwich_rating')
            service_val = safe_float(row.get('customer_service_rating'), 'customer_service_rating')
            speed_val = safe_float(row.get('speed_rating'), 'speed_rating')
            
            base_skills_dict[emp_id] = {
                'role': role,
                'coffee_rating': coffee_val,
                'sandwich_rating': sandwich_val,
                'customer_service_rating': service_val,
                'speed_rating': speed_val,
            }
            
            # Отладочная информация для первых нескольких сотрудников
            if emp_id <= 1006:
                print(f"  Сотрудник {emp_id} ({role}): coffee={coffee_val}, sandwich={sandwich_val}, service={service_val}, speed={speed_val}")
        
        print(f"  Загружено {len(base_skills_dict)} сотрудников из CSV")
        
    except Exception as e:
        print(f"  ⚠  Не удалось загрузить из CSV: {e}")
        print(f"  Пробуем загрузить из базы данных...")
        
        # Если не получилось из CSV, пробуем из базы данных
        session = get_session(db_url)
        try:
            employees = EmployeeRepository.get_all(session)
            for emp in employees:
                base_skills_dict[emp.employee_id] = {
                    'role': emp.primary_role,
                    'coffee_rating': emp.skill_coffee,
                    'sandwich_rating': emp.skill_sandwich,
                    'customer_service_rating': emp.customer_service_rating,
                    'speed_rating': emp.skill_speed,
                }
            print(f"  Загружено {len(base_skills_dict)} сотрудников из базы данных")
        finally:
            session.close()
    
    # Для каждого сотрудника определяем фиксированные изменения один раз
    print(f"\n[3/6] Определение изменений для каждого сотрудника...")
    
    employee_variations = {}  # Словарь: emp_id -> финальные значения навыков
    
    for emp_id, base_skills in base_skills_dict.items():
        role = base_skills['role']
        variations = {}
        
        if role == "MANAGER":
            # Менеджеры - без skill points
            variations = {
                'coffee_rating': '',
                'sandwich_rating': '',
                'customer_service_rating': '',
                'speed_rating': '',
            }
            
        elif role == "SANDWICH":
            # Sandwich makers - только sandwich_rating
            base_sandwich = base_skills['sandwich_rating']
            if base_sandwich is not None:
                change = calculate_skill_variation(base_sandwich)
                final_value = clamp_value(base_sandwich + change)
                variations['sandwich_rating'] = final_value
                print(f"  Сотрудник {emp_id} (SANDWICH): sandwich {base_sandwich} -> {final_value} (изменение: {change:+d})")
            else:
                variations['sandwich_rating'] = ''
            
            variations['coffee_rating'] = ''
            variations['customer_service_rating'] = ''
            variations['speed_rating'] = ''
            
        elif role in ["BARISTA", "WAITER"]:
            # Baristas и Waiters - coffee, customer_service, speed
            for skill_name, base_value in [
                ('coffee_rating', base_skills['coffee_rating']),
                ('customer_service_rating', base_skills['customer_service_rating']),
                ('speed_rating', base_skills['speed_rating']),
            ]:
                if base_value is not None:
                    change = calculate_skill_variation(base_value)
                    final_value = clamp_value(base_value + change)
                    variations[skill_name] = final_value
                    print(f"  Сотрудник {emp_id} ({role}): {skill_name} {base_value} -> {final_value} (изменение: {change:+d})")
                else:
                    variations[skill_name] = ''
            
            variations['sandwich_rating'] = ''
            
        else:
            # Для других ролей применяем все доступные навыки
            for skill_name, base_value in [
                ('coffee_rating', base_skills['coffee_rating']),
                ('sandwich_rating', base_skills['sandwich_rating']),
                ('customer_service_rating', base_skills['customer_service_rating']),
                ('speed_rating', base_skills['speed_rating']),
            ]:
                if base_value is not None:
                    change = calculate_skill_variation(base_value)
                    final_value = clamp_value(base_value + change)
                    variations[skill_name] = final_value
                else:
                    variations[skill_name] = ''
        
        employee_variations[emp_id] = variations
        
        # Отладочная информация для первых нескольких сотрудников
        if emp_id <= 1006:
            print(f"  Финальные значения для {emp_id} ({role}): {variations}")
    
    # Применяем фиксированные значения ко всем сменам сотрудников
    print(f"\n[4/6] Применение значений ко всем сменам...")
    
    updated_count = 0
    not_found_count = 0
    
    # Проверяем первые несколько применений для отладки
    debug_count = 0
    
    for idx, row in df.iterrows():
        emp_id = int(row['emp_id'])
        
        if emp_id in employee_variations:
            variations = employee_variations[emp_id]
            
            # Присваиваем значения
            df.at[idx, 'coffee_rating'] = variations['coffee_rating']
            df.at[idx, 'sandwich_rating'] = variations['sandwich_rating']
            df.at[idx, 'customer_service_rating'] = variations['customer_service_rating']
            df.at[idx, 'speed_rating'] = variations['speed_rating']
            
            # Отладочная информация для первых 3 применений
            if debug_count < 3:
                print(f"  Применено для {emp_id} (idx={idx}): coffee={variations['coffee_rating']}, sandwich={variations['sandwich_rating']}, service={variations['customer_service_rating']}, speed={variations['speed_rating']}")
                debug_count += 1
            
            updated_count += 1
        else:
            if not_found_count < 5:  # Показываем только первые 5
                print(f"⚠  Сотрудник {emp_id} не найден")
            not_found_count += 1
    
    # Сохраняем обновленный файл
    print(f"\n[5/6] Сохранение результата...")
    
    if output_csv is None:
        output_csv = shiftdetails_csv
    
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Убеждаемся, что числовые значения сохраняются как числа (или пустые строки)
    # Конвертируем колонки с рейтингами: числа -> int, пустые строки -> пустые строки
    for col in ['coffee_rating', 'sandwich_rating', 'customer_service_rating', 'speed_rating']:
        def convert_value(x):
            if pd.isna(x) or x == '' or x is None:
                return ''
            try:
                if isinstance(x, str) and x.strip() == '':
                    return ''
                # Пробуем преобразовать в число
                num_val = float(x)
                if pd.isna(num_val):
                    return ''
                return int(num_val)
            except (ValueError, TypeError):
                return ''
        
        df[col] = df[col].apply(convert_value)
    
    # Сохраняем с явным указанием формата для пустых значений
    # Используем na_rep='' чтобы пустые значения сохранялись как пустые строки
    df.to_csv(output_csv, index=False, na_rep='')
    
    # Статистика
    print(f"\n[6/6] Статистика...")
    
    print(f"\n{'=' * 60}")
    print(f"ИТОГО:")
    print(f"  ✓ Обновлено записей: {updated_count}")
    if not_found_count > 0:
        print(f"  ⚠  Не найдено сотрудников: {not_found_count}")
    print(f"  💾 Сохранено в: {output_csv}")
    print(f"{'=' * 60}")
    
    # Показываем пример обновленных данных
    print(f"\n📋 Пример обновленных данных (первые 5 строк):")
    print("-" * 60)
    print(df.head().to_string(index=False))
    
    # Показываем статистику по значениям
    print(f"\n📊 Статистика по skill points:")
    print("-" * 60)
    for skill_col in ['coffee_rating', 'sandwich_rating', 'customer_service_rating', 'speed_rating']:
        skill_values = df[skill_col].replace('', pd.NA).dropna()
        if len(skill_values) > 0:
            skill_values = pd.to_numeric(skill_values, errors='coerce').dropna()
            if len(skill_values) > 0:
                print(f"  {skill_col}:")
                print(f"    Минимум: {skill_values.min()}, Максимум: {skill_values.max()}")
                print(f"    Среднее: {skill_values.mean():.1f}, Медиана: {skill_values.median():.1f}")
                print(f"    Значений = 20: {(skill_values == 20).sum()} ({(skill_values == 20).sum() / len(skill_values) * 100:.1f}%)")
    
    print(f"\n{'=' * 60}")
    print("ГОТОВО! Skill points успешно добавлены с вариациями.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    import sys
    
    # Можно передать аргументы через командную строку
    shiftdetails_file = sys.argv[1] if len(sys.argv) > 1 else "data/shiftDetails_full_12w_v2.csv"
    employees_file = sys.argv[2] if len(sys.argv) > 2 else "data/employees_new_12w_v2.csv"
    db_file = sys.argv[3] if len(sys.argv) > 3 else "sqlite:///scheduler_full.db"
    output_file = sys.argv[4] if len(sys.argv) > 4 else None
    seed_value = int(sys.argv[5]) if len(sys.argv) > 5 else None
    
    add_skills_to_shiftdetails(
        shiftdetails_csv=shiftdetails_file,
        employees_csv=employees_file,
        db_url=db_file,
        output_csv=output_file,
        seed=seed_value
    )
