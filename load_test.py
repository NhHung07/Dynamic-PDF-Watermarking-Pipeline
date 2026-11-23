#!/usr/bin/env python3
"""
Công cụ Bắn tải & Kiểm thử Khả năng Chịu tải (Load Testing & Stress Testing)
dành riêng cho Nền tảng Ứng dụng Web Đóng dấu & Quản trị Tài liệu Số trên AWS.

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
import json
import os
import datetime
from concurrent.futures import ThreadPoolExecutor
import requests

# Cấu hình mặc định
DEFAULT_ALB_HOST = "http://PDF-Watermark-ALB-281030112.ap-southeast-1.elb.amazonaws.com"
DEFAULT_DURATION = 360   # 6 phút chuẩn kịch bản Demo Kịch bản 2
DEFAULT_CONCURRENCY = 28 # 28 luồng đồng thời đẩy CPU vượt 60% kích hoạt đầy đủ Alarm & Auto Scaling
DEFAULT_DOC = "ModelOptimization" # Tài liệu kiểm thử chuẩn (47 trang)

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
    "host_events": [],
    "timeline": [],
    "cw_timeline": [],
}
stats_lock = threading.Lock()
start_time = 0.0


def send_json_request(session: requests.Session, base_url: str, req_id: int, doc_code: str = DEFAULT_DOC, stream_hosts: bool = True):
    """Gửi yêu cầu theo chuẩn JSON RESTful API (/api/v1/watermark) và in trực tiếp Worker Host."""
    client_id, diag_prefix, header_prefix = random.choice(CLIENT_SYSTEMS)
    person = random.choice(SAMPLE_NAMES)
    unique_code = f"{random.randint(10000, 99999)}"

    payload = {
        "client_id": client_id,
        "source": {
            "doc_code": doc_code
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
        resp = session.post(url, json=payload, timeout=60)
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
                with stats_lock:
                    stats["host_events"].append({
                        "elapsed_s": elapsed,
                        "host": host,
                        "total_hosts": total_hosts,
                        "is_scale_out": total_hosts > 2
                    })
                if total_hosts > 2:
                    print(
                        f"\n" + "=" * 80 + "\n"
                        f"⚡ \033[1;37;41m [T+{elapsed:3d}s] AUTO-SCALING KÍCH HOẠT: MÁY CHỦ MỚI GIA NHẬP NHẬN TẢI: {host} \033[0m\n"
                        f"   Tổng số máy chủ EC2 đang hoạt động trong cụm: \033[1;32m{total_hosts} máy\033[0m\n"
                        + "=" * 80 + "\n"
                    )
                elif stream_hosts:
                    print(f"ℹ️ Máy chủ ban đầu nhận tải: \033[1;33m{host}\033[0m (Cụm hiện có: {total_hosts} máy)")
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


def send_legacy_request(session: requests.Session, base_url: str, req_id: int, doc_code: str = DEFAULT_DOC, stream_hosts: bool = True):
    """Gửi yêu cầu theo chuẩn Form Upload tương thích ngược (/api/watermark)."""
    client_id, diag_prefix, header_prefix = random.choice(CLIENT_SYSTEMS)
    person = random.choice(SAMPLE_NAMES)
    unique_code = f"{random.randint(10000, 99999)}"

    payload = {
        "client_id": client_id,
        "doc_code": doc_code,
        "diagonal_text": f"{diag_prefix} - {person.upper()} (#{req_id})",
        "header_text": f"{header_prefix}{unique_code}",
        "footer_text": "Tài liệu chỉ dùng cho mục đích xác minh tài chính",
        "stamp_text": "CONFIDENTIAL",
    }

    t0 = time.perf_counter()
    try:
        url = f"{base_url.rstrip('/')}/api/watermark"
        resp = session.post(url, data=payload, timeout=60)
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
                with stats_lock:
                    stats["host_events"].append({
                        "elapsed_s": elapsed,
                        "host": host,
                        "total_hosts": total_hosts,
                        "is_scale_out": total_hosts > 2
                    })
                if total_hosts > 2:
                    print(
                        f"\n" + "=" * 80 + "\n"
                        f"⚡ \033[1;37;41m [T+{elapsed:3d}s] AUTO-SCALING KÍCH HOẠT: MÁY CHỦ MỚI GIA NHẬP NHẬN TẢI: {host} \033[0m\n"
                        f"   Tổng số máy chủ EC2 đang hoạt động trong cụm: \033[1;32m{total_hosts} máy\033[0m\n"
                        + "=" * 80 + "\n"
                    )
                elif stream_hosts:
                    print(f"ℹ️ Máy chủ ban đầu nhận tải: \033[1;33m{host}\033[0m (Cụm hiện có: {total_hosts} máy)")
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


def worker_loop(base_url: str, end_time: float, worker_idx: int, use_json: bool, doc_code: str, stream_hosts: bool):
    counter = worker_idx * 100000
    with requests.Session() as session:
        while time.time() < end_time:
            counter += 1
            if use_json:
                send_json_request(session, base_url, counter, doc_code, stream_hosts)
            else:
                send_legacy_request(session, base_url, counter, doc_code, stream_hosts)


def cw_monitor_loop(end_time: float, start_t: float):
    """Giám sát số lượng máy chủ ASG và CPUUtilization từ CloudWatch định kỳ."""
    try:
        import manage_aws
        session = manage_aws.get_session()
        cw = session.client('cloudwatch', region_name=manage_aws.REGION)
        asg = session.client('autoscaling', region_name=manage_aws.REGION)
    except Exception:
        return

    while time.time() < end_time:
        try:
            now = datetime.datetime.now(datetime.timezone.utc)
            res_asg = asg.describe_auto_scaling_groups(AutoScalingGroupNames=[manage_aws.ASG_NAME])
            asg_group = res_asg['AutoScalingGroups'][0] if res_asg.get('AutoScalingGroups') else None
            inst_count = len(asg_group['Instances']) if asg_group else 0
            inservice_count = sum(1 for i in asg_group['Instances'] if i.get('LifecycleState') == 'InService') if asg_group else 0

            res_cw = cw.get_metric_statistics(
                Namespace='AWS/EC2',
                MetricName='CPUUtilization',
                Dimensions=[{'Name': 'AutoScalingGroupName', 'Value': manage_aws.ASG_NAME}],
                StartTime=now - datetime.timedelta(minutes=3),
                EndTime=now,
                Period=60,
                Statistics=['Average']
            )
            dps = sorted(res_cw.get('Datapoints', []), key=lambda x: x['Timestamp'])
            latest_cpu = dps[-1]['Average'] if dps else None

            elapsed = int(time.time() - start_t)
            with stats_lock:
                stats["cw_timeline"].append({
                    "elapsed_s": elapsed,
                    "asg_instances": inst_count,
                    "inservice_instances": inservice_count,
                    "cpu_utilization": round(latest_cpu, 2) if latest_cpu is not None else None
                })
            if latest_cpu is not None and (latest_cpu > 40 or inst_count > 2):
                print(f"\n\033[1;35m📊 [CloudWatch T+{elapsed:3d}s] CPU TB Cụm: {latest_cpu:.1f}% | Cụm ASG: {inservice_count}/{inst_count} InService\033[0m\n")
        except Exception:
            pass
        time.sleep(10)


def main():
    global start_time

    parser = argparse.ArgumentParser(description="Web Application Load Testing Tool for AWS PDF Watermarking")
    parser.add_argument("--url", default=DEFAULT_ALB_HOST, help=f"Địa chỉ ALB URL (Mặc định: {DEFAULT_ALB_HOST})")
    parser.add_argument("--concurrency", "-c", type=int, default=DEFAULT_CONCURRENCY, help=f"Số luồng đồng thời (Mặc định: {DEFAULT_CONCURRENCY})")
    parser.add_argument("--duration", "-d", type=int, default=DEFAULT_DURATION, help=f"Thời gian bắn tải (giây) (Mặc định: {DEFAULT_DURATION}s)")
    parser.add_argument("--doc", default=DEFAULT_DOC, help=f"Mã tài liệu kiểm thử (Mặc định: {DEFAULT_DOC})")
    parser.add_argument("--mode", choices=["json", "legacy"], default="json", help="Phương thức gọi API: json (/api/v1/watermark) hoặc legacy (/api/watermark)")
    parser.add_argument("--quiet", "-q", action="store_true", help="Chỉ in thống kê tóm tắt, không in từng dòng worker host")
    parser.add_argument("--output", "-o", default="report/load_test_results.json", help="Đường dẫn lưu kết quả JSON (Mặc định: report/load_test_results.json)")

    args = parser.parse_args()
    stream_hosts = not args.quiet

    print("=" * 80)
    print("🚀 BẮT ĐẦU BẮN TẢI KỊCH BẢN 2: WEB ĐÓNG DẤU TÀI LIỆU SỐ TRỰC TUYẾN (28 LUỒNG / 6 PHÚT)")
    print(f"🎯 Mục tiêu ALB    : {args.url}")
    print(f"🔌 Chế độ API      : {'RESTful JSON (/api/v1/watermark)' if args.mode == 'json' else 'Form Legacy (/api/watermark)'}")
    print(f"👥 Luồng đồng thời : {args.concurrency} concurrent threads")
    print(f"⏱️  Thời gian chạy  : {args.duration} giây ({args.duration/60:.1f} phút)")
    print(f"📄 Tài liệu kiểm thử: {args.doc}.pdf")
    print(f"💾 Tệp xuất kết quả: {args.output}")
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

    # Khởi chạy luồng giám sát CloudWatch trong nền
    monitor_thread = threading.Thread(target=cw_monitor_loop, args=(end_time, start_time), daemon=True)
    monitor_thread.start()

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        for i in range(args.concurrency):
            executor.submit(worker_loop, args.url, end_time, i, args.mode == "json", args.doc, stream_hosts)

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

            sorted_rec = sorted(recent_lats)
            p50_rec = sorted_rec[int(len(sorted_rec) * 0.50)] if sorted_rec else 0.0

            with stats_lock:
                stats["timeline"].append({
                    "elapsed_s": elapsed,
                    "ok_count": ok_cnt,
                    "err_count": err_cnt,
                    "rps": round(rps, 2),
                    "avg_latency_ms": round(avg_lat, 1),
                    "p50_latency_ms": round(p50_rec, 1),
                    "active_hosts": len(hosts_snapshot),
                    "hosts": hosts_snapshot
                })

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

    sorted_lats = sorted(stats["latencies"])
    p50 = sorted_lats[int(len(sorted_lats) * 0.50)] if sorted_lats else 0.0
    p90 = sorted_lats[int(len(sorted_lats) * 0.90)] if sorted_lats else 0.0
    p95 = sorted_lats[int(len(sorted_lats) * 0.95)] if sorted_lats else 0.0
    p99 = sorted_lats[int(len(sorted_lats) * 0.99)] if sorted_lats else 0.0
    min_lat = sorted_lats[0] if sorted_lats else 0.0
    max_lat = sorted_lats[-1] if sorted_lats else 0.0
    peak_rps = max([t["rps"] for t in stats["timeline"]]) if stats["timeline"] else 0.0
    avg_rps = total_ok / total_time

    print("\n" + "=" * 80)
    print("📊 BÁO CÁO TỔNG HỢP KẾT QUẢ BẮN TẢI (LOAD TEST SUMMARY)")
    print("=" * 75)
    print(f"⏱️  Thời gian thực thi   : {total_time} giây")
    print(f"📨 Tổng số yêu cầu gửi : {total_req:,}")
    print(f"✅ Yêu cầu thành công   : {total_ok:,} ({ (total_ok/max(1, total_req))*100:.1f}%)")
    print(f"❌ Yêu cầu thất bại     : {total_err:,} ({ (total_err/max(1, total_req))*100:.1f}%)")
    print(f"⚡ Tốc độ xử lý TB     : {avg_rps:.2f} requests/giây")
    print(f"🚀 Thông lượng đỉnh     : {peak_rps:.2f} requests/giây")
    print(f"📉 Độ trễ trung bình    : {avg_total_lat:.1f} ms")
    print(f"📊 Phân vị p50 (Median) : {p50:.1f} ms")
    print(f"📊 Phân vị p90          : {p90:.1f} ms")
    print(f"📊 Phân vị p95          : {p95:.1f} ms")
    print(f"📊 Phân vị p99          : {p99:.1f} ms")
    print(f"🖥️  Tổng số EC2 Worker   : {len(stats['hosts'])} máy tham gia xử lý")
    print("-" * 80)
    print("Phân bổ tải chi tiết giữa các EC2 Worker:")
    for host, count in sorted(stats["hosts"].items(), key=lambda x: x[1], reverse=True):
        pct = (count / max(1, total_ok)) * 100
        print(f"  • Worker \033[1;33m{host:15s}\033[0m : {count:4d} requests ({pct:5.1f}%)")
    print("=" * 80)

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        worker_dist = {}
        for host, count in sorted(stats["hosts"].items(), key=lambda x: x[1], reverse=True):
            worker_dist[host] = {
                "requests": count,
                "percentage": round((count / max(1, total_ok)) * 100, 2)
            }

        result_data = {
            "timestamp": datetime.datetime.now().isoformat(),
            "config": {
                "url": args.url,
                "concurrency": args.concurrency,
                "duration": args.duration,
                "mode": args.mode,
            },
            "summary": {
                "total_time_seconds": total_time,
                "total_requests": total_req,
                "successful_requests": total_ok,
                "failed_requests": total_err,
                "success_rate_pct": round((total_ok / max(1, total_req)) * 100, 2),
                "avg_rps": round(avg_rps, 2),
                "peak_rps": round(peak_rps, 2),
                "latency_ms": {
                    "mean": round(avg_total_lat, 1),
                    "median_p50": round(p50, 1),
                    "p90": round(p90, 1),
                    "p95": round(p95, 1),
                    "p99": round(p99, 1),
                    "min": round(min_lat, 1),
                    "max": round(max_lat, 1)
                },
                "total_workers": len(stats["hosts"]),
                "worker_distribution": worker_dist,
            },
            "host_events": stats["host_events"],
            "timeline": stats["timeline"],
            "cw_timeline": stats["cw_timeline"],
        }

        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Dữ liệu thực nghiệm đã được lưu vào: \033[1;32m{args.output}\033[0m\n")


if __name__ == "__main__":
    main()
