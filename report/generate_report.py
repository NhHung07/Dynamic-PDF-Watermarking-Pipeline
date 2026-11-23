import os
import sys
import weasyprint

def create_report():
    print("Generating comprehensive final report for INT3319 3...")

    # Load UET Logo as base64 Data URI
    import base64
    script_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(script_dir, "uet_logo.png")
    if not os.path.exists(logo_path):
        logo_path = "uet_logo.png"
    if not os.path.exists(logo_path):
        logo_path = "extracted_logo.png"
    
    with open(logo_path, "rb") as f:
        logo_b64 = base64.b64encode(f.read()).decode("utf-8")

    # Define the SVG Architecture Diagram
    svg_architecture = """
    <svg width="100%" height="480" viewBox="0 0 950 480" xmlns="http://www.w3.org/2000/svg" style="font-family: 'Liberation Sans', 'DejaVu Sans', sans-serif;">
      <defs>
        <linearGradient id="clientGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#2c3e50"/>
          <stop offset="100%" stop-color="#34495e"/>
        </linearGradient>
        <linearGradient id="albGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#7c3aed"/>
          <stop offset="100%" stop-color="#6d28d9"/>
        </linearGradient>
        <linearGradient id="ec2Grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#ea580c"/>
          <stop offset="100%" stop-color="#c2410c"/>
        </linearGradient>
        <linearGradient id="storageGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#0284c7"/>
          <stop offset="100%" stop-color="#0369a1"/>
        </linearGradient>
        <linearGradient id="rdsGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#059669"/>
          <stop offset="100%" stop-color="#047857"/>
        </linearGradient>
        <linearGradient id="cwGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#dc2626"/>
          <stop offset="100%" stop-color="#b91c1c"/>
        </linearGradient>
        <filter id="shadow" x="-5%" y="-5%" width="110%" height="115%" filterUnits="userSpaceOnUse">
          <feDropShadow dx="1" dy="2" stdDeviation="2" flood-opacity="0.12"/>
        </filter>
        <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#475569"/>
        </marker>
        <marker id="arrow-scale" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#dc2626"/>
        </marker>
      </defs>

      <!-- Background VPC Box -->
      <rect x="180" y="20" width="750" height="440" rx="12" fill="#f8fafc" stroke="#94a3b8" stroke-width="2" stroke-dasharray="6,4"/>
      <text x="200" y="48" font-size="14" font-weight="bold" fill="#1e293b">AMAZON VPC: 10.0.0.0/16 (Region: ap-southeast-1 Singapore)</text>

      <!-- Client Layer -->
      <g filter="url(#shadow)">
        <rect x="15" y="85" width="145" height="270" rx="8" fill="url(#clientGrad)"/>
        <text x="87" y="110" font-size="12" font-weight="bold" fill="#ffffff" text-anchor="middle">CLIENT &amp; WEB APPS</text>
        <line x1="25" y1="118" x2="150" y2="118" stroke="#64748b" stroke-width="1"/>
        <rect x="23" y="125" width="128" height="135" rx="4" fill="#1e293b"/>
        <text x="87" y="142" font-size="10.5" font-weight="bold" fill="#38bdf8" text-anchor="middle">Web Platform (5 Tab)</text>
        <text x="87" y="160" font-size="9" fill="#f1f5f9" text-anchor="middle">• Master Document Lib</text>
        <text x="87" y="177" font-size="9" fill="#f1f5f9" text-anchor="middle">• Live Studio (Canvas)</text>
        <text x="87" y="194" font-size="9" fill="#f1f5f9" text-anchor="middle">• Batch Studio (ZIP)</text>
        <text x="87" y="211" font-size="9" fill="#f1f5f9" text-anchor="middle">• SHA-256 Verifier</text>
        <text x="87" y="228" font-size="9" fill="#f1f5f9" text-anchor="middle">• RDS Audit Log</text>
        <text x="87" y="246" font-size="9" fill="#94a3b8" text-anchor="middle">Web Crypto API (&lt;20ms)</text>
        <text x="87" y="280" font-size="10" fill="#f8fafc" text-anchor="middle">Hệ thống Doanh nghiệp</text>
        <text x="87" y="295" font-size="9" fill="#cbd5e1" text-anchor="middle">(CRM / Billing / EdTech)</text>
        <text x="87" y="325" font-size="10" font-weight="bold" fill="#fca5a5" text-anchor="middle">Load Test (28 luồng)</text>
        <text x="87" y="340" font-size="8.5" fill="#fca5a5" text-anchor="middle">72.615 trang / 6 phút</text>
      </g>

      <!-- Public Subnets Box -->
      <rect x="205" y="70" width="200" height="375" rx="8" fill="#e0f2fe" stroke="#38bdf8" stroke-width="1.5"/>
      <text x="215" y="92" font-size="12" font-weight="bold" fill="#0369a1">Public Subnets (Multi-AZ)</text>
      <text x="215" y="108" font-size="10" fill="#0284c7">10.0.1.0/24 (1a) | 10.0.2.0/24 (1b)</text>

      <!-- ALB Component -->
      <g filter="url(#shadow)">
        <rect x="220" y="130" width="170" height="110" rx="6" fill="url(#albGrad)"/>
        <text x="305" y="155" font-size="12" font-weight="bold" fill="#ffffff" text-anchor="middle">Application Load Balancer</text>
        <text x="305" y="172" font-size="10" fill="#e9d5ff" text-anchor="middle">DNS: PDF-Watermark-ALB</text>
        <text x="305" y="190" font-size="10" fill="#ffffff" text-anchor="middle">• Internet-Facing (Port 80)</text>
        <text x="305" y="206" font-size="10" fill="#ffffff" text-anchor="middle">• Health Check: /health</text>
        <text x="305" y="222" font-size="10" fill="#ffffff" text-anchor="middle">• Thuật toán: Round-Robin</text>
      </g>

      <!-- NAT Gateway Component -->
      <g filter="url(#shadow)">
        <rect x="220" y="270" width="170" height="75" rx="6" fill="#0f766e"/>
        <text x="305" y="295" font-size="12" font-weight="bold" fill="#ffffff" text-anchor="middle">NAT Gateway / Instance</text>
        <text x="305" y="312" font-size="10" fill="#99f6e4" text-anchor="middle">Elastic IP tĩnh</text>
        <text x="305" y="330" font-size="10" fill="#ffffff" text-anchor="middle">Internet 1 chiều cho Private</text>
      </g>

      <!-- Private Subnets Box -->
      <rect x="430" y="70" width="485" height="375" rx="8" fill="#fef2f2" stroke="#f87171" stroke-width="1.5"/>
      <text x="445" y="92" font-size="12" font-weight="bold" fill="#b91c1c">Private Subnets (Multi-AZ | Không có Public IP)</text>
      <text x="445" y="108" font-size="10" fill="#dc2626">10.0.11.0/24 (ap-southeast-1a) &amp; 10.0.12.0/24 (ap-southeast-1b)</text>

      <!-- EC2 Auto Scaling Group Box -->
      <rect x="445" y="125" width="235" height="225" rx="6" fill="#fff7ed" stroke="#fb923c" stroke-width="1.5"/>
      <text x="562" y="145" font-size="11" font-weight="bold" fill="#c2410c" text-anchor="middle">Auto Scaling Group (2 - 4 EC2)</text>

      <!-- EC2 1 -->
      <g filter="url(#shadow)">
        <rect x="455" y="155" width="215" height="42" rx="4" fill="url(#ec2Grad)"/>
        <text x="562" y="172" font-size="10" font-weight="bold" fill="#ffffff" text-anchor="middle">EC2 Worker #1 (ip-10-0-11-204)</text>
        <text x="562" y="187" font-size="9" fill="#ffedd5" text-anchor="middle">FastAPI Engine v2.1 + PyMuPDF | Port 8000</text>
      </g>

      <!-- EC2 2 -->
      <g filter="url(#shadow)">
        <rect x="455" y="202" width="215" height="42" rx="4" fill="url(#ec2Grad)"/>
        <text x="562" y="219" font-size="10" font-weight="bold" fill="#ffffff" text-anchor="middle">EC2 Worker #2 (ip-10-0-12-89)</text>
        <text x="562" y="234" font-size="9" fill="#ffedd5" text-anchor="middle">FastAPI Engine v2.1 + PyMuPDF | Port 8000</text>
      </g>

      <!-- EC2 3 & 4 (Auto-Scaled) -->
      <rect x="455" y="250" width="215" height="42" rx="4" fill="#fed7aa" stroke="#ea580c" stroke-width="1" stroke-dasharray="3,2"/>
      <text x="562" y="267" font-size="10" font-weight="bold" fill="#9a3412" text-anchor="middle">EC2 Worker #3 &amp; #4 (Scale Out)</text>
      <text x="562" y="282" font-size="9" fill="#c2410c" text-anchor="middle">Khởi tạo tự động khi CPU &gt;= 50% trong 60s</text>

      <!-- Attached Storage within EC2 -->
      <rect x="455" y="300" width="215" height="40" rx="4" fill="#f1f5f9" stroke="#cbd5e1"/>
      <text x="562" y="315" font-size="9" font-weight="bold" fill="#334155" text-anchor="middle">Amazon EBS (gp3 20GB/máy)</text>
      <text x="562" y="328" font-size="8" fill="#64748b" text-anchor="middle">Root Volume OS &amp; Cache tạm thời /tmp</text>

      <!-- EFS Box -->
      <g filter="url(#shadow)">
        <rect x="700" y="125" width="200" height="75" rx="6" fill="url(#storageGrad)"/>
        <text x="800" y="147" font-size="11" font-weight="bold" fill="#ffffff" text-anchor="middle">Amazon EFS (Shared NFSv4)</text>
        <text x="800" y="163" font-size="9" fill="#bae6fd" text-anchor="middle">Mount point: /mnt/efs</text>
        <text x="800" y="177" font-size="9" fill="#ffffff" text-anchor="middle">• Cache PDF mẫu (Hit &lt;5ms)</text>
        <text x="800" y="191" font-size="9" fill="#ffffff" text-anchor="middle">• Kho Font Unicode &amp; Mẫu dấu</text>
      </g>

      <!-- RDS Box -->
      <g filter="url(#shadow)">
        <rect x="700" y="215" width="200" height="85" rx="6" fill="url(#rdsGrad)"/>
        <text x="800" y="237" font-size="11" font-weight="bold" fill="#ffffff" text-anchor="middle">Amazon RDS PostgreSQL 18.3</text>
        <text x="800" y="253" font-size="9" fill="#a7f3d0" text-anchor="middle">Instance: db.t4g.micro | Port 5432</text>
        <text x="800" y="269" font-size="9" fill="#ffffff" text-anchor="middle">• Bảng audit_logs (Mã SHA-256)</text>
        <text x="800" y="283" font-size="9" fill="#ffffff" text-anchor="middle">• Connection Pooling QueuePool</text>
      </g>

      <!-- S3 Managed Service -->
      <g filter="url(#shadow)">
        <rect x="700" y="315" width="200" height="110" rx="6" fill="#1e3a8a"/>
        <text x="800" y="337" font-size="11" font-weight="bold" fill="#ffffff" text-anchor="middle">Amazon S3 (uet-pdf-watermark)</text>
        <text x="800" y="353" font-size="9" fill="#93c5fd" text-anchor="middle">Lưu trữ Đối tượng (Private Bucket)</text>
        <text x="800" y="370" font-size="9" fill="#ffffff" text-anchor="middle">• input/: File gốc</text>
        <text x="800" y="386" font-size="9" fill="#ffffff" text-anchor="middle">• output/: File đã đóng dấu</text>
        <text x="800" y="402" font-size="9" fill="#38bdf8" text-anchor="middle">• S3 Pre-signed URL (15 phút)</text>
        <text x="800" y="416" font-size="9" fill="#94a3b8" text-anchor="middle">• Lifecycle Rule: Hủy sau 24h</text>
      </g>

      <!-- CloudWatch & SNS Box -->
      <g filter="url(#shadow)">
        <rect x="445" y="360" width="235" height="75" rx="6" fill="url(#cwGrad)"/>
        <text x="562" y="380" font-size="11" font-weight="bold" fill="#ffffff" text-anchor="middle">CloudWatch &amp; Amazon SNS</text>
        <text x="562" y="396" font-size="9" fill="#fecaca" text-anchor="middle">• Alarm CPU &gt;= 50% (Chu kỳ 60s)</text>
        <text x="562" y="412" font-size="9" fill="#ffffff" text-anchor="middle">• Ra lệnh ASG Scale Out tức thì</text>
        <text x="562" y="426" font-size="9" fill="#ffffff" text-anchor="middle">• Gửi Email cảnh báo qua SNS</text>
      </g>

      <!-- Connecting Flow Arrows -->
      <!-- 1. Client to ALB -->
      <path d="M 150 185 L 220 185" stroke="#475569" stroke-width="2" marker-end="url(#arrow)"/>
      <text x="185" y="177" font-size="9" font-weight="bold" fill="#1e293b" text-anchor="middle">① POST</text>

      <!-- 2. ALB to EC2 ASG -->
      <path d="M 390 185 L 445 185" stroke="#475569" stroke-width="2" marker-end="url(#arrow)"/>
      <text x="417" y="177" font-size="9" font-weight="bold" fill="#1e293b" text-anchor="middle">② Proxy</text>

      <!-- 3. EC2 to EFS -->
      <path d="M 670 160 L 700 160" stroke="#0284c7" stroke-width="1.8" marker-end="url(#arrow)"/>
      <text x="685" y="153" font-size="8" font-weight="bold" fill="#0369a1" text-anchor="middle">③ Cache</text>

      <!-- 4. EC2 to RDS -->
      <path d="M 670 230 L 700 230" stroke="#059669" stroke-width="1.8" marker-end="url(#arrow)"/>
      <text x="685" y="223" font-size="8" font-weight="bold" fill="#047857" text-anchor="middle">④ Audit</text>

      <!-- 5. EC2 to S3 -->
      <path d="M 670 335 L 700 335" stroke="#1e3a8a" stroke-width="1.8" marker-end="url(#arrow)"/>
      <text x="685" y="328" font-size="8" font-weight="bold" fill="#1e3a8a" text-anchor="middle">⑤ Upload</text>

      <!-- 6. EC2 to CloudWatch (metrics) -->
      <path d="M 562 295 L 562 360" stroke="#dc2626" stroke-width="1.5" stroke-dasharray="3,3" marker-end="url(#arrow-scale)"/>

      <!-- 7. CloudWatch to ASG (scale out) -->
      <path d="M 520 360 L 520 295" stroke="#dc2626" stroke-width="1.5" marker-end="url(#arrow-scale)"/>

      <!-- 8. Client direct download from S3 (dashed curve) -->
      <path d="M 700 410 C 350 490, 80 440, 85 340" stroke="#2563eb" stroke-width="1.5" stroke-dasharray="4,3" fill="none" marker-end="url(#arrow)"/>
      <text x="350" y="470" font-size="9" font-weight="bold" fill="#1d4ed8" text-anchor="middle">⑧ Client tải trực tiếp PDF từ S3 Pre-signed URL (Không nghẽn EC2/ALB)</text>
    </svg>
    """

    # Define the SVG Sequence Diagram (Request Lifecycle)
    svg_sequence = """
    <svg width="100%" height="320" viewBox="0 0 900 320" xmlns="http://www.w3.org/2000/svg" style="font-family: 'Liberation Sans', 'DejaVu Sans', sans-serif;">
      <!-- Participants -->
      <rect x="20" y="20" width="100" height="35" rx="5" fill="#334155"/>
      <text x="70" y="42" font-size="11" font-weight="bold" fill="#fff" text-anchor="middle">Client / App</text>
      <line x1="70" y1="55" x2="70" y2="290" stroke="#94a3b8" stroke-dasharray="4,4"/>

      <rect x="180" y="20" width="110" height="35" rx="5" fill="#6d28d9"/>
      <text x="235" y="42" font-size="11" font-weight="bold" fill="#fff" text-anchor="middle">ALB (Port 80)</text>
      <line x1="235" y1="55" x2="235" y2="290" stroke="#94a3b8" stroke-dasharray="4,4"/>

      <rect x="350" y="20" width="130" height="35" rx="5" fill="#ea580c"/>
      <text x="415" y="42" font-size="11" font-weight="bold" fill="#fff" text-anchor="middle">EC2 FastAPI Worker</text>
      <line x1="415" y1="55" x2="415" y2="290" stroke="#94a3b8" stroke-dasharray="4,4"/>

      <rect x="540" y="20" width="90" height="35" rx="5" fill="#0284c7"/>
      <text x="585" y="42" font-size="11" font-weight="bold" fill="#fff" text-anchor="middle">EFS Cache</text>
      <line x1="585" y1="55" x2="585" y2="290" stroke="#94a3b8" stroke-dasharray="4,4"/>

      <rect x="680" y="20" width="100" height="35" rx="5" fill="#059669"/>
      <text x="730" y="42" font-size="11" font-weight="bold" fill="#fff" text-anchor="middle">RDS Postgres</text>
      <line x1="730" y1="55" x2="730" y2="290" stroke="#94a3b8" stroke-dasharray="4,4"/>

      <rect x="810" y="20" width="80" height="35" rx="5" fill="#1e3a8a"/>
      <text x="850" y="42" font-size="11" font-weight="bold" fill="#fff" text-anchor="middle">Amazon S3</text>
      <line x1="850" y1="55" x2="850" y2="290" stroke="#94a3b8" stroke-dasharray="4,4"/>

      <!-- Arrows -->
      <!-- 1 -->
      <line x1="70" y1="80" x2="235" y2="80" stroke="#1e293b" stroke-width="1.5" marker-end="url(#arrow)"/>
      <text x="150" y="74" font-size="9" fill="#1e293b" text-anchor="middle">1. POST /api/v1/watermark (JSON payload)</text>

      <!-- 2 -->
      <line x1="235" y1="105" x2="415" y2="105" stroke="#1e293b" stroke-width="1.5" marker-end="url(#arrow)"/>
      <text x="325" y="99" font-size="9" fill="#1e293b" text-anchor="middle">2. Forward HTTP (Round-Robin tới Worker rảnh)</text>

      <!-- 3 -->
      <line x1="415" y1="130" x2="585" y2="130" stroke="#0284c7" stroke-width="1.5" marker-end="url(#arrow)"/>
      <text x="500" y="124" font-size="9" fill="#0284c7" text-anchor="middle">3. Đọc Font Unicode &amp; PDF gốc (/mnt/efs/input/ &lt;5ms)</text>

      <!-- 4 -->
      <rect x="405" y="145" width="20" height="30" fill="#f97316"/>
      <text x="440" y="162" font-size="9" fill="#c2410c">4. PyMuPDF render watermark 45° &amp; Hash SHA-256</text>

      <!-- 5 -->
      <line x1="415" y1="190" x2="730" y2="190" stroke="#059669" stroke-width="1.5" marker-end="url(#arrow)"/>
      <text x="572" y="184" font-size="9" fill="#059669" text-anchor="middle">5. Ghi nhật ký audit_logs (request_id, sha256, worker_host, time_vn)</text>

      <!-- 6 -->
      <line x1="415" y1="215" x2="850" y2="215" stroke="#1e3a8a" stroke-width="1.5" marker-end="url(#arrow)"/>
      <text x="632" y="209" font-size="9" fill="#1e3a8a" text-anchor="middle">6. Đẩy PDF lên S3 output/ &amp; Sinh Pre-signed URL (15 min)</text>

      <!-- 7 -->
      <line x1="415" y1="240" x2="235" y2="240" stroke="#475569" stroke-width="1.5" stroke-dasharray="3,2"/>
      <line x1="235" y1="240" x2="70" y2="240" stroke="#475569" stroke-width="1.5" stroke-dasharray="3,2"/>
      <text x="150" y="235" font-size="9" fill="#475569" text-anchor="middle">7. HTTP 200 OK: Trả JSON (sha256, worker_host, download_url)</text>

      <!-- 8 -->
      <line x1="70" y1="270" x2="850" y2="270" stroke="#2563eb" stroke-width="1.5" marker-end="url(#arrow)"/>
      <text x="460" y="265" font-size="9" font-weight="bold" fill="#2563eb" text-anchor="middle">8. Client GET trực tiếp file từ S3 Pre-signed URL (Giải phóng 100% băng thông EC2)</text>
    </svg>
    """

    # Define the SVG Load Testing & Auto Scaling Timeline Chart
    svg_load_test_chart = """
    <svg width="100%" height="260" viewBox="0 0 850 260" xmlns="http://www.w3.org/2000/svg" style="font-family: 'Liberation Sans', 'DejaVu Sans', sans-serif;">
      <!-- Background Grid -->
      <rect x="60" y="20" width="750" height="200" fill="#f8fafc" stroke="#cbd5e1" stroke-width="1"/>
      <line x1="60" y1="70" x2="810" y2="70" stroke="#e2e8f0" stroke-width="1"/>
      <line x1="60" y1="120" x2="810" y2="120" stroke="#e2e8f0" stroke-width="1"/>
      <line x1="60" y1="170" x2="810" y2="170" stroke="#e2e8f0" stroke-width="1"/>

      <!-- Threshold Line (CPU 50%) -->
      <line x1="60" y1="120" x2="810" y2="120" stroke="#dc2626" stroke-width="1.5" stroke-dasharray="5,3"/>
      <text x="750" y="115" font-size="9" font-weight="bold" fill="#dc2626">Ngưỡng Alarm CPU 50%</text>

      <!-- Y Axis Labels -->
      <text x="50" y="25" font-size="9" fill="#64748b" text-anchor="end">100% / 50 req/s</text>
      <text x="50" y="75" font-size="9" fill="#64748b" text-anchor="end">75% / 37.5</text>
      <text x="50" y="125" font-size="9" fill="#64748b" text-anchor="end">50% / 25.0</text>
      <text x="50" y="175" font-size="9" fill="#64748b" text-anchor="end">25% / 12.5</text>
      <text x="50" y="223" font-size="9" fill="#64748b" text-anchor="end">0% / 0</text>

      <!-- X Axis Labels (Time in Seconds) -->
      <text x="60" y="235" font-size="9" fill="#64748b" text-anchor="middle">T+0s</text>
      <text x="185" y="235" font-size="9" fill="#64748b" text-anchor="middle">T+60s (Alarm)</text>
      <text x="260" y="235" font-size="9" fill="#64748b" text-anchor="middle">T+80s (EC2 #3)</text>
      <text x="380" y="235" font-size="9" fill="#64748b" text-anchor="middle">T+135s (EC2 #4)</text>
      <text x="550" y="235" font-size="9" fill="#64748b" text-anchor="middle">T+240s</text>
      <text x="800" y="235" font-size="9" fill="#64748b" text-anchor="middle">T+360s (Kết thúc)</text>

      <!-- CPU Utilization Curve (Red) -->
      <!-- 0s(220) -> 60s(45) -> 80s(55) -> 135s(125) -> 240s(130) -> 360s(135) -->
      <path d="M 60 215 Q 120 45, 185 45 L 260 65 L 380 125 L 550 128 L 810 132" fill="none" stroke="#ea580c" stroke-width="2.5"/>

      <!-- Throughput RPS Curve (Blue) -->
      <!-- 0s(220) -> 60s(150) -> 80s(130) -> 135s(80) -> 240s(72) -> 360s(70) -->
      <path d="M 60 220 Q 120 150, 185 145 L 260 115 L 380 78 L 550 72 L 810 70" fill="none" stroke="#2563eb" stroke-width="2.5"/>

      <!-- Server Count Step Curve (Green) -->
      <!-- 0s-80s: 2 servers (y=180) -> 80-135s: 3 servers (y=150) -> 135-360s: 4 servers (y=120) -->
      <path d="M 60 180 L 260 180 L 260 150 L 380 150 L 380 120 L 810 120" fill="none" stroke="#059669" stroke-width="2" stroke-dasharray="4,2"/>

      <!-- Event Markers -->
      <circle cx="185" cy="45" r="4" fill="#dc2626"/>
      <text x="185" y="35" font-size="9" font-weight="bold" fill="#dc2626" text-anchor="middle">Alarm Kích hoạt (CPU 87%)</text>

      <circle cx="260" cy="65" r="4" fill="#ea580c"/>
      <text x="260" y="55" font-size="8" font-weight="bold" fill="#c2410c" text-anchor="middle">Worker #3 Nhận tải</text>

      <circle cx="380" cy="125" r="4" fill="#059669"/>
      <text x="380" y="145" font-size="8" font-weight="bold" fill="#047857" text-anchor="middle">Worker #4 Nhận tải (CPU hạ về 48%)</text>

      <!-- Legend -->
      <rect x="580" y="30" width="220" height="55" rx="4" fill="#ffffff" stroke="#cbd5e1" opacity="0.95"/>
      <line x1="590" y1="42" x2="615" y2="42" stroke="#ea580c" stroke-width="2.5"/>
      <text x="625" y="45" font-size="9" fill="#1e293b">CPU Trung bình Cụm ASG (%)</text>
      <line x1="590" y1="57" x2="615" y2="57" stroke="#2563eb" stroke-width="2.5"/>
      <text x="625" y="60" font-size="9" fill="#1e293b">Thông lượng RPS (req/giây)</text>
      <line x1="590" y1="72" x2="615" y2="72" stroke="#059669" stroke-width="2" stroke-dasharray="4,2"/>
      <text x="625" y="75" font-size="9" fill="#1e293b">Số lượng EC2 Worker hoạt động</text>
    </svg>
    """

    html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<title>BÁO CÁO CUỐI KỲ - INT3319 3 - DYNAMIC PDF WATERMARKING PIPELINE</title>
<style>
  @page {{
    size: A4 portrait;
    margin-top: 25mm;
    margin-bottom: 25mm;
    margin-left: 25mm;
    margin-right: 20mm;

    @top-left {{
      content: "BÁO CÁO CUỐI KỲ: DYNAMIC PDF WATERMARKING PIPELINE ON AWS";
      font-family: "Liberation Sans", "DejaVu Sans", sans-serif;
      font-size: 8pt;
      color: #64748b;
      border-bottom: 0.5pt solid #cbd5e1;
      padding-bottom: 4px;
    }}

    @top-right {{
      content: "INT3319 3 - ĐIỆN TOÁN ĐÁM MÂY";
      font-family: "Liberation Sans", "DejaVu Sans", sans-serif;
      font-size: 8pt;
      font-weight: bold;
      color: #64748b;
      border-bottom: 0.5pt solid #cbd5e1;
      padding-bottom: 4px;
    }}

    @bottom-left {{
      content: "Trường Đại học Công nghệ - ĐHQGHN";
      font-family: "Liberation Sans", "DejaVu Sans", sans-serif;
      font-size: 8pt;
      color: #94a3b8;
      border-top: 0.5pt solid #cbd5e1;
      padding-top: 4px;
    }}

    @bottom-right {{
      content: "Trang " counter(page) " / " counter(pages);
      font-family: "Liberation Sans", "DejaVu Sans", sans-serif;
      font-size: 8pt;
      font-weight: bold;
      color: #1e293b;
      border-top: 0.5pt solid #cbd5e1;
      padding-top: 4px;
    }}
  }}

  @page:first {{
    size: A4 portrait;
    margin-top: 14mm;
    margin-bottom: 14mm;
    margin-left: 15mm;
    margin-right: 15mm;
    @top-left {{ content: normal; border: none; }}
    @top-right {{ content: normal; border: none; }}
    @bottom-left {{ content: normal; border: none; }}
    @bottom-right {{ content: normal; border: none; }}
  }}

  body {{
    font-family: "Liberation Sans", "DejaVu Sans", sans-serif;
    font-size: 11pt;
    line-height: 1.55;
    color: #1e293b;
    text-align: justify;
  }}

  /* Khung viền kép trang bìa (Chuẩn mẫu báo cáo UET) */
  .cover-frame-outer {{
    border: 2.5px solid #0f172a;
    padding: 2.5mm;
    height: 268mm;
    box-sizing: border-box;
    page-break-after: always;
  }}
  .cover-frame-inner {{
    border: 0.8px solid #0f172a;
    padding: 10mm 10mm 8mm 10mm;
    height: 261mm;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    text-align: center;
  }}

  /* Typography Trang Bìa */
  .cover-header-box {{
    margin-top: 2mm;
  }}
  .cover-univ {{
    font-size: 14pt;
    font-weight: bold;
    text-align: center;
    margin: 0;
    text-transform: uppercase;
    color: #0f172a;
    letter-spacing: 0.5px;
  }}
  .cover-subuniv {{
    font-size: 13pt;
    font-weight: bold;
    text-align: center;
    margin-top: 5px;
    margin-bottom: 0;
    text-transform: uppercase;
    color: #0f172a;
  }}
  .cover-divider {{
    width: 38%;
    height: 1.2px;
    background-color: #0f172a;
    margin: 10px auto 0 auto;
  }}
  .cover-logo-box {{
    margin: 0 auto;
    text-align: center;
  }}
  .cover-logo-img {{
    width: 130px;
    height: 130px;
    object-fit: contain;
  }}
  .cover-title-box {{
    text-align: center;
    margin-top: 4px;
  }}
  .cover-report-type {{
    font-size: 16pt;
    font-weight: bold;
    color: #0f172a;
    letter-spacing: 0.5px;
    margin-bottom: 6px;
  }}
  .cover-course {{
    font-size: 12pt;
    font-weight: bold;
    color: #0f172a;
    margin-bottom: 12px;
  }}
  .cover-project-label {{
    font-size: 11pt;
    font-weight: bold;
    color: #0f172a;
    margin-bottom: 4px;
  }}
  .cover-project-title {{
    font-size: 13.5pt;
    font-weight: bold;
    color: #0f172a;
    line-height: 1.35;
    text-transform: uppercase;
  }}
  .cover-project-subtitle {{
    font-size: 10pt;
    font-style: italic;
    color: #334155;
    margin-top: 4px;
  }}
  .cover-meta {{
    margin-top: 8px;
    font-size: 10.5pt;
    line-height: 1.7;
    text-align: left;
    hyphens: none;
  }}
  .cover-meta table {{
    width: 95%;
    margin: 0 auto;
    border-collapse: collapse;
    text-align: left;
  }}
  .cover-meta td {{
    vertical-align: top;
    padding: 3px 0;
    text-align: left;
  }}
  .cover-footer {{
    text-align: center;
    margin-top: 8px;
    font-size: 10.5pt;
    font-weight: bold;
    color: #0f172a;
  }}

  /* Headings */
  h1.chapter-title {{
    font-size: 15pt;
    font-weight: bold;
    color: #0f172a;
    text-transform: uppercase;
    border-bottom: 2px solid #0369a1;
    padding-bottom: 6px;
    margin-top: 24pt;
    margin-bottom: 14pt;
    page-break-before: always;
  }}
  h1.chapter-title:first-of-type {{
    page-break-before: always;
  }}

  h2.section-title {{
    font-size: 12.5pt;
    font-weight: bold;
    color: #0369a1;
    margin-top: 16pt;
    margin-bottom: 8pt;
    page-break-after: avoid;
  }}

  h3.subsection-title {{
    font-size: 11.5pt;
    font-weight: bold;
    color: #334155;
    margin-top: 12pt;
    margin-bottom: 6pt;
    page-break-after: avoid;
  }}

  /* Paragraphs and lists */
  p {{
    margin-top: 0;
    margin-bottom: 8pt;
    text-indent: 1.2em;
  }}
  p.no-indent {{
    text-indent: 0;
  }}
  ul, ol {{
    margin-top: 0;
    margin-bottom: 8pt;
    padding-left: 24px;
  }}
  li {{
    margin-bottom: 4pt;
  }}

  /* Tables */
  table.report-table {{
    width: 100%;
    border-collapse: collapse;
    margin: 12pt 0;
    font-size: 9.5pt;
    line-height: 1.45;
  }}
  table.report-table thead {{
    display: table-header-group;
  }}
  table.report-table tr {{
    page-break-inside: avoid;
  }}
  table.report-table th, table.report-table td {{
    border: 1px solid #cbd5e1;
    padding: 6pt 8pt;
    text-align: left;
    vertical-align: top;
  }}
  table.report-table th {{
    background-color: #f1f5f9;
    font-weight: bold;
    color: #0f172a;
    text-align: center;
  }}
  table.report-table tr:nth-child(even) td {{
    background-color: #f8fafc;
  }}

  /* Callouts */
  .callout {{
    border-left: 4px solid #0284c7;
    background-color: #f0f9ff;
    padding: 8pt 12pt;
    margin: 10pt 0;
    border-radius: 0 4px 4px 0;
    font-size: 10pt;
    page-break-inside: avoid;
  }}
  .callout-title {{
    font-weight: bold;
    color: #0369a1;
    margin-bottom: 4pt;
  }}
  .callout-warn {{
    border-left-color: #f59e0b;
    background-color: #fffbeb;
  }}
  .callout-warn .callout-title {{
    color: #b45309;
  }}
  .callout-success {{
    border-left-color: #10b981;
    background-color: #ecfdf5;
  }}
  .callout-success .callout-title {{
    color: #047857;
  }}

  /* Code and Pre */
  pre {{
    background-color: #0f172a;
    color: #f8fafc;
    padding: 8pt 12pt;
    border-radius: 4px;
    font-family: "Liberation Mono", "DejaVu Sans Mono", monospace;
    font-size: 8.5pt;
    line-height: 1.4;
    overflow-x: hidden;
    white-space: pre-wrap;
    margin: 10pt 0;
    page-break-inside: avoid;
  }}
  code {{
    font-family: "Liberation Mono", "DejaVu Sans Mono", monospace;
    font-size: 9pt;
    background-color: #f1f5f9;
    color: #b91c1c;
    padding: 1.5pt 3.5pt;
    border-radius: 3px;
  }}
  pre code {{
    background-color: transparent;
    color: inherit;
    padding: 0;
  }}

  /* Figures */
  .figure-box {{
    margin: 14pt auto;
    text-align: center;
    page-break-inside: avoid;
  }}
  .figure-caption {{
    font-size: 9.5pt;
    font-style: italic;
    color: #475569;
    margin-top: 6pt;
    text-align: center;
  }}

  /* TOC */
  .toc {{
    margin: 12pt 0;
    line-height: 1.6;
    font-size: 9.5pt;
  }}
  .toc-item, a.toc-item {{
    display: flex;
    justify-content: space-between;
    border-bottom: 1px dotted #cbd5e1;
    padding-bottom: 1px;
    margin-bottom: 2px;
    text-decoration: none;
    color: inherit;
  }}
  a.toc-item:hover {{
    color: #0284c7;
  }}
  a.toc-item:hover .toc-ch, a.toc-item:hover .toc-sec, a.toc-item:hover .toc-subsec {{
    color: #0284c7;
  }}
  .toc-ch {{
    font-weight: bold;
    color: #0f172a;
  }}
  .toc-sec {{
    padding-left: 14px;
    color: #334155;
  }}
  .toc-subsec {{
    padding-left: 28px;
    color: #64748b;
    font-size: 8.8pt;
  }}

  .page-break {{
    page-break-before: always;
  }}
</style>
</head>
<body>

<!-- ========================================== -->
<!-- TRANG BÌA (KHUNG VIỀN ĐÔI & LOGO UET)       -->
<!-- ========================================== -->
<div class="cover-frame-outer">
  <div class="cover-frame-inner">
    <div class="cover-header-box">
      <div class="cover-univ">ĐẠI HỌC QUỐC GIA HÀ NỘI</div>
      <div class="cover-subuniv">TRƯỜNG ĐẠI HỌC CÔNG NGHỆ</div>
      <div class="cover-divider"></div>
    </div>

    <div class="cover-logo-box">
      <img class="cover-logo-img" src="data:image/png;base64,{logo_b64}" alt="Logo UET" />
    </div>

    <div class="cover-title-box">
      <div class="cover-report-type">BÁO CÁO CUỐI KỲ</div>
      <div class="cover-course">MÔN HỌC: ĐIỆN TOÁN ĐÁM MÂY</div>
      <div class="cover-project-label">ĐỀ TÀI</div>
      <div class="cover-project-title">
        HỆ THỐNG ĐÓNG DẤU BẢN QUYỀN VÀ QUẢN TRỊ<br>
        TÀI LIỆU SỐ TRỰC TUYẾN HÀNG LOẠT TRÊN AWS
      </div>
      <div class="cover-project-subtitle">
        (Dynamic PDF Watermarking &amp; Digital Document Management Web Platform on AWS)
      </div>
    </div>

    <div class="cover-meta">
      <table style="width: 96%; margin: 0 auto; border-collapse: collapse; text-align: left;">
        <tr>
          <td style="width: 32%; font-weight: bold; color: #0f172a; white-space: nowrap;">Giảng viên hướng dẫn:</td>
          <td style="width: 68%; font-weight: bold; color: #0f172a;">ThS. Nguyễn Xuân Trường</td>
        </tr>
        <tr>
          <td style="font-weight: bold; color: #0f172a; vertical-align: top; white-space: nowrap;">Sinh viên thực hiện:</td>
          <td>
            <table style="width: 100%; border-collapse: collapse; text-align: left;">
              <tr>
                <td style="padding: 2px 0; width: 62%;"><b>Trần Nhật Hưng</b> (Trưởng nhóm)</td>
                <td style="padding: 2px 0; width: 38%; color: #334155; white-space: nowrap;">- MSV: <b>24021507</b></td>
              </tr>
              <tr>
                <td style="padding: 2px 0;"><b>Nguyễn Nam Khánh</b></td>
                <td style="padding: 2px 0; color: #334155; white-space: nowrap;">- MSV: <b>24021531</b></td>
              </tr>
              <tr>
                <td style="padding: 2px 0;"><b>Đỗ Lê Duy</b></td>
                <td style="padding: 2px 0; color: #334155; white-space: nowrap;">- MSV: <b>24021445</b></td>
              </tr>
            </table>
          </td>
        </tr>
        <tr>
          <td style="font-weight: bold; color: #0f172a;">Lớp môn học:</td>
          <td>INT3319 3</td>
        </tr>
        <tr>
          <td style="font-weight: bold; color: #0f172a;">Học kỳ &amp; Năm học:</td>
          <td>Học kỳ I – Năm học 2026 - 2027</td>
        </tr>
        <tr>
          <td style="font-weight: bold; color: #0f172a;">Địa chỉ ALB:</td>
          <td style="font-family: monospace; font-size: 8.5pt; color: #b91c1c;">
            http://PDF-Watermark-ALB-281030112.ap-southeast-1.elb.amazonaws.com
          </td>
        </tr>
      </table>
    </div>

    <div class="cover-footer">
      HÀ NỘI, THÁNG 11/2026
    </div>
  </div>
</div>

<!-- ========================================== -->
<!-- MỤC LỤC                                     -->
<!-- ========================================== -->
<div class="page-break"></div>
<h1 class="chapter-title" style="page-break-before: avoid; margin-top: 10pt;">MỤC LỤC BÁO CÁO</h1>

<div class="toc">
  <a href="#ch-1" class="toc-item"><span class="toc-ch">1. TỔNG QUAN VỀ DỰ ÁN</span><span>3</span></a>
  <a href="#sec-1-1" class="toc-item"><span class="toc-sec">1.1. Giới thiệu chung và Bài toán thực tiễn</span><span>3</span></a>
  <a href="#sec-1-2" class="toc-item"><span class="toc-sec">1.2. Đối tượng sử dụng và Hệ sinh thái tích hợp</span><span>3</span></a>
  <a href="#sec-1-3" class="toc-item"><span class="toc-sec">1.3. Lý do bắt buộc sử dụng Điện toán đám mây &amp; Tính đàn hồi</span><span>4</span></a>
  <a href="#sec-1-4" class="toc-item"><span class="toc-sec">1.4. Các dịch vụ AWS cốt lõi được sử dụng trong dự án</span><span>5</span></a>
  <a href="#subsec-1-4-1" class="toc-item"><span class="toc-subsec">1.4.1. Nhóm Tính toán và Cân bằng tải (EC2, ALB, ASG)</span><span>5</span></a>
  <a href="#subsec-1-4-2" class="toc-item"><span class="toc-subsec">1.4.2. Nhóm Lưu trữ đa tầng (S3, EFS, EBS)</span><span>5</span></a>
  <a href="#subsec-1-4-3" class="toc-item"><span class="toc-subsec">1.4.3. Nhóm Cơ sở dữ liệu và Giám sát (RDS PostgreSQL, CloudWatch, SNS)</span><span>5</span></a>
  <a href="#subsec-1-4-4" class="toc-item"><span class="toc-subsec">1.4.4. Nhóm Mạng và Bảo mật (VPC Multi-AZ, Security Groups, IAM Roles)</span><span>6</span></a>

  <a href="#ch-2" class="toc-item" style="margin-top: 6px;"><span class="toc-ch">2. GIẢI PHÁP THỰC HIỆN</span><span>7</span></a>
  <a href="#sec-2-1" class="toc-item"><span class="toc-sec">2.1. Kiến trúc tính năng và 5 Phân hệ Web Studio Trực quan</span><span>7</span></a>
  <a href="#sec-2-2" class="toc-item"><span class="toc-sec">2.2. Kiến trúc triển khai hạ tầng trên AWS (Tiered Architecture)</span><span>7</span></a>
  <a href="#subsec-2-2-1" class="toc-item"><span class="toc-subsec">2.2.1. Sơ đồ kiến trúc triển khai hệ thống tổng thể</span><span>8</span></a>
  <a href="#subsec-2-2-2" class="toc-item"><span class="toc-subsec">2.2.2. Luồng xử lý chi tiết theo vòng đời yêu cầu (Request Lifecycle)</span><span>9</span></a>
  <a href="#sec-2-3" class="toc-item"><span class="toc-sec">2.3. Đặc tả chi tiết kỹ thuật trong giải pháp</span><span>9</span></a>
  <a href="#subsec-2-3-1" class="toc-item"><span class="toc-subsec">2.3.1. Đặc tả cấu hình Mạng VPC và Cân bằng tải ALB</span><span>9</span></a>
  <a href="#subsec-2-3-2" class="toc-item"><span class="toc-subsec">2.3.2. Giao diện và giao thức tương tác giữa các thành phần</span><span>10</span></a>
  <a href="#subsec-2-3-3" class="toc-item"><span class="toc-subsec">2.3.3. Mô hình Lưu trữ đa tầng tối ưu (EBS vs EFS vs S3)</span><span>10</span></a>
  <a href="#subsec-2-3-4" class="toc-item"><span class="toc-subsec">2.3.4. Thiết kế Cơ sở dữ liệu kiểm toán (RDS PostgreSQL Schema)</span><span>11</span></a>
  <a href="#subsec-2-3-5" class="toc-item"><span class="toc-subsec">2.3.5. Cơ chế phân quyền IAM và Tường lửa Security Groups</span><span>11</span></a>
  <a href="#subsec-2-3-6" class="toc-item"><span class="toc-subsec">2.3.6. Cơ chế Tự động mở rộng (Fast Auto-Scaling) và Cảnh báo</span><span>12</span></a>
  <a href="#subsec-2-3-7" class="toc-item"><span class="toc-subsec">2.3.7. Đặc tả RESTful API: Endpoint đóng dấu tài liệu (POST /api/v1/watermark)</span><span>12</span></a>
  <a href="#subsec-2-3-8" class="toc-item"><span class="toc-subsec">2.3.8. Đặc tả RESTful API: Endpoint tra cứu và kiểm định (GET /api/v1/audit-logs/verify)</span><span>13</span></a>

  <a href="#ch-3" class="toc-item" style="margin-top: 6px;"><span class="toc-ch">3. KẾT QUẢ THỰC HIỆN VÀ ĐÁNH GIÁ THỰC NGHIỆM</span><span>15</span></a>
  <a href="#sec-3-1" class="toc-item"><span class="toc-sec">3.1. Các bước triển khai thực tế trên AWS (Deployment Steps)</span><span>15</span></a>
  <a href="#sec-3-2" class="toc-item"><span class="toc-sec">3.2. Bảng đối chiếu và Nghiệm thu 8 hạng mục bắt buộc</span><span>15</span></a>
  <a href="#sec-3-3" class="toc-item"><span class="toc-sec">3.3. Nghiệm thu chức năng đóng dấu, mã băm SHA-256 và lưu trữ</span><span>17</span></a>
  <a href="#sec-3-4" class="toc-item"><span class="toc-sec">3.4. Nghiệm thu kiểm thử chịu tải (Load Testing) và Auto Scaling</span><span>17</span></a>
  <a href="#subsec-3-4-1" class="toc-item"><span class="toc-subsec">3.4.1. Kịch bản kiểm thử tải đa luồng mô phỏng thực tế</span><span>17</span></a>
  <a href="#subsec-3-4-2" class="toc-item"><span class="toc-subsec">3.4.2. Kết quả phân bổ lưu lượng và kích hoạt Auto Scaling</span><span>18</span></a>
  <a href="#subsec-3-4-3" class="toc-item"><span class="toc-subsec">3.4.3. Đánh giá thông số hiệu năng (Throughput, Latency, SLA)</span><span>18</span></a>
  <a href="#sec-3-5" class="toc-item"><span class="toc-sec">3.5. Phân tích chi phí vận hành và Tối ưu hóa FinOps</span><span>19</span></a>
  <a href="#sec-3-6" class="toc-item"><span class="toc-sec">3.6. Vai trò và tỷ lệ đóng góp của các thành viên</span><span>22</span></a>
  <a href="#sec-3-7" class="toc-item"><span class="toc-sec">3.7. Kịch bản DEMO 10 phút cho Giảng viên</span><span>23</span></a>
  <a href="#sec-3-8" class="toc-item"><span class="toc-sec">3.8. Liên kết mã nguồn và sản phẩm bàn giao</span><span>23</span></a>
</div>

<!-- ========================================== -->
<!-- CHƯƠNG 1                                    -->
<!-- ========================================== -->
<h1 id="ch-1" class="chapter-title">1. TỔNG QUAN VỀ DỰ ÁN</h1>

<h2 id="sec-1-1" class="section-title">1.1. Giới thiệu chung và Bài toán thực tiễn</h2>
<p>
Trong kỷ nguyên chuyển đổi số giáo dục và tự động hóa quy trình nghiệp vụ doanh nghiệp, các tài liệu định dạng PDF đóng vai trò là phương tiện lưu chuyển văn bản, đề thi, bảng điểm, giáo trình và tài liệu tài chính phổ biến nhất. Tuy nhiên, thách thức lớn nhất mà các tổ chức đang phải đối mặt chính là <b>nguy cơ rò rỉ dữ liệu mật, phát tán trái phép tài liệu có bản quyền và gian lận đề thi</b> thông qua các kênh trao đổi trực tuyến.
</p>
<p>
Các phương pháp bảo vệ truyền thống như đặt mật khẩu mở file (Password Protection) hoặc mã hóa tĩnh thường mang lại trải nghiệm người dùng kém, đồng thời hoàn toàn bất lực trước hành vi chụp ảnh màn hình hoặc phát tán tài liệu sau khi đã mở khóa. Để giải quyết triệt để vấn đề này, giải pháp tối ưu là <b>cá nhân hóa động (Dynamic Watermarking)</b>: tự động chèn thông tin định danh của chính người tải (Họ tên, Mã sinh viên/Mã nhân viên, Mã giao dịch, Dấu thời gian chính xác tới từng giây và Mã băm kiểm định SHA-256) chéo lên toàn bộ các trang của tệp PDF ngay tại thời điểm yêu cầu được gửi tới máy chủ.
</p>
<p>
Việc xuất hiện watermark cá nhân hóa rõ nét tạo nên rào cản tâm lý cực kỳ mạnh mẽ chống phát tán trái phép. Hơn thế nữa, mã băm <b>SHA-256</b> được tính toán độc lập và lưu vào cơ sở dữ liệu kiểm toán (Audit Logs) đảm bảo tính <b>chống chối bỏ (Non-Repudiation)</b> và <b>toàn vẹn dữ liệu (Integrity)</b>: bất kỳ sự can thiệp, chỉnh sửa hay tẩy xóa chữ số nào trên tài liệu đều bị phát hiện ngay lập tức khi tra cứu trên hệ thống.
</p>

<h2 id="sec-1-2" class="section-title">1.2. Đối tượng sử dụng và Hệ sinh thái tích hợp</h2>
<p>
Hệ thống được thiết kế theo mô hình <b>Nền tảng Ứng dụng Web trực tuyến (Web Application Platform)</b> với giao diện đồ họa tương tác trực tiếp cho người dùng cuối, đồng thời cung cấp giao thức chuẩn hóa qua <b>RESTful JSON API</b> (<code>POST /api/v1/watermark</code>). Hệ thống hướng tới 05 nhóm đối tượng thực tế:
</p>
<ul>
  <li><b>Khối Khảo thí &amp; Đào tạo Đại học (EdTech / LMS / Online Exams):</b> Tự động đóng dấu mã sinh viên, ca thi, mã đề thi lên đề thi trực tuyến của hàng nghìn sinh viên cùng một lúc ngay trước giờ thi, ngăn chặn tuyệt đối tình trạng rò rỉ đề thi ra ngoài.</li>
  <li><b>Khối Tài chính - Ngân hàng - Fintech (Core Banking, Billing System):</b> Tự động đóng dấu bản sao kê giao dịch ngân hàng, phiếu thu, hóa đơn điện tử đỏ gắn mã khách hàng và con dấu số điện tử bảo mật.</li>
  <li><b>Khối Quản trị Doanh nghiệp (ERP, HRM, CRM):</b> Xuất bảng lương bảo mật (Payslip), quyết định bổ nhiệm, hợp đồng kinh tế nội bộ, đảm bảo thông tin nhân sự và báo giá nhạy cảm không bị chia sẻ ra bên ngoài.</li>
  <li><b>Khối Y tế &amp; Bảo hiểm số (Hospital Information System - HIS, InsurTech):</b> Xuất kết quả xét nghiệm bệnh lý, hồ sơ bệnh án, chứng từ bồi thường bảo hiểm bảo mật thông tin cá nhân của bệnh nhân theo chuẩn an toàn thông tin y tế.</li>
  <li><b>Bên thứ ba thẩm định và cơ quan kiểm định (Audit &amp; Legal):</b> Sử dụng cổng tra cứu Web Portal công khai để đối chiếu mã SHA-256 của file PDF nghi vấn với nhật ký cấp phát bất biến lưu trong cơ sở dữ liệu.</li>
</ul>

<h2 id="sec-1-3" class="section-title">1.3. Lý do bắt buộc sử dụng Điện toán đám mây &amp; Tính đàn hồi</h2>
<p>
Bài toán xử lý đóng dấu PDF hàng loạt sở hữu những đặc thù kỹ thuật rất khắt khe, khiến việc triển khai trên máy chủ vật lý truyền thống (On-Premises) hoặc một máy ảo đơn lẻ bộc lộ nhiều hạn chế nghiêm trọng:
</p>
<ol>
  <li><b>Tác vụ tiêu tốn tài nguyên tính toán cực lớn (Compute-Intensive Task):</b> Khác với các ứng dụng web CRUD thông thường (chủ yếu là chờ I/O mạng hoặc truy vấn database), quy trình đóng dấu PDF đòi hỏi: giải mã nhị phân cấu trúc tệp PDF, tính toán ma trận tọa độ xoay chữ 45°, vẽ đồ họa vector Unicode tiếng Việt lên từng trang, nén tối ưu hóa kích thước tệp và băm mật mã học SHA-256. Thực nghiệm cho thấy, đóng dấu một tài liệu 47 trang (như file kiểm thử <code>ModelOptimization.pdf</code>) chiếm dụng gần <b>100% công suất của 1 vCPU trong 0.6 – 1.2 giây</b>.</li>
  <li><b>Đặc thù lưu lượng mang tính đột biến cực cao (Spike Traffic / Flash Crowds):</b> Trong thực tế, lưu lượng truy cập không phân bổ đều mà dồn dập vào những mốc thời gian cố định: Đúng 08h00 khi hệ thống khảo thí mở đề thi cho 5.000 sinh viên, hoặc 11h30 ngày 25 hàng tháng khi hệ thống nhân sự đồng loạt gửi thông báo nhận bảng lương. Khi đó, hàng nghìn request đổ về trong vòng 2-3 phút. Nếu chỉ dùng 1 máy chủ, hàng đợi sẽ tắc nghẽn lập tức, CPU đạt 100%, gây lỗi <i>Gateway Timeout (504)</i> hoặc sập máy chủ do cạn RAM (OOM Killer).</li>
  <li><b>Yêu cầu tính đàn hồi (Elasticity) và Tối ưu chi phí (FinOps):</b> Để chịu tải được lưu lượng đỉnh (Peak Load), nếu mua máy chủ vật lý cỡ lớn cấu hình 32 vCPU, 64GB RAM để duy trì 24/7 thì 95% thời gian còn lại hệ thống sẽ ở trạng thái nhàn rỗi (CPU &lt; 3%), gây lãng phí ngân sách rất lớn. <b>Điện toán đám mây AWS với cơ chế Auto Scaling</b> cho phép giải quyết triệt để mâu thuẫn này: bình thường chỉ duy trì 2 máy chủ nhỏ (<code>t3.small</code>) để trực chiến; khi tải tăng đột biến, hệ thống <b>tự động mở rộng (Scale Out) lên 4 – 6 máy chủ trong vài phút</b>, và tự động thu hồi (Scale In) khi hết tải. Cơ chế này giúp <b>tiết kiệm hơn 80% chi phí vận hành hạ tầng</b>.</li>
  <li><b>Độ sẵn sàng cao (High Availability - Multi-AZ):</b> Bằng cách triển khai cụm máy chủ trên 2 Vùng sẵn sàng độc lập (Availability Zones: <code>ap-southeast-1a</code> và <code>ap-southeast-1b</code>) đứng sau Application Load Balancer, nếu một trung tâm dữ liệu của AWS gặp sự cố, hệ thống vẫn duy trì hoạt động 100% không gián đoạn.</li>
</ol>

<h2 id="sec-1-4" class="section-title">1.4. Các dịch vụ AWS cốt lõi được sử dụng trong dự án</h2>
<p>
Để xây dựng một đường ống xử lý vững chắc, hệ thống đã ứng dụng đồng bộ 10 dịch vụ đám mây then chốt của Amazon Web Services:
</p>

<h3 id="subsec-1-4-1" class="subsection-title">1.4.1. Nhóm Tính toán và Cân bằng tải</h3>
<ul>
  <li><b>Amazon EC2 (Elastic Compute Cloud):</b> Đóng vai trò các Worker thực thi ứng dụng xử lý đóng dấu PDF (FastAPI + PyMuPDF). Các máy ảo được đặt hoàn toàn trong Private Subnet để đảm bảo an toàn, sử dụng loại instance <code>t3.small</code> (2 vCPU, 2GB RAM).</li>
  <li><b>Application Load Balancer (ALB):</b> Cân bằng tải tầng ứng dụng (Layer 7), tiếp nhận lưu lượng HTTP công khai từ Internet trên cổng 80, thực hiện kiểm tra sức khỏe (Health Check) liên tục trên endpoint <code>/health</code> và phân phối lưu lượng đều theo thuật toán Round-Robin tới các EC2 Worker.</li>
  <li><b>Auto Scaling Group (ASG):</b> Quản lý vòng đời cụm máy chủ EC2 với quy mô tối thiểu 2 máy, tối đa 4 máy. ASG tự động phát hiện máy lỗi để thay thế (Self-Healing) và tự động tăng giảm số lượng máy chủ dựa trên tín hiệu giám sát CPU từ CloudWatch.</li>
</ul>

<h3 id="subsec-1-4-2" class="subsection-title">1.4.2. Nhóm Lưu trữ đa tầng (Multi-Tier Storage)</h3>
<ul>
  <li><b>Amazon S3 (Simple Storage Service):</b> Lưu trữ đối tượng (Object Storage) chuẩn hóa, chứa các tệp PDF gốc (<code>input/</code>), các tệp PDF sau khi đóng dấu hoàn thiện (<code>output/</code>) và mã nguồn nạp tự động (<code>code/</code>). S3 cung cấp tính năng <b>Pre-signed URL</b> cho phép người dùng tải tệp trực tiếp và <b>Lifecycle Rules</b> tự hủy tệp tạm sau 24 giờ.</li>
  <li><b>Amazon EFS (Elastic File System):</b> Hệ thống tệp mạng chia sẻ chuẩn POSIX qua giao thức NFSv4, được gắn kết đồng thời vào tất cả các máy EC2 tại thư mục <code>/mnt/efs</code>. EFS đóng vai trò là kho lưu trữ bộ nhớ đệm (Cache) chứa tệp PDF gốc và các phông chữ Unicode tiếng Việt, giúp giảm độ trễ truy xuất từ 200ms (nếu tải từ S3) xuống <b>dưới 5ms</b>.</li>
  <li><b>Amazon EBS (Elastic Block Store):</b> Ổ cứng khối (Block Storage) loại <code>gp3</code> dung lượng 20GB gắn trực tiếp trên mỗi máy EC2, cung cấp hiệu năng IOPS cao để chứa hệ điều hành Ubuntu Linux và làm không gian làm việc đệm (working directory) tại <code>/tmp</code>.</li>
</ul>

<h3 id="subsec-1-4-3" class="subsection-title">1.4.3. Nhóm Cơ sở dữ liệu và Giám sát</h3>
<ul>
  <li><b>Amazon RDS for PostgreSQL:</b> Dịch vụ cơ sở dữ liệu quan hệ được quản trị toàn diện, vận hành phiên bản PostgreSQL 18.3 trên instance <code>db.t4g.micro</code> đặt trong Private Subnet. RDS chịu trách nhiệm lưu trữ nhật ký kiểm toán (Audit Logs), truy vết mã băm SHA-256, định danh máy chủ xử lý và thời gian cấp phát.</li>
  <li><b>Amazon CloudWatch:</b> Giám sát các chỉ số hiệu năng theo thời gian thực (CPUUtilization, NetworkIn/Out, ALB TargetResponseTime) với chu kỳ 60 giây. Thiết lập CloudWatch Alarm kích hoạt khi CPU trung bình cụm &ge; 50%.</li>
  <li><b>Amazon SNS (Simple Notification Service):</b> Dịch vụ thông báo dạng Publish/Subscribe, tự động gửi email cảnh báo tức thì cho đội ngũ vận hành khi hệ thống kích hoạt chế độ mở rộng tải khẩn cấp.</li>
</ul>

<h3 id="subsec-1-4-4" class="subsection-title">1.4.4. Nhóm Mạng và Bảo mật</h3>
<ul>
  <li><b>Amazon VPC (Virtual Private Cloud):</b> Thiết kế mạng riêng cô lập với dải mạng <code>10.0.0.0/16</code>, chia thành 2 Public Subnets và 2 Private Subnets trải rộng trên 2 Vùng sẵn sàng (Multi-AZ).</li>
  <li><b>Internet Gateway &amp; NAT Gateway:</b> Internet Gateway kết nối Public Subnet với mạng toàn cầu; NAT Gateway cho phép các máy chủ trong Private Subnet kết nối ra Internet một chiều an toàn để tải bản vá và liên lạc với API S3.</li>
  <li><b>Security Groups &amp; IAM Roles:</b> Áp dụng mô hình phòng thủ theo chiều sâu (Defense in Depth) và nguyên tắc đặc quyền tối thiểu (Least Privilege). Các máy chủ EC2 sử dụng IAM Role để truy cập S3/CloudWatch mà không cần lưu cứng bất kỳ Access Key nào trong mã nguồn.</li>
</ul>

<!-- ========================================== -->
<!-- CHƯƠNG 2                                    -->
<!-- ========================================== -->
<h1 id="ch-2" class="chapter-title">2. GIẢI PHÁP THỰC HIỆN</h1>

<h2 id="sec-2-1" class="section-title">2.1. Kiến trúc tính năng và 5 Phân hệ Web Studio Trực quan</h2>
<p>
Hệ thống <b>Dynamic PDF Watermarking Pipeline</b> được xây dựng dưới dạng một <b>Nền tảng Ứng dụng Web trực tuyến toàn diện (Full-stack Web Platform)</b> dựa trên nền tảng <b>FastAPI</b> và thư viện đồ họa vector cấp thấp <b>PyMuPDF (fitz)</b>. Kiến trúc tính năng được chuẩn hóa qua 05 phân hệ giao diện Web Studio trực quan:
</p>

<div class="callout callout-success">
  <div class="callout-title">05 Phân hệ tính năng cốt lõi trên Nền tảng Web Đóng dấu Trực tuyến</div>
  <ul>
    <li><b>1. Kho Lưu Trữ Tài Liệu Gốc (Master Document Library):</b> Cho phép tải lên tệp PDF gốc lưu trữ bền vững trên S3 và đồng bộ cache tức thì vào EFS (<code>/mnt/efs/input/</code>). Quản lý danh mục, xem trước trang đầu, phân loại và xóa tài liệu tập trung.</li>
    <li><b>2. Phòng Đóng Dấu Đơn Lẻ (Single Live Studio &amp; Canvas Preview):</b> Tùy biến dấu chìm xoay 45°, độ mờ, font tiếng Việt, tiêu đề Header/Footer và con dấu số. Tích hợp công nghệ <i>HTML5 Canvas Preview</i> xem trước trang in thời gian thực trước khi xuất bản.</li>
    <li><b>3. Phòng Đóng Dấu Hàng Loạt &amp; Nén ZIP Đa Luồng (Batch Studio):</b> Hỗ trợ nạp danh sách đối tượng qua tệp CSV/Excel hoặc form đa dòng, xử lý song song đa luồng (<code>ThreadPoolExecutor</code>), tự động xuất kèm bảng kê <code>kiem_dinh_manifest.csv</code> (chứa mã SHA-256 từng bản) và nén thành tệp ZIP tải về một chạm qua S3 Pre-signed URL.</li>
    <li><b>4. Cổng Kiểm Định Tính Toàn Vẹn Số (Public SHA-256 Verifier):</b> Cho phép kéo thả tệp PDF cần xác thực. Trình duyệt tính toán mã băm SHA-256 bằng <i>Web Crypto API</i> trong &lt;20ms không cần upload file, đối soát tức thì với RDS PostgreSQL.</li>
    <li><b>5. Nhật Ký Kiểm Toán Phân Tán (RDS PostgreSQL Audit Log Viewer):</b> Giám sát toàn bộ phiên đóng dấu trên các Worker node, tra cứu mã SHA-256, định danh host và mốc thời gian GMT+7.</li>
  </ul>
</div>

<h2 id="sec-2-2" class="section-title">2.2. Kiến trúc triển khai hạ tầng trên AWS (Tiered Architecture)</h2>
<p>
Hạ tầng hệ thống được triển khai tại Region <b>Singapore (<code>ap-southeast-1</code>)</b>, tuân thủ nghiêm ngặt Khung kiến trúc chuẩn của AWS (AWS Well-Architected Framework): phân tách ranh giới an toàn tuyệt đối giữa vùng mạng Internet công cộng và vùng máy chủ xử lý dữ liệu nội bộ.
</p>

<h3 id="subsec-2-2-1" class="subsection-title">2.2.1. Sơ đồ kiến trúc triển khai hệ thống tổng thể</h3>
<div class="figure-box">
  {svg_architecture}
  <div class="figure-caption">Hình 1. Sơ đồ kiến trúc triển khai phân tầng chuẩn Multi-AZ của Dynamic PDF Watermarking Pipeline trên AWS</div>
</div>

<h3 id="subsec-2-2-2" class="subsection-title">2.2.2. Luồng xử lý chi tiết theo vòng đời yêu cầu (Request Lifecycle)</h3>
<p>
Mọi yêu cầu xử lý từ phía người dùng hoặc các hệ thống nghiệp vụ tích hợp đều tuân theo chu trình khép kín 08 bước được tối ưu hóa độ trễ:
</p>

<div class="figure-box">
  {svg_sequence}
  <div class="figure-caption">Hình 2. Sơ đồ tuần tự thể hiện chi tiết vòng đời xử lý yêu cầu (Request Lifecycle) qua 8 bước</div>
</div>

<table class="report-table">
  <thead>
    <tr>
      <th style="width: 8%;">Bước</th>
      <th style="width: 25%;">Thành phần tương tác</th>
      <th>Mô tả hành vi xử lý chi tiết</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="text-align: center; font-weight: bold;">1</td>
      <td><b>Client &rarr; ALB</b></td>
      <td>Client gửi yêu cầu <code>POST /api/v1/watermark</code> kèm JSON chứa mã tài liệu cần đóng dấu, thông tin định danh và tùy chọn định dạng.</td>
    </tr>
    <tr>
      <td style="text-align: center; font-weight: bold;">2</td>
      <td><b>ALB &rarr; EC2 Worker</b></td>
      <td>ALB thực hiện thuật toán Round-Robin, định tuyến request vào cổng 8000 của một máy EC2 Worker đang ở trạng thái Healthy trong Private Subnet.</td>
    </tr>
    <tr>
      <td style="text-align: center; font-weight: bold;">3</td>
      <td><b>EC2 &harr; EFS Storage</b></td>
      <td>Worker kiểm tra tệp mẫu và font chữ Unicode tại thư mục mount <code>/mnt/efs/input/</code>. Do file đã được cache sẵn trên NFSv4, dữ liệu được đọc ngay lập tức (&lt;5ms).</td>
    </tr>
    <tr>
      <td style="text-align: center; font-weight: bold;">4</td>
      <td><b>EC2 Processing Engine</b></td>
      <td>FastAPI gọi PyMuPDF tính toán tâm trang $(c_x, c_y)$, vẽ chữ chéo xoay 45°, in tiêu đề, vẽ con dấu và tính toán mã băm SHA-256 trên bộ nhớ RAM.</td>
    </tr>
    <tr>
      <td style="text-align: center; font-weight: bold;">5</td>
      <td><b>EC2 &rarr; RDS PostgreSQL</b></td>
      <td>Worker ghi nhận một bản ghi kiểm toán mới vào bảng <code>audit_logs</code> (lưu <code>request_id</code>, <code>sha256</code>, <code>worker_host</code>, thời gian GMT+7).</td>
    </tr>
    <tr>
      <td style="text-align: center; font-weight: bold;">6</td>
      <td><b>EC2 &rarr; Amazon S3</b></td>
      <td>Worker đẩy tệp PDF hoàn thiện lên S3 bucket <code>output/</code> và sinh đường dẫn an toàn có thời hạn <b>S3 Pre-signed URL</b> (hết hạn sau 15 phút).</td>
    </tr>
    <tr>
      <td style="text-align: center; font-weight: bold;">7</td>
      <td><b>EC2 &rarr; ALB &rarr; Client</b></td>
      <td>Worker phản hồi mã HTTP 200 OK kèm payload JSON chứa mã băm SHA-256, thời gian xử lý (ms), IP của máy chủ thực hiện và đường dẫn tải file.</td>
    </tr>
    <tr>
      <td style="text-align: center; font-weight: bold;">8</td>
      <td><b>Client &rarr; Amazon S3</b></td>
      <td>Người dùng nhấn đường dẫn tải trực tiếp từ Amazon S3. Băng thông truyền tệp PDF không đi qua EC2 hay ALB, loại trừ triệt để nghẽn cổ chai.</td>
    </tr>
  </tbody>
</table>

<h2 id="sec-2-3" class="section-title">2.3. Đặc tả chi tiết kỹ thuật trong giải pháp</h2>

<h3 id="subsec-2-3-1" class="subsection-title">2.3.1. Đặc tả cấu hình Mạng VPC và Cân bằng tải ALB</h3>
<p>
Hệ thống mạng VPC được thiết kế nhằm cô lập tối đa các thành phần máy chủ nghiệp vụ:
</p>
<ul>
  <li><b>VPC ID:</b> <code>vpc-0f629db08b2b22010</code> | CIDR: <code>10.0.0.0/16</code> (Singapore <code>ap-southeast-1</code>).</li>
  <li><b>Public Subnet 1A:</b> <code>subnet-0c3625ad0d39f7124</code> (<code>10.0.1.0/24</code>) trên Vùng <code>ap-southeast-1a</code>. Chứa ALB và NAT Gateway.</li>
  <li><b>Public Subnet 1B:</b> <code>subnet-095294e5965b2e6b8</code> (<code>10.0.2.0/24</code>) trên Vùng <code>ap-southeast-1b</code>. Chứa ALB.</li>
  <li><b>Private Subnet 1A:</b> <code>subnet-035a2be5653475b55</code> (<code>10.0.11.0/24</code> trên <code>ap-southeast-1a</code>) – Chứa EC2 Worker, EFS Mount Target (<code>10.0.11.197</code>) và RDS Subnet. Tắt Public IPv4.</li>
  <li><b>Private Subnet 1B:</b> <code>subnet-0d266de855b93ca59</code> (<code>10.0.12.0/24</code> trên <code>ap-southeast-1b</code>) – Chứa EC2 Worker, EFS Mount Target (<code>10.0.12.118</code>) và RDS Subnet.</li>
  <li><b>Cấu hình Bảng định tuyến (Route Tables):</b>
    <ul>
      <li><i>Public Route Table:</i> Điều hướng <code>0.0.0.0/0</code> trực tiếp tới Internet Gateway (IGW).</li>
      <li><i>Private Route Table:</i> Điều hướng <code>0.0.0.0/0</code> tới NAT Gateway để các máy chủ Private Subnet có thể kết nối Internet một chiều.</li>
    </ul>
  </li>
  <li><b>Application Load Balancer (ALB):</b>
    <ul>
      <li>Tên tài nguyên: <code>PDF-Watermark-ALB</code> (Scheme: Internet-Facing, Port: 80).</li>
      <li>Target Group: <code>PDF-Watermark-TG</code> (Port: 8000, Protocol: HTTP).</li>
      <li>Health Check Path: <code>/health</code>, Interval: 15s, Timeout: 5s, Healthy Threshold: 2, Unhealthy Threshold: 3.</li>
    </ul>
  </li>
</ul>

<h3 id="subsec-2-3-2" class="subsection-title">2.3.2. Giao diện và giao thức tương tác giữa các thành phần</h3>
<table class="report-table">
  <thead>
    <tr>
      <th>Thành phần Nguồn &rarr; Đích</th>
      <th>Giao thức</th>
      <th>Cổng</th>
      <th>Cơ chế Xác thực</th>
      <th>Dữ liệu Trao đổi</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Client &rarr; ALB</td>
      <td>HTTP / REST</td>
      <td>80 / TCP</td>
      <td>Public / API Key</td>
      <td>Payload JSON yêu cầu đóng dấu hoặc kiểm định</td>
    </tr>
    <tr>
      <td>ALB &rarr; EC2 Worker</td>
      <td>HTTP (Reverse Proxy)</td>
      <td>8000 / TCP</td>
      <td>ALB Security Group</td>
      <td>Chuyển tiếp HTTP Request và nhận JSON Response</td>
    </tr>
    <tr>
      <td>EC2 Worker &harr; Amazon EFS</td>
      <td>NFSv4</td>
      <td>2049 / TCP</td>
      <td>EFS Security Group</td>
      <td>Đọc phông chữ TTF và tệp PDF mẫu gốc (&lt;5ms)</td>
    </tr>
    <tr>
      <td>EC2 Worker &rarr; Amazon RDS</td>
      <td>PostgreSQL Protocol</td>
      <td>5432 / TCP</td>
      <td>Database Credentials</td>
      <td>Ghi log kiểm toán (audit_logs) và tra cứu SHA-256</td>
    </tr>
    <tr>
      <td>EC2 Worker &rarr; Amazon S3</td>
      <td>HTTPS (AWS SDK / Boto3)</td>
      <td>443 / TCP</td>
      <td>IAM Instance Profile</td>
      <td>Tải tệp PDF kết quả và sinh Pre-signed URL</td>
    </tr>
    <tr>
      <td>EC2 Worker &rarr; CloudWatch</td>
      <td>HTTPS</td>
      <td>443 / TCP</td>
      <td>IAM Instance Profile</td>
      <td>Gửi số liệu CPUUtilization chu kỳ 60 giây</td>
    </tr>
  </tbody>
</table>

<h3 id="subsec-2-3-3" class="subsection-title">2.3.3. Mô hình Lưu trữ đa tầng tối ưu (EBS vs EFS vs S3)</h3>
<p>
Nhóm đã kết hợp linh hoạt cả 03 công nghệ lưu trữ của AWS nhằm tối ưu hóa cả về <b>tốc độ thực thi (Performance)</b> lẫn <b>chi phí vận hành (Cost Optimization)</b>:
</p>
<ul>
  <li><b>Amazon S3 (Chi phí rẻ nhất - 0.025 USD/GB):</b> Phù hợp lưu trữ dữ liệu đối tượng tĩnh. Được dùng lưu các bản PDF đầu vào và đầu ra. Kết hợp cùng <b>S3 Lifecycle Policy</b> cấu hình tự động dọn dẹp các tệp trong thư mục <code>output/</code> sau 24 giờ, giúp dung lượng không bị phình to theo thời gian mà không cần viết script dọn dẹp.</li>
  <li><b>Amazon EFS (Kho tài liệu gốc Master Hub &amp; Tốc độ đọc chia sẻ cao nhất):</b> Đóng vai trò là bộ đệm tài liệu gốc và font Unicode dùng chung. Khi người dùng tải lên tài liệu gốc, tệp được lưu đệm trên EFS tại <code>/mnt/efs/input/</code>. Toàn bộ máy EC2 trong cụm đọc chung bản cache với độ trễ <b>chỉ từ 2 – 5ms</b>, cho phép tạo hàng trăm bản đóng dấu tức thời mà xóa bỏ hoàn toàn nhu cầu upload lại file qua mạng.</li>
  <li><b>Amazon EBS (gp3):</b> Ổ cứng hệ điều hành cục bộ cung cấp tốc độ đọc ghi IOPS độc lập, đảm bảo hiệu năng tối đa cho nhân Linux và vùng đệm xử lý file nhị phân tức thời tại <code>/tmp</code>.</li>
</ul>

<div class="callout" style="margin-top: 6px;">
  <div class="callout-title">Phân tích Kiến trúc: Tại sao bắt buộc dùng Amazon EFS làm Bộ đệm chung thay vì EBS cục bộ trên từng EC2?</div>
  <p style="margin-bottom: 4px;">
    Một bài toán kiến trúc then chốt được đặt ra: <i>"Tại sao không cho mỗi EC2 tự tải và lưu 1 bản cache từ S3 về ổ EBS cục bộ?"</i>. Phân tích thực tế cho thấy giải pháp cache trên EBS bộc lộ <b>03 vấn đề nghiêm trọng</b>:
  </p>
  <ol style="margin-bottom: 2px;">
    <li><b>Cache Miss &amp; Cold-start do ALB Round-Robin:</b> Khi Worker A tải cache về EBS của nó, request kế tiếp do ALB phân phối sang Worker B lại bị Cold-start vì Worker B chưa có file (mất 1-2s delay và tốn chi phí S3 GetObject).</li>
    <li><b>Bất đồng bộ dữ liệu &amp; Lỗi Flapping nguy hiểm:</b> Khi cập nhật hoặc xóa tài liệu gốc ở Master Hub, lệnh xóa chỉ tới 1 worker. Các worker còn lại vẫn giữ file cũ trên EBS, dẫn tới người dùng lúc nhận bản mới, lúc nhận bản cũ.</li>
    <li><b>Nhân bản dung lượng lưu trữ:</b> 4 máy EC2 trong cụm Auto Scaling sẽ nhân bản 4 lần dung lượng cache trên các ổ EBS riêng biệt.</li>
  </ol>
  <p style="margin-top: 4px; margin-bottom: 0;">
    &rArr; <b>Amazon EFS (NFSv4 ReadWriteMany)</b> giải quyết triệt để vấn đề: tạo <i>Single Source of Truth</i> duy nhất, toàn bộ cụm EC2 truy cập chung với độ trễ &lt;2-5ms, nhất quán dữ liệu 100% khi xóa hoặc cập nhật.
  </p>
</div>

<h3 id="subsec-2-3-4" class="subsection-title">2.3.4. Thiết kế Cơ sở dữ liệu kiểm toán (RDS PostgreSQL Schema)</h3>
<p>
Cơ sở dữ liệu Amazon RDS PostgreSQL 18.3 vận hành bảng <code>audit_logs</code> với cấu trúc chuẩn hóa cao nhằm phục vụ công tác tra cứu truy vết tức thời:
</p>
<pre><code>CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    request_id VARCHAR(64) NOT NULL,
    client_id VARCHAR(64) DEFAULT 'default',
    doc_name VARCHAR(255) NOT NULL,
    pages_count INTEGER DEFAULT 0,
    sha256 VARCHAR(64) NOT NULL,
    worker_host VARCHAR(100) NOT NULL,
    output_key VARCHAR(255),
    processing_time_ms FLOAT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    student_id VARCHAR(64),
    full_name VARCHAR(128),
    doc_code VARCHAR(128),
    metadata_json TEXT
);

-- Chỉ mục tối ưu hóa tốc độ tra cứu kiểm định &lt; 5ms:
CREATE INDEX idx_audit_logs_sha256 ON audit_logs(sha256);
CREATE INDEX idx_audit_logs_client ON audit_logs(client_id);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at DESC);</code></pre>

<p class="no-indent">
Để ngăn chặn nguy cơ cạn kiệt Connection Pool của cơ sở dữ liệu khi cụm Auto Scaling nhân bản lên nhiều máy chủ EC2, ứng dụng sử dụng cơ chế <b>SQLAlchemy QueuePool</b> với các tham số khắt khe: <code>pool_size=10</code>, <code>max_overflow=20</code>, <code>pool_recycle=1800</code> và <code>pool_pre_ping=True</code>.
</p>

<h3 id="subsec-2-3-5" class="subsection-title">2.3.5. Cơ chế phân quyền IAM và Tường lửa Security Groups</h3>
<p>
Kiến trúc an ninh áp dụng triệt để nguyên tắc <i>Least Privilege</i> và <i>Zero Trust nội bộ</i>:
</p>
<ul>
  <li><b>ALB Security Group (<code>sg-05bf5f5fa01c9d6fb</code>):</b> Chỉ mở Inbound cổng <code>80</code> từ toàn mạng (<code>0.0.0.0/0</code>).</li>
  <li><b>EC2 App Security Group (<code>sg-070c4c8b7de9b74f0</code>):</b> <b>Tuyệt đối không mở cổng ra Internet</b>. Chỉ chấp nhận Inbound cổng <code>8000</code> duy nhất nếu nguồn truyền đến xuất phát từ chính <i>ALB Security Group</i>. Cổng <code>22</code> (SSH) chỉ được mở có điều kiện khi bảo trì.</li>
  <li><b>RDS Security Group (<code>sg-054d3bb817a90456e</code>):</b> Chỉ chấp nhận Inbound cổng <code>5432</code> nếu nguồn xuất phát từ <i>EC2 App Security Group</i>.</li>
  <li><b>EFS Security Group (<code>sg-0a52b994de226485a</code>):</b> Chỉ chấp nhận Inbound cổng <code>2049</code> (NFS) từ <i>EC2 App Security Group</i>.</li>
  <li><b>IAM Instance Profile Role (<code>EC2-PDFWatermark-Role</code>):</b> Được gắn trực tiếp vào Launch Template của EC2. Cung cấp quyền tối thiểu: đọc/ghi đúng S3 bucket <code>uet-pdf-watermark</code> và đẩy log tới CloudWatch. <b>Tuyệt đối không lưu Access Key/Secret Key trong mã nguồn hay biến môi trường</b>.</li>
</ul>

<h3 id="subsec-2-3-6" class="subsection-title">2.3.6. Cơ chế Tự động mở rộng (Fast Auto-Scaling) và Cảnh báo</h3>
<p>
Để đáp ứng thời gian thực cho kịch bản demo và bảo vệ hệ thống trước các đợt bắn tải đột biến, chính sách Auto Scaling được tinh chỉnh đặc biệt:
</p>
<ul>
  <li><b>Quy mô cụm (Capacity):</b> Tối thiểu (Min) = 2; Mong muốn (Desired) = 2; Tối đa (Max) = 4 instances.</li>
  <li><b>Chính sách mở rộng nhanh (Step Scaling / Target Tracking):</b> Kích hoạt dựa trên CloudWatch Metric <code>CPUUtilization</code> của Auto Scaling Group. Khi CPU trung bình vượt ngưỡng <b>&ge; 50%</b> liên tục trong <b>60 giây (1 chu kỳ)</b>, hệ thống lập tức ra lệnh bổ sung thêm máy chủ.</li>
  <li><b>Thời gian nguội (Cooldown Period):</b> Thiết lập 180 giây để ngăn chặn tình trạng mở rộng quá mức liên tục (Flapping).</li>
  <li><b>Launch Template &amp; Golden AMI:</b> Sử dụng Launch Template <code>PDF-Watermark-LT</code> (v6) cùng Golden Custom AMI <code>ami-01bb6124e2207ab88</code> (<code>PDF-Watermark-Golden-AMI-v2</code>). Nhóm đã đóng gói toàn bộ hệ điều hành Ubuntu, thư viện Python, mã nguồn FastAPI và cấu hình NFS mount vào một Custom AMI. Nhờ đó, máy chủ EC2 mới khi được khởi tạo chỉ mất <b>35 – 45 giây</b> để sẵn sàng nhận tải từ ALB (nhanh hơn 4 lần so với việc cài đặt bằng User Data script thông thường).</li>
</ul>

<h3 id="subsec-2-3-7" class="subsection-title">2.3.7. Đặc tả RESTful API: Endpoint đóng dấu tài liệu (POST /api/v1/watermark)</h3>
<p>
Endpoint chính tiếp nhận yêu cầu đóng dấu tự động từ các hệ thống đối tác trong doanh nghiệp:
</p>

<pre><code>POST /api/v1/watermark HTTP/1.1
Host: PDF-Watermark-ALB-281030112.ap-southeast-1.elb.amazonaws.com
Content-Type: application/json

{{
  "client_id": "crm-service",
  "source": {{
    "doc_code": "ModelOptimization"
  }},
  "watermark": {{
    "diagonal_text": "HỢP ĐỒNG ĐỐI TÁC BẢO MẬT - TRẦN NHẬT HƯNG",
    "header_text": "Hợp đồng kinh tế | Mã tra cứu: CRM-99234 | Mật",
    "footer_text": "Tài liệu mật tổ chức - Nghiêm cấm sao chép dưới mọi hình thức",
    "stamp_text": "CONFIDENTIAL",
    "diagonal_opacity": 0.22,
    "diagonal_fontsize": 38
  }},
  "metadata": {{
    "transaction_id": "TX-20261123-001"
  }}
}}</code></pre>

<p class="no-indent">
<b>Phản hồi thành công (HTTP 200 OK):</b>
</p>
<pre><code>HTTP/1.1 200 OK
Content-Type: application/json

{{
  "request_id": "4ff982da-e4c9-4903-8286-cca11d75b581",
  "client_id": "crm-service",
  "worker_host": "ip-10-0-12-89",
  "doc_name": "ModelOptimization",
  "pages_count": 47,
  "sha256": "0c09f432d34192a86a7aeabc1e0e9c3bbdf03d4261cf2d7bf7021cc97064c21b",
  "download_url": "https://uet-pdf-watermark.s3.amazonaws.com/output/ModelOptimization_watermarked.pdf?AWSAccessKeyId=...&amp;Signature=...&amp;Expires=...",
  "processing_time_ms": 1185.42
}}</code></pre>

<h3 id="subsec-2-3-8" class="subsection-title">2.3.8. Đặc tả RESTful API: Endpoint tra cứu và kiểm định (GET /api/v1/audit-logs/verify)</h3>
<p>
Dành cho bên thứ ba, cơ quan quản lý hoặc người dùng cuối kiểm tra tính nguyên bản của file PDF:
</p>
<pre><code>GET /api/v1/audit-logs/verify/0c09f432d34192a86a7aeabc1e0e9c3bbdf03d4261cf2d7bf7021cc97064c21b HTTP/1.1
Host: PDF-Watermark-ALB-281030112.ap-southeast-1.elb.amazonaws.com

HTTP/1.1 200 OK
Content-Type: application/json

{{
  "verified": true,
  "sha256": "0c09f432d34192a86a7aeabc1e0e9c3bbdf03d4261cf2d7bf7021cc97064c21b",
  "document": {{
    "client_id": "crm-service",
    "doc_name": "ModelOptimization",
    "pages_count": 47,
    "created_at_vn": "2026-11-23 02:19:09",
    "worker_host": "ip-10-0-12-89"
  }},
  "message": "Tài liệu chính thống đã được xác thực tính toàn vẹn và nguồn gốc cấp phát."
}}</code></pre>

<!-- ========================================== -->
<!-- CHƯƠNG 3                                    -->
<!-- ========================================== -->
<h1 id="ch-3" class="chapter-title">3. KẾT QUẢ THỰC HIỆN VÀ ĐÁNH GIÁ THỰC NGHIỆM</h1>

<h2 id="sec-3-1" class="section-title">3.1. Các bước triển khai thực tế trên AWS (Deployment Steps)</h2>
<p>
Quá trình triển khai hạ tầng thực tế được thực hiện tuần tự và kiểm thử nghiêm ngặt trên tài khoản AWS cá nhân thuộc Region <code>ap-southeast-1</code> qua 06 giai đoạn:
</p>
<ol>
  <li><b>Giai đoạn 1 – Thiết lập Hạ tầng Mạng và Bảo mật nền tảng:</b> Khởi tạo VPC CIDR <code>10.0.0.0/16</code>; phân tách 2 Public Subnets và 2 Private Subnets trên 2 AZ (<code>1a</code> và <code>1b</code>); đính kèm Internet Gateway; tạo Elastic IP và triển khai NAT Gateway; cấu hình 2 Bảng định tuyến (Public RT trỏ IGW, Private RT trỏ NAT). Khởi tạo 4 nhóm Security Group với luật Inbound/Outbound phân tách.</li>
  <li><b>Giai đoạn 2 – Triển khai Tầng Lưu trữ &amp; Cơ sở dữ liệu:</b> Khởi tạo Amazon S3 bucket <code>uet-pdf-watermark</code> với chính sách chặn Public Access; cấu hình Lifecycle Rule hủy tệp sau 24h. Khởi tạo Amazon EFS với 2 Mount Target tại 2 Private Subnet. Khởi tạo Amazon RDS PostgreSQL 18.3 (<code>db.t4g.micro</code>) trong DB Subnet Group thuộc Private Subnet.</li>
  <li><b>Giai đoạn 3 – Đóng gói Ứng dụng &amp; Tạo Golden AMI:</b> Khởi tạo máy ảo EC2 tạm thời để cài đặt môi trường Python 3.12, PyMuPDF, Boto3, cấu hình mount tự động EFS vào <code>/etc/fstab</code>, nạp bộ font tiếng Việt chuẩn và tạo dịch vụ <code>systemd</code> tự chạy FastAPI trên cổng 8000 khi khởi động. Tiến hành tạo Golden AMI mang tên <code>PDF-Watermark-Worker-v2</code>.</li>
  <li><b>Giai đoạn 4 – Thiết lập Cân bằng tải và Tự động mở rộng:</b> Tạo Launch Template sử dụng Golden AMI và gắn IAM Role <code>EC2-PDFWatermark-Role</code>. Khởi tạo Application Load Balancer trên 2 Public Subnet kèm Target Group. Khởi tạo Auto Scaling Group với Min=2, Desired=2, Max=4, gắn vào Target Group của ALB.</li>
  <li><b>Giai đoạn 5 – Thiết lập Giám sát và Cảnh báo tự động:</b> Cấu hình CloudWatch Metric Alarm theo dõi CPU trung bình cụm ASG &ge; 50% trong 1 phút, gắn hành động Scale-Out (+1 instance) và gửi thông báo tới Topic Amazon SNS.</li>
  <li><b>Giai đoạn 6 – Kiểm thử nghiệm thu và Xây dựng kịch bản FinOps:</b> Thực hiện bắn tải đa luồng kiểm chứng, đối chiếu 8 hạng mục bắt buộc và viết tập lệnh tự động hóa <code>manage_aws.py</code> phục vụ bật/tắt toàn bộ hạ tầng về 0 USD/giờ.</li>
</ol>

<h2 id="sec-3-2" class="section-title">3.2. Bảng đối chiếu và Nghiệm thu 8 hạng mục bắt buộc</h2>
<p>
Dưới đây là bảng đối chiếu chi tiết kết quả thực hiện của dự án so với 08 hạng mục bắt buộc của học phần Điện toán đám mây (INT3319):
</p>

<table class="report-table">
  <thead>
    <tr>
      <th style="width: 5%;">STT</th>
      <th style="width: 20%;">Hạng mục Bắt buộc</th>
      <th style="width: 35%;">Thành phần Triển khai Thực tế</th>
      <th style="width: 30%;">Minh chứng &amp; Lệnh Kiểm chứng</th>
      <th style="width: 10%;">Đánh giá</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="text-align: center; font-weight: bold;">1</td>
      <td><b>Thiết kế mạng riêng</b></td>
      <td>VPC <code>10.0.0.0/16</code> chia làm 2 Public Subnets và 2 Private Subnets trên 2 AZ (<code>ap-southeast-1a</code> và <code>1b</code>). Có Internet Gateway và NAT Gateway.</td>
      <td>VPC Console xác nhận Route Table Public trỏ <code>0.0.0.0/0 &rarr; igw</code>; Route Table Private trỏ <code>0.0.0.0/0 &rarr; nat-gateway</code>.</td>
      <td style="text-align: center; font-weight: bold; color: #059669;">ĐẠT</td>
    </tr>
    <tr>
      <td style="text-align: center; font-weight: bold;">2</td>
      <td><b>Máy chủ riêng tư</b></td>
      <td>Cụm EC2 Worker nằm hoàn toàn trong Private Subnets (<code>10.0.11.0/24</code>, <code>10.0.12.0/24</code>). Tắt Auto-assign Public IPv4.</td>
      <td>EC2 Console hiển thị máy chủ không có Public IP. Chỉ nhận request từ ALB qua Inbound port 8000 được gán từ ALB SG.</td>
      <td style="text-align: center; font-weight: bold; color: #059669;">ĐẠT</td>
    </tr>
    <tr>
      <td style="text-align: center; font-weight: bold;">3</td>
      <td><b>Đa dạng lưu trữ</b></td>
      <td>Kết hợp cả 3 công nghệ: Amazon EBS (gp3 cho OS/tmp), Amazon EFS (NFSv4 chia sẻ font/PDF gốc) và Amazon S3 (Object Storage xuất file).</td>
      <td>Thực tế mount EFS tại <code>/mnt/efs</code>; S3 bucket <code>uet-pdf-watermark</code> có Lifecycle 24h và cấp S3 Pre-signed URL an toàn.</td>
      <td style="text-align: center; font-weight: bold; color: #059669;">ĐẠT</td>
    </tr>
    <tr>
      <td style="text-align: center; font-weight: bold;">4</td>
      <td><b>Cơ sở dữ liệu</b></td>
      <td>Amazon RDS for PostgreSQL 18.3 (<code>db.t4g.micro</code>) triển khai trong Private Subnet. Có cơ chế Connection Pooling.</td>
      <td>Bảng <code>audit_logs</code> lưu vết băm SHA-256, host và thời gian. DB SG chỉ chấp nhận Inbound port 5432 từ EC2 App SG.</td>
      <td style="text-align: center; font-weight: bold; color: #059669;">ĐẠT</td>
    </tr>
    <tr>
      <td style="text-align: center; font-weight: bold;">5</td>
      <td><b>Quản lý phân quyền</b></td>
      <td>IAM Role <code>EC2-PDFWatermark-Role</code> gắn vào Launch Template theo nguyên tắc Least Privilege (chỉ đọc/ghi đúng S3 bucket).</td>
      <td>Mã nguồn và môi trường không chứa bất kỳ Access Key nào. EC2 tự lấy credential tạm thời từ metadata service.</td>
      <td style="text-align: center; font-weight: bold; color: #059669;">ĐẠT</td>
    </tr>
    <tr>
      <td style="text-align: center; font-weight: bold;">6</td>
      <td><b>Cân bằng tải &amp; Auto Scaling</b></td>
      <td>Application Load Balancer (Port 80) kết hợp Auto Scaling Group (Min=2, Desired=2, Max=4) trải rộng trên 2 Private Subnets.</td>
      <td>ALB phân phối Round-Robin đều giữa các Worker. Bắn tải 28 luồng kích hoạt ASG tự sinh thêm EC2 Worker #3 và #4.</td>
      <td style="text-align: center; font-weight: bold; color: #059669;">ĐẠT</td>
    </tr>
    <tr>
      <td style="text-align: center; font-weight: bold;">7</td>
      <td><b>Giám sát &amp; Cảnh báo</b></td>
      <td>Amazon CloudWatch Metric Alarm theo dõi CPU &ge; 50% trong 60 giây kết hợp Topic thông báo Amazon SNS.</td>
      <td>Bắn tải làm CPU vượt 50%, CloudWatch Alarm chuyển sang trạng thái <code>ALARM</code> và gửi email cảnh báo tự động qua SNS.</td>
      <td style="text-align: center; font-weight: bold; color: #059669;">ĐẠT</td>
    </tr>
    <tr>
      <td style="text-align: center; font-weight: bold;">8</td>
      <td><b>Bảng tính chi phí</b></td>
      <td>Bảng phân tích chi phí chi tiết từng dịch vụ (EC2, ALB, NAT, EBS, EFS, S3, RDS, CW) tại Singapore, kèm giải pháp FinOps.</td>
      <td>Trình bày đầy đủ tại Mục 3.5. Tập lệnh <code>manage_aws.py</code> hỗ trợ đưa toàn bộ chi phí về 0 USD/h khi không dùng.</td>
      <td style="text-align: center; font-weight: bold; color: #059669;">ĐẠT</td>
    </tr>
  </tbody>
</table>

<h2 id="sec-3-3" class="section-title">3.3. Nghiệm thu chức năng đóng dấu, mã băm SHA-256 và lưu trữ</h2>
<p>
Nhóm đã tiến hành kiểm nghiệm toàn diện chức năng xử lý trên tệp kiểm thử mẫu <b><code>ModelOptimization.pdf</code> (dung lượng 7.0 MB, gồm 47 trang văn bản và hình ảnh phức tạp)</b>:
</p>
<ul>
  <li><b>Tốc độ xử lý đóng dấu:</b> Nhờ công nghệ render vector trực tiếp trên bộ nhớ của PyMuPDF kết hợp phông chữ nạp tức thì từ EFS, thời gian xử lý toàn bộ 47 trang chỉ mất từ <b>1.150 ms đến 1.350 ms</b> (tương đương khoảng 26 ms cho mỗi trang tài liệu).</li>
  <li><b>Đo lường hiệu quả Cache EFS:</b> Lần gọi đầu tiên khi chưa có cache trên EFS mất khoảng 1.820 ms (do phải đồng bộ file gốc từ S3). Từ các lần gọi thứ hai trở đi, thời gian tải tệp mẫu từ <code>/mnt/efs/input/</code> chỉ mất <b>3.8 ms</b>, giúp giảm 98% thời gian trễ nạp dữ liệu đầu vào.</li>
  <li><b>Độ chính xác và toàn vẹn của mã băm SHA-256:</b>
    <ul>
      <li>Mã băm SHA-256 được tính toán trực tiếp trên chuỗi byte nhị phân của tệp PDF đã đóng dấu trước khi tải lên S3.</li>
      <li>Thực hiện thay đổi thử nghiệm dù chỉ 1 ký tự trong file và tính lại mã băm: mã băm SHA-256 thay đổi hoàn toàn, API <code>GET /verify</code> lập tức từ chối và cảnh báo tài liệu không chính thống.</li>
    </ul>
  </li>
  <li><b>Nghiệm thu S3 Pre-signed URL:</b> Đường dẫn tải trả về chứa đầy đủ chữ ký bảo mật <code>AWSAccessKeyId</code>, <code>Signature</code> và thời hạn <code>Expires</code> 3.600 giây (60 phút). Trình duyệt tải trực tiếp từ cụm máy chủ S3 với tốc độ tải đạt tối đa băng thông đường truyền của người dùng.</li>
</ul>

<h2 id="sec-3-4" class="section-title">3.4. Nghiệm thu kiểm thử chịu tải (Load Testing) và Auto Scaling</h2>

<h3 id="subsec-3-4-1" class="subsection-title">3.4.1. Kịch bản kiểm thử tải đa luồng mô phỏng thực tế</h3>
<p>
Để kiểm chứng năng lực chịu tải và độ nhạy của cơ chế Auto Scaling trong điều kiện áp lực cao, nhóm đã xây dựng công cụ kiểm thử chuyên dụng <code>load_test.py</code>:
</p>
<ul>
  <li><b>Mô hình bắn tải:</b> 28 luồng đồng thời (Concurrency = 28 threads) sử dụng <code>ThreadPoolExecutor</code>.</li>
  <li><b>Thời gian chạy:</b> 360 giây (6 phút) – khớp chính xác với khung thời gian kiểm thử của kịch bản demo.</li>
  <li><b>Mô phỏng đa đối tượng &amp; tích hợp hệ sinh thái:</b> Các request mô phỏng luân phiên ngẫu nhiên người dùng Web App và 5 hệ thống tích hợp doanh nghiệp (<code>crm-service</code>, <code>billing-service</code>, <code>hrm-payroll</code>, <code>fintech-core</code>, <code>edtech-portal</code>) cùng danh sách đối tượng người nhận ngẫu nhiên, đảm bảo các tệp PDF sinh ra hoàn toàn độc lập về nội dung và mã băm SHA-256.</li>
  <li><b>Mục tiêu kiểm chứng:</b> Xác minh ALB phân phối tải đều, CloudWatch Alarm phát hiện tải cao và ASG tự động mở rộng thêm máy chủ để giải tỏa áp lực CPU.</li>
</ul>

<h3 id="subsec-3-4-2" class="subsection-title">3.4.2. Kết quả phân bổ lưu lượng và kích hoạt Auto Scaling</h3>
<p>
Dưới tác động của 28 luồng gửi liên tục các tệp PDF 47 trang, diễn biến hệ thống diễn ra đúng như thiết kế kiến trúc:
</p>

<div class="figure-box">
  {svg_load_test_chart}
  <div class="figure-caption">Hình 3. Biểu đồ diễn biến tải CPU, thông lượng RPS và quá trình kích hoạt Auto Scaling thêm máy chủ theo thời gian thực</div>
</div>

<ol>
  <li><b>Giai đoạn 0s – 60s (Áp lực tải ban đầu trên 2 máy):</b> Lưu lượng dồn vào 2 máy EC2 ban đầu (<code>ip-10-0-12-190</code> và <code>ip-10-0-11-226</code>). CPU của 2 máy tăng vọt lên <b>75% - 85%</b>. Độ trễ trung bình khoảng 2.300 ms - 4.200 ms.</li>
  <li><b>Thời điểm T+60s (CloudWatch Alarm kích hoạt):</b> Metric <code>CPUUtilization</code> trung bình vượt ngưỡng 50% trong 60 giây. CloudWatch chuyển sang trạng thái <code>ALARM</code> và phát lệnh tăng quy mô (Scale Out) tới Auto Scaling Group, đồng thời gửi thông báo qua Amazon SNS.</li>
  <li><b>Thời điểm T+80s (Worker #3 gia nhập nhận tải):</b> Máy chủ EC2 thứ ba (<code>ip-10-0-12-180</code>) hoàn tất khởi động và vượt qua Health Check của ALB, lập tức tham gia chia sẻ 15.9% tổng lưu lượng.</li>
  <li><b>Thời điểm T+140s (Worker #4 gia nhập nhận tải):</b> Máy chủ EC2 thứ tư (<code>ip-10-0-11-9</code>) hoàn tất khởi tạo. Cụm đạt quy mô tối đa 4 máy. Tải được san sẻ cho toàn bộ 4 máy, <b>thông lượng đỉnh đạt 8.0 req/giây</b>, hoàn tất 1.545 bản đóng dấu thành công.</li>
</ol>

<h3 id="subsec-3-4-3" class="subsection-title">3.4.3. Đánh giá thông số hiệu năng (Throughput, Latency, SLA)</h3>
<p>
Bảng thống kê toàn diện kết quả thực nghiệm sau 360 giây bắn tải liên tục:
</p>

<table class="report-table">
  <thead>
    <tr>
      <th>Chỉ số Đo lường (Metrics)</th>
      <th>Kết quả Thực tế Đạt được</th>
      <th>Ý nghĩa Kỹ thuật &amp; Chuẩn Đánh giá</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><b>Tổng số Request xử lý</b></td>
      <td style="font-weight: bold; color: #0369a1;">1.551 requests</td>
      <td>Xử lý đóng dấu thành công <b>72.615 trang PDF</b> (1.545 tài liệu 47 trang hoàn tất).</td>
    </tr>
    <tr>
      <td><b>Tỷ lệ Thành công (HTTP 200 OK)</b></td>
      <td style="font-weight: bold; color: #059669;">99.61% (1.545 / 1.551)</td>
      <td>Chỉ 6 request timeout (0.39%) xảy ra vào thời điểm giao thời cụm đang Scale Out.</td>
    </tr>
    <tr>
      <td><b>Thông lượng trung bình (Avg RPS)</b></td>
      <td style="font-weight: bold;">4.21 req / giây</td>
      <td>Tương đương xử lý và băm kiểm định <b>198 trang PDF mỗi giây</b> trên toàn cụm.</td>
    </tr>
    <tr>
      <td><b>Thông lượng đỉnh (Peak RPS)</b></td>
      <td style="font-weight: bold; color: #b91c1c;">8.00 req / giây</td>
      <td>Đạt được khi cả 4 máy chủ EC2 cùng đồng thời nhận tải ở trạng thái InService.</td>
    </tr>
    <tr>
      <td><b>Độ trễ trung bình (Avg Latency)</b></td>
      <td><b>6.567 ms</b></td>
      <td>Bao gồm thời gian đọc EFS cache, render vector 47 trang, băm SHA-256 và ghi RDS.</td>
    </tr>
    <tr>
      <td><b>Độ trễ phân vị p50 (Median)</b></td>
      <td><b>5.709 ms</b></td>
      <td>50% các yêu cầu hoàn tất trong khoảng 5.7 giây đối với tệp nặng 47 trang.</td>
    </tr>
    <tr>
      <td><b>Độ trễ phân vị p95</b></td>
      <td><b>14.260 ms</b></td>
      <td>95% các yêu cầu hoàn tất an toàn trong ngưỡng SLA dưới 15 giây.</td>
    </tr>
    <tr>
      <td><b>Độ trễ phân vị p99</b></td>
      <td><b>18.474 ms</b></td>
      <td>Chỉ xuất hiện trong giai đoạn cao điểm ban đầu khi chỉ có 2 máy phải gánh 28 luồng.</td>
    </tr>
    <tr>
      <td><b>Tỷ lệ Phân bổ tải ALB giữa các EC2</b></td>
      <td>Worker 1: 39.5% | Worker 2: 39.5%<br>Worker 3: 15.9% | Worker 4: 5.2%</td>
      <td>ALB tự động nhận diện và san sẻ lưu lượng ngay khi các node mới vượt qua Health Check.</td>
    </tr>
  </tbody>
</table>

<h2 id="sec-3-5" class="section-title">3.5. Phân tích chi phí vận hành và Tối ưu hóa FinOps</h2>

<h3 id="subsec-3-5-1" class="subsection-title">3.5.1. Bảng ước tính chi phí hàng tháng (Region: ap-southeast-1)</h3>
<p>
Bảng chi phí được tính toán dựa trên biểu giá chính thức của AWS tại khu vực Singapore (<code>ap-southeast-1</code>) cho trường hợp giả định hệ thống hoạt động liên tục 24/7 (730 giờ/tháng):
</p>

<table class="report-table">
  <thead>
    <tr>
      <th>Thành phần / Dịch vụ AWS</th>
      <th>Cấu hình &amp; Quy mô Giả định</th>
      <th>Mục đích Sử dụng</th>
      <th>Đơn giá Tham khảo</th>
      <th>Chi phí / Tháng (USD)</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><b>Amazon EC2 (ASG)</b></td>
      <td>2 instances <code>t3.small</code> (2 vCPU, 2GB RAM) chạy 730h</td>
      <td>Cụm Worker xử lý đóng dấu PDF trong Private Subnet</td>
      <td>~0.0264 USD / giờ / máy</td>
      <td style="text-align: right; font-weight: bold;">~42.50 USD</td>
    </tr>
    <tr>
      <td><b>Amazon EBS (gp3)</b></td>
      <td>20 GB / máy &times; 2 máy = 40 GB General Purpose SSD</td>
      <td>Ổ cứng hệ điều hành Linux và bộ đệm tạm <code>/tmp</code></td>
      <td>0.096 USD / GB-tháng</td>
      <td style="text-align: right; font-weight: bold;">~3.84 USD</td>
    </tr>
    <tr>
      <td><b>Application Load Balancer</b></td>
      <td>1 ALB chạy 730 giờ + ~1 LCU trung bình</td>
      <td>Cân bằng tải HTTP/HTTPS ở Public Subnet</td>
      <td>~0.0252 USD / giờ + LCU</td>
      <td style="text-align: right; font-weight: bold;">~24.80 USD</td>
    </tr>
    <tr>
      <td><b>NAT Gateway / Instance</b></td>
      <td>1 NAT Gateway (730h) + 20 GB truyền dữ liệu</td>
      <td>Cấp Internet một chiều an toàn cho Private Subnets</td>
      <td>~0.059 USD / giờ + 0.059 USD/GB</td>
      <td style="text-align: right; font-weight: bold;">~44.25 USD<br><span style="font-size: 8pt; color: #059669;">(~4.30 USD nếu dùng NAT Instance)</span></td>
    </tr>
    <tr>
      <td><b>Amazon EFS (Standard)</b></td>
      <td>5 GB lưu trữ chia sẻ qua NFSv4 trên 2 AZ</td>
      <td>Lưu kho Phông chữ Unicode và Tệp PDF mẫu gốc</td>
      <td>0.36 USD / GB-tháng</td>
      <td style="text-align: right; font-weight: bold;">~1.80 USD</td>
    </tr>
    <tr>
      <td><b>Amazon S3 (Standard)</b></td>
      <td>100 GB lưu trữ PDF + 200.000 requests (Lifecycle 24h)</td>
      <td>Lưu trữ đối tượng PDF đầu vào và xuất qua Pre-signed URL</td>
      <td>0.025 USD / GB-tháng</td>
      <td style="text-align: right; font-weight: bold;">~3.20 USD</td>
    </tr>
    <tr>
      <td><b>Amazon RDS (PostgreSQL)</b></td>
      <td>1 instance <code>db.t4g.micro</code> (20 GB gp3)</td>
      <td>Lưu trữ cơ sở dữ liệu kiểm toán và mã băm SHA-256</td>
      <td>~0.018 USD / giờ + 2.3 USD đĩa</td>
      <td style="text-align: right; font-weight: bold;">~15.44 USD</td>
    </tr>
    <tr>
      <td><b>CloudWatch &amp; Amazon SNS</b></td>
      <td>5 Custom Metrics, 3 Alarms, 1.000 email SNS</td>
      <td>Giám sát tải CPU và gửi email cảnh báo tự động</td>
      <td>Nằm trong gói Free Tier / 0.10 USD alarm</td>
      <td style="text-align: right; font-weight: bold;">~0.30 USD</td>
    </tr>
    <tr style="background-color: #f1f5f9;">
      <td colspan="4" style="text-align: right; font-weight: bold; font-size: 10.5pt; color: #0f172a;">
        TỔNG CHI PHÍ VẬN HÀNH ƯỚC TÍNH (24/7):
      </td>
      <td style="text-align: right; font-weight: bold; font-size: 11pt; color: #b91c1c;">
        ~136.13 USD / tháng<br>
        <span style="font-size: 8.5pt; color: #059669;">(~96.18 USD nếu dùng NAT Instance)</span>
      </td>
    </tr>
  </tbody>
</table>

<h3 id="subsec-3-5-2" class="subsection-title">3.5.2. Giải pháp Tối ưu hóa FinOps Thực tế với `manage_aws.py`</h3>
<p>
Nhận thức rõ ràng việc vận hành các dịch vụ có phí tính theo giờ (như NAT Gateway ~1.4 USD/ngày, ALB ~0.8 USD/ngày, RDS ~0.5 USD/ngày) sẽ gây hao phí ngân sách trong môi trường thực hành của sinh viên, nhóm đã phát triển công cụ tự động hóa FinOps <code>manage_aws.py</code>:
</p>
<ul>
  <li><b>Lệnh tạm dừng tiết kiệm chi phí (Sleep Mode):</b>
    <pre><code>python3 manage_aws.py sleep</code></pre>
    Script tự động thực hiện 4 bước trong 60 giây: Đưa Auto Scaling Group về <code>Min=0, Desired=0</code> (xóa toàn bộ máy EC2); gửi lệnh <code>Stop</code> cơ sở dữ liệu RDS; xóa Application Load Balancer; và xóa NAT Gateway kèm nhả Elastic IP. <b>Chi phí hạ tầng giảm ngay về 0 USD/giờ</b>.
  </li>
  <li><b>Lệnh đánh thức phục vụ demo (Wake Mode):</b>
    <pre><code>python3 manage_aws.py wake</code></pre>
    Script tự động khởi tạo lại NAT Gateway, cấu hình lại Route Table cho Private Subnet, khởi động lại RDS, tái lập ALB, đưa ASG về <code>Min=2, Desired=2</code> và chờ đợi cho đến khi toàn bộ máy chủ đạt trạng thái <code>Healthy</code> sẵn sàng nhận lệnh.
  </li>
  <li><b>Tùy chọn cố định DNS:</b> Lệnh <code>python3 manage_aws.py sleep --keep-alb</code> cho phép tắt máy EC2, RDS và NAT Gateway nhưng giữ lại ALB nhằm duy trì cố định tên miền DNS phục vụ báo cáo.</li>
</ul>

<div class="callout callout-success">
  <div class="callout-title">Hiệu quả FinOps thực tế</div>
  Nhờ giải pháp này, trong suốt 4 tuần triển khai và thử nghiệm dự án, tổng chi phí AWS thực tế của nhóm chỉ tiêu tốn <b>chưa đầy 12.5 USD</b> (thay vì hơn 130 USD nếu duy trì liên tục), tiết kiệm <b>hơn 90% ngân sách</b>.
</div>

<h2 id="sec-3-6" class="section-title">3.6. Vai trò và tỷ lệ đóng góp của các thành viên</h2>
<table class="report-table">
  <thead>
    <tr>
      <th>Thành viên &amp; MSV</th>
      <th>Vai trò Phụ trách Chính</th>
      <th>Các Hạng mục Kỹ thuật Bàn giao Thực tế</th>
      <th>Tỷ lệ Đóng góp</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><b>Trần Nhật Hưng</b><br>(MSV: 24021507)</td>
      <td><b>Nhóm trưởng</b><br>Tính toán, Cân bằng tải, Tự động mở rộng &amp; Giám sát</td>
      <td>
        • Cấu hình cụm EC2 Worker, Launch Template và Golden Custom AMI.<br>
        • Thiết lập Application Load Balancer (ALB) và Auto Scaling Group (ASG).<br>
        • Cấu hình CloudWatch Alarm và Amazon SNS gửi email cảnh báo.<br>
        • Lập trình công cụ tự động hóa FinOps <code>manage_aws.py</code>.<br>
        • Điều phối tiến độ, chịu trách nhiệm tổng hợp báo cáo và diễn tập demo.
      </td>
      <td style="text-align: center; font-weight: bold; color: #0369a1;">34%</td>
    </tr>
    <tr>
      <td><b>Nguyễn Nam Khánh</b><br>(MSV: 24021531)</td>
      <td><b>Thành viên</b><br>Hạ tầng Mạng, Bảo mật &amp; Lưu trữ đa tầng</td>
      <td>
        • Thiết kế kiến trúc mạng Amazon VPC Multi-AZ, phân chia Subnets.<br>
        • Cấu hình Internet Gateway, NAT Gateway và hệ thống Route Tables.<br>
        • Thiết lập ma trận tường lửa Security Groups và IAM Role cho EC2.<br>
        • Triển khai Amazon S3 Bucket, cấu hình S3 Lifecycle Policy.<br>
        • Thiết lập Amazon EFS, Mount Targets và tối ưu hóa bộ nhớ đệm phông chữ.
      </td>
      <td style="text-align: center; font-weight: bold; color: #0369a1;">33%</td>
    </tr>
    <tr>
      <td><b>Đỗ Lê Duy</b><br>(MSV: 24021445)</td>
      <td><b>Thành viên</b><br>Cơ sở dữ liệu, Ứng dụng &amp; Kiểm thử tải</td>
      <td>
        • Khởi tạo và tối ưu hóa Amazon RDS PostgreSQL 18.3 trong Private Subnet.<br>
        • Lập trình Nền tảng Web FastAPI v2.1 kết hợp nhân đồ họa PyMuPDF.<br>
        • Xây dựng thuật toán băm mật mã học SHA-256 và sinh S3 Pre-signed URL.<br>
        • Lập trình công cụ bắn tải đa luồng <code>load_test.py</code> và script <code>get_sha256.py</code>.<br>
        • Thiết kế giao diện Web Portal kiểm định và cổng tra cứu Swagger API.
      </td>
      <td style="text-align: center; font-weight: bold; color: #0369a1;">33%</td>
    </tr>
  </tbody>
</table>

<div class="page-break"></div>
<h2 id="sec-3-7" class="section-title" style="margin-top: 10pt; margin-bottom: 6pt;">3.7. Kịch bản DEMO 10 phút cho Giảng viên</h2>
<p style="margin-bottom: 6pt;">
Nhóm đã chuẩn bị sẵn sàng hệ thống và tài nguyên để phục vụ buổi báo cáo và nghiệm thu trực tiếp trước Giảng viên:
</p>
<ul style="margin-bottom: 6pt;">
  <li style="margin-bottom: 2pt;"><b>Địa chỉ truy cập trực tiếp (Live ALB Endpoint):</b><br>
    <a href="http://PDF-Watermark-ALB-281030112.ap-southeast-1.elb.amazonaws.com" style="color: #0284c7; font-family: monospace; font-size: 8.8pt;">
      http://PDF-Watermark-ALB-281030112.ap-southeast-1.elb.amazonaws.com
    </a>
  </li>
  <li style="margin-bottom: 2pt;"><b>Tài liệu API tương tác trực tiếp (Swagger UI):</b><br>
    <a href="http://PDF-Watermark-ALB-281030112.ap-southeast-1.elb.amazonaws.com/docs" style="color: #0284c7; font-family: monospace; font-size: 8.8pt;">
      http://PDF-Watermark-ALB-281030112.ap-southeast-1.elb.amazonaws.com/docs
    </a>
  </li>
</ul>

<h3 class="subsection-title" style="margin-top: 8pt; margin-bottom: 4pt;">Kịch bản Trình diễn Hệ thống trong 10 Phút:</h3>
<table class="report-table" style="margin: 6pt 0; font-size: 8.8pt; line-height: 1.35;">
  <thead>
    <tr>
      <th style="width: 15%; padding: 4pt 6pt;">Thời lượng</th>
      <th style="width: 25%; padding: 4pt 6pt;">Nội dung Trình diễn</th>
      <th style="width: 30%; padding: 4pt 6pt;">Thao tác Kỹ thuật Thực tế</th>
      <th style="width: 30%; padding: 4pt 6pt;">Kết quả Trực quan trên Màn hình</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="text-align: center; font-weight: bold; padding: 4pt 6pt;">Phút 00 – 02</td>
      <td style="padding: 4pt 6pt;"><b>Kiểm chứng Hạ tầng Mạng, Bảo mật &amp; 3 Loại Lưu trữ</b></td>
      <td style="padding: 4pt 6pt;">Mở AWS Console: Kiểm tra VPC, 2 Public/2 Private Subnets. Mở EC2 Worker chỉ có Private IP. Mở S3, EFS và RDS Console.</td>
      <td style="padding: 4pt 6pt;">Giảng viên thấy rõ mô hình Multi-AZ chuẩn, các máy chủ không lộ IP công khai, các ổ đĩa mount EFS và bảng <code>audit_logs</code> trên RDS.</td>
    </tr>
    <tr>
      <td style="text-align: center; font-weight: bold; padding: 4pt 6pt;">Phút 02 – 05</td>
      <td style="padding: 4pt 6pt;"><b>Demo Nền tảng Web Studio, Master Hub &amp; Đóng Dấu Hàng Loạt Nén ZIP</b></td>
      <td style="padding: 4pt 6pt;">Mở Web App trực tiếp: Tải file lên Kho EFS/S3 một lần duy nhất; xem trước Canvas; nạp danh sách 10 sinh viên chạy đa luồng xuất tệp ZIP; kéo thả PDF kiểm định SHA-256.</td>
      <td style="padding: 4pt 6pt;">Giảng viên thấy rõ giao diện Web Studio trực quan, tải file 1 lần tái sử dụng nhiều lần, file ZIP nén kèm bảng kê manifest CSV và xác thực băm SHA-256 tức thì (&lt;20ms).</td>
    </tr>
    <tr>
      <td style="text-align: center; font-weight: bold; padding: 4pt 6pt;">Phút 05 – 08</td>
      <td style="padding: 4pt 6pt;"><b>Demo Bắn tải &amp; Kích hoạt Auto Scaling Trực tiếp</b></td>
      <td style="padding: 4pt 6pt;">Kích hoạt script <code>python3 load_test.py</code> (28 luồng đồng thời trong 360s). Mở đồng thời màn hình CloudWatch CPU và EC2 Instances.</td>
      <td style="padding: 4pt 6pt;">Màn hình terminal in tên từng Worker Host. CPU vượt 50%, CloudWatch Alarm chuyển đỏ, EC2 #3 và #4 tự động sinh ra và nhận tải trong 45s.</td>
    </tr>
    <tr>
      <td style="text-align: center; font-weight: bold; padding: 4pt 6pt;">Phút 08 – 10</td>
      <td style="padding: 4pt 6pt;"><b>Tổng kết Hiệu năng, FinOps &amp; Hỏi đáp (Q&amp;A)</b></td>
      <td style="padding: 4pt 6pt;">Chiếu bảng phân bổ tải, thời gian đáp ứng p95/p99; demo lệnh <code>manage_aws.py sleep</code> đưa chi phí về 0 USD/h; trả lời câu hỏi của Giảng viên.</td>
      <td style="padding: 4pt 6pt;">Chứng minh tính thực tiễn cao, khả năng tiết kiệm chi phí vượt trội và sự hiểu sâu về kiến trúc điện toán đám mây AWS.</td>
    </tr>
  </tbody>
</table>

<h2 id="sec-3-8" class="section-title" style="margin-top: 8pt; margin-bottom: 4pt;">3.8. Liên kết mã nguồn và sản phẩm bàn giao</h2>
<ul style="margin-bottom: 4pt;">
  <li style="margin-bottom: 2pt;"><b>Mã nguồn đầy đủ của dự án (GitHub Repository):</b><br>
    <code>https://github.com/NhHung07/Dynamic-PDF-Watermarking-Pipeline</code>
  </li>
  <li style="margin-bottom: 2pt;"><b>Tài liệu hướng dẫn triển khai &amp; Báo cáo chi tiết:</b><br>
    Bao gồm tệp <code>README.md</code>, mã nguồn <code>main.py</code>, công cụ bắn tải <code>load_test.py</code>, script FinOps <code>manage_aws.py</code> và tài liệu kiểm thử.
  </li>
</ul>

</body>
</html>
"""

    script_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(script_dir, "report.html")
    pdf_path = os.path.join(script_dir, "report.pdf")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"HTML report successfully written to {html_path}")
    print("Compiling PDF with WeasyPrint...")

    html_obj = weasyprint.HTML(filename=html_path)
    html_obj.write_pdf(pdf_path)

    print(f"PDF successfully generated at: {pdf_path}")
    size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
    print(f"File size: {size_mb:.2f} MB")

    artifact_dir = "/home/hung/.gemini/antigravity/brain/1c536a50-7cac-4c60-96c8-316054de8c63"
    if os.path.isdir(artifact_dir):
        dest_pdf = os.path.join(artifact_dir, "report.pdf")
        import shutil
        shutil.copy2(pdf_path, dest_pdf)
        print(f"Copied PDF to artifact directory: {dest_pdf}")

if __name__ == "__main__":
    create_report()
