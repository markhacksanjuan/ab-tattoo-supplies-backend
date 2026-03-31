# 🚀 Despliegue en Google Cloud — AB-Tattoo Backend

Guía para desplegar **Medusa** y **User-API** en **Cloud Run** usando **Cloud Build**.

---

## Arquitectura

```
                    ┌──────────────────┐
                    │   Cloud Build    │
                    │  (CI/CD pipeline)│
                    └────────┬─────────┘
                             │ build + push
                    ┌────────▼─────────┐
                    │ Artifact Registry│
                    │  (Docker images) │
                    └────────┬─────────┘
                             │ deploy
              ┌──────────────┴──────────────┐
              │                             │
    ┌─────────▼──────────┐      ┌───────────▼────────┐
    │  Cloud Run:        │      │  Cloud Run:        │
    │  abtattoo-medusa   │      │  abtattoo-user-api │
    │  (Node.js/Medusa)  │      │  (Python/FastAPI)  │
    │  Puerto 9000       │      │  Puerto 8000       │
    └─────────┬──────────┘      └───────────┬────────┘
              │                             │
    ┌─────────▼──────────┐      ┌───────────▼────────┐
    │  Cloud SQL /       │      │  MongoDB Atlas     │
    │  PostgreSQL externo│      │                    │
    │  + Redis           │      │                    │
    └────────────────────┘      └────────────────────┘
```

---

## Requisitos previos

1. **Google Cloud CLI** instalado y autenticado:
   ```bash
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   ```

2. **APIs habilitadas**:
   ```bash
   gcloud services enable \
     cloudbuild.googleapis.com \
     run.googleapis.com \
     artifactregistry.googleapis.com \
     secretmanager.googleapis.com
   ```

3. **Artifact Registry** — repositorio de imágenes Docker:
   ```bash
   gcloud artifacts repositories create abtattoo \
     --repository-format=docker \
     --location=europe-west1 \
     --description="AB-Tattoo Docker images"
   ```

---

## Paso 1: Configurar Secrets

Todos los secretos se gestionan con **Secret Manager**. Crea cada uno:

```bash
# Medusa secrets
echo -n "postgresql://user:pass@host:5432/db?sslmode=require" | \
  gcloud secrets create DATABASE_URL --data-file=-

echo -n "redis://10.0.0.3:6379" | \
  gcloud secrets create REDIS_URL --data-file=-

echo -n "$(openssl rand -hex 32)" | \
  gcloud secrets create JWT_SECRET --data-file=-

echo -n "$(openssl rand -hex 32)" | \
  gcloud secrets create COOKIE_SECRET --data-file=-

echo -n "sk_live_xxx" | \
  gcloud secrets create STRIPE_API_KEY --data-file=-

echo -n "https://tu-storefront.vercel.app" | \
  gcloud secrets create STORE_CORS --data-file=-

echo -n "https://tu-storefront.vercel.app,https://abtattoo-medusa-xxx-ew.a.run.app" | \
  gcloud secrets create ADMIN_CORS --data-file=-

echo -n "https://tu-storefront.vercel.app,https://abtattoo-medusa-xxx-ew.a.run.app" | \
  gcloud secrets create AUTH_CORS --data-file=-

echo -n "https://abtattoo-medusa-xxx-ew.a.run.app" | \
  gcloud secrets create MEDUSA_BACKEND_URL --data-file=-

echo -n "admin@abtattoo.com" | \
  gcloud secrets create MEDUSA_ADMIN_EMAIL --data-file=-

echo -n "TuPasswordSeguro123" | \
  gcloud secrets create MEDUSA_ADMIN_PASSWORD --data-file=-

# S3/GCS file storage secrets
echo -n "https://storage.googleapis.com/tu-bucket" | \
  gcloud secrets create S3_FILE_URL --data-file=-

echo -n "tu_access_key" | \
  gcloud secrets create S3_ACCESS_KEY_ID --data-file=-

echo -n "tu_secret_key" | \
  gcloud secrets create S3_SECRET_ACCESS_KEY --data-file=-

echo -n "auto" | \
  gcloud secrets create S3_REGION --data-file=-

echo -n "tu-bucket" | \
  gcloud secrets create S3_BUCKET --data-file=-

echo -n "https://storage.googleapis.com" | \
  gcloud secrets create S3_ENDPOINT --data-file=-

# User-API secrets
echo -n "mongodb+srv://user:pass@cluster.mongodb.net/users-db" | \
  gcloud secrets create MONGODB_URL --data-file=-

echo -n "$(openssl rand -hex 32)" | \
  gcloud secrets create USER_API_JWT_SECRET --data-file=-

echo -n "https://tu-storefront.vercel.app" | \
  gcloud secrets create CORS_ORIGINS --data-file=-

echo -n "pk_xxx" | \
  gcloud secrets create MEDUSA_PUBLISHABLE_KEY --data-file=-

# Google OAuth (optional)
echo -n "xxx.apps.googleusercontent.com" | \
  gcloud secrets create GOOGLE_CLIENT_ID --data-file=-

echo -n "xxx" | \
  gcloud secrets create GOOGLE_CLIENT_SECRET --data-file=-

echo -n "https://abtattoo-user-api-xxx-ew.a.run.app/api/auth/google/callback" | \
  gcloud secrets create GOOGLE_REDIRECT_URI --data-file=-

echo -n "https://tu-storefront.vercel.app" | \
  gcloud secrets create FRONTEND_URL --data-file=-
```

---

## Paso 2: Configurar permisos de Cloud Build

```bash
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')

# Permitir a Cloud Build desplegar en Cloud Run
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/run.admin"

# Permitir actuar como la cuenta de servicio de compute
gcloud iam service-accounts add-iam-policy-binding \
  ${PROJECT_NUMBER}-compute@developer.gserviceaccount.com \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# Permitir acceso a Secret Manager
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Permitir a la cuenta de servicio de Cloud Run acceder a los secretos
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

---

## Paso 3: Desplegar

### Desplegar ambos servicios
```bash
gcloud builds submit \
  --config=backend/cloudbuild.yaml \
  --substitutions=_PROJECT_ID=$PROJECT_ID
```

### Desplegar solo Medusa
```bash
gcloud builds submit \
  --config=backend/cloudbuild.yaml \
  --substitutions=_PROJECT_ID=$PROJECT_ID,_DEPLOY_MEDUSA=true,_DEPLOY_USER_API=false
```

### Desplegar solo User-API
```bash
gcloud builds submit \
  --config=backend/cloudbuild.yaml \
  --substitutions=_PROJECT_ID=$PROJECT_ID,_DEPLOY_MEDUSA=false,_DEPLOY_USER_API=true
```

---

## Paso 4: Obtener las URLs

Después del despliegue:

```bash
# URL de Medusa
gcloud run services describe abtattoo-medusa \
  --region=europe-west1 \
  --format='value(status.url)'

# URL de User-API
gcloud run services describe abtattoo-user-api \
  --region=europe-west1 \
  --format='value(status.url)'
```

> ⚠️ **Importante**: Después del primer despliegue, actualiza los secretos `MEDUSA_BACKEND_URL`, `ADMIN_CORS`, `AUTH_CORS`, `GOOGLE_REDIRECT_URI` y `FRONTEND_URL` con las URLs reales de Cloud Run, y re-despliega.

---

## Paso 5: Actualizar secretos (post-despliegue)

```bash
# Actualizar un secreto existente
echo -n "nuevo-valor" | \
  gcloud secrets versions add SECRET_NAME --data-file=-

# Re-desplegar para que tome el nuevo secreto
gcloud run services update abtattoo-medusa --region=europe-west1
gcloud run services update abtattoo-user-api --region=europe-west1
```

---

## CI/CD automático con Cloud Build Triggers

Para desplegar automáticamente en cada push:

```bash
# Crear trigger para la rama main
gcloud builds triggers create github \
  --name="abtattoo-backend-deploy" \
  --repo-name="ab-tattoo-supplies-storefront" \
  --repo-owner="markhacksanjuan" \
  --branch-pattern="^main$" \
  --build-config="backend/cloudbuild.yaml" \
  --substitutions="_PROJECT_ID=$PROJECT_ID" \
  --included-files="backend/**"
```

---

## Base de datos: opciones recomendadas

| Servicio     | Opción GCP                    | Opción externa               |
|--------------|-------------------------------|------------------------------|
| PostgreSQL   | Cloud SQL for PostgreSQL      | Supabase, Neon, Railway      |
| Redis        | Memorystore for Redis         | Upstash, Redis Cloud         |
| MongoDB      | MongoDB Atlas (recomendado)   | Self-hosted en Compute Engine|

> **Nota sobre Redis/Memorystore**: si usas Memorystore, necesitas configurar un **VPC Connector** en tu servicio Cloud Run. Si prefieres no complicarte, usa [Upstash](https://upstash.com/) que funciona sin VPC.

### Añadir VPC Connector (solo si usas Memorystore)
```bash
# Crear conector VPC
gcloud compute networks vpc-access connectors create abtattoo-connector \
  --region=europe-west1 \
  --range=10.8.0.0/28

# Actualizar Cloud Run para usar el conector
gcloud run services update abtattoo-medusa \
  --region=europe-west1 \
  --vpc-connector=abtattoo-connector
```

---

## Monitorización

```bash
# Ver logs de Medusa
gcloud run services logs read abtattoo-medusa --region=europe-west1

# Ver logs de User-API
gcloud run services logs read abtattoo-user-api --region=europe-west1

# Métricas en la consola
# https://console.cloud.google.com/run?project=YOUR_PROJECT_ID
```

---

## Costes estimados (europe-west1)

| Recurso               | Estimación (poco tráfico)  |
|------------------------|---------------------------|
| Cloud Run (2 servicios)| ~$0-5/mes (con min=0)     |
| Artifact Registry      | ~$0.10/GB/mes             |
| Secret Manager         | ~$0.06/secreto/mes        |
| Cloud Build            | 120 min/día gratis        |
| **Total estimado**     | **~$5-15/mes**            |

> Con `min-instances=0`, Cloud Run escala a cero cuando no hay tráfico (cold starts de ~3-5s para Medusa).
