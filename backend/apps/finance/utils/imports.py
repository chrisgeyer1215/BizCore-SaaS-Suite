"""
Finance Imports Utilities
Data import utilities
"""

import csv
from typing import List, Dict
from django.core.exceptions import ValidationError


class CSVImporter:
    """CSV import utilities"""
    
    @staticmethod
    def parse_csv_file(file_path: str, delimiter: str = ',') -> List[Dict]:
        """Parse CSV file and return list of dictionaries"""
        data = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file, delimiter=delimiter)
                for row in reader:
                    cleaned_row = {k: v.strip() if v else '' for k, v in row.items()}
                    data.append(cleaned_row)
        except Exception as e:
            raise ValidationError(f'Error reading CSV file: {str(e)}')
        
        return data
    
    @staticmethod
    def validate_csv_data(data: List[Dict], required_fields: List[str]) -> List[str]:
        """Validate CSV data and return list of errors"""
        errors = []
        
        if not data:
            errors.append('CSV file is empty')
            return errors
        
        # Check required fields
        if data:
            first_row = data[0]
            missing_fields = [field for field in required_fields if field not in first_row]
            if missing_fields:
                errors.append(f'Missing required fields: {", ".join(missing_fields)}')
        
        return errors


class DataValidator:
    """Data validation utilities"""
    
    @staticmethod
    def validate_decimal(value: str, field_name: str = 'amount'):
        """Validate and convert string to Decimal"""
        if not value:
            return None
        
        try:
            from decimal import Decimal
            return Decimal(str(value))
        except:
            raise ValidationError(f'{field_name} must be a valid number')
