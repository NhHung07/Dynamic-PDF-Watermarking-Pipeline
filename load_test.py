import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor
import requests

ALB_URL = "http://PDF-Watermark-ALB-1315238985.ap-southeast-1.elb.amazonaws.com/api/watermark"
DURATION_SECONDS = 360  # 6 phút: 3 phút đánh giá CPU + 90s khởi tạo EC2 thứ 3 + 90s chia tải
CONCURRENCY = 28        # 20 luồng với file 47 trang giữ CPU ~80-90%, không làm nghẽn /health

SAMPLE_NAMES = [
    "Trần Nhật Hưng",
    "Nguyễn Nam Khánh",
    "Đỗ Lê Duy",
    "Phạm Minh Tuấn",
    "Phạm Thùy Trang",
]

stats = {"ok": 0, "err": 0, "hosts": {}}
stats_lock = threading.Lock()
start_time = 0.0


def send_request(session: requests.Session, req_id: int):
    student_id = f"2402{random.randint(1000, 9999)}"
    full_name = f"{random.choice(SAMPLE_NAMES)} ({req_id})"
    payload = {
        "student_id": student_id,
        "full_name": full_name,
        "doc_code": "ModelOptimization",
    }
    try:
        resp = session.post(ALB_URL, data=payload, timeout=45)
        if resp.status_code == 200:
            data = resp.json()
            host = data.get("worker_host", "unknown")
            with stats_lock:
                is_new_host = host not in stats["hosts"]
                stats["ok"] += 1
                stats["hosts"][host] = stats["hosts"].get(host, 0) + 1
                total_hosts = len(stats["hosts"])
            if is_new_host:
                elapsed = int(time.time() - start_time)
                print(
                    f"\n>>> [{elapsed:3d}s] PHÁT HIỆN EC2 WORKER MỚI NHẬN TẢI: {host} "
                    f"(Tổng số máy đang chạy: {total_hosts}) <<<\n"
                )
        else:
            with stats_lock:
                stats["err"] += 1
    except Exception:
        with stats_lock:
            stats["err"] += 1


def worker_loop(end_time: float, worker_idx: int):
    counter = worker_idx * 10000
    with requests.Session() as session:
        while time.time() < end_time:
            counter += 1
            send_request(session, counter)


if __name__ == "__main__":
    print(f"Bắt đầu bắn tải đồng thời ({CONCURRENCY} threads) trong {DURATION_SECONDS}s tới ALB...")
    print(f"Target URL: {ALB_URL}")
    print("Tài liệu mẫu: ModelOptimization.pdf (47 trang)\n")

    start_time = time.time()
    end_time = start_time + DURATION_SECONDS

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        for i in range(CONCURRENCY):
            executor.submit(worker_loop, end_time, i)

        while time.time() < end_time:
            elapsed = int(time.time() - start_time)
            with stats_lock:
                ok_cnt = stats["ok"]
                err_cnt = stats["err"]
                hosts_snapshot = dict(stats["hosts"])
            print(
                f"[{elapsed:3d}s/{DURATION_SECONDS}s] Thành công: {ok_cnt:4d} | "
                f"Lỗi: {err_cnt:2d} | Số EC2: {len(hosts_snapshot)} | Phân phối: {hosts_snapshot}"
            )
            time.sleep(5)

        print("\nĐang chờ các request cuối cùng hoàn tất...")

    total_time = int(time.time() - start_time)
    print("\n=== KẾT QUẢ TỔNG HỢP ===")
    print(f"Thời gian chạy thực tế : {total_time}s")
    print(f"Tổng request thành công: {stats['ok']} | Lỗi: {stats['err']}")
    print(f"Tổng số máy EC2 tham gia: {len(stats['hosts'])}")
    print("Phân tải theo từng máy chủ EC2:", stats["hosts"])
