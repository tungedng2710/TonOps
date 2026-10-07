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

## 8. Câu hỏi thường gặp

### Có cần tất cả code và dữ liệu lưu trên server triển khai TonOps không?

Không. Máy chạy các dịch vụ TonOps, máy chứa dữ liệu và máy huấn luyện có thể
là các máy khác nhau. Chúng cần kết nối được đến các dịch vụ liên quan và có
thông tin xác thực phù hợp.

| Thành phần | Có thể đặt ở đâu? |
| --- | --- |
| Mã nguồn dự án | Máy của người dùng hoặc Git repository; ví dụ này gửi bản mã huấn luyện kèm tác vụ để worker thực thi |
| Dữ liệu gốc | Máy của người dùng, ổ đĩa dùng chung hoặc hệ thống lưu trữ của nhóm |
| Bộ dữ liệu đã đăng ký và checkpoint đã tải lên | RustFS hoặc nơi lưu trữ artifact được cấu hình; có thể triển khai riêng với server TonOps |
| Tiến trình huấn luyện | Máy GPU của người dùng hoặc worker GPU trên một máy khác |
| Thông tin thử nghiệm | Các dịch vụ TonOps quản lý trạng thái tác vụ, tham số, log, chỉ số và liên kết đến dữ liệu/mô hình |

Trong quy trình dùng hàng đợi của hướng dẫn này, `register` tải một bản dữ liệu
đã được quản lý phiên bản lên nơi lưu trữ. Worker lấy bản đó bằng Dataset ID
và tải mã huấn luyện từ tác vụ. Bạn không cần chép thủ công toàn bộ dự án và
dữ liệu gốc vào thư mục trên server TonOps. Docker image cũng phải có sẵn trên
máy worker hoặc trong registry mà worker truy cập được.

Nếu chạy trực tiếp trên máy của mình, bạn có thể đọc dữ liệu từ ổ đĩa cục bộ
và dùng TonOps để theo dõi thử nghiệm. Dữ liệu gốc không tự động được đăng ký
chỉ vì bạn bắt đầu huấn luyện; việc đăng ký bộ dữ liệu và tải kết quả lên là
các thao tác riêng trong ví dụ.

### Nếu người dùng muốn huấn luyện tại máy của họ thì sao?

Có hai cách, tùy bạn muốn chạy mã trực tiếp hay để agent quản lý việc thực thi.

**Chạy trực tiếp và theo dõi kết quả bằng TonOps.** Cấu hình tài khoản và địa
chỉ server trong `~/clearml.conf` như bước 1. Cài PyTorch hỗ trợ CUDA phù hợp
với máy của bạn, rồi cài các gói của ví dụ và chạy mã huấn luyện:

```bash
source .venv/tonops-example/bin/activate
python -m pip install -r examples/vehicle_detection_yolo12/requirements.txt
python examples/vehicle_detection_yolo12/train.py \
  --data /path/to/vehicles/data.yaml --epochs 1 --imgsz 320 --batch 2
```

Tệp YAML ở đây phải trỏ đúng đến dữ liệu trên máy của bạn; đặt `path` thành
đường dẫn gốc thực tế của bộ dữ liệu. Lệnh `train.py` không có tùy chọn
`--dataset-root`. Nếu muốn tải một phiên bản đã đăng ký, thay
`--data /path/to/vehicles/data.yaml` bằng `--dataset-id "$TONOPS_DATASET_ID"`.

Huấn luyện diễn ra trên máy của bạn. Script tạo tác vụ trong dự án
`Vehicle Detection/YOLO12`, gửi log/chỉ số đến TonOps và tải artifact cùng
checkpoint lên nơi lưu trữ đã cấu hình. Cách này không cần ClearML Agent,
Docker hoặc hàng đợi. `train.py` hiện yêu cầu GPU NVIDIA có CUDA và sử dụng
GPU số `0` mà tiến trình nhìn thấy.

**Chạy agent trên máy của mình.** Nếu muốn dùng cùng quy trình hàng đợi và
Docker như các worker khác, cài agent và build image trên máy của bạn theo
[hướng dẫn worker GPU](../../docs/clearml-gpu-worker.md). Dùng một hàng đợi
riêng để chủ động chọn máy huấn luyện:

```bash
python scripts/clearml-gpu-worker.py start --queue my-gpu --gpus 0 --detached
python examples/vehicle_detection_yolo12/project.py submit \
  --project "$TONOPS_PROJECT" --queue my-gpu \
  --dataset-id "$TONOPS_DATASET_ID" --epochs 1 --imgsz 320 --batch 2 \
  --output-uri "$TONOPS_OUTPUT_URI" --wait
```

Chỉ cho agent trên máy của bạn nhận tác vụ từ `my-gpu` nếu muốn tác vụ chạy
đúng tại máy đó. Server TonOps quản lý tác vụ; máy có agent thực hiện huấn luyện.

### Vì sao đã gửi tác vụ nhưng máy của tôi chưa bắt đầu huấn luyện?

`project.py submit` tạo tác vụ và đưa vào hàng đợi. Nó không tự khởi động
worker hoặc chạy huấn luyện trong tiến trình client. Kiểm tra **Workers &
Queues** hoặc chạy `project.py workers` để xác nhận có worker đang hoạt động
và nhận đúng hàng đợi. Nếu nhiều worker cùng nhận một hàng đợi, một worker
khác có thể lấy tác vụ; dùng hàng đợi riêng khi cần chọn máy cụ thể.

### Có thể chỉ dùng dữ liệu trên máy của tôi mà không tải lên RustFS không?

Có, với cách chạy trực tiếp bằng `train.py --data /path/to/vehicles/data.yaml`.
Máy huấn luyện đọc ảnh và nhãn từ đường dẫn cục bộ. Các artifact và checkpoint
mà script tải lên vẫn cần nơi lưu trữ có thể truy cập được.

Đối với worker trên máy khác hoặc chạy trong Docker, đường dẫn trên máy client
không tự xuất hiện trong môi trường huấn luyện. Cách dùng Dataset ID trong
hướng dẫn giải quyết việc này bằng bản dữ liệu đã đăng ký. Nếu dùng ổ đĩa
chung, bạn cần tự cấu hình quyền truy cập, mount vào container và đường dẫn
YAML tương ứng.

### Máy người dùng cần kết nối đến dịch vụ nào của TonOps?

Máy gửi tác vụ hoặc máy huấn luyện cần truy cập API để xác thực và cập nhật
tác vụ. Máy tải dữ liệu, mô hình hoặc kết quả cần truy cập nơi lưu trữ tương
ứng, chẳng hạn RustFS hoặc Files server. Người dùng truy cập Web để xem và
quản lý thử nghiệm. Các cổng mặc định trong hướng dẫn là API `7862`, Web
`7861`, Files `7863` và RustFS S3 `7868`; dùng địa chỉ/cổng thực tế của hệ thống.

Nếu server nằm trên máy khác, thay `localhost` bằng hostname hoặc IP truy cập
được từ máy của bạn. Cấu hình API và thông tin xác thực lưu trữ trên từng máy
client/worker cần dùng các dịch vụ đó; cấu hình trên server không tự cấu hình
các máy người dùng.

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
