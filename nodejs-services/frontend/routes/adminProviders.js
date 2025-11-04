const express = require('express');
const proveedoresBff = require('../bff/providers');

const router = express.Router();

async function obtenerPendientes(req, res) {
  try {
    const providers = await proveedoresBff.obtenerProveedoresPendientes();
    res.json({ providers });
  } catch (error) {
    const status = error?.status ?? 500;
    const payload = error?.data ?? {
      error: 'No se pudo obtener la lista de proveedores pendientes.'
    };
    res.status(status).json(payload);
  }
}

async function aprobarProveedor(req, res) {
  try {
    const { providerId } = req.params;
    const resultado = await proveedoresBff.aprobarProveedor(providerId, req.body ?? {});
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
    const resultado = await proveedoresBff.rechazarProveedor(providerId, req.body ?? {});
    res.json(resultado);
  } catch (error) {
    const status = error?.status ?? 500;
    const payload = error?.data ?? {
      error: 'No se pudo rechazar el proveedor.'
    };
    res.status(status).json(payload);
  }
}

router.get('/pending', obtenerPendientes);
router.post('/:providerId/approve', aprobarProveedor);
router.post('/:providerId/reject', rechazarProveedor);

module.exports = router;
