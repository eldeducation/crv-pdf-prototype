# 動画から用途に合った資料を作る 4つのユースケース

動画を、作業するとき・共有するとき・学ぶときに使える資料へ。YouTube・Xの公開動画リンクや動画ファイルから、内容と用途に合わせて写真・説明・図表を組み合わせたPDFを作る試作品です。

**2026年10月30日更新。** 招待制のクラウド試作品とGitHubの公開コードを追加しました。4用途の見本と、これまで作成した13題材・22種類のPDFを掲載しています。

## 共有リンクと現在の公開状況

- **[動画から資料を作る試作品（招待制）](https://crv-pdf-prototype.onrender.com/)**：Render Freeに配置しました。開発者のPCがスリープしていても、クラウド側で動作します。招待用パスワードは管理者から別途受け取ってください。**クラウドでの起動とログイン画面の表示まで確認済み。ログイン後の動画解析・PDF生成は検証中です。**
- **[紹介・操作デモと全PDF見本](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/)**：APIキー不要で、用途切り替え・アレンジ選択・資料検索・PDF閲覧を試せます。この紹介ページ内では新しいPDFを生成しません。
- **[公開プログラムとREADME](https://github.com/eldeducation/crv-pdf-prototype)**：キー・動画・利用者セッション・ログを除いたコードを公開しています。
- [クラウド配置の手順と制約](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/deployment/README.md) / [配置用ソース一式](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/deployment/cloud-generation.zip)：DockerビルドとRender上の起動は成功しています。動画取得・音声認識・PDF描画が無料枠に収まるかは実機検証が残っています。

利用者は、自分の対応APIキーを試作品に入力して生成します。API料金はそのキーの利用者が負担します。Lucasのキーは公開ページへ埋め込みません。キーはクラウドサーバーのメモリで扱い、抽出画像・字幕などは選択したAIサービスへ送信します。

無料サービスは休止・再起動する場合があり、起動待ちが発生します。アップロード動画や生成物は永続保存されないので、完成したPDFを保存してください。招待用パスワードは共有の入口保護で、個人アカウント認証や本番向けの安全性保証ではありません。

## 誰が、どのように使うか

| 画面で選ぶ用途 | 想定ユーザーと使う場面 | 入力する動画 → 得られる資料 | 今回の見本 |
| --- | --- | --- | --- |
| 動画に合わせる | 重要場面や出来事の流れを振り返りたい人 | サッカーハイライト → 得点までの流れや判定を整理した写真付きレポート | [使い方](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/use-cases/01-auto.md) / [PDF・5ページ](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/examples/auto-highlights.pdf) |
| 作業手順書 | 実演の順序や部品を確認しながら作業したい人 | MacBookのバッテリー交換 → 準備物、分解・組立て、確認点を写真でたどる作業ガイド | [使い方](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/use-cases/02-procedure.md) / [PDF・11ページ・要確認](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/examples/procedure-macbook-needs-review.pdf) |
| セミナー要約 | 英語の講演を理解し、同僚と検討したい担当者 | AI活用ビジネスの対談・実演 → 6案の価値・提供例・条件を比較する日本語の共有資料 | [使い方](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/use-cases/03-seminar.md) / [PDF・9ページ](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/examples/seminar-ai-business.pdf) |
| 研修資料 | 新人向けの接客・顧客対応研修を担当する人 | クレーム対応の講義 → 対応の流れ、言葉の使い方、確認問題・解答・練習を含む教材 | [使い方](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/use-cases/04-training.md) / [PDF・8ページ](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/examples/training-complaints.pdf) |

「動画に合わせる」は固定ジャンルではなく、構成を動画の内容に合わせる設定です。講演を作業手順にしたり、試合を操作マニュアルにしたりせず、読む目的に合う形へ整理します。

## 見本の冒頭

| 動画に合わせる | 作業手順書（要確認） |
| --- | --- |
| [![サッカーのレポート](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/examples/auto-highlights-cover.png)](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/use-cases/01-auto.md) | [![MacBookの作業ガイド](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/examples/procedure-macbook-cover.png)](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/use-cases/02-procedure.md) |
| **セミナー要約** | **研修資料** |
| [![AI活用ビジネスの要約](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/examples/seminar-ai-business-cover.png)](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/use-cases/03-seminar.md) | [![クレーム対応の研修教材](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/examples/training-complaints-cover.png)](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/use-cases/04-training.md) |

## 使う流れ

1. YouTube・Xの公開動画リンク、または自分の動画ファイルを入力する。
2. 用途、説明の詳しさ、出力言語を選ぶ。
3. デザイン重視を標準に、必要なら「すっきり」「図解多め」「写真多め」「比較で整理」を組み合わせる。追加の希望は任意。
4. 生成された内容、写真の対応、確認が必要な点を元動画と照合する。
5. PDFを保存し、必要に応じて編集用Markdownで調整する。

通常のAPI生成には、利用者自身の対応APIキーと利用料金が必要です。APIなしのテストは、チャットで作った回答JSONを取り込む手動の検証モードです。

## この見本で確認できること

作業は順序と写真、セミナーは論点と比較、研修は理解と練習というように、用途によって構成を変えています。デザイン重視は、図を一律に増やす設定ではなく、内容に合わせて見出し・色・余白・写真の大きさを整える標準方針です。

MacBookの見本には、映像だけでは確定できない加熱・溶剤の条件、接着施工、小部品の戻し位置があります。**PDFは作成済みですが「要確認」です。単独で安全に修理を再現できる手順書としては未承認です。** 不足を推測で埋めず、確認点として残した例でもあります。

## これまで作成した資料一覧

**13題材・22種類。** 同じファイルの別名コピーはまとめ、内容・デザインが異なる版は残しています。以下は作成済み資料の記録で、すべてを正解・監修済みと評価した一覧ではありません。ソフトウェアのテスト用PDF、未完成の一時ファイル、ユーザーから受け取った比較用PDFは含めていません。

| 題材・入力動画 | 作成済みPDF（ページ数） | 位置づけ・確認点 |
| --- | --- | --- |
| [金魚の折り紙](https://www.youtube.com/watch?v=N1P4VpXhrfo) | [初期API版・7ページ](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/catalog/goldfish-initial.pdf) | 初期のOpenRouter実行記録あり。動作説明の誤りを指摘された過去版。 |
| [金魚の折り紙](https://www.youtube.com/watch?v=N1P4VpXhrfo) | [初期改善版・要確認・10ページ](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/catalog/goldfish-early-review.pdf) | 旧パイプラインの検証版。実行記録はneeds_review。 |
| [金魚の折り紙](https://www.youtube.com/watch?v=N1P4VpXhrfo) | [APIなし改善版・10ページ](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/catalog/goldfish-manual.pdf) | 以後の準備写真・切断ガイド追加版と比較する過去版。 |
| [金魚の折り紙](https://www.youtube.com/watch?v=N1P4VpXhrfo) | [準備写真・切断ガイド追加・11ページ](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/catalog/goldfish-preparation.pdf) | 準備物の写真、切断位置、工程と写真の対応を改善。 |
| [カーネーション](https://www.youtube.com/watch?v=qQuXRAZS2OE) | [APIなし版・8ページ](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/catalog/carnation-manual.pdf) | 花の折り方を写真付きで整理。 |
| [カーネーション](https://www.youtube.com/watch?v=qQuXRAZS2OE) | [別タスクAstra比較版・8ページ](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/catalog/carnation-astra.pdf) | 前の分析を引き継がない別タスクで作成。ユーザーより画像の工程対応にずれの指摘あり。 |
| [バイエルン対アーセナル](https://www.youtube.com/watch?v=CFfVItBrWbM) | [PK訂正版・5ページ](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/catalog/soccer-pk-corrected.pdf) | PK原因を接触からハンドへ訂正。初期APIなしテスト名のPDFも現在は同じ内容。 |
| [バイエルン対アーセナル](https://www.youtube.com/watch?v=CFfVItBrWbM) | [外部情報照合版・5ページ](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/catalog/soccer-researched.pdf) | 現在の「動画に合わせる」の代表例。元映像と外部の公開情報を照合。 |
| [浴室換気乾燥機 BS-131LH](https://www.youtube.com/watch?v=AeKibD55QOY) | [動画実演ガイド・8ページ](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/catalog/bath-fan.pdf) | 安全条件・組立て復旧など映像の不足を記載。単独の保守作業指示として未承認。 |
| [Summer ピアノ](https://www.youtube.com/watch?v=t8zZAS0fK4E) | [音名・指番号ガイド・33ページ](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/catalog/piano.pdf) | 検証用。指番号は提案で、全音符の人手校正・実演検証は未完了。静止画資料の適性に限界。 |
| [秘密箱 35回＋1](https://www.youtube.com/watch?v=9cLZuxycbeY) | [写真付き開け方ガイド・12ページ](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/catalog/puzzle-box.pdf) | 36操作を写真で整理。実物での再現試験は未実施。 |
| [PHPの重大な脆弱性](https://www.youtube.com/watch?v=xSJaAFrZ7qw) | [要点まとめ・4ページ](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/catalog/php-security.pdf) | 技術解説の要点を整理。2026年10月23日時点の確認記録で、現在の対策情報を保証しない。 |
| [Wordの文字をきれいに揃える](https://www.youtube.com/watch?v=5bk8FDQaWy4) | [要点まとめ・4ページ](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/catalog/word-alignment.pdf) | 設定と操作を整理。実際のWord文書での再現試験は未実施。 |
| [クレーム対応](https://www.youtube.com/watch?v=Q2w4-mluYo0) | [初版研修資料・8ページ](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/catalog/complaints-original.pdf) | デザイン重視版との比較用。 |
| [クレーム対応](https://www.youtube.com/watch?v=Q2w4-mluYo0) | [デザイン重視版・8ページ](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/catalog/complaints-design.pdf) | 現在の研修資料の代表例。対応フロー、表現例、確認問題・解答・練習。 |
| [AI活用ビジネス6案](https://www.youtube.com/watch?v=hriu0irRcpE) | [初版要約・8ページ](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/catalog/ai-business-original.pdf) | 英語の動画を日本語に整理。 |
| [AI活用ビジネス6案](https://www.youtube.com/watch?v=hriu0irRcpE) | [デザイン重視版・9ページ](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/catalog/ai-business-design.pdf) | 現在のセミナー要約の代表例。6案の価値・条件を比較。 |
| [セミナー活用集客](https://www.youtube.com/watch?v=tRjStkeCaXs) | [通常版・7ページ](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/catalog/peatix-normal.pdf) | 同一動画で構成とデザインを比較するための版。 |
| [セミナー活用集客](https://www.youtube.com/watch?v=tRjStkeCaXs) | [デザイン重視版・7ページ](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/catalog/peatix-design.pdf) | 比較・フロー・数値の見せ方を変更した版。 |
| [セミナー活用集客](https://www.youtube.com/watch?v=tRjStkeCaXs) | [デザイン改善版・7ページ](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/catalog/peatix-design-improved.pdf) | 3版のうち後の改善版。講演の数値・集計差などの留保を明記。 |
| [MacBook Pro A1708 バッテリー交換](https://www.youtube.com/watch?v=5Gn5aZbzpdU) | [作業ガイド・要確認・11ページ](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/catalog/macbook.pdf) | 現在の作業手順書の代表例。加熱・溶剤・接着・小部品の復旧条件が不足しneeds_review。 |
| [AIの進化と起業の機会](https://x.com/ai_explorer25/status/2113976731854131272/video/1) | [X動画からの対談要約・9ページ](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/catalog/sam-altman-x.pdf) | X直接取込、ローカル音声認識、公式版との照合。対象はXの抜粋範囲。 |

ピアノでは、音やタイミングを含む動画を静止画の手順書にする限界が見られました。動画に合わせて資料化の方法を選ぶ必要があり、発表ではこの点に短く触れます。

## 作成経路と公開範囲

代表4例は、同じモデル・同じ条件による自動生成のベンチマークではありません。サッカーとMacBookは試作品のAPIなしモード、AIビジネスとクレーム研修の最新見本はチャットで作成した原稿をローカル描画処理でPDFにした例です。代表4例では有料AI APIを呼び出していません。

一覧には旧版のAPI実行例も含みます。初期の金魚2版にはOpenRouterの実行記録があり、後のAPIなし版と区別しています。画面のモデル選択欄にOpusと表示されていても、手動モードの資料をOpusのAPI生成結果とは扱いません。

各例の出典と作成経路は使用例ページと[代表例の記録](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/examples/provenance.json)、全PDFのページ数・ハッシュは[資料一覧の記録](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/catalog/manifest.json)を参照してください。照合は主に同じチャットでの自己点検で、独立した品質保証ではありません。映像・写真・講演内容の権利は各権利者に帰属します。

## 引き継ぎメモ：Opusでも比較したい

**最新の改善版について、Claude Opusを使うAPI経由の一連の比較テストはまだ行っていません。** 過去のClaude製の参考PDFや初期API版とは区別してください。

LucasからOpenRouterのAPIキーを共有してもらっています。時間があれば、このキーでOpusを使えるかを確認し、同じ条件で実験してみてほしいです。**料金がかかるので、使いすぎに注意してください。** 今回のREADME更新ではAPI実行はしていません。

1. キーは管理者から安全な方法で受け取り、OpenRouterを選ぶ。実際に利用できるOpusのモデルID・単価・残高を確認する。
2. まず短い動画を1本だけ使い、用途・言語・詳しさ・希望欄を揃える。比較の際は同じ動画・画像・字幕などの入力証拠を使う。
3. 少額の利用上限を決め、1件ずつ実行する。自動再試行や連続再生成は、原因と費用を確認してから行う。
4. 内容の誤り、工程と写真の対応、読みやすさ、手直し量、所要時間、API使用量・実費を記録する。条件が異なる場合はその差も残す。

APIキーの値はREADME・ソース・スクリーンショット・公開デモに載せません。Lucasのキーを公開ページに埋め込んだり、共有利用者全員へ配ったりしないでください。

## 開発者向け

試作品は、動画取得 → 画像・字幕／音声の抽出 → 内容案 → 紙面作成 → 元の証拠との照合 → ローカルPDF描画という構成です。APIなしモードではAIの応答をチャットで用意して取り込むため、完全自動生成の速度・精度とは区別します。

発表の説明は[発表メモ](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/presentation.md)、掲載手順は[GitHubへの掲載](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/publish.md)を参照してください。

## このリポジトリのコード

このリポジトリはRender用のDocker配置ソースです。Pythonモジュールは直下に置き、`editor.txt`はDockerビルド時に`/app/prompts/editor.txt`へ配置します。個別動画・APIキー・利用者セッション・Windows固有の実行パスは含みません。資料のPDFや説明ページは上記のクラウド紹介ページにリンクしています。

- `cloud_entry.py`：HTTPSオリジン確認、招待パスワード、クラウド用ポート待受。
- `share_gateway.py` / `server.py`：ブラウザ別セッション、設定・進行・ダウンロード。
- `pipeline.py` / `crv_worker.py`：動画・画像・字幕／音声の抽出、内容案、照合、紙面作成。
- `openrouter_client.py` / `usage_guard.py`：モデル接続とAPI使用量の管理。
- `render.cjs`：外部通信とJavaScriptを制限したローカルHTML→PDF描画。
- `security.py`：入力URL・API接続先・出力ヘッダーなどの検査。
- `Dockerfile` / `render.yaml`：FFmpeg・CPU Whisper・Chromium・日本語フォントを含むRender Free向けの候補設定。

### 配置状況

Dockerビルド・Render上の起動・ログイン画面表示は確認済みです。ログイン後の動画解析とPDF生成は実機検証中です。Free枠のメモリ・休止・一時ディスク、クラウドIPでの動画取得制限に注意してください。一般公開の安全性を承認したものではなく、招待した相手と使う試験用です。
