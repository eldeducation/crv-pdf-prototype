# 動画から用途に合った資料を作る 4つのユースケース

動画を、作業するとき・共有するとき・学ぶときに使える資料へ。YouTube・Xの公開動画リンクや動画ファイルから、内容と用途に合わせて写真・説明・図表を組み合わせたPDFを作る試作品です。

**2026年11月10日更新。** 各自のPCで自分のAIと使う配布版と、導入からPDF保存までの手順を掲載しています。4用途の見本と、これまで作成した13題材・22種類のPDFも閲覧できます。

## 各自のPCで、自分のAIと使う（2026-11-10）

**マイクラ風の操作サイトも同梱しています。** 各自のPCでサイトを起動し、ブラウザーで動画・用途を設定できます。開発者のPCやRenderの起動状態には依存しません。起動後の`127.0.0.1`のURLは、そのPCだけで使うアドレスです。

以下はWindowsで、**ローカルファイルを読み、画像を確認し、コマンドを実行できるAI開発ツール**と併用する手順です。AIは各自のアカウントで利用します。ブラウザーだけのAIチャットにログインしても、自動では連携しません。

### 1. ZIPをダウンロードして、すべて展開する

[配布ZIPをダウンロード](https://github.com/eldeducation/crv-pdf-prototype/releases/latest/download/crv-pdf-local.zip)し、右クリックから「すべて展開」します。GitHubの「Code → Download ZIP」ではなく、この配布ZIPを使ってください。展開後、`start.cmd`と`LLM-START.md`があるフォルダを開きます。ZIPの中から直接起動しません。

### 2. 自分のAIで、展開したフォルダを開く

AI開発ツールでそのフォルダを作業場所に指定します。ファイル読み取り・画像確認・コマンド実行を使える状態にしてください。ブラウザーのチャットだけを使う場合は、下の「ブラウザーだけのAIチャットを使う場合」へ進みます。

### 3. AIに初回準備と起動を依頼する

次の文章をコピーしてAIへ渡してください。

> このフォルダのLLM-START.mdを読んで、必要な環境を準備し、試作品を起動してください。AIのAPIは使わず、解析・画像抽出・内容確認・PDF生成の処理は変更しないでください。まずはサイトを開くところまで進めてください。

Python 3.12、Node.js 22以上、FFmpeg/ffprobeなどが必要です。初回は依存関係・音声認識用ライブラリ・PDF用ブラウザーをダウンロードするため、通信・空き容量・準備時間が必要です。不足するソフトの準備はAIの案内に従います。準備が整うと、**マイクラ風のサイトがブラウザーで開きます**。開かなければ、AIに起動したPC内のURLを案内してもらってください。

### 4. サイトで動画と資料の設定をして開始する

1. 「実行方法」で**「APIを使わないテスト」**を選ぶ。APIキーの入力は不要です。
2. YouTubeリンクを入力するか、手元の動画ファイルを選ぶ。
3. 「資料の用途」で「動画に合わせる／作業手順書／セミナー要約／研修資料」を選び、詳しさ・出力言語を設定する。
4. 必要なら「すっきり」「図解多め」「写真多め」「比較で整理」と追加の希望を指定する。未指定でもデザイン重視で作成します。
5. 解説音声がない動画では該当する設定を選び、**「テストを開始する」**を押す。

「テスト」という画面名ですが、実際のPDFを生成できます。サイトで開始したあとは、同じ動画をAIから重複して開始しないでください。

### 5. 同じAIへ「続けて作成する」と依頼する

同じフォルダを開いているAIへ、次の文章を渡します。

> サイトで開始しました。LLM-START.mdに従い、ai_handoff.pyで現在の依頼を読み、画像を実際に確認して回答を返してください。追加の依頼や修正にも対応し、PDFの確認まで進めてください。新しい生成を重複して開始せず、現在の生成を続けてください。

AIが、既存の内容整理・資料作成・照合・紙面確認の依頼に順番に回答します。**「回答ファイルを待っています」は計算中ではなくAIの回答待ちです。放置しても進みません。** 途中でAIが止まったら、現在の依頼を確認して続けるよう伝えてください。サイトとAIを使える状態にし、生成中はPCをスリープさせないでください。

### 6. PDFと編集用Markdownを保存する

完了したら、サイトの**「PDFを保存」**からダウンロードします。「編集用Markdown」も保存できます。**「要確認」**と表示された資料は、指摘を確認してから使ってください。写真と説明の対応も元動画で確認します。生成物は展開先の`app/runs`にも残ります。

### 次回の起動・困ったとき

- 次回からは同じフォルダをAIで開き、**`start.cmd`をダブルクリック**して、手順4から進めます。通常は初回セットアップをやり直す必要はありません。
- 起動しない場合は、エラー画面の内容をAIへ伝え、`LLM-START.md`に従って確認してもらいます。APIキーやパスワードをチャットへ貼る必要はありません。
- YouTubeリンクを取得できない場合は、手元の動画ファイルを指定してください。取得可否は回線と配信元の制限にも依存します。
- **ブラウザーだけのAIチャットを使う場合**：同じサイトで「APIを使わないテスト」を選び、指示・画像のZIPを保存してチャットへ渡します。返ってきた回答JSONを「回答を読み込んで続ける」で取り込み、依頼ごとに繰り返します。[詳しい受け渡し手順](distribution/MANUAL-TEST.md)。チャットへのログインだけでサイトとAIが自動接続するわけではありません。
- [受け取った人向けの導入案内](distribution/START-HERE.md)と同じ手順を配布ZIPのREADMEにも同梱しています。AIの契約・利用枠は各自のものです。この方式では外部の動画取得サービスやAI APIキーを使いません。

配布ZIPは公開ソースと同じ生成処理を使います。研修用途の構成改善は下記のとおりです。モデル・推論設定・会話履歴が違う場合の精度や完全一致は保証できません。生成ソースの識別子はZIP内の`QUALITY-BASELINE.json`に記録します。配布物のソース一致とオフライン検証を行い、別PCでのクリーンインストールは未検証です。

## 研修資料の構成改善（2026-11-10）

以前の教材の構成と、Opus版の具体例・写真の利点を両立させるため、「研修資料」を選んだときの編集指示と提出検査を改善しました。

- 学習目標・全体像から始め、要点と判断の関係、動画の具体例を説明する。
- 確認問題と応用練習を先に置き、解答・理由・進め方は後の別ページへ分ける。問題と答えの横並びを避ける。
- 応用練習は教材用の架空の場面と明記し、動画の実話と混同させない。実務へ持ち帰るため、適用先で相談・記入する項目も用意する。
- 写真は例文・重要表示・操作の変化に役立つ場面を選ぶ。似た話者写真やスライドを枚数のために増やさず、必要な準備・ガイド・中間操作の写真は維持する。

`training_quality.py`が、`training_plan`と実際の本文の原文・ページ・出典の対応、問題と解答の分離、応用練習・記入項目の実在を、既存の提出時に検査します。形式の一致だけでは意味の正しさを証明できないため、具体例・解答の根拠、架空の場面の表示、未確認の社内ルールの断定、写真の有用性は既存の内容照合でも確認します。別のAI工程は増やしていません。

研修用途以外にこの構成は強制しません。既存PDFは変更せず、改良は新規生成・作り直しに適用します。保存途中の旧版ジョブは生成仕様が変わるため、そのまま再開できません。今回の改善後の実モデルによる品質・費用の再測定はまだ行っていません。

## 共有リンクと現在の公開状況

- **[動画から資料を作る試作品（招待制）](https://crv-pdf-prototype.onrender.com/)**：Render Freeに配置しました。開発者のPCがスリープしていても、クラウド側で動作します。招待用パスワードは管理者から別途受け取ってください。**ログイン後、6秒・音声なしの自作動画を使い、画像抽出から日本語PDF・編集用MarkdownのダウンロードまでAPIなしで確認しました。YouTubeの直接取得は11月4日にクレーム動画で実機検証しましたが、YouTubeの認証要求で失敗しています。URL取り込みは未解決です。長い動画、音声認識、Xの直接取得、有料API生成はクラウドで未検証です。**
- **[紹介・操作デモと全PDF見本](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/)**：APIキー不要で、用途切り替え・アレンジ選択・資料検索・PDF閲覧を試せます。この紹介ページ内では新しいPDFを生成しません。
- **[公開プログラムとREADME](https://github.com/eldeducation/crv-pdf-prototype)**：キー・動画・利用者セッション・ログを除いたコードを公開しています。
- [クラウド配置の手順と制約](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/deployment/README.md) / [配置用ソース一式](https://crv-pdf-video-showcase.eldesign-8040.chatgpt.site/deployment/cloud-generation.zip)：Dockerビルド、起動、短いアップロード動画の画像抽出・PDF描画は成功しました。音声認識や長い動画の処理が無料枠に収まるかは未検証です。

クラウド版でAPI生成する場合は、利用者が自分の対応APIキーを試作品に入力します。API料金はそのキーの利用者が負担します。キーはクラウドサーバーのメモリで扱い、抽出画像・字幕などは選択したAIサービスへ送信します。上記の各自PCでAIと併用する方式では、APIキーは不要です。

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

通常のAPI生成には、利用者自身の対応APIキーと利用料金が必要です。費用の上限は入力しなくても、動画の準備後に計算した費用の目安から自動で決まります（目安が高いときはAIを使う前に確認します。詳しくは下の「2026-11-06〜09」）。APIなしのテストは、チャットで作った回答JSONを取り込む手動の検証モードです。

GitHubの開発用ソースを直接使う場合は `start_local.cmd`、配布ZIPを使う場合は上記の `start.cmd` で起動します。開発用ソースではアドレスを `server.local.json` に保存します。APIキーを設定するときに「このPCに保存する」を選ぶと、Windowsのユーザーアカウントで暗号化して保存し、次回の起動でも使えます。選ばなければ従来どおりメモリ内だけで、一定時間使わないと消えます。「接続を解除」で保存したキーも削除されます。共有用のセッションでは保存できません。APIなしでAIと併用する場合は、このキー設定は不要です。

生成データは `runs` に溜まります。`python cleanup_runs.py` で各フォルダーの容量と状態を一覧でき（何も消しません）、`--delete` を付けると確認の上で古い失敗分だけを削除します。完成・要確認の資料、他の生成が動画や画像を再利用している元データ、実行中・2日以内・最新の失敗分は削除の対象外です。

作成済みの資料は「内容を保って仕上がりを変更」で、動画・画像・内容案を再利用して別のアレンジで作り直せます。過去の内容確認済みの資料から選べます。

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

## API接続後のモデル選択（2026-10-30）

APIキーを設定すると、接続先のモデル一覧を自動取得します。固定の2モデルには限定していません。OpenRouterは、そのキーの利用設定・プライバシー設定・制限を反映した一覧を取得します。AnthropicはModels APIのページを最後まで取得します。

- 名前・モデルIDで検索し、使用するモデルを選択できます。「一覧を更新」で再取得できます。
- 一覧には非対応モデルも理由付きで表示します。資料作成には画像入力・文章出力・ツール機能が必要です。追加料金の見積もりに未対応のモデルも選択対象外です。
- 対応仕様が確認できないモデルはその旨を表示します。一覧の取得だけでは残高や生成成功まで保証しません。
- キー変更・接続解除・期限切れで一覧を破棄します。キーは一覧取得時も固定の公式APIにだけ送信し、リダイレクトを許可しません。
- 一覧取得はAI生成を呼びません。モデルに応じて非対応の推論パラメーターを省き、提供元の出力上限を守ります。直接Anthropic接続ではサーバーの料金設定が別途必要です。

推論設定もモデルに合わせて切り替わります。GPTは「Reasoning effort」、Claudeは「Effort」としてAPIの設定値を表示します。OpenRouterの `reasoning.supported_efforts` とAnthropicの対応機能を優先し、未取得時は確認済みのSol／Opusの仕様を使います。仕様不明のモデルは「モデル標準（自動）」だけを表示し、推論設定を送信しません。「超高」など独自の訳語や、チャット画面のモード名との混同を避けています。

`model_catalog.py` が一覧取得・対応機能の判定を担当します。`test_model_catalog.py` は偽キーとモック応答による無料の回帰テストです。実際の全モデルでのPDF生成を検証したという意味ではありません。

## 引き継ぎメモ：Opusでも比較したい

**最新の改善版について、Claude Opusを使うAPI経由の一連の比較テストはまだ完了していません。** 2026-11-06にOpenRouterのOpus 5.5で6回試し（約$12.5）、見つかった不具合を直しましたが、内容確認済みの完成PDFには届いていません（詳しくは下の「2026-11-06〜09」）。過去のClaude製の参考PDFや初期API版とは区別してください。

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
- `cost_estimate.py`：AIを使う前の費用の目安と自動上限。`prompt_cache.py`：同じ前半部分のキャッシュと料金計算。
- `document_design.py` / `editorial_quality.py`：デザイン重視の部品・配色と、紙面設計・紙面確認の検査。
- `markdown_export.py`：ページのHTMLから編集用Markdownを作る。
- `fixtures/drafts/`：回帰テスト用の下書き（架空の文章。画像はテスト時に生成し、動画の内容は含まない）。
- `render.cjs`：外部通信とJavaScriptを制限したローカルHTML→PDF描画。
- `security.py`：入力URL・API接続先・出力ヘッダーなどの検査。
- `Dockerfile` / `render.yaml`：FFmpeg・CPU Whisper・Chromium・日本語フォントを含むRender Free向けの候補設定。

### 変更の進め方と自動テスト（2026-11-05）

Codex・Claude Code・人が並行して変更するため、GitHubの`main`を唯一の正本とします。

1. 作業前に`git pull`で最新の`main`を取り込む。ファイル単位のコピーで上書きしない（古いコピーで他の人の変更を戻す事故が実際に起きたため）。
2. 変更はコミットし、`main`へのpushかプルリクエストで反映する。
3. pushとプルリクエストごとに、GitHub Actions（`.github/workflows/tests.yml`）がPythonテストとアップロード画面のJavaScriptテストを自動で実行する。結果はGitHubの「Actions」タブで確認できる。APIキー・動画のダウンロード・AI呼び出しは使わない。
4. Renderへのデプロイは、テストが通った`main`を「Deploy latest commit」で行う（自動デプロイは無効）。

テスト用の依存は`requirements-test.txt`です。音声認識（PyTorch）を除いた構成で、`requirements.txt`とDockerfileのyt-dlp固定と版をそろえます。

### 2026-11-09：配布・描画テスト・過去ログ・再開案内の改善

- **[各自のPC向け配布版](LOCAL-DISTRIBUTION.md)**は、mainのテストが通った同じコミットから自動作成し、GitHub Releasesへコミットごとに保存します。最新版ZIPの固定リンクを用意しました。11月5日のZIPは旧版として残します。利用者の設定・動画・履歴・DPAPI保存キーは同梱せず、実行環境のパスは各PCで作ります。
- 画面下部にコミットとソース識別子を表示し、ZIP内のbuild-info.json・MANIFEST.jsonと照合できます。共有セッション用の画面変更は元の版情報を保持し、ソースを変更すると識別子も変わります。
- 描画テストは実際の描画エラーを失敗として扱います。ローカルでNode/Playwright/Chromiumが未導入の場合だけスキップでき、CIではブラウザー・日本語フォントを用意して描画を必須にします。
- 過去のエラー・review_note・確認メモに残ったキー管理URLやキー形式の値は、画面表示とrun.json・usage.json・review-notes.txtのダウンロード時にも伏せます。元の保存記録とPDF本文は変更しません。
- 内容案が利用可能なら、編集用の保存位置がまだなくても「資料・PDFの作成」から再開と案内します。過去の仕上がり変更でも確認済みの元資料を再検証します。再整理が必要なら、その理由とAPI追加料金の可能性を表示します。API未接続の有料再開はボタンを無効にし、APIなしモードではキーを要求しません。

この変更は生成のモデル・プロンプト・画像抽出やPDFの内容基準を変更しません。有料APIによる生成はこの修正では実施していません。公開版への反映と配布ZIPの作成結果は、GitHub Actionsと実行画面の版表示で確認してください。

## 配置状況

Dockerビルド・起動・招待ログイン・6秒の無音アップロード動画からの画像抽出・日本語PDFとMarkdownの保存を確認しました。APIなしの手動応答テストで、有料API・音声認識・長い動画・Xのクラウド取得は未検証です。YouTube URL取得は実機検証で認証要求が残り、未解決です。Renderの通信元自体がGoogleに拒否されていることを確認済みです（下記「原因の切り分け」）。Free枠のメモリ・休止・一時ディスク、クラウドIPでの動画取得制限に注意してください。一般公開の安全性を承認したものではなく、招待した相手と使う試験用です。

## 2026-11-06〜09：デザイン重視の紙面・費用・検査の改善

この記載はソースの変更内容です。ローカル環境で確認しており、Renderへは反映していません。

### 雑誌風の部品（デザイン重視）

- 表紙（`.cover`・`.kicker`・`.cover-media`）、ひとことで言うと（`.tldr`）、要点3つ（`.keypoints`）、章見出し（`.chapter`：番号・PART・時刻）、矢印の流れ（`.chevrons`）、枠付き写真（`.shot`）、大きな引用・数字（`.quote-xl`・`.bigstat`・`.tiles`）、POINT枠（`.point`）、比較（`.versus`）、問答（`.qa`）、導入文（`.lede`）を用意しました。使い方は`editor.txt`に例付きで記載しています。
- 部品のスタイルは用意済みで、6つの配色に対応します。AIのcssでこれらのクラスを指定したルールは使わず、外したルールをAIに伝えます。
- AIが部品と同じ役割のものを独自クラスで作った場合（例：`.chap`・`.kp`・自前の矢印）、そのページに注意を付けます。注意はAIが直すか、紙面確認で理由を書きます。

### 紙面検査

- 文字と背景のコントラスト比を測ります。読めない文字（小さい文字で3未満、大きい文字で2未満）はエラー、4.5未満（大きい文字は3未満）は注意です。写真やグラデーションの上の文字は対象外です。
- はみ出しのエラーは、要素・文字・方向・px数を示します。大きな数字の文字枠による誤検出を避けるため、文字の大きさに応じた余裕を見ます。
- ページの充填が55%未満、横長の画面写真が本文幅の45%未満、1ページ目に表紙・要旨がない場合も注意を出します。

### AIの資料作成の流れ

- 編集用Markdownは、ページのHTMLから自動で作ります（AIは書きません）。AIの出力が約3割減り、PDFとMarkdownの内容が一致します。部品は「**ひとことで言うと：** …」「**3** 試した版の数」「**POINT：** …」「**Q.** … / **A.** …」、引用ブロックのように読みやすい形にし、`<final_verdict>`のような文字・箇条書き・改行も保ちます。
- 修正はページ単位（`revise_pages`）で差し替えられます。差し替えても毎回、資料全体を描画・検査・照合し直します。
- 提出前チェックリスト（必要な画像のファイル名、紙面設計の引用の条件など）を最初に渡し、検査の問題はまとめて返します。
- 処理は最大7回、映像の追加確認は最初の2回まで、はみ出しだけの修正は3回までです。資料作成の出力上限は65,536トークン（モデルの上限内）です。

### 費用

- 費用の上限は通常は入力不要です（詳細設定で手動指定も可）。動画の準備後、AIに送る量とモデルの単価から費用の目安を計算し、目安の高い方の約1.3倍（1回の生成で最大$10）を自動の上限にします。目安が$5を超えると、AIを使う前に確認します。管理者は環境変数`VIDEO_PDF_MAX_RUN_USD`・`VIDEO_PDF_CONFIRM_USD`で変更できます。
- 毎回同じ部分（指示・内容案・動画の画像）をキャッシュします（資料作成は1時間、分析は5分、最後の照合は使わない）。キャッシュが切れないよう、各工程の道具の一覧は毎回同じにし、映像確認の締め切りは呼び出しごとに断る形にしています。過去の実測データからの試算では、1回あたり約6〜15%の節約です（実測は未実施）。
- OpenRouterの401・402・403は理由を表示してすぐ止めます。402は出力上限をその工程で必要な分に下げて1回だけ送り直し、それでも断られたら、1回の処理に必要な残高の目安と、OpenRouter自身の説明（キーとURLを伏せ、最大300文字）を表示します。さらにキーの残りを確かめ、「キーの上限が足りない」か「アカウントのクレジット残高が足りない」かを書き添えます。
- AIを使う前に、キーの上限の残りを確認します。費用の目安の低い方にも足りなければ、料金ゼロのまま止めます。
- AI接続の欄の「キーの残りを確認」で、OpenRouterのキーの上限・残り・使用額を、ログインせずに確認できます（AIの生成は呼びません）。サーバーが問い合わせ、金額だけを表示します。キーの値・名前・アカウントのIDは返しません。結果は15秒間使い回します。アカウント全体のクレジット残高は、普通のキーでは確認できません。

### 使い勝手

- 「内容を保って仕上がりを変更」で、過去の内容確認済みの資料から選んで作り直せます（サーバー再起動後も）。APIなしで作った資料を、APIで作り直すこともできます。

### 検証状況

- 自動テスト：Python 171件、画面のJavaScript 6件。保存済みの下書きを模したテスト（`test_saved_drafts.py`）で、組み立て・Markdown・ページ単位の修正・紙面検査を確認します。ページを描画するテストは手元の環境だけで実行され、GitHub Actionsでは省略されます。
- APIなしのテストで、セミナー動画の作り直しを最後まで実行しました（14ページ、内容確認済み）。この中で見つかった不具合（`<mark>`の拒否、修正回数、Markdownの書式）を直しました。
- OpenRouterのOpus 5.5による有料テストは6回、合計約$12.5です。不具合を直しながら進めましたが、内容確認済みの完成PDFには届いていません（最後は残高・キー上限による402）。キャッシュの効果と費用の目安は、次の有料テストで実測が必要です。
- 2026-11-09の再試行（3回）は、いずれもAIの呼び出し前に402で断られ、料金はかかっていません。キーの上限は$50で残り$30.42でしたが、OpenRouterの説明は「1,915トークン分しか払えない」というもので、**キーが属するアカウントのクレジット残高の不足**と判断しました。補充はキーの持ち主（アカウント管理者）が行う必要があります。費用の目安は約$1.87〜3.45、自動の上限は$4.48でした。
- 2026-11-09のレビューで見つかった10件（Markdownの文字・箇条書き・改行、402への対応、修正の案内、トークン上限の計算、キャッシュの無駄など）も修正済みです。

## 2026-11-05：200MBアップロード対応

共有版の動画上限を90MBから200MBへ変更する実装です（200 × 1024²バイト）。ローカル版は従来どおり1GBです。この記載はソースの変更内容であり、稼働中のRenderへの反映完了を示すものではありません。

- ブラウザーは動画を8MBずつ順番に送信し、進捗を表示します。ゲートウェイと受信サーバーは64KBずつ転送・保存し、動画全体をメモリへ読み込みません。
- 完了した動画だけを生成処理へ登録します。総サイズ、送信順序、ファイル形式、認証・CSRFを検査し、共有セッションの合計512MBの制限には未完了分の予約も含めます。
- 中断した転送の部分ファイルは失敗時に取り除きます。1時間以上更新されない、この受信処理が作った部分ファイルは次のアップロード時に片付けます。既存の完成済み動画・PDFは削除しません。
- ローカルHTTP経由で200MBのテストデータを転送し、保存ファイルのサイズとSHA-256が一致することを確認しました。200MB超過の拒否、途中切断、順序異常、容量制限、認証チェックも検証しています。実際の200MB動画の解析・音声認識・有料API生成や、Renderの実環境での転送成功までは確認していません。

検証コマンド：`python -m unittest discover -v`（75件成功）、`node --test test_video_upload_ui.cjs`（6件成功）。後者はブラウザー送信処理をモック応答で検証します。

本番反映前には進行中の生成がないことと、必要な動画・PDFの保存を確認してください。Renderの再デプロイでは一時データが失われる可能性があります。問題があれば、この変更のコミットを取り消す新しいコミットを作り、履歴を保持したまま戻します。過去の履歴の削除・強制上書きは行いません。

## 2026-10-30：生成条件を維持したセキュリティ改善

環境変数の受け渡しを限定し、セッション起動中の共有ロックを解消しました。エラー表示の内部パスを伏せ、秘密情報を含めない操作ログを追加しました。モデル・プロンプト・画像抽出条件・音声認識・PDFの組版は変更していません。変更前後のテスト入力・Markdown・PDF本文・全ページ画像・動画フレームが一致しています。[対応範囲と残る課題](SECURITY.md)を参照してください。


### YouTube URL取り込みの検証（2026-11-04）

- Node 24とyt-dlp 2026.10.26/EJSを明示設定し、匿名クライアントの限定的な再試行を追加しました。
- yt-dlp公式ガイドで案内されているbgutil PO Token provider 2.0.2を固定バージョンで導入しました。取得用の子プロセスのみで動き、HTTPサーバーを公開しません。個人のYouTube CookieやAIキーは渡しません。
- 同じ公開URL `https://www.youtube.com/watch?v=Q2w4-mluYo0` をRender実行環境で2回確認しました。JS設定後・PO Token対応追加後とも `youtube_verification` で失敗しました。後者は74.9秒、AI呼び出しは0回です。これは動画の内容解析やモデルの問題ではありません。現環境でYouTube URLが利用可能になったとは主張しません。
- 自動ダウンロードテストは通常起動では無効です。管理者が `VIDEO_PDF_VERIFY_YOUTUBE` を明示設定したときだけ、最大300秒・一時ファイル削除付きの取得検査を行います。結果ログは成否などに限定し、認証情報やトークン本体は出力しません。
- 依存元：[yt-dlp EJS](https://github.com/yt-dlp/yt-dlp/wiki/EJS)、[PO Token Guide](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide)、[bgutil provider 2.0.2](https://github.com/Brainicism/bgutil-ytdlp-pot-provider/tree/2.0.2)。bgutilはGPL-3.0-onlyで、コンテナに元ライセンスを含めています。プロバイダーの説明にも、トークンはIP単位のログイン制限を解除するものではないと明記されています。


### 個人ログインを使わないChromium方式の検証（2026-11-04）

Render内の一時ChromiumとWPC provider 1.1.2 / nodriver 0.50.3を使い、同じクレーム動画URLで検証しました。ブラウザー起動待ち、仮想画面の限定的な環境変数受け渡し、プラグイン登録、共有する非同期ループを調整しました。

| 実機テスト | ブラウザー起動 | トークン作成 | 動画取得 | 時間 |
| --- | --- | --- | --- | --- |
| 匿名ブラウザー方式（`cdb319d`） | 成功 | 成功 | YouTubeが認証を要求 | 60.5秒 |
| 新規匿名セッション・User-Agentも一致（`e2bb283`） | 成功 | 成功 | YouTubeが認証を要求 | 58.5秒 |

**ブラウザー方式は動作しましたが、動画本体の取得は未解決です。** Renderでブラウザーを動かせないという結果ではありません。認証要求の内部条件までは特定しておらず、RenderのIPだけが原因だと断定しません。通常の生成処理へこの実験方式を接続していません。

- 個人のGoogleログイン・既存ブラウザープロファイル・個人Cookie・プロキシ・AI APIを使っていません。匿名セッション方式では、新しく作ったブラウザー由来の匿名Cookie名だけを許可し、取得処理のメモリ内で使いました。Cookie値・トークン値はログに出しません。
- ブラウザーのsandbox・証明書検証・サイト分離を維持しました。起動用のループバック接続を待ち、準備後に取得ライブラリを接続します。
- 実験は管理者専用の起動フラグ `VIDEO_PDF_VERIFY_YOUTUBE_BROWSER` で実行します。通常のDocker起動では無効です。子プロセスの待機は240秒、時間切れにはプロセス群を終了させます。一時ファイルの後処理は別に行います。
- ソースは `youtube_browser.py`、入力制限・匿名Cookieの限定・環境変数の除外・保護設定・停止処理のオフラインテストは `test_youtube_browser.py`（8件成功）です。モデル・プロンプト・抽出画像・字幕／音声・PDF組版は変更していません。
- 依存元：[WPC provider](https://github.com/coletdjnz/yt-dlp-getpot-wpc)（MIT）。これは取得方式の実験記録で、一般公開に向けた安全性監査やPDF生成成功の記録ではありません。


### 原因の切り分け：Renderの通信元がGoogleに拒否されている（2026-11-04）

これまでの検証では、普通のブラウザーでも同じ拒否を受けるかを確かめていませんでした。そこで `youtube_diagnose.py` を追加し、Render実機で1回ずつ（再試行なし・AI呼び出し0回）次を確認しました。

| Render実機（Oregon・IPv4のみ）での確認 | 結果 |
| --- | --- |
| 新規プロファイルの匿名Chromiumで通常の視聴ページを開く | **Googleの「異常なトラフィック」確認ページ（CAPTCHA）へ転送** |
| プライバシー強化の埋め込みページ | ページは開くが再生されない |
| yt-dlpの9クライアント（web、web_safari、mweb、tv、tv_simply、web_embedded、android_vr、ios、android） | 全クライアントが「bot確認のためログイン」を要求 |
| IPv6での接続 | Renderから利用できない |

- 別リージョンでも確認するため、無料の一時サービスをFrankfurtに作って同じ診断を実行しました（302.7秒、AI呼び出し0回）。匿名ブラウザーはYouTubeを開けたものの、プレーヤーが「botでないことをログインで確認」（`LOGIN_REQUIRED`）を返して再生されず、9クライアントもすべて同じ要求でした。IPv6も利用できませんでした。確認後、この一時サービスは削除しました。
- 同じ動画・同じコード・同じyt-dlp 2026.10.26を開発者PCの家庭回線で実行すると、android_vrとmwebで再生可能な形式を取得できました。
- 以上から、**原因は取得設定ではなく、Renderの共有の通信元IPがGoogle側で拒否されていること**と判断しました。OregonとFrankfurtの2リージョンで同じ結果でした。PO Token・クライアント変更・匿名Cookie・User-Agent一致では解除できません。Renderの有料プランに変えても通信元は共有のままのため、解決は見込めません。
- CAPTCHAの自動突破は行いません。個人のGoogleログインやCookieも使っていません。
- 検証途中で、yt-dlpのコマンド行既定値（`ignoreerrors='only_download'`）がエラーを握りつぶし、拒否が「形式なし」と表示される問題を見つけて修正しました。
- 診断は管理者専用の起動フラグ `VIDEO_PDF_DIAGNOSE_YOUTUBE` を設定したときだけ動きます。最大600秒で、ログには決められた項目だけを出し、IPアドレス・Cookie・トークンは出力しません。検証後、この設定はRenderから削除しました。オフラインテストは `test_youtube_diagnose.py` です。

**URL入力を維持して取得するには、最低限「YouTubeへの通信元を変える」条件変更が必要です。** 候補は、YouTube通信だけを住宅回線系のプロキシ経由にする方法（有料・認証情報が必要）か、Google側で拒否されていない別のネットワークで取得処理だけを動かす方法です。どちらも実施前に管理者の判断が必要です。
