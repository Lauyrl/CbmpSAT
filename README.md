# Cyclic Bandwidth Minimization Problem (CBMP) Solver

A research and evaluation repository for solving the **Cyclic Bandwidth Minimization Problem (CBMP)** on undirected graphs using Boolean Satisfiability (SAT), Constraint Programming (OR-Tools CP-SAT), and Mixed Integer Linear Programming (IBM ILOG CPLEX via DOcplex).

---

## 1. Cài đặt (Installation)

### Yêu cầu hệ thống
- Python 3.10+; môi trường chạy gần nhất đã xác minh: Python 3.12.16 trên macOS 15.7.4 arm64 (Apple M4, RAM 16 GB).
- Bộ giải SAT: `pysat` (tích hợp CaDiCaL 195, Glucose 4, MapleChrono, MiniSat 2.2, Lingeling).
- CP-SAT: `ortools`.
- MIP: `docplex` và `cplex` (Community Edition giới hạn <= 1000 biến & ràng buộc hoặc bản thương mại/học thuật đầy đủ).
- CP Optimizer (tùy chọn): `docplex.cp` (IBM CPLEX CP Optimizer).
- Gurobi (tùy chọn): `gurobipy` (yêu cầu bản quyền thương mại/học thuật).

### Khởi tạo môi trường ảo và cài đặt thư viện
```bash
# Tạo môi trường ảo
python3 -m venv .venv
source .venv/bin/activate

# Cài đặt các gói theo requirements.txt (đã ghim phiên bản chuẩn)
pip install -r requirements.txt
```

Các phiên bản quan sát được trong môi trường chạy gần nhất (không phải tất cả đều được ghim cứng trong `requirements.txt`):
- `python-sat==1.9.dev21`, `scipy==1.18.1`, `numpy==2.4.6`
- `ortools==9.15.6755`, `docplex==2.32.264`, `cplex==22.2.0.0`
- `pytest==9.2.0`, `pyyaml==6.0.3`
- `pandas==2.3.3`, `matplotlib==3.11.2`, `networkx==3.7`, `cnsplots==0.8.0`

Lưu ý: `results/env.json` lưu metadata của snapshot kết quả mới nhất. Không trộn kết quả từ các commit hoặc working tree khác nhau.

---

## 2. Cấu trúc thư mục (Directory Structure)

```
CBMP/
├── cbmp.py                 # Core SAT encoding & giải thuật lặp thu hẹp Cyclic Bandwidth
├── main.py                 # CLI giải 1 instance với timeout & multiprocessing isolation
├── sat_encodings.py        # Các mệnh đề CNF (Order và Pairwise encodings, phá đối xứng, cyclic edge)
├── alo_amo_eo_encodings.py # Các chiến lược ALO/AMO/EO (commander, pairwise, binary, sequential, product)
├── graph_utils.py          # Chuẩn hóa đồ thị, load MTX, độc lập kiểm định nghiệm & băng thông vòng
├── baselines/
│   ├── cpsat_cbmp.py       # Baseline OR-Tools CP-SAT
│   ├── cplex_cbmp.py       # Baseline IBM CPLEX MIP
│   ├── cplex_cp_cbmp.py    # Baseline IBM CPLEX CP Optimizer
│   └── gurobi_cbmp.py      # Baseline Gurobi MIP
├── experiments/
│   ├── configs.yaml        # Cấu hình các nhóm thực nghiệm (per_dataset, solvers, methods, ablation, encodings, exact_solvers)
│   └── run_experiments.py # Trình điều khiển thực nghiệm (deduplication, resuming, canonical keys, runner)
├── analysis/
│   ├── make_tables.py      # Sinh bảng CSV/LaTeX từ results/runs.jsonl
│   └── make_plots.py       # Sinh cactus plots và CNSPlots encoding comparison
├── datasets/               # Thư mục chứa ma trận đồ thị MatrixMarket (.mtx)
├── scripts/
│   ├── check_datasets.py   # Kiểm tra và cảnh báo nếu dataset trong config bị thiếu
│   ├── calibrate.py        # Thử nghiệm hiệu chuẩn thời gian và tài nguyên
│   └── make_subgraphs.py   # Tạo các đồ thị con cảm ứng liên thông
├── tests/                  # Bộ test tự động (brute force, baselines, mocked CP/Gurobi, encodings)
├── results/                # Snapshot hiện hành: runs.jsonl, env.json, tables/, figures/
├── docs/                   # Provenance của snapshot hiện tại
├── report/                 # Báo cáo khoa học LaTeX và template
├── requirements.txt
├── pytest.ini
└── README.md
```

---

## 3. Cách chạy `main.py` cho 1 instance

`main.py` nhận tên dataset (trong thư mục `datasets/`) hoặc đường dẫn file `.mtx`:

```bash
# Chạy với cấu hình tốt nhất (Rotation + Reflection symmetry breaking, Heuristic UB, CaDiCaL 195)
python main.py 30_bus --symmetry-break --heuristic-ub --timeout 60

# Chạy không dùng phá đối xứng và không dùng heuristic (trivial bound N//2+1)
python main.py 30_bus --timeout 60

# Chọn solver SAT khác (glucose4, maplechrono, minisat22, lingeling)
python main.py 30_bus --symmetry-break --solver glucose4 --timeout 60

# Lưu kết quả ra file JSON line
python main.py 30_bus --symmetry-break --heuristic-ub --timeout 60 --json-out results/single_run.jsonl
```

### Các cờ chính của `main.py`:
- `dataset`: Tên file (ví dụ `30_bus` hoặc `datasets/30_bus.mtx`).
- `--timeout`: Thời gian tối đa (giây), mặc định: 600.
- `--encoding`: Lựa chọn mã hóa SAT (`order` hoặc `pairwise`, mặc định: `order`).
- `--solving-mode`: Chế độ tìm kiếm SAT (`incremental` hoặc `iterative`, mặc định: `incremental`).
- `--eo-strategy`: Chiến lược mã hóa Exactly-One (`commander`, `pairwise`, `binary`, `sequential`, `product`, mặc định: `commander`).
- `--symmetry-break`: Bật cả phá đối xứng quay (`--sb-rotation`) và đối xứng gương (`--sb-reflection`).
- `--heuristic-ub`: Sử dụng nhãn xuất phát từ thuật toán Cuthill-McKee để khởi tạo cận trên.
- `--solver`: Trình giải SAT (mặc định: `cadical195`).
- `--json-out`: Đường dẫn file để ghi kết quả dưới dạng JSON line.

---

## 4. Kiểm tra dữ liệu (Dataset Validation)

Trước khi chạy thực nghiệm, bạn có thể kiểm tra xem tất cả các dataset được tham chiếu trong file cấu hình đã tồn tại hay chưa:

```bash
python scripts/check_datasets.py --config experiments/configs.yaml --dataset-dir datasets
```

Nếu thiếu file (ví dụ chưa có `14_bus.mtx`), script sẽ báo lỗi rõ ràng và liệt kê chính xác các file cần bổ sung.

---

## 5. Chạy thực nghiệm (Running Experiments)

Các kết quả được lưu tập trung trong `results/runs.jsonl`. Snapshot mới nhất hiện có ba group: `encodings`, `exact_solvers`, và `solvers_medium`. Các group khác còn được định nghĩa trong `experiments/configs.yaml`, nhưng chưa có record trong snapshot hiện tại; cấu hình không đồng nghĩa với kết quả đã chạy.

### Các nhóm có kết quả hiện tại

```bash
# Order Encoding vs Pairwise Encoding trên bốn đồ thị nhỏ
python experiments/run_experiments.py --group encodings --timeout 600

# So sánh sáu formulation: SAT Order, SAT Pairwise, CP-SAT,
# CPLEX MIP, CPLEX CP Optimizer, và Gurobi
python experiments/run_experiments.py --group exact_solvers --timeout 600

# So sánh năm SAT solvers trên bốn đồ thị trung bình (N=60, 80)
python experiments/run_experiments.py --group solvers_medium --timeout 600
```

### Kiểm soát resume và metadata

```bash
# Xem trước kế hoạch
python experiments/run_experiments.py --dry-run

# Ghi commit, timeout và cấu hình vào metadata
python experiments/run_experiments.py --group exact_solvers --record-metadata

# Tiếp tục từ các record tương thích trong results/runs.jsonl
python experiments/run_experiments.py --group all --resume

# Chỉ chạy lại record thất bại hoặc chưa có nghiệm incumbent hợp lệ
python experiments/run_experiments.py --group all --resume --retry-failed
```

Mỗi record ghi lại trạng thái solver riêng biệt. `OPTIMAL` nghĩa là đã chứng minh tối ưu; `FEASIBLE` chỉ có nghiệm khả thi; `TIMEOUT` là hết thời gian; `SIZE_LIMIT` là giới hạn kích thước của solver; `UNAVAILABLE` là solver không khả dụng. Không chuyển các trạng thái này thành cùng một loại kết quả.

## 6. Sinh bảng biểu và đồ thị (Analysis & Visualization)

Các bảng và đồ thị phải được sinh từ duy nhất `results/runs.jsonl`. Chạy:

```bash
python analysis/make_tables.py results/runs.jsonl --output-dir results/tables
python analysis/make_plots.py results/runs.jsonl --output-dir results/figures
```

Các bảng của snapshot hiện tại:

- `table_encoding_comparison.csv`: kết quả theo từng dataset của Order và Pairwise Encoding, lấy SAT records từ cả hai group `encodings` và `exact_solvers`.
- `table_encoding_comparison_pairs.csv`: đối chiếu cặp Order/Pairwise; chỉ tính runtime ratio khi hai encoding chứng minh cùng optimum.
- `table_exact_solvers.csv`: từng run trong nhóm `exact_solvers`, giữ riêng `OPTIMAL`, `FEASIBLE`, `SIZE_LIMIT`, và `UNAVAILABLE`.
- `table_solvers_medium.csv`: kết quả 5 SAT solvers trên bốn medium subgraphs.

Các lần chạy hiện tại chưa có dữ liệu cho ablation, randomized-label family, phase decomposition, small-solver comparison, hay SAT-vs-CP-SAT trên full-size graphs. Script phân tích có thể hỗ trợ các nhóm này khi có record tương ứng, nhưng không được xem file output cũ hoặc cấu hình trong YAML là bằng chứng rằng nhóm đã chạy.

`make_plots.py` dùng CNSPlots để tạo hình so sánh Order/Pairwise từ các nghiệm `OPTIMAL` hợp lệ; đồng thời tạo cactus plot cho nhóm medium và exact solvers nếu có dữ liệu phù hợp. Không tái sử dụng hình không được sinh từ snapshot hiện tại.

---

## 7. Trạng thái kết quả hiện tại (Current Results)

Nguồn dữ liệu mới nhất được theo dõi trong nhánh này là:

- `results/runs.jsonl`: 44 record duy nhất.
- `results/env.json`: metadata môi trường của snapshot.
- `results/tables/`: bảng được tạo từ raw records hiện tại.
- `results/figures/`: hình được tạo từ raw records hiện tại bằng `analysis/make_plots.py`.

Thành phần 44 record: **24 OPTIMAL, 12 TIMEOUT, 4 UNAVAILABLE, 3 SIZE_LIMIT, 1 FEASIBLE**. Group memberships là `exact_solvers` (24), `solvers_medium` (20), và `encodings` (4); các group có overlap nên không cộng số lượng memberships để tính số record duy nhất.

Tám dataset có kết quả trong snapshot: `14_bus`, `30_bus`, `494_bus_n40`, `662_bus_n40`, `494_bus_n60`, `662_bus_n60`, `494_bus_n80`, và `662_bus_n80`. Mỗi dataset/formulation chỉ có một run; không báo cáo median, confidence interval, hay significance test từ các record đơn lẻ.

**Giới hạn phạm vi hiện tại:** các full matrices `494_bus` và `662_bus` có trong `datasets/` nhưng chưa có run trong snapshot mới nhất. Vì vậy chưa thể kết luận khả năng mở rộng trên full-size graphs từ kết quả hiện có. Gurobi được ghi là `UNAVAILABLE`; CPLEX MIP bị `SIZE_LIMIT` trên ba trong bốn instance; một run CPLEX CP chỉ đạt `FEASIBLE`, chưa chứng minh tối ưu.

## 7.1 Cập nhật kết quả

1. Chạy các nhóm cần thiết trong `experiments/configs.yaml`.
2. Ghi metadata bằng `--record-metadata`.
3. Kiểm tra trạng thái và nghiệm trong `results/runs.jsonl`.
4. Sinh lại bảng và hình từ chính file raw mới nhất.
5. Không giữ file bảng/hình cũ khi raw input đã thay đổi; kiểm tra chúng có tương ứng với dữ liệu mới trước khi commit.

## 8. Chạy kiểm thử tự động (Running Tests)

Toàn bộ các thuật toán và mô hình được kiểm thử tự động bằng `pytest`:

```bash
# Chạy bộ test tiêu chuẩn (loại bỏ các bài test nặng, hoàn thành trong ~3 giây)
pytest -q -m "not slow"

# Chạy đầy đủ cả các bài test exhaustive graph atlas (1..7 đỉnh, ~60 giây)
pytest -q

# Chạy riêng từng file test:
pytest tests/test_correctness.py -v   # Tính đúng đắn của SAT encoding & phá đối xứng
pytest tests/count_solutions.py -v     # Kiểm chứng số lượng nghiệm và phá đối xứng lý thuyết
pytest tests/test_baselines.py -v     # Kiểm thử CP-SAT & CPLEX baselines
pytest tests/test_experiments.py -v   # Kiểm thử lập kế hoạch, tổng hợp số liệu
pytest tests/test_graph_atlas.py -v   # Đối chiếu toàn diện 1.252 đồ thị với Brute Force
```

---

## 9. Biên dịch báo cáo khoa học (Compiling the Scientific Report)

Báo cáo khoa học hoàn chỉnh được viết theo định dạng Elsevier CAS Single Column (`cas-sc.cls`) tại thư mục `report/`.

Để biên dịch báo cáo sang định dạng PDF:

```bash
cd report
pdflatex -interaction=nonstopmode report.tex
pdflatex -interaction=nonstopmode report.tex
```

Kết quả biên dịch là `report/report.pdf`. Số trang phụ thuộc nội dung và phiên bản LaTeX; không hard-code số trang trong README. Trước khi nộp, cần biên dịch sạch và kiểm tra các bảng/hình được sinh từ đúng bộ raw results đã lưu trữ.

---

## 10. Provenance

`docs/EXPERIMENT_PROVENANCE.md` mô tả duy nhất snapshot kết quả hiện tại, cấu hình thí nghiệm có record, và giới hạn độ bao phủ. Nhánh này không lưu các phase archive hoặc các bản raw results lịch sử.

