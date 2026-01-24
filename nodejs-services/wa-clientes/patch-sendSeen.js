const fs = require('fs');

const filePath = '/usr/src/app/node_modules/whatsapp-web.js/src/util/Injected/Utils.js';
let content = fs.readFileSync(filePath, 'utf8');

// Buscar y reemplazar la función sendSeen
const oldCode = `window.WWebJS.sendSeen = async (chatId) => {
        const chat = await window.WWebJS.getChat(chatId, { getAsModel: false });
        if (chat) {
            window.Store.WAWebStreamModel.Stream.markAvailable();
            await window.Store.SendSeen.sendSeen(chat);
            window.Store.WAWebStreamModel.Stream.markUnavailable();
            return true;
        }
        return false;
    };`;

const newCode = `window.WWebJS.sendSeen = async (chatId) => {
        try {
            const chat = await window.WWebJS.getChat(chatId, { getAsModel: false });
            if (chat) {
                window.Store.WAWebStreamModel.Stream.markAvailable();
                await window.Store.SendSeen.sendSeen(chat);
                window.Store.WAWebStreamModel.Stream.markUnavailable();
                return true;
            }
            return false;
        } catch (error) {
            // Ignorar errores de markedUnread - bug de whatsapp-web.js
            if (error.message && error.message.includes("markedUnread")) {
                return false;
            }
            throw error;
        }
    };`;

content = content.replace(oldCode, newCode);

fs.writeFileSync(filePath, content);
console.log('Patch aplicado correctamente a Utils.js');
