# crm/utils/custom_fields.py
"""
Custom Fields Utilities for CRM Module

Provides comprehensive custom field management capabilities including:
- Dynamic field creation and management
- Field type validation and serialization
- Custom field rendering and forms
- Field dependency management
- Conditional field logic
- Field migration and versioning
- Field permissions and security
"""

import json
import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, List, Optional, Union, Type
from dataclasses import dataclass, field
from enum import Enum

from django.db import models
from django.core.exceptions import ValidationError
from django.forms import widgets
from django import forms
from django.utils import timezone
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.contrib.contenttypes.models import ContentType
from django.apps import apps


class FieldType(Enum):
    """Supported custom field types."""
    TEXT = 'text'
    TEXTAREA = 'textarea'
    EMAIL = 'email'
    URL = 'url'
    PHONE = 'phone'
    NUMBER = 'number'
    DECIMAL = 'decimal'
    CURRENCY = 'currency'
    PERCENTAGE = 'percentage'
    DATE = 'date'
    DATETIME = 'datetime'
    TIME = 'time'
    BOOLEAN = 'boolean'
    CHOICE = 'choice'
    MULTIPLE_CHOICE = 'multiple_choice'
    FILE = 'file'
    IMAGE = 'image'
    JSON = 'json'
    REFERENCE = 'reference'  # Reference to another model


@dataclass
class FieldConfiguration:
    """Configuration for a custom field."""
    field_type: FieldType
    label: str
    description: str = ""
    required: bool = False
    default_value: Any = None
    max_length: Optional[int] = None
    min_value: Optional[Union[int, float, Decimal]] = None
    max_value: Optional[Union[int, float, Decimal]] = None
    decimal_places: Optional[int] = None
    choices: Optional[List[Dict[str, str]]] = None
    regex_pattern: Optional[str] = None
    regex_message: Optional[str] = None
    help_text: str = ""
    placeholder: str = ""
    css_classes: str = ""
    widget_attrs: Dict[str, Any] = field(default_factory=dict)
    validation_rules: Dict[str, Any] = field(default_factory=dict)
    conditional_logic: Dict[str, Any] = field(default_factory=dict)
    permissions: Dict[str, List[str]] = field(default_factory=dict)
    reference_model: Optional[str] = None
    reference_field: Optional[str] = None


@dataclass
class FieldValue:
    """Represents a custom field value."""
    field_name: str
    field_type: FieldType
    raw_value: Any
    display_value: str
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)


class CustomFieldManager:
    """
    Comprehensive custom field management system.
    """
    
    def __init__(self, tenant=None):
        self.tenant = tenant
        self.field_registry = {}
        self._load_field_definitions()
    
    def create_custom_field(self, model_name: str, field_name: str, 
                          config: FieldConfiguration) -> Dict[str, Any]:
        """
        Create a new custom field for a model.
        
        Args:
            model_name: Target model name
            field_name: Field name (must be unique per model)
            config: Field configuration
        
        Returns:
            Dict with creation result
        """
        try:
            # Validate field name
            if not self._is_valid_field_name(field_name):
                return {
                    'success': False,
                    'error': 'Invalid field name. Use only letters, numbers, and underscores.'
                }
            
            # Check if field already exists
            if self._field_exists(model_name, field_name):
                return {
                    'success': False,
                    'error': f'Field "{field_name}" already exists for model "{model_name}"'
                }
            
            # Validate configuration
            validation_result = self._validate_field_config(config)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': 'Invalid field configuration',
                    'validation_errors': validation_result['errors']
                }
            
            # Create field definition in database
            field_definition = self._create_field_definition(model_name, field_name, config)
            
            # Update field registry
            self._register_field(model_name, field_name, config)
            
            # Create database migration if needed
            if config.field_type not in [FieldType.JSON]:
                self._create_field_migration(model_name, field_name, config)
            
            return {
                'success': True,
                'field_id': field_definition.id if hasattr(field_definition, 'id') else None,
                'message': f'Custom field "{field_name}" created successfully'
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to create custom field: {str(e)}'
            }
    
    def update_custom_field(self, model_name: str, field_name: str, 
                          config: FieldConfiguration) -> Dict[str, Any]:
        """
        Update an existing custom field.
        
        Args:
            model_name: Target model name
            field_name: Field name to update
            config: New field configuration
        
        Returns:
            Dict with update result
        """
        try:
            if not self._field_exists(model_name, field_name):
                return {
                    'success': False,
                    'error': f'Field "{field_name}" does not exist for model "{model_name}"'
                }
            
            # Validate new configuration
            validation_result = self._validate_field_config(config)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': 'Invalid field configuration',
                    'validation_errors': validation_result['errors']
                }
            
            # Check for breaking changes
            breaking_changes = self._check_breaking_changes(model_name, field_name, config)
            if breaking_changes:
                return {
                    'success': False,
                    'error': 'Configuration contains breaking changes',
                    'breaking_changes': breaking_changes
                }
            
            # Update field definition
            self._update_field_definition(model_name, field_name, config)
            
            # Update registry
            self._register_field(model_name, field_name, config)
            
            return {
                'success': True,
                'message': f'Custom field "{field_name}" updated successfully'
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to update custom field: {str(e)}'
            }
    
    def delete_custom_field(self, model_name: str, field_name: str, 
                          force: bool = False) -> Dict[str, Any]:
        """
        Delete a custom field.
        
        Args:
            model_name: Target model name
            field_name: Field name to delete
            force: Force deletion even if field has data
        
        Returns:
            Dict with deletion result
        """
        try:
            if not self._field_exists(model_name, field_name):
                return {
                    'success': False,
                    'error': f'Field "{field_name}" does not exist for model "{model_name}"'
                }
            
            # Check if field has data
            if not force and self._field_has_data(model_name, field_name):
                return {
                    'success': False,
                    'error': 'Field contains data. Use force=True to delete anyway.',
                    'has_data': True
                }
            
            # Create backup of field data
            if self._field_has_data(model_name, field_name):
                self._backup_field_data(model_name, field_name)
            
            # Remove field definition
            self._delete_field_definition(model_name, field_name)
            
            # Remove from registry
            self._unregister_field(model_name, field_name)
            
            # Create migration to drop column
            self._create_drop_field_migration(model_name, field_name)
            
            return {
                'success': True,
                'message': f'Custom field "{field_name}" deleted successfully'
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to delete custom field: {str(e)}'
            }
    
    def get_custom_fields(self, model_name: str) -> List[Dict[str, Any]]:
        """
        Get all custom fields for a model.
        
        Args:
            model_name: Target model name
        
        Returns:
            List of custom field definitions
        """
        try:
            fields = []
            model_fields = self.field_registry.get(model_name, {})
            
            for field_name, config in model_fields.items():
                fields.append({
                    'name': field_name,
                    'type': config.field_type.value,
                    'label': config.label,
                    'description': config.description,
                    'required': config.required,
                    'default_value': config.default_value,
                    'configuration': config.__dict__
                })
            
            return fields
        
        except Exception as e:
            print(f"Error getting custom fields: {e}")
            return []
    
    def validate_field_value(self, model_name: str, field_name: str, 
                           value: Any) -> FieldValue:
        """
        Validate a custom field value.
        
        Args:
            model_name: Target model name
            field_name: Field name
            value: Value to validate
        
        Returns:
            FieldValue object with validation results
        """
        try:
            config = self._get_field_config(model_name, field_name)
            if not config:
                return FieldValue(
                    field_name=field_name,
                    field_type=FieldType.TEXT,
                    raw_value=value,
                    display_value=str(value) if value is not None else "",
                    is_valid=False,
                    validation_errors=[f'Field "{field_name}" not found']
                )
            
            # Validate value based on field type
            validation_result = self._validate_value_by_type(config, value)
            
            # Apply additional validation rules
            if validation_result['is_valid'] and config.validation_rules:
                validation_result = self._apply_validation_rules(
                    config, value, validation_result
                )
            
            # Format display value
            display_value = self._format_display_value(config, value)
            
            return FieldValue(
                field_name=field_name,
                field_type=config.field_type,
                raw_value=value,
                display_value=display_value,
                is_valid=validation_result['is_valid'],
                validation_errors=validation_result.get('errors', [])
            )
        
        except Exception as e:
            return FieldValue(
                field_name=field_name,
                field_type=FieldType.TEXT,
                raw_value=value,
                display_value=str(value) if value is not None else "",
                is_valid=False,
                validation_errors=[f'Validation error: {str(e)}']
            )
    
    def get_form_field(self, model_name: str, field_name: str) -> Optional[forms.Field]:
        """
        Get Django form field for custom field.
        
        Args:
            model_name: Target model name
            field_name: Field name
        
        Returns:
            Django form field or None
        """
        config = self._get_field_config(model_name, field_name)
        if not config:
            return None
        
        return self._create_form_field(config)
    
    def get_model_form_fields(self, model_name: str) -> Dict[str, forms.Field]:
        """
        Get all custom form fields for a model.
        
        Args:
            model_name: Target model name
        
        Returns:
            Dict of field_name -> form_field
        """
        form_fields = {}
        model_fields = self.field_registry.get(model_name, {})
        
        for field_name, config in model_fields.items():
            form_field = self._create_form_field(config)
            if form_field:
                form_fields[field_name] = form_field
        
        return form_fields
    
    def process_conditional_logic(self, model_name: str, field_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process conditional logic for custom fields.
        
        Args: field data
        
        Returns:
            Dict with field visibility and requirement updates
        """
        field_updates = {}
        model_fields = self.field_registry.get(model_name, {})
        
        for field_name, config in model_fields.items():
            if not config.conditional_logic:
                continue
            
            logic_result = self._evaluate_conditional_logic(
                config.conditional_logic, field_data
            )
            
            if logic_result:
                field_updates[field_name] = logic_result
        
        return field_updates
    
    def _load_field_definitions(self):
        """Load custom field definitions from database."""
        try:
            from crm.models.system import CustomField
            
            custom_fields = CustomField.objects.filter(
                tenant=self.tenant,
                is_active=True
            )
            
            for field_def in custom_fields:
                config = FieldConfiguration(
                    field_type=FieldType(field_def.field_type),
                    label=field_def.label,
                    description=field_def.description or "",
                    required=field_def.required,
                    default_value=field_def.default_value,
                    max_length=field_def.max_length,
                    min_value=field_def.min_value,
                    max_value=field_def.max_value,
                    decimal_places=field_def.decimal_places,
                    choices=json.loads(field_def.choices) if field_def.choices else None,
                    regex_pattern=field_def.regex_pattern,
                    regex_message=field_def.regex_message,
                    help_text=field_def.help_text or "",
                    placeholder=field_def.placeholder or "",
                    css_classes=field_def.css_classes or "",
                    widget_attrs=json.loads(field_def.widget_attrs) if field_def.widget_attrs else {},
                    validation_rules=json.loads(field_def.validation_rules) if field_def.validation_rules else {},
                    conditional_logic=json.loads(field_def.conditional_logic) if field_def.conditional_logic else {},
                    permissions=json.loads(field_def.permissions) if field_def.permissions else {},
                    reference_model=field_def.reference_model,
                    reference_field=field_def.reference_field
                )
                
                self._register_field(field_def.model_name, field_def.field_name, config)
        
        except Exception as e:
            print(f"Error loading field definitions: {e}")
    
    def _is_valid_field_name(self, field_name: str) -> bool:
        """Validate field name format."""
        if not field_name:
            return False
        
        # Check for valid identifier
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', field_name):
            return False
        
        # Check for reserved names
        reserved_names = [
            'id', 'pk', 'tenant', 'created_at', 'updated_at', 'deleted_at',
            'objects', 'DoesNotExist', 'MultipleObjectsReturned'
        ]
        
        if field_name in reserved_names:
            return False
        
        return True
    
    def _field_exists(self, model_name: str, field_name: str) -> bool:
        """Check if custom field already exists."""
        try:
            from crm.models.system import CustomField
            return CustomField.objects.filter(
                tenant=self.tenant,
                model_name=model_name,
                field_name=field_name,
                is_active=True
            ).exists()
        except:
            return False
    
    def _validate_field_config(self, config: FieldConfiguration) -> Dict[str, Any]:
        """Validate field configuration."""
        errors = []
        
        # Validate field type specific requirements
        if config.field_type == FieldType.CHOICE and not config.choices:
            errors.append("Choice field requires choices to be defined")
        
        if config.field_type == FieldType.MULTIPLE_CHOICE and not config.choices:
            errors.append("Multiple choice field requires choices to be defined")
        
        if config.field_type == FieldType.REFERENCE and not config.reference_model:
            errors.append("Reference field requires reference_model to be specified")
        
        if config.field_type in [FieldType.NUMBER, FieldType.DECIMAL, FieldType.CURRENCY]:
            if config.min_value is not None and config.max_value is not None:
                if config.min_value > config.max_value:
                    errors.append("min_value cannot be greater than max_value")
        
        if config.field_type == FieldType.TEXT and config.max_length and config.max_length > 1000:
            errors.append("Text field max_length cannot exceed 1000 characters")
        
        # Validate regex pattern
        if config.regex_pattern:
            try:
                re.compile(config.regex_pattern)
            except re.error:
                errors.append("Invalid regex pattern")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def _create_field_definition(self, model_name: str, field_name: str, 
                               config: FieldConfiguration):
        """Create field definition in database."""
        try:
            from crm.models.system import CustomField
            
            return CustomField.objects.create(
                tenant=self.tenant,
                model_name=model_name,
                field_name=field_name,
                field_type=config.field_type.value,
                label=config.label,
                description=config.description,
                required=config.required,
                default_value=config.default_value,
                max_length=config.max_length,
                min_value=config.min_value,
                max_value=config.max_value,
                decimal_places=config.decimal_places,
                choices=json.dumps(config.choices) if config.choices else None,
                regex_pattern=config.regex_pattern,
                regex_message=config.regex_message,
                help_text=config.help_text,
                placeholder=config.placeholder,
                css_classes=config.css_classes,
                widget_attrs=json.dumps(config.widget_attrs) if config.widget_attrs else None,
                validation_rules=json.dumps(config.validation_rules) if config.validation_rules else None,
                conditional_logic=json.dumps(config.conditional_logic) if config.conditional_logic else None,
                permissions=json.dumps(config.permissions) if config.permissions else None,
                reference_model=config.reference_model,
                reference_field=config.reference_field,
                is_active=True,
                created_at=timezone.now()
            )
        except Exception as e:
            print(f"Error creating field definition: {e}")
            return None
    
    def _register_field(self, model_name: str, field_name: str, config: FieldConfiguration):
        """Register field in memory registry."""
        if model_name not in self.field_registry:
            self.field_registry[model_name] = {}
        
        self.field_registry[model_name][field_name] = config
    
    def _unregister_field(self, model_name: str, field_name: str):
        """Remove field from memory registry."""
        if model_name in self.field_registry and field_name in self.field_registry[model_name]:
            del self.field_registry[model_name][field_name]
    
    def _get_field_config(self, model_name: str, field_name: str) -> Optional[FieldConfiguration]:
        """Get field configuration from registry."""
        return self.field_registry.get(model_name, {}).get(field_name)
    
    def _validate_value_by_type(self, config: FieldConfiguration, value: Any) -> Dict[str, Any]:
        """Validate value based on field type."""
        if value is None:
            if config.required:
                return {
                    'is_valid': False,
                    'errors': ['This field is required']
                }
            else:
                return {'is_valid': True}
        
        try:
            if config.field_type == FieldType.TEXT:
                if not isinstance(value, str):
                    value = str(value)
                if config.max_length and len(value) > config.max_length:
                    return {
                        'is_valid': False,
                        'errors': [f'Text cannot exceed {config.max_length} characters']
                    }
            
            elif config.field_type == FieldType.EMAIL:
                from django.core.validators import validate_email
                validate_email(value)
            
            elif config.field_type == FieldType.URL:
                from django.core.validators import URLValidator
                validator = URLValidator()
                validator(value)
            
            elif config.field_type == FieldType.PHONE:
                from crm.utils.validators import validate_phone_number
                validate_phone_number(value)
            
            elif config.field_type == FieldType.NUMBER:
                int_value = int(value)
                if config.min_value is not None and int_value < config.min_value:
                    return {
                        'is_valid': False,
                        'errors': [f'Value must be at least {config.min_value}']
                    }
                if config.max_value is not None and int_value > config.max_value:
                    return {
                        'is_valid': False,
                        'errors': [f'Value cannot exceed {config.max_value}']
                    }
            
            elif config.field_type in [FieldType.DECIMAL, FieldType.CURRENCY, FieldType.PERCENTAGE]:
                decimal_value = Decimal(str(value))
                if config.min_value is not None and decimal_value < Decimal(str(config.min_value)):
                    return {
                        'is_valid': False,
                        'errors': [f'Value must be at least {config.min_value}']
                    }
                if config.max_value is not None and decimal_value > Decimal(str(config.max_value)):
                    return {
                        'is_valid': False,
                        'errors': [f'Value cannot exceed {config.max_value}']
                    }
            
            elif config.field_type == FieldType.DATE:
                if isinstance(value, str):
                    datetime.strptime(value, '%Y-%m-%d')
            
            elif config.field_type == FieldType.DATETIME:
                if isinstance(value, str):
                    datetime.fromisoformat(value.replace('Z', '+00:00'))
            
            elif config.field_type == FieldType.BOOLEAN:
                if not isinstance(value, bool):
                    if str(value).lower() not in ['true', 'false', '1', '0', 'yes', 'no']:
                        return {
                            'is_valid': False,
                            'errors': ['Invalid boolean value']
                        }
            
            elif config.field_type == FieldType.CHOICE:
                if config.choices:
                    valid_choices = [choice['value'] for choice in config.choices]
                    if value not in valid_choices:
                        return {
                            'is_valid': False,
                            'errors': ['Invalid choice']
                        }
            
            elif config.field_type == FieldType.MULTIPLE_CHOICE:
                if config.choices:
                    valid_choices = [choice['value'] for choice in config.choices]
                    if isinstance(value, list):
                        for item in value:
                            if item not in valid_choices:
                                return {
                                    'is_valid': False,
                                    'errors': [f'Invalid choice: {item}']
                                }
                    else:
                        return {
                            'is_valid': False,
                            'errors': ['Multiple choice field requires list value']
                        }
            
            elif config.field_type == FieldType.JSON:
                if isinstance(value, str):
                    json.loads(value)  # Validate JSON format
            
            # Apply regex validation if specified
            if config.regex_pattern and isinstance(value, str):
                if not re.match(config.regex_pattern, value):
                    message = config.regex_message or f'Value does not match required pattern'
                    return {
                        'is_valid': False,
                        'errors': [message]
                    }
            
            return {'is_valid': True}
        
        except (ValueError, ValidationError, InvalidOperation) as e:
            return {
                'is_valid': False,
                'errors': [str(e)]
            }
    
    def _apply_validation_rules(self, config: FieldConfiguration, value: Any, 
                              current_result: Dict[str, Any]) -> Dict[str, Any]:
        """Apply additional validation rules."""
        if not current_result.get('is_valid', True):
            return current_result
        
        errors = []
        
        for rule_name, rule_config in config.validation_rules.items():
            if rule_name == 'custom_regex':
                pattern = rule_config.get('pattern')
                message = rule_config.get('message', 'Value does not match required format')
                if pattern and isinstance(value, str):
                    if not re.match(pattern, value):
                        errors.append(message)
            
            elif rule_name == 'unique_value':
                # Check uniqueness (would require database access)
                pass
            
            elif rule_name == 'depends_on':
                # Handle field dependencies
                pass
        
        if errors:
            return {
                'is_valid': False,
                'errors': current_result.get('errors', []) + errors
            }
        
        return current_result
    
    def _format_display_value(self, config: FieldConfiguration, value: Any) -> str:
        """Format value for display."""
        if value is None:
            return ""
        
        try:
            if config.field_type == FieldType.CURRENCY:
                from crm.utils.formatters import format_currency
                return format_currency(value)
            
            elif config.field_type == FieldType.PERCENTAGE:
                from crm.utils.formatters import format_percentage
                return format_percentage(value)
            
            elif config.field_type == FieldType.DATE:
                if isinstance(value, str):
                    value = datetime.strptime(value, '%Y-%m-%d').date()
                return value.strftime('%Y-%m-%d')
            
            elif config.field_type == FieldType.DATETIME:
                if isinstance(value, str):
                    value = datetime.fromisoformat(value.replace('Z', '+00:00'))
                return value.strftime('%Y-%m-%d %H:%M:%S')
            
            elif config.field_type == FieldType.CHOICE and config.choices:
                for choice in config.choices:
                    if choice['value'] == value:
                        return choice['label']
            
            elif config.field_type == FieldType.MULTIPLE_CHOICE and config.choices:
                if isinstance(value, list):
                    labels = []
                    for choice in config.choices:
                        if choice['value'] in value:
                            labels.append(choice['label'])
                    return ', '.join(labels)
            
            elif config.field_type == FieldType.BOOLEAN:
                return 'Yes' if value else 'No'
            
            return str(value)
        
        except Exception as e:
            return str(value)
    
    def _create_form_field(self, config: FieldConfiguration) -> Optional[forms.Field]:
        """Create Django form field based on configuration."""
        field_kwargs = {
            'label': config.label,
            'help_text': config.help_text,
            'required': config.required,
            'initial': config.default_value
        }
        
        # Add widget attributes
        if config.widget_attrs or config.placeholder or config.css_classes:
            widget_attrs = config.widget_attrs.copy()
            if config.placeholder:
                widget_attrs['placeholder'] = config.placeholder
            if config.css_classes:
                widget_attrs['class'] = config.css_classes
            
            field_kwargs['widget'] = self._get_widget_class(config)(attrs=widget_attrs)
        
        # Create field based on type
        if config.field_type == FieldType.TEXT:
            if config.max_length:
                field_kwargs['max_length'] = config.max_length
            return forms.CharField(**field_kwargs)
        
        elif config.field_type == FieldType.TEXTAREA:
            field_kwargs['widget'] = forms.Textarea(attrs=field_kwargs.get('widget', {}).attrs if hasattr(field_kwargs.get('widget', {}), 'attrs') else {})
            return forms.CharField(**field_kwargs)
        
        elif config.field_type == FieldType.EMAIL:
            return forms.EmailField(**field_kwargs)
        
        elif config.field_type == FieldType.URL:
            return forms.URLField(**field_kwargs)
        
        elif config.field_type == FieldType.PHONE:
            return forms.CharField(**field_kwargs)
        
        elif config.field_type == FieldType.NUMBER:
            if config.min_value is not None:
                field_kwargs['min_value'] = config.min_value
            if config.max_value is not None:
                field_kwargs['max_value'] = config.max_value
            return forms.IntegerField(**field_kwargs)
        
        elif config.field_type in [FieldType.DECIMAL, FieldType.CURRENCY, FieldType.PERCENTAGE]:
            if config.decimal_places is not None:
                field_kwargs['decimal_places'] = config.decimal_places
            if config.min_value is not None:
                field_kwargs['min_value'] = Decimal(str(config.min_value))
            if config.max_value is not None:
                field_kwargs['max_value'] = Decimal(str(config.max_value))
            return forms.DecimalField(**field_kwargs)
        
        elif config.field_type == FieldType.DATE:
            field_kwargs['widget'] = forms.DateInput(attrs={'type': 'date'})
            return forms.DateField(**field_kwargs)
        
        elif config.field_type == FieldType.DATETIME:
            field_kwargs['widget'] = forms.DateTimeInput(attrs={'type': 'datetime-local'})
            return forms.DateTimeField(**field_kwargs)
        
        elif config.field_type == FieldType.TIME:
            field_kwargs['widget'] = forms.TimeInput(attrs={'type': 'time'})
            return forms.TimeField(**field_kwargs)
        
        elif config.field_type == FieldType.BOOLEAN:
            return forms.BooleanField(**field_kwargs)
        
        elif config.field_type == FieldType.CHOICE and config.choices:
            choices = [(choice['value'], choice['label']) for choice in config.choices]
            field_kwargs['choices'] = choices
            return forms.ChoiceField(**field_kwargs)
        
        elif config.field_type == FieldType.MULTIPLE_CHOICE and config.choices:
            choices = [(choice['value'], choice['label']) for choice in config.choices]
            field_kwargs['choices'] = choices
            return forms.MultipleChoiceField(**field_kwargs)
        
        elif config.field_type == FieldType.FILE:
            return forms.FileField(**field_kwargs)
        
        elif config.field_type == FieldType.IMAGE:
            return forms.ImageField(**field_kwargs)
        
        elif config.field_type == FieldType.JSON:
            field_kwargs['widget'] = forms.Textarea(attrs={'rows': 5})
            return forms.CharField(**field_kwargs)
        
        elif config.field_type == FieldType.REFERENCE:
            # This would create a ModelChoiceField based on reference_model
            if config.reference_model:
                try:
                    model_class = apps.get_model(config.reference_model)
                    field_kwargs['queryset'] = model_class.objects.all()
                    return forms.ModelChoiceField(**field_kwargs)
                except:
                    pass
        
        return None
    
    def _get_widget_class(self, config: FieldConfiguration):
        """Get appropriate widget class for field type."""
        widget_mapping = {
            FieldType.TEXT: forms.TextInput,
            FieldType.TEXTAREA: forms.Textarea,
            FieldType.EMAIL: forms.EmailInput,
            FieldType.URL: forms.URLInput,
            FieldType.PHONE: forms.TextInput,
            FieldType.NUMBER: forms.NumberInput,
            FieldType.DECIMAL: forms.NumberInput,
            FieldType.CURRENCY: forms.NumberInput,
            FieldType.PERCENTAGE: forms.NumberInput,
            FieldType.DATE: forms.DateInput,
            FieldType.DATETIME: forms.DateTimeInput,
            FieldType.TIME: forms.TimeInput,
            FieldType.BOOLEAN: forms.CheckboxInput,
            FieldType.CHOICE: forms.Select,
            FieldType.MULTIPLE_CHOICE: forms.CheckboxSelectMultiple,
            FieldType.FILE: forms.FileInput,
            FieldType.IMAGE: forms.FileInput,
            FieldType.JSON: forms.Textarea
        }
        
        return widget_mapping.get(config.field_type, forms.TextInput)
    
    def _evaluate_conditional_logic(self, logic: Dict[str, Any], 
                                  fiel Optional[Dict[str, Any]]:
        """Evaluate conditional logic rules."""
        try:
            conditions = logic.get('conditions', [])
            operator = logic.get('operator', 'and')  # 'and' or 'or'
            actions = logic.get('actions', {})
            
            results = []
            
            for condition in conditions:
                field_name = condition.get('field')
                condition_type = condition.get('type')
                value = condition.get('value')
                field_value = field_data.get(field_name)
                
                if condition_type == 'equals':
                    results.append(field_value == value)
                elif condition_type == 'not_equals':
                    results.append(field_value != value)
                elif condition_type == 'contains':
                    results.append(value in str(field_value or ''))
                elif condition_type == 'is_empty':
                    results.append(not field_value)
                elif condition_type == 'is_not_empty':
                    results.append(bool(field_value))
                else:
                    results.append(False)
            
            # Evaluate conditions based on operator
            if operator == 'and':
                condition_met = all(results)
            else:  # 'or'
                condition_met = any(results)
            
            if condition_met:
                return actions
            
            return None
        
        except Exception as e:
            print(f"Error evaluating conditional logic: {e}")
            return None
    
    def _check_breaking_changes(self, model_name: str, field_name: str, 
                              new_config: FieldConfiguration) -> List[str]:
        """Check for breaking changes in field configuration."""
        current_config = self._get_field_config(model_name, field_name)
        if not current_config:
            return []
        
        breaking_changes = []
        
        # Type change is breaking
        if current_config.field_type != new_config.field_type:
            breaking_changes.append(f"Field type change from {current_config.field_type.value} to {new_config.field_type.value}")
        
        # Making field required when it wasn't is potentially breaking
        if not current_config.required and new_config.required:
            breaking_changes.append("Making field required")
        
        # Reducing max_length is breaking
        if (current_config.max_length and new_config.max_length and 
            new_config.max_length < current_config.max_length):
            breaking_changes.append(f"Reducing max_length from {current_config.max_length} to {new_config.max_length}")
        
        return breaking_changes
    
    def _field_has_data(self, model_name: str, field_name: str) -> bool:
        """Check if field has data in any records."""
        # This would check if the custom field has values
        # Implementation depends on how custom field values are stored
        return False
    
    def _backup_field_data(self, model_name: str, field_name: str):
        """Create backup of field data before deletion."""
        # Implementation would backup field values
        pass
    
    def _delete_field_definition(self, model_name: str, field_name: str):
        """Delete field definition from database."""
        try:
            from crm.models.system import CustomField
            CustomField.objects.filter(
                tenant=self.tenant,
                model_name=model_name,
                field_name=field_name
            ).update(is_active=False, deleted_at=timezone.now())
        except Exception as e:
            print(f"Error deleting field definition: {e}")
    
    def _update_field_definition(self, model_name: str, field_name: str, 
                               config: FieldConfiguration):
        """Update field definition in database."""
        try:
            from crm.models.system import CustomField
            CustomField.objects.filter(
                tenant=self.tenant,
                model_name=model_name,
                field_name=field_name
            ).update(
                label=config.label,
                description=config.description,
                required=config.required,
                default_value=config.default_value,
                max_length=config.max_length,
                min_value=config.min_value,
                max_value=config.max_value,
                decimal_places=config.decimal_places,
                choices=json.dumps(config.choices) if config.choices else None,
                regex_pattern=config.regex_pattern,
                regex_message=config.regex_message,
                help_text=config.help_text,
                placeholder=config.placeholder,
                css_classes=config.css_classes,
                widget_attrs=json.dumps(config.widget_attrs) if config.widget_attrs else None,
                validation_rules=json.dumps(config.validation_rules) if config.validation_rules else None,
                conditional_logic=json.dumps(config.conditional_logic) if config.conditional_logic else None,
                permissions=json.dumps(config.permissions) if config.permissions else None,
                reference_model=config.reference_model,
                reference_field=config.reference_field,
                updated_at=timezone.now()
            )
        except Exception as e:
            print(f"Error updating field definition: {e}")
    
    def _create_field_migration(self, model_name: str, field_name: str, config: FieldConfiguration):
        """Create database migration for new field."""
        # This would create Django migration files
        # Implementation depends on deployment strategy
        pass
    
    def _create_drop_field_migration(self, model_name: str, field_name: str):
        """Create migration to drop field from database."""
        # This would create Django migration to drop column
        pass


# Convenience functions
def create_custom_field(model_name: str, field_name: str, config: FieldConfiguration, 
                       tenant=None) -> Dict[str, Any]:
    """Create custom field."""
    manager = CustomFieldManager(tenant)
    return manager.create_custom_field(model_name, field_name, config)


def get_custom_fields(model_name: str, tenant=None) -> List[Dict[str, Any]]:
    """Get custom fields for model."""
    manager = CustomFieldManager(tenant)
    return manager.get_custom_fields(model_name)


def validate_custom_field_value(model_name: str, field_name: str, value: Any, 
                               tenant=None) -> FieldValue:
    """Validate custom field value."""
    manager = CustomFieldManager(tenant)
    return manager.validate_field_value(model_name, field_name, value)


def get_model_form_fields(model_name: str, tenant=None) -> Dict[str, forms.Field]:
    """Get Django form fields for model's custom fields."""
    manager = CustomFieldManager(tenant)
    return manager.get_model_form_fields(model_name)


def create_text_field(label: str, required: bool = False, max_length: int = 255) -> FieldConfiguration:
    """Create text field configuration."""
    return FieldConfiguration(
        field_type=FieldType.TEXT,
        label=label,
        required=required,
        max_length=max_length
    )


def create_choice_field(label: str, choices: List[Dict[str, str]], 
                       required: bool = False) -> FieldConfiguration:
    """Create choice field configuration."""
    return FieldConfiguration(
        field_type=FieldType.CHOICE,
        label=label,
        required=required,
        choices=choices
    )


def create_currency_field(label: str, required: bool = False, 
                         min_value: float = None, max_value: float = None) -> FieldConfiguration:
    """Create currency field configuration."""
    return FieldConfiguration(
        field_type=FieldType.CURRENCY,
        label=label,
        required=required,
        min_value=min_value,
        max_value=max_value,
        decimal_places=2
    )