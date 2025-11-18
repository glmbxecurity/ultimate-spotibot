# 🎧 Ultimate SpotiBOT & Spotify CLI Tools

¡Bienvenido a Ultimate SpotiBOT! Este proyecto es una suite de herramientas de automatización para Spotify escrita en Python. Permite gestionar, analizar y actualizar tus playlists de forma inteligente.

El proyecto incluye dos interfaces para usar las mismas herramientas:

* 🤖 Bot de Telegram: Para controlar todo desde el chat de tu móvil o PC.

* 💻 CLI (Consola): Para ejecutar scripts directamente en tu terminal sin necesidad de Telegram.

## 🚀 Funcionalidades

Ambas versiones (Telegram y CLI) incluyen las siguientes herramientas:

* 📊 Ranking de Popularidad: Analiza cualquier playlist y devuelve las canciones ordenadas por su índice de popularidad actual.

* 🍹 Party Mixer: Combina múltiples playlists en una sola.

  * Modo Normal: Añade las canciones de una lista tras otra.

  * Modo Mix: Intercala canciones para una mezcla perfecta.

* 🆕 Actualizador Automático: Lee un fichero de fuentes (playlists.txt) y busca canciones nuevas (agregadas en los últimos X días) para crear nuevas playlists por género o añadirlas automáticamente a tus propias playlists.

## 🛠️ Requisitos Previos

* Python 3.8 o superior.

* Una cuenta de Spotify (se recomienda Premium para evitar límites de API, pero funciona con Free).

* Una cuenta de Telegram (para la versión Bot).

## 📦 Instalación

Clona este repositorio:
```bash
git clone https://github.com/glmbxecurity/ultimate-spotibot/
cd ultimate-spotibot
```

Instala las dependencias:
Ejecuta el siguiente comando para instalar las librerías necesarias (spotipy, python-telegram-bot, pandas, etc.):
```bash
pip install spotipy python-telegram-bot pandas nest_asyncio
```

Prepara la estructura de carpetas:
El bot necesita ciertos archivos para funcionar correctamente. Asegúrate de que tu carpeta tenga esta estructura:
```bash
/ultimate-spotibot/
├── bot_spotibot.py      # Versión Telegram
├── cli_spotibot.py         # Versión Consola (CLI)
├── playlists.txt          # (Ver formato abajo)
├── global_tracks.txt      # (Se crea automáticamente)
├── data/                  # Carpeta vacía para historiales
└── images/                # Carpeta para portadas de playlists
```

## ⚙️ Configuración

Para que el bot funcione, necesitas obtener credenciales de Spotify y de Telegram.

* 1. Spotify Developer (API)

  * Ve al Spotify Developer Dashboard e inicia sesión.

  * Haz clic en "Create App".

  * Dale un nombre (ej: SpotiManager) y una descripción.

  * En Redirect URI, es CRUCIAL que añadas exactamente esta dirección: http://127.0.0.1:8888/callback

  * Guarda los cambios.

  * En los ajustes de tu App, copia el Client ID y el Client Secret.

* 2. Telegram Bot (Solo para la versión Bot)

  * Abre Telegram y busca a @BotFather.

  * Envía el comando /newbot.

  * Sigue los pasos y obtén tu HTTP API Token.

  * Averigua tu propio ID de usuario de Telegram (puedes usar @userinfobot para verlo). Esto es necesario para que solo tú puedas usar las funciones de administración.

* 3. Configurar los Scripts

Abre los archivos bot_spotibot.py y cli_spotibot.py con un editor de texto y rellena las variables al principio del archivo:
```bash
# En bot_spotibot.py y cli_spotibot.py
SPOTIPY_CLIENT_ID = "PEGA_AQUI_TU_CLIENT_ID"
SPOTIPY_CLIENT_SECRET = "PEGA_AQUI_TU_CLIENT_SECRET"
SPOTIPY_REDIRECT_URI = "http://127.0.0.1:8888/callback"

# Solo en bot_spotibot.py
TELEGRAM_TOKEN = "PEGA_AQUI_TU_TOKEN_DE_TELEGRAM"
AUTHORIZED_USER_IDS = {123456789} # Tu chat ID numérico de Telegram
```

### 📄 Archivos de Datos

playlists.txt

Este archivo le dice al "Actualizador" qué playlists debe espiar. El formato es:
```bash
URL_PLAYLIST # GENERO
```
Ejemplo:
```bash
https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M # ROCK
https://open.spotify.com/playlist/37i9dQZF1DX0XUsuxWHRQd # HIPHOP
```

Imágenes (images/)

Si quieres que tus playlists generadas tengan portada, guarda imágenes .jpg en la carpeta images/ con el nombre del género.

Ejemplo: rock.jpg, hiphop.jpg.

### 🎮 Cómo Usar

#### Opción A: Versión CLI (Consola)

Ideal si quieres ejecutar tareas rápidas desde tu ordenador sin abrir Telegram.

Ejecuta el script:
```bash
python3 cli_spotibot.py
```

Autenticación (Primera vez):

Si el script se ejecuta en un servidor sin pantalla (headless), te mostrará una URL en la consola.

Copia esa URL -> Pégala en tu navegador -> Autoriza -> Copia la URL a la que te redirige (http://127.0.0.1...) -> Pégala de vuelta en la consola.

Sigue el menú interactivo por pantalla.

#### Opción B: Versión Telegram Bot

Ideal para tener el control siempre a mano desde telegram.

Ejecuta el script:
```bash
python3 bot_spotibot.py
```

Autenticación: Al igual que la versión CLI, la primera vez verificará las credenciales por la consola antes de arrancar el bot. Sigue los pasos en la terminal si te lo pide.

Una vez veas el mensaje 🤖 Iniciando Bot de Telegram..., ve a tu bot en Telegram.

Envía /start.

Usa el menú:

/rank: Te pedirá una URL y te devolverá el Top Popularidad.

/mixer: Te pedirá varias URLs y creará una mezcla.

/create_update_playlist: Escaneará playlists.txt y actualizará tus listas.

## ⚠️ Solución de Problemas

Error "Redirect URI": Asegúrate de que en el Spotify Dashboard has puesto exactamente http://127.0.0.1:8888/callback.

El navegador no carga la página 127.0.0.1: Es normal. Cuando autorizas en Spotify, te redirige a esa dirección. Aunque veas "No se puede conectar", copia la URL completa de la barra de direcciones y pégala en la terminal.

Permission Denied: Asegúrate de que tu ID de Telegram está en la lista AUTHORIZED_USER_IDS.

## 📄 Licencia

Este proyecto es de uso personal y educativo. No está afiliado con Spotify.
