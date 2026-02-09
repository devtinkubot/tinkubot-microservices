const express = require('express');
const axios = require('axios');
const proveedoresBff = require('../bff/providers');

// Configuración de Supabase Storage
const supabaseUrl = process.env.SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_SERVICE_KEY;
const supabaseStorageUrl = supabaseUrl ? `${supabaseUrl.replace(/\/$/, '')}/storage/v1` : null;
const supabaseProvidersBucket =
  (process.env.SUPABASE_PROVIDERS_BUCKET || 'tinkubot-providers').trim();

const router = express.Router();

async function obtenerPendientes(req, res) {
  try {
    const providers = await proveedoresBff.obtenerProveedoresNuevos();
    res.json({ providers });
  } catch (error) {
    const status = error?.status ?? 500;
    const payload = error?.data ?? {
      error: 'No se pudo obtener la lista de proveedores pendientes.'
    };
    res.status(status).json(payload);
  }
}

async function obtenerNuevos(req, res) {
  try {
    const providers = await proveedoresBff.obtenerProveedoresNuevos();
    res.json({ providers });
  } catch (error) {
    const status = error?.status ?? 500;
    const payload = error?.data ?? {
      error: 'No se pudo obtener la lista de proveedores nuevos.'
    };
    res.status(status).json(payload);
  }
}

async function obtenerPostRevision(req, res) {
  try {
    const providers = await proveedoresBff.obtenerProveedoresPostRevision();
    res.json({ providers });
  } catch (error) {
    const status = error?.status ?? 500;
    const payload = error?.data ?? {
      error: 'No se pudo obtener la lista de proveedores post-revisión.'
    };
    res.status(status).json(payload);
  }
}

async function aprobarProveedor(req, res) {
  try {
    const { providerId } = req.params;
    const requestId = req.headers['x-request-id'] || req.headers['x-correlation-id'] || null;
    const resultado = await proveedoresBff.aprobarProveedor(providerId, req.body ?? {}, requestId);
    res.json(resultado);
  } catch (error) {
    const status = error?.status ?? 500;
    const payload = error?.data ?? {
      error: 'No se pudo aprobar el proveedor.'
    };
    res.status(status).json(payload);
  }
}

async function rechazarProveedor(req, res) {
  try {
    const { providerId } = req.params;
    const requestId = req.headers['x-request-id'] || req.headers['x-correlation-id'] || null;
    const resultado = await proveedoresBff.rechazarProveedor(providerId, req.body ?? {}, requestId);
    res.json(resultado);
  } catch (error) {
    const status = error?.status ?? 500;
    const payload = error?.data ?? {
      error: 'No se pudo rechazar el proveedor.'
    };
    res.status(status).json(payload);
  }
}

async function revisarProveedor(req, res) {
  try {
    const { providerId } = req.params;
    const requestId = req.headers['x-request-id'] || req.headers['x-correlation-id'] || null;
    const resultado = await proveedoresBff.revisarProveedor(
      providerId,
      req.body ?? {},
      requestId
    );
    res.json(resultado);
  } catch (error) {
    const status = error?.status ?? 500;
    const payload = error?.data ?? {
      error: 'No se pudo procesar la revisión del proveedor.'
    };
    res.status(status).json(payload);
  }
}

async function servirImagen(req, res) {
  try {
    const filePath = req.params[0]; // Para wildcard router.get('/image/*')

    if (!supabaseStorageUrl || !supabaseKey) {
      return res.status(500).json({ error: 'Storage no configurado' });
    }

    const sanitizedPath = (filePath || '')
      .split('/')
      .filter(segment => segment && segment !== '.' && segment !== '..')
      .join('/');

    if (!sanitizedPath) {
      return res.status(400).json({ error: 'Ruta de archivo inválida' });
    }

    const imageUrl = `${supabaseStorageUrl}/object/${supabaseProvidersBucket}/${sanitizedPath}`;

    const response = await axios.get(imageUrl, {
      headers: {
        'apikey': supabaseKey,
        'Authorization': `Bearer ${supabaseKey}`
      },
      responseType: 'stream'
    });

    // Pasar headers de la respuesta original
    res.set('Content-Type', response.headers['content-type']);
    res.set('Content-Length', response.headers['content-length']);
    res.set('Cache-Control', 'public, max-age=3600'); // Cache por 1 hora

    response.data.pipe(res);
  } catch (error) {
    console.error('Error sirviendo imagen:', error);
    res.status(404).json({ error: 'Imagen no encontrada' });
  }
}

router.get('/pending', obtenerPendientes);
router.get('/new', obtenerNuevos);
router.get('/post-review', obtenerPostRevision);
router.post('/:providerId/approve', aprobarProveedor);
router.post('/:providerId/reject', rechazarProveedor);
router.post('/:providerId/review', revisarProveedor);
router.get('/image/*', servirImagen);

module.exports = router;
