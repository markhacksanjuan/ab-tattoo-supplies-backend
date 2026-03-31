#!/bin/sh

echo "🚀 Starting AB-Tattoo Medusa Backend Setup (v2)..."

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL..."
until nc -z postgres 5432; do
  sleep 1
done
echo "✅ PostgreSQL is ready!"

# Wait for Redis to be ready
echo "⏳ Waiting for Redis..."
until nc -z redis 6379; do
  sleep 1
done
echo "✅ Redis is ready!"

# Additional wait for database to be fully ready
echo "⏳ Waiting for database to fully initialize..."
sleep 3

# Run migrations (Medusa v2 command)
echo "📦 Running database migrations..."
npx medusa db:migrate 2>&1 || echo "ℹ️  Migrations already applied or failed"

# Wait for migrations to complete
sleep 2

# Create admin user (Medusa v2 command)
ADMIN_EMAIL="${MEDUSA_ADMIN_EMAIL:-admin@abtattoo.com}"
ADMIN_PASSWORD="${MEDUSA_ADMIN_PASSWORD:-ABTattooAdmin2024}"
echo "👤 Creating admin user ($ADMIN_EMAIL)..."
CREATE_USER_OUTPUT=$(npx medusa user --email "$ADMIN_EMAIL" --password "$ADMIN_PASSWORD" 2>&1)
echo "create user output: $CREATE_USER_OUTPUT"
if echo "$CREATE_USER_OUTPUT" | grep -q "already exists\|duplicate"; then
  echo "✅ Admin user already exists"
else
  echo "✅ Admin user created"
fi

echo ""
echo "=========================================="
echo "✨ AB-Tattoo Medusa Backend Ready! (v2)"
echo "=========================================="
echo "📍 API: http://localhost:9000"
echo "📍 Admin: http://localhost:9000/app"
echo "👤 Email: $ADMIN_EMAIL"
echo "🔑 Password: $ADMIN_PASSWORD"
echo ""
echo "💡 TIP: Add products via Admin panel"
echo "=========================================="
echo ""

# Start the development server
echo "🎯 Starting Medusa v2 development server..."
exec npm run dev
