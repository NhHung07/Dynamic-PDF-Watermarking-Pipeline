#!/usr/bin/env python3
"""
Công cụ tính mã băm SHA-256 cho tệp tin cục bộ.
Khớp chuẩn 100% với thuật toán băm SHA-256 của dịch vụ PDF Watermarking Microservice.
"""

import os
import sys
import hashlib

ALB_DNS = "http://PDF-Watermark-ALB-1315238985.ap-southeast-1.elb.amazonaws.com"


def calculate_sha256(file_path: str, chunk_size: int = 65536) -> str:
    """
    Tính mã băm SHA-256 theo khối nhị phân (mặc định 64KB).
    Giúp xử lý mượt mà kể cả các file PDF lớn hàng trăm MB mà không tốn RAM.
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def format_size(bytes_num: int) -> str:
    """Chuyển đổi kích thước byte sang định dạng dễ đọc."""
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_num < 1024.0:
            return f"{bytes_num:.2f} {unit}"
        bytes_num /= 1024.0
    return f"{bytes_num:.2f} TB"


def process_file(file_path: str):
    """Tính toán và in chi tiết mã SHA-256 của file."""
    if not os.path.isfile(file_path):
        print(f"❌ [LỖI] Không tìm thấy tệp: '{file_path}'")
        return None

    size_bytes = os.path.getsize(file_path)
    file_hash = calculate_sha256(file_path)

    print("=" * 70)
    print(f"📄 Tên tệp        : {os.path.basename(file_path)}")
    print(f"📁 Đường dẫn      : {os.path.abspath(file_path)}")
    print(f"⚖️  Kích thước     : {format_size(size_bytes)} ({size_bytes:,} bytes)")
    print(f"🔑 Mã SHA-256     : \033[1;32m{file_hash}\033[0m")
    print("-" * 70)
    print("🌐 Link kiểm định nhanh trên AWS ALB:")
    print(f"   {ALB_DNS}/api/v1/audit-logs/verify/{file_hash}")
    print("=" * 70)
    print()

    return file_hash


def main():
    # 1. Nếu người dùng truyền đường dẫn file qua tham số dòng lệnh
    if len(sys.argv) > 1:
        for p in sys.argv[1:]:
            process_file(p.strip().strip("'\""))
        return

    # 2. Nếu chạy trực tiếp không có tham số: hỏi đường dẫn từ bàn phím
    print("=== CÔNG CỤ TÍNH MÃ BĂM SHA-256 CHO TỆP TIN ===")
    user_input = input("👉 Nhập đường dẫn tệp tin (hoặc kéo thả tệp vào đây): ").strip().strip("'\"")

    if user_input:
        process_file(user_input)
    else:
        # Nếu nhấn Enter để trống, tự động quét các file PDF có sẵn trong thư mục
        pdf_files = [f for f in os.listdir(".") if f.lower().endswith(".pdf")]
        if pdf_files:
            print("\n🔍 Không có đường dẫn, tự động tính cho các file PDF trong thư mục hiện tại:\n")
            for f in pdf_files:
                process_file(f)
        else:
            print("⚠️ Không tìm thấy file PDF nào trong thư mục hiện tại.")


if __name__ == "__main__":
    main()
