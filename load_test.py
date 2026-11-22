#!/usr/bin/env python3
"""
Công cụ Bắn tải & Kiểm thử Khả năng Chịu tải (Load Testing & Stress Testing)
dành riêng cho Enterprise PDF Watermarking Microservice trên AWS.

Tính năng:
- In trực tiếp từng Worker Host (IP EC2) xử lý mỗi request lên màn hình theo thời gian thực
- Chuẩn RESTful JSON API: POST /api/v1/watermark
- Đa dạng Client ID mô phỏng kiến trúc Microservice thực tế (CRM, Billing, HRM, Fintech)
- Cảnh báo trực quan khi Auto Scaling kích hoạt máy chủ thứ 3 & thứ 4
- Thống kê chi tiết RPS, độ trễ, và tỷ lệ phân phối tải giữa các máy
"""

import time
import random
import argparse
import threading
from concurrent.futures import ThreadPoolExecutor
import requests

# Cấu hình mặc định
DEFAULT_ALB_HOST = "http://PDF-Watermark-ALB-1315238985.ap-southeast-1.elb.amazonaws.com"
DEFAULT_DURATION = 360   # 6 phút chuẩn kịch bản Demo
DEFAULT_CONCURRENCY = 25 # 25 luồng đồng thời

# Các Client Microservice mô phỏng trong hệ sinh thái
CLIENT_SYSTEMS = [
    ("crm-service", "HỢP ĐỒNG ĐỐI TÁC BẢO MẬT", "Hợp đồng kinh tế | Mã tra cứu: CRM-"),
    ("billing-service", "BẢN SAO KÊ HÓA ĐƠN ĐỎ", "Hóa đơn điện tử | Ký số thuế: INV-"),
    ("hrm-payroll", "BẢNG LƯƠNG & THƯỞNG BẢO MẬT", "Thông tin nhân sự | Mã nhân viên: EMP-"),
    ("fintech-core", "BẢN SAO KÊ TÀI CHÍNH BẢO MẬT", "Giao dịch ngân hàng số | Mã GD: TX-"),
    ("edtech-portal", "CHỨNG NHẬN HOÀN THÀNH BẢO MẬT", "Văn bằng chứng chỉ số | Mã học viên: STU-"),
]

SAMPLE_NAMES = [
    "Trần Nhật Hưng",
    "Nguyễn Nam Khánh",
    "Đỗ Lê Duy",
    "Phạm Minh Tuấn",
    "Phạm Thùy Trang",
    "Lê Hoàng Long",
    "Vũ Thu Hà",
]

# Thống kê toàn cục
stats = {
    "ok": 0,
    "err": 0,
    "hosts": {},
    "latencies": [],
}
stats_lock = threading.Lock()
start_time = 0.0


def send_json_request(session: requests.Session, base_url: str, req_id: int, stream_hosts: bool = True):
    """Gửi yêu cầu theo chuẩn JSON RESTful API (/api/v1/watermark) và in trực tiếp Worker Host."""
    client_id, diag_prefix, header_prefix = random.choice(CLIENT_SYSTEMS)
    person = random.choice(SAMPLE_NAMES)
    unique_code = f"{random.randint(10000, 99999)}"

    payload = {
        "client_id": client_id,
        "source": {
            "doc_code": "ModelOptimization"
        },
        "watermark": {
            "diagonal_text": f"{diag_prefix} - {person.upper()} (#{req_id})",
            "header_text": f"{header_prefix}{unique_code} | Phát hành nội bộ",
            "footer_text": "Tài liệu mật tổ chức - Nghiêm cấm chỉnh sửa và sao chép",
            "stamp_text": "CONFIDENTIAL",
            "diagonal_opacity": 0.22,
        },
        "metadata": {
            "request_seq": req_id,
            "test_run": "aws-load-test-v2",
        }
    }

    t0 = time.perf_counter()
    try:
        url = f"{base_url.rstrip('/')}/api/v1/watermark"
        resp = session.post(url, json=payload, timeout=45)
        latency = (time.perf_counter() - t0) * 1000.0

        if resp.status_code == 200:
            data = resp.json()
            host = data.get("worker_host", "unknown")
            with stats_lock:
                is_new_host = host not in stats["hosts"]
                stats["ok"] += 1
                stats["hosts"][host] = stats["hosts"].get(host, 0) + 1
                stats["latencies"].append(latency)
                total_hosts = len(stats["hosts"])
                current_ok = stats["ok"]

            # In trực tiếp Worker Host lên terminal cho từng request
            if stream_hosts:
                print(f"[#{current_ok:4d}] \033[1;32m200 OK\033[0m | Worker Host: \033[1;33m{host:15s}\033[0m | {latency:5.0f}ms | Client: {client_id}")

            if is_new_host:
                elapsed = int(time.time() - start_time)
                print(
                    f"\n" + "=" * 80 + "\n"
                    f"⚡ \033[1;37;41m [T+{elapsed:3d}s] AUTO-SCALING KÍCH HOẠT: MÁY CHỦ MỚI GIA NHẬP NHẬN TẢI: {host} \033[0m\n"
                    f"   Tổng số máy chủ EC2 đang hoạt động trong cụm: \033[1;32m{total_hosts} máy\033[0m\n"
                    + "=" * 80 + "\n"
                )
        else:
            with stats_lock:
                stats["err"] += 1
            if stream_hosts:
                print(f"[ERR ] \033[1;31mHTTP {resp.status_code}\033[0m | Client: {client_id}")
    except Exception as e:
        with stats_lock:
            stats["err"] += 1
        if stream_hosts:
            print(f"[ERR ] \033[1;31mKết nối thất bại\033[0m ({e.__class__.__name__})")


def send_legacy_request(session: requests.Session, base_url: str, req_id: int, stream_hosts: bool = True):
    """Gửi yêu cầu theo chuẩn Form Upload tương thích ngược (/api/watermark)."""
    client_id, diag_prefix, header_prefix = random.choice(CLIENT_SYSTEMS)
    person = random.choice(SAMPLE_NAMES)
    unique_code = f"{random.randint(10000, 99999)}"

    payload = {
        "client_id": client_id,
        "doc_code": "ModelOptimization",
        "diagonal_text": f"{diag_prefix} - {person.upper()} (#{req_id})",
        "header_text": f"{header_prefix}{unique_code}",
        "footer_text": "Tài liệu chỉ dùng cho mục đích xác minh tài chính",
        "stamp_text": "CONFIDENTIAL",
    }

    t0 = time.perf_counter()
    try:
        url = f"{base_url.rstrip('/')}/api/watermark"
        resp = session.post(url, data=payload, timeout=45)
        latency = (time.perf_counter() - t0) * 1000.0

        if resp.status_code == 200:
            data = resp.json()
            host = data.get("worker_host", "unknown")
            with stats_lock:
                is_new_host = host not in stats["hosts"]
                stats["ok"] += 1
                stats["hosts"][host] = stats["hosts"].get(host, 0) + 1
                stats["latencies"].append(latency)
                total_hosts = len(stats["hosts"])
                current_ok = stats["ok"]

            if stream_hosts:
                print(f"[#{current_ok:4d}] \033[1;32m200 OK\033[0m | Worker Host: \033[1;33m{host:15s}\033[0m | {latency:5.0f}ms | Client: {client_id}")

            if is_new_host:
                elapsed = int(time.time() - start_time)
                print(
                    f"\n" + "=" * 80 + "\n"
                    f"⚡ \033[1;37;41m [T+{elapsed:3d}s] AUTO-SCALING KÍCH HOẠT: MÁY CHỦ MỚI GIA NHẬP NHẬN TẢI: {host} \033[0m\n"
                    f"   Tổng số máy chủ EC2 đang hoạt động trong cụm: \033[1;32m{total_hosts} máy\033[0m\n"
                    + "=" * 80 + "\n"
                )
        else:
            with stats_lock:
                stats["err"] += 1
            if stream_hosts:
                print(f"[ERR ] \033[1;31mHTTP {resp.status_code}\033[0m | Client: {client_id}")
    except Exception as e:
        with stats_lock:
            stats["err"] += 1
        if stream_hosts:
            print(f"[ERR ] \033[1;31mKết nối thất bại\033[0m ({e.__class__.__name__})")


def worker_loop(base_url: str, end_time: float, worker_idx: int, use_json: bool, stream_hosts: bool):
    counter = worker_idx * 100000
    with requests.Session() as session:
        while time.time() < end_time:
            counter += 1
            if use_json:
                send_json_request(session, base_url, counter, stream_hosts)
            else:
                send_legacy_request(session, base_url, counter, stream_hosts)


def main():
    global start_time

    parser = argparse.ArgumentParser(description="Microservice Load Testing Tool for AWS PDF Watermarking")
    parser.add_argument("--url", default=DEFAULT_ALB_HOST, help=f"Địa chỉ ALB URL (Mặc định: {DEFAULT_ALB_HOST})")
    parser.add_argument("--concurrency", "-c", type=int, default=DEFAULT_CONCURRENCY, help=f"Số luồng đồng thời (Mặc định: {DEFAULT_CONCURRENCY})")
    parser.add_argument("--duration", "-d", type=int, default=DEFAULT_DURATION, help=f"Thời gian bắn tải (giây) (Mặc định: {DEFAULT_DURATION}s)")
    parser.add_argument("--mode", choices=["json", "legacy"], default="json", help="Phương thức gọi API: json (/api/v1/watermark) hoặc legacy (/api/watermark)")
    parser.add_argument("--quiet", "-q", action="store_true", help="Chỉ in thống kê tóm tắt, không in từng dòng worker host")

    args = parser.parse_args()
    stream_hosts = not args.quiet

    print("=" * 80)
    print("🚀 BẮT ĐẦU BẮN TẢI ENTERPRISE PDF WATERMARKING MICROSERVICE")
    print(f"🎯 Mục tiêu ALB    : {args.url}")
    print(f"🔌 Chế độ API      : {'RESTful JSON (/api/v1/watermark)' if args.mode == 'json' else 'Form Legacy (/api/watermark)'}")
    print(f"👥 Luồng đồng thời : {args.concurrency} concurrent threads")
    print(f"⏱️  Thời gian chạy  : {args.duration} giây ({args.duration/60:.1f} phút)")
    print("📄 Tài liệu kiểm thử: ModelOptimization.pdf (47 trang)")
    print("📡 In trực tiếp Worker Host của từng request lên màn hình")
    print("=" * 80)
    print()

    # Kiểm tra kết nối ban đầu
    try:
        r_health = requests.get(f"{args.url.rstrip('/')}/health", timeout=5)
        if r_health.status_code == 200:
            h_info = r_health.json()
            print(f"✅ Kết nối ALB thành công! Service: {h_info.get('service')} v{h_info.get('version')} (Host ban đầu: {h_info.get('host')})\n")
        else:
            print(f"⚠️ ALB phản hồi mã HTTP {r_health.status_code}, tiếp tục bắn tải...\n")
    except Exception as e:
        print(f"⚠️ Cảnh báo kiểm tra sức khỏe ban đầu: {e}\n")

    start_time = time.time()
    end_time = start_time + args.duration

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        for i in range(args.concurrency):
            executor.submit(worker_loop, args.url, end_time, i, args.mode == "json", stream_hosts)

        last_ok = 0
        last_t = time.time()

        while time.time() < end_time:
            time.sleep(5)
            now = time.time()
            elapsed = int(now - start_time)
            dt = now - last_t

            with stats_lock:
                ok_cnt = stats["ok"]
                err_cnt = stats["err"]
                hosts_snapshot = dict(stats["hosts"])
                recent_lats = stats["latencies"][-30:] if stats["latencies"] else [0]

            rps = (ok_cnt - last_ok) / max(0.001, dt)
            last_ok = ok_cnt
            last_t = now
            avg_lat = sum(recent_lats) / len(recent_lats) if recent_lats else 0.0

            hosts_detail = " | ".join(f"\033[1;33m{h}\033[0m: {c}" for h, c in sorted(hosts_snapshot.items()))

            print(
                f"\n>>> \033[1;36m[T+{elapsed:3d}s/{args.duration:3d}s]\033[0m "
                f"Tổng OK: \033[1;32m{ok_cnt}\033[0m | Tốc độ: \033[1;36m{rps:.1f} req/s\033[0m | "
                f"Độ trễ TB: {avg_lat:.0f}ms | Số EC2: \033[1;33m{len(hosts_snapshot)}\033[0m\n"
                f"    Phân bổ Worker hiện tại: {hosts_detail}\n"
            )

        print("\n⏳ Đang hoàn tất các kết nối cuối cùng...")

    total_time = max(1, int(time.time() - start_time))
    total_ok = stats["ok"]
    total_err = stats["err"]
    total_req = total_ok + total_err
    avg_total_lat = sum(stats["latencies"]) / len(stats["latencies"]) if stats["latencies"] else 0.0

    print("\n" + "=" * 80)
    print("📊 BÁO CÁO TỔNG HỢP KẾT QUẢ BẮN TẢI (LOAD TEST SUMMARY)")
    print("=" * 75)
    print(f"⏱️  Thời gian thực thi   : {total_time} giây")
    print(f"📨 Tổng số yêu cầu gửi : {total_req:,}")
    print(f"✅ Yêu cầu thành công   : {total_ok:,} ({ (total_ok/max(1, total_req))*100:.1f}%)")
    print(f"❌ Yêu cầu thất bại     : {total_err:,} ({ (total_err/max(1, total_req))*100:.1f}%)")
    print(f"⚡ Tốc độ xử lý TB     : {total_ok / total_time:.2f} requests/giây")
    print(f"📉 Độ trễ trung bình    : {avg_total_lat:.1f} ms")
    print(f"🖥️  Tổng số EC2 Worker   : {len(stats['hosts'])} máy tham gia xử lý")
    print("-" * 80)
    print("Phân bổ tải chi tiết giữa các EC2 Worker:")
    for host, count in sorted(stats["hosts"].items(), key=lambda x: x[1], reverse=True):
        pct = (count / max(1, total_ok)) * 100
        print(f"  • Worker \033[1;33m{host:15s}\033[0m : {count:4d} requests ({pct:5.1f}%)")
    print("=" * 80)


if __name__ == "__main__":
    main()
