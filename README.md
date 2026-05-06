# Digital Twin GLB Viewer (Python)

This starter project loads a **GLB** 3D model in-browser and applies object colors based on database-driven threshold values.

## Features

- Load and view GLB with Three.js.
- Connect to PostgreSQL or MySQL from Python (FastAPI + SQLAlchemy).
- Query a value for a specific object (`mesh_name`) from DB.
- Color each 3D object by threshold bands (low / medium / high).

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

Open `http://localhost:8000`.

## Database setup

Create a table:

```sql
CREATE TABLE digital_twin_metrics (
    mesh_name VARCHAR(255) PRIMARY KEY,
    value DOUBLE PRECISION NOT NULL
);
```

Insert example:

```sql
INSERT INTO digital_twin_metrics(mesh_name, value)
VALUES ('Pump_01', 82.4), ('Tank_01', 44.3);
```

## Configure DB at runtime

Use this endpoint once after start:

```bash
curl -X POST http://localhost:8000/set-db \
  -H "Content-Type: application/json" \
  -d '{"database_url":"postgresql+psycopg://user:pass@localhost:5432/mydb"}'
```

MySQL URL example:

- `mysql+mysqldb://user:pass@localhost:3306/mydb`

## Expected GLB object naming

The object name in your GLB must match `mesh_name` in DB, for example:

- GLB mesh `Pump_01` ↔ DB row `mesh_name='Pump_01'`.

## Notes

- Place your GLB at `./static/model.glb` or change URL in the UI.
- This is a starter template; add auth, caching, and historical charts for production.
