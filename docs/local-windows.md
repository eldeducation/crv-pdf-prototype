# Windowsでの使い方（管理者権限なし・このリポジトリのメインの使い方）

このリポジトリをWindowsにそのまま置いて使う方法です。必要な部品はすべてフォルダー内の `_runtime\` に入り、PC全体には何も入れません（レジストリ・PATHの変更なし）。
配布ZIP（`distribution/`・[LOCAL-DISTRIBUTION.md](../LOCAL-DISTRIBUTION.md)）は、別のPCに渡すための版として残しています。

## フォルダーの中身
| 場所 | 内容 |
| --- | --- |
| `1_setup.bat`〜`5_autostart_*.bat` | ダブルクリックで使う入口（準備・起動・動画ダウンロード・チャットモード・自動起動） |
| `local\windows\` | 上の入口が呼び出すPowerShellスクリプト |
| `chat_worker.py` | チャットモードの受付係（[docs/chat-mode.md](chat-mode.md)） |
| `tests\` | 自動テスト（`python -m unittest discover -s tests -p "test_*.py"`） |
| `_runtime\`・`runs\`・`chat-jobs\`・`完成PDF\`・`成果物\`・`downloads\`・`_backup\` | 各PCで作られるデータ。GitHubには上げない |

## 使い方
1. `1_setup.bat` をダブルクリック（初回のみ・10〜20分程度、約2〜3GBダウンロード）
   - 最後に `RESULT` の各行が `OK` になっていれば完了。ログは `_runtime\setup-log.txt`
2. `2_start.bat` をダブルクリック → ブラウザーが `http://127.0.0.1:ポート/トークン/` で開く
   - このPC内（127.0.0.1）だけで動きます。外部公開はしません。
   - 終了はウィンドウを閉じるか Ctrl+C

## チャットモード（APIキー不要・おすすめ）
Claudeのチャットに動画のURLかファイルパスを送るだけで、完成したPDFがチャットに返ってくる使い方です。
AIの部分はチャットのClaudeが担当するので、APIキーもAPI料金も不要です。

1. `4_chat_mode.bat` をダブルクリックして、開いたウィンドウはそのままにしておく
   （毎回起動するのが面倒なら `5_autostart_on.bat` を一度実行すると、Windowsにサインインしたとき自動で起動します。やめるときは `5_autostart_off.bat`）
2. チャットで「この動画をPDFにして」とURLかパスを送る（用途：動画に合わせる／作業手順書／セミナー要約／研修資料 なども指定可）
3. 完成すると `完成PDF\` に保存され、チャットにもPDFが届く

仕組み：`chat-jobs\inbox\` に置かれた依頼をこのウィンドウが処理し、AIへの依頼が出るたびにチャットのClaudeが回答ファイルを置く。
途中経過は `chat-jobs\status\`、待機中のAI依頼は `runs\chat-bridge.json`。止めたいときは `chat-jobs\cancel\<依頼ID>` を作る（Claudeに言えばやります）。

## 入るもの（すべて `_runtime\` の中。PC全体には入れません）
| もの | 用途 |
| --- | --- |
| uv + Python 3.12（venv） | アプリ本体 |
| claude-real-video（crv）＋ openai-whisper（CPU版torch） | 動画からの画像・字幕／音声認識の抽出 |
| yt-dlp（deno付き） | YouTube・XのURL取り込み |
| FFmpeg / ffprobe | 動画処理 |
| Node.js 24（zip版）＋ Playwright 1.56.1 ＋ Chromium | HTML→PDF描画 |

`prompts\editor.txt` はDockerビルド時に作られる配置をローカル用に再現したコピーです。

## 注意
- APIキーは設定していません。画面の「APIなし（手動）モード」で試せます。キーを入力するとOpenRouter/Anthropicの**有料API**が動くので、入力は自己判断で。
- Whisperのモデル（base・約140MB）は初回の音声認識時に `runs\cache` へダウンロードされます。
- 削除したいときは、このフォルダごと消せば完全に消えます（レジストリ・PATHの変更なし）。

## 変更の記録
- 2026-11-05：Windowsで `[WinError 5] アクセスが拒否されました` で停止する問題を修正。
  進捗ファイルの上書き（`progress.json` など）が画面の読み込みとぶつかると失敗するため、短時間リトライするようにした。
  追加：`atomic_io.py`／変更：`job_progress.py`・`checkpoints.py`・`usage_guard.py`・`source_references.py`・`share_gateway.py`
- 2026-11-05：「途中から再開する」で、内容整理の工程（content_plan など）をAIがもう1回だけ修正・再提出できるようにした。
  初回生成の回数や品質チェックの基準は変更なし。変更：`content_quality.py`
- 2026-11-05：内容整理（content_plan）の1回あたりの出力上限を 24,576 → 49,152 トークンに拡大。
  推論xhighで思考と構成案が上限を超え、返答が途切れる問題への対応。他の工程の上限は変更なし。変更：`usage_guard.py`
- 2026-11-05：`2_start.bat` が毎回同じアドレス（ポート・URL）で起動するよう変更（`server.py --reuse-address`）。
  起動時にポート使用中のエラーが出たら `server.local.json` を削除してから起動し直す。変更：`start.ps1`
- 2026-11-05：`3_download.bat` を追加。URLの動画を `downloads\` に720pで保存し、90MBを超えたらRender用の小さいコピー（`-90MB.mp4`）も作る。追加：`3_download.bat`・`download.ps1`
- 2026-11-05：「APIを使わないテスト」モードに**チャット連携**を追加（APIキー・API料金なしで、Claudeのチャットが AI 役を担当）。
  依頼が出ると `runs\chat-bridge.json` に依頼フォルダーが書かれ、その中に `chat-response.json` を置くとアプリが自動で読み込む。
  回答は従来どおり request_id と形式のチェックを通す。不正な回答は `chat-response.rejected-N.json` に退避され、理由が `chat-response-error.txt` に出る。
  画面からの回答アップロードも従来どおり使える。変更：`manual_client.py`
- 2026-11-05：チャットモードを追加。追加：`chat_worker.py`・`chat_worker.ps1`・`4_chat_mode.bat`・`autostart.ps1`・`5_autostart_on.bat`・`5_autostart_off.bat`

## 2026-11-11 GitHub最新版（8ecf781）へ更新
- 上流の45コミット（11/5〜11/10）を反映。新規58・変更26ファイル。変更前のファイルは `_backup\20261105-aae83a8\` に保存。
- 上流の主な変更：資料作成のAIやり取り5→7回、末尾の「まとめ」ページ必須、研修資料の構成改善、HTML検査の改善、費用見積もり・照合キャッシュ、APIキー保存（任意）など。必要ライブラリは変更なし（再セットアップ不要）。
- ローカル修正は新しいコードに再適用：WinError対策（`atomic_io.py`）、再開時の追加修正1回（`content_quality.py`）、内容整理の出力上限49,152（`usage_guard.py`）、チャット連携（`manual_client.py`）、`app_version.py` の配布対象に `atomic_io.py` を追加。
- チャットモード一式（`chat_worker.py` など）、起動・ダウンロード用の bat/ps1 はそのまま。
- 上流の自動テスト233件がこの状態で成功（クラウド環境で確認）。見本PDF（docs/examples）と配布ZIPはコピーしていない。
- 注意：更新前に途中停止した生成は、仕様変更のため「途中から再開」できない。
- 2026-11-11：チャットモードに**検証レポート**を追加（APIは呼び出さない）。
  生成が終わる（または止まる）と、同じ回答をAPIで行っていた場合の目安をまとめる：AIへの依頼回数とAPIの回数上限、
  形式の不備で受け付けられなかった回答の数、アプリの検査での差し戻しと理由、依頼ごとの入力・出力の分量とAPIの出力上限、API換算の費用の目安。
  出力先：`runs\<run>\chat-report.json`・`chat-report.txt`、`完成PDF\<PDF名>_検証レポート.txt`、`chat-jobs\status\<id>.json` の `report`。
  依頼ファイルに `answerer`（回答したAIの名前・条件の自由記入）と `api_rates`（[入力, 出力] の100万トークン単価、既定 4・20）を書ける。
  費用は回答の分量だけの目安で、APIの「考える過程」の出力は含まない。生成の流れ・検査・回数の数え方は変更なし。
  変更：`chat_worker.py`・`manual_client.py`（変更前は `_backup\20261111-report\`）
- 2026-11-12：GitHubの最新版（9df49a7）に更新。ローカルの追加・修正（チャットモード、検証レポート、Windowsの書き込みエラー対策、
  内容整理の出力上限49,152、`*.bat`／`*.ps1` 一式）はそのまま残した。
  GitHub側の主な変更：差し戻された提出を最大2回まで修正して再提出できる仕組み（途中再開後も回数を引き継ぐ）、表紙の配色と文字の読みやすさの検査、
  PDFの強調表示の修正、Render版のログイン・メモリ診断。
  2026-11-05の「再開時に内容整理をもう1回だけ再提出できる」ローカル修正は、GitHub側の上の仕組みに含まれるため外した（`content_quality.py` はGitHub版のまま）。
  変更前のファイルは `_backup\20261112-9df49a7\`。
- 2026-11-12：作業手順書（用途 procedure）の**書き方ルール**を追加。読者が動画を見ずに作業できる文章にするため、
  です・ます調で言い切る、動画の実況や照合の記録を本文に書かない、不明点は該当手順の最後に※注1行だけ、表紙に作り手の説明を書かない、などを指示。
  他の用途（セミナー・研修など）と検査の仕組みは変更なし。
  変更：`editor.txt`・`prompts\editor.txt`（【作業手順書の書き方】を追加）、`document_options.py`（procedureの説明文）、
  `document_design.py`（procedure用の指示を1項目追加）。変更前は `_backup\20261112-procedure-rules\`。
- 2026-11-12：資料作成で「操作の説明と写真をsection data-step-unitsでまとめてください」が何度も出て、回数上限で止まる問題を修正。
  原因は、まとめ・表紙で工程を振り返るときに付けた出典spanまで「工程ブロックの外の説明」と判定していたこと。
  表紙・ひとことで言うと・要点・まとめ（.cover・.tldr・.keypoints・.wrapup）の中は対象外にし、エラーには何ページ目のどの工程かを表示するようにした。
  変更：`presentation_quality.py`（変更前は `_backup\20261112-step-check\`）。
  あわせて、止まった生成 `runs\20261112-135819-b27bc5` を「資料作成」からやり直せるよう、停止理由と資料作成の保存状態をリセット（元のファイルは同フォルダーの `_before_resume\`）。
- 2026-11-12：外部資料の出典表示を、同じページ内では同じ資料につき1回だけにした。
  これまでは工程ごとに「[外部資料: AirTagの電池を交換する方法 - Apple サポート (日本)]」が繰り返し入り、紙面があふれて回数上限で止まっていた。
  変更：`pipeline.py`（変更前は `_backup\20261112-citations\`）。
  止まった生成 `runs\20261112-135819-b27bc5` は、作成済みの資料を引き継いだまま残り3回で仕上げを続けられるよう再設定（元のファイルは `_before_resume2\`）。
- 2026-11-12：作業手順書の書き方ルールを見直し（v2）。動作を手順にするかを「省くと失敗するか・前提になるか・同時に行うか・話者が強調したか」で判断する、
  音声で説明された実用情報も使う、作業に寄与しない動き（試しにかぶせて外す等）は手順にしない、続く条件は1回だけ書く、手順番号は通し番号1種類、
  出典spanは工程ブロックごとに1つ、「※メーカーの手順による」は補った手順に1回だけ、など。
  変更：`editor.txt`・`prompts\editor.txt`・`document_design.py`（変更前は `_backup\20261112-procedure-rules-v2\`）。
  ※指示が変わったため、止まったAPI生成 `runs\20261112-135819-b27bc5` は途中再開できなくなる（新しく生成し直す）。
- 2026-11-12：作業手順書のルールを3段階に整理（v3）。「■1 必ず守ること」（少数）、「■2 目指す姿と良いやり方」（判断の基準と理由）、
  「■3 よくある失敗と直し方」（実際に出た失敗の悪い例→良い例）。内容整理の段階にも、実演だけの動きを独立した工程にしないよう伝える。
  変更：`editor.txt`・`prompts\editor.txt`・`document_options.py`（変更前は `_backup\20261112-procedure-rules-v3\`）。
- 2026-11-12：作業手順書の見た目を調整。各手順の見出しを「大きな手順番号＋小さな段階名＋動作」（.chapter）にし、
  出典の時刻と外部資料名は本文ではなくページ下の欄にまとめて表示（手順書のときだけ）。準備に音声の実用情報を書く、持ち方・向きの基準は「作業の前に」へ、などをルールに追加。
  変更：`pipeline.py`・`web_research.py`・`editor.txt`・`prompts\editor.txt`・`document_design.py`（変更前は `_backup\20261112-step-design\`）。
- 2026-11-12：作業手順書のデザイン方針を追加（セミナー要約の見本を参考）。表紙は強調語つきの題名と主役の写真、手順の前に全体の流れ（.chevrons）、
  手順ページは同じ型で主役の写真を大きく、コツは各手順1つまで.pointで、変化は表紙・流れ・応用・まとめに集中。
  変更：`editor.txt`・`prompts\editor.txt`・`document_design.py`（変更前は `_backup\20261112-procedure-design\`）。
- 2026-11-12：作業手順書のルールの例を、テストに使った動画（AirTag・もやい結び）から架空の作業（卓上ライトの電球交換）に差し替え、
  「例は書き方の説明で、語句・数・順番・覚え方を持ち込まない」と明記。覚え方・数値は内容案の表記どおりにすること、表紙とまとめも照合の対象にすることを追加。
  資料に例だけの語句（電球・シェード等）が入り、内容案にない場合は差し戻す検査を追加。
  変更：`editor.txt`・`prompts\editor.txt`・`document_options.py`・`pipeline.py`（変更前は `_backup\20261112-neutral-examples\`）。
