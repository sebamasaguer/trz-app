# Análisis de Código y Guía de Implementación en Dokploy

Este documento proporciona un análisis del código actual y los pasos detallados para implementar la aplicación utilizando Dokploy.

## 1. Análisis del Código

La aplicación es un sistema de gestión (TRZ FUNCIONAL) desarrollado con las siguientes tecnologías:

- **Framework Web:** FastAPI (Python 3.11+).
- **Base de Datos:** PostgreSQL (usando SQLAlchemy como ORM).
- **Migraciones:** Alembic.
- **Autenticación:** JWT (JSON Web Tokens) y cookies.
- **Dependencias:** Gestionadas vía `requirements.txt`.
- **Estructura Detallada:**
    - `app/`:
        - `core/`: Configuración global (`config.py`), logging y seguridad.
        - `models/`: Modelos de base de datos SQLAlchemy y enums.
        - `schemas/`: Esquemas Pydantic para validación de datos.
        - `repositories/`: Patrón Repository para el acceso a datos.
        - `services/`: Lógica de negocio centralizada.
        - `routers/`: Definición de endpoints de la API organizados por módulos (auth, admin, alumnos, profesores, etc.).
        - `templates/` y `static/`: Frontend basado en Jinja2 y archivos estáticos.
    - `alembic/`: Scripts de migración de base de datos.
    - `scripts/`: Scripts de utilidad adicionales.
    - `tests/`: Suite de pruebas (unitarias e integrales).

### Puntos clave para el despliegue:
- La aplicación requiere una base de datos PostgreSQL.
- Se configuran variables de entorno críticas en `app/core/config.py`.
- El punto de entrada es `app.main:app`.

---

## 2. Requisitos Previos en Dokploy

Antes de comenzar, asegúrate de tener:
1. Una instancia de Dokploy funcionando.
2. Acceso al repositorio de código (GitHub/GitLab) o capacidad para subir el código.

---

## 3. Paso a Paso para la Implementación

### Paso 1: Crear un nuevo Proyecto
1. Accede a tu panel de Dokploy.
2. Haz clic en **"Create Project"** y dale un nombre (ej. `trz-funcional`).

### Paso 2: Crear el servicio de Base de Datos
1. Dentro del proyecto, ve a **"Services"** y selecciona **"PostgreSQL"**.
2. Configura las credenciales (User, Password, Database Name).
3. Una vez creada, Dokploy te proporcionará una **Internal Connection String** (ej. `postgresql://user:pass@host:port/db`). *Cópiala, la necesitarás más adelante.*

### Paso 3: Crear la Aplicación
1. En el mismo proyecto, haz clic en **"Create Service"** -> **"Application"**.
2. Selecciona la fuente de tu código (Repositorio Git).
3. En la configuración de la aplicación:
    - **Build Type:** Selecciona `Dockerfile`.
    - **Port:** Configura el puerto `8000`.

### Paso 4: Configurar Variables de Entorno
Ve a la pestaña **"Environment"** de tu aplicación en Dokploy y agrega las siguientes variables (basadas en `app/core/config.py`):

| Variable | Valor Sugerido / Ejemplo |
| :--- | :--- |
| `ENV` | `production` |
| `DATABASE_URL` | *La URL de conexión de PostgreSQL del Paso 2* |
| `JWT_SECRET` | *Una cadena larga y aleatoria (min 16 chars)* |
| `QR_SECRET` | *Una cadena larga y aleatoria* |
| `APP_NAME` | `TRZ FUNCIONAL` |
| `COOKIE_SECURE` | `True` (si usas HTTPS) |
| `APP_BASE_URL` | `https://tu-dominio.com` |
| `OPENAI_API_KEY` | *Tu clave de API de OpenAI (opcional)* |
| `N8N_FOLLOWUP_WEBHOOK_URL` | *Webhook para seguimientos (opcional)* |

### Paso 5: Migraciones y Seed (Opcional/Inicial)
La aplicación está configurada para ejecutar las migraciones automáticamente al iniciar el contenedor mediante el archivo `entrypoint.sh`.

Si necesitas ejecutarlas manualmente o realizar el sembrado inicial:
1. **Migraciones:** `alembic upgrade head` (aunque se ejecutan solas al desplegar).
2. **Sembrar administrador:** `python seed_admin.py` (ejecutar desde la terminal de Dokploy si es la primera vez).

### Paso 6: Desplegar
1. Haz clic en **"Deploy"**. Dokploy construirá la imagen usando el `Dockerfile` y levantará el contenedor.
2. Configura el dominio en la pestaña **"Domains"** para exponer la aplicación al público.

---

## 4. Archivos Creados/Modificados
- `Dockerfile`: Configurado para empaquetar la aplicación FastAPI.
- `DEPLOYMENT.md`: Este manual de instrucciones.
