#!/bin/bash
# Patch para whatsapp-web.js - manejar error de markedUnread
FILE="/usr/src/app/node_modules/whatsapp-web.js/src/util/Injected/Utils.js"

# Crear un patch que envuelva el código en try-catch
python3 << 'PYTHON'
import re

with open('/usr/src/app/node_modules/whatsapp-web.js/src/util/Injected/Utils.js', 'r') as f:
    content = f.read()

# Buscar la función sendSeen y reemplazarla con versión con try-catch
old_pattern = r'''window\.WWebJS\.sendSeen = async \(chatId\) => \{
        const chat = await window\.WWebJS\.getChat\(chatId, \{ getAsModel: false \}\);
        if \(chat\) \{
            window\.Store\.WAWebStreamModel\.Stream\.markAvailable\(\);
            await window\.Store\.SendSeen\.sendSeen\(chat\);
            window\.Store\.WAWebStreamModel\.Stream\.markUnavailable\(\);
            return true;
        \}
        return false;
    \};'''

new_code = '''window.WWebJS.sendSeen = async (chatId) => {
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
            // Ignorar errores de markedUnread
            if (error.message && error.message.includes("markedUnread")) {
                return false;
            }
            throw error;
        }
    };'''

content = re.sub(old_pattern, new_code, content)

with open('/usr/src/app/node_modules/whatsapp-web.js/src/util/Injected/Utils.js', 'w') as f:
    f.write(content)

print("Patch aplicado correctamente")
PYTHON
