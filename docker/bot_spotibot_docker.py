import logging
import re
import os
import sys
import base64
import datetime
import asyncio
import pandas as pd
from datetime import timedelta
import nest_asyncio

# Telegram Imports
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

# Spotify Imports
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException

# --- CONFIGURACIÓN VÍA VARIABLES DE ENTORNO ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback")

# Procesar IDs autorizados (string "123,456" -> set {123, 456})
auth_ids_str = os.getenv("AUTHORIZED_USER_IDS", "")
try:
    AUTHORIZED_USER_IDS = {int(x.strip()) for x in auth_ids_str.split(",") if x.strip()}
except ValueError:
    print("❌ Error Config: AUTHORIZED_USER_IDS debe ser una lista numérica separada por comas.")
    sys.exit(1)

# Validación de seguridad
if not all([TELEGRAM_TOKEN, SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET]):
    print("❌ Error Fatal: Faltan variables de entorno. Revisa tu docker-compose.yml")
    sys.exit(1)

# --- RUTAS PERSISTENTES (DOCKER VOLUME) ---
# Si existe la carpeta /data (Docker), la usamos. Si no, usamos el directorio actual (Local).
BASE_DIR = "/data" if os.path.isdir("/data") else "."
CACHE_PATH = os.path.join(BASE_DIR, "token_cache.json")
PLAYLISTS_FILE = os.path.join(BASE_DIR, "playlists.txt")
GLOBAL_TRACKS_FILE = os.path.join(BASE_DIR, "global_tracks.txt")
IMAGES_DIR = os.path.join(BASE_DIR, "images")
DATA_DIR_HIST = os.path.join(BASE_DIR, "history") # Subcarpeta para historiales

# Asegurar que existan las carpetas
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(DATA_DIR_HIST, exist_ok=True)

# Scope permisos completos
SCOPE = "playlist-read-private playlist-modify-private ugc-image-upload playlist-modify-public user-library-read"

# --- LOGGING ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- ESTADOS DE LA CONVERSACIÓN ---
(
    CHOOSING_MODE,      
    RANK_URL,           
    RANK_NUMBER,        
    MIXER_INPUT,        
    MIXER_NAME,         
    CREATOR_DAYS,       
    SORT_URL,           
    TOP_URL,            
    TOP_NUMBER          
) = range(9)

# --- GESTIÓN DE AUTENTICACIÓN SPOTIFY ---
sp_global = None
sp_user_id_global = None

def init_spotify_auth():
    global sp_global, sp_user_id_global
    print("\n🔄 [Docker] Conectando con Spotify...")
    
    try:
        auth_manager = SpotifyOAuth(
            client_id=SPOTIPY_CLIENT_ID,
            client_secret=SPOTIPY_CLIENT_SECRET,
            redirect_uri=SPOTIPY_REDIRECT_URI,
            scope=SCOPE,
            cache_path=CACHE_PATH, # Ruta persistente
            open_browser=False
        )
        sp = spotipy.Spotify(auth_manager=auth_manager)
        user = sp.current_user()
        sp_global = sp
        sp_user_id_global = user['id']
        print(f"✅ Autenticación exitosa. Logueado como: {user['display_name']} ({sp_user_id_global})")
        return True

    except Exception as e:
        print("\n⚠️  ATENCIÓN - AUTENTICACIÓN REQUERIDA ⚠️")
        print("El bot necesita permisos de Spotify para funcionar.")
        print("Copia la siguiente URL, autoriza en tu navegador y pega la URL de vuelta aquí.")
        try:
            auth_url = auth_manager.get_authorize_url()
            print(f"🔗 URL DE AUTORIZACIÓN:\n{auth_url}\n")
            # Docker tty interaction
            response = input("👉 Pega aquí la URL de redirección completa: ").strip()
            code = auth_manager.parse_response_code(response)
            auth_manager.get_access_token(code)
            
            sp_global = spotipy.Spotify(auth_manager=auth_manager)
            user = sp_global.current_user()
            sp_user_id_global = user['id']
            print(f"✅ ¡Listo! Token guardado en {CACHE_PATH}")
            return True
        except Exception as err:
            print(f"❌ Error fatal de autenticación: {err}")
            return False

# --- HERRAMIENTAS DE ARCHIVOS ---
def load_txt_set(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_txt_set(path, new_items):
    with open(path, "a", encoding="utf-8") as f:
        for item in new_items:
            f.write(f"{item}\n")

def get_all_tracks_from_playlist(playlist_id):
    tracks = []
    results = sp_global.playlist_items(playlist_id)
    while results:
        for item in results['items']:
            if item.get('track'):
                tracks.append(item['track'])
        results = sp_global.next(results) if results['next'] else None
    return tracks

async def check_auth_telegram(update: Update):
    user_id = update.message.from_user.id
    if user_id not in AUTHORIZED_USER_IDS:
        return False
    return True

def verify_spotify_ownership(playlist_id):
    try:
        pl_details = sp_global.playlist(playlist_id)
        owner_id = pl_details['owner']['id']
        if owner_id != sp_user_id_global:
            return False, f"⛔ **Error de Permisos**\nEsta playlist es de `{owner_id}`. Solo puedes editar las tuyas."
        return True, None
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

async def finish_task(update: Update):
    await update.message.reply_text("✨ **¡Hecho!**\n👉 Para lanzar un nuevo comando pulsa /start", parse_mode="Markdown")

# ============================================================================
#   HANDLERS (Lógica Idéntica, adaptada a rutas Docker)
# ============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (
        "🎧 **Panel de Control SpotiBOT (Docker)**\n\n"
        "1️⃣ **Analizar Popularidad** (/rank)\n"
        "2️⃣ **Mezclador de Fiestas** (/mixer)\n"
        "3️⃣ **Escanear Novedades** (/updater)\n"
        "4️⃣ **Reordenar mis Listas** (/sort)\n"
        "5️⃣ **Filtrar Mejores Canciones** (/top)\n\n"
        "❌ Cancelar operación (/cancel)"
    )
    await update.message.reply_markdown(txt)
    return CHOOSING_MODE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operación cancelada. 👉 Para lanzar un nuevo comando pulsa /start")
    return ConversationHandler.END

# --- BOT 1: RANKING ---
async def enter_rank_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 **MODO RANKING**\nEnvíame el enlace de una playlist.")
    return RANK_URL

async def rank_handle_playlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["rank_url"] = update.message.text.strip()
    await update.message.reply_text("🔢 ¿Cuántas canciones quieres ver? (Número o 'all').")
    return RANK_NUMBER

async def rank_handle_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        url = context.user_data.get("rank_url")
        n_str = update.message.text.strip().lower()
        await update.message.reply_text("⏳ Analizando...")
        tracks = get_all_tracks_from_playlist(url)
        tracks.sort(key=lambda x: x['popularity'], reverse=True)
        
        n = len(tracks) if n_str == 'all' else int(n_str)
        top = tracks[:n]
        msg = [f"🏆 **Top {n} Popularidad**"]
        for i, t in enumerate(top):
            msg.append(f"{i+1}. {t['name']} - {t['artists'][0]['name']} ({t['popularity']})")
        
        text = "\n".join(msg)
        for i in range(0, len(text), 4000):
            await update.message.reply_text(text[i:i+4000])
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
    await finish_task(update)
    return ConversationHandler.END

# --- BOT 2: MIXER ---
async def enter_mixer_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth_telegram(update): return ConversationHandler.END
    context.user_data["mixer_mode"] = "normal"
    await update.message.reply_markdown("🍹 **MODO MIXER**\nEnvía enlaces separados por espacio.\nUsa `/modo mix` para intercalar.")
    return MIXER_INPUT

async def mixer_set_mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if "mix" in text:
        context.user_data["mixer_mode"] = "mix"
        await update.message.reply_text("🔀 Modo MIX activado.")
    else:
        context.user_data["mixer_mode"] = "normal"
        await update.message.reply_text("➡️ Modo NORMAL activado.")
    return MIXER_INPUT

async def mixer_process_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower().startswith("/modo"):
        # Reutilizamos la lógica del comando si el usuario lo escribe a mano
        return await mixer_set_mode_command(update, context)

    pids = [p.split("playlist/")[1].split("?")[0] for p in text.split() if "playlist/" in p]
    if len(pids) < 2:
        await update.message.reply_text("⚠️ Necesito al menos 2 enlaces.")
        return MIXER_INPUT

    context.user_data["mixer_pids"] = pids
    await update.message.reply_text("📝 ¿Qué nombre le ponemos a la playlist?")
    return MIXER_NAME

async def mixer_process_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    pids = context.user_data.get("mixer_pids", [])
    mode = context.user_data.get("mixer_mode", "normal")
    await update.message.reply_text(f"🍹 Creando '{name}'...")

    try:
        tracks_lists = []
        for pid in pids:
            tracks = get_all_tracks_from_playlist(pid)
            tracks_lists.append([t['uri'] for t in tracks])
            
        final_uris = []
        if mode == 'mix':
            max_len = max(len(l) for l in tracks_lists)
            for i in range(max_len):
                for l in tracks_lists:
                    if i < len(l) and l[i] not in final_uris: final_uris.append(l[i])
        else:
            seen = set()
            for l in tracks_lists:
                for u in l:
                    if u not in seen:
                        final_uris.append(u)
                        seen.add(u)

        if not final_uris:
            await update.message.reply_text("❌ No se encontraron canciones.")
            return ConversationHandler.END

        new_pl = sp_global.user_playlist_create(sp_user_id_global, name, public=False)
        for i in range(0, len(final_uris), 100):
            sp_global.playlist_add_items(new_pl['id'], final_uris[i:i+100])
        await update.message.reply_text(f"✅ Playlist creada:\n{new_pl['external_urls']['spotify']}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
    await finish_task(update)
    return ConversationHandler.END

# --- BOT 3: UPDATER (Dockerized) ---
async def enter_creator_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth_telegram(update): return ConversationHandler.END
    
    if not os.path.exists(PLAYLISTS_FILE):
        await update.message.reply_text(f"⚠️ Error: No encuentro `{PLAYLISTS_FILE}`. Verifica tu volumen de Docker.")
        return ConversationHandler.END

    await update.message.reply_text("🆕 **MODO ACTUALIZADOR**\n¿De cuántos días atrás busco novedades?")
    return CREATOR_DAYS

async def creator_process_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        days = int(update.message.text.strip())
        if days <= 0: days = 7
    except: days = 7
    
    await update.message.reply_text(f"🚀 Buscando novedades (últimos {days} días)...")
    msg_log = ""
    
    try:
        playlists_map = {}
        with open(PLAYLISTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(" ")
                if len(parts) < 2: continue
                url, genre = parts[0], parts[1]
                if "playlist/" in url:
                    pid = url.split("playlist/")[1].split("?")[0]
                    genre = genre.replace("&", "AND").replace("_", " ").upper()
                    if genre not in playlists_map: playlists_map[genre] = []
                    playlists_map[genre].append(pid)
        
        global_tracks = load_txt_set(GLOBAL_TRACKS_FILE)

        for genre, pids in playlists_map.items():
            target_name = f"{genre} {datetime.date.today().year}"
            target_id = None
            user_pls = sp_global.current_user_playlists(limit=50)
            for pl in user_pls['items']:
                if pl['name'] == target_name:
                    target_id = pl['id']; break
            
            if not target_id:
                new_pl = sp_global.user_playlist_create(sp_user_id_global, target_name, public=False, description=f"Auto-gen: {genre}")
                target_id = new_pl['id']
                # Buscar imagen en carpeta persistente
                img_path = os.path.join(IMAGES_DIR, f"{genre.lower().replace(' ', '_')}.jpg")
                if os.path.exists(img_path):
                    try:
                        with open(img_path, "rb") as img:
                            sp_global.playlist_upload_cover_image(target_id, base64.b64encode(img.read()))
                    except: pass

            tracks_to_add = []
            cutoff = datetime.datetime.now(datetime.timezone.utc) - timedelta(days=days)
            
            for pid in pids:
                # Historial en subcarpeta persistente
                local_hist_path = os.path.join(DATA_DIR_HIST, f"{pid}_tracks.txt")
                local_hist = load_txt_set(local_hist_path)
                new_local_items = []
                try:
                    res = sp_global.playlist_items(pid)
                    while res:
                        for item in res['items']:
                            if not item.get('track'): continue
                            tid = item['track']['id']; turi = item['track']['uri']
                            try:
                                added = datetime.datetime.strptime(item['added_at'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)
                                if added >= cutoff:
                                    if tid not in local_hist and tid not in global_tracks:
                                        tracks_to_add.append(turi)
                                        global_tracks.add(tid)
                                        new_local_items.append(tid)
                            except: pass
                        res = sp_global.next(res) if res['next'] else None
                    if new_local_items: save_txt_set(local_hist_path, new_local_items)
                except Exception as e: logger.warning(f"Error {pid}: {e}")

            if tracks_to_add:
                unique_uris = list(set(tracks_to_add))
                for i in range(0, len(unique_uris), 100):
                    sp_global.playlist_add_items(target_id, unique_uris[i:i+100])
                new_ids = [u.split(":")[-1] for u in unique_uris]
                save_txt_set(GLOBAL_TRACKS_FILE, new_ids)
                msg_log += f"✅ {genre}: +{len(unique_uris)}\n"
            else:
                msg_log += f"💤 {genre}: 0\n"

        await update.message.reply_text(f"🏁 **Resumen:**\n{msg_log}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

    await finish_task(update)
    return ConversationHandler.END

# --- BOT 4: SORT ---
async def enter_sort_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth_telegram(update): return ConversationHandler.END
    await update.message.reply_text("⚠️ **MODO ORDENAR**\nEsto modificará el orden de tu playlist.\nEnvíame el enlace:")
    return SORT_URL

async def process_sort_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    try:
        pid = url.split("playlist/")[1].split("?")[0]
        is_owner, err = verify_spotify_ownership(pid)
        if not is_owner:
            await update.message.reply_markdown(err); return ConversationHandler.END

        await update.message.reply_text("⏳ Ordenando...")
        tracks = get_all_tracks_from_playlist(pid)
        if not tracks:
            await update.message.reply_text("❌ Vacía."); return ConversationHandler.END

        tracks.sort(key=lambda x: x['popularity'], reverse=True)
        uris = [t['uri'] for t in tracks]

        sp_global.playlist_replace_items(pid, uris[:100])
        if len(uris) > 100:
            for i in range(100, len(uris), 100):
                sp_global.playlist_add_items(pid, uris[i:i+100])
        await update.message.reply_text(f"✅ Hecho. {len(uris)} canciones ordenadas.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
    await finish_task(update)
    return ConversationHandler.END

# --- BOT 5: TOP FILTER ---
async def enter_top_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth_telegram(update): return ConversationHandler.END
    await update.message.reply_text("✂️ **MODO TOP FILTER**\nMe quedaré con las mejores y borraré el resto.\nEnvíame el enlace:")
    return TOP_URL

async def process_top_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["top_url"] = update.message.text.strip()
    await update.message.reply_text("🔢 ¿Con cuántas te quieres quedar? (Ej: 50)")
    return TOP_NUMBER

async def process_top_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = int(update.message.text.strip())
        url = context.user_data["top_url"]
        pid = url.split("playlist/")[1].split("?")[0]
        is_owner, err = verify_spotify_ownership(pid)
        if not is_owner:
            await update.message.reply_markdown(err); return ConversationHandler.END

        await update.message.reply_text(f"⏳ Filtrando Top {n}...")
        tracks = get_all_tracks_from_playlist(pid)
        tracks.sort(key=lambda x: x['popularity'], reverse=True)
        uris = [t['uri'] for t in tracks[:n]]
        
        sp_global.playlist_replace_items(pid, uris[:100])
        if len(uris) > 100:
            for i in range(100, len(uris), 100):
                sp_global.playlist_add_items(pid, uris[i:i+100])
        await update.message.reply_text(f"✅ Listo. Playlist reducida a {len(uris)} canciones.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
    await finish_task(update)
    return ConversationHandler.END

# ============================================================================
#   MAIN
# ============================================================================
def main():
    if not init_spotify_auth():
        print("❌ Error Auth")
        return

    nest_asyncio.apply()
    print("🤖 Iniciando Bot (Docker Mode)...")
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    entry_points = [
        CommandHandler("start", start),
        CommandHandler("rank", enter_rank_mode),
        CommandHandler("mixer", enter_mixer_mode),
        CommandHandler("updater", enter_creator_mode),
        CommandHandler("sort", enter_sort_mode),
        CommandHandler("top", enter_top_mode)
    ]

    conv_handler = ConversationHandler(
        entry_points=entry_points,
        states={
            CHOOSING_MODE: entry_points,
            RANK_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, rank_handle_playlist)],
            RANK_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, rank_handle_number)],
            MIXER_INPUT: [
                CommandHandler("modo", mixer_set_mode_command),
                MessageHandler(filters.TEXT & ~filters.COMMAND, mixer_process_input)
            ],
            MIXER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, mixer_process_name)],
            CREATOR_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, creator_process_days)],
            SORT_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_sort_url)],
            TOP_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_top_url)],
            TOP_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_top_number)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)]
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == "__main__":
    main()
