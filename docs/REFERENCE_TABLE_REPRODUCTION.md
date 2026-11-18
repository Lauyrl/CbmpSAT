# Tái tạo Table 2 và Table 3

scripts/run_published_tables.py chạy lại ba thuật toán TSCB, ITPS và NILS trên bộ 113 đồ thị của bài báo, 50 lần với seed khác nhau và giới hạn 600 giây mỗi lần. Chương trình ghi kết quả thô có thể tiếp tục chạy sau khi bị dừng; chỉ sinh bảng khi đủ 16.950 lượt chạy thành công.

## Chuẩn bị NILS, ITPS và dữ liệu

Chạy từ thư mục gốc repo:

~~~bash
python3 -m pip install scipy
mkdir -p /tmp/cbmp-reference
git clone https://github.com/thetopjiji/NILS.git /tmp/cbmp-reference/NILS
git clone https://github.com/thetopjiji/ITPS.git /tmp/cbmp-reference/ITPS
unzip -q /tmp/cbmp-reference/ITPS/instances.zip -d /tmp/cbmp-reference
g++ /tmp/cbmp-reference/NILS/BCP_main.cpp \
    /tmp/cbmp-reference/NILS/BCP_c_LS.cpp \
    /tmp/cbmp-reference/NILS/BCP_mem.cpp \
    /tmp/cbmp-reference/NILS/BCP_X.cpp \
    -O3 -lm -Wall -o /tmp/cbmp-reference/NILS/BCP_1
python3 - <<'PY'
from pathlib import Path

source = Path("/tmp/cbmp-reference/ITPS/BCP_irace.cpp")
compat = Path("/tmp/cbmp-reference/ITPS/BCP_irace_compat.cpp")
compat.write_text(
    "".join(line for line in source.read_text(encoding="utf-8").splitlines(True)
            if line.strip() != "ç"),
    encoding="utf-8",
)
PY
g++ -std=c++98 /tmp/cbmp-reference/ITPS/BCP_irace_compat.cpp \
    -O3 -lm -Wall -o /tmp/cbmp-reference/ITPS/BCP
~~~

Bản ITPS hiện có một dòng chứa ký tự lạc ç và tên biến toàn cục exchange xung đột với thư viện C++ mới. Đoạn trên tạo bản tương thích riêng để biên dịch, không sửa file nguồn đã clone.

## Chuẩn bị TSCB

TSCB là phần cần có thêm trước khi chạy đủ ba thuật toán. Trang tải mã nguồn cũ được trích dẫn trong bài báo hiện không truy cập được, nên TSCB không được chép hoặc thay bằng mã giả trong repo. Cần có executable TSCB tương thích với các file .rnd.

Runner nhận lệnh TSCB dưới dạng mẫu. Các placeholder {instance}, {seed}, {rep}, {lower_bound} và {time_limit} được thay bằng giá trị của lượt chạy. Ví dụ mẫu dưới đây giả định TSCB nhận -i, --seed và --time-limit; thay các cờ đó theo CLI thực tế của executable. Hai regex phải có nhóm bắt thứ nhất lần lượt là best cost và thời gian tìm được best cost (giây):

~~~text
--tscb-command '/absolute/path/to/tscb -i {instance} --seed {seed} --time-limit {time_limit}'
--tscb-cost-regex 'best_cost=([0-9]+)'
--tscb-time-regex 'time_to_best=([0-9]+(?:\.[0-9]+)?)'
~~~

Regex được áp dụng trên cả stdout và stderr của TSCB. Không có cách tự chọn regex hoặc tham số lệnh chính xác cho bản TSCB chưa có sẵn; hãy đối chiếu với bản executable bạn dùng.

## Chạy lại

Sau khi chuẩn bị TSCB, chạy lệnh dưới đây từ thư mục gốc repo và thay ba giá trị TSCB mẫu theo phần trên:

~~~bash
python3 scripts/run_published_tables.py \
  --instances-dir /tmp/cbmp-reference/instances \
  --nils-bin /tmp/cbmp-reference/NILS/BCP_1 \
  --itps-bin /tmp/cbmp-reference/ITPS/BCP \
  --tscb-command '/absolute/path/to/tscb -i {instance} --seed {seed} --time-limit {time_limit}' \
  --tscb-cost-regex 'best_cost=([0-9]+)' \
  --tscb-time-regex 'time_to_best=([0-9]+(?:\.[0-9]+)?)'
~~~

Chạy thử một instance trước khi chạy toàn bộ:

~~~bash
python3 scripts/run_published_tables.py \
  --instances-dir /tmp/cbmp-reference/instances \
  --nils-bin /tmp/cbmp-reference/NILS/BCP_1 \
  --itps-bin /tmp/cbmp-reference/ITPS/BCP \
  --algorithms TSCB ITPS NILS --family path --limit 1 --reps 1 \
  --tscb-command '/absolute/path/to/tscb -i {instance} --seed {seed} --time-limit {time_limit}' \
  --tscb-cost-regex 'best_cost=([0-9]+)' \
  --tscb-time-regex 'time_to_best=([0-9]+(?:\.[0-9]+)?)'
~~~

Lệnh thử chỉ ghi dữ liệu thô, không tạo bảng. Lần chạy đầy đủ sẽ tự bỏ qua các lượt đã hoàn tất trong cùng file CSV; dùng --overwrite nếu muốn chạy lại từ đầu. Dữ liệu lưu tại results/tables/reproduced/benchmark_runs.csv. Khi đủ lượt chạy, runner tạo:

- reproduced_table2.csv và .tex
- reproduced_table3.csv và .tex
- per_instance_metrics.csv
- published_comparison.csv — đối chiếu với CSV tham chiếu đã lưu trong results/tables/reference/

Nếu đã có đủ dữ liệu thô và chỉ cần dựng lại bảng:

~~~bash
python3 scripts/run_published_tables.py --aggregate-only
~~~

Chạy tuần tự theo điều kiện bài báo có thể mất nhiều ngày; thời gian thực tế phụ thuộc máy và thời gian dừng sớm của từng thuật toán. Table 3 trong nguồn in tổng số instance là 185 dù tám hàng cộng lại thành 113; bảng tái tạo dùng tổng 113 và file đối chiếu sẽ đánh dấu khác biệt này.

## Cách tính và nguồn tham chiếu

- benchmark_manifest.csv ghi tên 113 file đầu vào, nhóm đồ thị, cận dừng của thuật toán, cận dùng tính RMSE và mục tiêu best-known dùng tính % Best. Các giá trị cho đồ thị Harwell–Boeing phân biệt cận dưới/lời giải đã biết; xem chính file manifest khi kiểm tra từng instance.
- Table 2 lấy trung bình trên các đồ thị trong mỗi nhóm: best cyclic bandwidth trung bình 50 lần, thời gian trung bình để đạt best, trung bình RMSE theo instance, và phần trăm instance đạt mục tiêu best-known.
- Table 3 kiểm định riêng 50 best-cost mỗi instance bằng Shapiro–Wilk, Bartlett, ANOVA hoặc Welch; nếu dữ liệu không chuẩn thì Kruskal–Wallis. Mức ý nghĩa là 0,05. Dấu + nghĩa NILS tốt hơn, - nghĩa NILS kém hơn, * nghĩa chưa thấy khác biệt có ý nghĩa.
- CSV trong results/tables/reference/ là số đã công bố để đối chiếu; không được dùng làm kết quả đầu vào của lần chạy lại.
