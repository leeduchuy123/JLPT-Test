# JLPT N3 – Web tổng ôn (cá nhân)

Web tĩnh (HTML/CSS/JS thuần, ES modules, không build step), host trên Vercel. Tiến độ lưu trong `localStorage` của trình duyệt, có xuất/nhập file sao lưu, và (tuỳ chọn) đồng bộ giữa các thiết bị qua một Vercel Function + Upstash Redis.

Mục tiêu: tổng ôn N3 trong ~2 tháng bằng cách **làm đề → sai ở đâu học lại ở đó**, với lịch ôn lại theo spaced repetition.

## Tính năng
| Trang | Nội dung |
|---|---|
| **Hôm nay** | Đếm ngược ngày thi, mục tiêu câu/ngày, bài đang làm dở, câu đến hạn ôn, dạng bài yếu nhất, kết quả gần đây |
| **Thi thử** | *Strict* (có giờ, tự nộp khi hết giờ): đề đầy đủ 3 phần (30 + 70 + 40 phút) hoặc từng phần. *Normal* (không giờ, thoát/làm tiếp bất cứ lúc nào): từng phần. Nguồn đề: 45 bộ đề thật từ các trang luyện thi, hoặc đề ngẫu nhiên ghép đúng tỉ lệ 問題 của JLPT N3 (ưu tiên câu chưa làm / hay sai) |
| **Luyện nhanh** | Chọn dạng bài (問題1–7, nghe), 10/20/30 câu hoặc 1–3 đoạn đọc; chữa ngay từng câu; phím 1–4 và Enter |
| **Chữa bài** | Mỗi câu: đáp án đúng/sai, giải thích từng lựa chọn (moji), giải thích mẫu ngữ pháp + dịch cả câu (bunpo), dịch cả đoạn (dokkai), script + câu then chốt (choukai); nút **☆ Lưu Xem sau**, **Ghi chú**, **Học lại** (ngữ pháp / từ vựng / kanji liên quan) |
| **Xem sau** | SRS: câu bạn gắn cờ hoặc làm sai, lặp lại 1 → 3 → 7 → 14 → 30 → 60 ngày; đánh giá Quên / Khó / Nhớ / Dễ |
| **Tiến độ** | Biểu đồ 30 ngày, độ chính xác theo phần và theo dạng bài, điểm thi thử theo thời gian, lịch sử, ước tính điểm JLPT |
| **Tra cứu** | Ngữ pháp N3, từ vựng N3, kanji N3 có tìm kiếm |
| **Cài đặt** | Giao diện sáng/tối, ngày thi, mục tiêu ngày, tự thêm câu sai vào Xem sau, đồng bộ giữa các thiết bị, xuất/nhập/xoá dữ liệu, thống kê ngân hàng câu hỏi |

## Cấu trúc
```
index.html              # shell SPA (hash router)
css/style.css           # giao diện, light/dark
js/app.js               # router, theme, nav
js/store.js             # state + localStorage (stats, history, SRS, notes, sessions), ghi mốc thời gian cho đồng bộ
js/merge.js             # gộp 2 bản tiến độ (từng mục theo lần sửa cuối, mục đã xoá, đếm ngày theo thiết bị)
js/sync.js              # đồng bộ đám mây phía trình duyệt (kéo / gộp / đẩy, nén gzip)
api/sync.js             # Vercel Function: kho đồng bộ 1 người dùng (Upstash Redis REST, khoá bằng mật khẩu)
js/srs.js               # lịch lặp lại
js/data.js              # tải bank/exams/refs, ghép đề, tìm tra cứu liên quan
js/question.js          # render câu hỏi / đoạn văn / giải thích / hành động
js/charts.js            # biểu đồ SVG thuần
js/pages/*.js           # home, test, drill, review, progress, ref, settings
data/bank/<section>.json  # ngân hàng câu hỏi đã lọc trùng (moji, bunpo, dokkai, choukai)
data/exams.json           # các bộ đề thật
data/ref/*.json           # từ vựng / kanji / ngữ pháp N3
data/manifest.json        # thống kê build
scripts/crawl/*.py        # crawler từng nguồn (xem SCHEMA.md)
scripts/build_bank.py     # gộp crawl/raw → data/ (lọc trùng, gắn giải thích)
scripts/explain/          # chia lô & kiểm tra giải thích (crawl/explain/out/*.json)
crawl/                    # dữ liệu thô + cache (không deploy)
```

## Chạy local
```bash
npm run dev          # http://localhost:3000 (không có /api → đồng bộ báo lỗi, phần còn lại chạy bình thường)
```

## Cập nhật dữ liệu
```bash
python -I scripts/crawl/<source>.py     # crawl lại một nguồn (có cache)
python -I scripts/build_bank.py         # gộp → data/
python -I scripts/explain/make_batches.py   # tạo lô câu chưa có giải thích
python -I scripts/explain/validate.py       # kiểm tra giải thích
```
Giải thích do AI viết theo vai giáo viên, lưu ở `crawl/explain/out/`, được gắn vào bank khi build.

## Deploy Vercel
Framework: **Other**, không build command, output root. `vercel.json` đã có cleanUrls + header bảo mật; `js/`, `css/`, `data/` luôn hỏi lại máy chủ (ETag) để không bị trộn file JS cũ/mới sau khi deploy. `.vercelignore` loại `crawl/`, `scripts/`, `docs/`. Thư mục `api/` được Vercel tự nhận làm Functions.

### Chuyển tiến độ sang máy khác (không cần cài gì)

**Cài đặt → Chuyển tiến độ sang máy khác**:
1. Máy cũ: **Xuất file tiến độ** → tải về `jlpt-n3-tien-do-<ngày>_<giờ>.json` (kết quả từng câu, Xem sau + lịch ôn, ghi chú, lịch sử thi, bài làm dở, số câu mỗi ngày, cài đặt).
2. Gửi file sang máy mới.
3. Máy mới: **Nhập file tiến độ** → **Gộp** (giữ tiến độ của cả hai máy, mục nào sửa sau thì thắng; nhập lại cùng file không bị cộng trùng) hoặc **Thay thế** (dùng đúng như trong file).

### (Nâng cao, tuỳ chọn) Đồng bộ tự động giữa các thiết bị
1. Vercel → project → **Storage** → **Create Database** → **Upstash for Redis** (gói Free) → connect vào project. Tích hợp tự thêm biến `KV_REST_API_URL` / `KV_REST_API_TOKEN` (hoặc `UPSTASH_REDIS_REST_URL` / `_TOKEN`, đều dùng được).
2. **Settings → Environment Variables**: thêm `SYNC_PASSWORD` = một mật khẩu dài (≥ 16 ký tự, có dấu tiếng Việt cũng được).
3. **Deployments → Redeploy** để biến môi trường có hiệu lực.
4. Trên mỗi máy: **Cài đặt → Đồng bộ giữa các thiết bị** → nhập mật khẩu. Dữ liệu sẵn có trên máy được gộp với máy chủ, không ghi đè.

Cách gộp: mỗi câu / thẻ Xem sau / ghi chú / bài đang làm lấy bản sửa sau cùng; mục đã xoá không bị máy khác làm sống lại; số câu mỗi ngày đếm riêng từng thiết bị rồi cộng; giao diện sáng/tối giữ riêng từng máy. "Xoá toàn bộ" và "Nhập từ file" áp dụng cho mọi thiết bị. Máy chủ chỉ lưu một chuỗi nén (~120 KB khi đã làm hết ngân hàng câu), sai mật khẩu 20 lần / 15 phút thì khoá IP đó.

## Dữ liệu (build 2026-10-06)
| | Số lượng |
|---|---|
| Câu hỏi sau lọc trùng | 9.265 (moji 4.516 · bunpo 3.103 · dokkai 913 · choukai 733) |
| Đề thi thật các năm | 28 kỳ, 7/2010 đến 12/2024, không có phần nghe |
| Đề luyện / mô phỏng | 43 |
| Đoạn đọc hiểu có bản dịch | 514 |
| Câu có giải thích tiếng Việt | 9.265 / 9.265 |
| Câu gốc có vấn đề (bị loại khỏi bài luyện mới) | 133 |
| Tra cứu | 2.120 từ · 367 kanji · 182 mẫu ngữ pháp |

Đề thật: jlptpracticetest.com (tham chiếu chính khi lọc trùng, nên các đề thật luôn nguyên vẹn).
Nguồn hạng A khác: dethitiengnhat, japanesetest4you, tryjlpt, challenge-jlpt, bunpro, nihongo-pro, mlcjapanese, mazii (3 đề miễn phí), kanji123.
Nguồn hạng B (bài luyện tự sinh, độ khó không đều, có thể tắt trong Luyện nhanh): japanesequizzes, gyanmirai.
Lọc: trùng câu (1.304), câu thiếu đáp án/đoạn văn/audio, dạng "tất cả đều đúng", nguồn không phải N3 (jlpt.u-biq.org).
Khi một câu bị gộp vào bản trùng, `data/aliases.json` ánh xạ id cũ sang id mới và app tự chuyển tiến độ học.
Không lấy: nihonez, tryjlpt (phần cần đăng nhập), Mazii đề 4–15 (Premium), Migii (dữ liệu mã hoá).
Chỉ dùng cho mục đích học cá nhân.
