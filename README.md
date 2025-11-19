🎧 Ultimate SpotiBOT & Spotify CLI Tools

¡Bienvenido a Ultimate SpotiBOT! Este proyecto sirve para unificar todos los proyectos anteriores relacionados con herramientas CLI y bots de Spotify.
Es una suite de herramientas de automatización para Spotify escrita en Python. Permite gestionar, analizar y actualizar tus playlists de forma inteligente.

El proyecto incluye dos interfaces para usar las mismas herramientas:

🤖 Bot de Telegram: Para controlar todo desde el chat de tu móvil o PC.

💻 CLI (Consola): Para ejecutar scripts directamente en tu terminal sin necesidad de Telegram.

🚀 Funcionalidades

El bot cuenta con 5 herramientas principales divididas en análisis, creación y edición:

1. 📊 Ranking de Popularidad (/rank)

Analiza cualquier playlist (tuya o de otros) y devuelve una lista de todas sus canciones ordenadas por su índice de popularidad actual según Spotify. Ideal para descubrir cuáles son los verdaderos "hits" de una lista.

2. 🍹 Party Mixer (/mixer)

Combina múltiples playlists en una sola nueva playlist creada en tu cuenta.

Modo Normal: Añade las canciones de una lista tras otra (ej: Lista A completa + Lista B completa).

Modo Mix: Intercala canciones para una mezcla perfecta (ej: 1 de A, 1 de B, 1 de A...).

3. 🆕 Actualizador Automático (/updater)

Esta herramienta lee un fichero de configuración (playlists.txt) donde le indicas qué listas de Spotify quieres "espiar". El bot busca canciones nuevas agregadas en los últimos X días (configurable) en esas listas y las añade automáticamente a tus propias playlists organizadas por género.

4. ⚠️ Reordenar mis Listas (/sort)

Funcionalidad de Edición. Toma una playlist de la que eres dueño y reordena permanentemente sus canciones basándose en la popularidad (de mayor a menor).

Nota: Esta acción modifica el orden original de tu playlist en Spotify.

5. ✂️ Filtrar Mejores Canciones (/top)

Funcionalidad de Edición Destructiva. Ideal para limpiar listas largas. Ordena tu playlist por popularidad y conserva únicamente las "N" mejores canciones que tú elijas (ej: Top 50), eliminando el resto de la lista.

🛠️ Requisitos Previos

Python 3.8 o superior.

Una cuenta de Spotify (se recomienda Premium para evitar límites de API, pero funciona con Free).

Una cuenta de Telegram (para la versión Bot).

📦 Instalación

Clona este repositorio:

git clone [https://github.com/glmbxecurity/ultimate-spotibot/](https://github.com/glmbxecurity/ultimate-spotibot/)
cd ultimate-spotibot


Instala las dependencias:
Ejecuta el siguiente comando para instalar las librerías necesarias:

pip install spotipy python-telegram-bot pandas nest_asyncio


Prepara la estructura de carpetas:
Asegúrate de que tu carpeta tenga esta estructura:

/ultimate-spotibot/
├── bot_spotibot.py        # Versión Telegram
├── cli_spotibot.py        # Versión Consola (CLI)
├── playlists.txt          # Archivo de fuentes (URL GENERO)
├── global_tracks.txt      # Registro para evitar duplicados (Se crea solo)
├── data/                  # Carpeta para historiales locales
└── images/                # Carpeta para portadas de playlists (.jpg)


⚙️ Configuración

Para que el bot funcione, necesitas obtener credenciales de Spotify y de Telegram.

1. Spotify Developer (API)

Ve al Spotify Developer Dashboard e inicia sesión.

Haz clic en "Create App".

Dale un nombre (ej: SpotiManager) y una descripción.

En Redirect URI, es CRUCIAL que añadas exactamente esta dirección:
http://127.0.0.1:8888/callback

Guarda los cambios.

En los ajustes de tu App, copia el Client ID y el Client Secret.

2. Telegram Bot (Solo para la versión Bot)

Abre Telegram y busca a @BotFather.

Envía el comando /newbot.

Sigue los pasos y obtén tu HTTP API Token.

Averigua tu propio ID de usuario de Telegram (puedes usar @userinfobot para verlo). Esto es necesario para autorizarte en el script.

3. Configurar los Scripts

Abre los archivos bot_spotibot.py y cli_spotibot.py con un editor de texto y rellena las variables al principio del archivo:

# En bot_spotibot.py y cli_spotibot.py
SPOTIPY_CLIENT_ID = "PEGA_AQUI_TU_CLIENT_ID"
SPOTIPY_CLIENT_SECRET = "PEGA_AQUI_TU_CLIENT_SECRET"
SPOTIPY_REDIRECT_URI = "[http://127.0.0.1:8888/callback](http://127.0.0.1:8888/callback)"

# Solo en bot_spotibot.py
TELEGRAM_TOKEN = "PEGA_AQUI_TU_TOKEN_DE_TELEGRAM"
AUTHORIZED_USER_IDS = {123456789} # Tu chat ID numérico de Telegram


📄 Archivos de Datos

playlists.txt

Este archivo le dice al "Actualizador" qué playlists debe espiar. El formato debe separar la URL y el género por un espacio.
URL_PLAYLIST GENERO

Ejemplo:

[https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M](https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M) ROCK
[https://open.spotify.com/playlist/37i9dQZF1DX0XUsuxWHRQd](https://open.spotify.com/playlist/37i9dQZF1DX0XUsuxWHRQd) HIPHOP


Imágenes (images/)

Si quieres que tus playlists generadas tengan portada, guarda imágenes .jpg en la carpeta images/ con el nombre del género exacto.

Ejemplo: rock.jpg, hiphop.jpg.

🎮 Cómo Usar

Opción A: Versión CLI (Consola)

Ideal para tareas rápidas desde tu ordenador.

Ejecuta el script:

python3 cli_spotibot.py


Autenticación (Primera vez): Si no tienes entorno gráfico, el script te mostrará una URL. Cópiala, ábrela en tu navegador, autoriza y pega la URL de redirección (http://127.0.0.1...) de vuelta en la consola.

Sigue el menú interactivo.

Opción B: Versión Telegram Bot

Para tener el control siempre a mano.

Ejecuta el script:

python3 bot_spotibot.py


Autenticación: Igual que en la versión CLI, la primera vez verificará credenciales por la consola del servidor.

Ve a tu bot en Telegram y envía /start.

Usa el menú interactivo:

/rank: Ver ranking de popularidad.

/mixer: Crear mezclas de playlists.

/updater: Actualizar novedades desde playlists.txt.

/sort: Ordenar una de tus playlists por fama.

/top: Filtrar y dejar solo las mejores canciones de tu playlist.

⚠️ Solución de Problemas

Error "Redirect URI": Asegúrate de que en el Spotify Dashboard has puesto exactamente http://127.0.0.1:8888/callback.

El navegador no carga la página 127.0.0.1: Es normal. Cuando autorizas en Spotify, te redirige a esa dirección local. Aunque veas "No se puede conectar", copia la URL completa de la barra de direcciones y pégala en la terminal.

Permission Denied / Sin Permiso:

En Telegram: Asegúrate de que tu ID está en AUTHORIZED_USER_IDS.

En Spotify (/sort o /top): Asegúrate de que la playlist que intentas editar es tuya (creada por tu cuenta). No puedes editar listas de otros usuarios o de Spotify.

📄 Licencia

Este proyecto es de uso personal y educativo. No está afiliado con Spotify.
