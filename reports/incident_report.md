# Incident Postmortem: Silent Revenue Distortion & Stale Support Knowledge Base

## Severity
**P1 — High Impact (Financial Reporting & Customer Operations)**

## Summary
Vào ngày Game Day, hệ thống pipeline ETL vẫn báo trạng thái `SUCCESS`, tuy nhiên số liệu trên CEO Revenue Dashboard bị sai lệch nghiêm trọng và Customer Support Agent phản hồi chính sách hoàn tiền cũ cho khách hàng. Qua điều tra dựa trên hệ thống Observability & Data Contracts mới được nâng cấp, đội ngũ đã xác định được 3 sự cố xảy ra đồng thời ở các tầng ingestion, transformation và knowledge base.

---

## Detection
- **Signal 1 (Ingestion Contract)**: Data Contract Validator và Great Expectations phát hiện 3 dòng trùng lặp `order_id` (`duplicate_pk`), vi phạm ràng buộc `unique` với severity `critical`.
- **Signal 2 (Volume Anomaly)**: Statistical Anomaly Detector (MAD / Z-score) kích hoạt cảnh báo khi số lượng bản ghi đơn hàng giảm bất thường từ ~600 xuống còn 150 dòng (`score = 5.53 > 3.5`), dù dữ liệu không vi phạm schema.
- **Signal 3 (RAG / Freshness SLO)**: Thời gian trễ của Knowledge Base tăng lên **190.3 phút** (vượt ngưỡng SLA 60 phút), kích hoạt vi phạm SLO `rag_index_freshness` (target 99.0%).

---

## Root Cause
1. **Lỗi Ingestion Influx (Duplicate Keys)**: Dịch vụ thanh toán upstream retry webhook không kèm idempotency key, làm phát sinh các bản ghi đơn hàng trùng mã `order_id` đi thẳng vào `data/incoming/orders.csv`.
2. **Lỗi Partial Ingestion (Volume Drop)**: Cronjob trích xuất dữ liệu bị timeout giữa chừng, chỉ lưu 25% số lượng đơn hàng (150/600 rows). Do không có schema error nên pipeline truyền thống không thể bắt lỗi nếu không có Statistical Anomaly Detection.
3. **Lỗi Đồng bộ Knowledge Base (Stale KB)**: Pipeline cập nhật tài liệu chính sách chăm sóc khách hàng bị gián đoạn 3 giờ, khiến Vector DB / RAG Index tiếp tục nhúng tài liệu chính sách hoàn tiền đã hết hạn.
4. **Lỗi Join Dimension (SCD Type 2)**: Model dbt `fct_daily_revenue` thực hiện join trực tiếp `stg_orders` với `stg_customers` chỉ theo `customer_id` mà không kiểm tra khoảng hiệu lực `valid_from / valid_to`, dẫn đến nhân đôi doanh thu nếu một khách hàng có nhiều bản ghi active.

---

## Evidence
1. **Contract Failure Log**:
   ```json
   {"check": "unique", "column": "order_id", "severity": "critical", "passed": false, "details": "duplicate_rows=6"}
   ```
2. **Great Expectations Action**:
   ```text
   [FAIL] ExpectColumnValuesToBeUnique (column=order_id)
   Overall GX Result: FAIL -> Action: BLOCK / QUARANTINE
   ```
3. **Anomaly Signal**:
   ```json
   {"is_anomaly": true, "score": 5.53, "method": "auto:mad", "reason": "median=258.000, mad=15.000, threshold=3.5"}
   ```
4. **Freshness & SLO Metric**:
   ```text
   KB freshness minutes: 190.3 (Threshold: 60.0 min, Breached: True)
   RAG SLO Burn Rate: 100.0x, Remaining Budget: 0.0%
   ```

---

## Blast Radius

### Dataset-level Lineage:
```text
[raw_orders] ---> [stg_orders] ---> [fct_daily_revenue] ---> [ceo_revenue_dashboard]
[raw_customers]-> [stg_customers]-/

[kb_documents] -> [kb_active_docs] -> [rag_index] ----------> [support_agent]
```

### Column-level Transitive Lineage:
```text
raw_orders.amount -> stg_orders.amount_usd -> fct_daily_revenue.daily_revenue -> ceo_revenue_dashboard.revenue
kb_documents.content -> kb_active_docs.content -> rag_index.embedding -> support_agent.answer
```

Tài sản bị ảnh hưởng trực tiếp:
- Báo cáo doanh thu Ban Giám Đốc (`ceo_revenue_dashboard`)
- Hệ thống hỗ trợ khách hàng tự động (`support_agent`)

---

## Mitigation
1. **Chặn dữ liệu lỗi tại cửa ngõ**: Bật chế độ `BLOCK / QUARANTINE` trong `contract_validator.py` và Great Expectations Checkpoint để cô lập các batch đơn hàng trùng PK hoặc sai kiểu dữ liệu.
2. **Bổ sung Anomaly Gate**: Thiết lập quy tắc dừng dbt run nếu `detect_metric` trả về `is_anomaly=True` cho chỉ số `row_count`.
3. **Trigger Re-sync Knowledge Base**: Chạy lại pipeline nạp KB với timestamp mới nhất, tái lập chỉ mục Vector RAG.
4. **Sửa Logic dbt SCD Join**: Bổ sung điều kiện lọc thời gian có hiệu lực `order_date between valid_from and coalesce(valid_to, '9999-12-31')` và thêm singular reconciliation test `assert_revenue_reconciliation.sql`.

---

## Recovery
1. Chạy `make reset` để khôi phục snapshot dữ liệu sạch.
2. Chạy `make dbt` để build lại toàn bộ mart tables và thực thi 100% tests.
3. Chạy `make baseline` để thẩm định tất cả chỉ số sức khỏe của pipeline.

---

## Verification
- [x] **Contract healthy**: 0 failed checks, 0 critical failures trên incoming batch sạch.
- [x] **dbt tests healthy**: 18/18 checks pass (bao gồm generic tests, singular reconciliation test và dbt unit test).
- [x] **Anomaly returned to expected range**: MAD / Z-score trong khoảng kiểm soát an toàn.
- [x] **SLO healthy / budget understood**: Burn rate trở về 0.0x, Error budget phục hồi 100%.
- [x] **Downstream output verified**: Dashboard CEO và Support Agent phản hồi đúng số liệu và chính sách mới nhất.

---

## Prevention / Action Items

| Action | Owner | Deadline | Why |
|---|---|---|---|
| Tích hợp Contract Validator vào CI/CD & Airflow Pre-hook | Data Platform | T+3 days | Chặn dữ liệu rác trước khi ghi vào Raw Data Lake |
| Bật Multi-Window Burn Rate Alerting qua PagerDuty | SRE / DevOps | T+5 days | Cảnh báo tức thì khi ngân sách lỗi bị tiêu hao nhanh |
| Chuẩn hóa SCD Type 2 Macro cho dbt models | Analytics Eng | T+7 days | Ngăn ngừa lỗi nhân đôi doanh thu khi join dimensions |
| Tự động hóa kiểm tra Freshness cho RAG Pipeline | AI Ops | T+5 days | Đảm bảo Support Agent không bao giờ sử dụng dữ liệu hết hạn |
