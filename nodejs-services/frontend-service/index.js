const express = require('express');
const axios = require('axios');
const path = require('path');
const QRCode = require('qrcode');
const app = express();

// Configuración
const PORT = process.env.FRONTEND_PORT || 6002;
const WHATSAPP_CLIENTES_URL =
  process.env.WHATSAPP_CLIENTES_URL || 'http://whatsapp-service-clientes:7001';
const WHATSAPP_PROVEEDORES_URL =
  process.env.WHATSAPP_PROVEEDORES_URL || 'http://whatsapp-service-proveedores:7002';

// Configuración de instancias
const WHATSAPP_INSTANCES = [
  {
    id: 'bot-clientes',
    name: 'TinkuBot Clientes',
    url: WHATSAPP_CLIENTES_URL,
    port: 7001,
  },
  {
    id: 'bot-proveedores',
    name: 'TinkuBot Proveedores',
    url: WHATSAPP_PROVEEDORES_URL,
    port: 7002,
  },
];

console.warn('🔧 Configuración de instancias:');
WHATSAPP_INSTANCES.forEach(instance => {
  console.warn(`  - ${instance.name}: ${instance.url}`);
});

// Middleware
app.use(express.static('public'));
app.use(express.json());

// Rutas
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'admin-dashboard.html'));
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
