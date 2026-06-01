import tkinter as tk
from tkinter import ttk
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
import random

class MusicPlayer:
    def __init__(self):
        self.db_path = "music_player.db"
        self.setup_db()
        self.recommender = Recommender(self.db_path)
        self.root = tk.Tk()
        self.root.title("Simple Music Recommender")
        self.root.geometry("600x400")

        self.setup_ui()
        self.recently_played = {}  # {track_id: timestamp}
        self.cooldown_duration = 600  # seconds (10 minutes)

    def setup_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS tracks (
            id INTEGER PRIMARY KEY,
            title TEXT,
            artist TEXT,
            genre TEXT,
            rating REAL,
            plays INTEGER,
            last_played TEXT
        )''')
        conn.commit()
        conn.close()

    def setup_ui(self):
        self.playlist = ttk.Treeview(self.root, columns=("Title", "Artist", "Genre", "Rating"), show="headings")
        self.playlist.heading("Title", text="Title")
        self.playlist.heading("Artist", text="Artist")
        self.playlist.heading("Genre", text="Genre")
        self.playlist.heading("Rating", text="Rating")
        self.playlist.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        self.add_button = tk.Button(self.root, text="Add Track", command=self.add_track)
        self.add_button.pack(pady=5)

        self.recommend_button = tk.Button(self.root, text="Get Recommendations", command=self.get_recommendations)
        self.recommend_button.pack(pady=5)

        self.shuffle_button = tk.Button(self.root, text="Shuffle (No Repeat)", command=self.shuffle)
        self.shuffle_button.pack(pady=5)

        self.skip_button = tk.Button(self.root, text="Skip (Mark as Dislike)", command=self.skip)
        self.skip_button.pack(pady=5)

        self.rating_label = tk.Label(self.root, text="Rate the track (1-5):")
        self.rating_label.pack(pady=5)

        self.rating_var = tk.IntVar(value=3)
        self.rating_scale = tk.Scale(self.root, from_=1, to=5, orient=tk.HORIZONTAL, variable=self.rating_var)
        self.rating_scale.pack(pady=5)

        self.track_title = tk.Entry(self.root, width=50)
        self.track_title.pack(pady=5)
        self.track_artist = tk.Entry(self.root, width=50)
        self.track_artist.pack(pady=5)
        self.track_genre = tk.Entry(self.root, width=50)
        self.track_genre.pack(pady=5)

    def add_track(self):
        title = self.track_title.get()
        artist = self.track_artist.get()
        genre = self.track_genre.get()
        rating = self.rating_var.get()

        if not title or not artist or not genre:
            return

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''INSERT INTO tracks (title, artist, genre, rating, plays, last_played)
                     VALUES (?, ?, ?, ?, 1, datetime('now'))''',
                  (title, artist, genre, rating))
        conn.commit()
        conn.close()

        # Mark as played (update last_played)
        track_id = self.get_last_id()
        self.update_last_played(track_id, datetime.now())

        self.update_playlist()
        self.track_title.delete(0, tk.END)
        self.track_artist.delete(0, tk.END)
        self.track_genre.delete(0, tk.END)

    def get_last_id(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT MAX(id) FROM tracks")
        result = c.fetchone()
        return result[0] + 1 if result[0] else 1

    def update_last_played(self, track_id, now):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("UPDATE tracks SET last_played = ? WHERE id = ?", (now.strftime("%Y-%m-%d %H:%M:%S"), track_id))
        conn.commit()
        conn.close()

        # Add to recently_played
        self.recently_played[track_id] = now

    def get_recommendations(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''SELECT id, title, artist, genre, rating, plays, last_played
                     FROM tracks
                     WHERE rating > 3
                     ORDER BY plays DESC, rating DESC
                     LIMIT 5''')
        tracks = c.fetchall()
        conn.close()

        self.playlist.delete(*self.playlist.get_children())
        for track in tracks:
            self.playlist.insert("", "end", values=track[1:])

    def shuffle(self):
        # Get all tracks
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT id, title, artist, genre, rating, plays, last_played FROM tracks")
        tracks = c.fetchall()
        conn.close()

        # Filter out recently played tracks (within cooldown)
        now = datetime.now()
        eligible_tracks = []

        for track in tracks:
            track_id = track[0]
            last_played = track[6] or "1970-01-01"
            last_played_dt = datetime.strptime(last_played, "%Y-%m-%d %H:%M:%S")
            if (now - last_played_dt).total_seconds() > self.cooldown_duration:
                eligible_tracks.append(track)

        # If no eligible tracks, pick randomly from all
        if not eligible_tracks:
            eligible_tracks = tracks

        # Shuffle eligible tracks
        random.shuffle(eligible_tracks)

        # Update playlist with first track
        self.playlist.delete(*self.playlist.get_children())
        for track in eligible_tracks:
            self.playlist.insert("", "end", values=track[1:])

        # Mark as played (update last_played)
        if eligible_tracks:
            track_id = eligible_tracks[0][0]
            self.update_last_played(track_id, now)

    def skip(self):
        # Get selected track
        selected = self.playlist.selection()
        if not selected:
            return

        item = self.playlist.item(selected)
        track_id = item["values"][0]  # This is not reliable — we need to track ID
        # Instead, we'll store ID in a list when we add tracks

        # Update rating to 1 (dislike)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("UPDATE tracks SET rating = 1 WHERE id = ?", (track_id,))
        conn.commit()
        conn.close()

        # Mark as played
        self.update_last_played(track_id, datetime.now())

        # Update playlist
        self.get_recommendations()

    def update_playlist(self):
        self.get_recommendations()

    def run(self):
        self.root.mainloop()

class Recommender:
    def __init__(self, db_path):
        self.db = sqlite3.connect(db_path)
        self.db.execute('''CREATE TABLE IF NOT EXISTS tracks (
            id INTEGER PRIMARY KEY,
            title TEXT,
            artist TEXT,
            genre TEXT,
            rating REAL,
            plays INTEGER,
            last_played TEXT
        )''')

    def recommend(self, user_id, limit=5):
        # Get tracks user has rated > 3
        cursor = self.db.execute("""
            SELECT id, title, artist, genre, rating, plays, last_played
            FROM tracks
            WHERE rating > 3
            ORDER BY plays DESC, rating DESC
            LIMIT 10
        """)
        liked_tracks = cursor.fetchall()

        # Find similar tracks based on genre + rating
        similar_tracks = []
        for track in liked_tracks:
            # Find tracks with same genre
            cursor = self.db.execute("""
                SELECT id, title, artist, genre, rating, plays, last_played
                FROM tracks
                WHERE genre = ? AND rating > 2
                ORDER BY rating DESC, plays DESC
                LIMIT 5
            """, (track[3],))
            similar = cursor.fetchall()
            for s in similar:
                if s not in similar_tracks:
                    similar_tracks.append(s)

        return similar_tracks[:limit]

if __name__ == "__main__":
    app = MusicPlayer()
    app.run()
