"""
Air‑Quality Flask API
====================
Standalone Flask service that exposes sensor metadata and air‑quality
readings from a PostgreSQL database.  All configuration values are hard‑coded
here for clarity; adjust them directly in the *DB_KWARGS* or *API_* constants
as needed.

Endpoints
---------
GET /sensors
    List of sensors (id, name, coordinates, …)

GET /air_quality
GET /air_quality/<idsensore>
    Latest 1 000 readings overall or for a single sensor.

GET /sensors/geojson
    Same sensor list returned as a GeoJSON *FeatureCollection* (handy for
    maps).

If PostgreSQL is unavailable the API falls back to a small in‑memory demo set
so you can test the endpoints right away.
"""
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from flask import Flask, jsonify
from flask_cors import CORS

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:  # psycopg2 is optional → demo‑only mode
    psycopg2 = None  # type: ignore

# ─────────────────────────────  Configuration  ──────────────────────────────
API_HOST = "127.0.0.1"
API_PORT = 5000  # change the port here if necessary

DB_KWARGS = {
    "dbname": "db_2019",      # database name
    "user": "postgres",   # PostgreSQL user
    "password": "1111", # PostgreSQL password
    "host": "localhost",  # PostgreSQL host
    "port": 5432,          # PostgreSQL port
}

# ────────────────────────────────  Flask app  ───────────────────────────────
app = Flask(__name__)
CORS(app)


def db_conn():
    """Return a new Postgres connection or raise in demo‑only mode."""
    if psycopg2 is None:
        raise RuntimeError("psycopg2 not installed – running in DEMO mode")
    return psycopg2.connect(cursor_factory=RealDictCursor, **DB_KWARGS)


# ─────────────────────────────  Demo fall‑back  ─────────────────────────────
DEMO_SENSORS = pd.DataFrame(
    {
        "id_sensore": [1, 2],
        "nome_stazione": ["Demo North", "Demo South"],
        "provincia": ["XX", "YY"],
        "comune": ["Foo", "Bar"],
        "latitude": [45.0, 44.5],
        "longitude": [9.0, 9.2],
    }
)


def demo_aq(n_days: int = 3) -> pd.DataFrame:
    """Generate synthetic air‑quality readings for the demo sensors."""
    now = datetime.utcnow()
    rng = pd.date_range(end=now, periods=n_days * 24, freq="h")
    rows: list[dict[str, Any]] = []
    for sid in DEMO_SENSORS["idsensore"]:
        vals = np.random.randint(20, 180, size=len(rng))
        rows.extend(
            {"idsensore": sid, "data": d, "valore": v, "stato": "V"}
            for d, v in zip(rng, vals)
        )
    return pd.DataFrame(rows)


# ────────────────────────────────  Endpoints  ───────────────────────────────
@app.route("/sensors")
def sensors():
    """Return all sensors ordered by *id_sensore*."""
    if psycopg2:
        try:
            with db_conn() as conn, conn.cursor() as cur:
                cur.execute("SELECT * FROM sensors ORDER BY id_sensore;")
                return jsonify(cur.fetchall())
        except Exception as err:  # pragma: no cover
            print("⚠️  /sensors:", err)

    return jsonify(DEMO_SENSORS.to_dict("records"))


@app.route("/air_quality")
@app.route("/air_quality/<int:idsensore>")
def air_quality(idsensore: int | None = None):
    """Return last 1 000 AQ readings (optionally filtered by *idsensore*)."""
    if psycopg2:
        try:
            with db_conn() as conn, conn.cursor() as cur:
                q = "SELECT * FROM air_quality"
                params: tuple[Any, ...] = ()
                if idsensore is not None:
                    q += " WHERE idsensore = %s"
                    params = (idsensore,)
                q += " ORDER BY data DESC LIMIT 100000;"
                cur.execute(q, params)
                return jsonify(cur.fetchall())
        except Exception as err:  # pragma: no cover
            print("⚠️  /air_quality:", err)

    df = demo_aq()
    if idsensore is not None:
        df = df[df["idsensore"] == idsensore]
    return jsonify(
        df.sort_values("data", ascending=False).head(100000).to_dict("records")
    )


@app.route("/sensors/geojson")
def sensors_geojson():
    """Return sensor list as GeoJSON FeatureCollection."""
    df = pd.DataFrame(sensors().json)  # type: ignore
    features = [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [r["longitude"], r["latitude"]],
            },
            "properties": {
                "id_sensore": r["id_sensore"],
                "nome_stazione": r["nome_stazione"],
                "provincia": r["provincia"],
                "comune": r["comune"],
            },
        }
        for _, r in df.iterrows()
    ]
    return jsonify({"type": "FeatureCollection", "features": features})

# ────────────────────────────────  Endpoint  ───────────────────────────────
@app.route('/data_1', methods=['GET']) # A read endpoint to fetch data
def get_data():
    mydb_conn = db_conn()

    # Use RealDictCursor to return results as a list of dictionaries
    cursor = mydb_conn.cursor(cursor_factory=RealDictCursor)  # Use RealDictCursor for JSON-like output

    cursor.execute("SELECT nome_tipo_sensore, provincia, comune, day, avg_value FROM avg_per_day_by_each_comune_and_pollutant ORDER BY day")  # Replace with your table name
    data = cursor.fetchall()
    cursor.close()
    # print(data)
    mydb_conn.close()
    return jsonify(data)

# ────────────────────────────────  User management  ───────────────────────────────
# Endpoints for user registration and management
@app.route('/users', methods=['GET']) 
def get_users():
    mydb_conn = db_conn()
    cursor = mydb_conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT username, password_hash FROM users ORDER BY id")
    data = cursor.fetchall()

    cursor.close()
    mydb_conn.close()
    return jsonify(data)

from flask import request

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password_hash = data.get('password_hash')

    conn = db_conn()
    cursor = conn.cursor()

    # Check if the username already exists
    cursor.execute("SELECT 1 FROM users WHERE username = %s", (username,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return 'Username already exists', 409

    # Add the new user to the database
    cursor.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (username, password_hash))
    conn.commit()
    cursor.close()
    conn.close()

    return 'User registered successfully', 201


# ─────────────────────────────────  Main  ───────────────────────────────────
if __name__ == "__main__":
    url = f"http://{API_HOST}:{API_PORT}"
    print(f"🚀  Air‑Quality Flask API running on {url} …")
    app.run(host=API_HOST, port=API_PORT, debug=False)

