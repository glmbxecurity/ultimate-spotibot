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
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials

# --- CONFIGURACIÓN (EDITAR AQUÍ) ---
TELEGRAM_TOKEN = "PON_AQUI_TU_TOKEN_DE_TELEGRAM"

SPOTIPY_CLIENT_ID = "d03aa02f8eee4816ad49125646d00260"
SPOTIPY_CLIENT_SECRET = "32ef80a08b8b475198d06ee284d5d245"
SPOTIPY_REDIRECT_URI = "http://127.0.0.1:8888/callback"

# IDs de Telegram autorizados (para funciones de escritura como mixer/creator)
# Sustituye estos números por tu ID de Telegram (puedes verlo con @userinfobot)
AUTHORIZED_USER_IDS = {942135888, 123456789}

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
    CHOOSING_MODE,      # Menú Principal
    RANK_URL,           # Bot 1: Esperando URL
    RANK_NUMBER,        # Bot 1: Esperando número
    MIXER_INPUT,        # Bot 2: Esperando links
    CREATOR_DAYS        # Bot 3: Esperando días
) = range(5)

# --- GESTIÓN DE AUTENTICACIÓN SPOTIFY ---
# Variable global para el cliente de Spotify
sp_global = None
sp_user_id_global = None

def init_spotify_auth():
    """
    Realiza la autenticación inicial en la consola del servidor.
    Si no hay token, detiene el flujo hasta que el usuario lo pegue en la consola.
    """
    global sp_global, sp_user_id_global
    print("\n🔄 Conectando con Spotify...")
    
    try:
        auth_manager = SpotifyOAuth(
            client_id=SPOTIPY_CLIENT_ID,
            client_secret=SPOTIPY_CLIENT_SECRET,
            redirect_uri=SPOTIPY_REDIRECT_URI,
            scope=SCOPE,
            cache_path="token_cache.json",
            open_browser=False  # Importante para servidores sin GUI
        )
        
        # Creamos el cliente. Si no hay token válido, spotipy intentará usar input()
        # pero a veces es mejor forzar el flujo manual si falla.
        sp = spotipy.Spotify(auth_manager=auth_manager)
        
        # Intentamos una llamada simple para verificar o disparar el auth flow
        user = sp.current_user()
        
        sp_global = sp
        sp_user_id_global = user['id']
        print(f"✅ Autenticación exitosa. Logueado como: {user['display_name']} ({sp_user_id_global})")
        return True

    except Exception as e:
        print("\n⚠️  ATENCIÓN - AUTENTICACIÓN REQUERIDA ⚠️")
        print("El bot necesita permisos de Spotify para funcionar.")
        print("1. Copia la URL que aparecerá (o se ha impreso arriba en el error).")
        print("2. Pégala en tu navegador y autoriza.")
        print("3. Copia la URL a la que te redirige (localhost/127.0.0.1...) y pégala aquí abajo.")
        print("-" * 60)
        # Si spotipy no disparó el input automáticamente, lo hacemos manualmente:
        try:
            auth_url = auth_manager.get_authorize_url()
            print(f"🔗 URL DE AUTORIZACIÓN:\n{auth_url}\n")
            response = input("👉 Pega aquí la URL de redirección completa: ").strip()
            code = auth_manager.parse_response_code(response)
            auth_manager.get_access_token(code)
            
            # Reintentamos conectar
            sp_global = spotipy.Spotify(auth_manager=auth_manager)
            user = sp_global.current_user()
            sp_user_id_global = user['id']
            print(f"✅ ¡Listo! Logueado como: {user['display_name']}")
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
    os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
    with open(path, "a", encoding="utf-8") as f:
        for item in new_items:
            f.write(f"{item}\n")

# ============================================================================
#   LÓGICA DEL MENÚ PRINCIPAL DE TELEGRAM
# ============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (
        "🎵 **Bienvenido al Super SpotiBOT** 🎵\n\n"
        "Selecciona una herramienta:\n\n"
        "1️⃣ /rank - Rankear canciones (Popularidad)\n"
        "2️⃣ /mixer - Mezclar varias playlists\n"
        "3️⃣ /create_update_playlist - Actualizar novedades por género\n\n"
        "❌ /cancel - Detener operación actual"
    )
    await update.message.reply_markdown(txt)
    return CHOOSING_MODE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operación cancelada. Escribe /start para volver al menú.")
    return ConversationHandler.END

def check_auth_telegram(user_id):
    if user_id not in AUTHORIZED_USER_IDS:
        return False
    return True

# ============================================================================
#   BOT 1: RANKING
# ============================================================================

async def enter_rank_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 **MODO RANKING**\n"
        "Envíame el enlace de la playlist de Spotify que quieres analizar."
    )
    return RANK_URL

async def rank_handle_playlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not "spotify.com" in url and len(url) < 10:
        await update.message.reply_text("❌ Eso no parece un enlace válido. Intenta de nuevo o /cancel.")
        return RANK_URL

    context.user_data["rank_url"] = url
    await update.message.reply_text("🔢 ¿Cuántas canciones quieres ver en el top? (Escribe un número o 'all').")
    return RANK_NUMBER

async def rank_handle_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip().lower()
    url = context.user_data.get("rank_url")
    
    await update.message.reply_text("⏳ Procesando ranking...")

    try:
        # Usamos el cliente global autenticado
        results = sp_global.playlist_items(url, additional_types=["track"])
        tracks = results["items"]
        while results["next"]:
            results = sp_global.next(results)
            tracks.extend(results["items"])
        
        data_list = []
        for item in tracks:
            if item.get("track"):
                t = item["track"]
                data_list.append({
                    "track_name": t["name"],
                    "popularity": t["popularity"],
                    "artist": t["artists"][0]["name"]
                })

        df = pd.DataFrame(data_list).sort_values(by="popularity", ascending=False)
        
        if user_input == "all":
            n = len(df)
        else:
            try:
                n = int(user_input)
            except:
                await update.message.reply_text("❌ Número inválido. Escribe un número o 'all'.")
                return RANK_NUMBER

        top_tracks = df.head(n)
        msg_lines = [f"🏆 **Top {n} Popularidad**"]
        for i, row in top_tracks.iterrows():
            msg_lines.append(f"{i+1}. {row['track_name']} - {row['artist']} ({row['popularity']})")

        # Enviar en trozos si es muy largo
        full_msg = "\n".join(msg_lines)
        if len(full_msg) > 4000:
            for i in range(0, len(msg_lines), 40):
                chunk = "\n".join(msg_lines[i:i+40])
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(full_msg)

    except Exception as e:
        logger.error(e)
        await update.message.reply_text(f"❌ Error: {str(e)}")

    await update.message.reply_text("\n✅ Ranking finalizado. Usa /start para volver al menú.")
    return ConversationHandler.END

# ============================================================================
#   BOT 2: PARTY MIXER
# ============================================================================

async def enter_mixer_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth_telegram(update.message.from_user.id):
        await update.message.reply_text("⛔ No tienes permiso para usar funciones de escritura.")
        return ConversationHandler.END

    context.user_data["mixer_mode"] = "normal" # Default
    msg = (
        "🍹 **MODO MIXER**\n"
        "Envía 2 o más URLs de playlists separadas por espacio.\n\n"
        "⚙️ Configuración actual: `Modo Normal` (una tras otra)\n"
        "Si quieres cambiar a intercalado, escribe `/modo mix` antes de enviar los links."
    )
    await update.message.reply_markdown(msg)
    return MIXER_INPUT

async def mixer_set_mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if args and args[0].lower() == 'mix':
        context.user_data["mixer_mode"] = "mix"
        await update.message.reply_text("🔀 Modo cambiado a: **MIX** (Intercalado). Ahora envía los links.")
    else:
        context.user_data["mixer_mode"] = "normal"
        await update.message.reply_text("➡️ Modo cambiado a: **NORMAL** (Secuencial). Ahora envía los links.")
    return MIXER_INPUT

async def mixer_process_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # Capturar comando /modo si el usuario lo escribe sin hacer click
    if text.lower().startswith("/modo"):
        if "mix" in text.lower():
            context.user_data["mixer_mode"] = "mix"
            await update.message.reply_text("🔀 Modo Mix activado.")
        else:
            context.user_data["mixer_mode"] = "normal"
            await update.message.reply_text("➡️ Modo Normal activado.")
        return MIXER_INPUT

    playlist_ids = []
    for part in text.split():
        if "playlist/" in part:
            try:
                pid = part.split("playlist/")[1].split("?")[0]
                playlist_ids.append(pid)
            except: pass
        elif len(part) > 10: 
            playlist_ids.append(part)

    if len(playlist_ids) < 2:
        await update.message.reply_text("⚠️ Necesito al menos 2 playlists válidas separadas por espacio.")
        return MIXER_INPUT

    await update.message.reply_text("🍹 Mezclando... espera un momento.")

    try:
        playlist_tracks_lists = []
        for pid in playlist_ids:
            tracks = []
            res = sp_global.playlist_items(pid)
            while res:
                for item in res['items']:
                    if item.get('track') and item['track'].get('uri'):
                        tracks.append(item['track']['uri'])
                res = sp_global.next(res) if res['next'] else None
            playlist_tracks_lists.append(tracks)

        final_uris = []
        mode = context.user_data.get("mixer_mode", "normal")
        
        if mode == 'mix':
            max_len = max(len(pl) for pl in playlist_tracks_lists)
            for i in range(max_len):
                for pl in playlist_tracks_lists:
                    if i < len(pl):
                        if pl[i] not in final_uris:
                            final_uris.append(pl[i])
        else:
            seen = set()
            for pl in playlist_tracks_lists:
                for uri in pl:
                    if uri not in seen:
                        final_uris.append(uri)
                        seen.add(uri)

        if not final_uris:
            await update.message.reply_text("❌ No se encontraron canciones.")
            return ConversationHandler.END

        new_name = f"Mixer {mode.upper()} - {datetime.datetime.now().strftime('%d/%m %H:%M')}"
        new_playlist = sp_global.user_playlist_create(sp_user_id_global, new_name, public=False, description="Created via Super SpotiBot Telegram")
        
        # Añadir en lotes
        for i in range(0, len(final_uris), 100):
            sp_global.playlist_add_items(new_playlist['id'], final_uris[i:i+100])

        await update.message.reply_text(f"✅ ¡Listo! Playlist creada:\n{new_playlist['external_urls']['spotify']}")

    except Exception as e:
        logger.error(e)
        await update.message.reply_text(f"❌ Error: {e}")

    return ConversationHandler.END

# ============================================================================
#   BOT 3: CREATOR/UPDATER
# ============================================================================

async def enter_creator_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth_telegram(update.message.from_user.id):
        await update.message.reply_text("⛔ No tienes permiso.")
        return ConversationHandler.END
    
    if not os.path.exists("playlists.txt"):
        await update.message.reply_text("⚠️ Error: No encuentro el archivo 'playlists.txt' en el servidor.")
        return ConversationHandler.END

    await update.message.reply_text(
        "🆕 **MODO ACTUALIZADOR**\n"
        "Actualizaré tus playlists basadas en 'playlists.txt'.\n"
        "¿De cuántos días atrás quieres buscar novedades? (Ej: 7)"
    )
    return CREATOR_DAYS

async def creator_process_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        days = int(update.message.text.strip())
        if days <= 0: days = 7
    except ValueError:
        days = 7
    
    await update.message.reply_text(f"🚀 Iniciando actualización (Días: {days}). Esto puede tardar...")

    msg_log = ""
    try:
        # Cargar playlists
        playlists_map = {}
        with open("playlists.txt", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(" ")
                if len(parts) < 2: continue
                url, genre = parts[0], parts[1]
                if "playlist/" in url:
                    pid = url.split("playlist/")[1].split("?")[0]
                    genre = genre.replace("&", "AND").replace("_", " ").upper()
                    if genre not in playlists_map: playlists_map[genre] = []
                    playlists_map[genre].append(pid)

        global_tracks = load_txt_set("global_tracks.txt")
        
        for genre, pids in playlists_map.items():
            # 1. Buscar/Crear Playlist Destino
            target_name = f"{genre} {datetime.date.today().year}"
            target_id = None
            
            # Búsqueda simplificada
            user_pls = sp_global.current_user_playlists(limit=50)
            for pl in user_pls['items']:
                if pl['name'] == target_name:
                    target_id = pl['id']
                    break
            
            if not target_id:
                new_pl = sp_global.user_playlist_create(sp_user_id_global, target_name, public=False, description=f"Auto-gen: {genre}")
                target_id = new_pl['id']
                # Imagen
                img_path = f"images/{genre.lower().replace(' ', '_')}.jpg"
                if os.path.exists(img_path):
                    try:
                        with open(img_path, "rb") as img:
                            sp_global.playlist_upload_cover_image(target_id, base64.b64encode(img.read()))
                    except: pass

            # 2. Procesar canciones
            tracks_to_add = []
            cutoff = datetime.datetime.now(datetime.timezone.utc) - timedelta(days=days)
            
            for pid in pids:
                local_hist_path = f"data/{pid}_tracks.txt"
                local_hist = load_txt_set(local_hist_path)
                new_local_items = []
                
                try:
                    res = sp_global.playlist_items(pid)
                    while res:
                        for item in res['items']:
                            if not item.get('track'): continue
                            tid = item['track']['id']
                            turi = item['track']['uri']
                            try:
                                added = datetime.datetime.strptime(item['added_at'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)
                                if added >= cutoff:
                                    if tid not in local_hist and tid not in global_tracks:
                                        tracks_to_add.append(turi)
                                        global_tracks.add(tid) # Actualizar memoria
                                        new_local_items.append(tid)
                            except: pass
                        res = sp_global.next(res) if res['next'] else None
                    
                    if new_local_items:
                        save_txt_set(local_hist_path, new_local_items)
                        
                except Exception as e:
                    logger.warning(f"Error en playlist {pid}: {e}")

            # 3. Añadir a Spotify
            if tracks_to_add:
                unique_uris = list(set(tracks_to_add))
                for i in range(0, len(unique_uris), 100):
                    sp_global.playlist_add_items(target_id, unique_uris[i:i+100])
                
                # Guardar en global (IDs)
                new_ids = [u.split(":")[-1] for u in unique_uris]
                save_txt_set("global_tracks.txt", new_ids)
                msg_log += f"✅ {genre}: +{len(unique_uris)} canciones.\n"
            else:
                msg_log += f"💤 {genre}: Sin novedades.\n"

        await update.message.reply_text(f"🏁 **Resumen:**\n{msg_log}")

    except Exception as e:
        logger.error(e)
        await update.message.reply_text(f"❌ Error crítico: {str(e)}")

    return ConversationHandler.END

# ============================================================================
#   MAIN EXECUTION
# ============================================================================

def main():
    # 1. Primero asegurar autenticación de Spotify en Consola
    if not init_spotify_auth():
        print("❌ No se pudo autenticar en Spotify. Saliendo...")
        return

    # 2. Iniciar Bot de Telegram
    nest_asyncio.apply()
    print("🤖 Iniciando Bot de Telegram...")
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_MODE: [
                CommandHandler("rank", enter_rank_mode),
                CommandHandler("mixer", enter_mixer_mode),
                CommandHandler("create_update_playlist", enter_creator_mode)
            ],
            RANK_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, rank_handle_playlist)],
            RANK_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, rank_handle_number)],
            MIXER_INPUT: [
                CommandHandler("modo", mixer_set_mode_command),
                MessageHandler(filters.TEXT & ~filters.COMMAND, mixer_process_input)
            ],
            CREATOR_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, creator_process_days)]
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)]
    )

    application.add_handler(conv_handler)
    
    print("🚀 Bot en ejecución. Presiona Ctrl+C para detener.")
    application.run_polling()

if __name__ == "__main__":
    main()
