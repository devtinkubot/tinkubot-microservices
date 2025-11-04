const express = require('express');
const axios = require('axios');
const path = require('path');
const QRCode = require('qrcode');
const fs = require('fs');
const adminProvidersRouter = require('./routes/adminProviders');
const app = express();

const parsearPuerto = valor => {
  const numero = Number(valor);
  return Number.isFinite(numero) && numero > 0 ? numero : undefined;
};

const resolverPuerto = (valorPorDefecto, ...candidatos) => {
  for (const candidato of candidatos) {
    const puerto = parsearPuerto(candidato);
    if (puerto !== undefined) {
      return puerto;
    }
  }
  return valorPorDefecto;
};

// Configuración
const PORT = resolverPuerto(5000, process.env.FRONTEND_SERVICE_PORT);
const clientesPort = resolverPuerto(
  5001,
  process.env.CLIENTES_WHATSAPP_PORT,
  process.env.WHATSAPP_CLIENTES_PORT
);
const proveedoresPort = resolverPuerto(
  5002,
  process.env.PROVEEDORES_WHATSAPP_PORT,
  process.env.WHATSAPP_PROVEEDORES_PORT
);

const serverDomain = process.env.SERVER_DOMAIN;
const clientesHost = serverDomain || 'wa-clientes';
const proveedoresHost = serverDomain || 'wa-proveedores';

const WHATSAPP_CLIENTES_URL =
  process.env.WHATSAPP_CLIENTES_URL || `http://${clientesHost}:${clientesPort}`;
const WHATSAPP_PROVEEDORES_URL =
  process.env.WHATSAPP_PROVEEDORES_URL || `http://${proveedoresHost}:${proveedoresPort}`;

const CLIENTES_INSTANCE_ID = process.env.CLIENTES_INSTANCE_ID || 'bot-clientes';
const CLIENTES_INSTANCE_NAME = process.env.CLIENTES_INSTANCE_NAME || 'TinkuBot Clientes';
const PROVEEDORES_INSTANCE_ID =
  process.env.PROVEEDORES_INSTANCE_ID || 'bot-proveedores';
const PROVEEDORES_INSTANCE_NAME =
  process.env.PROVEEDORES_INSTANCE_NAME || 'TinkuBot Proveedores';

// Configuración de instancias
const WHATSAPP_INSTANCES = [
  {
    id: CLIENTES_INSTANCE_ID,
    name: CLIENTES_INSTANCE_NAME,
    url: WHATSAPP_CLIENTES_URL,
    port: clientesPort,
  },
  {
    id: PROVEEDORES_INSTANCE_ID,
    name: PROVEEDORES_INSTANCE_NAME,
    url: WHATSAPP_PROVEEDORES_URL,
    port: proveedoresPort,
  },
];

console.warn('🔧 Configuración de instancias:');
WHATSAPP_INSTANCES.forEach(instance => {
  console.warn(`  - ${instance.name}: ${instance.url}`);
});

const dashboardDistPath = path.join(__dirname, 'apps', 'admin-dashboard', 'dist');
const publicPath = path.join(__dirname, 'public');

const existeCompilacionDashboard = () => fs.existsSync(path.join(dashboardDistPath, 'index.html'));

if (fs.existsSync(dashboardDistPath)) {
  console.warn(`🧱 Dashboard compilado encontrado en: ${dashboardDistPath}`);
} else {
  console.warn('⚠️ No se encontró build del dashboard, sirviendo versión legacy desde /public.');
}

// Middleware
if (fs.existsSync(dashboardDistPath)) {
  app.use(express.static(dashboardDistPath));
}
app.use(express.static(publicPath));
app.use(express.json());
app.use('/admin/providers', adminProvidersRouter);

// Health check para monitoreo básico
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    instances: WHATSAPP_INSTANCES.map(({ id, name, url }) => ({ id, name, url })),
    uptime_seconds: Math.round(process.uptime()),
  });
});

// Rutas
app.get('/', (req, res) => {
  if (existeCompilacionDashboard()) {
    return res.sendFile(path.join(dashboardDistPath, 'index.html'));
  }
  return res.sendFile(path.join(publicPath, 'admin-dashboard.html'));
});

app.get('/login.html', (req, res) => {
  res.redirect('/');
});

// API para obtener estado de WhatsApp por instancia
app.get('/api/whatsapp/:instanceId/status', async (req, res) => {
  try {
    const { instanceId } = req.params;
    const instance = WHATSAPP_INSTANCES.find(inst => inst.id === instanceId);

    if (!instance) {
      return res.status(404).json({ error: 'Instancia no encontrada' });
    }

    const response = await axios.get(`${instance.url}/status`, { timeout: 5000 });
    res.json({
      ...response.data,
      instanceId: instance.id,
      instanceName: instance.name,
    });
  } catch (error) {
    console.error('Error al obtener estado de WhatsApp:', error);
    res.status(500).json({ error: 'Error al conectar con WhatsApp Service' });
  }
});

// API para obtener QR por instancia
app.get('/api/whatsapp/:instanceId/qr', async (req, res) => {
  try {
    const { instanceId } = req.params;
    const instance = WHATSAPP_INSTANCES.find(inst => inst.id === instanceId);

    if (!instance) {
      return res.status(404).json({ error: 'Instancia no encontrada' });
    }

    const response = await axios.get(`${instance.url}/qr`, { timeout: 5000 });
    res.json({
      ...response.data,
      instanceId: instance.id,
      instanceName: instance.name,
    });
  } catch (error) {
    console.error('Error al obtener QR:', error);
    res.status(500).json({ error: 'Error al obtener QR de WhatsApp' });
  }
});

// API para enviar mensaje por instancia
app.post('/api/whatsapp/:instanceId/send', async (req, res) => {
  try {
    const { instanceId } = req.params;
    const { phone, message } = req.body;
    const instance = WHATSAPP_INSTANCES.find(inst => inst.id === instanceId);

    if (!instance) {
      return res.status(404).json({ error: 'Instancia no encontrada' });
    }

    const response = await axios.post(
      `${instance.url}/send`,
      { phone, message },
      { timeout: 5000 }
    );
    res.json({
      ...response.data,
      instanceId: instance.id,
      instanceName: instance.name,
    });
  } catch (error) {
    console.error('Error al enviar mensaje:', error);
    res.status(500).json({ error: 'Error al enviar mensaje' });
  }
});

app.post('/api/whatsapp/:instanceId/refresh', async (req, res) => {
  try {
    const { instanceId } = req.params;
    const instance = WHATSAPP_INSTANCES.find(inst => inst.id === instanceId);

    if (!instance) {
      return res.status(404).json({ error: 'Instancia no encontrada' });
    }

    const response = await axios.post(`${instance.url}/refresh`, null, { timeout: 5000 });
    res.json({
      ...response.data,
      instanceId: instance.id,
      instanceName: instance.name,
    });
  } catch (error) {
    console.error('Error al regenerar QR:', error?.message || error);
    const status = error.response?.status || 500;
    const payload = error.response?.data || { error: 'Error al regenerar el código QR' };
    res.status(status).json(payload);
  }
});

// API para obtener estado de WhatsApp (simplificado)
app.get('/whatsapp-status', async (req, res) => {
  try {
    const statuses = {};

    for (const instance of WHATSAPP_INSTANCES) {
      try {
        // Obtener estado del servicio
        const statusResponse = await axios.get(`${instance.url}/status`, { timeout: 3000 });
        const statusData = statusResponse.data;

        // Si el estado es qr_ready, obtener el código QR y convertirlo a imagen
        if (statusData.status === 'qr_ready') {
          let qrText;
          try {
            const qrResponse = await axios.get(`${instance.url}/qr`, { timeout: 5000 });
            qrText = qrResponse.data.qr;

            // Convertir QR de texto a imagen base64
            console.warn(`${instance.name}: Convirtiendo QR texto a imagen...`);
            const qrImage = await QRCode.toDataURL(qrText, {
              width: 300,
              margin: 2,
              color: {
                dark: '#000000',
                light: '#FFFFFF',
              },
            });
            console.warn(
              `${instance.name}: QR convertido exitosamente, longitud: ${qrImage.length}`
            );

            statuses[instance.id] = {
              connected: false,
              qr: qrImage,
              phone: null,
              battery: null,
            };
          } catch (qrError) {
            console.error(`Error al procesar QR de ${instance.name}:`, qrError);
            console.error('Texto QR recibido:', qrText ? `${qrText.substring(0, 50)}...` : 'null');
            statuses[instance.id] = {
              connected: false,
              qr: null,
              phone: null,
              battery: null,
            };
          }
        } else if (statusData.status === 'connected' || statusData.connected) {
          // Si está conectado, usar los datos reales
          statuses[instance.id] = {
            connected: true,
            qr: null,
            phone: statusData.phone || null,
            battery: statusData.battery || null,
          };
        } else {
          // Para cualquier otro estado, mostrar como desconectado
          statuses[instance.id] = {
            connected: false,
            qr: null,
            phone: null,
            battery: null,
          };
        }
      } catch (error) {
        console.error(`Error al obtener estado de ${instance.name}:`, error);
        statuses[instance.id] = {
          connected: false,
          qr: null,
          phone: null,
          battery: null,
        };
      }
    }

    res.json(statuses);
  } catch (error) {
    console.error('Error al obtener estado de WhatsApp:', error);
    res.status(500).json({ error: 'Error al obtener estado de WhatsApp' });
  }
});

// Endpoint de health check
app.get('/health', async (req, res) => {
  const healthStatus = {
    status: 'healthy',
    service: 'frontend-service',
    port: PORT,
    timestamp: new Date().toISOString(),
    dependencies: {},
  };

  for (const instance of WHATSAPP_INSTANCES) {
    healthStatus.dependencies[instance.id] = {
      name: instance.name,
      status: 'unknown',
    };

    try {
      const { data } = await axios.get(`${instance.url}/health`, { timeout: 4000 });
      const dependencyStatus = data.status || data.health || 'unknown';

      healthStatus.dependencies[instance.id] = {
        name: instance.name,
        status: dependencyStatus,
        whatsapp_status: data.whatsapp_status || data.status || null,
        ai_service: data.ai_service || null,
        timestamp: data.timestamp || null,
      };

      if (dependencyStatus !== 'healthy') {
        healthStatus.status = dependencyStatus === 'degraded' ? 'degraded' : 'unhealthy';
      }
    } catch (error) {
      healthStatus.dependencies[instance.id] = {
        name: instance.name,
        status: 'unreachable',
        error: error.message,
      };
      healthStatus.status = 'unhealthy';
    }
  }

  res.json(healthStatus);
});

// Iniciar servidor
app.listen(PORT, '0.0.0.0', () => {
  console.warn(`🚀 Frontend Service corriendo en puerto ${PORT}`);
  console.warn(`📱 Dashboard disponible en: http://localhost:${PORT}`);
  console.warn(`🔗 Conectado a ${WHATSAPP_INSTANCES.length} instancias de WhatsApp`);
});
