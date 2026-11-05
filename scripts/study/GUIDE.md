# Viết bài học N2 (data/study/<track>/<id>.json)

Người học: người Việt, đã đỗ / sắp thi N3, tự học N2 bằng bộ 新完全マスター N2. Sách đủ kiến thức nhưng
giải thích quá ngắn và khó hiểu. Nhiệm vụ của mỗi bài: **giải thích thật rõ ràng, dễ hiểu bằng tiếng Việt,
có nhiều ví dụ cụ thể**, rồi cho bài tập dạng đề JLPT N2 có giải thích từng câu.

Khung khoá học: `scripts/study/courses.json` (id bài, tên, trang sách). Bài mẫu chuẩn: `data/study/bunpo/b01.json`
— đọc kỹ bài mẫu trước khi viết, giữ đúng độ sâu và giọng văn đó.

## Bản quyền — bắt buộc
Repo này public. Chỉ dùng sách để **xác định danh mục kiến thức** của từng bài (mẫu ngữ pháp nào, từ nào,
kỹ năng đọc nào, ý chính của mẫu). **Không chép** câu ví dụ, bài tập, đoạn văn đọc hiểu, lời giải của sách.
Mọi câu ví dụ, câu hỏi, đoạn văn đều tự viết mới (có thể cùng chủ đề, nhưng câu chữ khác hẳn).

## Ảnh trang sách
Các trang đã render sẵn thành PNG (đọc bằng tool Read):
`C:\Users\LeDucHuy\AppData\Local\Temp\claude\20e04b49a78aa9bb\83540a7a-259e-4009-b5b5-a80569b32333\scratchpad\pdf\{bun,goi,dok}\pNNN.png`
(bun = 文法, goi = 語彙, dok = 読解; NNN = chỉ số trang PDF, 3 chữ số, bắt đầu từ 000).
Chỉ số PDF ≈ số trang in + độ lệch: 文法 +9, 語彙 +7 (đầu sách) … +5 (cuối sách), 読解 +6 (đầu) … +5 (cuối).
Độ lệch trôi dần, nên luôn kiểm tra số trang in ở chân trang / tiêu đề bài trên ảnh rồi lùi/tiến 1–2 trang.

## Định dạng văn bản
Áp dụng cho mọi chuỗi (giải thích tiếng Việt lẫn câu tiếng Nhật):
- `\n` xuống dòng, `\n\n` đoạn mới, dòng bắt đầu bằng `- ` = gạch đầu dòng, `**đậm**`.
- Furigana: `{漢字|かんじ}` (mỗi cặp một từ, không lồng nhau, không có `{` `}` `|` nào khác).
  Ví dụ (`examples`), đoạn văn và câu hỏi: gắn furigana cho từ có kanji từ mức N3 trở lên (người học bật/tắt được).
  Không gắn furigana cho chính từ đang bị hỏi cách đọc/cách viết.
- Gạch chân trong câu tiếng Nhật: `[[u:từ]]` (dùng cho từ bị hỏi trong câu hỏi đọc/ nghĩa, hoặc phần gạch chân của đoạn đọc).
  Có thể đánh số: `[[u1:…]]`, `[[u2:…]]` → hiện số nhỏ trước phần gạch chân.
- Chỗ trống: `（　　）`. Dạng 並べ替え: đúng 4 ô `＿＿＿` cách nhau bằng dấu cách, một ô là `★` thay cho `＿＿＿`
  (vd `… ＿＿＿ ＿＿＿ ★ ＿＿＿ …`).
- Không dùng HTML.

## Câu hỏi (dùng chung cho mọi track)
```json
{"id": "b01-q1", "kind": "form", "ref": "b01-1", "pass": "p1",
 "q": "…（　　）…", "options": ["", "", "", ""], "answer": 0,
 "order": [1, 3, 0, 2],
 "vi": "dịch câu hoàn chỉnh (đáp án đúng đã điền)",
 "why": "giải thích: vì sao đúng, vì sao TỪNG phương án sai (ngắn gọn)"}
```
- `id`: `<bài>-q<n>` (quiz), `<bài>-p<n>` (practice), `<bài>-t<n>` (test), `<bài>-w<n>` (worked, chỉ đọc hiểu). Duy nhất.
- `options`: đúng 4 phương án, không trùng nhau. `answer`: 0–3. **Rải đều vị trí đáp án đúng** (không để một vị trí > 40%).
- `ref`: id của mục kiến thức liên quan (point / word) — nên có. `pass`: id đoạn văn trong `passages` (nếu câu dựa vào đoạn văn).
- `order` (chỉ kind `order`): thứ tự đúng của 4 mảnh, tính theo chỉ số trong `options`; `answer` = mảnh đứng ở vị trí ★.
- `kind`:
  - Ngữ pháp: `form` (chọn mẫu điền chỗ trống — 問題7), `order` (sắp xếp ★ — 問題8), `usage` (chọn câu dùng đúng),
    `passage` (điền vào đoạn văn — 問題9, có `pass`).
  - Từ vựng: `read` (đọc kanji gạch chân), `write` (chọn kanji cho từ hiragana gạch chân), `formation` (語形成: tiền/hậu tố, từ ghép),
    `context` (文脈規定), `paraphrase` (言い換え: chọn từ/câu gần nghĩa nhất với phần gạch chân), `usage` (用法: 4 câu, chọn câu dùng từ đúng;
    khi đó `q` là chính từ đó, ví dụ 「{発揮|はっき}」).
  - Đọc hiểu: `passage`.
- Câu hỏi phải có **đúng một** đáp án đúng rõ ràng, mức độ N2 thật (không quá dễ), phương án nhiễu hợp lý (cùng loại từ / mẫu dễ nhầm).
- Bộ câu hỏi: `quiz` = kiểm tra nhanh ngay sau khi học (mỗi mục chính ít nhất một câu); `practice` = dùng cho ngày 練習
  (gộp 2 bài); `test` = dùng cho まとめ問題 (gộp 4 bài). Ba bộ **không trùng câu**.

## Track 文法 (bunpo) — `points`
Xem `b01.json`. Mỗi mẫu (point):
- `id` `<bài>-<n>`, `pattern` (ghi đúng như sách, vd 「〜に際して・〜にあたって」), `reading` (hiragana), `meaning` (1 dòng tiếng Việt),
- `structure`: các dạng nối (V辞書形／Vた形／Vない形／Vます形／い形／な形／N …),
- `explain`: giải thích dễ hiểu — nghĩa thực sự là gì, hình ảnh / cách nhớ, khi nào dùng, mỗi nghĩa con nếu có (3–8 câu, có thể dùng gạch đầu dòng),
- `nuance`: văn phong (trang trọng / văn nói / văn viết), sắc thái cảm xúc, giới hạn (vế sau không được là gì, chủ ngữ…),
- `examples`: 4–6 câu, đa dạng ngữ cảnh (đời sống, công việc, tin tức), mỗi câu có `ja`, `vi`, `note` (ngắn: dạng nối / điểm cần để ý, có thể rỗng),
- `compare`: 1–3 mẫu dễ nhầm (trong bài, bài khác hoặc N3) và khác nhau ở đâu,
- `mistakes`: 1–3 lỗi hay gặp, dạng `✗ … → ○ …`,
- `tip`: mẹo nhận ra đáp án trong đề.
Thêm: `intro` (bức tranh chung của bài: các mẫu liên quan nhau thế nào, điểm then chốt), `summary` (bảng ôn nhanh: `pattern`, `meaning`, `key`).
Số câu: `quiz` ~20 (bài > 10 mẫu: mỗi mẫu ≥ 1 câu, tối đa 28; xem EXPAND.md), `practice` 10–12, `test` 6–8. Trộn `form` (đa số), `order` (≥ 2 mỗi bộ practice/test), `usage`.

Bài không có danh sách mẫu trong courses.json (IV A–G, 第2部, 第3部): đọc trang sách để lấy danh mục
(`items` trong index.json được build_index.py tự lấy từ `pattern` của các point, không cần sửa courses.json). Với 第2部 / 第3部 (ngữ pháp câu & văn bản), mỗi point là một **quy tắc / điểm ngữ pháp**
(vd 「自動詞・他動詞の使い分け」), `structure` có thể là các khuôn câu, ví dụ nên có cặp ✗/○. Bài 第3部 nên có câu `passage`
(đoạn văn ngắn tự viết với 2–4 chỗ trống, kiểu 問題9).

## Track 語彙 (goi) — `sections`
```json
{"id": "g01", "track": "goi", "intro": "…",
 "sections": [{"title": "親類", "title_vi": "Họ hàng", "words": [
   {"id": "g01-w1", "w": "親戚", "r": "しんせき", "hv": "THÂN THÍCH", "pos": "名", "vi": "họ hàng", "key": true,
    "ex": {"ja": "…", "vi": "…"}, "col": ["親戚付き合い"], "rel": "≒ 親類", "note": "…",
    "senses": [{"vi": "…", "ex": {"ja": "…", "vi": "…"}}]}]}],
 "focus": [{"title": "Phân biệt 〜 và 〜", "body": "…"}],
 "quiz": [], "practice": [], "test": []}
```
- Lấy **đầy đủ** các từ trong phần 言葉 / 語形成 / 連語 của bài trong sách (giữ cách nhóm của sách thành `sections`). `key: true` cho từ
  in đậm (N2 cần học). `w` = cách viết thông dụng, `r` = hiragana, `hv` = âm Hán Việt in hoa (bỏ trống nếu không có kanji / là từ ngoại lai),
  `pos`: 名 / 動 / 自動 / 他動 / い形 / な形 / 副 / 連語 / 接頭 / 接尾 …, `vi` ngắn gọn, chính xác.
- `ex`: một câu ví dụ tự viết (bắt buộc với từ `key`, nên có với mọi từ). `col`: cụm hay đi kèm (連語). `rel`: đồng nghĩa ≒, trái nghĩa ↔.
  `note`: sắc thái / dễ nhầm (nếu có). Từ nhiều nghĩa (đặc biệt 第2部 1章) dùng `senses` (mỗi nghĩa một ví dụ).
- `focus`: 3–6 mục giải thích sâu: cặp từ dễ nhầm, cách dùng khác nhau, quy tắc ghép từ / tiền-hậu tố của bài, quán ngữ… có ví dụ.
- Số câu: `quiz` 8–10, `practice` 12–15, `test` 10–12, trộn các kind của từ vựng (đọc, viết, 文脈規定, 言い換え, 用法, 語形成 khi hợp).

## Track 読解 (dokkai) — kỹ năng đọc
```json
{"id": "d01", "track": "dokkai", "intro": "…",
 "strategy": [{"title": "Bước 1 …", "body": "…"}],
 "signals": [{"ja": "〜に対して", "vi": "trái lại …", "note": "…"}],
 "passages": {"p1": {"title": "", "kind": "評論", "ja": "…", "vi": "bản dịch đầy đủ"}},
 "worked": [{"id": "d01-w1", "kind": "passage", "pass": "p1", "q": "…", "options": [], "answer": 0, "why": "…",
             "walkthrough": "phân tích từng bước: đọc câu hỏi → tìm tín hiệu → loại trừ"}],
 "quiz": [], "practice": [], "test": []}
```
- `intro` + `strategy`: dạy **kỹ năng** của bài (vd [対比]: nhận ra hai vế được so sánh, ý tác giả nằm ở vế nào) thật cụ thể, từng bước.
- `signals`: từ / cụm tín hiệu nhận diện cấu trúc (8–15 mục), mỗi mục có ví dụ ngắn trong `note` nếu cần.
- `passages`: tất cả tự viết, độ khó N2, kèm bản dịch `vi` đầy đủ. Độ dài theo dạng bài: 短文 ~200 字, 中文 ~500 字,
  長文 ~900 字, 統合理解 hai bài A/B ~300 字 mỗi bài (ghi `A` / `B` trong cùng `ja`), 情報検索 = thông báo / bảng / danh sách
  (dùng dòng, gạch đầu dòng, 【 】, ・ để trình bày bảng bằng chữ).
- `worked`: 1–2 ví dụ mẫu có `walkthrough` chi tiết. `quiz` 2–3 câu (1 đoạn), `practice` 4–6 câu (2–3 đoạn), `test` 3–5 câu (1–2 đoạn).
  Mỗi đoạn chỉ thuộc một bộ (worked / quiz / practice / test). Câu hỏi về phần gạch chân dùng `[[u:…]]` trong đoạn văn.

## Kiểm tra
`python -I scripts/study/validate.py data/study/<track>/<id>.json` phải không còn lỗi (ERROR). Sửa hết rồi mới coi là xong.
Sau đó `python -I scripts/study/build_index.py` (người điều phối chạy).
