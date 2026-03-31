import { defineMiddlewares } from "@medusajs/medusa"
import type { MedusaNextFunction, MedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { join } from "path"
import { createReadStream, existsSync, statSync } from "fs"

// Función para obtener el mime type basado en la extensión
const getMimeType = (filePath: string): string => {
    const ext = filePath.split('.').pop()?.toLowerCase()
    const mimeTypes: Record<string, string> = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'gif': 'image/gif',
        'webp': 'image/webp',
        'svg': 'image/svg+xml',
        'pdf': 'application/pdf',
    }
    return mimeTypes[ext || ''] || 'application/octet-stream'
}

// Middleware para servir archivos estáticos desde /uploads
const serveUploads = async (
    req: MedusaRequest,
    res: MedusaResponse,
    next: MedusaNextFunction
) => {
    const filename = req.params.filename
    
    if (!filename) {
        return next()
    }
    
    const uploadsDir = join(process.cwd(), "uploads")
    const filePath = join(uploadsDir, filename)

    // Verificar que el archivo existe y está dentro del directorio uploads
    if (!filePath.startsWith(uploadsDir)) {
        res.status(403).json({ message: "Forbidden" })
        return
    }

    if (!existsSync(filePath)) {
        res.status(404).json({ message: "File not found" })
        return
    }

    try {
        const stat = statSync(filePath)
        const mimeType = getMimeType(filePath)

        res.setHeader("Content-Type", mimeType)
        res.setHeader("Content-Length", stat.size)
        res.setHeader("Cache-Control", "public, max-age=31536000")

        const stream = createReadStream(filePath)
        stream.pipe(res)
    } catch (error) {
        console.error("Error serving file:", error)
        res.status(500).json({ message: "Error serving file" })
    }
}

export default defineMiddlewares({
    routes: [
        {
            matcher: "/uploads/:filename",
            method: "GET",
            middlewares: [serveUploads],
        },
    ],
})
