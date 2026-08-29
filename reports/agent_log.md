# AI Agent Decision Log — Lab 27 Data Reliability Game Day

Nhật ký ghi lại các quyết định kỹ thuật cốt lõi trong quá trình cộng tác giữa Kỹ sư (Học viên) và AI Coding Agent. Mọi quyết định đều tuân thủ chu trình: **Hypothesis → Prompt → Proposal → Empirical Evidence → Decision → Engineering Rationale**.

---

## Decision 1: Type Coercion vs Strict Contract & Freshness Enforcement
- **Hypothesis**: Việc sử dụng `pd.to_numeric(errors='coerce')` ngầm định ở starter code sẽ che giấu các lỗi trôi kiểu dữ liệu (ví dụ số thực lọt vào cột mã định danh nguyên `order_id`), đồng thời không có cơ chế phát hiện dữ liệu quá hạn (`stale data`) trước khi ghi vào kho.
- **Prompt / request to agent**: Viết bộ quy tắc validate kiểu dữ liệu tường minh (`integer`, `number`, `datetime`, `boolean`, `string`) trong `src/contract_validator.py`, bổ sung kiểm tra SLA độ tươi theo phút dựa trên config YAML, và xác định hành động vận hành (`block`, `quarantine`, `warn`).
- **Agent proposal**: Tạo hàm kiểm tra từng kiểu dữ liệu (dùng modulo số nguyên `numeric % 1 == 0` để chặn float trong int), đo lường độ trễ timestamp so với UTC now, và trả về hành động `block` nếu có lỗi critical.
- **Evidence/test**:
  - `pytest tests_public/test_contracts.py` pass 12/12 tests.
  - Bắt thành công `test_type_drift_float_in_int` (`order_id = [1.25, 2.75]`) và `test_stale_data_fails_freshness` (trễ 180 phút).
- **Accept / reject / revise**: **Accept**.
- **Why**: Chặn đứng dữ liệu rác ngay tại cửa ngõ ingestion thay vì để lỗi lan truyền xuống các mô hình dbt downstream.

---

## Decision 2: Replacing Naive Z-Score with Robust MAD & Seasonality Awareness
- **Hypothesis**: Phương pháp Z-score truyền thống bị vô hiệu hóa khi lịch sử bị nhiễm outlier (Masking effect) và gây báo động giả vào ngày cuối tuần (Seasonality).
- **Prompt / request to agent**: Nâng cấp `observability/anomaly.py` để xử lý triệt để ca biên `mad == 0` (lịch sử hằng số), tự động bóc tách phân đoạn theo thứ trong tuần (`day_of_week`), và hỗ trợ sự kiện đặc biệt (`known_event`).
- **Agent proposal**: Ban đầu Agent đề xuất dùng EWMA rolling window. Học viên yêu cầu chỉnh sửa (**Revise**) sang Median Absolute Deviation (MAD với scale `0.6745`) kết hợp `same_segment_history` vì MAD miễn nhiễm với outlier trong lịch sử và dễ giải thích toán học hơn.
- **Evidence/test**:
  - `test_mad_resists_outlier_contamination_in_history`: Khi lịch sử có outlier `5000`, Z-score bị mù ($Z=0.28 < 3.0$) nhưng MAD bắt chính xác điểm dị biệt ($score=50.4 > 3.5$).
  - `test_auto_seasonality_saturday_vs_monday`: 200 đơn vào Thứ 7 là bình thường ($score < 3.5$), nhưng 200 đơn vào Thứ 2 bị gắn cờ bất thường ($score > 3.5$).
- **Accept / reject / revise**: **Accept after Revise**.
- **Why**: Tối ưu hóa độ nhạy phát hiện sụt giảm dữ liệu thực tế (Partial Ingestion) mà không gây báo động giả theo chu kỳ kinh doanh.

---

## Decision 3: Distribution Shift: Two-Sample Kolmogorov-Smirnov Test vs Mean Ratio
- **Hypothesis**: Chỉ so sánh tỷ lệ giá trị trung bình (`mean_ratio`) là không đủ, vì dữ liệu có thể bị biến dạng phân bố nghiêm trọng (phân cực 2 đầu - bimodal) nhưng giá trị trung bình vẫn không đổi.
- **Prompt / request to agent**: Cải tiến `observability/distribution.py` để phát hiện sự thay đổi về hình dạng phân phối giữa tập hiện tại và baseline.
- **Agent proposal**: Triển khai thuật toán kiểm định 2 mẫu phi tham số Kolmogorov-Smirnov (pure numpy CDF distance: $D = \sup |F_{cur}(x) - F_{base}(x)|$) kết hợp cùng tỷ lệ Mean Ratio.
- **Evidence/test**:
  - `test_same_mean_different_distribution_ks_test_catches_shift`: Baseline là Uniform `[1..19]` (Mean=10.0), Current là Bimodal `{0, 20}` (Mean=10.0). Tỷ lệ Mean ratio $= 1.0$ (bỏ sót lỗi), nhưng KS-statistic đạt $0.50 > 0.35$ và bắt trọn anomaly.
- **Accept / reject / revise**: **Accept**.
- **Why**: Nâng cao năng lực giám sát Data Drift cho cả dữ liệu bảng và vector embedding norms.

---

## Decision 4: dbt Transformation Protection: SCD Type 2 Revenue Inflation & Unit Testing
- **Hypothesis**: Bảng `stg_customers` có cấu trúc SCD Type 2. Phép join `stg_orders` với `stg_customers` không kèm khoảng thời gian hiệu lực `valid_from/valid_to` sẽ làm nhân bản bản ghi khi một khách hàng có nhiều active version, dẫn đến thổi phồng doanh thu mà không phát sinh lỗi SQL.
- **Prompt / request to agent**: Viết dbt unit test nhỏ nhất cô lập failure mode này và bổ sung singular test đối soát doanh thu.
- **Agent proposal**: Tạo `dbt_project/models/marts/unit_tests.yml` với input fixtures giả lập, và tạo singular test `assert_revenue_reconciliation.sql` kiểm tra tổng doanh thu mart so với completed orders ở staging.
- **Evidence/test**:
  - `dbt build` chạy thành công 18/18 artifacts (12 data tests, 1 unit test, 1 singular test).
  - Test đối soát doanh thu phát hiện ngay sai lệch nếu xảy ra hiện tượng duplicate join.
- **Accept / reject / revise**: **Accept**.
- **Why**: Phân tách rõ ràng giữa Data Test (kiểm tra dữ liệu thực tế) và Unit Test (kiểm tra logic chuyển đổi mã nguồn).

---

## Decision 5: Multi-Window Multi-Burn-Rate Alerting Policy (Google SRE Standard)
- **Hypothesis**: Cảnh báo SLO dựa trên một khung thời gian đơn lẻ hoặc giá trị tức thời sẽ dẫn đến "Alert Fatigue" khi gặp các đợt tăng vọt ngắn hạn (transient spike) hoặc cảnh báo quá muộn khi ngân sách lỗi bị bào mòn âm ỉ.
- **Prompt / request to agent**: Cài đặt hàm `evaluate_multiwindow_burn()` theo hướng dẫn trong Google SRE Workbook.
- **Agent proposal**: Thiết lập 3 mức đánh giá:
  1. **Sustained Fast Burn** ($Burn_{short} \ge 14.4 \land Burn_{long} \ge 14.4$): Bắn cảnh báo khẩn cấp (`page=True, severity=critical`).
  2. **Sustained Slow Burn** ($Burn_{short} \ge 6.0 \land Burn_{long} \ge 6.0$): Cảnh báo mức cảnh giác (`page=True, severity=warning`).
  3. **Transient Spike** ($Burn_{short} \ge 6.0 \land Burn_{long} < 6.0$): Ghi log cảnh báo, không page on-call (`page=False`).
- **Evidence/test**:
  - `test_multiwindow_burn_sustained_fast_burn_pages` (Pass).
  - `test_multiwindow_burn_transient_spike_does_not_page` (Pass với `short=16.0, long=2.0`).
- **Accept / reject / revise**: **Accept**.
- **Why**: Đảm bảo phản ứng nhanh trước các sự cố nghiêm trọng đe dọa trực tiếp đến thỏa thuận mức dịch vụ (SLA) mà không làm phiền kỹ sư trực vận hành.

---

## Decision 6: Transitive Column Lineage BFS Traversal & Cycle Prevention
- **Hypothesis**: Starter code chỉ trả về direct children ở cấp cột, khiến việc phân tích phạm vi ảnh hưởng (Blast Radius) khi một trường dữ liệu gốc bị hỏng không thể truy vết đến các metric trên dashboard của Ban Giám Đốc.
- **Prompt / request to agent**: Viết lại `get_column_downstream` trong `observability/lineage.py` hỗ trợ duyệt toàn bộ cây phụ thuộc đa cấp (transitive dependency) và xử lý an toàn nếu đồ thị có chu trình kín (cycle).
- **Agent proposal**: Sử dụng hàng đợi BFS kết hợp tập `seen = {start}` để duyệt tất cả các nút con transitive mà không bị lặp vô tận.
- **Evidence/test**:
  - `test_transitive_column_downstream` pass: Truy vết trọn vẹn `raw_orders.amount → stg_orders.amount_usd → fct_daily_revenue.daily_revenue → ceo_revenue_dashboard.revenue`.
  - `test_cyclic_graph_does_not_infinite_loop` pass mượt mà trên đồ thị chu trình `A → B → C → A`.
- **Accept / reject / revise**: **Accept**.
- **Why**: Cung cấp bức tranh toàn cảnh về tác động nghiệp vụ (Blast Radius) cho Incident Commander khi xảy ra sự cố dữ liệu.
