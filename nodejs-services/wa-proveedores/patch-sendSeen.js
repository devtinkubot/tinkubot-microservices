const fs = require('fs');

const filePath = '/usr/src/app/node_modules/whatsapp-web.js/src/util/Injected/Utils.js';
let content = fs.readFileSync(filePath, 'utf8');

// Buscar y reemplazar la función sendSeen usando un patrón más flexible
const oldPattern = /window\.WWebJS\.sendSeen = async \(chatId\) => \{[\s\S]*?window\.Store\.WAWebStreamModel\.Stream\.markAvailable\(\);[\s\S]*?await window\.Store\.SendSeen\.sendSeen\(chat\);[\s\S]*?window\.Store\.WAWebStreamModel\.Stream\.markUnavailable\(\);[\s\S]*?return true;[\s\S]*?\}[\s\S]*?return false;[\s\S]*?\};/;

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

if (oldPattern.test(content)) {
    content = content.replace(oldPattern, newCode);
    fs.writeFileSync(filePath, content);
    console.log('✅ Patch aplicado correctamente a Utils.js');
} else {
    console.log('⚠️  No se encontró el patrón original, intentando método alternativo...');
    // Método alternativo: buscar y reemplazar de forma más directa
    const oldString = 'window.WWebJS.sendSeen = async (chatId) => {\n        const chat = await window.WWebJS.getChat(chatId, { getAsModel: false });\n        if (chat) {\n            window.Store.WAWebStreamModel.Stream.markAvailable();\n            await window.Store.SendSeen.sendSeen(chat);\n            window.Store.WAWebStreamModel.Stream.markUnavailable();\n            return true;\n        }\n        return false;\n    };';
    if (content.includes(oldString)) {
        content = content.replace(oldString, newCode);
        fs.writeFileSync(filePath, content);
        console.log('✅ Patch aplicado correctamente (método alternativo)');
    } else {
        console.log('❌ No se pudo aplicar el patch');
        process.exit(1);
    }
}
