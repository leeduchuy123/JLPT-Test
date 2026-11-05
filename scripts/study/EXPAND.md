# Mở rộng bộ "Kiểm tra nhanh" (quiz) của bài 文法 lên ~20 câu

Lý do: ngày học bài mới chỉ có 6–7 câu, quá ít. Mục tiêu: mỗi bài `data/study/bunpo/bXX.json` có `quiz` **20 câu**
(bài có hơn 10 mẫu: mỗi mẫu ≥ 1 câu, tổng tối đa 28). `practice` và `test` giữ nguyên.

Đọc trước: `scripts/study/GUIDE.md` (schema, markup, chất lượng, bản quyền) và bài mẫu `data/study/bunpo/b01.json`.

## Yêu cầu
- **Giữ nguyên** các câu quiz đang có và `id` của chúng (tiến độ học tham chiếu tới id). Câu mới dùng id nối tiếp
  (`b05-q7`, `b05-q8`…), không trùng id nào trong file. Chỉ sửa câu cũ nếu thấy sai rõ ràng, và ghi lại trong báo cáo.
- **Phủ đều**: mỗi mẫu (point) có ít nhất 2 câu trong quiz (bài ≤ 10 mẫu). Mỗi câu có `ref` = id của mẫu.
  Bám vào `nuance`, `mistakes`, `compare` của bài: nên có câu kiểm tra đúng những giới hạn / chỗ dễ nhầm đó.
- **Loại câu**: khoảng 60% `form` (問題7: chọn mẫu điền chỗ trống), 25% `order` (問題8: sắp xếp ★), 15% `usage`
  (chọn câu dùng đúng mẫu). Có thể có 1–2 câu phân biệt hai mẫu trong cùng bài.
- **Thứ tự mảng quiz**: dễ trước khó sau, và không để nhiều câu liền nhau cùng một mẫu. Câu cũ có thể đổi chỗ
  (không đổi id).
- **Không trùng** câu, tình huống hay câu văn với bất kỳ câu nào đã có trong `quiz` / `practice` / `test` của bài.
- **Chất lượng** (giống đề JLPT N2 thật):
  - câu tiếng Nhật tự nhiên, trình độ N2, ngữ cảnh đời sống / công việc / tin tức đa dạng;
  - **đúng một** đáp án; phương án nhiễu là mẫu ngữ pháp có thật (ưu tiên mẫu trong bài hoặc mẫu dễ nhầm),
    sai **rõ ràng** trong ngữ cảnh đó, kể cả loại "nghe được nhưng kém tự nhiên" cũng không được để;
  - `order`: 4 mảnh, thử mọi cách xếp, chỉ có **một** thứ tự tự nhiên; `order` là thứ tự đúng, `answer` là mảnh ở ★;
  - `vi`: bản dịch chính xác; `why`: tiếng Việt dễ hiểu, nói vì sao đáp án đúng **và** vì sao từng phương án kia sai;
  - furigana `{漢字|かな}` theo GUIDE; vị trí đáp án đúng phân bố đều 0–3 (validator cảnh báo nếu một vị trí > 45%).
- **Bản quyền**: mọi câu tự viết mới; không lấy câu từ sách 新完全マスター hay đề thi.
- **Tự kiểm**: viết xong, giải lại từng câu mới như người làm đề (không nhìn `answer`), sửa ngay câu nào mơ hồ.

## Cách sửa file
- Sửa bằng script Python chạy `python -I -X utf8 <script>` (script để trong thư mục scratchpad riêng của bạn),
  chỉ thay khối `"quiz"` và giữ nguyên định dạng còn lại của file (mỗi câu một dòng, CRLF), `ensure_ascii=False`.
  Không ghi lại cả file bằng `indent=2` vì diff sẽ phình to.
- Xong mỗi bài: `python -I -X utf8 scripts/study/validate.py data/study/bunpo/bXX.json` (chạy từ D:\JLPT-app)
  phải **0 lỗi, 0 cảnh báo**.
- Không sửa file nào khác, không chạy git, không chạy build_index.py.

## Báo cáo (ngắn)
Mỗi bài: số câu trước → sau, số câu theo loại (form/order/usage), câu cũ nào đã sửa và vì sao, điều gì còn chưa chắc.
