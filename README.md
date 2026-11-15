# Hệ thống Đóng dấu Bản quyền Tài liệu Đề thi và Giáo trình Hàng loạt trên AWS
## (Dynamic PDF Watermarking Pipeline) 🚀

> **Học phần:** Điện toán đám mây (INT 3319 3)  
> **Khoa Công nghệ Thông tin – Trường Đại học Công nghệ, Đại học Quốc gia Hà Nội (UET - VNU)**  

---

## 👥 1. Thông tin nhóm thực hiện

| STT | Họ và tên | Mã sinh viên | Vai trò | Mảng phụ trách chính |
|:---:|---|:---:|:---:|---|
| **1** | **Trần Nhật Hưng** | **24021507** | Nhóm trưởng | **Tính toán & Mở rộng:** Cấu hình EC2, Cân bằng tải (ALB), Tự động mở rộng (ASG), Giám sát (CloudWatch, SNS) & Tối ưu chi phí. |
| **2** | **Nguyễn Nam Khánh** | **24021531** | Thành viên | **Hạ tầng & Lưu trữ:** Thiết kế VPC, Phân quyền & Bảo mật (Security Group, IAM Role), Lưu trữ đối tượng (S3) & Hệ tệp mạng (EFS). |
| **3** | **Đỗ Lê Duy** | **24021445** | Thành viên | **Ứng dụng & Dữ liệu:** Cơ sở dữ liệu kiểm toán (RDS), Phát triển Web/API đóng dấu PDF (FastAPI + PyMuPDF) & Kịch bản kiểm thử chịu tải (Load Testing). |

---

## 🎯 2. Bài toán thực tiễn & Lý do lựa chọn Cloud

* **Đối tượng sử dụng:** Các trường đại học, trung tâm khảo thí, nhà xuất bản số và tổ chức giáo dục.
* **Bài toán thực tế:** Trước mỗi kỳ thi trực tuyến hoặc đợt phát hành giáo trình nội bộ, hàng nghìn sinh viên truy cập đồng thời để tải tài liệu. Để chống rò rỉ đề thi và phát tán tài liệu trái phép, hệ thống cần tự động chèn động (**Dynamic Watermark**) thông tin định danh của từng cá nhân (Họ tên, Mã sinh viên, Thời gian cấp phát, Mã băm kiểm chứng SHA-256) cùng con dấu tổ chức lên toàn bộ các trang PDF theo thời gian thực.
* **Vì sao cần Điện toán đám mây:**
  - **Tải đột biến (Peak Load):** Lưu lượng truy cập tăng vọt gấp hàng chục lần trong vài phút khi mở đề thi. Máy chủ vật lý đơn lẻ sẽ bị quá tải (CPU 100%, lỗi 504 Gateway Timeout).
  - **Auto Scaling & Pay-as-you-go:** AWS Auto Scaling tự động co giãn số lượng EC2 Worker theo tải CPU thực tế, vừa đảm bảo tính sẵn sàng cao (High Availability), vừa có thể thu hồi tài nguyên về mức 0 USD/giờ khi hết kỳ thi để tối ưu ngân sách.

---

## 🏛 3. Sơ đồ kiến trúc & Luồng dữ liệu

### 3.1. Sơ đồ kiến trúc trên AWS (Region: ap-southeast-1, VPC CIDR: 10.0.0.0/16)

```mermaid
flowchart TD
    subgraph Internet ["Môi trường ngoài / Người dùng"]
        User["Client (Sinh viên / Hệ thống khảo thí)"]
    end

    subgraph VPC ["Amazon Virtual Private Cloud (10.0.0.0/16)"]
        subgraph PublicSubnets ["Public Subnets (ap-southeast-1a & 1b)"]
            ALB["Application Load Balancer (ALB)\n(Port 80 -> Health Check /health)"]
            NAT["NAT Gateway\n(Cấp Internet 1 chiều cho Private Subnets)"]
        end

        subgraph PrivateSubnets ["Private Subnets (10.0.11.0/24 & 10.0.12.0/24)"]
            ASG["Auto Scaling Group (EC2 Workers)\n(FastAPI + PyMuPDF | Port 8000)"]
            EFS["Amazon EFS (NFSv4)\n(Kho Font Unicode & Con dấu mẫu)"]
            RDS[("Amazon RDS (PostgreSQL / MySQL)\n(Bảng audit_logs định danh)")]
        end
    end

    subgraph AWSStorage ["Dịch vụ Lưu trữ & Giám sát AWS"]
        S3[("Amazon S3 (uet-pdf-watermark)\n- input/: PDF gốc\n- output/: PDF đã đóng dấu")]
        CW["Amazon CloudWatch & SNS\n(Alarm CPU > 60% -> Kích hoạt ASG & Gửi Email)"]
    end

    User -->|1. Gửi yêu cầu đóng dấu| ALB
    ALB -->|2. Phân phối tải HTTP| ASG
    ASG -->|3. Đọc font & logo mẫu| EFS
    ASG -->|4. Lấy PDF gốc & Upload PDF kết quả| S3
    ASG -->|5. Ghi nhật ký kiểm toán SHA-256| RDS
    ASG -->|6. Trả Pre-signed URL| ALB
    ALB -->|7. Nhận Pre-signed URL| User
    User -->|8. Tải PDF trực tiếp tốc độ cao| S3
    ASG -.->|Giám sát CPU Metrics| CW
    CW -.->|Kích hoạt Scale Out| ASG
```

### 3.2. Luồng dữ liệu (Data Flow)
1. **Gửi yêu cầu:** Người dùng gửi yêu cầu cấp phát tài liệu (kèm Mã sinh viên, Họ tên, Mã tài liệu hoặc file tùy chỉnh) tới DNS của **ALB**.
2. **Điều phối tải:** ALB kiểm tra trạng thái sức khỏe (`/health`) và điều phối request tới một EC2 Worker trong Private Subnet.
3. **Truy xuất tài nguyên kép:** EC2 Worker sử dụng **IAM Role** để tải PDF gốc từ **S3** (hoặc EFS cache đệm) và đọc font chữ chuẩn, logo mẫu trực tiếp từ **Amazon EFS**.
4. **Xử lý đồ họa:** Worker chèn watermark định danh cá nhân và con dấu bản quyền lên toàn bộ các trang PDF bằng **PyMuPDF**.
5. **Định danh & Ghi nhật ký:** Tính mã băm **SHA-256**, upload bản PDF hoàn thiện lên **S3** (`output/`), lưu vết vào bảng `audit_logs` trên **Amazon RDS**, và sinh **S3 Pre-signed URL** (hạn 60 phút).
6. **Phản hồi:** Trả URL về cho người dùng tải trực tiếp từ S3, giải phóng băng thông cho cụm EC2 và ALB.

---

## 💡 4. Lý giải lựa chọn công nghệ (CLO2)

* **Vì sao kết hợp cả S3, EFS và EBS?**
  - **S3 (Object Storage):** Lưu trữ PDF đầu vào/đầu ra với độ bền 99.999999999% (11 số 9), chi phí rẻ hơn EFS ~10 lần. Pre-signed URL giúp người dùng tải trực tiếp từ S3, giảm tải tối đa cho EC2/ALB.
  - **EFS (File Storage):** Thư viện PyMuPDF cần đọc trực tiếp font `.ttf` và hình ảnh con dấu từ đường dẫn file POSIX. EFS cho phép mọi EC2 Worker (kể cả máy mới do ASG bật lên) dùng chung kho tài nguyên qua giao thức NFSv4 mà không cần rebuild Custom AMI.
  - **EBS (Block Storage):** Cung cấp IOPS cao và độ trễ thấp nhất cho phân vùng root OS và thư mục xử lý tạm `/tmp/wm_work`.
* **Vì sao chọn Amazon RDS thay vì tự cài DB trên EC2 hay DynamoDB?**
  - So với tự cài DB: RDS tự động hóa sao lưu (Automated Backups), bảo mật và hỗ trợ Multi-AZ sẵn sàng cho môi trường sản xuất.
  - So với DynamoDB: Nhật ký kiểm toán có quan hệ chặt chẽ giữa Sinh viên - Tài liệu - Lịch sử cấp phát, cần câu lệnh truy vấn cấu trúc SQL và đảm bảo tính toàn vẹn dữ liệu (ACID).
* **Vì sao chọn EC2 Auto Scaling + ALB thay vì AWS Lambda?**
  - Tác vụ xử lý PDF nặng (tài liệu giáo trình 200 - 300 trang) cần môi trường thực thi chứa thư viện native C/C++, RAM lớn và mount đĩa EFS. Khi xử lý liên tục, EC2 ASG tối ưu chi phí hơn và thể hiện rõ cấu trúc mạng doanh nghiệp (VPC/Subnets) theo chuẩn học phần.

---

## 📁 5. Cấu trúc mã nguồn

```text
Dynamic-PDF-Watermarking-Pipeline/
├── main.py                   # Ứng dụng Web FastAPI & Logic đóng dấu PDF bằng PyMuPDF
├── manage_aws.py             # Script tự động hóa Wake / Sleep toàn bộ hạ tầng AWS
├── load_test.py              # Script bắn tải đa luồng mô phỏng sinh viên tải tài liệu
├── ModelOptimization.pdf     # Tệp tài liệu kiểm thử mẫu (47 trang)
├── requirements.txt          # Danh sách thư viện Python phụ thuộc
├── .env.example              # Mẫu biến môi trường hệ thống
├── .env                      # File cấu hình biến môi trường cục bộ (được gitignore)
├── .gitignore                # Bảo vệ an toàn Access Keys, PEM keys và Virtualenv
└── README.md                 # Tài liệu toàn diện về dự án
```

---

## 🛠 6. Hướng dẫn cài đặt & Chạy ứng dụng

### 6.1. Khởi tạo môi trường ảo

```bash
# 1. Tạo môi trường ảo
python3 -m venv .venv

# 2. Kích hoạt môi trường ảo
source .venv/bin/activate       # Trên Linux/macOS
# .venv\Scripts\Activate.ps1   # Trên Windows PowerShell

# 3. Cài đặt các thư viện phụ thuộc
pip install -r requirements.txt
```

### 6.2. Cấu hình biến môi trường (`.env`)

Tạo file `.env` từ file mẫu:
```bash
cp .env.example .env
```
Nội dung file `.env`:
```ini
DB_URL=sqlite:////tmp/audit.db
# Khi kết nối tới RDS thực tế:
# DB_URL=postgresql://postgres:password@pdf-watermark-db.xxxx.ap-southeast-1.rds.amazonaws.com:5432/watermark_db

S3_BUCKET=uet-pdf-watermark
EFS_DIR=/tmp/watermark_efs_fallback   # Hoặc /mnt/efs trên EC2
AWS_REGION=ap-southeast-1
```

### 6.3. Chạy ứng dụng

* **Chạy Web API tại máy cục bộ:**
  ```bash
  python main.py
  # Hoặc: uvicorn main:app --reload --host 0.0.0.0 --port 8000
  ```
  Truy cập giao diện tại: `http://localhost:8000`

* **Quản trị hạ tầng AWS từ xa (`manage_aws.py`):**
  > Đặt file `hung_accessKeys.csv` vào thư mục gốc để script tự nạp thông tin xác thực an toàn.

  ```bash
  # Đánh thức hạ tầng (Bật NAT, RDS, ALB, 2 máy EC2 và chờ Healthy):
  python manage_aws.py wake

  # Tạm dừng toàn bộ hệ thống về 0 USD/giờ (Xóa NAT, ALB, Stop RDS, đưa ASG về 0):
  python manage_aws.py sleep

  # Tạm dừng EC2/RDS/NAT nhưng giữ lại ALB để cố định DNS:
  python manage_aws.py sleep --keep-alb
  ```

* **Chạy script kiểm thử tải:**
  ```bash
  python load_test.py
  ```

---

## 💰 7. Bảng ước tính chi phí hàng tháng (Region: ap-southeast-1)

| Dịch vụ AWS | Quy mô giả định (24/7) | Mục đích sử dụng | Đơn giá tham khảo | Chi phí ước tính/tháng |
|---|---|---|---|:---:|
| **Amazon EC2 (ASG)** | 2 instances t3.small (730h) | Xử lý đóng dấu PDF | ~0.0264 USD/giờ | ~42.50 USD |
| **Amazon EBS (gp3)** | 20 GB x 2 máy = 40 GB | Ổ đĩa HĐH & bộ đệm tạm | 0.096 USD/GB-tháng | ~3.84 USD |
| **Application Load Balancer** | 1 ALB (730h) + 1 LCU | Cân bằng tải HTTP Public | ~0.0252 USD/giờ + LCU | ~24.80 USD |
| **NAT Gateway** | 1 NAT Gateway (730h) + 20 GB data | Cấp Internet an toàn cho Private Subnet | ~0.059 USD/giờ + traffic | ~44.25 USD *(hoặc ~4.30 USD nếu dùng NAT Instance)* |
| **Amazon EFS** | 5 GB Standard lưu trữ qua NFSv4 | Kho Font Unicode & Logo mẫu | 0.36 USD/GB-tháng | ~1.80 USD |
| **Amazon S3** | 100 GB lưu trữ PDF + 200.000 requests | Lưu trữ PDF gốc & xuất file | 0.025 USD/GB-tháng | ~3.20 USD |
| **Amazon RDS** | 1 instance db.t4g.micro (20 GB gp3) | Cơ sở dữ liệu kiểm toán SHA-256 | ~0.018 USD/giờ + đĩa | ~15.44 USD |
| **CloudWatch & SNS** | 5 Metrics, 3 Alarms, 1.000 email SNS | Giám sát & gửi email cảnh báo | Ngưỡng Free Tier / 0.10$ | ~0.30 USD |
| **TỔNG CỘNG** | | | | **~136.13 USD/tháng** *(hoặc **~96.18 USD** với NAT Instance)* |

> [!TIP]
> **Giải pháp tối ưu chi phí thực tế:** Dự án sử dụng lệnh `python manage_aws.py sleep` sau mỗi buổi thực hành, giúp hạ toàn bộ chi phí EC2, ALB, NAT và RDS về **0 USD/giờ**, loại bỏ hoàn toàn nguy cơ vượt hạn mức credit AWS.

