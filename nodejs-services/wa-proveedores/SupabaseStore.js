const { createClient } = require('@supabase/supabase-js');
const fs = require('fs-extra');
const archiver = require('archiver');
const unzipper = require('unzipper');

/**
 * SupabaseStore - Almacenamiento de sesiones de WhatsApp en Supabase Storage
 * Compatible con la estrategia RemoteAuth de whatsapp-web.js
 */
class SupabaseStore {
  constructor(supabaseUrl, supabaseKey, bucketName = 'wa_sessions') {
    this.supabase = createClient(supabaseUrl, supabaseKey);
    this.bucketName = bucketName;
    this.lastSaveLogTs = 0;
    this.saveLogIntervalMs = 60 * 1000; // throttle log to once per minute
    console.warn(`[SupabaseStore] Inicializado con bucket: ${bucketName}`);
  }

  /**
   * Verifica si una sesión existe en el storage
   */
  async sessionExists({ session }) {
    try {
      const { data, error } = await this.supabase.storage.from(this.bucketName).list('');
      if (error || !Array.isArray(data)) return false;
      return data.some(item => item.name === `${session}.zip`);
    } catch (error) {
      console.error(`Error checking session ${session}:`, error);
      return false;
    }
  }

  /**
   * Guarda una sesión comprimida en Supabase Storage
   */
  async save({ session, path }) {
    try {
      const sessionZipPath = `${session}.zip`;

      // Si se proporciona un directorio, comprimirlo primero
      if (path && (await fs.pathExists(path))) {
        await this.compressDir(path, sessionZipPath);
      }

      // Verificar si el ZIP existe
      if (!(await fs.pathExists(sessionZipPath))) {
        console.error(`Session file ${sessionZipPath} not found`);
        return null;
      }

      const fileBuffer = await fs.readFile(sessionZipPath);

      // Subir a Supabase Storage
      const { data, error } = await this.supabase.storage
        .from(this.bucketName)
        .upload(`${session}.zip`, fileBuffer, {
          upsert: true,
          contentType: 'application/zip',
        });

      if (error) {
        console.error(`Error saving session ${session}:`, error);
        throw error;
      }

      const now = Date.now();
      if (now - this.lastSaveLogTs >= this.saveLogIntervalMs) {
        console.debug(`✅ Session ${session} saved to Supabase Storage`);
        this.lastSaveLogTs = now;
      }
      // Nota: no eliminar el ZIP aquí; whatsapp-web.js lo eliminará
      return data;
    } catch (error) {
      console.error(`Error in save operation for session ${session}:`, error);
      throw error;
    }
  }

  /**
   * Extrae una sesión desde Supabase Storage
   */
  async extract({ session, path }) {
    try {
      const sessionZipPath = path || `${session}.zip`;

      // Solución 2: Verificar edad del archivo antes de descargar
      const { data: fileList, error: listError } = await this.supabase.storage
        .from(this.bucketName)
        .list('');

      if (!listError && Array.isArray(fileList)) {
        const fileMetadata = fileList.find(item => item.name === `${session}.zip`);
        if (fileMetadata && fileMetadata.updated_at) {
          const fileAge = Date.now() - new Date(fileMetadata.updated_at).getTime();
          const MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000; // 7 días

          if (fileAge > MAX_AGE_MS) {
            const ageDays = Math.floor(fileAge / (24 * 60 * 60 * 1000));
            console.warn(
              `⚠️ [SupabaseStore] Session ${session} is too old (${ageDays} days). ` +
              `Deleting and requesting fresh QR.`
            );
            await this.delete({ session });
            return null; // Forzar generación de nuevo QR
          }
        }
      }

      const { data, error } = await this.supabase.storage
        .from(this.bucketName)
        .download(`${session}.zip`);

      if (error || !data) {
        console.warn(
          `ℹ️ [SupabaseStore] No remote session found for ${session}. Will generate new QR code.`
        );
        return null; // Permitir generar QR nuevo
      }

      let fileBuffer = data;
      if (typeof data.arrayBuffer === 'function') {
        fileBuffer = Buffer.from(await data.arrayBuffer());
      }

      await fs.writeFile(sessionZipPath, fileBuffer);
      // Solución 4: Agregar tamaño del archivo al log
      const sizeKB = (fileBuffer.length / 1024).toFixed(2);
      console.warn(`✅ [SupabaseStore] Session ${session} downloaded to ${sessionZipPath} (${sizeKB} KB)`);
      // Nota: no descomprimir ni eliminar; whatsapp-web.js se encarga
      return true;
    } catch (error) {
      console.warn(`ℹ️ [SupabaseStore] Skipping restore for ${session} due to error:`, error?.message || error);
      return null; // Continuar sin sesión
    }
  }

  /**
   * Elimina una sesión del storage
   */
  async delete({ session }) {
    try {
      const { data, error } = await this.supabase.storage
        .from(this.bucketName)
        .remove([`${session}.zip`]);

      if (error) {
        console.error(`Error deleting session ${session}:`, error);
        throw error;
      }

      console.warn(`✅ Session ${session} deleted from Supabase Storage`);
      return data;
    } catch (error) {
      console.error(`Error in delete operation for session ${session}:`, error);
      throw error;
    }
  }

  /**
   * Extrae un archivo ZIP en el directorio especificado
   */
  async extractZip(zipPath, extractPath) {
    if (!(await fs.pathExists(zipPath))) {
      return;
    }
    return new Promise((resolve, reject) => {
      fs.createReadStream(zipPath)
        .pipe(unzipper.Extract({ path: extractPath }))
        .on('error', reject)
        .on('finish', resolve);
    });
  }

  /**
   * Comprime un directorio en un archivo ZIP
   */
  async compressDir(sourceDir, outputPath) {
    return new Promise((resolve, reject) => {
      const output = fs.createWriteStream(outputPath);
      const archive = archiver('zip', { zlib: { level: 9 } });

      output.on('close', resolve);
      archive.on('error', reject);

      archive.pipe(output);
      archive.directory(sourceDir, false);
      archive.finalize();
    });
  }

  /**
   * Lista todas las sesiones disponibles
   */
  async listSessions() {
    try {
      const { data, error } = await this.supabase.storage.from(this.bucketName).list();

      if (error) {
        console.error('Error listing sessions:', error);
        throw error;
      }

      return data
        .filter(item => item.name.endsWith('.zip'))
        .map(item => ({
          name: item.name.replace('.zip', ''),
          size: item.metadata?.size || 0,
          created_at: item.created_at,
        }));
    } catch (error) {
      console.error('Error in listSessions operation:', error);
      throw error;
    }
  }
}

module.exports = SupabaseStore;
