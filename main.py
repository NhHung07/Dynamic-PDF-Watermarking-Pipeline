import os
import re
import time
import socket
import hashlib
from typing import Optional

import boto3
import pymupdf as fitz
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, inspect, text

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = FastAPI(title="Dynamic PDF Watermarking Pipeline - UET")

DB_URL = os.getenv("DB_URL") or os.getenv("DATABASE_URL") or "sqlite:////tmp/audit.db"
S3_BUCKET = os.getenv("S3_BUCKET", "uet-pdf-watermark")
EFS_DIR = os.getenv("EFS_DIR", "/mnt/efs")
AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-1")

if not os.path.isdir(EFS_DIR) or not os.access(EFS_DIR, os.W_OK):
    EFS_DIR = "/tmp/watermark_efs_fallback"

os.makedirs(os.path.join(EFS_DIR, "input"), exist_ok=True)
os.makedirs("/tmp/wm_work", exist_ok=True)

engine = create_engine(DB_URL, pool_pre_ping=True)
s3_client = boto3.client("s3", region_name=AWS_REGION)

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]
UNICODE_FONT = next((p for p in FONT_CANDIDATES if os.path.exists(p)), None)


def sanitize_code(raw_name: str) -> str:
    base = os.path.splitext(raw_name)[0]
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", base).strip("_")
    return cleaned or f"doc_{int(time.time())}"


def list_available_docs() -> list[str]:
    docs = []
    try:
        resp = s3_client.list_objects_v2(Bucket=S3_BUCKET, Prefix="input/")
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            if key.lower().endswith(".pdf"):
                docs.append(os.path.splitext(os.path.basename(key))[0])
    except Exception:
        pass
    return docs or ["ModelOptimization", "giaotrinh_301"]


def log_audit(student_id: str, full_name: str, doc_code: str, sha256_hash: str, worker_host: str, output_key: str):
    try:
        insp = inspect(engine)
        if not insp.has_table("audit_logs"):
            return
        cols = {c["name"] for c in insp.get_columns("audit_logs")}
        candidate_values = {
            "student_id": student_id,
            "full_name": full_name,
            "doc_code": doc_code,
            "sha256": sha256_hash,
            "file_hash": sha256_hash,
            "worker_host": worker_host,
            "output_key": output_key,
            "s3_key": output_key,
        }
        insert_cols = [k for k in candidate_values if k in cols]
        if not insert_cols:
            return
        col_list = ", ".join(insert_cols)
        val_list = ", ".join(f":{k}" for k in insert_cols)
        sql = text(f"INSERT INTO audit_logs ({col_list}) VALUES ({val_list})")
        with engine.begin() as conn:
            conn.execute(sql, {k: candidate_values[k] for k in insert_cols})
    except Exception as e:
        print(f"[WARN] Audit log insert skipped: {e}")


@app.get("/health")
def health_check():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "healthy", "host": socket.gethostname()}


@app.get("/", response_class=HTMLResponse)
def index():
    docs = list_available_docs()
    options_html = "\n".join(
        f'<option value="{d}">{d}.pdf (Có sẵn trên S3)</option>' for d in docs
    )
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Hệ thống Cấp phát Tài liệu Đóng dấu Bản quyền Động</title>
  <style>
    * {{ box-sizing: border-box; font-family: 'Segoe UI', Roboto, Arial, sans-serif; }}
    body {{ background: #f0f4f8; margin: 0; padding: 32px 16px; color: #1e293b; }}
    .container {{ max-width: 680px; margin: 0 auto; background: #ffffff; border-radius: 12px;
                  box-shadow: 0 10px 25px rgba(15, 23, 42, 0.08); padding: 32px; }}
    .header {{ border-bottom: 2px solid #e2e8f0; padding-bottom: 16px; margin-bottom: 24px; }}
    .header h1 {{ margin: 0 0 6px; font-size: 22px; color: #0f172a; }}
    .header p {{ margin: 0; font-size: 14px; color: #64748b; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    @media (max-width: 600px) {{ .grid {{ grid-template-columns: 1fr; }} }}
    .field {{ margin-bottom: 18px; }}
    label {{ display: block; font-weight: 600; font-size: 14px; margin-bottom: 6px; color: #334155; }}
    .hint {{ font-size: 12px; color: #64748b; margin-top: 4px; }}
    input[type="text"], select, input[type="file"] {{
      width: 100%; padding: 10px 12px; border: 1px solid #cbd5e1; border-radius: 8px;
      font-size: 14px; background: #f8fafc; transition: border-color 0.2s;
    }}
    input[type="text"]:focus, select:focus {{ outline: none; border-color: #2563eb; background: #fff; }}
    .box {{ background: #f8fafc; border: 1px dashed #94a3b8; border-radius: 8px; padding: 14px; margin-bottom: 18px; }}
    button {{
      width: 100%; padding: 13px; background: #2563eb; color: #fff; border: none;
      border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer;
    }}
    button:hover {{ background: #1d4ed8; }}
    button:disabled {{ background: #94a3b8; cursor: not-allowed; }}
    .result {{ margin-top: 24px; padding: 18px; border-radius: 8px; background: #ecfdf5;
               border: 1px solid #10b981; display: none; }}
    .result.error {{ background: #fef2f2; border-color: #ef4444; }}
    .meta {{ font-size: 13px; line-height: 1.7; word-break: break-all; }}
    .download-btn {{
      display: inline-block; margin-top: 12px; padding: 10px 18px; background: #059669;
      color: #fff; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 14px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Dynamic PDF Watermarking</h1>
    </div>

    <form id="wmForm">
      <div class="grid">
        <div class="field">
          <label for="student_id">Mã sinh viên *</label>
          <input type="text" id="student_id" name="student_id" placeholder="VD: 24021507" required />
        </div>
        <div class="field">
          <label for="full_name">Họ và tên sinh viên *</label>
          <input type="text" id="full_name" name="full_name" placeholder="VD: Trần Nhật Hưng" required />
        </div>
      </div>

      <div class="box">
        <div class="field" style="margin-bottom: 0;">
          <label for="logo_file">Tải Logo đóng dấu (PNG / JPG)</label>
          <input type="file" id="logo_file" name="logo_file" accept="image/png,image/jpeg" />
          <div class="hint">Logo sẽ được chèn vào góc trên bên phải mỗi trang. Nếu bỏ trống, hệ thống dùng con dấu mặc định UET-VNU.</div>
        </div>
      </div>

      <div class="box">
        <div class="field">
          <label for="pdf_file">Tải tài liệu PDF từ máy tính (Tùy chọn)</label>
          <input type="file" id="pdf_file" name="pdf_file" accept="application/pdf" />
          <div class="hint">File tải lên sẽ được lưu tự động lên S3 & đồng bộ EFS cho toàn bộ cụm Worker.</div>
        </div>
        <div class="field" style="margin-bottom: 0;">
          <label for="doc_code">Hoặc chọn tài liệu có sẵn trên S3</label>
          <select id="doc_code" name="doc_code">
            {options_html}
          </select>
        </div>
      </div>

      <button type="submit" id="submitBtn">Tạo & Tải tài liệu Bản quyền</button>
    </form>

    <div id="resultBox" class="result"></div>
  </div>

  <script>
    const form = document.getElementById('wmForm');
    const btn = document.getElementById('submitBtn');
    const resBox = document.getElementById('resultBox');

    form.addEventListener('submit', async (e) => {{
      e.preventDefault();
      btn.disabled = true;
      btn.textContent = 'Đang xử lý đóng dấu trên EC2 Worker...';
      resBox.style.display = 'none';

      const formData = new FormData(form);
      const pdfInput = document.getElementById('pdf_file');
      const logoInput = document.getElementById('logo_file');
      if (!pdfInput.files.length) formData.delete('pdf_file');
      if (!logoInput.files.length) formData.delete('logo_file');

      try {{
        const resp = await fetch('/api/watermark', {{ method: 'POST', body: formData }});
        const data = await resp.json();
        resBox.style.display = 'block';
        if (!resp.ok) {{
          resBox.className = 'result error';
          resBox.innerHTML = '<strong>Lỗi xử lý:</strong> ' + (data.detail || 'Không xác định');
        }} else {{
          resBox.className = 'result';
          resBox.innerHTML = `
            <div class="meta">
              <strong>Trạng thái:</strong> Đóng dấu hoàn tất!<br/>
              <strong>EC2 Worker xử lý:</strong> <code>${{data.worker_host}}</code><br/>
              <strong>Tài liệu:</strong> <code>${{data.doc_code}}.pdf</code><br/>
              <strong>SHA-256 định danh:</strong> <code>${{data.sha256}}</code>
            </div>
            <a class="download-btn" href="${{data.download_url}}" target="_blank">Tải xuống tài liệu PDF (Pre-signed URL)</a>
          `;
        }}
      }} catch (err) {{
        resBox.style.display = 'block';
        resBox.className = 'result error';
        resBox.innerHTML = '<strong>Lỗi kết nối:</strong> ' + err.message;
      }} finally {{
        btn.disabled = false;
        btn.textContent = 'Tạo & Tải tài liệu Bản quyền';
      }}
    }});
  </script>
</body>
</html>"""


@app.post("/api/watermark")
async def create_watermark(
    student_id: str = Form(...),
    full_name: str = Form(...),
    doc_code: str = Form("ModelOptimization"),
    pdf_file: Optional[UploadFile] = File(None),
    logo_file: Optional[UploadFile] = File(None),
):
    worker_host = socket.gethostname()
    timestamp = int(time.time())

    if pdf_file is not None and pdf_file.filename:
        if not pdf_file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Chỉ chấp nhận tệp định dạng PDF.")
        pdf_bytes = await pdf_file.read()
        if not pdf_bytes:
            raise HTTPException(status_code=400, detail="Tệp PDF tải lên bị rỗng.")
        doc_code = sanitize_code(pdf_file.filename)
        input_key = f"input/{doc_code}.pdf"
        cached_input_path = os.path.join(EFS_DIR, "input", f"{doc_code}.pdf")
        with open(cached_input_path, "wb") as f:
            f.write(pdf_bytes)
        s3_client.upload_file(cached_input_path, S3_BUCKET, input_key)
    else:
        doc_code = sanitize_code(doc_code)
        input_key = f"input/{doc_code}.pdf"
        cached_input_path = os.path.join(EFS_DIR, "input", f"{doc_code}.pdf")
        if not os.path.exists(cached_input_path):
            try:
                s3_client.head_object(Bucket=S3_BUCKET, Key=input_key)
                s3_client.download_file(S3_BUCKET, input_key, cached_input_path)
            except Exception as e:
                raise HTTPException(status_code=404, detail=f"Không tìm thấy PDF trên S3: {e}")

    logo_bytes = None
    if logo_file is not None and logo_file.filename:
        logo_bytes = await logo_file.read()
        if not logo_bytes:
            logo_bytes = None

    out_filename = f"{student_id}_{doc_code}_{timestamp}.pdf"
    local_out_path = os.path.join("/tmp/wm_work", out_filename)
    watermark_text = f"{student_id} - {full_name.upper()}"

    font_kwargs = {"fontfile": UNICODE_FONT, "fontname": "dejavu"} if UNICODE_FONT else {}

    try:
        doc = fitz.open(cached_input_path)
        for page in doc:
            rect = page.rect
            page.insert_text(
                (42, 28),
                f"{watermark_text} | {doc_code}",
                fontsize=9,
                color=(0.75, 0.15, 0.15),
                **font_kwargs,
            )
            page.insert_text(
                (42, rect.height - 20),
                f"Tài liệu cấp phát cho SV {full_name} ({student_id})",
                fontsize=8,
                color=(0.4, 0.4, 0.4),
                **font_kwargs,
            )
            if logo_bytes:
                logo_rect = fitz.Rect(rect.width - 110, 14, rect.width - 30, 64)
                page.insert_image(logo_rect, stream=logo_bytes, keep_proportion=True)
            else:
                stamp_rect = fitz.Rect(rect.width - 125, 16, rect.width - 35, 42)
                page.draw_rect(stamp_rect, color=(0.8, 0.1, 0.1), width=1.2)
                page.insert_text(
                    (rect.width - 118, 33),
                    "UET - VNU",
                    fontsize=10,
                    color=(0.8, 0.1, 0.1),
                )
        doc.save(local_out_path, garbage=3, deflate=True)
        doc.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý PDF/Logo: {e}")

    sha256_hash = hashlib.sha256()
    with open(local_out_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256_hash.update(chunk)
    digest = sha256_hash.hexdigest()

    output_key = f"output/{out_filename}"
    s3_client.upload_file(local_out_path, S3_BUCKET, output_key)
    os.remove(local_out_path)

    presigned_url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": output_key},
        ExpiresIn=3600,
    )

    log_audit(student_id, full_name, doc_code, digest, worker_host, output_key)

    return {
        "worker_host": worker_host,
        "doc_code": doc_code,
        "sha256": digest,
        "download_url": presigned_url,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
