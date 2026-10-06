# Crawl output schema (normalized question)

Every crawler writes ONE file: `D:/JLPT-app/crawl/raw/<source>.json` = JSON array of Question objects.
Only JLPT **N3** content. Encoding UTF-8, `ensure_ascii=False`, `indent=1`.

```ts
type Question = {
  id: string;            // "<source>:<stable-id>" — deterministic (use source's own id, or sha1 of question+options)
  source: string;        // short slug: "dethitiengnhat" | "jt4y" | "ubiq" | "nihonez" | "kanji123" | "tryjlpt" | "challenge" | "bunpro" | "migii" | "mazii" | ...
  source_url: string;    // page the question came from
  exam: string | null;   // mock-exam set name if the question belongs to a full/partial exam, e.g. "dethitiengnhat N3 Đề 12"; null for standalone drills
  section: "moji" | "bunpo" | "dokkai" | "choukai";
  //   moji   = 文字・語彙 (Kanji reading, orthography, context, paraphrase, usage)
  //   bunpo  = 文法 (grammar form, sentence composition ★, text grammar)
  //   dokkai = 読解
  //   choukai= 聴解
  mondai: number | null; // JLPT 問題 number within its section if known (moji 1-5, bunpo 1-3, dokkai 4-7, choukai 1-5)
  type:
    | "kanji_reading"      // 漢字読み (moji 問題1)
    | "orthography"        // 表記 (moji 問題2)
    | "context"            // 文脈規定 (moji 問題3)
    | "paraphrase"         // 言い換え類義 (moji 問題4)
    | "usage"              // 用法 (moji 問題5)
    | "grammar_form"       // 文法形式 (bunpo 問題1)
    | "sentence_order"     // 文の組み立て ★ (bunpo 問題2)
    | "text_grammar"       // 文章の文法 (bunpo 問題3) — needs passage
    | "reading_short" | "reading_mid" | "reading_long" | "info_retrieval"  // dokkai 問題4-7 — need passage
    | "listening"          // choukai — needs audio
    | "vocab_meaning" | "kanji_meaning" | "grammar_misc";  // generic drills that don't map to a JLPT 問題
  passage: string | null;    // full passage text (plain text, keep line breaks \n). Same text for every question of the passage.
  passage_id: string | null; // "<source>:<passage-id>" shared by questions on the same passage
  question: string;          // the stem; keep blank markers as "＿＿＿" / "（　）" / "★" exactly as source. For passage questions this is the actual question (e.g. 「筆者が一番言いたいことは何か」)
  options: string[];         // 2–4 strings, no leading "1." / "A." numbering
  answer: number;            // 0-based index into options. MUST come from the source's answer key — never guess. Drop the question if no answer available.
  explanation: string | null;// explanation text from source if any (any language), else null
  audio: string | null;      // absolute URL of mp3 (choukai)
  image: string | null;      // absolute URL if the question depends on an image
  transcript: string | null; // listening script if source provides
  furigana: boolean;         // true if question/options contain ruby/furigana that you flattened (prefer: keep kanji only, strip readings)
}
```

Rules
- Strip HTML, normalize whitespace, keep Japanese full-width punctuation. Convert `<ruby>漢<rt>かん</rt></ruby>` → `漢` (drop rt), unless the reading IS the question.
- Convert `<br>` to `\n` inside passages.
- Politeness: 0.6–1.2 s sleep between requests, custom UA, honour robots.txt; cache every fetched HTML/JSON under `D:/JLPT-app/crawl/cache/<source>/` so re-runs are free.
- Scripts live in `D:/JLPT-app/scripts/crawl/<source>.py` and are run from `D:/JLPT-app` with `python -I scripts/crawl/<source>.py`.
- At the end print a summary: total questions, count per section/type, how many have explanation, how many dropped and why.
