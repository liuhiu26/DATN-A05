\# Đồ án tốt nghiệp – Nhóm A05



\*\*Đề tài:\*\* Xây dựng khung Kiểm thử an toàn và phát hiện bất thường cho mô hình kiểm soát truy cập

\*\*GVHD:\*\* Lê Hà Thanh



\## Phân công và kết quả (cập nhật 30/10/2026)



| Thành viên | Nội dung | Kết quả | Vị trí trên repo |

|---|---|---|---|

| TV2 – Hiếu | Hệ thống HR Docs (FastAPI, Keycloak, OPA, Kong, Loki/Grafana, MongoDB); 6 luật RBAC–ABAC bằng Rego; audit log 16 trường; hai bản: đã vá và cài sẵn lỗ hổng | Test chính sách OPA: bản vá 26/26, bản lỗ hổng 22/26 (4 test fail đúng thiết kế) | `hr-docs-app-iam-stack/`, `hr-docs-app-iam-stack-vulnerable/` |

| TV1 – Cường | Công cụ pentest 14 kịch bản (BOLA/IDOR, leo thang đặc quyền, giả mạo token) | Bản lỗ hổng bị khai thác 11/14; bản đã vá 0/14 | 

| TV3 – Duy | Trình mô phỏng người dùng, pipeline thu log, trích đặc trưng; thử Isolation Forest trên CERT r4.2 | ROC-AUC 0,861; Recall hiện còn thấp | `ml/`; notebook: https://www.kaggle.com/code/leduy7/if-cert |



\## Tiến độ

\- Hoàn thành đúng hạn kế hoạch tuần 3–5; đang bước vào tuần 6–7.



\## Việc tuần tới (đến 6/11/2026)

\- Hiếu: đồng bộ phần cơ sở dữ liệu vào bản đã vá, chạy kịch bản của Cường lên cả hai bản, viết tài liệu chính sách.

\- Cường: mở rộng kịch bản, sinh log tấn công có gắn nhãn, bàn giao cho Duy.

\- Duy: bổ sung đặc trưng, chọn ngưỡng theo Precision–Recall, chạy thử trên log của ứng dụng.



\## Cách chạy

Xem `README.md` trong từng thư mục ứng dụng. 

