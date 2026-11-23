"""Dịch vụ đóng dấu PDF cho đề thi: mỗi request đóng dấu đúng một file cho một sinh viên.

Luồng: trình duyệt gửi PDF + logo một lần (POST /api/docs) -> nhận doc_id;
sau đó đọc CSV và gửi từng request nhỏ (POST /api/watermark) kèm doc_id;
cuối cùng tự gộp các PDF nhận về thành ZIP.
"""
import hashlib
import json
import math
import os
import shutil
import socket
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

import boto3
import pymupdf
from botocore.exceptions import ClientError
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, create_engine

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


# ============================================================================
# CẤU HÌNH: mọi tham số đều đọc từ biến môi trường (.env), có giá trị mặc định
# ============================================================================
def cfg(name, default):
    return type(default)(os.getenv(name, default))


# --- AWS / dữ liệu ---
S3_BUCKET = cfg("S3_BUCKETs", "uet-pdf-watermark")
AWS_REGION = cfg("AWS_REGION", "ap-southeast-1")
DB_URL = os.getenv("DB_URL") or "sqlite:////tmp/audit.db"
CACHE_DIR = cfg("CACHE_DIR", "/tmp/wm_cache")  # cache PDF/logo trên ổ EBS của từng máy
CACHE_TTL_HOURS = cfg("CACHE_TTL_HOURS", 6.0)  # thư mục cache cũ hơn số giờ này sẽ bị xóa
WORKERS = cfg("WORKERS", 2)  # số tiến trình uvicorn, nên bằng số vCPU

# --- Giới hạn (chỉ trình duyệt kiểm tra, server không kiểm tra) ---
MAX_PDF_MB = cfg("MAX_PDF_MB", 10.0)
MAX_LOGO_KB = cfg("MAX_LOGO_KB", 200.0)
MAX_CSV_ROWS = cfg("MAX_CSV_ROWS", 300)
MAX_PARALLEL = cfg("MAX_PARALLEL", 6)  # số request đóng dấu chạy song song mỗi trình duyệt
MAX_RETRIES = cfg("MAX_RETRIES", 2)  # số lần thử lại khi một request lỗi

# --- Watermark ---
FONT_PATH = cfg("FONT_PATH", str(Path(__file__).parent / "fonts" / "DejaVuSans.ttf"))
WM_ANGLE = cfg("WM_ANGLE", 45.0)  # góc nghiêng (độ), chữ chạy từ dưới-trái lên trên-phải
WM_FONTSIZE = cfg("WM_FONTSIZE", 30.0)  # cỡ chữ tối đa của dòng chính
WM_SUB_RATIO = cfg("WM_SUB_RATIO", 0.45)  # cỡ chữ dòng phụ (timestamp) so với dòng chính
WM_OPACITY = cfg("WM_OPACITY", 0.2)
WM_COLOR = (0.7, 0.15, 0.15)
LOGO_WIDTH = cfg("LOGO_WIDTH", 80.0)  # khung logo ở góc trên bên phải
LOGO_HEIGHT = cfg("LOGO_HEIGHT", 50.0)
LOGO_MARGIN = cfg("LOGO_MARGIN", 20.0)

VN_TZ = timezone(timedelta(hours=7))
HOST = socket.gethostname()

# ============================================================================
# KHỞI TẠO
# ============================================================================
s3 = boto3.client("s3", region_name=AWS_REGION)
FONT = pymupdf.Font(fontfile=FONT_PATH)
PDF_LOCK = Lock()  # PyMuPDF không an toàn khi chạy đa luồng: mỗi tiến trình chỉ đóng dấu một file một lúc
Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)

engine = create_engine(DB_URL, pool_pre_ping=True)
log_table = Table(
    "watermark_logs",
    MetaData(),
    Column("id", Integer, primary_key=True),
    Column("created_at", DateTime, default=lambda: datetime.now(timezone.utc)),
    Column("student_id", String(64)),
    Column("full_name", String(128)),
    Column("doc_id", String(36)),
    Column("sha256", String(64), index=True),
    Column("worker_host", String(100)),
)
try:
    log_table.metadata.create_all(engine)
except Exception as e:
    print(f"[WARN] Không tạo được bảng watermark_logs: {e}")

app = FastAPI(title="PDF Watermarking")


# ============================================================================
# CACHE PDF / LOGO TRÊN EBS
# ============================================================================
def cleanup_cache():
    cutoff = time.time() - CACHE_TTL_HOURS * 3600
    for d in os.scandir(CACHE_DIR):
        if d.is_dir() and d.stat().st_mtime < cutoff:
            shutil.rmtree(d.path, ignore_errors=True)


def get_doc_files(doc_id: str):
    """Trả về (đường dẫn PDF, đường dẫn logo hoặc None). Dùng cache nếu có, không thì tải từ S3."""
    try:
        uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(404, "doc_id không hợp lệ")

    d = Path(CACHE_DIR) / doc_id
    if not d.exists():
        cleanup_cache()
        # Tải vào thư mục tạm rồi đổi tên một lần, để request khác không đọc phải file đang tải dở
        tmp = Path(CACHE_DIR) / f".tmp-{uuid.uuid4().hex}"
        tmp.mkdir()
        try:
            try:
                s3.download_file(S3_BUCKET, f"docs/{doc_id}/input.pdf", str(tmp / "input.pdf"))
            except ClientError:
                raise HTTPException(404, "Không tìm thấy tài liệu (có thể đã hết hạn)")
            try:
                s3.download_file(S3_BUCKET, f"docs/{doc_id}/logo", str(tmp / "logo"))
            except ClientError as e:
                if e.response["Error"]["Code"] not in ("404", "NoSuchKey"):
                    raise
            try:
                os.replace(tmp, d)
            except OSError:
                pass  # request khác đã tạo xong thư mục này trước
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    logo = d / "logo"
    return d / "input.pdf", (logo if logo.exists() else None)


# ============================================================================
# ĐÓNG DẤU
# ============================================================================
def stamp_pdf(pdf_path: Path, logo_path: Optional[Path], line1: str, line2: str) -> bytes:
    logo = logo_path.read_bytes() if logo_path else None
    ang = math.radians(WM_ANGLE)
    dx, dy = math.cos(ang), -math.sin(ang)  # hướng chạy của chữ (hệ tọa độ trang: y hướng xuống)
    px, py = math.sin(ang), math.cos(ang)  # hướng vuông góc, trỏ xuống dưới dòng chữ

    with PDF_LOCK:
        doc = pymupdf.open(pdf_path)
        logo_xref = 0
        for page in doc:
            w, h = page.rect.width, page.rect.height
            cx, cy = w / 2, h / 2

            # Cỡ chữ: vừa trong trang theo hướng nghiêng, tối đa WM_FONTSIZE
            max_len = 0.85 * min(w / max(abs(dx), 1e-6), h / max(abs(dy), 1e-6))
            fs = min(WM_FONTSIZE, max_len / FONT.text_length(line1, fontsize=1))

            def put(text, size, offset):
                length = FONT.text_length(text, fontsize=size)
                p = pymupdf.Point(cx + offset * px - length / 2 * dx, cy + offset * py - length / 2 * dy)
                page.insert_text(
                    p, text, fontsize=size, fontname="wm", fontfile=FONT_PATH,
                    color=WM_COLOR, fill_opacity=WM_OPACITY,
                    morph=(p, pymupdf.Matrix(WM_ANGLE)),
                )

            put(line1, fs, 0)
            put(line2, fs * WM_SUB_RATIO, fs * 0.9)

            if logo:
                rect = pymupdf.Rect(w - LOGO_MARGIN - LOGO_WIDTH, 14, w - LOGO_MARGIN, 14 + LOGO_HEIGHT)
                # Lần đầu chèn ảnh, các trang sau tham chiếu lại cùng một đối tượng ảnh (xref)
                logo_xref = page.insert_image(
                    rect, stream=None if logo_xref else logo, xref=logo_xref, keep_proportion=True
                )

        doc.subset_fonts()  # chỉ giữ các ký tự đã dùng, tránh nhúng cả font ~750 KB vào mỗi file
        out = doc.tobytes(garbage=3, deflate=True)
        doc.close()
    return out


# ============================================================================
# API
# ============================================================================
@app.get("/health")
def health():
    return {"status": "ok", "host": HOST}


@app.post("/api/docs")
def upload_doc(pdf: UploadFile = File(...), logo: Optional[UploadFile] = File(None)):
    """Nhận PDF (và logo nếu có) một lần, lưu vào S3, trả doc_id."""
    doc_id = str(uuid.uuid4())
    s3.put_object(Bucket=S3_BUCKET, Key=f"docs/{doc_id}/input.pdf", Body=pdf.file.read())
    if logo is not None and logo.filename:
        data = logo.file.read()
        if data:
            s3.put_object(Bucket=S3_BUCKET, Key=f"docs/{doc_id}/logo", Body=data)
    return {"doc_id": doc_id}


@app.post("/api/watermark")
def watermark(student_id: str = Form(...), full_name: str = Form(...), doc_id: str = Form(...)):
    """Đóng dấu một file PDF cho một sinh viên, trả PDF trực tiếp."""
    student_id, full_name = student_id.strip(), full_name.strip()
    pdf_path, logo_path = get_doc_files(doc_id)
    now = datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M:%S")

    try:
        out = stamp_pdf(pdf_path, logo_path, f"{full_name} - {student_id}", now)
    except Exception as e:
        raise HTTPException(500, f"Lỗi khi đóng dấu PDF: {e}")

    digest = hashlib.sha256(out).hexdigest()
    try:
        with engine.begin() as conn:
            conn.execute(log_table.insert().values(
                student_id=student_id, full_name=full_name, doc_id=doc_id, sha256=digest, worker_host=HOST,
            ))
    except Exception as e:
        print(f"[WARN] Không ghi được nhật ký: {e}")

    return Response(out, media_type="application/pdf", headers={"X-Worker-Host": HOST})


# ============================================================================
# TRANG WEB
# ============================================================================
PAGE = r"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Đóng dấu đề thi</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js"></script>
<style>
  :root { color-scheme: light dark; --fg:#1b2430; --bg:#f6f7f9; --card:#fff; --line:#d5dae1; --accent:#1f5fbf; --bad:#b3261e; --ok:#1b7a3d; }
  @media (prefers-color-scheme: dark) { :root { --fg:#e6e9ee; --bg:#14181d; --card:#1d232a; --line:#333c47; --accent:#6ea2f0; --bad:#f2918a; --ok:#6fcf8f; } }
  * { box-sizing: border-box; }
  body { margin:0; padding:32px 16px; background:var(--bg); color:var(--fg); font:16px/1.5 system-ui, "Segoe UI", Roboto, sans-serif; }
  main { max-width:640px; margin:0 auto; background:var(--card); border:1px solid var(--line); border-radius:8px; padding:28px; }
  h1 { margin:0 0 4px; font-size:1.4rem; }
  p.sub { margin:0 0 24px; color:var(--fg); opacity:.7; }
  label { display:block; margin:16px 0 4px; font-weight:600; }
  .hint { font-size:.875rem; opacity:.7; margin-top:2px; }
  input[type=file] { width:100%; padding:8px; border:1px solid var(--line); border-radius:6px; background:var(--bg); color:var(--fg); }
  button { margin-top:24px; width:100%; padding:12px; border:0; border-radius:6px; background:var(--accent); color:#fff; font:inherit; font-weight:600; cursor:pointer; }
  button:disabled { opacity:.5; cursor:not-allowed; }
  :focus-visible { outline:3px solid var(--accent); outline-offset:2px; }
  progress { width:100%; height:14px; margin-top:24px; }
  #status { margin-top:8px; }
  #errors { margin-top:12px; color:var(--bad); font-size:.9rem; word-break:break-word; }
  .ok { color:var(--ok); }
</style>
</head>
<body>
<main>
  <h1>Đóng dấu đề thi</h1>
  <p class="sub">Tạo một bản đề có tên và mã sinh viên cho từng người trong danh sách, đóng gói thành một file ZIP.</p>
  <form id="form">
    <label for="pdf">Đề thi (PDF)</label>
    <input type="file" id="pdf" accept="application/pdf" required>
    <div class="hint" id="pdfHint"></div>

    <label for="csv">Danh sách sinh viên (CSV)</label>
    <input type="file" id="csv" accept=".csv,text/csv" required>
    <div class="hint" id="csvHint"></div>

    <label for="logo">Logo (không bắt buộc)</label>
    <input type="file" id="logo" accept="image/png,image/jpeg">
    <div class="hint" id="logoHint"></div>

    <button type="submit" id="go">Tạo và tải file ZIP</button>
  </form>
  <progress id="bar" value="0" max="1" hidden></progress>
  <div id="status" role="status"></div>
  <div id="errors"></div>
</main>

<script>
const CFG = __CONFIG__;
const $ = id => document.getElementById(id);
let running = false;

$('pdfHint').textContent = `Tối đa ${CFG.max_pdf_mb} MB.`;
$('csvHint').textContent = `Dòng đầu là tiêu đề, có cột student_id (hoặc msv) và full_name (hoặc ho_ten). Tối đa ${CFG.max_csv_rows} sinh viên.`;
$('logoHint').textContent = `PNG hoặc JPG, tối đa ${CFG.max_logo_kb} KB. Nếu bỏ trống, đề được đóng dấu không có logo.`;

window.addEventListener('beforeunload', e => {
  if (running) { e.preventDefault(); e.returnValue = ''; }
});

function parseCSV(text) {
  text = text.replace(/^\uFEFF/, '');
  const first = text.split('\n')[0];
  const delim = (first.match(/;/g) || []).length > (first.match(/,/g) || []).length ? ';' : ',';
  const rows = []; let row = [], cur = '', quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"') { if (text[i + 1] === '"') { cur += '"'; i++; } else quoted = false; }
      else cur += c;
    } else if (c === '"') quoted = true;
    else if (c === delim) { row.push(cur); cur = ''; }
    else if (c === '\n') { row.push(cur); rows.push(row); row = []; cur = ''; }
    else if (c !== '\r') cur += c;
  }
  if (cur || row.length) { row.push(cur); rows.push(row); }
  return rows.filter(r => r.some(x => x.trim()));
}

function readStudents(text) {
  const rows = parseCSV(text);
  if (rows.length < 2) throw new Error('File CSV không có dòng dữ liệu nào.');
  const head = rows[0].map(x => x.trim().toLowerCase());
  const iId = head.findIndex(h => ['student_id', 'msv', 'mssv'].includes(h));
  const iName = head.findIndex(h => ['full_name', 'ho_ten', 'hoten'].includes(h));
  if (iId < 0 || iName < 0) throw new Error('Dòng tiêu đề CSV cần có cột student_id (hoặc msv) và full_name (hoặc ho_ten).');
  const list = rows.slice(1)
    .map(r => ({ id: (r[iId] || '').trim(), name: (r[iName] || '').trim() }))
    .filter(s => s.id && s.name);
  if (!list.length) throw new Error('File CSV không có sinh viên hợp lệ.');
  if (list.length > CFG.max_csv_rows) throw new Error(`File CSV có ${list.length} sinh viên, vượt giới hạn ${CFG.max_csv_rows}.`);
  return list;
}

$('form').addEventListener('submit', async e => {
  e.preventDefault();
  $('errors').textContent = ''; $('status').className = '';
  const pdf = $('pdf').files[0], csv = $('csv').files[0], logo = $('logo').files[0];

  let students;
  try {
    if (pdf.size > CFG.max_pdf_mb * 1048576) throw new Error(`File PDF lớn hơn ${CFG.max_pdf_mb} MB.`);
    if (logo && logo.size > CFG.max_logo_kb * 1024) throw new Error(`File logo lớn hơn ${CFG.max_logo_kb} KB.`);
    students = readStudents(await csv.text());
  } catch (err) { $('errors').textContent = err.message; return; }

  running = true; $('go').disabled = true;
  const bar = $('bar'); bar.hidden = false; bar.max = students.length; bar.value = 0;
  let done = 0; const failed = [];
  const render = () => {
    bar.value = done + failed.length;
    $('status').textContent = `Đã xong ${done}, lỗi ${failed.length} / ${students.length}`;
  };

  try {
    $('status').textContent = 'Đang tải đề lên...';
    const up = new FormData(); up.append('pdf', pdf); if (logo) up.append('logo', logo);
    const r = await fetch('/api/docs', { method: 'POST', body: up });
    if (!r.ok) throw new Error('Không tải được đề lên hệ thống.');
    const docId = (await r.json()).doc_id;

    const zip = new JSZip(), used = {};
    const zipName = id => {
      const base = id.replace(/[^\w.-]/g, '_');
      used[base] = (used[base] || 0) + 1;
      return (used[base] > 1 ? `${base}_${used[base]}` : base) + '.pdf';
    };

    const one = async s => {
      for (let attempt = 0; attempt <= CFG.max_retries; attempt++) {
        try {
          const fd = new FormData();
          fd.append('student_id', s.id); fd.append('full_name', s.name); fd.append('doc_id', docId);
          const res = await fetch('/api/watermark', { method: 'POST', body: fd });
          if (res.ok) { zip.file(zipName(s.id), await res.blob()); return true; }
        } catch (_) { /* thử lại */ }
      }
      return false;
    };

    render();
    let next = 0;
    const lane = async () => {
      while (next < students.length) {
        const s = students[next++];
        (await one(s)) ? done++ : failed.push(s);
        render();
      }
    };
    await Promise.all(Array.from({ length: Math.min(CFG.max_parallel, students.length) }, lane));

    if (done > 0) {
      const blob = await zip.generateAsync({ type: 'blob' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob); a.download = 'de-thi-da-dong-dau.zip'; a.click();
    }
    if (failed.length) $('errors').textContent = 'Các sinh viên bị lỗi, chưa có trong file ZIP: ' + failed.map(s => s.id).join(', ');
    else { $('status').className = 'ok'; $('status').textContent += '. Hoàn tất.'; }
  } catch (err) {
    $('errors').textContent = err.message;
  } finally {
    running = false; $('go').disabled = false;
  }
});
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index():
    config = {
        "max_pdf_mb": MAX_PDF_MB,
        "max_logo_kb": MAX_LOGO_KB,
        "max_csv_rows": MAX_CSV_ROWS,
        "max_parallel": MAX_PARALLEL,
        "max_retries": MAX_RETRIES,
    }
    return PAGE.replace("__CONFIG__", json.dumps(config))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, workers=WORKERS)
