-- Archivo de inicialización para PostgreSQL
-- Este archivo se ejecuta automáticamente cuando se crea el contenedor por primera vez

-- Crear extensiones necesarias para Medusa
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Configurar permisos
GRANT ALL PRIVILEGES ON DATABASE tattoo_store TO tattoo_medusa_user;
