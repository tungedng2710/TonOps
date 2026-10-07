# Xây dựng dự án phát hiện đối tượng với TonOps

[English](README.md) | [Tiếng Việt](README.vi.md)

Hướng dẫn này sử dụng YOLO12 để minh họa cách quản lý một dự án phát hiện đối
tượng trên TonOps: kết nối tài khoản, quản lý phiên bản bộ dữ liệu, gửi tác vụ
huấn luyện đến worker GPU, so sánh các lần thử nghiệm và chạy dự đoán bằng mô
hình đã đăng ký. Hãy thay các lớp phương tiện và đường dẫn dữ liệu trong ví dụ
bằng thông tin của dự án của bạn.

Chạy các lệnh dưới đây từ **thư mục gốc của repository**. Dùng
`python examples/vehicle_detection_yolo12/project.py --help` để xem các lệnh
của công cụ dòng lệnh (CLI) dành cho dự án.

## 1. Kết nối với không gian làm việc TonOps

Khởi động hệ thống theo [hướng dẫn thiết lập stack](../../README.md#start-with-docker-compose).
Mở giao diện web, đăng nhập vào tài khoản của bạn và tạo thông tin xác thực API
trong **Account settings**. Cài đặt công cụ client trên máy chứa bộ dữ liệu:

```bash
python3.10 -m venv .venv/tonops-example
source .venv/tonops-example/bin/activate
python -m pip install -r examples/vehicle_detection_yolo12/requirements-client.txt
clearml-init
```

Nhập thông tin xác thực API của tài khoản và địa chỉ các dịch vụ trong hệ thống:

| Dịch vụ | Máy chủ trên cùng máy | Máy chủ từ xa |
| --- | --- | --- |
| Web | `http://localhost:7861` | `http://SERVER_HOST:7861` |
| API | `http://localhost:7862` | `http://SERVER_HOST:7862` |
| Files | `http://localhost:7863` | `http://SERVER_HOST:7863` |

Cấu hình thông tin xác thực RustFS và kết nối S3 trong tệp riêng
`~/clearml.conf` theo [ví dụ cấu hình lưu trữ](../../README.md#start-with-docker-compose).
Sử dụng hostname RustFS mà cả máy client và worker GPU đều truy cập được.
Không đưa tệp cấu hình chứa thông tin xác thực vào Git.

Chọn tên dự án và URI lưu trữ các tệp kết quả (artifact) của hệ thống:

```bash
export TONOPS_PROJECT='Vehicle Detection/YOLO12'
export TONOPS_OUTPUT_URI='s3://YOUR_RUSTFS_HOST:7868/tonops-artifacts'
```

Các lời gọi ClearML SDK trong ví dụ kết nối đến TonOps. Phiên bản bộ dữ liệu,
các lần thử nghiệm, chỉ số đánh giá và mô hình xuất hiện trên giao diện web
TonOps. RustFS lưu trữ các tệp được tải lên.

## 2. Khởi động worker GPU và kiểm tra luồng huấn luyện

Trên máy có GPU, làm theo [hướng dẫn thiết lập worker GPU](../../docs/clearml-gpu-worker.md)
để cài agent, cấu hình thông tin xác thực API và lưu trữ, rồi build Docker image
dùng cho huấn luyện. Khởi động worker bằng lệnh:

```bash
python scripts/clearml-gpu-worker.py start --queue gpu --gpus 0 --detached
```

Trên máy client, kiểm tra worker đang hoạt động và gửi tác vụ nhỏ dùng COCO8:

```bash
python examples/vehicle_detection_yolo12/project.py workers
python examples/vehicle_detection_yolo12/project.py submit \
  --project "$TONOPS_PROJECT" --queue gpu \
  --output-uri "$TONOPS_OUTPUT_URI" --wait
```

Trong **Workers & Queues**, xác nhận worker đang nhận tác vụ từ hàng đợi `gpu`.
Mở tác vụ vừa gửi trong danh sách thử nghiệm của dự án. Phần console cần hiển
thị thông tin môi trường GPU; trạng thái tác vụ sẽ chuyển từ chờ trong hàng đợi
sang đang chạy, rồi hoàn thành. Lần chạy kiểm tra với một epoch giúp xác nhận
việc thực thi và tải kết quả lên. Sử dụng bộ dữ liệu của bạn để huấn luyện dự án
và so sánh độ chính xác.

Client tải lên mã huấn luyện cùng thông tin về các gói phụ thuộc, tham số và
Docker image. Worker lấy tác vụ và chạy mã trong container dùng image đó.
Máy client không cần cài PyTorch hoặc có GPU để gửi tác vụ. Mỗi worker nhận tác
vụ từ hàng đợi cần có image được build trên máy hoặc có thể lấy từ registry.

## 3. Chuẩn bị và kiểm tra bộ dữ liệu

Sử dụng nhãn phát hiện đối tượng theo định dạng YOLO: mỗi dòng biểu diễn một
đối tượng với các trường `class_id x_center y_center width height`. Tọa độ được
chuẩn hóa theo kích thước ảnh và mã lớp bắt đầu từ số không. Tệp nhãn rỗng biểu
diễn ảnh không có đối tượng.

Với cấu hình phương tiện đi kèm, sắp xếp dữ liệu theo cấu trúc:

```text
/path/to/vehicles/
├── train/
│   ├── images/
│   └── labels/
├── valid/
│   ├── images/
│   └── labels/
└── test/                 # tùy chọn; xóa mục tương ứng trong YAML nếu không có
    ├── images/
    └── labels/
```

Mỗi ảnh cần có tệp nhãn `.txt` tương ứng trong thư mục `labels` của tập dữ liệu
đó, giữ nguyên tên và cấu trúc đường dẫn tương đối. Tệp
[data.yaml mẫu](data.yaml) định nghĩa các lớp bicycle, bus, car, motorbike và
truck, tương ứng với xe đạp, xe buýt, ô tô, xe máy và xe tải. Sao chép tệp này
cho dự án của bạn, rồi sửa `names`, `train`, `val` và `test` nếu có cho phù hợp.
Mỗi tập dữ liệu phải trỏ đến một thư mục `images` có thư mục `labels` cùng cấp.

```bash
export TONOPS_DATA_ROOT=/path/to/vehicles

python examples/vehicle_detection_yolo12/project.py validate \
  --dataset-root "$TONOPS_DATA_ROOT" \
  --data examples/vehicle_detection_yolo12/data.yaml
```

Lệnh kiểm tra xác nhận đường dẫn các tập dữ liệu, tập ảnh không rỗng, nhãn tương
ứng, mã lớp và tọa độ hộp giới hạn đã chuẩn hóa. Lệnh in số lượng ảnh, nhãn và
đối tượng theo từng tập và lớp mà không kết nối đến máy chủ. Nếu dùng cấu hình
khác, truyền `--data /path/to/your/data.yaml` khi kiểm tra và đăng ký dữ liệu.
`--dataset-root` ghi đè trường `path` trong YAML; đường dẫn các tập dữ liệu phải
nằm bên trong thư mục gốc được cung cấp.

## 4. Đăng ký một phiên bản bộ dữ liệu

```bash
python examples/vehicle_detection_yolo12/project.py register \
  --project "$TONOPS_PROJECT" --name vehicles --version 1.0.0 \
  --dataset-root "$TONOPS_DATA_ROOT" \
  --data examples/vehicle_detection_yolo12/data.yaml \
  --output-uri "$TONOPS_OUTPUT_URI"

export TONOPS_DATASET_ID=$(cat docker-data/examples/object-detection/dataset-id)
```

Lệnh đăng ký kiểm tra lại dữ liệu, tải ảnh và nhãn lên, đồng thời thêm một tệp
`data.yaml` dùng đường dẫn tương đối để có thể sử dụng trên các worker khác
nhau. Lệnh lưu thông tin kiểm tra và chốt phiên bản bộ dữ liệu. Tệp YAML nguồn
của bạn được giữ nguyên. Tìm phiên bản vừa đăng ký trong **Datasets** và lưu
Dataset ID; worker dùng ID này để tải đúng bộ dữ liệu.

Khi nhãn hoặc cách chia dữ liệu thay đổi, đăng ký một phiên bản mới, chẳng hạn
`1.1.0`, rồi dùng Dataset ID mới cho các lần chạy tiếp theo. Những phiên bản đã
chốt vẫn được giữ lại để tái lập các thử nghiệm trước đó. Mỗi lần gọi lệnh đăng
ký sẽ tạo một phiên bản mới; hãy dùng lại ID đã lưu khi dữ liệu chưa thay đổi.

## 5. Huấn luyện mô hình qua hàng đợi GPU

Bắt đầu bằng một lần chạy nhỏ trên bộ dữ liệu đã đăng ký:

```bash
python examples/vehicle_detection_yolo12/project.py submit \
  --project "$TONOPS_PROJECT" --name 'vehicles-smoke' --queue gpu \
  --dataset-id "$TONOPS_DATASET_ID" --model yolo12n.pt \
  --epochs 1 --fraction 0.01 --imgsz 320 --batch 2 \
  --output-uri "$TONOPS_OUTPUT_URI" --wait
```

Sau đó gửi một lần huấn luyện cơ sở (baseline) sử dụng toàn bộ tập huấn luyện:

```bash
python examples/vehicle_detection_yolo12/project.py submit \
  --project "$TONOPS_PROJECT" --name 'vehicles-baseline' --queue gpu \
  --dataset-id "$TONOPS_DATASET_ID" --model yolo12n.pt \
  --epochs 50 --imgsz 640 --batch 8 --workers 2 \
  --output-uri "$TONOPS_OUTPUT_URI"

export TONOPS_TASK_ID=$(cat docker-data/examples/object-detection/task-id)
python examples/vehicle_detection_yolo12/project.py check \
  --task-id "$TONOPS_TASK_ID" --wait --timeout 7200
```

Worker tải bộ dữ liệu, xác định đường dẫn dựa trên thư mục cache của chính nó,
huấn luyện trên tập train và báo cáo các chỉ số trên tập validation. Tác vụ ghi
lại Dataset ID, thông tin môi trường GPU, các chỉ số cuối cùng và mô hình đầu
ra chứa checkpoint tốt nhất cùng tên các lớp. Tập test, nếu có, được dành cho
một lần đánh giá riêng; ví dụ này không sử dụng tập test để lựa chọn mô hình.

Lệnh gửi tác vụ in Task ID và URL xem kết quả. Task ID được lưu là ID của lần
gửi gần nhất; hãy lưu các ID trước đó hoặc dùng `--task-id-file` để lưu riêng
từng lần chạy. `check --wait` trả về mã `0` khi hoàn thành, `1` khi thất bại,
bị dừng hoặc đóng, và `2` khi hết thời gian chờ. Hết thời gian chờ không dừng
tác vụ đang chạy hoặc đang nằm trong hàng đợi. Nếu không dùng `--wait`, lệnh
chỉ hiển thị trạng thái hiện tại mà không chờ tác vụ hoàn thành.

## 6. So sánh các lần thử nghiệm và chọn mô hình

Mở dự án trong TonOps và chọn các lần chạy để so sánh tham số huấn luyện,
precision/recall trên tập validation, mAP và các giá trị loss. Giữ nguyên
Dataset ID khi thay đổi một lựa chọn huấn luyện, chẳng hạn so sánh
`--imgsz 640` với `--imgsz 320`. Đặt tên mô tả rõ mục đích cho từng lần chạy.

Với các lần chạy dùng bộ dữ liệu của bạn, artifact của tác vụ gồm `dataset`,
`gpu-runtime` và `final-metrics`. Mô hình đầu ra liên kết checkpoint với lần
huấn luyện đã tạo ra nó. Lệnh `check` cũng in các Model ID đầu ra. Sao chép
Model ID đã chọn từ kết quả này hoặc trang của mô hình để chạy dự đoán. Thành
viên dự án cần quyền truy cập cả dự án lẫn nơi lưu trữ artifact để tải mô hình.

## 7. Chạy dự đoán bằng mô hình đã đăng ký

Cài các gói phụ thuộc phục vụ suy luận trên một máy truy cập được TonOps và
RustFS. Mặc định, dự đoán chạy trên CPU:

```bash
python -m pip install -r examples/vehicle_detection_yolo12/requirements.txt
export TONOPS_MODEL_ID=YOUR_OUTPUT_MODEL_ID

python examples/vehicle_detection_yolo12/project.py predict \
  --model-id "$TONOPS_MODEL_ID" --source /path/to/image.jpg
```

Lệnh tải checkpoint đã đăng ký, rồi lưu ảnh có đánh dấu kết quả và tệp JSON vào
`docker-data/examples/object-detection/predictions/`. Mỗi kết quả phát hiện
chứa mã lớp, tên lớp, điểm tin cậy và hộp giới hạn tính theo pixel của ảnh gốc.
Dùng `--confidence 0.4` để thay ngưỡng tin cậy, `--device 0` để chạy trên máy có
GPU hoặc `--output-dir /path/to/results` để đổi thư mục lưu kết quả.

Lệnh này giúp bạn kiểm tra mô hình đã chọn trên các ảnh mới. Để triển khai thành
một ứng dụng, sử dụng cùng Model ID và logic suy luận trong dịch vụ của bạn,
đồng thời lựa chọn cách xác thực, cấu hình mạng và triển khai phù hợp với ứng dụng.

## Các tệp mã nguồn để điều chỉnh cho dự án của bạn

| Tệp | Vai trò |
| --- | --- |
| [project.py](project.py) | Các lệnh người dùng: validate, register, submit, check, workers và predict |
| [dataset.py](dataset.py) | Kiểm tra nhãn và đăng ký bộ dữ liệu dùng được trên nhiều worker |
| [train.py](train.py) | Tác vụ huấn luyện độc lập được worker thực thi |
| [data.yaml](data.yaml) | Cấu trúc dữ liệu và tên lớp mẫu |
| [requirements-client.txt](requirements-client.txt) | Các gói cần cho client đăng ký dữ liệu và gửi tác vụ |
| [requirements.txt](requirements.txt) | Các gói của client và các gói phục vụ suy luận trên máy cục bộ |

Hai script ở thư mục gốc, `scripts/example-yolo12.py` và
`scripts/clearml-yolo12-job.py`, chuyển tiếp đến CLI của dự án này và nhận cùng
các lệnh con. Các tùy chọn trước đây dành cho pipeline cục bộ và HTTP endpoint
đã được thay bằng quy trình register → submit → check → predict ở trên.
`train.py` là điểm vào của tác vụ trên worker; gửi thử nghiệm qua `project.py`
để ghi lại bộ dữ liệu, container và tham số cùng nhau.
