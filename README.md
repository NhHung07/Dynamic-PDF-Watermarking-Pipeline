# Enterprise PDF Watermarking & Integrity Verification Microservice Pipeline on AWS Cloud 🚀

> **Học phần:** Điện toán đám mây (INT 3319 3)  
> **Khoa Công nghệ Thông tin – Trường Đại học Công nghệ, Đại học Quốc gia Hà Nội (UET - VNU)**  
> **Live ALB Endpoint:** `http://PDF-Watermark-ALB-1315238985.ap-southeast-1.elb.amazonaws.com`

---

## 👥 1. Thông tin nhóm thực hiện

| STT | Họ và tên | Mã sinh viên | Vai trò | Mảng phụ trách chính |
|:---:|---|:---:|:---:|---|
| **1** | **Trần Nhật Hưng** | **24021507** | Nhóm trưởng | **Tính toán & Mở rộng:** Cấu hình EC2, Cân bằng tải (ALB), Tự động mở rộng (ASG), Giám sát (CloudWatch, SNS), Tối ưu hoá góc hình học Watermark & Fast Auto-Scaling. |
| **2** | **Nguyễn Nam Khánh** | **24021531** | Thành viên | **Hạ tầng & Lưu trữ:** Thiết kế VPC Multi-AZ, Phân quyền & Bảo mật (Security Group, IAM Role), Lưu trữ đối tượng (S3) & Bộ nhớ đệm tệp dùng chung (EFS). |
| **3** | **Đỗ Lê Duy** | **24021445** | Thành viên | **Ứng dụng & Dữ liệu:** Cơ sở dữ liệu kiểm toán (RDS PostgreSQL), Phát triển Microservice REST API (FastAPI + PyMuPDF) & Kịch bản kiểm thử tải đa luồng (Load Testing). |

---

## 🎯 2. Bài toán thực tiễn & Lý do lựa chọn Cloud

### 2.1. Đối tượng sử dụng (Target Users & Microservices)
Hệ thống được thiết kế theo mô hình **Microservice dùng chung (Shared Infrastructure Service)**, phục vụ các hệ thống nghiệp vụ quy mô doanh nghiệp:
* **Khối Tài chính - Ngân hàng - Fintech (Core Banking, Billing System):** Tự động đóng dấu xuất sao kê giao dịch, phiếu thu, hóa đơn điện tử đỏ có gắn mã khách hàng và watermark bảo mật.
* **Khối Doanh nghiệp & SaaS (CRM, ERP, HRM):** Hệ thống nhân sự (HRM) xuất bảng lương & thưởng bảo mật (Payslip); CRM xuất báo giá đối tác, hợp đồng kinh tế nội bộ.
* **Khối Giáo dục & Đào tạo trực tuyến (EdTech, LMS):** Phát hành giáo trình số bản quyền, chứng chỉ số cá nhân hóa cho học viên để ngăn chặn phát tán lậu lên Internet.
* **Khối Y tế & Bảo hiểm (Hospital Information System - HIS, InsurTech):** Xuất kết quả xét nghiệm bệnh lý, hồ sơ bệnh án, chứng từ bồi thường bảo hiểm bảo mật thông tin nhạy cảm.
* **Bên thứ ba thẩm định (Ngân hàng, Tòa án, Cơ quan quản lý):** Tra cứu mã băm SHA-256 để xác thực tính nguyên bản và nguồn gốc cấp phát của văn bản.

### 2.2. Mục đích sử dụng (Business Objectives)
1. **Cá nhân hóa và xác lập bản quyền động (Dynamic Watermarking):** Chèn tự động thông tin người nhận, thời gian cấp phát, dòng tiêu đề và con dấu pháp nhân lên toàn bộ các trang PDF theo thời gian thực.
2. **Ngăn chặn rò rỉ dữ liệu mật (Deterrence & Leak Prevention):** Watermark in chéo giữa trang hiển thị danh tính người tải là rào cản tâm lý trực quan mạnh mẽ chống chụp ảnh hoặc chia sẻ trái phép.
3. **Bảo vệ tính toàn vẹn và chống làm giả (Integrity & Anti-Tampering):** Tính toán mã băm mật mã học **SHA-256** lưu vào cơ sở dữ liệu kiểm toán. Bất kỳ ai can thiệp sửa đổi dù chỉ 1 chữ số hay 1 dấu chấm đều bị phát hiện ngay lập tức.
4. **Chống chối bỏ và truy vết nguồn gốc (Non-Repudiation & Traceability):** Cung cấp bằng chứng số bất biến: Tài liệu do hệ thống nào gọi (`client_id`), xuất vào giây nào (`created_at_vn`), chạy trên máy chủ nào (`worker_host`).
5. **Chuẩn hóa kiến trúc độc lập (Decoupled Shared Microservice):** Tách toàn bộ tác vụ xử lý PDF nặng nề ra khỏi các hệ thống nghiệp vụ cốt lõi, tích hợp đơn giản qua RESTful JSON API (`POST /api/v1/watermark`).

### 2.3. Vì sao bắt buộc phải sử dụng Điện toán đám mây & Auto-Scaling?
* **Tác vụ xử lý PDF ngốn CPU và RAM (Compute-Intensive):** Khác với web CRUD thông thường chỉ chờ database, đóng dấu PDF đòi hỏi giải mã nhị phân, tính ma trận hình học xoay chữ, render vector Unicode, nén lại tài liệu và băm SHA-256. Xử lý 1 file 47 trang chiếm gần 100% của 1 vCPU trong 0.5 – 1.0 giây.
* **Lưu lượng đột biến theo chu kỳ (Spike Load / Flash Crowds):** Đúng 11h30 ngày 25 hàng tháng khi HRM bắn thông báo trả lương cho 5.000 nhân viên, hoặc khi ngân hàng chốt sao kê, hàng nghìn request đổ về cùng lúc. Máy chủ vật lý đơn lẻ sẽ bị nghẽn hàng đợi và sập nguồn (Out-Of-Memory Crash).
* **Đàn hồi & Tối ưu chi phí (Elasticity & Pay-as-you-go):** Bình thường chỉ chạy 2 máy chủ nhỏ để trực; khi cao điểm tự động nở ra 4 – 6 máy trong 15 phút rồi tự động tắt đi, **tiết kiệm hơn 80% chi phí hạ tầng** so với thuê server cấu hình lớn 24/7.
* **Độ sẵn sàng cao (High Availability):** Cụm EC2 chạy trên nhiều vùng sẵn sàng (Multi-AZ). Nếu 1 máy chủ gặp sự cố, ALB tự động chuyển luồng sang máy khỏe và ASG tự sinh máy thay thế trong 60s mà không gián đoạn dịch vụ.

---

## 🏛 3. Sơ đồ kiến trúc & Luồng dữ liệu trên AWS

### 3.1. Sơ đồ kiến trúc mạng (Region: ap-southeast-1, VPC CIDR: 10.0.0.0/16)

```mermaid
flowchart TD
    subgraph Internet ["Môi trường Internet / Khách hàng"]
        Clients["Clients / Hệ thống nghiệp vụ\n(CRM, ERP, Billing, Web UI, Load Test)"]
    end

    subgraph VPC ["Amazon Virtual Private Cloud (10.0.0.0/16)"]
        subgraph PublicSubnets ["Public Subnets (ap-southeast-1a & 1b)"]
            ALB["Application Load Balancer (ALB)\n(Port 80 -> Health Check /health)"]
            NAT["NAT Gateway\n(Internet 1 chiều cho Private Subnets)"]
        end

        subgraph PrivateSubnets ["Private Subnets (10.0.11.0/24 & 10.0.12.0/24)"]
            ASG["Auto Scaling Group (EC2 Workers)\n(FastAPI + PyMuPDF | Port 8000)\n- Min: 2, Max: 4, Desired: 2"]
            EFS["Amazon EFS (NFSv4)\n(Shared Input Cache & Font Unicode)"]
            RDS[("Amazon RDS (PostgreSQL 16)\n(Bảng audit_logs & Lịch sử cấp phát)")]
        end
    end

    subgraph AWSStorage ["Lưu trữ & Giám sát AWS"]
        S3[("Amazon S3 (uet-pdf-watermark)\n- code/: Mã nguồn main.py\n- input/: PDF mẫu\n- output/: PDF hoàn thiện")]
        CW["Amazon CloudWatch & SNS\n(Alarm CPU >= 50% 1-min -> Fast Scale Out)"]
    end

    Clients -->|1. POST /api/v1/watermark| ALB
    ALB -->|2. Cân bằng tải HTTP| ASG
    ASG -->|3. Đọc cache PDF mẫu & Font| EFS
    ASG -->|4. Lưu file hoàn thiện & Sinh Pre-signed URL| S3
    ASG -->|5. Ghi vết kiểm toán (SHA-256, Worker Host, Time VN)| RDS
    ASG -->|6. Trả URL có Content-Disposition UTF-8| ALB
    ALB -->|7. Phản hồi JSON kết quả| Clients
    Clients -->|8. Tải trực tiếp tốc độ cao| S3
    ASG -.->|Gửi chỉ số CPU| CW
    CW -.->|Kích hoạt Scale Out thêm EC2| ASG
```

### 3.2. Phân vai lưu trữ: EFS vs S3
* **Amazon EFS (`/mnt/efs`):** Đóng vai trò **Bộ nhớ đệm dùng chung (Shared Input Cache)**. Lưu trữ tài liệu mẫu và font Unicode chuẩn tiếng Việt. Khi 1 máy kéo file mẫu từ S3 về EFS, toàn bộ các máy khác trong cụm đều truy cập được ngay lập tức ở tốc độ mạng nội bộ ($< 5\text{ms}$), loại bỏ hoàn toàn việc nghẽn băng thông S3 (Rate Limiting).
* **Amazon S3 (`uet-pdf-watermark`):** Đóng vai trò **Lưu trữ vĩnh viễn (Output Storage)** với độ bền $99.999999999\%$. Hệ thống cấp phát **S3 Pre-signed URL** kèm mã hóa RFC 5987 để người dùng tải trực tiếp từ CDN S3 mà không chiếm dụng băng thông của EC2 Worker.

---

## 🌟 4. Các tính năng kỹ thuật nổi bật

1. **Thuật toán hình học Watermark tự thích ứng (Dynamic Geometric Watermarking):**
   * Tính toán tâm chính xác của trang giấy $(cx, cy) = (w/2, h/2)$.
   * Góc nghiêng động: $\theta = \arctan(h/w) \times 0.82$ ($45^\circ$ cho khổ dọc A4, $32^\circ$ cho khổ ngang Landscape).
   * Tự động co giãn cỡ chữ (Adaptive Font Sizing từ 13pt đến 38pt) đảm bảo chuỗi ký tự dù ngắn hay dài đều hiển thị trọn vẹn ở chính giữa trang, không bao giờ bị cắt cụt hay tràn mép giấy.
2. **Bảo toàn tên tệp UTF-8 tiếng Việt khi tải về:**
   * Sử dụng tiêu chuẩn **RFC 5987 / RFC 6266**: `Content-Disposition: attachment; filename="doc.pdf"; filename*=UTF-8''...`
   * Người dùng tải về tệp có dấu đầy đủ: `UET1002 4.Trần Nhật Hưng.24021507_watermarked.pdf`.
3. **Múi giờ Việt Nam (GMT+7 / Asia/Ho_Chi_Minh):**
   * Mọi mốc thời gian lưu trữ và hiển thị đều được chuẩn hóa chính xác sang giờ Việt Nam (`YYYY-MM-DD HH:mm:ss`).
4. **Cơ chế Fast Auto-Scaling (1-Minute Alarm):**
   * CloudWatch Alarm `Fast-HighCPU-ScaleOut-Alarm` đánh giá chu kỳ 60 giây CPU $\ge 50\%$ kích hoạt mở rộng máy chủ ngay lập tức.
5. **Cổng kiểm định toàn vẹn trực tuyến (Document Integrity Verification):**
   * Nhập mã băm SHA-256 trên Web Portal hoặc gọi API `/api/v1/audit-logs/verify/{sha256}` để kiểm tra tính nguyên bản của tài liệu.

---

## 🔌 5. Đặc tả RESTful API

### 5.1. Đóng dấu tài liệu JSON (`POST /api/v1/watermark`)
Dành cho các Microservice (CRM, Billing, HRM) tích hợp tự động:

**Request Body:**
```json
{
  "client_id": "crm-service",
  "source": {
    "doc_code": "ModelOptimization"
  },
  "watermark": {
    "diagonal_text": "BẢN SAO KÊ BẢO MẬT - TRẦN NHẬT HƯNG",
    "header_text": "Phát hành nội bộ | Mã truy xuất: ACC-98234",
    "footer_text": "Tài liệu chỉ dùng cho mục đích xác minh tài chính",
    "stamp_text": "CONFIDENTIAL",
    "diagonal_opacity": 0.22,
    "diagonal_fontsize": 38
  },
  "metadata": {
    "transaction_id": "TX-998823"
  }
}
```

**Response (200 OK):**
```json
{
  "request_id": "4ff982da-e4c9-4903-8286-cca11d75b581",
  "client_id": "crm-service",
  "worker_host": "ip-10-0-12-89",
  "doc_name": "ModelOptimization",
  "pages_count": 47,
  "sha256": "0c09f432d34192a86a7aeabc1e0e9c3bbdf03d4261cf2d7bf7021cc97064c21b",
  "download_url": "https://uet-pdf-watermark.s3.amazonaws.com/output/ModelOptimization_watermarked.pdf?...",
  "processing_time_ms": 1285.76
}
```

### 5.2. Kiểm định tài liệu (`GET /api/v1/audit-logs/verify/{sha256}`)
Tra cứu nguồn gốc và tính toàn vẹn của tệp PDF:

**Response (200 OK - Hợp lệ):**
```json
{
  "verified": true,
  "sha256": "0c09f432d34192a86a7aeabc1e0e9c3bbdf03d4261cf2d7bf7021cc97064c21b",
  "document": {
    "client_id": "crm-service",
    "doc_name": "ModelOptimization",
    "pages_count": 47,
    "created_at_vn": "2026-11-23 02:19:09",
    "worker_host": "ip-10-0-12-89"
  },
  "message": "Tài liệu chính thống đã được xác thực tính toàn vẹn và nguồn gốc cấp phát."
}
```

### 5.3. Các endpoint khác
* `GET /health`: Kiểm tra sức khỏe phục vụ ALB Target Group.
* `GET /api/v1/audit-logs?limit=50`: Lấy danh sách nhật ký kiểm toán gần nhất.
* `POST /api/watermark`: Endpoint tương thích ngược hỗ trợ Form Upload trực tiếp từ máy tính.
* `GET /docs`: Swagger UI tương tác trực tiếp chuẩn OpenAPI.

---

## 📁 6. Cấu trúc mã nguồn

```text
Dynamic-PDF-Watermarking-Pipeline/
├── main.py                   # Microservice FastAPI v2.1 (Watermarking Engine, API, Web Portal)
├── load_test.py              # Công cụ bắn tải đa luồng 6 phút, in Worker Host trực tiếp
├── get_sha256.py             # Script tính mã SHA-256 cục bộ và tạo link kiểm định nhanh
├── manage_aws.py             # Script tự động hóa Wake / Sleep hạ tầng AWS về 0 USD/h
├── ModelOptimization.pdf     # Tệp PDF kiểm thử mẫu (47 trang)
├── requirements.txt          # Thư viện phụ thuộc (FastAPI, PyMuPDF, Boto3, SQLAlchemy, Psycopg2)
├── .env.example              # Mẫu cấu hình môi trường hệ thống
├── .env                      # Cấu hình biến môi trường cục bộ (được gitignore)
├── .gitignore                # Bảo vệ an toàn Access Keys, PEM keys và Virtualenv
└── README.md                 # Tài liệu toàn diện về dự án
```

---

## 🛠 7. Hướng dẫn cài đặt & Thực thi

### 7.1. Cài đặt môi trường cục bộ
```bash
# 1. Tạo và kích hoạt môi trường ảo
python3 -m venv .venv
source .venv/bin/activate       # Trên Linux/macOS
# .venv\Scripts\Activate.ps1   # Trên Windows PowerShell

# 2. Cài đặt thư viện
pip install -r requirements.txt

# 3. Chạy server phát triển cục bộ
python3 main.py
# Truy cập giao diện: http://localhost:8000
```

### 7.2. Kiểm thử mã băm SHA-256 cục bộ
```bash
python3 get_sha256.py ModelOptimization.pdf
# Hoặc chạy tương tác kéo-thả file vào terminal:
python3 get_sha256.py
```

### 7.3. Kịch bản chạy bắn tải & Demo Auto-Scaling (6 phút)
```bash
# Bắn tải đồng thời 25 luồng trong 360 giây tới Application Load Balancer
python3 load_test.py
```
* **Màn hình Terminal sẽ hiển thị theo thời gian thực:**
  * Từng Worker Host xử lý mỗi request.
  * Thông báo màu vàng khi máy chủ thứ 3 & thứ 4 gia nhập nhận tải.
  * Tốc độ xử lý (req/s), độ trễ (ms) và bảng phân bổ tỷ lệ phần trăm giữa các EC2.

### 7.4. Quản trị hạ tầng AWS từ xa (`manage_aws.py`)
> Đặt file `hung_accessKeys.csv` vào thư mục gốc để script tự nạp quyền an toàn.

```bash
# 1. Đánh thức toàn bộ hệ thống (Bật NAT, RDS, ALB, 2 máy EC2 và chờ Healthy):
python3 manage_aws.py wake

# 2. Tạm dừng toàn bộ hệ thống về 0 USD/giờ (Xóa NAT, xóa ALB, Stop RDS, đưa ASG về 0):
python3 manage_aws.py sleep

# 3. Tạm dừng EC2/RDS/NAT nhưng giữ lại ALB để cố định DNS:
python3 manage_aws.py sleep --keep-alb
```

---

## 💰 8. Bảng ước tính chi phí hàng tháng (Region: ap-southeast-1)

| Dịch vụ AWS | Quy mô giả định (24/7) | Mục đích sử dụng | Đơn giá tham khảo | Chi phí ước tính/tháng |
|---|---|---|---|:---:|
| **Amazon EC2 (ASG)** | 2 instances t3.small (730h) | Worker xử lý đóng dấu PDF | ~0.0264 USD/giờ | ~42.50 USD |
| **Amazon EBS (gp3)** | 20 GB x 2 máy = 40 GB | Ổ đĩa OS & bộ đệm tạm `/tmp` | 0.096 USD/GB-tháng | ~3.84 USD |
| **Application Load Balancer** | 1 ALB (730h) + 1 LCU | Cân bằng tải HTTP Public & SSL | ~0.0252 USD/giờ + LCU | ~24.80 USD |
| **NAT Gateway** | 1 NAT Gateway (730h) + 20 GB | Cấp Internet an toàn cho Private Subnets | ~0.059 USD/giờ + data | ~44.25 USD *(~4.30 USD nếu dùng NAT Instance)* |
| **Amazon EFS** | 5 GB Standard lưu trữ NFSv4 | Shared Input Cache & Font Unicode | 0.36 USD/GB-tháng | ~1.80 USD |
| **Amazon S3** | 100 GB lưu trữ + 200.000 requests | Lưu trữ mã nguồn & xuất PDF | 0.025 USD/GB-tháng | ~3.20 USD |
| **Amazon RDS** | 1 instance db.t4g.micro (PostgreSQL) | Nhật ký kiểm toán `audit_logs` | ~0.018 USD/giờ + đĩa | ~15.44 USD |
| **CloudWatch & SNS** | 5 Metrics, 3 Alarms, Email SNS | Cảm biến giám sát & kích hoạt ASG | Ngưỡng Free Tier / 0.10$ | ~0.30 USD |
| **TỔNG CỘNG** | | | | **~136.13 USD/tháng** *(hoặc **~96.18 USD** với NAT Instance)* |

> [!TIP]
> **Chiến lược tối ưu ngân sách thực tế:** Sử dụng lệnh `python3 manage_aws.py sleep` ngay sau các buổi học và demo thực hành để hạ toàn bộ chi phí EC2, ALB, NAT và RDS về **0 USD/giờ**, bảo toàn tuyệt đối hạn mức credit của tài khoản.
