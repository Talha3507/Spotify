import os
from flask import Flask, redirect, request, session, render_template, jsonify
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()

print("REDIRECT_URI =", os.getenv("REDIRECT_URI"))

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

sp_oauth = SpotifyOAuth(
    client_id=os.getenv("CLIENT_ID"),
    client_secret=os.getenv("CLIENT_SECRET"),
    redirect_uri=os.getenv("REDIRECT_URI"),
    scope = "user-top-read user-read-private user-read-recently-played user-read-currently-playing user-read-playback-state user-modify-playback-state user-follow-read playlist-read-private playlist-read-collaborative",
    show_dialog=True,
    cache_path=None
)

def get_spotify_client():
    token_info = session.get("token_info")
    if not token_info:
        return None

    # Token süresini kontrol et ve gerekirse yenile
    if sp_oauth.is_token_expired(token_info):
        token_info = sp_oauth.refresh_access_token(token_info["refresh_token"])
        session["token_info"] = token_info

    sp = spotipy.Spotify(auth=token_info["access_token"])
    return sp

def get_profile(sp):
    user = sp.current_user()
    return {
        "name": user.get("display_name", "Spotify User"),
        "image": user["images"][0]["url"] if user.get("images") else None,
        "product": user.get("product", "free")
    }
        
@app.route("/login")
def login():
    auth_url = sp_oauth.get_authorize_url()
    print("MOBIL AUTH URL:", auth_url)
    return redirect(auth_url)

@app.route("/")
def home():
    return render_template("index.html")

##@app.route("/following")
##def following():
##    return "OK FOLLOWING"

@app.route("/following")
def following():
    sp = get_spotify_client()
    if sp is None:
        return redirect("/login")

    profile = get_profile(sp)

    following_artists = []
    results = sp.current_user_followed_artists(limit=50)
    for artist in results['artists']['items']:
        following_artists.append({
            "name": artist['name'],
            "image": artist['images'][0]['url'] if artist.get('images') else None,
            "url": artist['external_urls']['spotify']
        })

    return render_template("following.html", profile=profile, artists=following_artists)

@app.route("/playlists")
def playlists():
    sp = get_spotify_client()

    if sp is None:
        return redirect("/login")

    profile = get_profile(sp)

    playlists_data = []

    results = sp.current_user_playlists(limit=50)

    while True:
        for playlist in results["items"]:

            track_count = playlist.get("tracks", {}).get("total", 0)

            playlists_data.append({
                "name": playlist["name"],
                "image": playlist["images"][0]["url"]
                    if playlist.get("images") and len(playlist["images"]) > 0
                    else None,
                "tracks": track_count,
                "owner": playlist["owner"]["display_name"],
                "url": playlist["external_urls"]["spotify"]
            })

            print(
                f"{playlist['name']} | "
                f"Sahip: {playlist['owner']['display_name']} | "
                f"Şarkı: {track_count}"
            )

        if results["next"]:
            results = sp.next(results)
        else:
            break

    return render_template(
        "playlists.html",
        profile=profile,
        playlists=playlists_data
    )

@app.route("/play", methods=["POST"])
def play():
    sp = get_spotify_client()
    if sp is None:
        return jsonify({"error": "no token"}), 401

    devices = sp.devices()

    if not devices["devices"]:
        return jsonify({"error": "no active device"}), 400

    device = next((d for d in devices["devices"] if d["is_active"]), None)

    if not device:
        device = devices["devices"][0]

    device_id = device["id"]

    sp.start_playback(device_id=device_id)
    return jsonify({"status": "playing"})

@app.route("/pause", methods=["POST"])
def pause():
    sp = get_spotify_client()
    if sp is None:
        return jsonify({"error": "no token"}), 401

    devices = sp.devices()

    if not devices["devices"]:
        return jsonify({"error": "no active device"}), 400

    device = next((d for d in devices["devices"] if d["is_active"]), None)

    if not device:
        device = devices["devices"][0]

    device_id = device["id"]

    sp.pause_playback(device_id=device_id)
    return jsonify({"status": "paused"})

@app.route("/next", methods=["POST"])
def next_track():
    sp = get_spotify_client()
    if sp is None:
        return jsonify({"error": "no token"}), 401

    sp.next_track()
    return jsonify({"status": "next"})

@app.route("/previous", methods=["POST"])
def previous_track():
    sp = get_spotify_client()
    if sp is None:
        return jsonify({"error": "no token"}), 401

    sp.previous_track()
    return jsonify({"status": "previous"})


@app.route("/overview")
def overview():
    sp = get_spotify_client()
    if sp is None:
        return redirect("/login")

    profile = get_profile(sp)

    tracks_raw = sp.current_user_top_tracks(limit=3)["items"]
    artists_raw = sp.current_user_top_artists(limit=3)["items"]

    top_tracks = []
    for t in tracks_raw:
        top_tracks.append({
            "name": t["name"],
            "artist": t["artists"][0]["name"],
            "image": t["album"]["images"][0]["url"],
            "url": t["external_urls"]["spotify"]
        })

    top_artists = []
    for a in artists_raw:
        top_artists.append({
            "name": a["name"],
            "image": a["images"][0]["url"] if a.get("images") else None,
            "url": a["external_urls"]["spotify"]
        })
                          
    results = sp.current_user_top_tracks(limit=50)
    album_dict = {}

    for item in results["items"]:
        album = item["album"]
        album_id = album["id"]

        if album_id not in album_dict:
            album_dict[album_id] = {
                "name": album["name"],
                "artist": album["artists"][0]["name"],
                "image": album["images"][0]["url"],
                "url": album["external_urls"]["spotify"]
            }

    top_albums = list(album_dict.values())[:3]

    return render_template("overview.html",
                           top_tracks=top_tracks,
                           top_artists=top_artists,
                           top_albums=top_albums,
                           profile=profile
                        )

@app.route("/history")
def history():
    sp = get_spotify_client()
    if sp is None:
        return redirect("/login")

    profile = get_profile(sp)

    current = sp.current_playback()

    if current and current["item"]:
        now_playing = {
            "name": current["item"]["name"],
            "artist": current["item"]["artists"][0]["name"],
            "image": current["item"]["album"]["images"][0]["url"],
            "progress": current["progress_ms"],
            "duration": current["item"]["duration_ms"],
            "url": current["item"]["external_urls"]["spotify"]
        }
    else:
        now_playing = None

    profile = sp.current_user()
    profile = {
        "name": profile.get("display_name"),
        "image": profile["images"][0]["url"] if profile.get("images") else None,
        "product": profile.get("product")
    }
    history = sp.current_user_recently_played(limit=25)["items"]


    history_data = sp.current_user_recently_played(limit=10)["items"]
    history_tracks = []
    for item in history:
        track = item["track"]
        history_tracks.append({
            "name": track["name"],
            "artist": track["artists"][0]["name"],
            "image": track["album"]["images"][0]["url"],
            "url": track["external_urls"]["spotify"]
        })

    return render_template(
        "history.html",
        profile=profile,
        now_playing=now_playing,
        history=history_tracks
    )

@app.route("/now_playing_api")
def now_playing_api():
    sp = get_spotify_client()
    if sp is None:
        return jsonify({"error": "no token"}), 401


    current = sp.current_playback()
    if current and current["item"]:
        now_playing = {
            "name": current["item"]["name"],
            "artist": current["item"]["artists"][0]["name"],
            "image": current["item"]["album"]["images"][0]["url"],
            "progress": current["progress_ms"],
            "duration": current["item"]["duration_ms"],
            "url": current["item"]["external_urls"]["spotify"],
            "is_playing": current["is_playing"]
        }
    else:
        now_playing = None
    return jsonify(now_playing)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    token_info = sp_oauth.get_access_token(code, as_dict=True)
    session["token_info"] = token_info
    return redirect("/history")

@app.route("/albums")
def top_albums():
    sp = get_spotify_client()
    if sp is None:
            return redirect("/login")

    time_range = request.args.get("range")
    if time_range not in ["short_term", "medium_term", "long_term"]:
        time_range = "long_term"

    profile = get_profile(sp)

    results = sp.current_user_top_tracks(limit=50, time_range=time_range)

    album_dict = {}
    for item in results["items"]:
        album_id = item["album"]["id"]
        if album_id not in album_dict:
            album_dict[album_id] = {
                "name": item["album"]["name"],
                "artist": item["album"]["artists"][0]["name"],
                "image": item["album"]["images"][0]["url"],
                "popularity": 0
            }
        album_dict[album_id]["popularity"] += 1

    albums_sorted = sorted(album_dict.values(), key=lambda x: x["popularity"], reverse=True)
    albums = albums_sorted[:10]

    chart_labels = [album["name"] for album in albums]
    chart_data = [album["popularity"] * 10 for album in albums]


    return render_template(
        "albums.html",
        albums=albums,
        current_range=time_range,
        profile=profile,
        chart_labels=chart_labels,
        chart_data=chart_data
    )

@app.route("/tracks")
def top_tracks():
    sp = get_spotify_client()
    if sp is None:
        return redirect("/")

    time_range = request.args.get("range")
    if time_range not in ["short_term", "medium_term", "long_term"]:
        time_range = "long_term"

    profile = get_profile(sp)
    
    results = sp.current_user_top_tracks(limit=25, time_range=time_range)

    tracks = []
    chart_labels = []
    chart_data = []

    for index, item in enumerate(results["items"]):
        score = 100 - (index * 4)
        if score < 0:
            score = 0

        tracks.append({
            "name": item["name"],
            "artist": item["artists"][0]["name"],
            "image": item["album"]["images"][0]["url"],
            "popularity": score
        })

        chart_labels.append(item["name"])
        chart_data.append(score)

    # Artık html string ile uğraşmıyoruz, template render ediyoruz
    return render_template("top.html", tracks=tracks, current_range=time_range, profile=profile, chart_labels=chart_labels, chart_data=chart_data)

@app.route("/artists")
def top_artists():
    sp = get_spotify_client()
    if sp is None:
       return redirect("/")




    time_range = request.args.get("range")
    if time_range not in ["short_term", "medium_term", "long_term"]:
        time_range = "long_term"


    profile = get_profile(sp)

    results = sp.current_user_top_artists(limit=25, time_range=time_range)

    artists = []
    chart_labels = []
    chart_data = []
    chart_genres = []

    for index, artist in enumerate(results["items"]):

        score = 100 - (index * 4)
        if score < 0:
            score = 0

        genres = artist.get("genres", [])
        genre_text = ", ".join(genres) if genres else "Tür bilgisi yok"

        artists.append({
            "name": artist.get("name"),
            "image": artist["images"][0]["url"] if artist.get("images") else None,
            "popularity": score,
            "genres": genre_text
        })

        chart_labels.append(artist.get("name"))
        chart_data.append(score)
        chart_genres.append(genre_text)

    return render_template(
        "artists.html",
        artists=artists,
        current_range=time_range,
        profile=profile,
        chart_labels=chart_labels,
        chart_data=chart_data,
        chart_genres=chart_genres
    )
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
