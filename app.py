from __future__ import annotations

import os
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

load_dotenv()

app = FastAPI(title="Digital Twin GLB Viewer")


class ConfigPayload(BaseModel):
    database_url: str = Field(
        ...,
        description=(
            "SQLAlchemy URL. Example PostgreSQL: postgresql+psycopg://user:pass@host/db "
            "or MySQL: mysql+mysqldb://user:pass@host/db"
        ),
    )


class ThresholdConfig(BaseModel):
    mesh_name: str
    value: float
    low_threshold: float = 30
    high_threshold: float = 70
    low_color: str = "#00b894"
    medium_color: str = "#fdcb6e"
    high_color: str = "#d63031"


DB_URL = os.getenv("DATABASE_URL", "")


def _color_from_threshold(payload: ThresholdConfig) -> str:
    if payload.value < payload.low_threshold:
        return payload.low_color
    if payload.value < payload.high_threshold:
        return payload.medium_color
    return payload.high_color


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """
<!DOCTYPE html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <title>Digital Twin GLB Viewer</title>
    <style>
      body { margin:0; font-family:Arial, sans-serif; overflow:hidden; }
      #panel {
        position:absolute; top:10px; left:10px; z-index:2;
        background:rgba(255,255,255,.92); padding:12px; border-radius:8px;
        width: 390px;
      }
      #canvas-wrap { width:100vw; height:100vh; }
      label { display:block; margin-top:8px; font-size:12px; }
      input, button { width:100%; margin-top:4px; padding:8px; }
      .hint { font-size: 11px; color:#555; }
    </style>
  </head>
  <body>
    <div id=\"panel\">
      <h3 style=\"margin:0 0 8px 0\">Digital Twin Controls</h3>
      <label>GLB URL (served static or CDN)</label>
      <input id=\"glbUrl\" value=\"/static/model.glb\" />
      <button id=\"loadModel\">Load Model</button>

      <label>Mesh/Object Name</label>
      <input id=\"meshName\" placeholder=\"e.g. Pump_01\" />

      <label>Sensor Value</label>
      <input id=\"sensorValue\" type=\"number\" step=\"0.01\" value=\"25\" />

      <label>Low Threshold</label>
      <input id=\"low\" type=\"number\" value=\"30\" />
      <label>High Threshold</label>
      <input id=\"high\" type=\"number\" value=\"70\" />

      <button id=\"applyThreshold\">Apply Color from Threshold</button>
      <button id=\"refreshFromDb\">Refresh Value from DB</button>
      <p class=\"hint\">Your DB table should contain: <code>mesh_name</code>, <code>value</code>.</p>
    </div>
    <div id=\"canvas-wrap\"></div>

    <script type=\"module\">
      import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.167.1/build/three.module.js';
      import { OrbitControls } from 'https://cdn.jsdelivr.net/npm/three@0.167.1/examples/jsm/controls/OrbitControls.js';
      import { GLTFLoader } from 'https://cdn.jsdelivr.net/npm/three@0.167.1/examples/jsm/loaders/GLTFLoader.js';

      const wrap = document.getElementById('canvas-wrap');
      const scene = new THREE.Scene();
      scene.background = new THREE.Color(0xf0f2f5);
      const camera = new THREE.PerspectiveCamera(60, innerWidth/innerHeight, 0.1, 1000);
      camera.position.set(4, 3, 7);

      const renderer = new THREE.WebGLRenderer({ antialias: true });
      renderer.setSize(innerWidth, innerHeight);
      wrap.appendChild(renderer.domElement);

      const controls = new OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;

      scene.add(new THREE.AmbientLight(0xffffff, 0.8));
      const dir = new THREE.DirectionalLight(0xffffff, 1.2);
      dir.position.set(8, 10, 6);
      scene.add(dir);

      const loader = new GLTFLoader();
      let glbRoot = null;

      function animate() {
        requestAnimationFrame(animate);
        controls.update();
        renderer.render(scene, camera);
      }
      animate();

      window.addEventListener('resize', () => {
        camera.aspect = innerWidth / innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(innerWidth, innerHeight);
      });

      function getMeshByName(name) {
        if (!glbRoot) return null;
        let found = null;
        glbRoot.traverse((obj) => {
          if (obj.isMesh && obj.name === name) found = obj;
        });
        return found;
      }

      document.getElementById('loadModel').onclick = async () => {
        const url = document.getElementById('glbUrl').value.trim();
        if (!url) return alert('Provide GLB URL');
        if (glbRoot) scene.remove(glbRoot);

        loader.load(url, (gltf) => {
          glbRoot = gltf.scene;
          scene.add(glbRoot);
          console.log('Loaded meshes:', glbRoot);
        }, undefined, (err) => alert('Failed to load GLB: ' + err.message));
      }

      document.getElementById('applyThreshold').onclick = async () => {
        const mesh_name = document.getElementById('meshName').value.trim();
        const value = parseFloat(document.getElementById('sensorValue').value);
        const low_threshold = parseFloat(document.getElementById('low').value);
        const high_threshold = parseFloat(document.getElementById('high').value);

        const res = await fetch('/threshold-color', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mesh_name, value, low_threshold, high_threshold })
        });
        const data = await res.json();
        if (!res.ok) return alert(data.detail || 'Failed to compute color');

        const mesh = getMeshByName(mesh_name);
        if (!mesh) return alert('Mesh not found: ' + mesh_name);
        mesh.material = mesh.material.clone();
        mesh.material.color = new THREE.Color(data.color);
      }

      document.getElementById('refreshFromDb').onclick = async () => {
        const mesh_name = document.getElementById('meshName').value.trim();
        if (!mesh_name) return alert('Provide mesh name');

        const response = await fetch(`/sensor-value/${encodeURIComponent(mesh_name)}`);
        const data = await response.json();
        if (!response.ok) return alert(data.detail || 'Could not fetch DB value');

        document.getElementById('sensorValue').value = data.value;
        document.getElementById('applyThreshold').click();
      }
    </script>
  </body>
</html>
    """


@app.post("/set-db")
def set_db(cfg: ConfigPayload):
    global DB_URL
    DB_URL = cfg.database_url
    return {"status": "ok", "database_url": DB_URL}


@app.get("/sensor-value/{mesh_name}")
def sensor_value(mesh_name: str):
    if not DB_URL:
        raise HTTPException(status_code=400, detail="Database URL not configured. POST /set-db first.")

    try:
        engine = create_engine(DB_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT value FROM digital_twin_metrics WHERE mesh_name = :mesh_name LIMIT 1"),
                {"mesh_name": mesh_name},
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail=f"No value for mesh '{mesh_name}'")
            return {"mesh_name": mesh_name, "value": float(row[0])}
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail=f"DB query failed: {exc}") from exc


@app.post("/threshold-color")
def threshold_color(payload: ThresholdConfig):
    color = _color_from_threshold(payload)
    return {
        "mesh_name": payload.mesh_name,
        "value": payload.value,
        "color": color,
        "band": (
            "low"
            if payload.value < payload.low_threshold
            else "medium"
            if payload.value < payload.high_threshold
            else "high"
        ),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
