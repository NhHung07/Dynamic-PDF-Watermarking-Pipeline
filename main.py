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
import concurrent.futures
import zipfile
import io

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
SERVICE_NAME = "Online-PDF-Watermark-Platform"
SERVICE_VERSION = "2.1.0"

DB_URL = os.getenv("DB_URL") or os.getenv("DATABASE_URL") or "sqlite:////tmp/audit.db"
S3_BUCKET = os.getenv("S3_BUCKET", "uet-pdf-watermark")
EFS_DIR = os.getenv("EFS_DIR", "/mnt/efs")
AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-1")
API_KEY = os.getenv("API_KEY", "")  # Để trống nếu không yêu cầu xác thực API Key

# Múi giờ Việt Nam (UTC+7 / GMT+7)
VN_TIMEZONE = timezone(timedelta(hours=7))

# Thiết lập thư mục EFS cache (với fallback an toàn và kiểm tra quyền ghi)
def setup_storage_dir(base_path: str) -> str:
    """Đảm bảo thư mục lưu trữ tồn tại, có quyền ghi và tạo sẵn input/fonts."""
    candidates = [base_path, "/tmp/watermark_efs_cache", "/tmp/watermark_efs_fallback"]
    for candidate in candidates:
        try:
            os.makedirs(candidate, mode=0o777, exist_ok=True)
            input_p = os.path.join(candidate, "input")
            os.makedirs(input_p, mode=0o777, exist_ok=True)
            try:
                os.chmod(candidate, 0o777)
                os.chmod(input_p, 0o777)
            except Exception:
                pass
            test_f = os.path.join(input_p, ".perm_test")
            with open(test_f, "w") as f:
                f.write("ok")
            os.remove(test_f)
            return candidate
        except Exception:
            continue
    return "/tmp/watermark_efs_fallback"

EFS_DIR = setup_storage_dir(os.getenv("EFS_DIR", "/mnt/efs"))
os.makedirs(os.path.join(EFS_DIR, "input"), mode=0o777, exist_ok=True)
os.makedirs("/tmp/wm_work", mode=0o777, exist_ok=True)

# Khởi tạo kết nối SQLAlchemy & Boto3 S3
engine = create_engine(DB_URL, pool_pre_ping=True)


def get_boto3_s3_client():
    cred_files = ["hung_accessKeys.csv", "hung_credentials.csv"]
    for cred_file in cred_files:
        if os.path.exists(cred_file):
            try:
                import csv
                with open(cred_file, mode="r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        ak = row.get("Access key ID") or row.get("AccessKeyId")
                        sk = row.get("Secret access key") or row.get("SecretAccessKey")
                        if ak and sk:
                            return boto3.client(
                                "s3",
                                aws_access_key_id=ak.strip(),
                                aws_secret_access_key=sk.strip(),
                                region_name=AWS_REGION,
                            )
            except Exception:
                pass
    return boto3.client("s3", region_name=AWS_REGION)


s3_client = get_boto3_s3_client()

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



def format_size(bytes_num: int) -> str:
    """Chuyển đổi kích thước byte sang định dạng đọc được (KB, MB)."""
    val = float(bytes_num)
    for unit in ["B", "KB", "MB", "GB"]:
        if val < 1024.0:
            return f"{val:.1f} {unit}"
        val /= 1024.0
    return f"{val:.1f} TB"


def get_document_metadata(file_path: str) -> dict:
    """Trích xuất số trang và dung lượng của tệp PDF."""
    size_bytes = 0
    pages_count = 0
    try:
        if os.path.exists(file_path):
            size_bytes = os.path.getsize(file_path)
            if size_bytes > 0:
                try:
                    doc = pymupdf.open(file_path)
                    pages_count = len(doc)
                    doc.close()
                except Exception:
                    try:
                        import fitz
                        doc = fitz.open(file_path)
                        pages_count = len(doc)
                        doc.close()
                    except Exception:
                        pass
    except Exception:
        pass
    return {
        "size_bytes": size_bytes,
        "size_formatted": format_size(size_bytes),
        "pages_count": pages_count,
    }


def list_master_documents() -> list[dict]:
    """Lấy danh sách các tài liệu gốc có sẵn trong kho EFS, tệp mẫu cục bộ và S3 với auto-caching."""
    docs_dict = {}

    # 1. Quét S3 bucket input/ trước (Nguồn lưu trữ bền vững chuẩn)
    s3_filenames = set()
    try:
        resp = s3_client.list_objects_v2(Bucket=S3_BUCKET, Prefix="input/", MaxKeys=50)
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            if key.lower().endswith(".pdf"):
                fname = os.path.basename(key)
                code = os.path.splitext(fname)[0]
                size_b = obj.get("Size", 0)
                s3_filenames.add(fname.lower())
                s3_filenames.add(code.lower())

                # Tự động nạp vào bộ nhớ đệm EFS nếu chưa có để đảm bảo EFS luôn sẵn sàng!
                cached_path = os.path.join(EFS_DIR, "input", f"{code}.pdf")
                need_download = not os.path.exists(cached_path) or os.path.getsize(cached_path) == 0
                if need_download:
                    try:
                        s3_client.download_file(S3_BUCKET, key, cached_path)
                        try:
                            os.chmod(cached_path, 0o666)
                        except Exception:
                            pass
                    except Exception as e:
                        print(f"[WARN] Failed to download {key} to EFS: {e}")

                meta = get_document_metadata(cached_path)
                pages_num = meta["pages_count"] if meta["pages_count"] > 0 else (47 if code == "ModelOptimization" else 1)
                size_text = meta["size_formatted"] if meta["size_bytes"] > 0 else format_size(size_b)

                docs_dict[code] = {
                    "doc_code": code,
                    "filename": fname,
                    "display_name": clean_doc_title(code),
                    "pages_count": pages_num,
                    "size_formatted": size_text,
                    "source": "Amazon EFS Cache",
                }
    except Exception as e:
        print(f"[WARN] S3 list objects: {e}")

    # 2. Thư mục EFS cache input (Dọn sạch cache mồ côi nếu file đã bị xóa trên S3)
    efs_input = os.path.join(EFS_DIR, "input")
    if os.path.exists(efs_input):
        for fname in sorted(os.listdir(efs_input)):
            if fname.lower().endswith(".pdf"):
                code = os.path.splitext(fname)[0]
                fpath = os.path.join(efs_input, fname)
                
                # Nếu file trong cache không tồn tại trên S3 và không phải tệp mẫu mặc định -> Dọn sạch cache
                if (fname.lower() not in s3_filenames and 
                    code.lower() not in s3_filenames and 
                    fname != "ModelOptimization.pdf" and 
                    fname != "Đề tài BTL.pdf"):
                    try:
                        os.remove(fpath)
                        print(f"[INFO] Cleaned stale orphan cache: {fpath}")
                    except Exception:
                        pass
                    continue

                if code not in docs_dict:
                    meta = get_document_metadata(fpath)
                    docs_dict[code] = {
                        "doc_code": code,
                        "filename": fname,
                        "display_name": clean_doc_title(code),
                        "pages_count": meta["pages_count"],
                        "size_formatted": meta["size_formatted"],
                        "source": "Amazon EFS Cache",
                    }

    # 3. Tệp cục bộ mặc định tại thư mục gốc (ModelOptimization.pdf, etc.)
    for fname in sorted(os.listdir(".")):
        if fname.lower().endswith(".pdf") and not fname.startswith("report") and not fname.startswith("presentation"):
            code = os.path.splitext(fname)[0]
            if code not in docs_dict:
                meta = get_document_metadata(fname)
                docs_dict[code] = {
                    "doc_code": code,
                    "filename": fname,
                    "display_name": clean_doc_title(code),
                    "pages_count": meta["pages_count"],
                    "size_formatted": meta["size_formatted"],
                    "source": "Amazon EFS Cache",
                }

    return list(docs_dict.values())


def resolve_master_document_path(doc_code: str) -> tuple[str, str]:
    """
    Tìm đường dẫn file tài liệu gốc từ kho EFS, kéo từ S3 hoặc lấy từ tệp mẫu có sẵn.
    Trả về: (đường_dẫn_file_local_efs, tên_hiển_thị).
    """
    storage_code = safe_storage_key(doc_code)
    display_name = clean_doc_title(doc_code)
    cached_path = os.path.join(EFS_DIR, "input", f"{storage_code}.pdf")

    if not os.path.exists(cached_path):
        # 1. Thử kéo từ S3
        s3_key = f"input/{storage_code}.pdf"
        try:
            s3_client.download_file(S3_BUCKET, s3_key, cached_path)
        except Exception:
            # 2. Thử tìm tệp mẫu cục bộ
            candidates = [
                f"{storage_code}.pdf",
                f"{doc_code}.pdf",
                "ModelOptimization.pdf"
            ]
            found = None
            for cand in candidates:
                if os.path.exists(cand):
                    found = cand
                    break
            if found:
                import shutil
                shutil.copyfile(found, cached_path)
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"Không tìm thấy tài liệu gốc '{doc_code}' trong kho lưu trữ EFS/S3."
                )

    return cached_path, display_name


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
            # Điểm tâm chính xác của trang giấy
            cx, cy = w / 2.0, h / 2.0

            # Góc nghiêng chéo tính theo tỷ lệ trang (hướng chéo lên từ góc dưới-trái qua tâm lên góc trên-phải)
            diag_angle = math.degrees(math.atan2(h, w))
            angle_deg = min(48.0, max(30.0, diag_angle * 0.82))
            rad = math.radians(angle_deg)
            cos_a = math.cos(rad)
            sin_a = math.sin(rad)

            # Tính chiều dài khả dụng tối đa dọc theo hướng nghiêng để chữ không chạm mép giấy
            # Chừa lề an toàn tối thiểu: 45pt hai bên, 55pt trên dưới
            margin_x = 45.0
            margin_y = 55.0
            max_len_x = max(100.0, (cx - margin_x) / cos_a * 2.0)
            max_len_y = max(100.0, (cy - margin_y) / sin_a * 2.0)
            max_allowed_len = min(max_len_x, max_len_y)

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

            # Điểm bắt đầu vẽ sao cho TRỌNG TÂM CỦA CHUỖI KÝ TỰ TRÙNG KHÍT VỚI TÂM TRANG GIẤY (cx, cy)
            # x_start ở bên trái tâm: cx - (L/2)*cos
            # y_start ở bên dưới tâm: cy + (L/2)*sin (trong hệ tọa độ PDF, y lớn hơn là ở phía dưới)
            p_start = pymupdf.Point(cx - (actual_tlen / 2.0) * cos_a, cy + (actual_tlen / 2.0) * sin_a)

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


class SingleDocumentWatermarkRequest(BaseModel):
    client_id: Optional[str] = Field("web-studio", description="Mã hệ thống gọi hoặc phiên người dùng")
    recipient_name: Optional[str] = Field(None, description="Họ và tên người nhận")
    recipient_id: Optional[str] = Field(None, description="Mã số người nhận (MSSV/ID/CMND)")
    diagonal_text: Optional[str] = Field(None, description="Chữ chìm chéo giữa trang")
    stamp_text: Optional[str] = Field(None, description="Chữ hiển thị trong khung con dấu góc trên bên phải")
    header_text: Optional[str] = Field(None, description="Dòng chữ tiêu đề trang")
    footer_text: Optional[str] = Field(None, description="Dòng chữ chân trang")
    diagonal_opacity: Optional[float] = Field(0.22, ge=0.05, le=1.0, description="Độ mờ chữ chéo (0.05 đến 1.0)")
    diagonal_fontsize: Optional[int] = Field(38, ge=12, le=72, description="Cỡ chữ watermark chéo")


class BatchWatermarkRequest(BaseModel):
    client_id: Optional[str] = Field("web-batch", description="Mã định danh phiên đóng dấu hàng loạt")
    stamp_text: Optional[str] = Field("CONFIDENTIAL", description="Con dấu tổ chức góc trên")
    header_template: Optional[str] = Field("Bản cấp phát nội bộ | Người nhận: {name} ({id})", description="Mẫu dòng tiêu đề")
    footer_template: Optional[str] = Field("Bản quyền tài liệu thuộc UET - VNU | Mã kiểm định: {id}", description="Mẫu dòng chân trang")
    diagonal_template: Optional[str] = Field("BẢN SAO BẢO MẬT - {name} - {id}", description="Mẫu chữ chìm chéo giữa trang")
    recipients_text: Optional[str] = Field(None, description="Danh sách người nhận dạng văn bản nhiều dòng hoặc CSV")
    recipients_list: Optional[List[Dict[str, Any]]] = Field(None, description="Danh sách người nhận dạng JSON mảng")
    diagonal_opacity: Optional[float] = Field(0.22, ge=0.05, le=1.0)
    diagonal_fontsize: Optional[int] = Field(38, ge=12, le=72)


# ==============================================================================
# 6. KHỞI TẠO ỨNG DỤNG FASTAPI & ENDPOINTS
# ==============================================================================
app = FastAPI(
    title=SERVICE_NAME,
    version=SERVICE_VERSION,
    description="Nền tảng ứng dụng web đóng dấu bản quyền tài liệu số trực tuyến, kiểm định tính toàn vẹn (SHA-256) và kiểm toán phân tán trên AWS.",
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
# 6.0. CÁC ENDPOINT QUẢN TRỊ KHO TÀI LIỆU GỐC & ĐÓNG DẤU HÀNG LOẠT (WEB APP)
# ------------------------------------------------------------------------------
@app.post("/api/v1/documents/upload")
async def upload_master_document(
    pdf_file: UploadFile = File(...),
    custom_title: Optional[str] = Form(None)
):
    """
    Tải lên tài liệu gốc MỘT LẦN DUY NHẤT vào kho EFS & S3.
    Người dùng nhận được doc_code để tái sử dụng tạo bao nhiêu watermark tùy thích mà không cần up lại file.
    """
    if not pdf_file.filename or not pdf_file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận tệp tài liệu định dạng PDF.")

    pdf_bytes = await pdf_file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Tệp PDF tải lên bị rỗng.")

    clean_name = custom_title or pdf_file.filename
    display_name = clean_doc_title(clean_name)
    storage_code = safe_storage_key(clean_name)
    cached_path = os.path.join(EFS_DIR, "input", f"{storage_code}.pdf")

    # Lưu vào EFS
    with open(cached_path, "wb") as f:
        f.write(pdf_bytes)

    # Đồng bộ lên Amazon S3
    s3_key = f"input/{storage_code}.pdf"
    try:
        s3_client.upload_file(cached_path, S3_BUCKET, s3_key)
    except Exception as e:
        print(f"[WARN] S3 upload master doc: {e}")

    meta = get_document_metadata(cached_path)
    master_sha256 = hashlib.sha256(pdf_bytes).hexdigest()

    return {
        "status": "success",
        "message": "Tài liệu gốc đã được lưu trữ thành công trên EFS/S3 sẵn sàng đóng dấu.",
        "doc_code": storage_code,
        "filename": pdf_file.filename,
        "display_name": display_name,
        "pages_count": meta["pages_count"],
        "size_formatted": meta["size_formatted"],
        "sha256": master_sha256,
        "created_at_vn": format_vn_time(datetime.now(timezone.utc)),
    }


@app.get("/api/v1/documents")
def get_master_documents_api():
    """Liệt kê toàn bộ các tài liệu gốc có sẵn trong kho lưu trữ EFS/S3."""
    docs = list_master_documents()
    return {
        "status": "success",
        "total": len(docs),
        "documents": docs,
    }


@app.delete("/api/v1/documents/{doc_code}")
def delete_master_document(doc_code: str):
    """
    Xóa tài liệu gốc khỏi kho EFS cache và Amazon S3 bucket.
    Hỗ trợ đối soát đa biến thể tên tệp để đảm bảo xóa triệt để.
    """
    storage_code = safe_storage_key(doc_code)
    deleted = False

    # 1. Xóa cache trên Amazon EFS
    efs_input = os.path.join(EFS_DIR, "input")
    efs_paths = [
        os.path.join(efs_input, f"{storage_code}.pdf"),
        os.path.join(efs_input, f"{doc_code}.pdf"),
        os.path.join(efs_input, doc_code),
    ]
    for p in efs_paths:
        if os.path.exists(p):
            try:
                os.remove(p)
                deleted = True
                print(f"[INFO] Deleted EFS cache: {p}")
            except Exception as e:
                print(f"[WARN] Error deleting EFS path {p}: {e}")

    # 2. Xóa trên Amazon S3 input/
    s3_keys = [
        f"input/{storage_code}.pdf",
        f"input/{doc_code}.pdf",
        f"input/{doc_code}",
    ]
    for key in s3_keys:
        try:
            # Thử head_object để xác định tồn tại
            s3_client.head_object(Bucket=S3_BUCKET, Key=key)
            s3_client.delete_object(Bucket=S3_BUCKET, Key=key)
            deleted = True
            print(f"[INFO] Deleted S3 key: {key}")
        except ClientError as e:
            code_err = e.response.get("Error", {}).get("Code", "")
            if code_err not in ("404", "NoSuchKey"):
                # Thử xóa trực tiếp nếu head bị chặn
                try:
                    s3_client.delete_object(Bucket=S3_BUCKET, Key=key)
                    deleted = True
                except Exception:
                    pass
        except Exception:
            pass

    # 3. Quét S3 input/ nếu tên chứa ký tự đặc biệt hoặc hoa/thường khác nhau
    if not deleted:
        try:
            resp = s3_client.list_objects_v2(Bucket=S3_BUCKET, Prefix="input/")
            for obj in resp.get("Contents", []):
                k = obj["Key"]
                fname = os.path.basename(k)
                code = os.path.splitext(fname)[0]
                if (code.lower() == doc_code.lower() or 
                    safe_storage_key(code).lower() == storage_code.lower() or
                    fname.lower() == doc_code.lower()):
                    s3_client.delete_object(Bucket=S3_BUCKET, Key=k)
                    deleted = True
                    print(f"[INFO] Deleted S3 scanned key: {k}")
        except Exception as e:
            print(f"[WARN] S3 scan delete failed: {e}")

    # 4. Kiểm tra tệp cục bộ nếu có (ngoại trừ tệp ModelOptimization mặc định)
    for local_f in [f"{storage_code}.pdf", f"{doc_code}.pdf"]:
        if os.path.exists(local_f) and local_f != "ModelOptimization.pdf" and local_f != "Đề tài BTL.pdf":
            try:
                os.remove(local_f)
                deleted = True
            except Exception:
                pass

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy tài liệu gốc '{doc_code}' trong kho EFS/S3 để xóa."
        )

    return {
        "status": "success",
        "message": f"Đã xóa thành công tài liệu gốc '{doc_code}' khỏi kho EFS và S3.",
        "doc_code": doc_code
    }


@app.post("/api/v1/documents/{doc_code}/watermark")
async def watermark_stored_document(
    doc_code: str,
    req: SingleDocumentWatermarkRequest
):
    """
    Tạo watermark trực tiếp từ tài liệu gốc ĐÃ CÓ trong kho EFS/S3.
    Người dùng KHÔNG CẦN upload lại file PDF, thời gian xử lý siêu tốc < 1 giây!
    """
    start_t = time.perf_counter()
    request_id = str(uuid.uuid4())
    worker_host = socket.gethostname()
    timestamp = int(time.time())

    cached_input_path, display_name = resolve_master_document_path(doc_code)
    storage_code = safe_storage_key(doc_code)

    r_name = (req.recipient_name or "").strip()
    r_id = (req.recipient_id or "").strip()

    diag = req.diagonal_text or (f"BẢN SAO BẢO MẬT - {r_name} ({r_id})" if r_name else "CONFIDENTIAL")
    hdr = req.header_text or f"Phát hành nội bộ | Cấp cho: {r_name or 'Người dùng'} | {display_name}"
    ftr = req.footer_text or f"Bản quyền thuộc UET - VNU | Mã kiểm định: {r_id or request_id[:8]}"
    stamp = req.stamp_text or "UET - VNU"

    out_filename = f"{storage_code}_{r_id or 'user'}_{request_id[:8]}.pdf"
    local_out_path = os.path.join("/tmp/wm_work", out_filename)

    try:
        pages_count, digest = apply_watermarks(
            input_path=cached_input_path,
            output_path=local_out_path,
            header_text=hdr,
            footer_text=ftr,
            diagonal_text=diag,
            stamp_text=stamp,
            diagonal_opacity=req.diagonal_opacity or 0.22,
            diagonal_fontsize=req.diagonal_fontsize or 38,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi xử lý đóng dấu: {e}")

    # S3 Upload & Pre-signed URL
    output_key = f"output/{out_filename}"
    dl_filename = f"{display_name}_{r_name or 'watermarked'}.pdf"
    encoded_name = urllib.parse.quote(dl_filename)
    content_disp = f'attachment; filename="watermarked.pdf"; filename*=UTF-8\'\'{encoded_name}'
    download_url = f"/api/v1/download/{out_filename}?original_name={encoded_name}"

    try:
        s3_client.upload_file(local_out_path, S3_BUCKET, output_key)
        download_url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": S3_BUCKET,
                "Key": output_key,
                "ResponseContentDisposition": content_disp,
            },
            ExpiresIn=3600,
        )
    except Exception as e:
        print(f"[WARN] S3 single watermark upload: {e}")

    proc_time_ms = (time.perf_counter() - start_t) * 1000.0

    record_audit(
        request_id=request_id,
        client_id=req.client_id or "web-studio",
        doc_name=display_name,
        pages_count=pages_count,
        sha256_hash=digest,
        worker_host=worker_host,
        output_key=output_key,
        proc_time_ms=proc_time_ms,
        student_id=r_id,
        full_name=r_name,
        doc_code=storage_code,
        meta_dict={"mode": "single_studio", "recipient": r_name, "id": r_id},
    )

    return {
        "status": "success",
        "request_id": request_id,
        "doc_code": storage_code,
        "doc_name": display_name,
        "pages_count": pages_count,
        "sha256": digest,
        "worker_host": worker_host,
        "download_url": download_url,
        "filename": dl_filename,
        "processing_time_ms": round(proc_time_ms, 1),
        "created_at_vn": format_vn_time(datetime.now(timezone.utc)),
    }


@app.post("/api/v1/documents/{doc_code}/batch")
async def batch_watermark_document(
    doc_code: str,
    req: BatchWatermarkRequest
):
    """
    ĐÓNG DẤU HÀNG LOẠT (BATCH PROCESSING) TỪ TÀI LIỆU GỐC & XUẤT FILE NÉN ZIP:
    Nhận danh sách N người nhận -> Chạy đa luồng sinh N bản PDF riêng biệt -> Nén toàn bộ vào tệp ZIP.
    Mỗi file PDF đều có mã băm SHA-256 riêng và được lưu vết trong CSDL PostgreSQL!
    """
    start_t = time.perf_counter()
    batch_id = uuid.uuid4().hex[:8]
    worker_host = socket.gethostname()
    timestamp = int(time.time())

    cached_input_path, display_name = resolve_master_document_path(doc_code)
    storage_code = safe_storage_key(doc_code)

    # 1. Phân tích danh sách người nhận
    recipients = []
    if req.recipients_list:
        for item in req.recipients_list:
            name = str(item.get("name", "")).strip()
            r_id = str(item.get("id", "")).strip()
            if name or r_id:
                recipients.append({"name": name, "id": r_id})
    elif req.recipients_text:
        lines = [line.strip() for line in req.recipients_text.splitlines() if line.strip()]
        for line in lines:
            parts = [p.strip() for p in re.split(r"[,|\t\-]+", line) if p.strip()]
            if len(parts) >= 2:
                recipients.append({"name": parts[0], "id": parts[1]})
            elif len(parts) == 1:
                recipients.append({"name": parts[0], "id": f"ID-{len(recipients)+1:03d}"})

    if not recipients:
        raise HTTPException(
            status_code=400,
            detail="Danh sách người nhận không hợp lệ. Vui lòng nhập ít nhất 1 người nhận."
        )

    if len(recipients) > 100:
        raise HTTPException(status_code=400, detail="Số lượng người nhận tối đa cho mỗi mẻ là 100 người.")

    today_vn = datetime.now(VN_TIMEZONE).strftime("%d/%m/%Y")

    # 2. Hàm xử lý từng bản ghi
    def process_item(r, idx):
        r_name = r.get("name", f"NguoiNhan_{idx+1}")
        r_id = r.get("id", f"{idx+1:03d}")
        out_fname = f"{storage_code}_{r_id}_{uuid.uuid4().hex[:6]}.pdf"
        local_out = os.path.join("/tmp/wm_work", out_fname)

        diag = (req.diagonal_template or "BẢN SAO BẢO MẬT - {name} - {id}")\
            .replace("{name}", r_name).replace("{id}", r_id).replace("{date}", today_vn).replace("{doc}", display_name)
        hdr = (req.header_template or "Bản phát hành nội bộ | Người nhận: {name}")\
            .replace("{name}", r_name).replace("{id}", r_id).replace("{date}", today_vn).replace("{doc}", display_name)
        ftr = (req.footer_template or "Bản quyền UET - VNU | Mã số: {id}")\
            .replace("{name}", r_name).replace("{id}", r_id).replace("{date}", today_vn).replace("{doc}", display_name)

        t0 = time.perf_counter()
        p_count, sha = apply_watermarks(
            input_path=cached_input_path,
            output_path=local_out,
            header_text=hdr,
            footer_text=ftr,
            diagonal_text=diag,
            stamp_text=req.stamp_text,
            diagonal_opacity=req.diagonal_opacity or 0.22,
            diagonal_fontsize=req.diagonal_fontsize or 38,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        dl_name = f"{display_name}_{r_name}_{r_id}.pdf"
        encoded_name = urllib.parse.quote(dl_name)
        s3_key = f"output/{out_fname}"
        content_disp = f'attachment; filename="watermarked.pdf"; filename*=UTF-8\'\'{encoded_name}'
        dl_url = f"/api/v1/download/{out_fname}?original_name={encoded_name}"

        try:
            s3_client.upload_file(local_out, S3_BUCKET, s3_key)
            dl_url = s3_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": S3_BUCKET,
                    "Key": s3_key,
                    "ResponseContentDisposition": content_disp,
                },
                ExpiresIn=3600,
            )
        except Exception:
            pass

        req_uuid = str(uuid.uuid4())
        record_audit(
            request_id=req_uuid,
            client_id=req.client_id or "web-batch",
            doc_name=display_name,
            pages_count=p_count,
            sha256_hash=sha,
            worker_host=worker_host,
            output_key=s3_key,
            proc_time_ms=elapsed_ms,
            student_id=r_id,
            full_name=r_name,
            doc_code=storage_code,
            meta_dict={"batch_id": batch_id, "recipient": r_name, "id": r_id},
        )

        return {
            "index": idx + 1,
            "recipient": r_name,
            "id": r_id,
            "filename": dl_name,
            "local_path": local_out,
            "pages_count": p_count,
            "sha256": sha,
            "download_url": dl_url,
            "processing_time_ms": round(elapsed_ms, 1),
        }

    # 3. Thực thi song song qua ThreadPoolExecutor
    max_workers = min(8, max(2, (os.cpu_count() or 2) * 2))
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(process_item, r, idx) for idx, r in enumerate(recipients)]
        for fut in concurrent.futures.as_completed(futures):
            results.append(fut.result())

    results.sort(key=lambda x: x["index"])

    # 4. Đóng gói tệp ZIP hoàn thiện
    zip_fname = f"batch_{batch_id}_{storage_code}.zip"
    local_zip_path = os.path.join("/tmp/wm_work", zip_fname)

    manifest_lines = ["STT,Họ và tên,Mã định danh (MSSV/ID),Tên tệp PDF,Mã băm SHA-256 (Kiểm định toàn vẹn),Thời gian xử lý (ms)"]
    for it in results:
        manifest_lines.append(f'{it["index"]},"{it["recipient"]}","{it["id"]}","{it["filename"]}",{it["sha256"]},{it["processing_time_ms"]}')
    manifest_csv = "\n".join(manifest_lines)

    with zipfile.ZipFile(local_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("kiem_dinh_manifest.csv", manifest_csv.encode("utf-8-sig"))
        for it in results:
            if os.path.exists(it["local_path"]):
                zf.write(it["local_path"], arcname=it["filename"])

    zip_s3_key = f"output/{zip_fname}"
    zip_dl_name = f"{display_name}_batch_{len(results)}_files.zip"
    encoded_zip_name = urllib.parse.quote(zip_dl_name)
    zip_content_disp = f'attachment; filename="batch.zip"; filename*=UTF-8\'\'{encoded_zip_name}'
    zip_download_url = f"/api/v1/download/{zip_fname}?original_name={encoded_zip_name}"

    try:
        s3_client.upload_file(local_zip_path, S3_BUCKET, zip_s3_key)
        zip_download_url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": S3_BUCKET,
                "Key": zip_s3_key,
                "ResponseContentDisposition": zip_content_disp,
            },
            ExpiresIn=3600,
        )
    except Exception as e:
        print(f"[WARN] S3 Upload zip: {e}")

    total_time_ms = (time.perf_counter() - start_t) * 1000.0

    return {
        "status": "success",
        "batch_id": batch_id,
        "doc_code": storage_code,
        "display_name": display_name,
        "total_items": len(results),
        "successful_items": len(results),
        "total_time_ms": round(total_time_ms, 1),
        "worker_host": worker_host,
        "zip_download_url": zip_download_url,
        "zip_filename": zip_dl_name,
        "items": [
            {
                "index": it["index"],
                "recipient": it["recipient"],
                "id": it["id"],
                "filename": it["filename"],
                "sha256": it["sha256"],
                "download_url": it["download_url"],
                "processing_time_ms": it["processing_time_ms"],
            }
            for it in results
        ],
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
    """Tải trực tiếp file PDF hoặc ZIP từ thư mục tạm làm việc với tiêu đề tên tệp UTF-8."""
    clean = os.path.basename(filename)
    path = os.path.join("/tmp/wm_work", clean)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Tệp tin không tồn tại hoặc đã bị dọn dẹp.")

    final_name = original_name or clean
    if not (final_name.lower().endswith(".pdf") or final_name.lower().endswith(".zip")):
        final_name += ".pdf"
    encoded_name = urllib.parse.quote(final_name)
    media_type = "application/zip" if clean.lower().endswith(".zip") else "application/pdf"
    fallback_name = "batch.zip" if clean.lower().endswith(".zip") else "document.pdf"
    headers = {
        "Content-Disposition": f'attachment; filename="{fallback_name}"; filename*=UTF-8\'\'{encoded_name}'
    }
    return FileResponse(path, media_type=media_type, headers=headers)


# ==============================================================================
# 7. GIAO DIỆN WEB APPLICATION HOÀN CHỈNH (WEB STUDIO & BATCH ZIP PLATFORM)
# ==============================================================================
WEB_APP_HTML = r"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>UET Smart Watermark Platform - Nền tảng Đóng dấu & Bảo mật Tài liệu Số</title>
  <style>
    :root {
      --primary: #1d4ed8;
      --primary-hover: #1e40af;
      --primary-light: #eff6ff;
      --success: #059669;
      --success-light: #ecfdf5;
      --warning: #d97706;
      --danger: #dc2626;
      --bg: #f8fafc;
      --card: #ffffff;
      --text: #0f172a;
      --text-muted: #64748b;
      --border: #e2e8f0;
      --border-focus: #3b82f6;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
    body { background: var(--bg); color: var(--text); padding-bottom: 60px; line-height: 1.5; }
    
    /* Top Navbar */
    .navbar {
      background: #1e3a8a;
      color: #fff;
      padding: 16px 24px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    .nav-container {
      max-width: 1200px;
      margin: 0 auto;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .brand-icon {
      font-size: 28px;
    }
    .brand-title {
      font-size: 20px;
      font-weight: 700;
      letter-spacing: -0.3px;
    }
    .brand-subtitle {
      font-size: 12px;
      color: #93c5fd;
    }
    .infra-badges {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    .badge {
      font-size: 11px;
      font-weight: 600;
      padding: 4px 9px;
      border-radius: 999px;
      display: inline-flex;
      align-items: center;
      gap: 5px;
    }
    .badge-aws { background: rgba(255,255,255,0.15); color: #fff; border: 1px solid rgba(255,255,255,0.25); }
    .badge-dot { width: 7px; height: 7px; border-radius: 50%; background: #10b981; }

    /* Main Container */
    .main-wrap {
      max-width: 1200px;
      margin: 24px auto 0;
      padding: 0 16px;
    }

    /* Tabs Bar */
    .tabs-bar {
      display: flex;
      gap: 6px;
      background: #e2e8f0;
      padding: 6px;
      border-radius: 12px;
      margin-bottom: 24px;
      overflow-x: auto;
    }
    .tab-btn {
      flex: 1;
      min-width: 170px;
      padding: 10px 16px;
      border: none;
      background: transparent;
      color: #475569;
      font-size: 14px;
      font-weight: 600;
      border-radius: 8px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      transition: all 0.2s;
      white-space: nowrap;
    }
    .tab-btn:hover { background: rgba(255,255,255,0.6); color: var(--text); }
    .tab-btn.active { background: #fff; color: var(--primary); box-shadow: 0 2px 4px rgba(0,0,0,0.06); }

    /* Cards */
    .card {
      background: var(--card);
      border-radius: 12px;
      border: 1px solid var(--border);
      padding: 24px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.03);
      margin-bottom: 24px;
    }
    .card-title {
      font-size: 18px;
      font-weight: 700;
      color: #1e293b;
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .card-desc {
      font-size: 14px;
      color: var(--text-muted);
      margin-bottom: 20px;
      margin-top: -8px;
    }

    /* Forms & Grid */
    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
    .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }
    @media (max-width: 860px) {
      .grid-2, .grid-3 { grid-template-columns: 1fr; }
    }
    .field { margin-bottom: 16px; }
    label { display: block; font-size: 13px; font-weight: 600; color: #334155; margin-bottom: 6px; }
    .hint { font-size: 12px; color: var(--text-muted); margin-top: 4px; }
    input[type="text"], input[type="number"], select, textarea {
      width: 100%;
      padding: 10px 12px;
      border: 1px solid #cbd5e1;
      border-radius: 8px;
      font-size: 14px;
      background: #fff;
      transition: border-color 0.2s;
    }
    input:focus, select:focus, textarea:focus {
      outline: none;
      border-color: var(--border-focus);
      box-shadow: 0 0 0 3px rgba(59,130,246,0.15);
    }
    textarea { font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace; }

    /* Buttons */
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 10px 20px;
      border-radius: 8px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      border: none;
      transition: all 0.2s;
      text-decoration: none;
    }
    .btn-primary { background: var(--primary); color: #fff; }
    .btn-primary:hover { background: var(--primary-hover); }
    .btn-success { background: var(--success); color: #fff; }
    .btn-success:hover { background: #047857; }
    .btn-outline { background: #fff; border: 1px solid #cbd5e1; color: #334155; }
    .btn-outline:hover { background: #f1f5f9; border-color: #94a3b8; }
    .btn-danger-outline { background: #fff; border: 1px solid #fca5a5; color: #dc2626; padding: 6px 12px; font-size: 12px; }
    .btn-danger-outline:hover { background: #fef2f2; }
    .btn-sm { padding: 6px 12px; font-size: 12px; }
    .btn:disabled { opacity: 0.6; cursor: not-allowed; }

    /* Tables */
    .table-wrap { overflow-x: auto; margin-top: 12px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; text-align: left; }
    th { background: #f1f5f9; color: #475569; font-weight: 600; padding: 12px; border-bottom: 2px solid var(--border); }
    td { padding: 12px; border-bottom: 1px solid var(--border); vertical-align: middle; }
    tr:hover td { background: #f8fafc; }
    code { font-family: monospace; background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 12px; }

    /* Upload Dropzone */
    .dropzone {
      border: 2px dashed #93c5fd;
      border-radius: 12px;
      background: #f0f7ff;
      padding: 32px 20px;
      text-align: center;
      cursor: pointer;
      transition: all 0.2s;
    }
    .dropzone:hover, .dropzone.dragover { background: #e0f2fe; border-color: var(--primary); }
    .dropzone-icon { font-size: 40px; margin-bottom: 8px; }

    /* Preview Canvas Box */
    .preview-box {
      background: #f1f5f9;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 16px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
    }
    canvas#previewCanvas {
      background: #fff;
      box-shadow: 0 4px 12px rgba(0,0,0,0.12);
      border-radius: 4px;
      max-width: 100%;
      height: auto;
    }

    /* Result Banners */
    .alert-box {
      padding: 16px;
      border-radius: 8px;
      margin-top: 16px;
      display: none;
    }
    .alert-success { background: var(--success-light); border: 1px solid #10b981; color: #065f46; }
    .alert-error { background: #fef2f2; border: 1px solid #ef4444; color: #991b1b; }
    .alert-info { background: #eff6ff; border: 1px solid #3b82f6; color: #1e40af; }

    /* Status Pill */
    .source-pill {
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 999px;
      font-weight: 600;
    }
    .source-efs { background: #dcfce7; color: #15803d; }
    .source-s3 { background: #ffedd5; color: #c2410c; }
    .source-builtin { background: #e0e7ff; color: #4338ca; }

    .tab-content { display: none; }
    .tab-content.active { display: block; }
  </style>
</head>
<body>

  <!-- Top Navbar -->
  <header class="navbar">
    <div class="nav-container">
      <div class="brand">
        <span class="brand-icon">🛡️</span>
        <div>
          <div class="brand-title">UET Smart Watermark Platform</div>
          <div class="brand-subtitle">Nền tảng Quản trị & Đóng dấu Tài liệu Số Trực tuyến | ĐHQGHN</div>
        </div>
      </div>
      <div class="infra-badges">
        <span class="badge badge-aws"><span class="badge-dot"></span> ALB AWS Sẵn Sàng</span>
        <span class="badge badge-aws">⚙️ Auto Scaling (2+ Nodes)</span>
        <span class="badge badge-aws">🐘 RDS PostgreSQL 18.3</span>
        <span class="badge badge-aws">⚡ EFS + S3 Hybrid Cache</span>
      </div>
    </div>
  </header>

  <!-- Main Workspace -->
  <main class="main-wrap">

    <!-- Navigation Tabs -->
    <nav class="tabs-bar">
      <button class="tab-btn active" onclick="switchTab('tab-library')">📁 1. Kho Tài liệu Gốc</button>
      <button class="tab-btn" onclick="switchTab('tab-studio')">🎨 2. Phòng Đóng Dấu Đơn Lẻ</button>
      <button class="tab-btn" onclick="switchTab('tab-batch')">⚡ 3. Đóng Dấu Hàng Loạt (ZIP)</button>
      <button class="tab-btn" onclick="switchTab('tab-verify')">🔍 4. Kiểm Định SHA-256</button>
      <button class="tab-btn" onclick="switchTab('tab-logs')">📊 5. Nhật Ký Kiểm Toán RDS</button>
    </nav>

    <!-- TAB 1: KHO TÀI LIỆU GỐC -->
    <section id="tab-library" class="tab-content active">
      <div class="card">
        <h2 class="card-title">📁 Kho Lưu Trữ Tài Liệu Gốc (Master Document Library)</h2>
        <p class="card-desc">
          Tải tài liệu PDF lên <b>MỘT LẦN DUY NHẤT</b>. Hệ thống tự động đồng bộ lên bộ nhớ đệm tốc độ cao <b>Amazon EFS</b> và lưu trữ bền vững trên <b>Amazon S3</b>.
          Sau khi tải lên, bạn có thể tạo hàng trăm bản đóng dấu cá nhân hóa ngay lập tức mà <b>không cần tốn băng thông tải lại file!</b>
        </p>

        <!-- Dropzone -->
        <div class="dropzone" id="uploadDropzone" onclick="document.getElementById('masterFileInput').click()">
          <div class="dropzone-icon">📤</div>
          <h3 style="font-size: 16px; margin-bottom: 4px;">Kéo & thả tệp PDF tài liệu gốc vào đây, hoặc click để chọn file</h3>
          <p style="font-size: 12px; color: var(--text-muted);">Hỗ trợ giáo trình, đề thi, hợp đồng, tài liệu nội bộ PDF dung lượng tới 100MB</p>
          <input type="file" id="masterFileInput" accept=".pdf" style="display: none;" onchange="handleMasterFileSelect(this.files[0])" />
        </div>

        <!-- Optional custom title & upload action -->
        <div id="uploadActionArea" style="display: none; margin-top: 16px; padding: 16px; background: #f8fafc; border: 1px solid var(--border); border-radius: 8px;">
          <div class="grid-2">
            <div class="field">
              <label>Tệp đã chọn:</label>
              <div id="selectedFileName" style="font-weight: 600; color: var(--primary);"></div>
            </div>
            <div class="field">
              <label>Tên hiển thị gợi nhớ (tùy chọn):</label>
              <input type="text" id="customDocTitle" placeholder="Ví dụ: Đề thi Cuối Kỳ Mạng Máy Tính" />
            </div>
          </div>
          <div style="display: flex; gap: 10px; justify-content: flex-end; margin-top: 8px;">
            <button class="btn btn-outline btn-sm" onclick="cancelUpload()">Hủy</button>
            <button class="btn btn-primary" id="btnUploadSubmit" onclick="submitUploadMasterDoc()">🚀 Lưu Vào Kho EFS & S3</button>
          </div>
        </div>

        <div id="uploadStatusAlert" class="alert-box"></div>
      </div>

      <!-- Danh sách tài liệu có sẵn -->
      <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <h3 class="card-title" style="margin-bottom: 0;">📚 Danh Sách Tài Liệu Gốc Đang Có Trong Kho</h3>
          <button class="btn btn-outline btn-sm" onclick="loadMasterDocuments()">🔄 Làm mới danh sách</button>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Mã Tài Liệu</th>
                <th>Tên Tài Liệu Gốc</th>
                <th>Số Trang</th>
                <th>Dung Lượng</th>
                <th>Vị Trí Lưu Trữ</th>
                <th>Hành Động Khả Dụng</th>
              </tr>
            </thead>
            <tbody id="masterDocsTbody">
              <tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 24px;">Đang tải danh sách tài liệu từ EFS/S3...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- TAB 2: PHÒNG ĐÓNG DẤU ĐƠN LẺ & CANVAS PREVIEW -->
    <section id="tab-studio" class="tab-content">
      <div class="card">
        <h2 class="card-title">🎨 Phòng Đóng Dấu Đơn Lẻ Trực Quan (Live Watermark Studio)</h2>
        <p class="card-desc">Chọn tài liệu có sẵn trong kho, tùy biến chữ chìm và xem trước trang in trực tiếp trên Canvas trước khi xuất bản!</p>

        <div class="grid-2">
          <!-- Cột cấu hình -->
          <div>
            <div class="field">
              <label>1. Chọn tài liệu gốc từ kho:</label>
              <select id="singleDocSelect" onchange="onStudioDocChange()"></select>
              <div class="hint">Tài liệu đã nằm sẵn trên máy chủ EFS, đóng dấu trong &lt; 0.5s!</div>
            </div>

            <div class="grid-2">
              <div class="field">
                <label>2. Họ và tên người nhận:</label>
                <input type="text" id="recipientName" placeholder="Nguyễn Văn An" value="Nguyễn Văn An" oninput="onRecipientChange()" />
              </div>
              <div class="field">
                <label>3. Mã định danh (MSSV / CCCD):</label>
                <input type="text" id="recipientId" placeholder="21020001" value="21020001" oninput="onRecipientChange()" />
              </div>
            </div>

            <div class="field">
              <label>4. Dòng chữ chìm chéo giữa trang (Watermark):</label>
              <input type="text" id="diagonalText" placeholder="BẢN SAO BẢO MẬT - Nguyễn Văn An (21020001)" value="BẢN SAO BẢO MẬT - Nguyễn Văn An (21020001)" oninput="onUserDiagonalChange()" />
            </div>

            <div class="grid-2">
              <div class="field">
                <label>5. Con dấu tổ chức (Góc trên phải):</label>
                <input type="text" id="stampText" placeholder="CONFIDENTIAL" value="CONFIDENTIAL" oninput="updateCanvasPreview()" />
              </div>
              <div class="field">
                <label>6. Tiêu đề đầu trang (Header):</label>
                <input type="text" id="headerText" placeholder="Bản cấp phát nội bộ | Cấp cho: Nguyễn Văn An (21020001)" value="Bản cấp phát nội bộ | Cấp cho: Nguyễn Văn An (21020001)" oninput="onUserHeaderChange()" />
              </div>
            </div>

            <div class="grid-2">
              <div class="field">
                <label>Độ mờ chữ chéo (Opacity): <span id="opacityVal">22%</span></label>
                <input type="range" id="diagonalOpacity" min="0.05" max="0.8" step="0.01" value="0.22" oninput="onOpacityChange(this.value)" />
              </div>
              <div class="field">
                <label>Cỡ chữ watermark (Font Size): <span id="fontSizeVal">38pt</span></label>
                <input type="range" id="diagonalFontsize" min="16" max="64" step="1" value="38" oninput="onFontSizeChange(this.value)" />
              </div>
            </div>

            <div style="margin-top: 16px;">
              <button class="btn btn-primary" style="width: 100%; padding: 14px; font-size: 15px;" id="btnDoSingleWatermark" onclick="executeSingleWatermark()">
                ⚡ Đóng Dấu & Xuất Bản PDF (< 1 giây)
              </button>
            </div>
          </div>

          <!-- Cột xem trước Canvas -->
          <div>
            <label style="margin-bottom: 8px;">Trực quan hóa trang in (Live Canvas Preview):</label>
            <div class="preview-box">
              <canvas id="previewCanvas" width="380" height="490"></canvas>
              <div style="font-size: 11px; color: var(--text-muted); margin-top: 10px; text-align: center;">
                Mô phỏng bố cục đóng dấu chuẩn A4 (Header, Footer, Stamp góc phải & Watermark chữ chéo)
              </div>
            </div>
          </div>
        </div>

        <!-- Single Watermark Result -->
        <div id="singleResultAlert" class="alert-box"></div>
      </div>
    </section>

    <!-- TAB 3: ĐÓNG DẤU HÀNG LOẠT & XUẤT TỆP ZIP -->
    <section id="tab-batch" class="tab-content">
      <div class="card">
        <h2 class="card-title">⚡ Đóng Dấu Hàng Loạt & Xuất Tệp ZIP Đa Luồng (Batch Studio)</h2>
        <p class="card-desc">
          Nhập hoặc <b>tải tệp CSV danh sách người nhận</b> (sinh viên, phòng thi, đối tác). Cụm máy chủ EC2 sẽ kích hoạt 
          <b>xử lý song song đa luồng (Multi-threading)</b>, tạo từng bản PDF riêng biệt và nén toàn bộ thành <b>tệp ZIP duy nhất</b> kèm theo file bảng kê kiểm định <code>kiem_dinh_manifest.csv</code>!
        </p>

        <div class="grid-2">
          <!-- Cột Cấu Hình & Danh Sách Người Nhận -->
          <div>
            <div class="field">
              <label>1. Chọn tài liệu gốc từ kho:</label>
              <select id="batchDocSelect" onchange="updateBatchCanvasPreview()"></select>
            </div>

            <!-- CSV Upload Dropzone / Button Bar -->
            <div class="field">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; flex-wrap: wrap; gap: 6px;">
                <label style="margin-bottom: 0;">2. Danh sách người nhận (Họ tên, Mã số):</label>
                <div style="display: flex; gap: 6px; flex-wrap: wrap;">
                  <input type="file" id="batchCsvInput" accept=".csv,.txt,.tsv" style="display:none;" onchange="handleBatchCsvFile(this.files[0])" />
                  <button type="button" class="btn btn-primary btn-sm" onclick="document.getElementById('batchCsvInput').click()">📂 Tải tệp CSV / Excel</button>
                  <button type="button" class="btn btn-outline btn-sm" onclick="downloadSampleCsv()">📥 Tải mẫu CSV</button>
                  <button type="button" class="btn btn-outline btn-sm" onclick="loadSampleRecipients('students')">+ Mẫu 5 SV</button>
                  <button type="button" class="btn btn-outline btn-sm" onclick="loadSampleRecipients('rooms')">+ 10 Phòng Thi</button>
                </div>
              </div>

              <!-- Hộp trạng thái CSV -->
              <div id="csvStatusBadge" style="display: none; padding: 6px 12px; border-radius: 6px; background: #ecfdf5; border: 1px solid #10b981; font-size: 12px; margin-bottom: 6px; color: #065f46;"></div>

              <textarea id="batchRecipientsText" rows="6" oninput="updateBatchCanvasPreview()" placeholder="Nguyễn Văn An, 21020001
Trần Thị Bích, 21020002
Lê Hoàng Cường, 21020003
Phạm Thu Dung, 21020004
Hoàng Minh Đức, 21020005"></textarea>
              <div class="hint">Hỗ trợ kéo-thả tệp CSV vào đây, hoặc nhập dạng: <code>Họ và Tên, Mã_Số</code> (mỗi dòng 1 người)</div>
            </div>

            <!-- Khung tùy chỉnh mẫu watermark (giống studio đơn lẻ) -->
            <div class="card" style="background: #f8fafc; padding: 16px; margin-bottom: 16px; border: 1px solid var(--border);">
              <h4 style="font-size: 13px; margin-bottom: 12px; color: #1e3a8a; font-weight: 700;">Tùy biến mẫu watermark động (Variables: {name}, {id}, {date}, {doc}):</h4>
              
              <div class="field">
                <label>Mẫu chữ chìm chéo giữa trang:</label>
                <input type="text" id="batchDiagTpl" value="BẢN SAO BẢO MẬT - {name} ({id})" oninput="updateBatchCanvasPreview()" />
              </div>

              <div class="grid-2">
                <div class="field">
                  <label>Con dấu bảo mật góc trên:</label>
                  <input type="text" id="batchStamp" value="CONFIDENTIAL" oninput="updateBatchCanvasPreview()" />
                </div>
                <div class="field">
                  <label>Mẫu dòng tiêu đề (Header):</label>
                  <input type="text" id="batchHeaderTpl" value="Bản cấp phát nội bộ | Người nhận: {name} ({id})" oninput="updateBatchCanvasPreview()" />
                </div>
              </div>

              <div class="field">
                <label>Mẫu dòng chân trang (Footer):</label>
                <input type="text" id="batchFooterTpl" value="Bản quyền tài liệu thuộc UET - VNU | Mã kiểm định: {id}" oninput="updateBatchCanvasPreview()" />
              </div>

              <!-- Thanh trượt Độ mờ & Cỡ chữ (Giống hệt studio đơn lẻ) -->
              <div class="grid-2">
                <div class="field">
                  <label>Độ mờ chữ chéo (Opacity): <span id="batchOpacityVal" style="color: var(--primary); font-weight: 700;">22%</span></label>
                  <input type="range" id="batchDiagonalOpacity" min="0.05" max="0.8" step="0.01" value="0.22" oninput="onBatchOpacityChange(this.value)" />
                </div>
                <div class="field">
                  <label>Cỡ chữ watermark (Font Size): <span id="batchFontSizeVal" style="color: var(--primary); font-weight: 700;">38pt</span></label>
                  <input type="range" id="batchDiagonalFontsize" min="16" max="64" step="1" value="38" oninput="onBatchFontSizeChange(this.value)" />
                </div>
              </div>
            </div>

            <div>
              <button class="btn btn-success" style="width: 100%; padding: 14px; font-size: 15px;" id="btnDoBatchWatermark" onclick="executeBatchWatermark()">
                🚀 Bắt Đầu Đóng Dấu Đa Luồng & Nén Tệp ZIP
              </button>
            </div>
          </div>

          <!-- Cột Xem Trước Trực Quan Canvas & Tóm Tắt Lô -->
          <div>
            <label style="margin-bottom: 8px;">Trực quan hóa trang in của người nhận đầu tiên (Live Batch Canvas Preview):</label>
            <div class="preview-box">
              <canvas id="batchPreviewCanvas" width="380" height="490"></canvas>
              <div style="font-size: 11px; color: var(--text-muted); margin-top: 10px; text-align: center;">
                Mô phỏng bản in với người nhận đầu tiên trong lô. Cập nhật tức thì khi chỉnh sửa mẫu, độ mờ hoặc cỡ chữ!
              </div>
            </div>

            <!-- Thẻ tóm tắt thông số lô -->
            <div style="margin-top: 16px; padding: 14px; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; font-size: 13px; line-height: 1.8;">
              <div style="display: flex; justify-content: space-between;">
                <span>👥 Số lượng người nhận trong lô:</span>
                <b id="batchRecipientCount" style="color: var(--primary);">5 người</b>
              </div>
              <div style="display: flex; justify-content: space-between;">
                <span>⚙️ Cơ chế thực thi cụm máy chủ:</span>
                <b style="color: #1e3a8a;">Đa luồng ThreadPoolExecutor</b>
              </div>
              <div style="display: flex; justify-content: space-between;">
                <span>📦 Định dạng kết quả bàn giao:</span>
                <b style="color: #059669;">Tệp ZIP + kiem_dinh_manifest.csv</b>
              </div>
            </div>
          </div>
        </div>

        <!-- Batch Result Panel -->
        <div id="batchResultAlert" class="alert-box"></div>
      </div>
    </section>

    <!-- TAB 4: KIỂM ĐỊNH TOÀN VẸN SHA-256 -->
    <section id="tab-verify" class="tab-content">
      <div class="card">
        <h2 class="card-title">🔍 Tra Cứu & Kiểm Định Tính Toàn Vẹn Tài Liệu (Public SHA-256 Verifier)</h2>
        <p class="card-desc">
          Bất kỳ ai (nhà tuyển dụng, sinh viên, cán bộ coi thi) đều có thể kéo thả tệp PDF vào đây để xác minh tính chính thống.
          Trình duyệt tự động băm mã <b>SHA-256 nội bộ trong 20ms</b> bằng <code>Web Crypto API</code> (không cần tải file lên mạng) và đối soát trực tiếp với cơ sở dữ liệu kiểm toán <b>RDS PostgreSQL</b>!
        </p>

        <!-- Dropzone Verifier -->
        <div class="dropzone" id="verifyDropzone" onclick="document.getElementById('verifyFileInput').click()">
          <div class="dropzone-icon">🔎</div>
          <h3 style="font-size: 16px; margin-bottom: 4px;">Kéo & thả tệp PDF cần kiểm định vào đây</h3>
          <p style="font-size: 12px; color: var(--text-muted);">Mã băm SHA-256 sẽ được tạo ngay trên trình duyệt mà không cần tải file lên máy chủ</p>
          <input type="file" id="verifyFileInput" accept=".pdf" style="display: none;" onchange="handleVerifyFileSelect(this.files[0])" />
        </div>

        <div style="margin-top: 20px; text-align: center; color: var(--text-muted); font-size: 13px;">— HOẶC NHẬP TRỰC TIẾP CHUỖI MÃ BĂM SHA-256 —</div>

        <div style="margin-top: 16px; display: flex; gap: 8px;">
          <input type="text" id="verifyShaInput" placeholder="Dán mã băm 64 ký tự hex SHA-256 tại đây..." style="flex: 1;" />
          <button class="btn btn-primary" onclick="verifyHash(document.getElementById('verifyShaInput').value.trim())">Kiểm Định Ngay</button>
        </div>

        <!-- Verification Result Box -->
        <div id="verifyResultDisplay" class="alert-box"></div>
      </div>
    </section>

    <!-- TAB 5: NHẬT KÝ KIỂM TOÁN RDS -->
    <section id="tab-logs" class="tab-content">
      <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 10px;">
          <div>
            <h2 class="card-title" style="margin-bottom: 4px;">📊 Nhật Ký Kiểm Toán Thời Gian Thực (RDS PostgreSQL)</h2>
            <div style="font-size: 13px; color: var(--text-muted);">Bảng <code>audit_logs</code> lưu vết bất biến mọi giao dịch đóng dấu tài liệu trên hệ thống</div>
          </div>
          <div style="display: flex; gap: 8px;">
            <input type="text" id="logSearchInput" placeholder="Tìm theo tên SV, MSSV, tài liệu..." oninput="filterLogsTable()" style="width: 240px; padding: 6px 10px; font-size: 13px;" />
            <button class="btn btn-outline btn-sm" onclick="loadAuditLogs()">🔄 Cập nhật</button>
          </div>
        </div>

        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Thời Gian (VN)</th>
                <th>Người Nhận (Cấp Cho)</th>
                <th>Mã Số</th>
                <th>Tài Liệu Gốc</th>
                <th>Trang</th>
                <th>Worker EC2</th>
                <th>Thời Gian Xử Lý</th>
                <th>Mã Băm SHA-256</th>
              </tr>
            </thead>
            <tbody id="logsTbody">
              <tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 24px;">Đang nạp nhật ký kiểm toán từ PostgreSQL...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

  </main>

  <script>
    // Tab switching
    function switchTab(tabId) {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      
      const targetBtn = Array.from(document.querySelectorAll('.tab-btn')).find(b => b.getAttribute('onclick').includes(tabId));
      if (targetBtn) targetBtn.classList.add('active');
      
      const targetContent = document.getElementById(tabId);
      if (targetContent) targetContent.classList.add('active');

      if (tabId === 'tab-studio') {
        updateCanvasPreview();
      } else if (tabId === 'tab-batch') {
        updateBatchCanvasPreview();
      } else if (tabId === 'tab-logs') {
        loadAuditLogs();
      }
    }

    // -------------------------------------------------------------
    // TAB 1: KHO TÀI LIỆU GỐC
    // -------------------------------------------------------------
    let currentMasterDocs = [];
    let pendingUploadFile = null;

    async function loadMasterDocuments() {
      const tbody = document.getElementById('masterDocsTbody');
      tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 20px;">Đang tải danh sách tài liệu...</td></tr>';
      try {
        const resp = await fetch('/api/v1/documents');
        const data = await resp.json();
        currentMasterDocs = data.documents || [];

        // Update single & batch select dropdowns
        const singleSel = document.getElementById('singleDocSelect');
        const batchSel = document.getElementById('batchDocSelect');
        singleSel.innerHTML = '';
        batchSel.innerHTML = '';

        if (currentMasterDocs.length === 0) {
          tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 20px; color: var(--text-muted);">Chưa có tài liệu nào trong kho. Hãy tải lên tệp PDF đầu tiên ở trên!</td></tr>';
          return;
        }

        tbody.innerHTML = currentMasterDocs.map(d => {
          let sourceBadge = `<span class="source-pill source-builtin">${d.source}</span>`;
          if (d.source.includes('EFS')) sourceBadge = `<span class="source-pill source-efs">Amazon EFS</span>`;
          else if (d.source.includes('S3')) sourceBadge = `<span class="source-pill source-s3">Amazon S3</span>`;

          return `
            <tr>
              <td><code>${d.doc_code}</code></td>
              <td><b>${d.display_name}</b><div style="font-size: 11px; color: #64748b;">${d.filename}</div></td>
              <td>${d.pages_count > 0 ? d.pages_count + ' trang' : '-'}</td>
              <td>${d.size_formatted}</td>
              <td>${sourceBadge}</td>
              <td>
                <div style="display: flex; gap: 6px;">
                  <button class="btn btn-outline btn-sm" onclick="selectForStudio('${d.doc_code}')">🎨 Đóng dấu lẻ</button>
                  <button class="btn btn-outline btn-sm" onclick="selectForBatch('${d.doc_code}')">⚡ Đóng hàng loạt</button>
                  <button class="btn btn-danger-outline btn-sm" onclick="deleteMasterDoc('${d.doc_code}')">🗑️</button>
                </div>
              </td>
            </tr>
          `;
        }).join('');

        currentMasterDocs.forEach(d => {
          const opt1 = document.createElement('option');
          opt1.value = d.doc_code;
          opt1.textContent = `${d.display_name} (${d.size_formatted})`;
          singleSel.appendChild(opt1);

          const opt2 = document.createElement('option');
          opt2.value = d.doc_code;
          opt2.textContent = `${d.display_name} (${d.size_formatted})`;
          batchSel.appendChild(opt2);
        });

        updateCanvasPreview();
      } catch (err) {
        tbody.innerHTML = `<tr><td colspan="6" style="color: red; text-align: center;">Lỗi tải dữ liệu: ${err.message}</td></tr>`;
      }
    }

    function handleMasterFileSelect(file) {
      if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
        alert('Vui lòng chọn tệp định dạng PDF.');
        return;
      }
      pendingUploadFile = file;
      document.getElementById('selectedFileName').textContent = `${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`;
      document.getElementById('customDocTitle').value = file.name.replace(/\.[^/.]+$/, "");
      document.getElementById('uploadActionArea').style.display = 'block';
    }

    function cancelUpload() {
      pendingUploadFile = null;
      document.getElementById('masterFileInput').value = '';
      document.getElementById('uploadActionArea').style.display = 'none';
    }

    async function submitUploadMasterDoc() {
      if (!pendingUploadFile) return;
      const btn = document.getElementById('btnUploadSubmit');
      const statusBox = document.getElementById('uploadStatusAlert');
      btn.disabled = true;
      btn.textContent = '⏳ Đang lưu trữ lên EFS & S3...';
      statusBox.style.display = 'none';

      const formData = new FormData();
      formData.append('pdf_file', pendingUploadFile);
      const customTitle = document.getElementById('customDocTitle').value.trim();
      if (customTitle) formData.append('custom_title', customTitle);

      try {
        const resp = await fetch('/api/v1/documents/upload', {
          method: 'POST',
          body: formData,
        });
        const res = await resp.json();
        if (resp.ok) {
          statusBox.className = 'alert-box alert-success';
          statusBox.style.display = 'block';
          statusBox.innerHTML = `
            <b>✅ Thành công!</b> Tài liệu <b>${res.display_name}</b> (${res.pages_count} trang) đã được lưu vào kho EFS & S3 với mã <code>${res.doc_code}</code>.<br/>
            Bây giờ bạn có thể đóng dấu liên tục hàng trăm lần mà không cần upload lại file!
          `;
          cancelUpload();
          await loadMasterDocuments();
        } else {
          throw new Error(res.detail || 'Lỗi tải lên máy chủ.');
        }
      } catch (err) {
        statusBox.className = 'alert-box alert-error';
        statusBox.style.display = 'block';
        statusBox.innerHTML = `<b>❌ Lỗi tải lên:</b> ${err.message}`;
      } finally {
        btn.disabled = false;
        btn.textContent = '🚀 Lưu Vào Kho EFS & S3';
      }
    }

    async function deleteMasterDoc(code) {
      if (!confirm(`Bạn có chắc chắn muốn xóa tài liệu gốc '${code}' khỏi kho lưu trữ EFS/S3?`)) return;
      try {
        const resp = await fetch(`/api/v1/documents/${code}`, { method: 'DELETE' });
        const res = await resp.json();
        if (resp.ok) {
          alert('Đã xóa tài liệu thành công.');
          loadMasterDocuments();
        } else {
          alert('Lỗi: ' + (res.detail || 'Không thể xóa.'));
        }
      } catch (err) {
        alert('Lỗi kết nối: ' + err.message);
      }
    }

    function selectForStudio(docCode) {
      document.getElementById('singleDocSelect').value = docCode;
      switchTab('tab-studio');
      updateCanvasPreview();
    }

    function selectForBatch(docCode) {
      document.getElementById('batchDocSelect').value = docCode;
      switchTab('tab-batch');
      updateBatchCanvasPreview();
    }

    // -------------------------------------------------------------
    // TAB 2: LIVE STUDIO & INTERACTIVE CANVAS PREVIEW
    // -------------------------------------------------------------
    let diagonalTextIsCustom = false;
    let headerTextIsCustom = false;

    function onRecipientChange() {
      const rName = document.getElementById('recipientName').value.trim() || 'Nguyễn Văn An';
      const rId = document.getElementById('recipientId').value.trim() || '21020001';

      if (!diagonalTextIsCustom) {
        document.getElementById('diagonalText').value = `BẢN SAO BẢO MẬT - ${rName} (${rId})`;
      }
      if (!headerTextIsCustom) {
        document.getElementById('headerText').value = `Bản cấp phát nội bộ | Cấp cho: ${rName} (${rId})`;
      }
      updateCanvasPreview();
    }

    function onUserDiagonalChange() {
      diagonalTextIsCustom = true;
      updateCanvasPreview();
    }

    function onUserHeaderChange() {
      headerTextIsCustom = true;
      updateCanvasPreview();
    }

    function onStudioDocChange() {
      updateCanvasPreview();
    }

    function onOpacityChange(val) {
      document.getElementById('opacityVal').textContent = Math.round(val * 100) + '%';
      updateCanvasPreview();
    }

    function onFontSizeChange(val) {
      document.getElementById('fontSizeVal').textContent = val + 'pt';
      updateCanvasPreview();
    }

    function updateCanvasPreview() {
      const canvas = document.getElementById('previewCanvas');
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      const w = canvas.width;
      const h = canvas.height;

      // 1. Clear & draw page sheet
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, w, h);

      // Draw mock text lines to simulate document
      ctx.fillStyle = '#e2e8f0';
      for (let y = 80; y < h - 70; y += 18) {
        const lw = (y % 36 === 0) ? w - 90 : (y % 54 === 0) ? w - 160 : w - 80;
        ctx.fillRect(40, y, lw, 8);
      }

      const rName = document.getElementById('recipientName').value.trim() || 'Nguyễn Văn An';
      const rId = document.getElementById('recipientId').value.trim() || '21020001';

      // LẤY TRỰC TIẾP TỪ Ô NHẬP LIỆU -> ĐẢM BẢO 100% TRÙNG KHỚP VỚI MÀN HÌNH!
      const diagUser = document.getElementById('diagonalText').value.trim();
      const diagText = diagUser || `BẢN SAO BẢO MẬT - ${rName} (${rId})`;
      const stampText = document.getElementById('stampText').value.trim() || 'CONFIDENTIAL';
      const headerUser = document.getElementById('headerText').value.trim();
      const headerText = headerUser || `Bản cấp phát nội bộ | Cấp cho: ${rName} (${rId})`;
      const footerText = `Bản quyền UET - VNU | Mã số: ${rId}`;
      const opacity = parseFloat(document.getElementById('diagonalOpacity').value) || 0.22;
      const fSize = parseInt(document.getElementById('diagonalFontsize').value) || 38;

      // 2. Draw Header
      ctx.fillStyle = '#64748b';
      ctx.font = '10px sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(headerText, 30, 28);
      ctx.strokeStyle = '#cbd5e1';
      ctx.lineWidth = 0.8;
      ctx.beginPath();
      ctx.moveTo(30, 36);
      ctx.lineTo(w - 30, 36);
      ctx.stroke();

      // 3. Draw Stamp in top-right
      ctx.save();
      ctx.translate(w - 75, 48);
      ctx.rotate(-0.08);
      ctx.strokeStyle = '#dc2626';
      ctx.lineWidth = 1.5;
      ctx.strokeRect(-40, 0, 80, 22);
      ctx.fillStyle = '#dc2626';
      ctx.font = 'bold 9px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(stampText, 0, 15);
      ctx.restore();

      // 4. Draw Diagonal Watermark (Center)
      ctx.save();
      ctx.translate(w / 2, h / 2);
      ctx.rotate(-45 * Math.PI / 180);
      ctx.globalAlpha = opacity;
      ctx.fillStyle = '#94a3b8';
      ctx.font = `bold ${Math.round(fSize * 0.5)}px sans-serif`;
      ctx.textAlign = 'center';
      ctx.fillText(diagText, 0, 0);
      ctx.restore();

      // 5. Draw Footer
      ctx.globalAlpha = 1.0;
      ctx.strokeStyle = '#cbd5e1';
      ctx.beginPath();
      ctx.moveTo(30, h - 36);
      ctx.lineTo(w - 30, h - 36);
      ctx.stroke();
      ctx.fillStyle = '#64748b';
      ctx.font = '9px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(footerText, w / 2, h - 22);
    }

    async function executeSingleWatermark() {
      const docCode = document.getElementById('singleDocSelect').value;
      if (!docCode) {
        alert('Vui lòng chọn hoặc tải lên một tài liệu gốc trước.');
        return;
      }

      const btn = document.getElementById('btnDoSingleWatermark');
      const resBox = document.getElementById('singleResultAlert');
      btn.disabled = true;
      btn.textContent = '⏳ Đang áp dụng dấu & tính mã băm SHA-256...';
      resBox.style.display = 'none';

      const payload = {
        recipient_name: document.getElementById('recipientName').value.trim(),
        recipient_id: document.getElementById('recipientId').value.trim(),
        diagonal_text: document.getElementById('diagonalText').value.trim() || undefined,
        stamp_text: document.getElementById('stampText').value.trim() || undefined,
        header_text: document.getElementById('headerText').value.trim() || undefined,
        diagonal_opacity: parseFloat(document.getElementById('diagonalOpacity').value) || 0.22,
        diagonal_fontsize: parseInt(document.getElementById('diagonalFontsize').value) || 38,
      };

      try {
        const resp = await fetch(`/api/v1/documents/${docCode}/watermark`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const res = await resp.json();
        if (resp.ok) {
          resBox.className = 'alert-box alert-success';
          resBox.style.display = 'block';
          resBox.innerHTML = `
            <div style="font-size: 16px; font-weight: 700; margin-bottom: 8px;">🎉 Đóng dấu thành công trong ${res.processing_time_ms} ms!</div>
            <div style="font-size: 13px; line-height: 1.8;">
              • <b>Tài liệu:</b> ${res.doc_name} (${res.pages_count} trang)<br/>
              • <b>Máy chủ EC2 xử lý:</b> <code>${res.worker_host}</code><br/>
              • <b>Mã băm SHA-256 kiểm định:</b> <code style="word-break: break-all;">${res.sha256}</code><br/>
              • <b>Thời gian ghi nhận (VN):</b> ${res.created_at_vn}
            </div>
            <div style="margin-top: 14px;">
              <a href="${res.download_url}" target="_blank" class="btn btn-success" style="font-size: 14px; padding: 10px 20px;">
                📥 Tải Ngay File PDF Đã Đóng Dấu
              </a>
            </div>
          `;
        } else {
          throw new Error(res.detail || 'Lỗi đóng dấu.');
        }
      } catch (err) {
        resBox.className = 'alert-box alert-error';
        resBox.style.display = 'block';
        resBox.innerHTML = `<b>❌ Lỗi xử lý:</b> ${err.message}`;
      } finally {
        btn.disabled = false;
        btn.textContent = '⚡ Đóng Dấu & Xuất Bản PDF (< 1 giây)';
      }
    }

    // -------------------------------------------------------------
    // TAB 3: BATCH PROCESSING & ZIP EXPORT
    // -------------------------------------------------------------
    function onBatchOpacityChange(val) {
      document.getElementById('batchOpacityVal').textContent = Math.round(val * 100) + '%';
      updateBatchCanvasPreview();
    }

    function onBatchFontSizeChange(val) {
      document.getElementById('batchFontSizeVal').textContent = val + 'pt';
      updateBatchCanvasPreview();
    }

    function downloadSampleCsv() {
      const csvContent = "\uFEFFHọ và tên,Mã định danh (MSSV/ID)\nNguyễn Văn An,21020001\nTrần Thị Bích,21020002\nLê Hoàng Cường,21020003\nPhạm Thu Dung,21020004\nHoàng Minh Đức,21020005\n";
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.setAttribute('href', url);
      link.setAttribute('download', 'danh_sach_nguoi_nhan_mau.csv');
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }

    function handleBatchCsvFile(file) {
      if (!file) return;
      const reader = new FileReader();
      reader.onload = function(e) {
        const text = e.target.result;
        const lines = text.split(/\r?\n/);
        const parsed = [];
        for (let i = 0; i < lines.length; i++) {
          const line = lines[i].trim();
          if (!line) continue;
          const parts = line.split(/[,;\t]+/).map(p => p.trim().replace(/^["']|["']$/g, ''));
          if (parts.length >= 2) {
            const lower0 = parts[0].toLowerCase();
            const lower1 = parts[1].toLowerCase();
            if (i === 0 && (lower0.includes('tên') || lower0.includes('name') || lower0.includes('stt') || lower1.includes('id') || lower1.includes('mssv') || lower1.includes('mã'))) {
              continue;
            }
            if (parts.length >= 3 && /^\d+$/.test(parts[0])) {
              parsed.push(`${parts[1]}, ${parts[2]}`);
            } else {
              parsed.push(`${parts[0]}, ${parts[1]}`);
            }
          } else if (parts.length === 1 && parts[0]) {
            parsed.push(`${parts[0]}, ID-${String(parsed.length + 1).padStart(3, '0')}`);
          }
        }

        if (parsed.length > 0) {
          document.getElementById('batchRecipientsText').value = parsed.join('\n');
          const badge = document.getElementById('csvStatusBadge');
          badge.style.display = 'block';
          badge.innerHTML = `✅ Đã nạp thành công <b>${parsed.length} người nhận</b> từ tệp <i>${file.name}</i>!`;
          updateBatchCanvasPreview();
        } else {
          alert('Không tìm thấy dữ liệu hợp lệ trong tệp CSV. Vui lòng kiểm tra định dạng.');
        }
      };
      reader.readAsText(file, 'UTF-8');
    }

    function getFirstBatchRecipient() {
      const rawText = document.getElementById('batchRecipientsText').value.trim();
      if (!rawText) return { name: 'Nguyễn Văn An', id: '21020001', count: 0 };
      const lines = rawText.split('\n').map(l => l.trim()).filter(Boolean);
      const count = lines.length;
      if (count === 0) return { name: 'Nguyễn Văn An', id: '21020001', count: 0 };
      const parts = lines[0].split(/[,;\t]+/).map(p => p.trim().replace(/^["']|["']$/g, ''));
      let rName = parts[0] || 'Nguyễn Văn An';
      let rId = parts[1] || '21020001';
      if (parts.length >= 3 && /^\d+$/.test(parts[0])) {
        rName = parts[1];
        rId = parts[2];
      }
      return { name: rName, id: rId, count: count };
    }

    function updateBatchCanvasPreview() {
      const canvas = document.getElementById('batchPreviewCanvas');
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      const w = canvas.width;
      const h = canvas.height;

      // 1. Clear & draw page sheet
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, w, h);

      // Draw mock text lines to simulate document
      ctx.fillStyle = '#e2e8f0';
      for (let y = 80; y < h - 70; y += 18) {
        const lw = (y % 36 === 0) ? w - 90 : (y % 54 === 0) ? w - 160 : w - 80;
        ctx.fillRect(40, y, lw, 8);
      }

      const { name: rName, id: rId, count } = getFirstBatchRecipient();
      const countEl = document.getElementById('batchRecipientCount');
      if (countEl) countEl.textContent = `${count} người nhận`;

      const selDoc = document.getElementById('batchDocSelect');
      const docName = selDoc && selDoc.options[selDoc.selectedIndex] ? selDoc.options[selDoc.selectedIndex].text : 'Tài liệu gốc';
      const todayVN = new Date().toLocaleDateString('vi-VN');

      const diagTpl = document.getElementById('batchDiagTpl').value.trim() || 'BẢN SAO BẢO MẬT - {name} - {id}';
      const headerTpl = document.getElementById('batchHeaderTpl').value.trim() || 'Bản cấp phát nội bộ | Người nhận: {name} ({id})';
      const footerTpl = document.getElementById('batchFooterTpl').value.trim() || 'Bản quyền tài liệu thuộc UET - VNU | Mã kiểm định: {id}';
      const stampText = document.getElementById('batchStamp').value.trim() || 'CONFIDENTIAL';

      const diagText = diagTpl.replace(/{name}/g, rName).replace(/{id}/g, rId).replace(/{date}/g, todayVN).replace(/{doc}/g, docName);
      const headerText = headerTpl.replace(/{name}/g, rName).replace(/{id}/g, rId).replace(/{date}/g, todayVN).replace(/{doc}/g, docName);
      const footerText = footerTpl.replace(/{name}/g, rName).replace(/{id}/g, rId).replace(/{date}/g, todayVN).replace(/{doc}/g, docName);

      const opacity = parseFloat(document.getElementById('batchDiagonalOpacity').value) || 0.22;
      const fSize = parseInt(document.getElementById('batchDiagonalFontsize').value) || 38;

      // 2. Draw Header
      ctx.fillStyle = '#64748b';
      ctx.font = '10px sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(headerText, 30, 28);
      ctx.strokeStyle = '#cbd5e1';
      ctx.lineWidth = 0.8;
      ctx.beginPath();
      ctx.moveTo(30, 36);
      ctx.lineTo(w - 30, 36);
      ctx.stroke();

      // 3. Draw Stamp in top-right
      ctx.save();
      ctx.translate(w - 75, 48);
      ctx.rotate(-0.08);
      ctx.strokeStyle = '#dc2626';
      ctx.lineWidth = 1.5;
      ctx.strokeRect(-40, 0, 80, 22);
      ctx.fillStyle = '#dc2626';
      ctx.font = 'bold 9px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(stampText, 0, 15);
      ctx.restore();

      // 4. Draw Diagonal Watermark (Center)
      ctx.save();
      ctx.translate(w / 2, h / 2);
      ctx.rotate(-45 * Math.PI / 180);
      ctx.globalAlpha = opacity;
      ctx.fillStyle = '#94a3b8';
      ctx.font = `bold ${Math.round(fSize * 0.5)}px sans-serif`;
      ctx.textAlign = 'center';
      ctx.fillText(diagText, 0, 0);
      ctx.restore();

      // 5. Draw Footer
      ctx.globalAlpha = 1.0;
      ctx.strokeStyle = '#cbd5e1';
      ctx.beginPath();
      ctx.moveTo(30, h - 36);
      ctx.lineTo(w - 30, h - 36);
      ctx.stroke();
      ctx.fillStyle = '#64748b';
      ctx.font = '9px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(footerText, w / 2, h - 22);
    }

    function loadSampleRecipients(type) {
      const area = document.getElementById('batchRecipientsText');
      if (type === 'students') {
        area.value = `Nguyễn Văn An, 21020001
Trần Thị Bích, 21020002
Lê Hoàng Cường, 21020003
Phạm Thu Dung, 21020004
Hoàng Minh Đức, 21020005`;
      updateBatchCanvasPreview();
      } else if (type === 'rooms') {
        let lines = [];
        for (let i = 1; i <= 10; i++) {
          lines.push(`Phòng Thi P${100+i}, PT-P${100+i}`);
        }
        area.value = lines.join('\n');
      }
      updateBatchCanvasPreview();
    }

    async function executeBatchWatermark() {
      const docCode = document.getElementById('batchDocSelect').value;
      if (!docCode) {
        alert('Vui lòng chọn một tài liệu gốc trước.');
        return;
      }
      const rawText = document.getElementById('batchRecipientsText').value.trim();
      if (!rawText) {
        alert('Vui lòng nhập danh sách người nhận.');
        return;
      }

      const btn = document.getElementById('btnDoBatchWatermark');
      const resBox = document.getElementById('batchResultAlert');
      btn.disabled = true;
      btn.textContent = '⏳ Đang kích hoạt cụm máy chủ EC2 đa luồng & nén ZIP...';
      resBox.style.display = 'none';

      const payload = {
        recipients_text: rawText,
        diagonal_template: document.getElementById('batchDiagTpl').value.trim(),
        header_template: document.getElementById('batchHeaderTpl').value.trim(),
        footer_template: document.getElementById('batchFooterTpl').value.trim(),
        stamp_text: document.getElementById('batchStamp').value.trim(),
        diagonal_opacity: parseFloat(document.getElementById('batchDiagonalOpacity').value) || 0.22,
        diagonal_fontsize: parseInt(document.getElementById('batchDiagonalFontsize').value) || 38,
      };

      try {
        const resp = await fetch(`/api/v1/documents/${docCode}/batch`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const res = await resp.json();
        if (resp.ok) {
          resBox.className = 'alert-box alert-success';
          resBox.style.display = 'block';

          let rowsHtml = res.items.map(it => `
            <tr>
              <td>${it.index}</td>
              <td><b>${it.recipient}</b></td>
              <td><code>${it.id}</code></td>
              <td title="${it.sha256}"><code>${it.sha256.substring(0, 16)}...</code></td>
              <td>${it.processing_time_ms} ms</td>
              <td><a href="${it.download_url}" target="_blank" style="color: var(--primary); text-decoration: none; font-weight: 600;">Tải file lẻ</a></td>
            </tr>
          `).join('');

          resBox.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 12px;">
              <div>
                <div style="font-size: 18px; font-weight: 700; color: #065f46;">
                  🚀 Hoàn tất đóng dấu ${res.total_items} tài liệu trong ${res.total_time_ms} ms!
                </div>
                <div style="font-size: 13px; color: #1e293b; margin-top: 4px;">
                  Tất cả các bản PDF và file kiểm định <code>kiem_dinh_manifest.csv</code> đã được nén an toàn trong gói ZIP.
                </div>
              </div>
              <a href="${res.zip_download_url}" target="_blank" class="btn btn-success" style="padding: 12px 24px; font-size: 15px; box-shadow: 0 4px 10px rgba(5,150,105,0.3);">
                📥 TẢI XUỐNG GÓI ZIP TOÀN BỘ (${res.total_items} PDFs)
              </a>
            </div>

            <div class="table-wrap" style="max-height: 280px; overflow-y: auto; background: #fff; border-radius: 8px; border: 1px solid var(--border);">
              <table>
                <thead>
                  <tr>
                    <th>STT</th>
                    <th>Người Nhận</th>
                    <th>Mã Số</th>
                    <th>Mã Băm SHA-256</th>
                    <th>Thời Gian</th>
                    <th>Tải Lẻ</th>
                  </tr>
                </thead>
                <tbody>${rowsHtml}</tbody>
              </table>
            </div>
          `;
        } else {
          throw new Error(res.detail || 'Lỗi đóng dấu hàng loạt.');
        }
      } catch (err) {
        resBox.className = 'alert-box alert-error';
        resBox.style.display = 'block';
        resBox.innerHTML = `<b>❌ Lỗi xử lý:</b> ${err.message}`;
      } finally {
        btn.disabled = false;
        btn.textContent = '🚀 Bắt Đầu Đóng Dấu Đa Luồng & Nén Tệp ZIP';
      }
    }

    // -------------------------------------------------------------
    // TAB 4: CLIENT-SIDE SHA-256 VERIFIER
    // -------------------------------------------------------------
    async function handleVerifyFileSelect(file) {
      if (!file) return;
      const resBox = document.getElementById('verifyResultDisplay');
      resBox.className = 'alert-box alert-info';
      resBox.style.display = 'block';
      resBox.innerHTML = `Đang đọc và tính mã băm SHA-256 trên trình duyệt (${(file.size/1024).toFixed(1)} KB)...`;

      const t0 = performance.now();
      const arrayBuffer = await file.arrayBuffer();
      const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
      const elapsed = (performance.now() - t0).toFixed(1);

      document.getElementById('verifyShaInput').value = hashHex;
      verifyHash(hashHex, file.name, elapsed);
    }

    async function verifyHash(hash, clientFileName, hashTimeMs) {
      const resBox = document.getElementById('verifyResultDisplay');
      if (!hash) {
        alert('Vui lòng nhập hoặc kéo thả file để lấy mã băm SHA-256.');
        return;
      }
      resBox.className = 'alert-box alert-info';
      resBox.style.display = 'block';
      resBox.innerHTML = `Đang đối soát mã băm <code>${hash.substring(0, 16)}...</code> với cơ sở dữ liệu kiểm toán RDS PostgreSQL...`;

      try {
        const resp = await fetch(`/api/v1/audit-logs/verify/${hash}`);
        const data = await resp.json();
        if (data.verified) {
          const doc = data.document;
          resBox.className = 'alert-box alert-success';
          resBox.innerHTML = `
            <div style="font-size: 16px; font-weight: 700; color: #065f46; margin-bottom: 8px;">
              ✅ TÀI LIỆU HỢP LỆ & NGUYÊN GỐC (VERIFIED AUTHENTIC)
            </div>
            <div style="font-size: 13px; line-height: 1.9; color: #1e293b;">
              • <b>Người nhận được cấp phát:</b> <b>${doc.full_name || 'Người dùng nội bộ'}</b> (Mã: <code>${doc.student_id || 'ID-001'}</code>)<br/>
              • <b>Tài liệu gốc:</b> <b>${doc.doc_name}</b> (${doc.pages_count || 0} trang)<br/>
              • <b>Thời gian phát hành (Giờ VN):</b> <b>${doc.created_at_vn || doc.created_at}</b><br/>
              • <b>Máy chủ EC2 thực thi cấp phát:</b> <code>${doc.worker_host || doc.worker}</code><br/>
              • <b>Hệ thống định danh (Client ID):</b> <code>${doc.client_id}</code><br/>
              • <b>Mã băm toàn vẹn SHA-256:</b> <code style="word-break: break-all;">${hash}</code>
              ${hashTimeMs ? `<br/><small style="color: #64748b;">(Thời gian tính băm trên Web Crypto API: ${hashTimeMs} ms)</small>` : ''}
            </div>
          `;
        } else {
          resBox.className = 'alert-box alert-error';
          resBox.innerHTML = `
            <div style="font-size: 16px; font-weight: 700; color: #991b1b; margin-bottom: 6px;">
              ❌ CẢNH BÁO: TÀI LIỆU KHÔNG HỢP LỆ HOẶC ĐÃ BỊ CHỈNH SỬA
            </div>
            <div style="font-size: 13px; line-height: 1.6;">
              Mã băm SHA-256 <code>${hash}</code> không tồn tại trong sổ cái kiểm toán RDS PostgreSQL.
              Điều này chứng tỏ tài liệu này chưa từng được cấp phát chính thống, hoặc nội dung bên trong đã bị tẩy xóa, can thiệp trái phép!
            </div>
          `;
        }
      } catch (err) {
        resBox.className = 'alert-box alert-error';
        resBox.innerHTML = `<b>Lỗi kết nối kiểm định:</b> ${err.message}`;
      }
    }

    // -------------------------------------------------------------
    // TAB 5: AUDIT LOGS
    // -------------------------------------------------------------
    let allLogs = [];

    async function loadAuditLogs() {
      const tbody = document.getElementById('logsTbody');
      tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 20px;">Đang tải nhật ký kiểm toán...</td></tr>';
      try {
        const resp = await fetch('/api/v1/audit-logs?limit=50');
        const data = await resp.json();
        allLogs = data.logs || [];
        renderLogsTable(allLogs);
      } catch (err) {
        tbody.innerHTML = `<tr><td colspan="8" style="color: red; text-align: center;">Lỗi tải nhật ký: ${err.message}</td></tr>`;
      }
    }

    function renderLogsTable(logs) {
      const tbody = document.getElementById('logsTbody');
      if (logs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 20px;">Chưa có giao dịch kiểm toán nào.</td></tr>';
        return;
      }
      tbody.innerHTML = logs.map(l => {
        const sha = l.sha256 || l.sha256_hash || '-';
        return `
          <tr>
            <td style="white-space: nowrap;">${l.created_at_vn || l.created_at || '-'}</td>
            <td><b>${l.full_name || l.client_id || 'Khách'}</b></td>
            <td><code>${l.student_id || '-'}</code></td>
            <td title="${l.doc_name}">${l.doc_name}</td>
            <td>${l.pages_count || 0}</td>
            <td><small><code>${l.worker_host || l.worker || 'ec2'}</code></small></td>
            <td>${l.processing_time_ms ? l.processing_time_ms.toFixed(1) + ' ms' : '-'}</td>
            <td title="${sha}"><code>${sha !== '-' ? sha.substring(0, 14) + '...' : '-'}</code></td>
          </tr>
        `;
      }).join('');
    }

    function filterLogsTable() {
      const q = document.getElementById('logSearchInput').value.toLowerCase().trim();
      if (!q) {
        renderLogsTable(allLogs);
        return;
      }
      const filtered = allLogs.filter(l => {
        return (l.full_name && l.full_name.toLowerCase().includes(q)) ||
               (l.student_id && l.student_id.toLowerCase().includes(q)) ||
               (l.doc_name && l.doc_name.toLowerCase().includes(q)) ||
               (l.sha256 && l.sha256.toLowerCase().includes(q));
      });
      renderLogsTable(filtered);
    }

    // Initialize on load
    window.addEventListener('DOMContentLoaded', () => {
      loadMasterDocuments();
      updateCanvasPreview();
      updateBatchCanvasPreview();

      const batchArea = document.getElementById('batchRecipientsText');
      if (batchArea) {
        batchArea.addEventListener('dragover', (e) => { e.preventDefault(); batchArea.style.borderColor = 'var(--primary)'; });
        batchArea.addEventListener('dragleave', (e) => { e.preventDefault(); batchArea.style.borderColor = '#cbd5e1'; });
        batchArea.addEventListener('drop', (e) => {
          e.preventDefault();
          batchArea.style.borderColor = '#cbd5e1';
          if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
            handleBatchCsvFile(e.dataTransfer.files[0]);
          }
        });
      }
    });
  </script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
def developer_portal():
    """Giao diện Web Application hoàn chỉnh cho người dùng và quản trị viên."""
    return HTMLResponse(content=WEB_APP_HTML)



# ==============================================================================
# 8. ĐIỂM KHỞI CHẠY UVICORN
# ==============================================================================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
