import os
import time
import io
import json
import zipfile
from urllib.parse import urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler
import cgi
from pathlib import Path

def _run_task(task, category, file_path, auto_confirm):
    import importlib
    m = importlib.import_module("main")
    if hasattr(m, "run_task"):
        return m.run_task(task, category=category, file_path=file_path, auto_confirm=auto_confirm)
    return None

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path != "/run":
            self.send_response(404)
            self.end_headers()
            return
        content_type = self.headers.get("Content-Type")
        form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": content_type})
        task = form.getvalue("task")
        category = form.getvalue("category")
        auto_confirm_raw = form.getvalue("auto_confirm")
        auto_confirm = str(auto_confirm_raw).lower() in ("1", "true", "yes")
        upload_field = form["file"] if "file" in form else None
        if not task:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "task is required"}).encode("utf-8"))
            return
        start_ts = time.time()
        uploads_dir = Path("uploads")
        uploads_dir.mkdir(exist_ok=True)
        saved_path = None
        if upload_field is not None and upload_field.file:
            filename = Path(upload_field.filename or "upload.bin").name
            saved_path = uploads_dir / f"{int(start_ts)}_{filename}"
            with open(saved_path, "wb") as f:
                f.write(upload_field.file.read())
        result = _run_task(task, category, str(saved_path) if saved_path else None, auto_confirm)
        excel_path = None
        if isinstance(result, dict) and "excel_file" in result:
            excel_path = result.get("excel_file")
        if excel_path and os.path.exists(excel_path):
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f"attachment; filename=\"{Path(excel_path).name}\"")
            self.end_headers()
            with open(excel_path, "rb") as f:
                self.wfile.write(f.read())
            return
        output_dir = Path("output")
        generated = []
        if output_dir.exists():
            for root, _, files in os.walk(output_dir):
                for name in files:
                    p = Path(root) / name
                    try:
                        if p.stat().st_mtime >= start_ts:
                            generated.append(p)
                    except FileNotFoundError:
                        pass
        if generated:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                for p in generated:
                    z.write(p, arcname=str(p.relative_to(output_dir)))
            data = buf.getvalue()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", "attachment; filename=output.zip")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "message": "no downloadable output"}).encode("utf-8"))

def run():
    port = int(os.getenv("IO_SERVER_PORT", "8080"))
    host = os.getenv("IO_SERVER_HOST", "0.0.0.0")
    server = HTTPServer((host, port), Handler)
    server.serve_forever()

if __name__ == "__main__":
    run()
