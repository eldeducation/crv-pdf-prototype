# チャットモード（APIキーなしで、チャットのAIがAI役をする）

アプリがAIに送るはずの依頼をファイルに書き出し、チャットのAI（Claude・ChatGPTなど、PCのファイルを読み書きできるもの）が回答ファイルを置くと、アプリがそれを読み込んで先へ進みます。
依頼の中身・使える操作・アプリの検査はAPIで生成するときと同じで、変わるのはやり取りの経路だけです。APIモードとRender版には影響しません（「APIなし」モードのときだけ動きます）。

## 使い方
1. `4_chat_mode.bat` を起動し、ウィンドウを開いたままにする。
2. `chat-jobs\inbox\<依頼ID>.json` に依頼を置く。
   ```json
   {"source": "https://... または動画ファイルの絶対パス", "purpose": "procedure", "detail_level": "standard",
    "output_language": "ja", "external_research": true, "answerer": "回答するAIの名前・条件（検証レポート用）"}
   ```
   `purpose` は auto / procedure / seminar / training、`detail_level` は compact / standard / detailed。
   止めた生成の続きは `{"resume_folder": "<runs内のフォルダー名>"}`。
3. AIへの依頼が出ると `runs\chat-bridge.json` に `status: waiting` と依頼フォルダー（`request_dir`）が書かれる。
4. チャットのAIが `request_dir` の `request.json` と `images\` を読み、
   `{"request_id": "...", "tool_calls": [{"name": "...", "input": {...}}]}` を `request_dir\chat-response.json` に置く。
   受理されると `response.json` ができ、次の依頼が出る。形式の不備は `chat-response.rejected-N.json` と `chat-response-error.txt` に理由が出る。
5. 進み具合は `chat-jobs\status\<依頼ID>.json`。止めるときは `chat-jobs\cancel\<依頼ID>` を作る。
6. 完成すると `完成PDF\` にPDFと「_検証レポート.txt」が保存される。

## 検証レポート
同じ回答をAPIで行っていた場合の目安（AIへの依頼回数とAPIの回数上限、形式の不備、検査での差し戻しと理由、依頼ごとの入出力の分量と出力上限、API換算の費用の目安）を、`runs\<生成>\chat-report.json`・`.txt` と `完成PDF\<PDF名>_検証レポート.txt` に出します。APIは呼び出しません。費用は回答の分量だけの目安で、APIの「考える過程」の出力は含みません。

## APIのAIと条件をそろえて試すとき
チャットのAIは、APIのAIより多くの情報や道具を持っています。モデルの出来を比べるときは、回答するAIに次を守らせます。
- 過去のチャット・他の会話・メモリを参照しない。今回以外の生成フォルダー、完成PDF・成果物・作業メモを開かない。
- アプリのソースコード（`editor.txt` を含む）を読まない。判断には `request.json` と `images\` の中身だけを使う。
- 提出前に自分で紙面を描いて確かめるなど、APIのAIにはできないことをしない。
