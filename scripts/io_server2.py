import os
import time
import io
import json
import zipfile
from http.server import HTTPServer, BaseHTTPRequestHandler
import cgi
from pathlib import Path

def _run_task(task, category, file_path, auto_confirm):
    import importlib
    m = importlib.import_module("main")
    if hasattr(m, "run_task"):
        return m.run_task(task, category=category, file_path=file_path, auto_confirm=auto_confirm)
    return None

INDEX_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>AMZ Ops</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{font-family:system-ui,Arial;padding:24px;max-width:1100px;margin:auto;color:#111}
h2{margin:0 0 16px}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ddd;padding:10px;text-align:left}
th{background:#f6f6f6}button{padding:8px 14px;border:1px solid #333;background:#111;color:#fff;border-radius:4px;cursor:pointer}
button.secondary{background:#fff;color:#111}input,select{padding:8px;margin:6px 0;width:100%;box-sizing:border-box}
#modal{position:fixed;inset:0;background:rgba(0,0,0,.5);display:none;align-items:center;justify-content:center}
#modal>.card{background:#fff;padding:20px;border-radius:6px;min-width:360px;max-width:560px}
#toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#111;color:#fff;padding:10px 16px;border-radius:4px;display:none}
</style></head><body>
<h2>Amazon Ops Service</h2>
<p>选择功能并运行。如需上传文件或指定品类，点击运行后在弹窗中配置。</p>
<table><thead><tr><th>序号</th><th>功能名称</th><th>操作</th></tr></thead><tbody id="tbody"></tbody></table>
<p style="margin-top:12px">健康检查：<code>/health</code>；接口：<code>POST /run</code></p>
<div id="modal"><div class="card">
<div id="modalTitle" style="font-weight:600;margin-bottom:10px"></div>
<div id="fileRow" style="display:none"><label id="fileHint"></label><input type="file" id="fileInput"></div>
<div id="categoryRow" style="display:none"><label>品类</label><input id="categoryInput" placeholder="CABINET/HOME_MIRROR"></div>
<label style="display:flex;gap:8px;align-items:center;margin:8px 0"><input type="checkbox" id="autoConfirm" value="true"><span>Auto Confirm</span></label>
<div style="display:flex;gap:8px;margin-top:10px"><button id="runBtn">开始运行</button><button class="secondary" id="cancelBtn">取消</button></div>
</div></div>
<div id="toast"></div>
<script>
const tasks=[
{id:'1.1',name:'同步全量Giga收藏商品详情',code:'sync-products'},
{id:'1.2',name:'导入亚马逊全量listing数据',code:'import-amz-report',file:true,fileHint:'上传Amazon报告 .txt'},
{id:'1.3',name:'更新亚马逊父品发品状态',code:'update-listing-status'},
{id:'1.4',name:'使用AI生成商品详情（并自动映射SKU）',code:'generate-details'},
{id:'1.5',name:'同步Giga商品价格',code:'sync-prices'},
{id:'1.6',name:'同步Giga商品库存',code:'sync-inventory'},
{id:'1.7',name:'更新售价',code:'update-prices'},
{id:'1.8',name:'生成亚马逊发品文件',code:'generate-listing',category:true},
{id:'2.1',name:'查看数据统计',code:'view-statistics'},
{id:'2.2',name:'查看待发品统计',code:'pending-statistics'},
{id:'2.3',name:'查看最近发品记录',code:'recent-listings'},
{id:'3.1',name:'列出所有可用品类',code:'list-categories'},
{id:'3.2',name:'解析新的亚马逊类目模板到数据库',code:'template-update',file:true,fileHint:'上传模板 .xlsm',category:true},
{id:'3.3',name:'从亚马逊报错文件自动矫正模板规则',code:'template-correction',file:true,fileHint:'上传报错文件 .xlsm',category:true},
{id:'3.4',name:'更新需要维护的品类(来自Giga)',code:'sync-giga-categories'},
{id:'3.5',name:'从CSV批量更新品类映射',code:'update-mappings-from-csv',file:true,fileHint:'上传CSV'},
{id:'4.1',name:'从CSV批量同步SKU映射(未实现)',code:'sku-sync-from-csv',disabled:true},
{id:'5.1',name:'(一键) 生成亚马逊价格与库存更新文件',code:'generate-update-file'}
];
const tbody=document.getElementById('tbody');
tasks.forEach(t=>{const tr=document.createElement('tr');tr.innerHTML=`<td>${t.id}</td><td>${t.name}</td><td>${t.disabled?'<span style="color:#999">不可用</span>':'<button data-code="'+t.code+'" data-file="'+(t.file?'1':'0')+'" data-category="'+(t.category?'1':'0')+'">运行</button>'}</td>`;tbody.appendChild(tr)});
function toast(s){const t=document.getElementById('toast');t.textContent=s;t.style.display='block';setTimeout(()=>t.style.display='none',2500)}
let current={};const modal=document.getElementById('modal');const fileRow=document.getElementById('fileRow');const categoryRow=document.getElementById('categoryRow');const fileHint=document.getElementById('fileHint');const fileInput=document.getElementById('fileInput');const categoryInput=document.getElementById('categoryInput');const autoConfirm=document.getElementById('autoConfirm');const modalTitle=document.getElementById('modalTitle');
tbody.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;current={code:b.dataset.code,file:b.dataset.file==='1',category:b.dataset.category==='1'};modalTitle.textContent=tasks.find(x=>x.code===current.code)?.name||'';fileRow.style.display=current.file?'block':'none';categoryRow.style.display=current.category?'block':'none';fileInput.value='';categoryInput.value='';autoConfirm.checked=false;modal.style.display='flex'});
document.getElementById('cancelBtn').onclick=()=>{modal.style.display='none'};
document.getElementById('runBtn').onclick=async()=>{try{const fd=new FormData();fd.append('task',current.code);if(current.category){fd.append('category',categoryInput.value||'')}if(autoConfirm.checked){fd.append('auto_confirm','true')}if(current.file){const f=fileInput.files[0];if(!f){toast('请选择文件');return}fd.append('file',f,f.name)}const r=await fetch('/run',{method:'POST',body:fd});const ct=r.headers.get('Content-Type')||'';const cd=r.headers.get('Content-Disposition')||'';if(ct.includes('application/zip')||ct.includes('application/octet-stream')||cd.includes('attachment')){const blob=await r.blob();let filename='output.zip';const m=/filename=\"?([^\";]+)\"?/i.exec(cd);if(m)filename=m[1];const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=filename;document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(a.href);toast('下载开始');}else{const text=await r.text();toast(text.slice(0,200))}modal.style.display='none'}catch(e){toast('请求失败')}}
</script>
</body></html>"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
            return
        if self.path == "/" or self.path.startswith("/index"):
            data = INDEX_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
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
    port = int(os.getenv("PORT") or os.getenv("IO_SERVER_PORT", "8080"))
    host = os.getenv("IO_SERVER_HOST", "0.0.0.0")
    server = HTTPServer((host, port), Handler)
    server.serve_forever()

if __name__ == "__main__":
    run()

