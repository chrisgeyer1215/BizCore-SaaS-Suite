# BizCore SaaS Suite

BizCore SaaS Suite is a modular, multi-tenant business platform built with Django and Django REST Framework. It is designed to support modern SaaS operations across multiple organizations, with tenant-aware data isolation, role-based access, API-driven workflows, and background processing for automation and analytics.

The platform combines core business capabilities such as CRM, inventory, ecommerce, finance, and AI-assisted features into a single extensible system.

## Overview

This repository contains the backend services and infrastructure for a scalable SaaS application. The system is built around:

- Multi-tenant architecture using tenant-aware schemas
- Secure authentication and authorization with JWT-based APIs
- Modular business applications for CRM, inventory, ecommerce, and finance
- Async background jobs and scheduled tasks with Celery
- OpenAPI-based API documentation and interactive Swagger/Redoc views
- Containerized deployment with Docker Compose

## Key Features

- Tenant-based isolation for multi-company deployments
- RESTful APIs for core business operations
- Custom authentication flow with email-based login support
- CRM and sales workflow management
- Inventory and product management
- Ecommerce and commerce-related services
- Finance and accounting integrations
- AI and analytics-ready application structure
- Background task processing and scheduled jobs

## Technology Stack

### Backend
- Python 3
- Django 4.2
- Django REST Framework
- Django Tenants
- Celery + Redis
- PostgreSQL
- JWT authentication
- drf-spectacular for API schema generation

### Infrastructure
- Docker Compose
- PostgreSQL container
- Redis container
- Optional frontend service container

## Project Structure

```text
backend/                # Django application and API services
  apps/                  # Core modules: auth, crm, inventory, ecommerce, finance, ai
  config/                # Django settings, URLs, and Celery configuration
  templates/             # Shared templates
  tests/                 # Backend tests
backup inv/             # Additional backup/inventory-related module
deployment/             # Deployment assets and manifests
docker-compose.yml      # Local development stack
```

## Getting Started

### Prerequisites

Make sure the following are installed on your machine:

- Docker Desktop
- Docker Compose
- Git

### Quick Start with Docker

From the project root, run:

```bash
docker compose up --build
```

This will start the following services:

- PostgreSQL database
- Redis cache/message broker
- Django backend API
- Celery worker
- Celery beat scheduler
- Frontend service (when available in the local environment)

Once the services are running, you can access:

- API: http://localhost:8000
- Swagger UI: http://localhost:8000/api/docs/
- Redoc: http://localhost:8000/api/redoc/
- Frontend: http://localhost:3000

## Development Setup

If you want to work directly in the backend environment:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Then configure your environment variables and start the Django server:

```bash
python manage.py migrate
python manage.py runserver
```

## Environment Variables

The application uses environment variables for configuration, including:

- `SECRET_KEY`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`

For local development, Docker Compose provides sensible defaults. For production, these values should be changed to secure, environment-specific configuration.

## API Documentation

The project exposes interactive API documentation via:

- Swagger UI: `/api/docs/`
- Redoc: `/api/redoc/`
- OpenAPI schema: `/api/schema/`

## Testing

Run backend tests with:

```bash
cd backend
python manage.py test
```

## Contribution Guidelines

Contributions are welcome. To contribute:

1. Fork the repository
2. Create a feature branch
3. Implement your changes
4. Add or update tests where appropriate
5. Submit a pull request with a clear summary

## License

A license file has not been added to this repository yet. Please contact the maintainers for usage and distribution terms.

## Contact

For questions, support, or collaboration opportunities, please reach out through the repository maintainers or project owners.
