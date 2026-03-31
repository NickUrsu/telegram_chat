# src/models.py
from decimal import Decimal

def convert_numbers_to_decimal(obj):
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: convert_numbers_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_numbers_to_decimal(v) for v in obj]
    return obj
