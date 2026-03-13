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

async function obtenerMonetizacionResumen(req, res) {
  try {
    const overview = await proveedoresBff.obtenerMonetizacionResumen();
    res.json(overview);
  } catch (error) {
    const status = error?.status ?? 500;
    const payload = error?.data ?? {
      error: 'No se pudo obtener el resumen de monetización.'
    };
    res.status(status).json(payload);
  }
}

async function obtenerMonetizacionProveedores(req, res) {
  try {
    const status = typeof req.query.status === 'string' ? req.query.status : 'all';
    const limit = Number.isFinite(Number(req.query.limit))
      ? Number(req.query.limit)
      : undefined;
    const offset = Number.isFinite(Number(req.query.offset))
      ? Number(req.query.offset)
      : undefined;

    const resultado = await proveedoresBff.obtenerMonetizacionProveedores({
      status,
      limit,
      offset
    });
    res.json(resultado);
  } catch (error) {
    const status = error?.status ?? 500;
    const payload = error?.data ?? {
      error: 'No se pudo obtener el listado de monetización por proveedor.'
    };
    res.status(status).json(payload);
  }
}

async function obtenerMonetizacionProveedor(req, res) {
  try {
    const { providerId } = req.params;
    const resultado = await proveedoresBff.obtenerMonetizacionProveedor(providerId);
    res.json(resultado);
  } catch (error) {
    const status = error?.status ?? 500;
    const payload = error?.data ?? {
      error: 'No se pudo obtener el detalle de monetización del proveedor.'
    };
    res.status(status).json(payload);
  }
}

async function obtenerTaxonomiaSugerencias(req, res) {
  try {
    const status = typeof req.query.status === 'string' ? req.query.status : 'pending';
    const limit = Number.isFinite(Number(req.query.limit))
      ? Number(req.query.limit)
      : undefined;

    const resultado = await proveedoresBff.obtenerTaxonomiaSugerencias({
      status,
      limit
    });
    res.json(resultado);
  } catch (error) {
    const status = error?.status ?? 500;
    const payload = error?.data ?? {
      error: 'No se pudieron obtener las sugerencias de taxonomía.'
    };
    res.status(status).json(payload);
  }
}

async function obtenerGovernanceReviews(req, res) {
  try {
    const status = typeof req.query.status === 'string' ? req.query.status : 'pending';
    const limit = Number.isFinite(Number(req.query.limit))
      ? Number(req.query.limit)
      : undefined;

    const resultado = await proveedoresBff.obtenerGovernanceReviews({
      status,
      limit,
    });
    res.json(resultado);
  } catch (error) {
    const status = error?.status ?? 500;
    const payload = error?.data ?? {
      error: 'No se pudieron obtener las revisiones de gobernanza.'
    };
    res.status(status).json(payload);
  }
}

async function obtenerGovernanceDomains(req, res) {
  try {
    const resultado = await proveedoresBff.obtenerGovernanceDomains();
    res.json(resultado);
  } catch (error) {
    const status = error?.status ?? 500;
    const payload = error?.data ?? {
      error: 'No se pudieron obtener los dominios operativos.'
    };
    res.status(status).json(payload);
  }
}

async function obtenerGovernanceMetrics(req, res) {
  try {
    const resultado = await proveedoresBff.obtenerGovernanceMetrics();
    res.json(resultado);
  } catch (error) {
    const status = error?.status ?? 500;
    const payload = error?.data ?? {
      error: 'No se pudieron obtener las métricas de gobernanza.'
    };
    res.status(status).json(payload);
  }
}

async function aprobarGovernanceReview(req, res) {
  try {
    const { reviewId } = req.params;
    const requestId = req.headers['x-request-id'] || req.headers['x-correlation-id'] || null;
    const resultado = await proveedoresBff.aprobarGovernanceReview(
      reviewId,
      req.body ?? {},
      requestId
    );
    res.json(resultado);
  } catch (error) {
    const status = error?.status ?? 500;
    const payload = error?.data ?? {
      error: 'No se pudo aprobar la revisión de gobernanza.'
    };
    res.status(status).json(payload);
  }
}

async function rechazarGovernanceReview(req, res) {
  try {
    const { reviewId } = req.params;
    const requestId = req.headers['x-request-id'] || req.headers['x-correlation-id'] || null;
    const resultado = await proveedoresBff.rechazarGovernanceReview(
      reviewId,
      req.body ?? {},
      requestId
    );
    res.json(resultado);
  } catch (error) {
    const status = error?.status ?? 500;
    const payload = error?.data ?? {
      error: 'No se pudo rechazar la revisión de gobernanza.'
    };
    res.status(status).json(payload);
  }
}

async function obtenerTaxonomiaClusters(req, res) {
  try {
    const status = typeof req.query.status === 'string' ? req.query.status : 'pending';
    const limit = Number.isFinite(Number(req.query.limit))
      ? Number(req.query.limit)
      : undefined;

    const resultado = await proveedoresBff.obtenerTaxonomiaClusters({
      status,
      limit
    });
    res.json(resultado);
  } catch (error) {
    const status = error?.status ?? 500;
    const payload = error?.data ?? {
      error: 'No se pudieron obtener los clusters de taxonomía.'
    };
    res.status(status).json(payload);
  }
}

async function obtenerTaxonomiaOverview(req, res) {
  try {
    const resultado = await proveedoresBff.obtenerTaxonomiaOverview();
    res.json(resultado);
  } catch (error) {
    const status = error?.status ?? 500;
    const payload = error?.data ?? {
      error: 'No se pudo obtener el overview de taxonomía.'
    };
    res.status(status).json(payload);
  }
}

async function obtenerTaxonomiaCatalogo(req, res) {
  try {
    const resultado = await proveedoresBff.obtenerTaxonomiaCatalogo();
    res.json(resultado);
  } catch (error) {
    const status = error?.status ?? 500;
    const payload = error?.data ?? {
      error: 'No se pudo obtener el catálogo publicado de taxonomía.'
    };
    res.status(status).json(payload);
  }
}

async function revisarTaxonomiaSugerencia(req, res) {
  try {
    const { suggestionId } = req.params;
    const resultado = await proveedoresBff.revisarTaxonomiaSugerencia(
      suggestionId,
      req.body ?? {}
    );
    res.json(resultado);
  } catch (error) {
    const status = error?.status ?? 500;
    const payload = error?.data ?? {
      error: 'No se pudo actualizar la sugerencia de taxonomía.'
    };
    res.status(status).json(payload);
  }
}

async function aprobarTaxonomiaSugerencia(req, res) {
  try {
    const { suggestionId } = req.params;
    const resultado = await proveedoresBff.aprobarTaxonomiaSugerencia(
      suggestionId,
      req.body ?? {}
    );
    res.json(resultado);
  } catch (error) {
    const status = error?.status ?? 500;
    const payload = error?.data ?? {
      error: 'No se pudo aprobar la sugerencia de taxonomía.'
    };
    res.status(status).json(payload);
  }
}

async function revisarTaxonomiaCluster(req, res) {
  try {
    const { clusterId } = req.params;
    const resultado = await proveedoresBff.revisarTaxonomiaCluster(
      clusterId,
      req.body ?? {}
    );
    res.json(resultado);
  } catch (error) {
    const status = error?.status ?? 500;
    const payload = error?.data ?? {
      error: 'No se pudo actualizar el cluster de taxonomía.'
    };
    res.status(status).json(payload);
  }
}

async function aprobarTaxonomiaCluster(req, res) {
  try {
    const { clusterId } = req.params;
    const resultado = await proveedoresBff.aprobarTaxonomiaCluster(
      clusterId,
      req.body ?? {}
    );
    res.json(resultado);
  } catch (error) {
    const status = error?.status ?? 500;
    const payload = error?.data ?? {
      error: 'No se pudo aprobar el cluster de taxonomía.'
    };
    res.status(status).json(payload);
  }
}

async function obtenerTaxonomiaDrafts(req, res) {
  try {
    const resultado = await proveedoresBff.obtenerTaxonomiaDrafts();
    res.json(resultado);
  } catch (error) {
    const status = error?.status ?? 500;
    const payload = error?.data ?? {
      error: 'No se pudieron obtener los drafts de taxonomía.'
    };
    res.status(status).json(payload);
  }
}

async function aplicarTaxonomiaDraft(req, res) {
  try {
    const { changeId } = req.params;
    const resultado = await proveedoresBff.aplicarTaxonomiaDraft(changeId);
    res.json(resultado);
  } catch (error) {
    const status = error?.status ?? 500;
    const payload = error?.data ?? {
      error: 'No se pudo aplicar el draft de taxonomía.'
    };
    res.status(status).json(payload);
  }
}

async function publicarTaxonomiaDrafts(req, res) {
  try {
    const resultado = await proveedoresBff.publicarTaxonomiaDrafts();
    res.json(resultado);
  } catch (error) {
    const status = error?.status ?? 500;
    const payload = error?.data ?? {
      error: 'No se pudo publicar la nueva versión de taxonomía.'
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
router.get('/monetization/overview', obtenerMonetizacionResumen);
router.get('/monetization/providers', obtenerMonetizacionProveedores);
router.get('/monetization/provider/:providerId', obtenerMonetizacionProveedor);
router.get('/governance/reviews', obtenerGovernanceReviews);
router.get('/governance/domains', obtenerGovernanceDomains);
router.get('/governance/metrics', obtenerGovernanceMetrics);
router.post('/governance/reviews/:reviewId/approve', aprobarGovernanceReview);
router.post('/governance/reviews/:reviewId/reject', rechazarGovernanceReview);
router.get('/taxonomy/overview', obtenerTaxonomiaOverview);
router.get('/taxonomy/catalog', obtenerTaxonomiaCatalogo);
router.get('/taxonomy/suggestions', obtenerTaxonomiaSugerencias);
router.get('/taxonomy/suggestion-clusters', obtenerTaxonomiaClusters);
router.post('/taxonomy/suggestions/:suggestionId/review', revisarTaxonomiaSugerencia);
router.post('/taxonomy/suggestions/:suggestionId/approve-draft', aprobarTaxonomiaSugerencia);
router.post('/taxonomy/suggestion-clusters/:clusterId/review', revisarTaxonomiaCluster);
router.post('/taxonomy/suggestion-clusters/:clusterId/approve-draft', aprobarTaxonomiaCluster);
router.get('/taxonomy/drafts', obtenerTaxonomiaDrafts);
router.post('/taxonomy/drafts/:changeId/apply', aplicarTaxonomiaDraft);
router.post('/taxonomy/publish', publicarTaxonomiaDrafts);
router.get('/image/*', servirImagen);

module.exports = router;
