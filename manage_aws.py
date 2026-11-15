import csv
import os
import re
import sys
import time
import boto3
from botocore.exceptions import ClientError

REGION = "ap-southeast-1"
VPC_ID = "vpc-0f629db08b2b22010"
PUBLIC_SUBNET_1A = "subnet-0c3625ad0d39f7124"
PUBLIC_SUBNET_1B = "subnet-095294e5965b2e6b8"
ALB_SG_ID = "sg-05bf5f5fa01c9d6fb"

ASG_NAME = "PDF-Watermark-ASG"
RDS_ID = "pdf-watermark-db"
ALB_NAME = "PDF-Watermark-ALB"
TG_NAME = "PDF-Watermark-TG"
PRIVATE_RT_NAME = "Private-RT"
CRED_FILES = [
    "hung_accessKeys.csv",
    "hung_credentials.csv",
]


def get_session():
    for cred_file in CRED_FILES:
        if os.path.exists(cred_file):
            try:
                with open(cred_file, mode="r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        ak = row.get("Access key ID") or row.get("AccessKeyId")
                        sk = row.get("Secret access key") or row.get("SecretAccessKey")
                        if ak and sk:
                            print(f"[INFO] Đã nạp thông tin xác thực AWS từ: {cred_file}")
                            return boto3.Session(
                                aws_access_key_id=ak.strip(),
                                aws_secret_access_key=sk.strip(),
                                region_name=REGION,
                            )
            except Exception as e:
                print(f"[WARN] Lỗi khi đọc {cred_file}: {e}")
    return boto3.Session(region_name=REGION)


def sleep_infra(sess, keep_alb=False):
    asg = sess.client("autoscaling")
    rds = sess.client("rds")
    ec2 = sess.client("ec2")
    elbv2 = sess.client("elbv2")

    print("1/4. Đưa Auto Scaling Group về 0 máy EC2...")
    asg.update_auto_scaling_group(
        AutoScalingGroupName=ASG_NAME, MinSize=0, DesiredCapacity=0
    )
    print(f"   -> Đã đặt {ASG_NAME}: Min=0, Desired=0.")

    print("2/4. Tạm dừng cơ sở dữ liệu RDS...")
    db_status = rds.describe_db_instances(DBInstanceIdentifier=RDS_ID)["DBInstances"][0]["DBInstanceStatus"]
    if db_status == "available":
        rds.stop_db_instance(DBInstanceIdentifier=RDS_ID)
        print(f"   -> Đã gửi lệnh Stop cho {RDS_ID}.")
    else:
        print(f"   -> Bỏ qua ({RDS_ID} đang ở trạng thái: {db_status}).")

    if not keep_alb:
        print("3/4. Xóa Application Load Balancer để tiết kiệm credit...")
        try:
            lbs = elbv2.describe_load_balancers(Names=[ALB_NAME])["LoadBalancers"]
            if lbs:
                elbv2.delete_load_balancer(LoadBalancerArn=lbs[0]["LoadBalancerArn"])
                print(f"   -> Đã xóa {ALB_NAME}.")
        except ClientError:
            print(f"   -> {ALB_NAME} không tồn tại hoặc đã xóa.")
    else:
        print("3/4. Giữ nguyên ALB theo tùy chọn --keep-alb.")

    print("4/4. Xóa NAT Gateway và giải phóng Elastic IP...")
    nats = ec2.describe_nat_gateways(
        Filters=[
            {"Name": "vpc-id", "Values": [VPC_ID]},
            {"Name": "state", "Values": ["available", "pending"]},
        ]
    )["NatGateways"]

    eip_allocs = []
    for nat in nats:
        nat_id = nat["NatGatewayId"]
        for addr in nat.get("NatGatewayAddresses", []):
            if "AllocationId" in addr:
                eip_allocs.append(addr["AllocationId"])
        ec2.delete_nat_gateway(NatGatewayId=nat_id)
        print(f"   -> Đang xóa NAT Gateway {nat_id} (chờ ~45s để nhả Elastic IP)...")
        while True:
            state = ec2.describe_nat_gateways(NatGatewayIds=[nat_id])["NatGateways"][0]["State"]
            if state == "deleted":
                break
            time.sleep(5)

    for alloc_id in eip_allocs:
        ec2.release_address(AllocationId=alloc_id)
        print(f"   -> Đã giải phóng Elastic IP ({alloc_id}).")

    # Dọn thêm các Elastic IP nhàn rỗi (nếu có)
    for addr in ec2.describe_addresses()["Addresses"]:
        if "AssociationId" not in addr:
            ec2.release_address(AllocationId=addr["AllocationId"])
            print(f"   -> Đã giải phóng EIP nhàn rỗi ({addr['PublicIp']}).")

    print("\n[HOÀN TẤT] Toàn bộ hạ tầng đã về trạng thái nghỉ (0 USD/giờ).")


def wake_infra(sess):
    asg = sess.client("autoscaling")
    rds = sess.client("rds")
    ec2 = sess.client("ec2")
    elbv2 = sess.client("elbv2")

    print("1/4. Khôi phục NAT Gateway & cập nhật Private-RT...")
    nats = ec2.describe_nat_gateways(
        Filters=[
            {"Name": "vpc-id", "Values": [VPC_ID]},
            {"Name": "state", "Values": ["available", "pending"]},
        ]
    )["NatGateways"]

    if nats:
        nat_id = nats[0]["NatGatewayId"]
        print(f"   -> Đã có sẵn NAT Gateway: {nat_id}")
    else:
        eip = ec2.allocate_address(Domain="vpc")
        nat = ec2.create_nat_gateway(
            SubnetId=PUBLIC_SUBNET_1A,
            AllocationId=eip["AllocationId"],
            TagSpecifications=[
                {"ResourceType": "natgateway", "Tags": [{"Key": "Name", "Value": "PDF-Watermark-NAT"}]}
            ],
        )["NatGateway"]
        nat_id = nat["NatGatewayId"]
        print(f"   -> Đang khởi tạo NAT Gateway {nat_id} (chờ ~60-90s)...")
        ec2.get_waiter("nat_gateway_available").wait(NatGatewayIds=[nat_id])

    rts = ec2.describe_route_tables(
        Filters=[
            {"Name": "vpc-id", "Values": [VPC_ID]},
            {"Name": "tag:Name", "Values": [PRIVATE_RT_NAME]},
        ]
    )["RouteTables"]
    if rts:
        rt_id = rts[0]["RouteTableId"]
        try:
            ec2.replace_route(RouteTableId=rt_id, DestinationCidrBlock="0.0.0.0/0", NatGatewayId=nat_id)
        except ClientError:
            ec2.create_route(RouteTableId=rt_id, DestinationCidrBlock="0.0.0.0/0", NatGatewayId=nat_id)
        print(f"   -> Đã trỏ route 0.0.0.0/0 của {PRIVATE_RT_NAME} ({rt_id}) sang {nat_id}.")

    print("2/4. Khởi động lại cơ sở dữ liệu RDS...")
    while True:
        db_status = rds.describe_db_instances(DBInstanceIdentifier=RDS_ID)["DBInstances"][0]["DBInstanceStatus"]
        if db_status == "available":
            print(f"   -> {RDS_ID} đã sẵn sàng (available).")
            break
        if db_status == "stopped":
            rds.start_db_instance(DBInstanceIdentifier=RDS_ID)
            print(f"   -> Đã gửi lệnh Start cho {RDS_ID}, đang chờ khởi động...")
        else:
            print(f"   -> {RDS_ID} đang ở trạng thái '{db_status}', chờ 15s...")
        time.sleep(15)

    print("3/4. Kiểm tra / Dựng lại Application Load Balancer...")
    tg_arn = elbv2.describe_target_groups(Names=[TG_NAME])["TargetGroups"][0]["TargetGroupArn"]
    try:
        alb = elbv2.describe_load_balancers(Names=[ALB_NAME])["LoadBalancers"][0]
        alb_dns = alb["DNSName"]
        print(f"   -> ALB đang hoạt động: {alb_dns}")
    except ClientError:
        alb = elbv2.create_load_balancer(
            Name=ALB_NAME,
            Subnets=[PUBLIC_SUBNET_1A, PUBLIC_SUBNET_1B],
            SecurityGroups=[ALB_SG_ID],
            Scheme="internet-facing",
            Type="application",
            IpAddressType="ipv4",
        )["LoadBalancers"][0]
        alb_arn = alb["LoadBalancerArn"]
        alb_dns = alb["DNSName"]
        print(f"   -> Đang tạo mới {ALB_NAME} ({alb_dns}), chờ ~60s...")
        elbv2.get_waiter("load_balancer_available").wait(LoadBalancerArns=[alb_arn])
        elbv2.create_listener(
            LoadBalancerArn=alb_arn,
            Protocol="HTTP",
            Port=80,
            DefaultActions=[{"Type": "forward", "TargetGroupArn": tg_arn}],
        )

    asg.attach_load_balancer_target_groups(
        AutoScalingGroupName=ASG_NAME, TargetGroupARNs=[tg_arn]
    )

    if os.path.exists("load_test.py"):
        with open("load_test.py", "r", encoding="utf-8") as f:
            code = f.read()
        updated = re.sub(r"http://PDF-Watermark-ALB-[^/\"]+", f"http://{alb_dns}", code)
        with open("load_test.py", "w", encoding="utf-8") as f:
            f.write(updated)
        print("   -> Đã tự động cập nhật ALB_URL mới vào load_test.py.")

    print("4/4. Bật cụm 2 máy EC2 Worker qua Auto Scaling Group...")
    asg.update_auto_scaling_group(
        AutoScalingGroupName=ASG_NAME, MinSize=2, DesiredCapacity=2
    )
    print("   -> Đang chờ 2 máy EC2 khởi động và vượt qua ALB Health Check (~90s)...")
    while True:
        targets = elbv2.describe_target_health(TargetGroupArn=tg_arn)["TargetHealthDescriptions"]
        healthy_count = sum(1 for t in targets if t["TargetHealth"]["State"] == "healthy")
        if healthy_count >= 2:
            break
        time.sleep(10)

    print(f"\n[SẴN SÀNG] Toàn bộ hệ thống đã hoạt động!")
    print(f"Truy cập Web UI tại: http://{alb_dns}")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("sleep", "wake"):
        print("Cách dùng:")
        print("  python3 manage_aws.py sleep             # Tắt toàn bộ (0 USD/giờ)")
        print("  python3 manage_aws.py sleep --keep-alb  # Tắt EC2/RDS/NAT, giữ cố định DNS ALB")
        print("  python3 manage_aws.py wake              # Bật lại toàn bộ & chờ Healthy")
        sys.exit(1)

    session = get_session()
    if sys.argv[1] == "sleep":
        sleep_infra(session, keep_alb=("--keep-alb" in sys.argv))
    else:
        wake_infra(session)
