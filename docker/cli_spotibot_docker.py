import os
import sys
import re
import time
import base64
import datetime
from datetime import timedelta
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# --- CONFIGURACIÓN VÍA VARIABLES DE ENTORNO ---
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback")

if not all([SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET]):
    print("❌ Error Fatal: Faltan variables de entorno en docker-compose.yml")
    sys.exit(1)

# --- RUTAS PERSISTENTES (DOCKER VOLUME) ---
# Usamos /data si existe (Docker), sino local.
BASE_DIR = "/data" if os.path.isdir("/data") else "."
CACHE_PATH = os.path.join(BASE_DIR, "token_cache.json")
PLAYLISTS_FILE = os.path.join(BASE_DIR, "playlists.txt")
GLOBAL_TRACKS_FILE = os.path.join(BASE_DIR, "global_tracks.txt")
IMAGES_DIR = os.path.join(BASE_DIR, "images")
DATA_DIR_HIST = os.path.join(BASE_DIR, "history")

# Asegurar que existan las carpetas necesarias
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(DATA_DIR_HIST, exist_ok=True)

SCOPE = "playlist-read-private playlist-modify-private ugc-image-upload playlist-modify-public user-library-read"

# --- AUTENTICACIÓN ---
def get_spotify_client():
    try:
        auth_manager = SpotifyOAuth(
            client_id=SPOTIPY_CLIENT_ID,
            client_secret=SPOTIPY_CLIENT_SECRET,
            redirect_uri=SPOTIPY_REDIRECT_URI,
            scope=SCOPE,
            cache_path=CACHE_PATH,
            open_browser=False  
        )
        sp = spotipy.Spotify(auth_manager=auth_manager)
        return sp
    except Exception as e:
        print(f"❌ Error de autenticación: {e}")
        sys.exit()

print("🔄 [Docker CLI] Conectando con Spotify...")
sp = get_spotify_client()
sp_user_id = None

try:
    user_info = sp.current_user()
    sp_user_id = user_info['id']
    print(f"✅ Logueado como: {user_info['display_name']} ({sp_user_id})")
except Exception as e:
    print("\n⚠️  TOKEN INVÁLIDO O INEXISTENTE ⚠️")
    print("Por favor, ejecuta primero el bot de Telegram (docker-compose up) y realiza la autenticación inicial.")
    sys.exit()

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
    """Descarga todos los tracks paginando."""
    tracks = []
    print("   ↳ Leyendo lista...", end="", flush=True)
    try:
        results = sp.playlist_items(playlist_id)
        while results:
            print(".", end="", flush=True)
            for item in results['items']:
                if item.get('track'):
                    tracks.append(item['track'])
            results = sp.next(results) if results['next'] else None
        print(" OK")
    except Exception as e:
        print(f"\n❌ Error leyendo playlist: {e}")
    return tracks

def verify_ownership(playlist_id):
    try:
        pl = sp.playlist(playlist_id)
        if pl['owner']['id'] != sp_user_id:
            print(f"\n⛔ PERMISO DENEGADO: Esta playlist pertenece a '{pl['owner']['id']}'.")
            print("   Solo puedes modificar playlists creadas por ti mismo.")
            return False
        return True
    except:
        print("❌ No se pudo verificar la propiedad de la playlist.")
        return False

# ==========================================
# 1. RANKING
# ==========================================
def feature_ranking():
    print("\n" + "="*50)
    print("📊 MODO RANKING DE POPULARIDAD")
    print("="*50)
    print("Este modo analiza una playlist (tuya o de otro) y muestra")
    print("las canciones ordenadas por su índice de popularidad actual.")
    
    url = input("\n👉 Pega el enlace de la playlist: ").strip()
    if "spotify.com" not in url and len(url) < 10:
        print("❌ URL inválida.")
        return

    try:
        tracks = get_all_tracks_from_playlist(url)
        # Ordenar por popularidad descendente
        tracks.sort(key=lambda x: x['popularity'], reverse=True)
        
        lim_input = input("👉 ¿Cuántas canciones quieres ver? (Escribe un número o 'all'): ").strip().lower()
        n = len(tracks) if lim_input == 'all' else int(lim_input)
        
        print(f"\n🏆 --- TOP {n} CANCIONES MÁS POPULARES ---")
        for i, t in enumerate(tracks[:n]):
            print(f"{i+1}. {t['name']} - {t['artists'][0]['name']} (Pop: {t['popularity']})")
            
        input("\n✅ Pulsa Enter para volver al menú...")

    except ValueError:
        print("❌ Debes introducir un número válido.")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")

# ==========================================
# 2. MIXER
# ==========================================
def feature_mixer():
    print("\n" + "="*50)
    print("🍹 PARTY MIXER (MEZCLADOR)")
    print("="*50)
    print("Combina múltiples playlists en una sola.")
    print("Puedes elegir entre:")
    print("  1. MODO NORMAL: Añade las listas una detrás de otra.")
    print("  2. MODO MIX: Intercala canciones (1 de A, 1 de B, 1 de A...).")
    
    urls_input = input("\n👉 Pega las URLs separadas por ESPACIO: ").strip()
    pids = [u.split("playlist/")[1].split("?")[0] for u in urls_input.split() if "playlist" in u]
    
    if len(pids) < 2:
        print("⚠️ Necesitas al menos 2 playlists para mezclar.")
        return
    
    mode = input("👉 Elige modo (1=Normal, 2=Mix): ").strip()
    name = input("👉 Nombre para la nueva playlist: ").strip()
    if not name: name = f"Mixer {datetime.date.today()}"
    
    print(f"\n⏳ Descargando {len(pids)} playlists...")
    lists = []
    for pid in pids:
        tracks = get_all_tracks_from_playlist(pid)
        uris = [t['uri'] for t in tracks]
        lists.append(uris)
    
    final_uris = []
    if mode == "2":
        print("🔀 Mezclando en modo MIX...")
        max_len = max(len(l) for l in lists)
        for i in range(max_len):
            for l in lists:
                if i < len(l) and l[i] not in final_uris:
                    final_uris.append(l[i])
    else:
        print("➡️ Uniendo en modo NORMAL...")
        seen = set()
        for l in lists:
            for u in l:
                if u not in seen:
                    final_uris.append(u)
                    seen.add(u)
    
    if not final_uris:
        print("❌ No se encontraron canciones válidas.")
        return

    try:
        print(f"💾 Creando playlist '{name}' con {len(final_uris)} canciones...")
        pl = sp.user_playlist_create(sp_user_id, name, public=False, description="Created with Ultimate SpotiBOT CLI")
        
        # Subir en lotes de 100
        for i in range(0, len(final_uris), 100):
            sp.playlist_add_items(pl['id'], final_uris[i:i+100])
            print(f"   ...Lote {i//100 + 1} subido")
            
        print(f"\n✅ ¡ÉXITO! Playlist disponible en:\n{pl['external_urls']['spotify']}")
        input("\nPulsa Enter para continuar...")
        
    except Exception as e: 
        print(f"❌ Error creando playlist: {e}")

# ==========================================
# 3. UPDATER
# ==========================================
def feature_updater():
    print("\n" + "="*50)
    print("🆕 ACTUALIZADOR AUTOMÁTICO")
    print("="*50)
    print(f"Este módulo busca canciones nuevas en las listas de '{PLAYLISTS_FILE}'.")
    print("Las canciones nuevas se añadirán a tus playlists personales por género.")
    
    if not os.path.exists(PLAYLISTS_FILE):
        print(f"\n❌ Error: No se encuentra el archivo {PLAYLISTS_FILE}")
        print("Asegúrate de haberlo creado en tu carpeta 'data'.")
        return

    try:
        days_input = input("\n👉 ¿Cuántos días atrás quieres buscar? (Enter = 7): ").strip()
        days = int(days_input) if days_input else 7
    except:
        days = 7
        
    print(f"\n🚀 Iniciando escaneo (Últimos {days} días)...")
    
    # Cargar Playlists
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
    cutoff_date = datetime.datetime.now(datetime.timezone.utc) - timedelta(days=days)

    for genre, pids in playlists_map.items():
        print(f"\n📂 Procesando Género: {genre}")
        
        # 1. Buscar/Crear Playlist Destino
        target_name = f"{genre} {datetime.date.today().year}"
        target_id = None
        
        user_pls = sp.current_user_playlists(limit=50)
        for pl in user_pls['items']:
            if pl['name'] == target_name:
                target_id = pl['id']
                break
        
        if not target_id:
            print(f"   ✨ Creando nueva playlist: {target_name}")
            new_pl = sp.user_playlist_create(sp_user_id, target_name, public=False, description=f"Auto-generated: {genre}")
            target_id = new_pl['id']
            # Imagen
            img_path = os.path.join(IMAGES_DIR, f"{genre.lower().replace(' ', '_')}.jpg")
            if os.path.exists(img_path):
                try:
                    with open(img_path, "rb") as img:
                        sp.playlist_upload_cover_image(target_id, base64.b64encode(img.read()))
                except: pass

        tracks_to_add = []
        
        for pid in pids:
            # Historial local
            local_hist_path = os.path.join(DATA_DIR_HIST, f"{pid}_tracks.txt")
            local_hist = load_txt_set(local_hist_path)
            new_local_items = []

            try:
                # Paginación manual para obtener 'added_at'
                results = sp.playlist_items(pid)
                while results:
                    for item in results['items']:
                        if not item.get('track'): continue
                        tid = item['track']['id']
                        turi = item['track']['uri']
                        
                        try:
                            added_at = datetime.datetime.strptime(item['added_at'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)
                            if added_at >= cutoff_date:
                                if tid not in local_hist and tid not in global_tracks:
                                    tracks_to_add.append(turi)
                                    global_tracks.add(tid)
                                    new_local_items.append(tid)
                        except: pass # Si falla la fecha ignoramos
                    
                    results = sp.next(results) if results['next'] else None
                
                if new_local_items:
                    save_txt_set(local_hist_path, new_local_items)

            except Exception as e:
                print(f"   ⚠️ Error leyendo fuente {pid}: {e}")

        if tracks_to_add:
            unique_uris = list(set(tracks_to_add))
            print(f"   🔥 ¡Encontradas {len(unique_uris)} canciones nuevas!")
            for i in range(0, len(unique_uris), 100):
                sp.playlist_add_items(target_id, unique_uris[i:i+100])
            
            # Guardar en global
            new_ids = [u.split(":")[-1] for u in unique_uris]
            save_txt_set(GLOBAL_TRACKS_FILE, new_ids)
        else:
            print("   💤 Sin novedades recientes.")
            
    input("\n✅ Proceso finalizado. Pulsa Enter...")

# ==========================================
# 4. SORT
# ==========================================
def feature_sort():
    print("\n" + "="*50)
    print("⚠️  ORDENAR PLAYLIST (SORT)")
    print("="*50)
    print("Este comando reordenará una playlist TUYA de mayor a menor popularidad.")
    print("❗ ATENCIÓN: Esto sobrescribirá el orden original de las canciones.")
    
    url = input("\n👉 URL de la playlist: ").strip()
    try:
        pid = url.split("playlist/")[1].split("?")[0]
    except:
        print("❌ URL inválida.")
        return

    if not verify_ownership(pid): return

    print("⏳ Descargando y analizando...")
    tracks = get_all_tracks_from_playlist(pid)
    if not tracks:
        print("❌ Playlist vacía.")
        return
        
    tracks.sort(key=lambda x: x['popularity'], reverse=True)
    uris = [t['uri'] for t in tracks]
    
    print(f"🔄 Reordenando {len(uris)} canciones...")
    try:
        sp.playlist_replace_items(pid, uris[:100])
        if len(uris) > 100:
            for i in range(100, len(uris), 100):
                sp.playlist_add_items(pid, uris[i:i+100])
                print(f"   ...Lote {i//100 + 1}")
        print("✅ ¡Hecho! Playlist ordenada por popularidad.")
        input("\nPulsa Enter para continuar...")
    except Exception as e:
        print(f"❌ Error: {e}")

# ==========================================
# 5. TOP FILTER
# ==========================================
def feature_top():
    print("\n" + "="*50)
    print("✂️  FILTRAR TOP CANCIONES")
    print("="*50)
    print("Este comando mantiene solo las mejores canciones y ELIMINA el resto.")
    print("Ejemplo: Si tienes 100 canciones y pides el Top 10, borrará las 90 peores.")
    
    url = input("\n👉 URL de la playlist: ").strip()
    try:
        pid = url.split("playlist/")[1].split("?")[0]
    except:
        print("❌ URL inválida.")
        return

    if not verify_ownership(pid): return

    try:
        n = int(input("👉 ¿Con cuántas canciones te quieres quedar? (Ej: 50): ").strip())
    except:
        print("❌ Número inválido.")
        return

    print("⏳ Procesando...")
    tracks = get_all_tracks_from_playlist(pid)
    tracks.sort(key=lambda x: x['popularity'], reverse=True)
    
    top_uris = [t['uri'] for t in tracks[:n]]
    
    print(f"🔄 Reduciendo playlist a las {len(top_uris)} mejores...")
    try:
        sp.playlist_replace_items(pid, top_uris[:100])
        if len(top_uris) > 100:
            for i in range(100, len(top_uris), 100):
                sp.playlist_add_items(pid, top_uris[i:i+100])
        print("✅ ¡Hecho! Playlist filtrada.")
        input("\nPulsa Enter para continuar...")
    except Exception as e:
        print(f"❌ Error: {e}")

# ==========================================
# MAIN MENU
# ==========================================
def main():
    while True:
        # Limpiar pantalla (compatible linux/mac/windows)
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print("\n" + "█"*50)
        print("   🎧 ULTIMATE SPOTIBOT CLI (DOCKER) 🎧")
        print("█"*50)
        print("\nSELECCIONA UNA HERRAMIENTA:")
        print("  1️⃣  RANKING: Ver popularidad de canciones")
        print("  2️⃣  MIXER: Fusionar varias playlists")
        print("  3️⃣  UPDATER: Escanear novedades (playlists.txt)")
        print("  4️⃣  SORT: Ordenar mis listas por fama")
        print("  5️⃣  TOP: Filtrar y limpiar mis listas")
        print("  6️⃣  SALIR")
        
        opt = input("\n👉 Elige una opción (1-6): ").strip()

        if opt == "1": feature_ranking()
        elif opt == "2": feature_mixer()
        elif opt == "3": feature_updater()
        elif opt == "4": feature_sort()
        elif opt == "5": feature_top()
        elif opt == "6": 
            print("¡Adiós! 👋")
            break
        else: 
            input("❌ Opción no válida. Pulsa Enter...")

if __name__ == "__main__":
    main()
