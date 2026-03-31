import { defineConfig, loadEnv } from "@medusajs/framework/utils";

loadEnv(process.env.NODE_ENV || "development", process.cwd());

// ── Helpers ────────────────────────────────────────────────────────
// A Redis URL is considered "real" only when the env var exists,
// is not the word "placeholder", and actually looks like a redis:// URL.
const isRedisAvailable =
  !!process.env.REDIS_URL &&
  !process.env.REDIS_URL.includes("placeholder") &&
  process.env.REDIS_URL.startsWith("redis");

// S3 is considered configured only when real credentials are provided
// (not the "placeholder" values created by gcp-setup.sh).
const isS3Configured =
  !!process.env.S3_ACCESS_KEY_ID &&
  process.env.S3_ACCESS_KEY_ID !== "placeholder" &&
  !!process.env.S3_FILE_URL &&
  !!process.env.S3_ENDPOINT;

export default defineConfig({
  projectConfig: {
    databaseUrl: process.env.DATABASE_URL || "postgresql://tattoo_medusa_user:tattoo_medusa_pass@localhost:5432/tattoo_store?sslmode=disable",
    // IMPORTANT: only set redisUrl when Redis is truly available.
    // Setting it to a non-existent or placeholder URL causes Medusa to
    // auto-configure locking/workflow modules with Redis, which then
    // throw "Invalid URL" at startup.
    ...(isRedisAvailable ? { redisUrl: process.env.REDIS_URL } : {}),
    workerMode: (process.env.MEDUSA_WORKER_MODE || "shared") as "shared" | "worker" | "server",
    http: {
      storeCors: process.env.STORE_CORS || "http://localhost:3000",
      adminCors: process.env.ADMIN_CORS || "http://localhost:3000,http://localhost:7000,http://localhost:9000",
      authCors: process.env.AUTH_CORS || "http://localhost:3000,http://localhost:7000,http://localhost:9000",
      jwtSecret: process.env.JWT_SECRET || "supersecret",
      cookieSecret: process.env.COOKIE_SECRET || "supersecret",
    },
  },
  admin: {
    backendUrl: process.env.MEDUSA_BACKEND_URL || "http://localhost:9000",
    disable: false,
  },
  modules: [
    // Redis modules: only use Redis if a real redis:// URL is available.
    // Otherwise, Medusa falls back to in-memory (suitable for initial deploy / migrations)
    ...(isRedisAvailable
      ? [
          {
            resolve: "@medusajs/medusa/cache-redis",
            options: {
              redisUrl: process.env.REDIS_URL,
            },
          },
          {
            resolve: "@medusajs/medusa/event-bus-redis",
            options: {
              redisUrl: process.env.REDIS_URL,
            },
          },
        ]
      : []),
    {
      resolve: "@medusajs/medusa/file",
      options: {
        providers: [
          // Use S3 / GCS in production (only when real credentials exist),
          // local filesystem otherwise.
          ...(isS3Configured
            ? [
                {
                  resolve: "@medusajs/file-s3",
                  id: "s3",
                  options: {
                    file_url: process.env.S3_FILE_URL,
                    access_key_id: process.env.S3_ACCESS_KEY_ID,
                    secret_access_key: process.env.S3_SECRET_ACCESS_KEY,
                    region: process.env.S3_REGION || "auto",
                    bucket: process.env.S3_BUCKET,
                    endpoint: process.env.S3_ENDPOINT,
                    prefix: process.env.S3_PREFIX || "uploads",
                  },
                },
              ]
            : [
                {
                  resolve: "@medusajs/medusa/file-local",
                  id: "local",
                  options: {
                    upload_dir: "uploads",
                    backend_url: process.env.MEDUSA_BACKEND_URL || "http://localhost:9000",
                  },
                },
              ]),
        ],
      },
    },
    {
      resolve: "@medusajs/medusa/payment",
      options: {
        providers: [
          {
            resolve: "@medusajs/medusa/payment-stripe",
            id: "stripe",
            options: {
              apiKey: process.env.STRIPE_API_KEY || "",
            },
          },
        ],
      },
    },
    {
      resolve: "@medusajs/medusa/fulfillment",
      options: {
        providers: [
          {
            resolve: "@medusajs/medusa/fulfillment-manual",
            id: "manual",
          },
        ],
      },
    },
  ],
});
