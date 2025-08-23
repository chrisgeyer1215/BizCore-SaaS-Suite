X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999  
X-RateLimit-Reset: 1640995200

### **6. Postman Collection Generator (`backend/management/commands/generate_postman.py`)**

```python
# backend/apps/core/management/commands/generate_postman.py
import json
from django.core.management.base import BaseCommand
from django.urls import reverse
from django.conf import settings

class Command(BaseCommand):
    help = 'Generate Postman collection for API testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='api_postman_collection.json',
            help='Output file name for Postman collection'
        )

    def handle(self, *args, **options):
        collection = {
            "info": {
                "name": "SaaS-AICE CRM API",
                "description": "Complete API collection for SaaS-AICE multi-tenant CRM platform",
                "version": "1.0.0",
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
            },
            "auth": {
                "type": "bearer",
                "bearer": [{"key": "token", "value": "{{jwt_token}}", "type": "string"}]
            },
            "variable": [
                {
                    "key": "base_url",
                    "value": "https://{{tenant}}.saas-aice.com/api/v1",
                    "type": "string"
                },
                {
                    "key": "tenant",
                    "value": "acme-corp",
                    "type": "string"
                },
                {
                    "key": "jwt_token", 
                    "value": "",
                    "type": "string"
                }
            ],
            "item": [
                self._get_auth_folder(),
                self._get_crm_folder(),
                self._get_analytics_folder(),
                self._get_bulk_operations_folder(),
            ]
        }
        
        output_file = options['output']
        with open(output_file, 'w') as f:
            json.dump(collection, f, indent=2)
            
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully generated Postman collection: {output_file}'
            )
        )

    def _get_auth_folder(self):
        return {
            "name": "Authentication",
            "item": [
                {
                    "name": "Login",
                    "request": {
                        "method": "POST",
                        "header": [
                            {"key": "Content-Type", "value": "application/json"}
                        ],
                        "body": {
                            "mode": "raw",
                            "raw": json.dumps({
                                "email": "user@example.com",
                                "password": "password123"
                            })
                        },
                        "url": {
                            "raw": "{{base_url}}/auth/login/",
                            "host": ["{{base_url}}"],
                            "path": ["auth", "login", ""]
                        }
                    },
                    "event": [
                        {
                            "listen": "test",
                            "script": {
                                "exec": [
                                    "if (responseCode.code === 200) {",
                                    "    const response = pm.response.json();",
                                    "    pm.collectionVariables.set('jwt_token', response.access_token);",
                                    "}"
                                ]
                            }
                        }
                    ]
                },
                {
                    "name": "Refresh Token",
                    "request": {
                        "method": "POST",
                        "header": [
                            {"key": "Content-Type", "value": "application/json"}
                        ],
                        "body": {
                            "mode": "raw",
                            "raw": json.dumps({
                                "refresh": "{{refresh_token}}"
                            })
                        },
                        "url": {
                            "raw": "{{base_url}}/auth/refresh/",
                            "host": ["{{base_url}}"], 
                            "path": ["auth", "refresh", ""]
                        }
                    }
                }
            ]
        }

    def _get_crm_folder(self):
        return {
            "name": "CRM Operations",
            "item": [
                {
                    "name": "Accounts",
                    "item": [
                        {
                            "name": "List Accounts",
                            "request": {
                                "method": "GET",
                                "url": {
                                    "raw": "{{base_url}}/crm/accounts/",
                                    "host": ["{{base_url}}"],
                                    "path": ["crm", "accounts", ""]
                                }
                            }
                        },
                        {
                            "name": "Create Account", 
                            "request": {
                                "method": "POST",
                                "header": [
                                    {"key": "Content-Type", "value": "application/json"}
                                ],
                                "body": {
                                    "mode": "raw",
                                    "raw": json.dumps({
                                        "name": "Example Corp",
                                        "email": "contact@example.com",
                                        "phone": "+1-555-0123",
                                        "industry": "technology",
                                        "annual_revenue": 5000000,
                                        "employees": 100
                                    })
                                },
                                "url": {
                                    "raw": "{{base_url}}/crm/accounts/",
                                    "host": ["{{base_url}}"],
                                    "path": ["crm", "accounts", ""]
                                }
                            }
                        }
                    ]
                },
                # Add more CRM endpoints...
            ]
        }

    def _get_analytics_folder(self):
        return {
            "name": "Analytics & Reporting",
            "item": [
                {
                    "name": "Sales Pipeline",
                    "request": {
                        "method": "GET",
                        "url": {
                            "raw": "{{base_url}}/crm/analytics/sales-pipeline/?time_range=90d",
                            "host": ["{{base_url}}"],
                            "path": ["crm", "analytics", "sales-pipeline", ""],
                            "query": [{"key": "time_range", "value": "90d"}]
                        }
                    }
                }
            ]
        }

    def _get_bulk_operations_folder(self):
        return {
            "name": "Bulk Operations",
            "item": [
                {
                    "name": "Bulk Import Leads",
                    "request": {
                        "method": "POST",
                        "header": [],
                        "body": {
                            "mode": "formdata",
                            "formdata": [
                                {
                                    "key": "file",
                                    "type": "file",
                                    "src": ""
                                },
                                {
                                    "key": "skip_duplicates", 
                                    "value": "true",
                                    "type": "text"
                                }
                            ]
                        },
                        "url": {
                            "raw": "{{base_url}}/crm/leads/bulk-import/",
                            "host": ["{{base_url}}"],
                            "path": ["crm", "leads", "bulk-import", ""]
                        }
                    }
                }
            ]
        }