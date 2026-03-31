# =============================================
# Stage 1: Build
# =============================================
FROM node:20-slim AS builder

WORKDIR /app

# Copy package files and install ALL dependencies (including devDependencies for build)
COPY package*.json ./
RUN npm install --no-audit --no-fund --loglevel=error

# Copy application source
COPY . .

# Ensure directories exist for build
RUN mkdir -p src/api/store src/api/admin src/modules src/scripts uploads

# Build Medusa for production
# Set MEDUSA_BACKEND_URL so the admin dashboard is compiled for the correct origin
RUN MEDUSA_BACKEND_URL=https://abtattoo-medusa-xqvxl67u7a-ew.a.run.app npx medusa build

# Verify admin dashboard was built
RUN test -f .medusa/server/public/admin/index.html \
    || (echo "ERROR: Admin dashboard build not found!" && find .medusa -name 'index.html' 2>/dev/null && exit 1)

# =============================================
# Stage 2: Production runtime
# =============================================
FROM node:20-slim

WORKDIR /app

# Install only what's needed at runtime
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Copy built artifacts and production files from builder
COPY --from=builder /app/.medusa ./.medusa
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/medusa-config.ts ./medusa-config.ts
COPY --from=builder /app/tsconfig.json ./tsconfig.json
COPY --from=builder /app/src ./src

# Ensure admin dashboard is accessible at the path medusa start expects.
# medusa build outputs to .medusa/server/public/admin/ but medusa start
# may look for it at ./public/admin/ relative to the project root.
RUN mkdir -p public && ln -s /app/.medusa/server/public/admin public/admin

# Copy production start script
COPY start.prod.sh ./start.prod.sh
RUN chmod +x start.prod.sh

# Create uploads directory
RUN mkdir -p uploads

# Cloud Run uses PORT env var (default 9000)
ENV PORT=9000
EXPOSE ${PORT}

# Health check (used locally / docker-compose; Cloud Run uses its own probes)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Start production server
CMD ["./start.prod.sh"]
