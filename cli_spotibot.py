import os
import sys
import re
import time
import base64
import datetime
from datetime import timedelta
import pandas as pd
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# --- CONFIGURACIÓN (EDITAR AQUÍ) ---
SPOTIPY_CLIENT_ID = "d03aa02f8eee4816ad49125646d00260"
SPOTIPY_CLIENT_SECRET = "32ef80a08b8b475198d06ee284d5d245"
# Cambiado a 127.0.0.1 para evitar el warning de deprecated
SPOTIPY_REDIRECT_URI = "http://127.0.0.1:8888/callback" 

# Scope amplio para que funcione todo con una sola autenticación
SCOPE = "playlist-read-private playlist-modify-private ugc-image-upload playlist-modify-public user-library-read"

# --- AUTHENTICATION ---
def get_spotify_client():
    try:
        # open_browser=False es CLAVE para entornos sin GUI (VPS, SSH)
        auth_manager = SpotifyOAuth(
            client_id=SPOTIPY_CLIENT_ID,
            client_secret=SPOTIPY_CLIENT_SECRET,
            redirect_uri=SPOTIPY_REDIRECT_URI,
            scope=SCOPE,
            cache_path="token_cache.json",
            open_browser=False  
        )
        sp = spotipy.Spotify(auth_manager=auth_manager)
        return sp
    except Exception as e:
        print(f"❌ Error de autenticación: {e}")
        sys.exit()

# Intentamos conectar e imprimir instrucciones si falta auth
print("🔄 Conectando con Spotify...")
sp = get_spotify_client()

# Esta llamada forzará el flujo de autenticación si no hay token válido
try:
    user_info = sp.current_user()
    USER_ID = user_info['id']
    print(f"✅ Logueado como: {user_info['display_name']} ({USER_ID})")
except Exception as e:
    print("\n⚠️  SI ES LA PRIMERA VEZ, SIGUE LAS INSTRUCCIONES ARRIBA ⚠️")
    print("Copia la URL que aparece arriba, pégala en tu navegador, autoriza y pega la URL de vuelta aquí.")
    # Si falla aquí es porque el usuario no completó el input que pide spotipy internamente
    sys.exit()

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

# ==========================================
# 1. RANKING
# ==========================================
def feature_ranking():
    print("\n📊 --- RANKING DE PLAYLIST ---")
    url = input("👉 Pega la URL de la playlist: ").strip()
    
    if not "spotify.com" in url and len(url) < 10:
        print("❌ URL no válida.")
        return

    limit_input = input("👉 ¿Cuántas canciones quieres ver? (Número o 'all'): ").strip().lower()
    
    print("⏳ Obteniendo canciones...")
    try:
        results = sp.playlist_items(url, additional_types=["track"])
        tracks = results["items"]
        while results["next"]:
            results = sp.next(results)
            tracks.extend(results["items"])

        data = []
        for item in tracks:
            if item.get("track"):
                t = item["track"]
                data.append({
                    "Nombre": t["name"],
                    "Artista": t["artists"][0]["name"],
                    "Popularidad": t["popularity"]
                })

        df = pd.DataFrame(data).sort_values(by="Popularidad", ascending=False)
        
        if limit_input == "all":
            print(df.to_string(index=False))
        else:
            try:
                n = int(limit_input)
                print(df.head(n).to_string(index=False))
            except:
                print(df.head(10).to_string(index=False))

    except Exception as e:
        print(f"❌ Error: {e}")

# ==========================================
# 2. PARTY MIXER
# ==========================================
def feature_mixer():
    print("\n🍹 --- PARTY MIXER ---")
    print("Introduce las URLs de las playlists separadas por ESPACIO.")
    urls_input = input("👉 URLs: ").strip()
    
    playlist_ids = []
    for part in urls_input.split():
        if "playlist/" in part:
            playlist_ids.append(part.split("playlist/")[1].split("?")[0])
        elif len(part) > 10:
            playlist_ids.append(part)
            
    if len(playlist_ids) < 2:
        print("⚠️ Necesitas al menos 2 playlists.")
        return

    mode = input("👉 ¿Modo mezcla? (1=Normal [Seguidas], 2=Mix [Intercaladas]): ").strip()
    
    all_tracks_lists = []
    print("⏳ Descargando canciones de las fuentes...")
    
    for pid in playlist_ids:
        p_tracks = []
        try:
            res = sp.playlist_items(pid)
            while res:
                for item in res['items']:
                    if item.get('track') and item['track'].get('id'):
                        p_tracks.append(item['track']['uri'])
                res = sp.next(res) if res['next'] else None
            all_tracks_lists.append(p_tracks)
        except Exception as e:
            print(f"⚠️ Error leyendo playlist {pid}: {e}")

    final_uris = []
    if mode == "2": # Mix
        max_len = max(len(l) for l in all_tracks_lists)
        for i in range(max_len):
            for l in all_tracks_lists:
                if i < len(l) and l[i] not in final_uris:
                    final_uris.append(l[i])
        prefix = "Mezcla MIX"
    else: # Normal
        seen = set()
        for l in all_tracks_lists:
            for uri in l:
                if uri not in seen:
                    final_uris.append(uri)
                    seen.add(uri)
        prefix = "Mezcla Normal"

    if not final_uris:
        print("❌ No se encontraron canciones válidas.")
        return

    print(f"💿 Total canciones únicas: {len(final_uris)}")
    name = f"{prefix} - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
    
    try:
        new_pl = sp.user_playlist_create(USER_ID, name, public=False, description="Generada con Python Console Bot")
        # Subir en lotes de 100
        for i in range(0, len(final_uris), 100):
            sp.playlist_add_items(new_pl['id'], final_uris[i:i+100])
            print(f"   ...Subiendo lote {i//100 + 1}")
        print(f"✅ ¡Lista creada! -> {new_pl['external_urls']['spotify']}")
    except Exception as e:
        print(f"❌ Error creando playlist: {e}")

# ==========================================
# 3. CREATOR / UPDATER
# ==========================================
def feature_updater():
    print("\n🆕 --- ACTUALIZADOR DE PLAYLISTS ---")
    print("Este módulo lee 'playlists.txt' y busca novedades.")
    
    try:
        days_str = input("👉 ¿Días de antigüedad para considerar 'novedad'? (Enter = 7): ").strip()
        days = int(days_str) if days_str else 7
    except:
        days = 7

    if not os.path.exists("playlists.txt"):
        print("❌ Error: No existe el archivo 'playlists.txt'.")
        return

    # Cargar playlists
    source_map = {}
    with open("playlists.txt", "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(" ")
            if len(parts) >= 2:
                url, genre = parts[0], parts[1]
                if "playlist/" in url:
                    pid = url.split("playlist/")[1].split("?")[0]
                    genre = genre.replace("&", "AND").replace("_", " ").upper()
                    if genre not in source_map: source_map[genre] = []
                    source_map[genre].append(pid)

    global_tracks = load_txt_set("global_tracks.txt")
    
    print(f"🚀 Iniciando escaneo de {len(source_map)} géneros...")

    for genre, pids in source_map.items():
        print(f"\n📂 Procesando GÉNERO: {genre}")
        
        # 1. Obtener/Crear Playlist Destino
        dest_name = f"{genre} {datetime.date.today().year}"
        dest_id = None
        
        # Busqueda simple en las primeras 50 (mejorar si tienes muchísimas)
        user_pls = sp.current_user_playlists(limit=50)
        for pl in user_pls['items']:
            if pl['name'] == dest_name:
                dest_id = pl['id']
                break
        
        if not dest_id:
            print(f"   Creating new playlist: {dest_name}")
            new_pl = sp.user_playlist_create(USER_ID, dest_name, public=False)
            dest_id = new_pl['id']
            
            # Imagen
            img_path = f"images/{genre.lower().replace(' ', '_')}.jpg"
            if os.path.exists(img_path):
                try:
                    with open(img_path, "rb") as img:
                        sp.playlist_upload_cover_image(dest_id, base64.b64encode(img.read()))
                except Exception as e: print(f"   Error imagen: {e}")

        # 2. Buscar canciones
        tracks_to_add = []
        cutoff = datetime.datetime.now(datetime.timezone.utc) - timedelta(days=days)

        for pid in pids:
            # Historial local
            local_file = f"data/{pid}_tracks.txt"
            local_hist = load_txt_set(local_file)
            new_local_hist = []

            try:
                res = sp.playlist_items(pid)
                while res:
                    for item in res['items']:
                        if not item.get('track'): continue
                        tid = item['track']['id']
                        turi = item['track']['uri']
                        
                        # Filtro fecha
                        try:
                            added = datetime.datetime.strptime(item['added_at'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)
                        except:
                            continue # Si no tiene fecha, ignorar

                        if added >= cutoff:
                            if tid not in local_hist and tid not in global_tracks:
                                tracks_to_add.append(turi)
                                global_tracks.add(tid)
                                new_local_hist.append(tid)
                    
                    res = sp.next(res) if res['next'] else None
                
                if new_local_hist:
                    save_txt_set(local_file, new_local_hist)

            except Exception as e:
                print(f"   Error leyendo fuente {pid}: {e}")

        # 3. Guardar cambios
        if tracks_to_add:
            unique_uris = list(set(tracks_to_add))
            print(f"   🔥 Agregando {len(unique_uris)} canciones nuevas...")
            for i in range(0, len(unique_uris), 100):
                sp.playlist_add_items(dest_id, unique_uris[i:i+100])
            
            # Guardar IDs en global (extraemos ID de URI)
            new_ids = [u.split(":")[-1] for u in unique_uris]
            save_txt_set("global_tracks.txt", new_ids)
        else:
            print("   💤 Sin novedades.")

# ==========================================
# MAIN MENU
# ==========================================
def main():
    while True:
        print("\n" + "="*30)
        print("   🎧 EDDYGALAMBA's SPOTIFY CLI TOOL 🎧")
        print("="*30)
        print("1. 📊 Ranking de Popularidad")
        print("2. 🍹 Party Mixer (Mezclador)")
        print("3. 🆕 Actualizador Automático")
        print("4. 🚪 Salir")
        
        opt = input("\n👉 Elige una opción: ").strip()

        if opt == "1":
            feature_ranking()
        elif opt == "2":
            feature_mixer()
        elif opt == "3":
            feature_updater()
        elif opt == "4":
            print("¡Adiós! 👋")
            break
        else:
            print("Opción no válida.")
        
        input("\nPresiona ENTER para volver al menú...")

if __name__ == "__main__":
    # Pequeño hack para limpiar pantalla al inicio
    os.system('cls' if os.name == 'nt' else 'clear')
    main()
