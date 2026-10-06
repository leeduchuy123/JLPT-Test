# -*- coding: utf-8 -*-
"""Hand-authored structure + example sentences for N3 grammar points whose jlptsensei detail
page could not be fetched (SiteGround anti-bot challenge, HTTP 202).  Used by build_grammar.py
only when the crawl has no structure/examples for the pattern.  Vietnamese translations of
these sentences live in grammar_examples_vi.py."""
FALLBACK = {
"どうしても": {
    "structure": "どうしても + Verb (たい / 肯定) / どうしても + Verb (ない形)",
    "notes": "Khẳng định: 'bằng mọi giá, nhất định'. Phủ định: 'cố mãi cũng không…'.",
    "examples": [
        {"ja": "どうしても行きたいなら、止めないよ。", "en": "If you really want to go no matter what, I won't stop you."},
        {"ja": "この問題はどうしても解けない。", "en": "I just can't solve this problem no matter what."},
    ]},
"さて": {
    "structure": "さて、 + Sentence (đứng đầu câu)",
    "notes": "Liên từ chuyển đề tài hoặc bắt đầu hành động mới; thường dùng trong văn nói/thuyết trình.",
    "examples": [
        {"ja": "さて、そろそろ始めましょうか。", "en": "Well then, shall we get started?"},
        {"ja": "さて、次の話題に移ります。", "en": "Now, let's move on to the next topic."},
    ]},
"しばらく": {
    "structure": "しばらく + Verb / しばらく(の間) + Noun",
    "notes": "Chỉ một khoảng thời gian không xác định, có thể ngắn (một lát) hoặc khá dài (một thời gian). しばらくぶり = lâu rồi mới…",
    "examples": [
        {"ja": "しばらくお待ちください。", "en": "Please wait a moment."},
        {"ja": "しばらく日本語を勉強していなかった。", "en": "I hadn't studied Japanese for a while."},
    ]},
"すでに": {
    "structure": "すでに + Verb (た形 / ている)",
    "notes": "Trang trọng hơn もう; thường đi với thể hoàn thành.",
    "examples": [
        {"ja": "彼はすでに帰ってしまった。", "en": "He has already gone home."},
        {"ja": "その店はすでに閉まっていた。", "en": "The shop was already closed."},
    ]},
"すなわち": {
    "structure": "A、すなわち B (Noun / Sentence)",
    "notes": "Diễn đạt lại hoặc nói rõ hơn vế trước; văn viết, trang trọng hơn つまり.",
    "examples": [
        {"ja": "彼は私の母の弟、すなわち叔父です。", "en": "He is my mother's younger brother, that is, my uncle."},
        {"ja": "日本の首都、すなわち東京に住んでいます。", "en": "I live in the capital of Japan, namely Tokyo."},
    ]},
"数量 + は（すうりょう + は）": {
    "structure": "Số lượng (時間・金額・回数…) + は + Verb",
    "notes": "は sau lượng từ nhấn mạnh mức tối thiểu: ít nhất cũng chừng đó.",
    "examples": [
        {"ja": "この仕事は三日はかかる。", "en": "This job will take at least three days."},
        {"ja": "修理には一万円はかかるだろう。", "en": "The repair will probably cost at least 10,000 yen."},
    ]},
"て済む（てすむ）": {
    "structure": "Verb (て形) + 済む / Noun + で + 済む / Verb (ない形) + で済む (không cần… cũng xong)",
    "notes": "Việc được giải quyết chỉ với mức độ đó, không cần làm thêm. ないで済む = thoát khỏi việc phải làm.",
    "examples": [
        {"ja": "この程度のけがなら薬を塗るだけで済む。", "en": "For an injury like this, just applying some medicine will do."},
        {"ja": "電話で済むことなら、わざわざ行かなくていい。", "en": "If it can be settled by phone, there's no need to go all the way there."},
    ]},
"ている場合じゃない（ているばあいじゃない）": {
    "structure": "Verb (て形) + いる場合じゃない / Noun + の場合じゃない",
    "notes": "Văn nói; chỉ trích hoặc tự nhắc rằng không phải lúc làm việc gì đó.",
    "examples": [
        {"ja": "今はテレビを見ている場合じゃない。", "en": "This is no time to be watching TV."},
        {"ja": "のんびりしている場合じゃないよ。急ごう。", "en": "This is no time to be relaxing. Let's hurry."},
    ]},
"ても始まらない（てもはじまらない）": {
    "structure": "Verb (て形) + も始まらない",
    "notes": "Thường đi với 今さら, いくら, 文句を言う, 後悔する, 泣く…",
    "examples": [
        {"ja": "今さら後悔しても始まらない。", "en": "There's no point regretting it now."},
        {"ja": "文句を言っても始まらないから、やるしかない。", "en": "Complaining won't get us anywhere, so we just have to do it."},
    ]},
"ところが": {
    "structure": "Sentence A。ところが、Sentence B (kết quả trái với dự đoán)",
    "notes": "Liên từ đứng đầu câu; vế sau là sự thật trái với mong đợi, không dùng cho ý chí/mệnh lệnh của người nói.",
    "examples": [
        {"ja": "急いで駅に行った。ところが、電車はもう出ていた。", "en": "I hurried to the station. However, the train had already left."},
        {"ja": "晴れると思っていた。ところが、急に雨が降り出した。", "en": "I thought it would be sunny. But then it suddenly started raining."},
    ]},
"ように見える（ようにみえる）": {
    "structure": "Verb (普通形) + ように見える / い-Adj + ように見える / な-Adj + な + ように見える / Noun + の + ように見える",
    "notes": "Phán đoán dựa trên cái nhìn bề ngoài; so với そう, ように見える nhấn mạnh 'trông như' qua quan sát.",
    "examples": [
        {"ja": "彼は疲れているように見える。", "en": "He looks tired."},
        {"ja": "この絵は本物のように見える。", "en": "This painting looks like the real thing."},
    ]},
"ようとしない": {
    "structure": "Verb (意向形) + としない",
    "notes": "Chủ ngữ thường là người khác (ngôi thứ 3); diễn tả thái độ không chịu, không có ý định làm.",
    "examples": [
        {"ja": "彼は自分の間違いを認めようとしない。", "en": "He won't admit his own mistake."},
        {"ja": "息子は全然勉強しようとしない。", "en": "My son makes no effort to study at all."},
    ]},
}
