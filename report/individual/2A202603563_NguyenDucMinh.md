# Báo cáo cá nhân — Day 6

Nguyễn Đức Minh · 2A202603563 · L3A

## Dữ liệu và pipeline
- **Chủ đề, nguồn/quyền, số trang và quy tắc tính trang:** *The Elements of Style* (William Strunk Jr., 1920), Project Gutenberg #37134 (https://www.gutenberg.org/ebooks/37134). Gutenberg ghi trạng thái bản quyền là "Public domain in the USA"; file gốc giữ nguyên phần giấy phép Gutenberg. File text không có trang vật lý. Vì vậy phần thân sách (từ "I. INTRODUCTORY" đến bài tập cuối) được gom đoạn theo thứ tự thành **47 đơn vị ≥1.500 ký tự** (tổng 80.797 ký tự). Đơn vị không vượt qua ranh giới chương và không nhân bản nội dung. Chi tiết từng đơn vị nằm trong `data/manifest.json`.
- **Chuẩn hóa, lỗi và giới hạn:** Unicode NFC; CRLF→LF; bỏ ký hiệu nghiêng/đậm của Gutenberg (`_x_`, `=x=`). Đã loại header/giấy phép Gutenberg, trang tựa, mục lục và danh sách sửa lỗi của người chép (`results/logs/ingest_log.txt`). Không có đơn vị rỗng hay ngắn, không cần OCR. Giới hạn: "trang" là đơn vị tự chia nên một mục từ có thể bị tách qua 2 trang (ví dụ mục *However* nằm ở trang 36–37, xem lỗi q19).
- **Embedding, vector store, lệnh chạy và chi phí:** `sentence-transformers/all-MiniLM-L6-v2` chạy local trên CPU (sentence-transformers 5.1.2, torch 2.8.0+cpu), 384 chiều. Query và document dùng cùng cách xử lý: không prefix, chuẩn hóa L2. Vector store là Chroma 1.5.9 `PersistentClient` (`chroma_db/`), HNSW (approximate), metric cosine, mỗi cấu hình một collection. Lệnh chạy: `python src/run.py` (Python 3.9.13, Windows). Chi phí **0 USD**. Tổng thời gian chạy 76 giây, trong đó 56 giây là tải model lần đầu.
- **Nạp lại:** ID của chunk cố định và nạp bằng `upsert`, nên nạp lần 2 cùng phiên bản vẫn giữ 202/188/188 bản ghi, không bị trùng. Nếu tài liệu thay đổi, các ID không còn tồn tại sẽ bị xóa (`results/run_info.json`).
- **Metadata:** trường bắt buộc gồm `document_id`, `source`, `page` (số đơn vị 1–47) và `page_id`. Trường lọc là **`chapter`** (int 1–7) cùng `chapter_title`, lấy từ tiêu đề chương có sẵn trong văn bản, không tự đoán. Lý do chọn `chapter`: cùng một chủ đề xuất hiện ở nhiều chương (ví dụ dấu ngoặc ở Rule 3 và chương IV, *while* ở Rule 4 và chương V), nên lọc theo chương giúp loại các đoạn gần giống nhưng sai phạm vi.

## Cấu hình và benchmark
- **A:** cắt cố định 500 ký tự, overlap 50, trong phạm vi từng trang; không lọc.
- **B:** gộp nguyên đoạn đến tối đa 800 ký tự; mở chunk mới ở mỗi tiêu đề rule hoặc mục từ (ví dụ "Data. …"). Một đoạn dài hơn 800 ký tự được giữ nguyên, không cắt. Không lọc.
- **C:** dùng đúng chunk của B, chỉ thêm `where chapter = <chương người dùng nêu trong câu hỏi>`, và chỉ áp dụng cho các câu có filter. **Khác biệt duy nhất giữa B và C là filter.**
- **Benchmark:** 21 câu (`benchmark/questions.jsonl`) gồm 16 dev và 5 test, chia trước khi chạy. Các loại câu: trực tiếp, diễn đạt lại, điều kiện/ngoại lệ. 4 câu có filter: q14, q15, q16 (dev) và q20 (test). Giá trị filter là chương mà người dùng nêu trong câu hỏi. Evidence được đọc đối chiếu với nguồn, và `src/verify_benchmark.py` kiểm tra từng câu evidence nằm đúng trang gold trước khi truy xuất.
- **Tiêu chí chọn chiến lược (chốt trước khi xem test):** Hit@3 dev cao nhất, sau đó Hit@1 dev, sau đó ít chunk hơn.

## Kết quả
| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian (embed / store / query) | Chi phí |
|---|---|---|---|---|---|---|
| A | dev | 9/16 | 13/16 | 202 | 5,33s / 0,96s / 0,06s | 0 |
| A | test | 2/5 | 3/5 | 202 | (cùng lần chạy) | 0 |
| B | dev | 9/16 | 13/16 | 188 | 5,38s / 0,82s / 0,07s | 0 |
| B | test | 3/5 | 5/5 | 188 | (cùng lần chạy) | 0 |
| C | dev | 9/16 | 13/16 | 188 | 5,49s / 0,76s / 0,09s | 0 |
| C | test | 3/5 | 5/5 | 188 | (cùng lần chạy) | 0 |

| Strategy | Coherence trung bình /2 (n) | Metadata đủ và đúng (n/N) | Filter tuân thủ (n/N) | Grounding 0/1/2 (số câu) và trung bình /2 |
|---|---|---|---|---|
| A | 0,9 (10) | 15/15 | test 0/1 · dev 1/3 | 1 / 1 / 3 → 1,4 |
| B | 1,5 (10) | 15/15 | test 0/1 · dev 1/3 | 0 / 0 / 5 → 2,0 |
| C | 1,5 (10) | 15/15 | test 1/1 · dev 3/3 | 0 / 0 / 5 → 2,0 |

A và B không dùng filter. Cột "filter tuân thủ" của A và B chỉ cho biết top-3 có tình cờ nằm trong chương người dùng yêu cầu hay không.

**Trace, nhãn và cách chọn mẫu:** trace nằm ở `results/traces/trace_{A,B,C}.jsonl`, chỉ số ở `results/metrics.csv`, nhãn ở `results/audit/`.
- Coherence: lấy vị trí ký tự thứ 600 của các trang p01–p10, chốt trước khi xem điểm.
- Grounding và metadata: 5 câu test × top-3.
- Nhãn do AI (Claude) đề xuất, tác giả đọc lại và xác nhận. Người chấm cũng là tác giả nên có nguy cơ thiên lệch.

## Phân tích và kết luận
- **A–B (chỉ đổi cách chunk):** trên dev hai cấu hình bằng nhau (9/16, 13/16); trên test B tốt hơn (Hit@3 5/5 so với 3/5). Coherence của B cao hơn rõ (1,5 so với 0,9): A cắt giữa từ hoặc giữa câu ở 10/10 vị trí, và ở vị trí pos07 chunk A nhắc "three forms given above" nhưng hai dạng đó nằm ở chunk trước. B có ít chunk hơn (188 so với 202). Grounding test của B là 2,0, của A là 1,4.
- **B–C (chỉ đổi filter):** Hit@1 và Hit@3 không đổi, vì cả 4 câu filter đã đúng ở top-1 ngay với B. Filter chỉ thay các kết quả ở hạng 2–3 nằm ngoài chương:
  - q14: B có kết quả ở chương III.
  - q15: B có kết quả ở chương VII và chương II.
  - q20: B có kết quả ở chương VII.
  
  Với C, top-3 nằm trọn trong chương được yêu cầu (dev 3/3, test 1/1).
- **Ví dụ lỗi 1 — q19 (test, nguồn trang 37):** mục *However* bị tách qua trang 36–37. Ở cả 3 cấu hình, top-1 là nửa đầu ở trang 36 (nói nghĩa "nevertheless" không được đứng đầu câu). Câu trả lời ("When however comes first, it means in whatever way…") nằm ở trang 37. B và C vẫn lấy được ở hạng 3; A thì trượt. Nguyên nhân là ranh giới trang do mình tự chia, không phải lỗi của model.
- **Ví dụ lỗi 2 — q12 (dev, nguồn trang 19):** câu "the expression *the fact that* should be revised out of every sentence" trượt ở cả 3 cấu hình. Top-3 là các đoạn chung chung về câu và đoạn văn (trang 1, 11, 24…). Embedding ngữ nghĩa nhỏ không bắt được cụm từ nguyên văn; dùng thêm BM25 (hybrid) có thể khắc phục. q04 (diễn đạt lại về "chỉ một dấu phẩy") cũng trượt ở cả 3 cấu hình.
- **Chiến lược chọn: C.** Theo tiêu chí chốt trước, B và C hơn A vì ít chunk hơn khi các chỉ số dev bằng nhau. B và C hòa hoàn toàn trên dev. Mình tách hòa bằng tỷ lệ tuân thủ filter trên dev (3/3 so với 1/3). Tiêu chí tách hòa này được thêm **sau khi** đã thấy kết quả dev, vì script in dev và test cùng một lúc. Đánh đổi của C: filter chỉ có ích khi người dùng biết chương cần tìm; nếu chọn sai chương thì sẽ mất kết quả đúng. C phù hợp khi giao diện cho người dùng chọn phạm vi (chương, mục).
- **Hạn chế:**
  - Test chỉ có 5 câu nên chênh lệch 3/5 so với 5/5 không đủ để kết luận tổng quát.
  - Nhãn do một người chấm (có AI hỗ trợ).
  - "Trang" là đơn vị tự chia nên có thể cắt ngang một mục từ.
  - Thời gian chỉ đo một lần trên CPU cá nhân.
  - Chỉ có 1 tài liệu nên `document_id` không giúp phân biệt nguồn.
  - Trường `chapter` chỉ có 7 giá trị.
- **Nếu làm lại hoặc mở rộng:**
  - Chia trang theo mục từ hoặc rule thay vì theo số ký tự, để tránh lỗi kiểu q19.
  - Thêm hybrid BM25 cho các câu hỏi dạng cụm từ nguyên văn (q12).
  - Thêm trường `rule` hoặc `entry` để lọc mịn hơn.
  - Tăng số câu test và nhờ người khác chấm độc lập.
  - Thử model embedding lớn hơn (ví dụ `bge-small` hoặc `e5`) với cùng benchmark.
