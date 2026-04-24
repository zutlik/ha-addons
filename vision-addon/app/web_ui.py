import asyncio
import io
import logging
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse

logger = logging.getLogger(__name__)

EMOJI = {
    "thumbs_up": "👍", "thumbs_down": "👎", "open_palm": "✋",
    "fist": "✊", "pointing_up": "☝️", "peace": "✌️",
    "rock_on": "🤟", "shaka": "🤙", "ok": "👌", "five_spread": "🖐️",
}

HTML = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Vision Addon</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { font-family: sans-serif; background: #111; color: #eee; margin: 0; padding: 16px; }
    h1 { margin: 0 0 16px; font-size: 1.4em; }
    .grid { display: flex; gap: 16px; flex-wrap: wrap; }
    .card { background: #1e1e1e; border-radius: 8px; padding: 16px; flex: 1; min-width: 280px; }
    img#stream { width: 100%; border-radius: 6px; }
    .gesture-box { font-size: 3em; text-align: center; padding: 12px; }
    .badge { display: inline-block; background: #333; border-radius: 4px; padding: 2px 8px; margin: 2px; font-size: 0.85em; }
    .badge.on { background: #1a6a1a; }
    input[type=text] { background: #333; border: 1px solid #555; color: #eee; padding: 6px; border-radius: 4px; width: 200px; }
    button { background: #2563eb; color: #fff; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; margin: 4px; }
    button.danger { background: #dc2626; }
    .face-list { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
    label { display: block; margin: 8px 0 4px; font-size: 0.9em; color: #aaa; }
  </style>
</head>
<body>
  <h1>🎥 Vision Addon</h1>
  <div class="grid">
    <div class="card">
      <b>Live Stream</b>
      <img id="stream" src="/stream" alt="Camera stream">
      <div id="faces" style="margin-top:8px;"></div>
    </div>
    <div class="card">
      <b>Last Gesture</b>
      <div class="gesture-box" id="gesture">—</div>
      <hr style="border-color:#333">
      <b>Register Known Face</b>
      <label>Name</label>
      <input type="text" id="name" placeholder="e.g. John">
      <label>Photo</label>
      <input type="file" id="photo" accept="image/*">
      <br><button onclick="registerFace()">Register</button>
      <div id="register-msg" style="margin-top:8px;font-size:0.85em;"></div>
      <hr style="border-color:#333">
      <b>Known People</b>
      <div class="face-list" id="face-list">Loading...</div>
    </div>
  </div>
  <script>
    async function poll() {
      try {
        const r = await fetch('/status');
        const d = await r.json();
        const em = {"thumbs_up":"👍","thumbs_down":"👎","open_palm":"✋","fist":"✊","pointing_up":"☝️","peace":"✌️","rock_on":"🤟","shaka":"🤙","ok":"👌","five_spread":"🖐️"};
        document.getElementById('gesture').textContent = d.gesture ? (em[d.gesture] || d.gesture) : '—';
        const fc = document.getElementById('faces');
        if (d.faces.length === 0) {
          fc.innerHTML = '<span style="color:#888">No faces detected</span>';
        } else {
          fc.innerHTML = d.faces.map(f => `<span class="badge ${f.name !== 'unknown' ? 'on' : ''}">${f.name}</span>`).join('');
        }
        loadKnown();
      } catch(e) {}
      setTimeout(poll, 1500);
    }
    async function loadKnown() {
      const r = await fetch('/faces');
      const d = await r.json();
      const el = document.getElementById('face-list');
      if (d.names.length === 0) {
        el.innerHTML = '<span style="color:#888">None registered</span>';
      } else {
        el.innerHTML = d.names.map(n =>
          `<span class="badge on">${n} <button class="danger" style="padding:2px 6px;font-size:0.8em" onclick="removeFace('${n}')">✕</button></span>`
        ).join('');
      }
    }
    async function registerFace() {
      const name = document.getElementById('name').value.trim();
      const file = document.getElementById('photo').files[0];
      const msg = document.getElementById('register-msg');
      if (!name || !file) { msg.textContent = 'Name and photo required.'; return; }
      const fd = new FormData();
      fd.append('name', name);
      fd.append('file', file);
      const r = await fetch('/faces', {method:'POST', body: fd});
      const d = await r.json();
      msg.textContent = d.ok ? `✅ ${name} registered!` : `❌ ${d.error}`;
      loadKnown();
    }
    async function removeFace(name) {
      await fetch(`/faces/${name}`, {method:'DELETE'});
      loadKnown();
    }
    poll();
  </script>
</body>
</html>"""


def create_app(vision) -> FastAPI:
    app = FastAPI(title="Vision Addon")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTML

    @app.get("/stream")
    async def stream():
        async def gen():
            while True:
                with vision.frame_lock:
                    frame = vision.latest_frame
                if frame:
                    yield (
                        b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                    )
                await asyncio.sleep(0.1)

        return StreamingResponse(gen(), media_type="multipart/x-mixed-replace;boundary=frame")

    @app.get("/status")
    async def status():
        with vision.frame_lock:
            return {
                "gesture": vision.latest_gesture,
                "faces": vision.latest_faces,
                "persons": vision.known_persons,
                "face_enabled": vision.face_engine is not None,
            }

    @app.get("/faces")
    async def list_faces():
        if vision.face_engine is None:
            return {"names": [], "enabled": False}
        return {"names": vision.face_engine.list_known()}

    @app.post("/faces")
    async def add_face(name: str = Form(...), file: UploadFile = File(...)):
        if vision.face_engine is None:
            return JSONResponse(
                {"ok": False, "error": "Face detection is disabled"},
                status_code=503,
            )
        data = await file.read()
        ok = vision.face_engine.register_face(name, data)
        if not ok:
            return JSONResponse({"ok": False, "error": "No face found in image"}, status_code=400)
        return {"ok": True}

    @app.delete("/faces/{name}")
    async def delete_face(name: str):
        if vision.face_engine is None:
            return {"ok": False, "error": "Face detection is disabled"}
        removed = vision.face_engine.remove_face(name)
        return {"ok": removed}

    return app
