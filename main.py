import os
import re
import math
import time
import socket
import hashlib
import uuid
import json
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

import boto3
from botocore.exceptions import ClientError
import pymupdf
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Header, Query, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel, Field
import sqlalchemy as sa
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float, DateTime, select, desc, text

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ==============================================================================
# 1. CẤU HÌNH HỆ THỐNG & KHỞI TẠO DỊCH VỤ
# ==============================================================================
SERVICE_NAME = "PDF-Watermarking-Microservice"
SERVICE_VERSION = "2.1.0"

DB_URL = os.getenv("DB_URL") or os.getenv("DATABASE_URL") or "sqlite:////tmp/audit.db"
S3_BUCKET = os.getenv("S3_BUCKET", "uet-pdf-watermark")
EFS_DIR = os.getenv("EFS_DIR", "/mnt/efs")
AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-1")
API_KEY = os.getenv("API_KEY", "")  # Để trống nếu không yêu cầu xác thực API Key

# Múi giờ Việt Nam (UTC+7 / GMT+7)
VN_TIMEZONE = timezone(timedelta(hours=7))

# Thiết lập thư mục EFS cache (với fallback cục bộ nếu EFS chưa mount)
if not os.path.isdir(EFS_DIR) or not os.access(EFS_DIR, os.W_OK):
    EFS_DIR = "/tmp/watermark_efs_fallback"

os.makedirs(os.path.join(EFS_DIR, "input"), exist_ok=True)
os.makedirs("/tmp/wm_work", exist_ok=True)

# Khởi tạo kết nối SQLAlchemy & Boto3 S3
engine = create_engine(DB_URL, pool_pre_ping=True)
s3_client = boto3.client("s3", region_name=AWS_REGION)

# ==============================================================================
# 2. TỰ ĐỘNG KHỞI TẠO CƠ SỞ DỮ LIỆU AUDIT LOGS (SCHEMA QUẢN TRỊ MICROSERVICE)
# ==============================================================================
metadata = MetaData()
audit_logs = Table(
    "audit_logs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("request_id", String(64), index=True),
    Column("client_id", String(64), index=True, default="default"),
    Column("doc_name", String(255)),
    Column("pages_count", Integer, default=0),
    Column("sha256", String(64), index=True),
    Column("worker_host", String(100)),
    Column("output_key", String(255)),
    Column("processing_time_ms", Float),
    Column("created_at", DateTime, default=lambda: datetime.now(timezone.utc)),
    # Các trường mở rộng & tương thích ngược với đề tài cũ
    Column("student_id", String(64), nullable=True),
    Column("full_name", String(128), nullable=True),
    Column("doc_code", String(128), nullable=True),
    Column("metadata_json", String(1024), nullable=True),
)

# Tự động tạo bảng nếu chưa có & tự động thêm các cột mới vào RDS PostgreSQL/MySQL
def init_and_migrate_db():
    try:
        insp = sa.inspect(engine)
        if not insp.has_table("audit_logs"):
            metadata.create_all(engine)
        else:
            existing_cols = {c["name"] for c in insp.get_columns("audit_logs")}
            new_columns = [
                ("request_id", "VARCHAR(64)"),
                ("client_id", "VARCHAR(64)"),
                ("doc_name", "VARCHAR(255)"),
                ("pages_count", "INTEGER DEFAULT 0"),
                ("sha256", "VARCHAR(64)"),
                ("worker_host", "VARCHAR(100)"),
                ("output_key", "VARCHAR(255)"),
                ("processing_time_ms", "FLOAT"),
                ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
                ("student_id", "VARCHAR(64)"),
                ("full_name", "VARCHAR(128)"),
                ("doc_code", "VARCHAR(128)"),
                ("metadata_json", "TEXT"),
            ]
            with engine.begin() as conn:
                for c_name, c_type in new_columns:
                    if c_name not in existing_cols:
                        try:
                            conn.execute(text(f"ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS {c_name} {c_type}"))
                        except Exception as ex:
                            print(f"[WARN] ALTER TABLE audit_logs ADD COLUMN {c_name} failed: {ex}")
    except Exception as e:
        print(f"[WARN] Database schema check/migration: {e}")

try:
    init_and_migrate_db()
except Exception as e:
    print(f"[WARN] Database auto-migration skipped: {e}")

# ==============================================================================
# 3. FONT UNICODE & CÁC HÀM TIỆN ÍCH HỆ THỐNG
# ==============================================================================
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
]
UNICODE_FONT = next((p for p in FONT_CANDIDATES if os.path.exists(p)), None)


def measure_text_width(text: str, fontsize: float) -> float:
    """Đo chiều rộng thực tế của chuỗi văn bản theo font Unicode hoặc Helvetica fallback."""
    try:
        if UNICODE_FONT and os.path.exists(UNICODE_FONT):
            font_obj = pymupdf.Font(fontfile=UNICODE_FONT)
            return font_obj.text_length(text, fontsize=fontsize)
    except Exception:
        pass
    try:
        return pymupdf.get_text_length(text, fontname="helv", fontsize=fontsize)
    except Exception:
        return len(text) * fontsize * 0.6


def clean_doc_title(raw_name: str) -> str:
    """
    Chuẩn hóa tên tài liệu người dùng đọc được (Display Name):
    Giữ nguyên tiếng Việt có dấu, khoảng trắng, dấu chấm, loại bỏ ký tự điều khiển hoặc path traversal.
    """
    base = os.path.splitext(os.path.basename(raw_name))[0].strip()
    # Loại bỏ các ký tự nguy hiểm cho hệ thống tệp và tiêu đề HTTP: / \ : * ? " < > | \0
    cleaned = re.sub(r'[\/\\:\*\?"<>\|\x00-\x1f]', '_', base).strip()
    return cleaned or f"doc_{int(time.time())}"


def safe_storage_key(raw_name: str) -> str:
    """
    Chuyển đổi tên tệp thành chuỗi ASCII an toàn cho S3 Object Key và cache đường dẫn nội bộ.
    Giữ nguyên ý nghĩa bằng cách chuyển tiếng Việt có dấu sang không dấu (e.g. Trần Nhật Hưng -> Tran_Nhat_Hung).
    """
    import unicodedata
    base = os.path.splitext(os.path.basename(raw_name))[0].strip()
    nfkd = unicodedata.normalize('NFKD', base)
    ascii_base = "".join([c for c in nfkd if not unicodedata.combining(c)])
    cleaned = re.sub(r'[^a-zA-Z0-9_-]+', '_', ascii_base).strip('_')
    return cleaned or f"doc_{int(time.time())}"


def sanitize_filename(raw_name: str) -> str:
    """Tương thích ngược với các lệnh gọi cũ."""
    return safe_storage_key(raw_name)


def format_vn_time(dt: Optional[datetime]) -> str:
    """Định dạng thời gian theo múi giờ Việt Nam (UTC+7) chuẩn YYYY-MM-DD HH:mm:ss."""
    if not dt:
        return "-"
    try:
        if dt.tzinfo is None:
            # Coi như UTC
            dt = dt.replace(tzinfo=timezone.utc)
        dt_vn = dt.astimezone(VN_TIMEZONE)
        return dt_vn.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(dt)


def list_available_docs() -> list[str]:
    """Lấy danh sách các file PDF mẫu có sẵn trên S3 hoặc EFS."""
    docs = []
    # 1. Thử lấy từ S3
    try:
        resp = s3_client.list_objects_v2(Bucket=S3_BUCKET, Prefix="input/", MaxKeys=30)
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            if key.lower().endswith(".pdf"):
                docs.append(os.path.splitext(os.path.basename(key))[0])
    except Exception:
        pass
    # 2. Thử lấy từ EFS cache hoặc thư mục hiện tại
    if not docs:
        for f in os.listdir("."):
            if f.lower().endswith(".pdf"):
                docs.append(os.path.splitext(f)[0])
    return list(dict.fromkeys(docs)) or ["ModelOptimization"]


def record_audit(
    request_id: str,
    client_id: str,
    doc_name: str,
    pages_count: int,
    sha256_hash: str,
    worker_host: str,
    output_key: str,
    proc_time_ms: float,
    student_id: Optional[str] = None,
    full_name: Optional[str] = None,
    doc_code: Optional[str] = None,
    meta_dict: Optional[dict] = None,
):
    """Ghi vết kiểm toán chuẩn Microservice vào cơ sở dữ liệu (tương thích mọi phiên bản schema)."""
    try:
        insp = sa.inspect(engine)
        if not insp.has_table("audit_logs"):
            metadata.create_all(engine)
        cols = {c["name"] for c in insp.get_columns("audit_logs")}
        candidate_values = {
            "request_id": request_id,
            "client_id": client_id or "default",
            "doc_name": doc_name,
            "doc_code": doc_code or doc_name,
            "pages_count": pages_count,
            "sha256": sha256_hash,
            "sha256_hash": sha256_hash,
            "file_hash": sha256_hash,
            "worker_host": worker_host,
            "worker": worker_host,
            "output_key": output_key,
            "s3_key": output_key,
            "processing_time_ms": proc_time_ms,
            "created_at": datetime.now(timezone.utc),
            "student_id": student_id,
            "full_name": full_name,
            "metadata_json": json.dumps(meta_dict) if meta_dict else None,
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
        print(f"[WARN] Failed to insert audit log: {e}")


# ==============================================================================
# 4. BỘ MÁY ĐÓNG DẤU PDF NÂNG CAO (GENERIC WATERMARKING ENGINE)
# ==============================================================================
def apply_watermarks(
    input_path: str,
    output_path: str,
    header_text: Optional[str] = None,
    footer_text: Optional[str] = None,
    diagonal_text: Optional[str] = None,
    stamp_text: Optional[str] = None,
    logo_bytes: Optional[bytes] = None,
    diagonal_opacity: float = 0.22,
    diagonal_fontsize: int = 38,
    diagonal_color: tuple = (0.75, 0.2, 0.2),
) -> tuple[int, str]:
    """
    Thực hiện chèn watermark động lên toàn bộ trang PDF bằng PyMuPDF.
    Đặc biệt xử lý watermark chéo: Tự động căn chính giữa trang và co giãn font
    linh hoạt theo kích thước trang giấy (A4, Letter, Khổ dọc/ngang), đảm bảo không bao giờ bị cắt chữ.
    Trả về: (số trang, chuỗi băm SHA-256).
    """
    font_kwargs = {"fontfile": UNICODE_FONT, "fontname": "unicode_font"} if UNICODE_FONT else {}

    doc = pymupdf.open(input_path)
    pages_count = len(doc)

    # Đảm bảo các tham số text là chuỗi hợp lệ
    header_text = header_text if isinstance(header_text, str) and header_text.strip() else None
    footer_text = footer_text if isinstance(footer_text, str) and footer_text.strip() else None
    diagonal_text = diagonal_text if isinstance(diagonal_text, str) and diagonal_text.strip() else None
    stamp_text = stamp_text if isinstance(stamp_text, str) and stamp_text.strip() else None

    for page in doc:
        rect = page.rect
        w, h = rect.width, rect.height

        # 1. Chèn Watermark chữ chéo chìm (Tự thích ứng kích thước & căn chính giữa trang)
        if diagonal_text:
            angle_deg = -38.0  # Độ nghiêng hướng chéo lên từ góc dưới-trái sang trên-phải
            rad = math.radians(angle_deg)
            cos_a = math.cos(rad)
            sin_a = math.sin(rad)

            # Tính chiều dài khả dụng tối đa dọc theo hướng nghiêng để chữ không chạm mép giấy
            # Ray: x(t) = w/2 + t*cos, y(t) = h/2 + t*sin => |t| <= (w/2)/|cos| và |t| <= (h/2)/|sin|
            t_max = min((w * 0.44) / max(0.001, abs(cos_a)), (h * 0.44) / max(0.001, abs(sin_a)))
            max_allowed_len = 2.0 * t_max * 0.88  # Chừa 12% lề an toàn

            # Ước lượng độ dài văn bản tại cỡ chữ 10pt
            test_len = measure_text_width(diagonal_text, 10.0)
            if not test_len or test_len <= 0:
                test_len = len(diagonal_text) * 6.0

            # Tính font size tối ưu
            target_fs = int((max_allowed_len / test_len) * 10.0)
            fs = max(13, min(diagonal_fontsize, target_fs))

            # Tinh chỉnh lại cỡ chữ nếu văn bản thực tế vẫn vượt quá giới hạn an toàn
            actual_tlen = measure_text_width(diagonal_text, fs)
            while actual_tlen > max_allowed_len and fs > 12:
                fs -= 1
                actual_tlen = measure_text_width(diagonal_text, fs)

            # Điểm tâm chính xác của trang giấy
            cx, cy = w / 2.0, h / 2.0

            # Điểm bắt đầu vẽ sao cho TRỌNG TÂM CỦA CHUỖI KÝ TỰ TRÙNG KHÍT VỚI TÂM TRANG GIẤY
            # p_start = (cx - (L/2)*cos, cy - (L/2)*sin)
            p_start = pymupdf.Point(cx - (actual_tlen / 2.0) * cos_a, cy - (actual_tlen / 2.0) * sin_a)

            page.insert_text(
                p_start,
                diagonal_text,
                fontsize=fs,
                color=diagonal_color,
                fill_opacity=diagonal_opacity,
                morph=(p_start, pymupdf.Matrix(angle_deg)),
                **font_kwargs,
            )

        # 2. Chèn Header (Góc trên bên trái)
        if header_text:
            page.insert_text(
                (42, 28),
                header_text,
                fontsize=9,
                color=(0.75, 0.15, 0.15),
                **font_kwargs,
            )

        # 3. Chèn Footer (Góc dưới bên trái)
        if footer_text:
            page.insert_text(
                (42, h - 20),
                footer_text,
                fontsize=8,
                color=(0.4, 0.4, 0.4),
                **font_kwargs,
            )

        # 4. Chèn Con dấu / Logo (Góc trên bên phải)
        if logo_bytes:
            logo_rect = pymupdf.Rect(w - 110, 14, w - 30, 64)
            page.insert_image(logo_rect, stream=logo_bytes, keep_proportion=True)
        elif stamp_text:
            stamp_rect = pymupdf.Rect(w - 130, 16, w - 35, 42)
            page.draw_rect(stamp_rect, color=(0.8, 0.1, 0.1), width=1.2)
            page.insert_text(
                (w - 122, 33),
                stamp_text[:14],
                fontsize=9,
                color=(0.8, 0.1, 0.1),
                **font_kwargs,
            )

    # Nén tối đa kích thước PDF đầu ra
    doc.save(output_path, garbage=3, deflate=True)
    doc.close()

    # Tính mã băm SHA-256 theo khối 64KB
    sha256 = hashlib.sha256()
    with open(output_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    digest = sha256.hexdigest()

    return pages_count, digest


# ==============================================================================
# 5. PYDANTIC SCHEMAS CHO RESTFUL JSON API
# ==============================================================================
class WatermarkStyle(BaseModel):
    diagonal_text: Optional[str] = Field(None, description="Chữ chìm chéo giữa trang (VD: CONFIDENTIAL, DRAFT, TÊN KHÁCH HÀNG)")
    header_text: Optional[str] = Field(None, description="Dòng chữ tiêu đề trang (VD: Mã giao dịch | Ngày xuất)")
    footer_text: Optional[str] = Field(None, description="Dòng chữ chân trang (VD: Chỉ sử dụng cho mục đích nội bộ)")
    stamp_text: Optional[str] = Field(None, description="Chữ hiển thị trong khung con dấu góc trên bên phải (VD: ACME CORP)")
    diagonal_opacity: float = Field(0.22, ge=0.05, le=1.0, description="Độ mờ chữ chéo (0.1 đến 1.0)")
    diagonal_fontsize: int = Field(38, ge=12, le=72, description="Cỡ chữ watermark chéo")


class DocumentSource(BaseModel):
    s3_key: Optional[str] = Field(None, description="Đường dẫn file trên S3 (VD: input/contract.pdf)")
    doc_code: Optional[str] = Field(None, description="Tên file tài liệu mẫu có sẵn trên S3 hoặc EFS")
    base64_content: Optional[str] = Field(None, description="Nội dung file PDF dạng Base64 (tùy chọn)")


class WatermarkRequest(BaseModel):
    client_id: Optional[str] = Field("default", description="Mã định danh hệ thống gọi (VD: crm-service, edtech-app)")
    source: DocumentSource = Field(..., description="Nguồn tài liệu PDF cần xử lý")
    watermark: WatermarkStyle = Field(default_factory=WatermarkStyle, description="Cấu hình các lớp đóng dấu")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata đính kèm tự do lưu vào nhật ký kiểm toán")


class WatermarkResponse(BaseModel):
    request_id: str
    client_id: str
    worker_host: str
    doc_name: str
    pages_count: int
    sha256: str
    download_url: str
    processing_time_ms: float


# ==============================================================================
# 6. KHỞI TẠO ỨNG DỤNG FASTAPI & ENDPOINTS
# ==============================================================================
app = FastAPI(
    title=SERVICE_NAME,
    version=SERVICE_VERSION,
    description="Microservice đóng dấu bản quyền tài liệu động, kiểm định tính toàn vẹn (SHA-256) và kiểm toán phân tán trên AWS.",
)


@app.get("/health")
def health_check():
    """Endpoint kiểm tra sức khỏe phục vụ Application Load Balancer và Container Health Check."""
    db_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    return {
        "status": "healthy" if db_ok else "degraded",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "host": socket.gethostname(),
        "database": "connected" if db_ok else "disconnected",
        "storage": {
            "s3_bucket": S3_BUCKET,
            "efs_dir": EFS_DIR,
        },
    }


# ------------------------------------------------------------------------------
# 6.1. API CHUẨN JSON RESTful DÀNH CHO CÁC MICROSERVICE KHÁC TÍCH HỢP
# ------------------------------------------------------------------------------
@app.post("/api/v1/watermark", response_model=WatermarkResponse)
async def api_watermark_v1(req: WatermarkRequest, x_api_key: Optional[str] = Header(None)):
    """API JSON chuẩn dành cho các hệ thống khác (CRM, ERP, EdTech) gọi tích hợp đóng dấu."""
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Xác thực không hợp lệ: API Key không đúng.")

    start_t = time.perf_counter()
    request_id = str(uuid.uuid4())
    worker_host = socket.gethostname()
    timestamp = int(time.time())

    # 1. Xác định file PDF đầu vào
    doc_identifier = req.source.doc_code or req.source.s3_key or "document"
    display_doc_name = clean_doc_title(doc_identifier)
    storage_code = safe_storage_key(doc_identifier)
    cached_input_path = os.path.join(EFS_DIR, "input", f"{storage_code}.pdf")

    if req.source.base64_content:
        import base64
        try:
            pdf_bytes = base64.b64decode(req.source.base64_content)
            with open(cached_input_path, "wb") as f:
                f.write(pdf_bytes)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Base64 không hợp lệ: {e}")
    else:
        # Nếu chưa có ở cache EFS thì kéo từ S3 về
        if not os.path.exists(cached_input_path):
            s3_key = req.source.s3_key or f"input/{storage_code}.pdf"
            try:
                s3_client.download_file(S3_BUCKET, s3_key, cached_input_path)
            except Exception as e:
                # Fallback: kiểm tra tệp cục bộ
                local_fallback = f"{storage_code}.pdf"
                if os.path.exists(local_fallback):
                    import shutil
                    shutil.copyfile(local_fallback, cached_input_path)
                else:
                    raise HTTPException(status_code=404, detail=f"Không tìm thấy tài liệu '{s3_key}' trên S3/EFS: {e}")

    # 2. Xử lý đóng dấu
    out_filename = f"{storage_code}_{request_id[:8]}_{timestamp}.pdf"
    local_out_path = os.path.join("/tmp/wm_work", out_filename)

    try:
        pages_count, digest = apply_watermarks(
            input_path=cached_input_path,
            output_path=local_out_path,
            header_text=req.watermark.header_text,
            footer_text=req.watermark.footer_text,
            diagonal_text=req.watermark.diagonal_text,
            stamp_text=req.watermark.stamp_text,
            diagonal_opacity=req.watermark.diagonal_opacity,
            diagonal_fontsize=req.watermark.diagonal_fontsize,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi xử lý đóng dấu PDF: {e}")

    # 3. Tải lên S3 & Tạo Pre-signed URL hỗ trợ tên tải về chuẩn UTF-8
    output_key = f"output/{out_filename}"
    download_filename = f"{display_doc_name}_watermarked.pdf"
    encoded_download_name = urllib.parse.quote(download_filename)
    content_disp = f"attachment; filename=\"watermarked.pdf\"; filename*=UTF-8''{encoded_download_name}"

    presigned_url = f"/api/v1/download/{out_filename}?original_name={encoded_download_name}"
    try:
        s3_client.upload_file(local_out_path, S3_BUCKET, output_key)
        presigned_url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": S3_BUCKET,
                "Key": output_key,
                "ResponseContentDisposition": content_disp,
            },
            ExpiresIn=3600,
        )
        if os.path.exists(local_out_path):
            os.remove(local_out_path)
    except Exception as e:
        print(f"[WARN] S3 Upload bypassed / using local download: {e}")

    proc_time_ms = (time.perf_counter() - start_t) * 1000.0

    # 4. Ghi vết kiểm toán
    record_audit(
        request_id=request_id,
        client_id=req.client_id or "default",
        doc_name=display_doc_name,
        pages_count=pages_count,
        sha256_hash=digest,
        worker_host=worker_host,
        output_key=output_key,
        proc_time_ms=proc_time_ms,
        doc_code=storage_code,
        meta_dict=req.metadata,
    )

    return WatermarkResponse(
        request_id=request_id,
        client_id=req.client_id or "default",
        worker_host=worker_host,
        doc_name=display_doc_name,
        pages_count=pages_count,
        sha256=digest,
        download_url=presigned_url,
        processing_time_ms=round(proc_time_ms, 2),
    )


# ------------------------------------------------------------------------------
# 6.2. ENDPOINT TƯƠNG THÍCH NGƯỢC (TƯƠNG THÍCH CẢ LOAD_TEST.PY & FORM UPLOAD)
# ------------------------------------------------------------------------------
@app.post("/api/watermark")
async def create_watermark_legacy(
    student_id: Optional[str] = Form(None),
    full_name: Optional[str] = Form(None),
    doc_code: str = Form("ModelOptimization"),
    pdf_file: Optional[UploadFile] = File(None),
    logo_file: Optional[UploadFile] = File(None),
    # Các tham số mới mở rộng cho Microservice
    header_text: Optional[str] = Form(None),
    footer_text: Optional[str] = Form(None),
    diagonal_text: Optional[str] = Form(None),
    stamp_text: Optional[str] = Form(None),
    client_id: Optional[str] = Form("web-client"),
):
    """
    Endpoint linh hoạt: vừa hỗ trợ form web / upload file trực tiếp, vừa tương thích
    100% với script bắn tải load_test.py cũ.
    """
    start_t = time.perf_counter()
    request_id = str(uuid.uuid4())
    worker_host = socket.gethostname()
    timestamp = int(time.time())

    # Chuẩn hóa giá trị tham số (tránh trường hợp gọi trực tiếp nhận đối tượng Form)
    student_id = student_id if isinstance(student_id, str) and student_id.strip() else None
    full_name = full_name if isinstance(full_name, str) and full_name.strip() else None
    doc_code = doc_code if isinstance(doc_code, str) and doc_code.strip() else "ModelOptimization"
    header_text = header_text if isinstance(header_text, str) and header_text.strip() else None
    footer_text = footer_text if isinstance(footer_text, str) and footer_text.strip() else None
    diagonal_text = diagonal_text if isinstance(diagonal_text, str) and diagonal_text.strip() else None
    stamp_text = stamp_text if isinstance(stamp_text, str) and stamp_text.strip() else None
    client_id = client_id if isinstance(client_id, str) and client_id.strip() else "web-client"

    # Xử lý tương thích ngược: Nếu truyền student_id và full_name thì tự động sinh header/footer
    if student_id and full_name:
        if not header_text:
            header_text = f"{student_id} - {full_name.upper()} | {doc_code}"
        if not footer_text:
            footer_text = f"Tài liệu cấp phát cho {full_name} ({student_id})"
        if not diagonal_text:
            diagonal_text = f"{student_id} - {full_name.upper()}"
        if not stamp_text:
            stamp_text = "UET - VNU"

    # 1. Quản lý file PDF đầu vào
    if pdf_file is not None and pdf_file.filename:
        if not pdf_file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Chỉ chấp nhận tệp định dạng PDF.")
        pdf_bytes = await pdf_file.read()
        if not pdf_bytes:
            raise HTTPException(status_code=400, detail="Tệp PDF tải lên bị rỗng.")
        display_doc_name = clean_doc_title(pdf_file.filename)
        storage_code = safe_storage_key(pdf_file.filename)
        input_key = f"input/{storage_code}.pdf"
        cached_input_path = os.path.join(EFS_DIR, "input", f"{storage_code}.pdf")
        with open(cached_input_path, "wb") as f:
            f.write(pdf_bytes)
        try:
            s3_client.upload_file(cached_input_path, S3_BUCKET, input_key)
        except Exception:
            pass
    else:
        display_doc_name = clean_doc_title(doc_code)
        storage_code = safe_storage_key(doc_code)
        input_key = f"input/{storage_code}.pdf"
        cached_input_path = os.path.join(EFS_DIR, "input", f"{storage_code}.pdf")
        if not os.path.exists(cached_input_path):
            try:
                s3_client.head_object(Bucket=S3_BUCKET, Key=input_key)
                s3_client.download_file(S3_BUCKET, input_key, cached_input_path)
            except Exception:
                # Fallback file cục bộ
                local_f = f"{storage_code}.pdf"
                if os.path.exists(local_f):
                    import shutil
                    shutil.copyfile(local_f, cached_input_path)
                else:
                    raise HTTPException(status_code=404, detail=f"Không tìm thấy PDF '{input_key}' trên S3/EFS")

    # 2. Xử lý ảnh logo tải lên (nếu có)
    logo_bytes = None
    if logo_file is not None and logo_file.filename:
        logo_bytes = await logo_file.read()
        if not logo_bytes:
            logo_bytes = None

    # 3. Đóng dấu
    prefix = student_id or client_id or "doc"
    out_filename = f"{prefix}_{storage_code}_{timestamp}.pdf"
    local_out_path = os.path.join("/tmp/wm_work", out_filename)

    try:
        pages_count, digest = apply_watermarks(
            input_path=cached_input_path,
            output_path=local_out_path,
            header_text=header_text,
            footer_text=footer_text,
            diagonal_text=diagonal_text,
            stamp_text=stamp_text or "ACME CORP",
            logo_bytes=logo_bytes,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi xử lý đóng dấu PDF: {e}")

    # 4. Upload S3 & Sinh Pre-signed URL hỗ trợ tên tải về chuẩn UTF-8
    output_key = f"output/{out_filename}"
    download_filename = f"{display_doc_name}_watermarked.pdf"
    encoded_download_name = urllib.parse.quote(download_filename)
    content_disp = f"attachment; filename=\"watermarked.pdf\"; filename*=UTF-8''{encoded_download_name}"

    presigned_url = f"/api/v1/download/{out_filename}?original_name={encoded_download_name}"
    try:
        s3_client.upload_file(local_out_path, S3_BUCKET, output_key)
        presigned_url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": S3_BUCKET,
                "Key": output_key,
                "ResponseContentDisposition": content_disp,
            },
            ExpiresIn=3600,
        )
        if os.path.exists(local_out_path):
            os.remove(local_out_path)
    except Exception as e:
        print(f"[WARN] S3 Upload bypassed / using local download: {e}")

    proc_time_ms = (time.perf_counter() - start_t) * 1000.0

    # 5. Ghi nhật ký kiểm toán
    record_audit(
        request_id=request_id,
        client_id=client_id or "web-client",
        doc_name=display_doc_name,
        pages_count=pages_count,
        sha256_hash=digest,
        worker_host=worker_host,
        output_key=output_key,
        proc_time_ms=proc_time_ms,
        student_id=student_id,
        full_name=full_name,
        doc_code=storage_code,
    )

    # Trả về JSON bao gồm tất cả các trường mà load_test.py lẫn client mới đều hiểu
    return {
        "request_id": request_id,
        "worker_host": worker_host,
        "doc_code": storage_code,
        "doc_name": display_doc_name,
        "pages_count": pages_count,
        "sha256": digest,
        "download_url": presigned_url,
        "processing_time_ms": round(proc_time_ms, 2),
    }


# ------------------------------------------------------------------------------
# 6.3. API KIỂM TOÁN & TRA CỨU TÍNH TOÀN VẸN (AUDIT & INTEGRITY VERIFICATION)
# ------------------------------------------------------------------------------
@app.get("/api/v1/audit-logs")
def get_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    client_id: Optional[str] = None,
    sha256: Optional[str] = None,
):
    """Truy vấn danh sách nhật ký kiểm toán với bộ lọc linh hoạt và chuyển đổi giờ Việt Nam."""
    try:
        actual_limit = int(limit) if isinstance(limit, (int, str)) and str(limit).isdigit() else 50
        actual_offset = int(offset) if isinstance(offset, (int, str)) and str(offset).isdigit() else 0

        with engine.connect() as conn:
            insp = sa.inspect(engine)
            if not insp.has_table("audit_logs"):
                return {"total": 0, "logs": []}
            existing_cols = {c["name"] for c in insp.get_columns("audit_logs")}

            where_clauses = ["1=1"]
            params = {"lim": actual_limit, "off": actual_offset}
            if client_id and isinstance(client_id, str) and "client_id" in existing_cols:
                where_clauses.append("client_id = :cid")
                params["cid"] = client_id
            if sha256 and isinstance(sha256, str):
                h_col = next((c for c in ["sha256", "sha256_hash", "file_hash"] if c in existing_cols), None)
                if h_col:
                    where_clauses.append(f"{h_col} = :h")
                    params["h"] = sha256

            sql = f"SELECT * FROM audit_logs WHERE {' AND '.join(where_clauses)} ORDER BY id DESC LIMIT :lim OFFSET :off"
            results = conn.execute(text(sql), params).fetchall()

            logs_list = []
            for r in results:
                d = dict(r._mapping)
                raw_dt = d.get("created_at")
                if isinstance(raw_dt, datetime):
                    d["created_at"] = raw_dt.isoformat()
                    d["created_at_vn"] = format_vn_time(raw_dt)
                else:
                    d["created_at_vn"] = str(raw_dt or "-")

                # Chuẩn hóa trường để không bao giờ bị undefined trên frontend
                d["sha256"] = d.get("sha256") or d.get("sha256_hash") or d.get("file_hash") or ""
                d["worker_host"] = d.get("worker_host") or d.get("worker") or socket.gethostname()
                logs_list.append(d)
            return {"total": len(logs_list), "logs": logs_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi truy vấn cơ sở dữ liệu: {e}")


@app.get("/api/v1/audit-logs/verify/{sha256}")
def verify_document_integrity(sha256: str):
    """
    Điểm kiểm định tài liệu (Integrity Verification):
    Cho phép bất kỳ hệ thống nào kiểm tra xem file PDF có đúng do hệ thống cấp phát không.
    """
    try:
        with engine.connect() as conn:
            insp = sa.inspect(engine)
            if not insp.has_table("audit_logs"):
                return {"verified": False, "sha256": sha256, "message": "Chưa có bảng dữ liệu kiểm toán."}
            existing_cols = {c["name"] for c in insp.get_columns("audit_logs")}

            col_match = next((c for c in ["sha256", "sha256_hash", "file_hash"] if c in existing_cols), None)
            if not col_match:
                return {"verified": False, "sha256": sha256, "message": "Cột mã băm kiểm định chưa được thiết lập."}

            sql = text(f"SELECT * FROM audit_logs WHERE {col_match} = :h ORDER BY id DESC LIMIT 1")
            row = conn.execute(sql, {"h": sha256.strip()}).fetchone()
            if not row:
                return {
                    "verified": False,
                    "sha256": sha256,
                    "message": "Không tìm thấy tài liệu này trong nhật ký kiểm toán! File có thể bị giả mạo hoặc chưa từng được cấp phát.",
                }
            data = dict(row._mapping)
            raw_dt = data.get("created_at")
            if isinstance(raw_dt, datetime):
                data["created_at"] = raw_dt.isoformat()
                data["created_at_vn"] = format_vn_time(raw_dt)
            else:
                data["created_at_vn"] = str(raw_dt or "-")

            data["sha256"] = data.get("sha256") or data.get("sha256_hash") or data.get("file_hash") or ""
            data["worker_host"] = data.get("worker_host") or data.get("worker") or socket.gethostname()

            return {
                "verified": True,
                "sha256": sha256,
                "document": data,
                "message": "Tài liệu chính thống đã được xác thực tính toàn vẹn và nguồn gốc cấp phát.",
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi kiểm tra tính toàn vẹn: {e}")


@app.get("/api/v1/download/{filename}")
def download_local_file(filename: str, original_name: Optional[str] = None):
    """Tải trực tiếp file từ thư mục tạm làm việc với tiêu đề tên tệp UTF-8."""
    clean = os.path.basename(filename)
    path = os.path.join("/tmp/wm_work", clean)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Tệp tin không tồn tại hoặc đã bị dọn dẹp.")

    final_name = original_name or clean
    if not final_name.lower().endswith(".pdf"):
        final_name += ".pdf"
    encoded_name = urllib.parse.quote(final_name)
    headers = {
        "Content-Disposition": f"attachment; filename=\"document.pdf\"; filename*=UTF-8''{encoded_name}"
    }
    return FileResponse(path, media_type="application/pdf", headers=headers)


# ==============================================================================
# 7. GIAO DIỆN DEVELOPER PORTAL & PLAYGROUND (HTML/JS)
# ==============================================================================
@app.get("/", response_class=HTMLResponse)
def developer_portal():
    docs = list_available_docs()
    options_html = "\n".join(
        f'<option value="{d}">{d}.pdf</option>' for d in docs
    )
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Enterprise PDF Watermarking Microservice</title>
  <style>
    :root {{ --primary: #2563eb; --primary-hover: #1d4ed8; --bg: #f8fafc; --card: #ffffff; --text: #0f172a; --border: #e2e8f0; }}
    * {{ box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }}
    body {{ background: var(--bg); margin: 0; padding: 24px 16px; color: var(--text); }}
    .container {{ max-width: 960px; margin: 0 auto; }}
    .header {{ background: var(--card); border-radius: 12px; padding: 24px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom: 20px; border: 1px solid var(--border); }}
    .header h1 {{ margin: 0 0 6px; font-size: 24px; color: #1e3a8a; display: flex; align-items: center; gap: 10px; }}
    .header p {{ margin: 0; font-size: 14px; color: #64748b; }}
    .badge {{ display: inline-block; font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 999px; background: #dbeafe; color: #1d4ed8; vertical-align: middle; }}
    .tabs {{ display: flex; gap: 8px; margin-bottom: 16px; border-bottom: 2px solid var(--border); padding-bottom: 8px; }}
    .tab-btn {{ background: none; border: none; padding: 8px 16px; font-size: 15px; font-weight: 600; color: #64748b; cursor: pointer; border-radius: 6px; }}
    .tab-btn.active {{ background: #eff6ff; color: var(--primary); }}
    .card {{ background: var(--card); border-radius: 12px; padding: 24px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); border: 1px solid var(--border); margin-bottom: 24px; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    @media (max-width: 640px) {{ .grid {{ grid-template-columns: 1fr; }} }}
    .field {{ margin-bottom: 16px; }}
    label {{ display: block; font-weight: 600; font-size: 13px; margin-bottom: 6px; color: #334155; }}
    .hint {{ font-size: 12px; color: #64748b; margin-top: 4px; }}
    input[type="text"], input[type="file"], select {{
      width: 100%; padding: 10px 12px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; background: #fff;
    }}
    input:focus, select:focus {{ outline: none; border-color: var(--primary); ring: 2px solid #bfdbfe; }}
    button.btn-primary {{
      width: 100%; padding: 12px; background: var(--primary); color: #fff; border: none; border-radius: 8px;
      font-size: 15px; font-weight: 600; cursor: pointer; transition: background 0.2s;
    }}
    button.btn-primary:hover {{ background: var(--primary-hover); }}
    button:disabled {{ background: #94a3b8; cursor: not-allowed; }}
    .result {{ margin-top: 20px; padding: 16px; border-radius: 8px; background: #ecfdf5; border: 1px solid #10b981; display: none; }}
    .result.error {{ background: #fef2f2; border-color: #ef4444; }}
    .meta-item {{ font-size: 13px; line-height: 1.8; word-break: break-all; }}
    .btn-download {{ display: inline-block; margin-top: 10px; padding: 9px 16px; background: #059669; color: #fff; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 13px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 12px; }}
    th, td {{ padding: 10px; border-bottom: 1px solid var(--border); text-align: left; }}
    th {{ background: #f1f5f9; color: #475569; font-weight: 600; }}
    pre {{ background: #0f172a; color: #e2e8f0; padding: 16px; border-radius: 8px; font-size: 13px; overflow-x: auto; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Enterprise PDF Watermarking Engine <span class="badge">v2.1 Microservice</span></h1>
      <p>Microservice đóng dấu tài liệu động, kiểm định tính toàn vẹn (SHA-256) và kiểm toán phân tán trên AWS Cloud.</p>
    </div>

    <div class="tabs">
      <button class="tab-btn active" onclick="switchTab('playground')">🎮 Playground Thử nghiệm</button>
      <button class="tab-btn" onclick="switchTab('audit')">📜 Nhật ký Kiểm toán & Xác minh</button>
      <button class="tab-btn" onclick="switchTab('api-docs')">🔌 Hướng dẫn Tích hợp API</button>
    </div>

    <!-- TAB 1: PLAYGROUND -->
    <div id="tab-playground" class="card">
      <form id="wmForm">
        <div class="grid">
          <div class="field">
            <label>Mã hệ thống gọi (Client ID)</label>
            <input type="text" name="client_id" value="crm-service" placeholder="VD: crm-service, edtech-app" />
          </div>
          <div class="field">
            <label>Con dấu tổ chức (Stamp Text)</label>
            <input type="text" name="stamp_text" value="CONFIDENTIAL" placeholder="VD: ACME CORP, UET-VNU" />
          </div>
        </div>

        <div class="field">
          <label>Chữ chìm chéo giữa trang (Diagonal Watermark) 🌟</label>
          <input type="text" name="diagonal_text" value="BẢN SAO KÊ BẢO MẬT - NGUYỄN VĂN A" placeholder="VD: CONFIDENTIAL, DRAFT, TÊN KHÁCH HÀNG" />
          <div class="hint">Watermark chìm xoay chéo tự thích ứng kích thước trang giấy, tự động co giãn font và luôn hiển thị trọn vẹn ở giữa trang.</div>
        </div>

        <div class="grid">
          <div class="field">
            <label>Dòng tiêu đề trên (Header Text)</label>
            <input type="text" name="header_text" value="Phát hành nội bộ | Mã truy xuất: ACC-98234" />
          </div>
          <div class="field">
            <label>Dòng chân trang (Footer Text)</label>
            <input type="text" name="footer_text" value="Tài liệu chỉ dùng cho mục đích xác minh tài chính" />
          </div>
        </div>

        <div class="grid">
          <div class="field">
            <label>Tải PDF từ máy tính (Tùy chọn)</label>
            <input type="file" id="pdf_file" name="pdf_file" accept="application/pdf" />
          </div>
          <div class="field">
            <label>Hoặc chọn PDF có sẵn trên S3/EFS</label>
            <select name="doc_code">
              {options_html}
            </select>
          </div>
        </div>

        <div class="field">
          <label>Tải Logo tùy chỉnh (Tùy chọn)</label>
          <input type="file" id="logo_file" name="logo_file" accept="image/png,image/jpeg" />
          <div class="hint">Nếu tải logo, ảnh sẽ được đặt vào góc trên bên phải thay thế con dấu mặc định.</div>
        </div>

        <button type="submit" id="submitBtn" class="btn-primary">⚡ Thực thi Đóng dấu & Xuất bản quyền</button>
      </form>

      <div id="resultBox" class="result"></div>
    </div>

    <!-- TAB 2: AUDIT LOGS -->
    <div id="tab-audit" class="card" style="display: none;">
      <h3 style="margin-top: 0;">Tra cứu & Kiểm định Tính toàn vẹn (Document Verification)</h3>
      <div style="display: flex; gap: 8px; margin-bottom: 20px;">
        <input type="text" id="verifyShaInput" placeholder="Dán mã SHA-256 vào đây để kiểm tra nguồn gốc tài liệu..." style="flex: 1;" />
        <button onclick="verifyDoc()" class="btn-primary" style="width: auto; padding: 0 20px;">Kiểm tra</button>
      </div>
      <div id="verifyResult" style="margin-bottom: 20px;"></div>

      <div style="display: flex; justify-content: space-between; align-items: center;">
        <h4 style="margin: 0;">50 Bản ghi Kiểm toán gần nhất (Giờ Việt Nam - GMT+7)</h4>
        <button onclick="loadAuditLogs()" style="background: none; border: 1px solid var(--border); padding: 6px 12px; border-radius: 6px; cursor: pointer;">🔄 Làm mới</button>
      </div>
      <div style="overflow-x: auto;">
        <table id="auditTable">
          <thead>
            <tr>
              <th>ID</th>
              <th>Thời gian (VN)</th>
              <th>Client ID</th>
              <th>Tài liệu</th>
              <th>Số trang</th>
              <th>Worker Host</th>
              <th>Thời gian xử lý</th>
              <th>SHA-256 Hash</th>
            </tr>
          </thead>
          <tbody>
            <tr><td colspan="8" style="text-align: center; color: #64748b;">Đang tải dữ liệu...</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- TAB 3: API DOCS -->
    <div id="tab-api-docs" class="card" style="display: none;">
      <h3 style="margin-top: 0;">Tích hợp Microservice qua RESTful API</h3>
      <p style="font-size: 14px;">Bất kỳ dịch vụ nào (CRM, ERP, Web App) đều có thể gọi endpoint JSON chuẩn để đóng dấu tự động:</p>

      <h4>1. Gửi yêu cầu qua cURL:</h4>
      <pre><code>curl -X POST "http://&lt;ALB_DNS&gt;/api/v1/watermark" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "client_id": "crm-backend",
    "source": {{ "s3_key": "input/ModelOptimization.pdf" }},
    "watermark": {{
      "diagonal_text": "CONFIDENTIAL - NGUYEN VAN A",
      "header_text": "Hợp đồng đối tác số #10928",
      "stamp_text": "ACME CORP"
    }}
  }}'</code></pre>

      <h4>2. Swagger UI trực quan:</h4>
      <p>Truy cập tài liệu OpenAPI chuẩn hóa tại: <a href="/docs" target="_blank" style="color: var(--primary); font-weight: 600;">/docs (Swagger UI)</a></p>
    </div>
  </div>

  <script>
    function switchTab(tab) {{
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.getElementById('tab-playground').style.display = tab === 'playground' ? 'block' : 'none';
      document.getElementById('tab-audit').style.display = tab === 'audit' ? 'block' : 'none';
      document.getElementById('tab-api-docs').style.display = tab === 'api-docs' ? 'block' : 'none';
      event.target.classList.add('active');
      if (tab === 'audit') loadAuditLogs();
    }}

    function formatVNTime(isoStr) {{
      if (!isoStr || isoStr === '-') return '-';
      try {{
        let s = isoStr;
        if (!s.endsWith('Z') && !s.includes('+')) s += 'Z';
        const d = new Date(s);
        return d.toLocaleString('vi-VN', {{
          timeZone: 'Asia/Ho_Chi_Minh',
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false
        }});
      }} catch (e) {{
        return isoStr.substring(0, 19).replace('T', ' ');
      }}
    }}

    // Xử lý gửi Form đóng dấu
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
            <div class="meta-item">
              <strong>Trạng thái:</strong> ✅ Đóng dấu hoàn tất thành công!<br/>
              <strong>EC2 Worker thực thi:</strong> <code>${{data.worker_host || 'ec2-worker'}}</code><br/>
              <strong>Tài liệu:</strong> <code>${{data.doc_name}}.pdf</code> (${{data.pages_count}} trang)<br/>
              <strong>Thời gian xử lý:</strong> <code>${{data.processing_time_ms}} ms</code><br/>
              <strong>Mã băm SHA-256 định danh:</strong> <code>${{data.sha256}}</code>
            </div>
            <a class="btn-download" href="${{data.download_url}}" target="_blank">📥 Tải tài liệu hoàn tất (Download)</a>
          `;
        }}
      }} catch (err) {{
        resBox.style.display = 'block';
        resBox.className = 'result error';
        resBox.innerHTML = '<strong>Lỗi kết nối máy chủ:</strong> ' + err.message;
      }} finally {{
        btn.disabled = false;
        btn.textContent = '⚡ Thực thi Đóng dấu & Xuất bản quyền';
      }}
    }});

    // Tải danh sách Audit Logs
    async function loadAuditLogs() {{
      const tbody = document.querySelector('#auditTable tbody');
      tbody.innerHTML = '<tr><td colspan="8" style="text-align: center;">Đang nạp dữ liệu từ CSDL...</td></tr>';
      try {{
        const resp = await fetch('/api/v1/audit-logs?limit=50');
        const data = await resp.json();
        if (!data.logs || !data.logs.length) {{
          tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: #64748b;">Chưa có bản ghi kiểm toán nào.</td></tr>';
          return;
        }}
        tbody.innerHTML = data.logs.map(l => {{
          const sha = l.sha256 || l.sha256_hash || '-';
          const worker = l.worker_host || l.worker || '-';
          const timeVN = l.created_at_vn || formatVNTime(l.created_at);
          return `
          <tr>
            <td>#${{l.id}}</td>
            <td><b>${{timeVN}}</b></td>
            <td><code>${{l.client_id || 'default'}}</code></td>
            <td title="${{l.doc_name}}">${{l.doc_name}}</td>
            <td>${{l.pages_count || 0}}</td>
            <td><small><code>${{worker}}</code></small></td>
            <td>${{l.processing_time_ms ? l.processing_time_ms.toFixed(1) + ' ms' : '-'}}</td>
            <td title="${{sha}}"><code>${{sha && sha !== '-' ? sha.substring(0, 14) + '...' : '-'}}</code></td>
          </tr>
          `;
        }}).join('');
      }} catch (err) {{
        tbody.innerHTML = `<tr><td colspan="8" style="color: red; text-align: center;">Lỗi tải dữ liệu: ${{err.message}}</td></tr>`;
      }}
    }}

    // Kiểm tra tính toàn vẹn qua mã SHA-256
    async function verifyDoc() {{
      const hash = document.getElementById('verifyShaInput').value.trim();
      const resDiv = document.getElementById('verifyResult');
      if (!hash) return;
      resDiv.innerHTML = 'Đang tra cứu cơ sở dữ liệu kiểm toán...';
      try {{
        const resp = await fetch(`/api/v1/audit-logs/verify/${{hash}}`);
        const data = await resp.json();
        if (data.verified) {{
          const doc = data.document;
          const timeVN = doc.created_at_vn || formatVNTime(doc.created_at);
          const worker = doc.worker_host || doc.worker || 'ec2-worker';
          const sha = doc.sha256 || doc.sha256_hash || hash;
          resDiv.innerHTML = `
            <div style="background: #ecfdf5; border: 1px solid #10b981; padding: 16px; border-radius: 8px;">
              <strong style="color: #065f46; font-size: 15px;">✅ TÀI LIỆU CHÍNH THỐNG:</strong> ${{data.message}}<br/>
              <div style="margin-top: 8px; font-size: 13px; line-height: 1.8; color: #1e293b;">
                • <b>Hệ thống cấp phát (Client ID):</b> <code>${{doc.client_id || 'default'}}</code><br/>
                • <b>Tài liệu gốc:</b> <code>${{doc.doc_name}}</code> (${{doc.pages_count || 0}} trang)<br/>
                • <b>Thời gian cấp (Giờ Việt Nam):</b> <b>${{timeVN}}</b><br/>
                • <b>Máy chủ EC2 thực thi:</b> <code>${{worker}}</code><br/>
                • <b>Mã băm SHA-256 kiểm định:</b> <code style="word-break: break-all;">${{sha}}</code>
              </div>
            </div>
          `;
        }} else {{
          resDiv.innerHTML = `
            <div style="background: #fef2f2; border: 1px solid #ef4444; padding: 12px; border-radius: 8px; color: #991b1b;">
              <strong>❌ KHÔNG HỢP LỆ:</strong> ${{data.message}}
            </div>
          `;
        }}
      }} catch (err) {{
        resDiv.innerHTML = `<span style="color: red;">Lỗi khi kết nối API: ${{err.message}}</span>`;
      }}
    }}
  </script>
</body>
</html>"""


# ==============================================================================
# 8. ĐIỂM KHỞI CHẠY UVICORN
# ==============================================================================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
