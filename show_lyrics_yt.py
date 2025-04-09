from flask import Flask, render_template_string, jsonify
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from lyricsgenius import Genius
import requests
from io import BytesIO
from colorthief import ColorThief
import os
from dotenv import load_dotenv
load_dotenv()  

GENIUS_TOKEN = os.environ.get("GENIUS_TOKEN")
SPOTIPY_CLIENT_ID = os.environ.get("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.environ.get("SPOTIPY_CLIENT_SECRET")
SPOTIPY_REDIRECT_URI = os.environ.get("SPOTIPY_REDIRECT_URI", "http://localhost:8080")

SCOPE = 'user-read-currently-playing user-read-playback-position'

genius = Genius(GENIUS_TOKEN, remove_section_headers=True, skip_non_songs=True)
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET,
    redirect_uri=SPOTIPY_REDIRECT_URI,
    scope=SCOPE
))

app = Flask(__name__)
last_track_id = None
cached_lyrics = []

@app.route('/')
def index():
    return render_template_string(html_template)

@app.route('/now_playing')
def now_playing():
    global last_track_id, cached_lyrics
    try:
        current = sp.currently_playing()
        if not current or not current.get("is_playing"):
            return jsonify({"error": "No song is currently playing."})

        track = current['item']
        track_name = track['name']
        artist_name = track['artists'][0]['name']
        track_id = track['id']
        duration_ms = track['duration_ms']
        progress_ms = current['progress_ms']
        album_image_url = track['album']['images'][0]['url']

        response = requests.get(album_image_url)
        img_file = BytesIO(response.content)
        color_thief = ColorThief(img_file)
        dominant_color = color_thief.get_color(quality=1)
        rgb = f"rgb({dominant_color[0]}, {dominant_color[1]}, {dominant_color[2]})"

        if track_id != last_track_id:
            song = genius.search_song(track_name, artist_name)
            if song and song.lyrics:
                lines = [line.strip() for line in song.lyrics.split("\n")[1:] if line.strip()]
                cached_lyrics = lines
            else:
                cached_lyrics = ["Lyrics not found."]
            last_track_id = track_id

        return jsonify({
            "track_name": track_name,
            "artist_name": artist_name,
            "album_image_url": album_image_url,
            "lyrics": cached_lyrics,
            "duration_ms": duration_ms,
            "progress_ms": progress_ms,
            "dominant_color": rgb
        })

    except Exception as e:
        return jsonify({"error": str(e)})

html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Live Spotify Lyrics</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@500&family=Roboto+Mono&display=swap" rel="stylesheet">
    <style>
        body {
            margin: 0;
            font-family: 'Montserrat', sans-serif;
            background: #000; /* changed from #0f0f0f */
            color: #f1f1f1;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            border-radius: 16px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
            width: 95%;
            max-width: 1000px;
            overflow: hidden;
            display: flex;
            flex-direction: row;
            flex-wrap: wrap;
            background: none; /* remove any background */
        }
        .left {
            background: #111;
            padding: 30px;
            text-align: center;
            flex: 1;
        }
        .right {
            flex: 2;
            padding: 30px;
            overflow-y: auto;
            max-height: 90vh;
            scroll-behavior: smooth;
        }
        .lyrics-card {
            background-color: #2a2a2a;
            border-radius: 12px;
            padding: 20px 30px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.3);
            font-family: 'Roboto Mono', monospace;
            font-size: 16px;
            line-height: 1.7;
            white-space: pre-wrap;
        }
        .lyrics-card p {
            margin: 8px 0;
        }
        .progress-container {
            height: 10px;
            width: 100%;
            background-color: #333;
            border-radius: 5px;
            margin: 20px 0;
        }
        .progress-bar {
            height: 100%;
            width: 0%;
            background-color: #1db954;
            transition: width 0.5s ease;
            border-radius: 5px;
        }
        img.album-art {
            border-radius: 12px;
            width: 220px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.6);
        }
    </style>
</head>
<body>
    <div class="container" id="main-wrapper">
        <div class="left">
            <h3 id="track-name"></h3>
            <h4 id="artist-name" style="color: #aaa;"></h4>
            <img id="album-art" class="album-art" src="" alt="Album Art">
            <div class="progress-container">
                <div id="progress-bar" class="progress-bar"></div>
            </div>
        </div>
        <div class="right">
            <div class="lyrics-card" id="lyrics-text"></div>
        </div>
    </div>

    <script>
        async function updateNowPlaying() {
            try {
                const res = await fetch('/now_playing');
                const data = await res.json();

                if (data.error) {
                    document.getElementById('track-name').textContent = data.error;
                    return;
                }

                document.getElementById('track-name').textContent = data.track_name;
                document.getElementById('artist-name').textContent = data.artist_name;
                document.getElementById('album-art').src = data.album_image_url;

                const lyricsContainer = document.getElementById('lyrics-text');
                const lyricsLines = data.lyrics;
                lyricsContainer.innerHTML = '';

                lyricsLines.forEach((line, idx) => {
                    const p = document.createElement('p');
                    p.textContent = line;
                    p.setAttribute('data-line-index', idx);
                    lyricsContainer.appendChild(p);
                });

                const progressRatio = data.progress_ms / data.duration_ms;
                const section = Math.floor(progressRatio * lyricsLines.length);
                const targetLine = document.querySelector(`[data-line-index='${section}']`);
                if (targetLine) {
                    targetLine.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }

                const progressPercent = (data.progress_ms / data.duration_ms) * 100;
                document.getElementById('progress-bar').style.width = progressPercent + "%";

                document.getElementById('lyrics-text').style.background = `linear-gradient(135deg, ${data.dominant_color}, #121212)`;


            } catch (err) {
                console.error("Error fetching song:", err);
            }
        }

        updateNowPlaying();
        setInterval(updateNowPlaying, 2000);
    </script>
</body>
</html>
"""
if __name__ == '__main__':
    # Get the PORT from environment variable (Render sets this)
    port = int(os.environ.get("PORT", 5002))
    # Don't use host="0.0.0.0" in production unless needed
    app.run(port=port, debug=False

