# AI Agent Decision Log

Nhật ký ghi lại các quyết định thiết kế và tối ưu kỹ thuật quan trọng trong quá trình triển khai Lab 27 Game Day.

---

## Decision 1: Robust Type & Freshness Validation in Data Contracts
- **Hypothesis**: Việc chỉ ép kiểu ngầm qua `pd.to_numeric(errors='coerce')` sẽ nuốt chửng các lỗi trôi kiểu dữ liệu (type drift) và không bắt được sự cố dữ liệu quá hạn (stale data) tại tầng ingestion.
- **Prompt / request to agent**: Nâng cấp `src/contract_validator.py` để hỗ trợ kiểm tra kiểu dữ liệu tường minh (`integer`, `number`, `datetime`, `boolean`), kiểm tra SLA độ tươi (`freshness`) theo phút, và phân loại severity (`critical`, `warning`) cùng hành động vận hành (`block`, `quarantine`, `warn`).
- **Agent proposal**: Bổ sung hàm kiểm tra `type` theo từng kiểu dữ liệu khai báo, tích hợp `freshness` check so sánh max timestamp với `UTC now()`, và bổ sung hàm `determine_action(issues)`.
- **Evidence / test**:
  - `pytest tests_public/test_contracts.py` pass 5/5 tests (bao gồm `test_type_drift_is_detected` và `test_stale_data_fails_freshness`).
  - Great Expectations bắt chính xác duplicate PK và trả về action `BLOCK / QUARANTINE`.
- **Accept / reject / revise**: **Accept**.
- **Why**: Đảm bảo pipeline chặn đứng dữ liệu sai định dạng ngay tại ranh giới ingestion trước khi lan xuống các mô hình dbt downstream.

---

## Decision 2: Context-Aware Anomaly Detection with Robust MAD
- **Hypothesis**: Phương pháp Z-score truyền thống rất nhạy cảm với outliers trong lịch sử và dễ báo động giả khi dữ liệu có tính chu kỳ tuần (seasonality giữa ngày trong tuần và cuối tuần).
- **Prompt / request to agent**: Nâng cấp `observability/anomaly.py` để xử lý triệt để trường hợp `mad == 0` (lịch sử không biến thiên) và tự động nhận diện ngữ cảnh (`day_of_week`, `same_segment_history`, `known_event`).
- **Agent proposal**: Sử dụng Median Absolute Deviation (MAD) với hệ số `0.6745`, xử lý fallback Mean Absolute Deviation khi `mad == 0`, và ưu tiên segment history cùng thứ trong tuần khi gọi `method="auto"`.
- **Evidence / test**:
  - `test_mad_detector_handles_zero_mad` và `test_auto_context_with_segment_history` đều pass.
  - Khi inject fault `volume_drop` (150 rows), detector kích hoạt anomaly chính xác (`score = 5.53 > 3.5`).
- **Accept / reject / revise**: **Accept**.
- **Why**: Giảm thiểu False Positive vào các ngày cuối tuần khi volume thấp tự nhiên, đồng thời duy trì độ nhạy cao với các đợt sụt giảm đột ngột (partial ingestion).

---

## Decision 3: dbt Data Tests & Native Unit Testing for SCD Join Inflation
- **Hypothesis**: Bảng `stg_customers` có cấu trúc SCD Type 2 (`valid_from`, `valid_to`). Nếu join `stg_orders` với `stg_customers` mà không ràng buộc thời gian, một khách hàng có nhiều bản ghi active sẽ làm nhân đôi doanh thu mà không hề phát sinh lỗi SQL.
- **Prompt / request to agent**: Viết dbt unit test nhỏ nhất để expose hiện tượng revenue inflation và bổ sung singular test đối soát doanh thu.
- **Agent proposal**: Tạo `dbt_project/models/marts/unit_tests.yml` kiểm thử model `fct_daily_revenue` với fixture input, đồng thời tạo test `dbt_project/tests/assert_revenue_reconciliation.sql` đối chiếu tổng doanh thu giữa mart và completed orders tại staging.
- **Evidence / test**:
  - `dbt build` chạy thành công 18/18 artifacts (1 seed, 1 table, 12 data tests, 1 unit test, 2 views).
- **Accept / reject / revise**: **Accept**.
- **Why**: Kết hợp giữa unit test (kiểm tra logic chuyển đổi code) và data test (kiểm tra chất lượng dữ liệu thực tế) bảo vệ pipeline toàn diện.

---

## Decision 4: Google SRE Multi-Window Multi-Burn-Rate Alerting
- **Hypothesis**: Sử dụng một khung thời gian đơn lẻ để cảnh báo SLO sẽ gây ra tiếng ồn (alert fatigue) khi có spike ngắn hạn hoặc cảnh báo quá muộn khi ngân sách lỗi bị đốt nhanh liên tục.
- **Prompt / request to agent**: Cài đặt `evaluate_multiwindow_burn()` theo nguyên lý Google SRE Workbook.
- **Agent proposal**:
  - Sustained fast burn (`short >= 14.4` và `long >= 14.4`) $\rightarrow$ `page=True`, `severity="critical"`.
  - Sustained slow burn (`short >= 6.0` và `long >= 6.0`) $\rightarrow$ `page=True`, `severity="warning"`.
  - Transient spike (`short >= 6.0` nhưng `long < 6.0`) $\rightarrow$ `page=False`, ghi nhận warning/info không page on-call.
- **Evidence / test**:
  - `test_multiwindow_burn_sustained_fast_burn_pages` (pass) và `test_multiwindow_burn_transient_spike_does_not_page` (pass).
- **Accept / reject / revise**: **Accept**.
- **Why**: Cân bằng tối ưu giữa việc phát hiện sự cố nghiêm trọng kịp thời và bảo vệ kỹ sư trực on-call khỏi báo động giả.

---

## Decision 5: Transitive Column-Level Lineage BFS Traversal
- **Hypothesis**: Starter code chỉ trả về direct children ở cấp cột, khiến việc phân tích phạm vi ảnh hưởng (blast radius) khi một cột gốc bị lỗi (như `raw_orders.amount`) không tìm ra được các thuộc tính đích ở tầng báo cáo (`ceo_revenue_dashboard.revenue`).
- **Prompt / request to agent**: Cài đặt thuật toán duyệt BFS cho `get_column_downstream` trong `observability/lineage.py`.
- **Agent proposal**: Triển khai hàng đợi BFS với tập `seen` để trả về danh sách transitive downstream columns theo đúng thứ tự phụ thuộc.
- **Evidence / test**:
  - `test_transitive_column_downstream` pass: `raw_orders.amount` $\rightarrow$ `stg_orders.amount_usd` $\rightarrow$ `fct_daily_revenue.daily_revenue` $\rightarrow$ `ceo_revenue_dashboard.revenue`.
- **Accept / reject / revise**: **Accept**.
- **Why**: Giúp kỹ sư xác định chính xác tất cả các metric/chart/dashboard bị sai lệch khi có sự cố schema hoặc giá trị ở tầng upstream.
