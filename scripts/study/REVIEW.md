# Rà soát bài học N2 bằng cách đối chiếu với sách

Mục tiêu: các bài ở `data/study/<track>/<id>.json` đều do AI tự viết. Việc rà soát là đối chiếu chúng với sách 新完全マスター N2
(trang giải thích, bài tập, 別冊 đáp án) để sửa chỗ sai, và kiểm tra độc lập mọi câu hỏi.
Người rà soát **không phải** người viết bài, nên hãy đọc với con mắt phê bình.

## Bản quyền (giữ nguyên)
Repo này public. **Không chép** câu ví dụ, bài tập, đoạn văn hay lời giải của sách vào file JSON. Sách chỉ dùng làm
**chuẩn để kiểm tra** (nghĩa, quy tắc, giới hạn, cách dùng nào sách coi là sai). Câu nào cần sửa thì viết câu mới của mình.

## Ảnh trang sách
`C:\Users\LeDucHuy\AppData\Local\Temp\claude\20e04b49a78aa9bb\83540a7a-259e-4009-b5b5-a80569b32333\scratchpad\pdf\{bun,goi,dok}\pNNN.png`
(xem GUIDE.md để biết độ lệch trang). Ảnh chỉ rộng 612px. Muốn đọc chữ nhỏ hay phân biệt in đậm thì render lại vùng cần xem
từ PDF gốc trong Downloads bằng PyMuPDF với zoom 2–2.5, lưu vào thư mục con **của riêng bạn** trong scratchpad
(chạy `python -P script.py` từ thư mục chứa script, vì PyMuPDF nằm ở user site-packages).
別冊 đáp án ở cuối mỗi PDF: 文法 khoảng p213–p227, 語彙 khoảng p210–p244, 読解 khoảng p198–p237. Xem số trang in và tiêu đề trên ảnh
để tìm đúng phần đáp án của bài.

## Việc cần làm với từng bài
1. **Đối chiếu kiến thức**: đọc trang giải thích của bài trong sách, các trang bài tập và đáp án tương ứng trong 別冊.
   - Kiểm tra bài trong app có đủ mọi mục sách dạy không: mẫu ngữ pháp, nghĩa con, từ, kỹ năng. Thiếu thì bổ sung, viết bằng lời của mình.
   - Kiểm tra mọi khẳng định trong `explain` / `nuance` / `compare` / `mistakes` / `tip` có **mâu thuẫn với sách** không,
     ví dụ sách nói "vế sau không dùng ý chí" mà app lại có ví dụ dùng ý chí. Sửa theo sách.
   - Xem 別冊 để biết sách coi cách dùng nào là đúng hay sai ở những chỗ ranh giới. Câu hỏi của app không được trái với nhận định đó.
   - Từ vựng: cách đọc (`r`), nghĩa (`vi`), Hán Việt (`hv`) và cờ `key` (từ in đậm) phải khớp sách.
2. **Tự giải từng câu hỏi** (quiz, practice, test, worked) **trước khi** xem `answer`. Sau đó so với đáp án:
   - Đáp án ghi trong file sai → sửa `answer` và `why`.
   - Có hơn một phương án chấp nhận được, kể cả "nghe được nhưng kém tự nhiên" → thay phương án nhiễu bằng phương án sai rõ ràng,
     cập nhật `why`.
   - Không có phương án nào đúng, câu tiếng Nhật không tự nhiên, hoặc bản dịch `vi` sai → sửa.
   - Câu 並べ替え: thử mọi cách xếp hợp lý. Chỉ được có một thứ tự tự nhiên, `order` phải đúng thứ tự đó, `answer` là mảnh ở vị trí ★.
   - Đọc hiểu: đáp án phải dựa được vào một câu cụ thể trong đoạn văn. Phương án nhiễu không được đúng theo cách hiểu khác của đoạn văn.
3. **Ví dụ**: câu tiếng Nhật phải tự nhiên và đúng ngữ pháp, furigana `{漢字|かな}` phải đọc đúng, bản dịch phải chính xác.

## Quy tắc sửa
- Giữ nguyên schema (GUIDE.md) và **giữ nguyên `id`** của mọi câu hỏi, point và word, vì tiến độ người học tham chiếu tới chúng.
  Thêm mục mới thì dùng id mới, chưa có trong file.
- Sửa trực tiếp file JSON, giữ UTF-8, giữ `ensure_ascii=False` nếu ghi bằng Python.
- Sửa xong chạy `python -I scripts/study/validate.py data/study/<track>/<id>.json` (từ D:\JLPT-app) và phải sạch ERROR.
- Không sửa file ngoài phần được giao, không chạy git, không chạy build_index.py.

## Báo cáo (ngắn)
Với từng bài:
- số câu đã sửa đáp án, số câu đã sửa vì mơ hồ, số chỗ giải thích đã sửa vì trái với sách, các mục đã bổ sung;
- 1–3 ví dụ tiêu biểu (id câu + vấn đề);
- những gì còn chưa chắc.
