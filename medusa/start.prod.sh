#!/bin/sh
set -e

echo "🚀 Starting AB-Tattoo Medusa Backend (Production)..."

# ── Database migrations ──────────────────────────────────────────
echo "⏳ Waiting for database connection..."
MAX_RETRIES=30
RETRY=0
until npx medusa db:migrate 2>&1; do
    RETRY=$((RETRY + 1))
    if [ "$RETRY" -ge "$MAX_RETRIES" ]; then
        echo "❌ Database migration failed after ${MAX_RETRIES} attempts. Aborting."
        exit 1
    fi
    echo "⚠️  Migration attempt ${RETRY}/${MAX_RETRIES} failed. Retrying in 5s..."
    sleep 5
done
echo "✅ Database migrations completed successfully"

# Create admin user if it doesn't exist
if [ -n "$MEDUSA_ADMIN_EMAIL" ]; then
    echo "👤 Ensuring admin user exists..."
    npx medusa user --email "$MEDUSA_ADMIN_EMAIL" --password "${MEDUSA_ADMIN_PASSWORD:-ABTattooAdmin2024}" 2>&1 || {
        echo "✅ Admin user already exists or creation skipped"
    }
fi

echo ""
echo "=========================================="
echo "✨ AB-Tattoo Medusa Backend Ready!"
echo "=========================================="
echo "📍 API: ${MEDUSA_BACKEND_URL:-http://localhost:9000}"
echo "📍 Admin: ${MEDUSA_BACKEND_URL:-http://localhost:9000}/app"
echo "=========================================="
echo ""

# Start the production server
echo "🎯 Starting Medusa production server..."
exec npx medusa start
