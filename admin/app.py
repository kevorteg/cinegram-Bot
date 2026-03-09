from flask import Flask, render_template, jsonify, request
import sqlite3
import os
import sys
import requests

# Path setup
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, ".."))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from cinegram.services.db_service import DbService
from cinegram.services.history_service import HistoryService

app = Flask(__name__)
DB_PATH = os.path.join(root_dir, "cinegram", "assets", "cinegram.db")
DbService.DB_PATH = DB_PATH

def get_db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        conn = get_db_conn()
        cursor = conn.cursor()
        
        # Historial total
        cursor.execute("SELECT COUNT(*) FROM history")
        total_movies = cursor.fetchone()[0]
        
        # Usuarios totales
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        # Películas de hoy
        cursor.execute("SELECT COUNT(*) FROM history WHERE published_at >= date('now')")
        today_uploads = cursor.fetchone()[0]
        
        conn.close()
        return jsonify({
            "total_movies": total_movies,
            "total_users": total_users,
            "today_uploads": today_uploads,
            "system_status": "Online"
        })
    except Exception as e:
        print(f"Stats Error: {e}")
        return jsonify({"total_movies": 0, "total_users": 0, "today_uploads": 0, "system_status": "Error"}), 500

@app.route('/api/movies', methods=['GET'])
def get_movies():
    q = request.args.get('q', '').lower()
    year = request.args.get('year', '')
    genre = request.args.get('genre', '')
    
    try:
        conn = get_db_conn()
        cursor = conn.cursor()
        
        query = "SELECT tmdb_id, title, published_at FROM history WHERE 1=1"
        params = []
        
        if q:
            query += " AND (lower(title) LIKE ? OR tmdb_id LIKE ?)"
            params.extend([f'%{q}%', f'%{q}%'])
        
        # Como no tenemos año/género real en DB aun, filtramos por la fecha de publicación o texto del título si existe.
        # En una versión madura usaríamos las columnas reales.
        
        query += " ORDER BY published_at DESC LIMIT 100"
        cursor.execute(query, params)
        movies = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(movies)
    except Exception as e:
        print(f"Movies Error: {e}")
        return jsonify([])

@app.route('/api/filters', methods=['GET'])
def get_filters():
    # Extraer años de publicación únicos para el filtro
    try:
        conn = get_db_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT strftime('%Y', published_at) as year FROM history WHERE published_at IS NOT NULL ORDER BY year DESC")
        years = [row['year'] for row in cursor.fetchall() if row['year']]
        conn.close()
        
        genres = ["Acción", "Comedia", "Terror", "Drama", "Animación", "Ciencia Ficción"]
        return jsonify({"years": years, "genres": genres})
    except:
        return jsonify({"years": [], "genres": []})

@app.route('/api/poster/<tmdb_id>')
def get_poster(tmdb_id):
    try:
        from cinegram.config import settings
        # Cache de posters local para no saturar la API
        res = requests.get(f"https://api.themoviedb.org/3/movie/{tmdb_id}", params={"api_key": settings.TMDB_API_KEY})
        if res.status_code == 200:
            path = res.json().get('poster_path')
            if path:
                return jsonify({"url": f"https://image.tmdb.org/t/p/w500{path}"})
        return jsonify({"url": f"https://placehold.co/300x450/11121d/38bdf8?text=No+Poster"})
    except:
        return jsonify({"url": f"https://placehold.co/300x450/11121d/38bdf8?text=Error"})

@app.route('/api/movies/<tmdb_id>', methods=['DELETE'])
def delete_movie(tmdb_id):
    try:
        conn = get_db_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM history WHERE tmdb_id = ?", (str(tmdb_id),))
        conn.commit()
        conn.close()
        return jsonify({"status": "deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/movies/<tmdb_id>', methods=['PUT'])
def update_movie(tmdb_id):
    data = request.json
    new_title = data.get('title')
    try:
        conn = get_db_conn()
        cursor = conn.cursor()
        cursor.execute("UPDATE history SET title = ? WHERE tmdb_id = ?", (new_title, str(tmdb_id)))
        conn.commit()
        conn.close()
        return jsonify({"status": "updated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
