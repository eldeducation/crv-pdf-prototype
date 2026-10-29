// Embedded in index.html so the existing local server can serve the updated UI.
const $=id=>document.getElementById(id);
const translations={
 '次の操作へ':'Next action',
 'この段階は、チャットで作成した回答JSONの取り込み待ちです。下の「次の操作へ」を開いてください。':'This step is waiting for a reply JSON prepared in chat. Open Next action below.',
 '実行方法':'Execution mode', 'APIで生成する':'Generate using an API',
 'APIを使わないテスト':'Test without an API',
 'APIなしのテストでは、指示・画像を取り出してチャットで回答を作り、その回答JSONを読み込んで進めます。APIキーは不要です。':'In manual mode, download the instructions and images, prepare a reply in chat, then import the reply JSON. No API key is needed.',
 'APIなしテスト：回答の取り込み':'Manual test: import a reply',
 '1. 指示・画像をまとめて保存':'1. Download instructions and images',
 '2. チャットで回答を作る':'2. Prepare the reply in chat',
 '保存したZIPを展開し、README.txtの案内に従ってください。このチャットで作った回答JSONを読み込むと、検査して次の依頼へ進みます。':'Extract the ZIP and follow README.txt. Import the reply JSON prepared in chat to run the checks and continue to the next request.',
 '3. 回答JSONを選ぶ':'3. Choose the reply JSON',
 '回答を読み込んで続ける':'Import reply and continue',
 'APIなしのテスト：回答ファイルを待っています。':'Manual test: waiting for a reply file.',
 '回答を受け取りました。通常の検査を続けています。':'Reply received. Continuing the ordinary checks.',
 '回答ファイルを選んでください。':'Choose a reply file.',
 '回答ファイルは3MB以内にしてください。':'Reply files must be no larger than 3 MB.',
 'テストを開始する':'Start manual test',
 'API呼び出しなし。このチャット側の利用量は集計対象外です。':'No API requests. Chat usage is not included in these records.',
 '動画から、伝わる資料へ。':'Turn videos into clear, visual documents.',
 '大事な内容を読み取り、写真と説明にメリハリをつけたPDFに。':'Create an illustrated PDF that gives the important details room to stand out.',
 'AI接続を確認しています':'Checking AI connection',
 'AI接続の設定':'AI connection settings',
 'APIキー':'API key',
 'OpenRouter / Anthropic APIキー':'OpenRouter / Anthropic API key',
 '接続設定を使う':'Use this API key',
 '1. 動画を選ぶ':'1. Choose a video',
 '動画ファイル':'Video file',
 'MP4・MOV・WebM・MKV。最初の試作品は30分以内・1GB以内に対応。':'MP4, MOV, WebM or MKV. Up to 30 minutes and 1 GB.',
 'MP4・MOV・WebM・MKV。最初の試作品は30分以内・90MB以内に対応。':'MP4, MOV, WebM or MKV. Up to 30 minutes and 90 MB.',
 'または、YouTube・Xの動画リンク':'Or paste a YouTube or X video link',
 'Xは公開投稿の動画に対応。ログインが必要な投稿は取り込めません。':'X supports videos in public posts. Posts requiring login cannot be imported.',
 'YouTubeまたはXの動画付き投稿リンクか、動画ファイルを指定してください。':'Use a YouTube or X video-post link, or upload a video file.',
 'Xの動画を取得できませんでした。投稿の公開状態・動画番号・取得制限を確認してください。ログインが必要な投稿には対応していません。動画ファイルのアップロードも利用できます。':'Could not import the X video. Check post visibility, the video number, and download restrictions. Login-required posts are not supported. You can also upload the video file.',
 '動画ファイルを選んだ場合は、ファイルを優先します。':'If a file is selected, it takes priority over the link.',
 '解説音声がない動画（文字起こしを省略）':'No spoken explanation (skip transcription)',
 '必要な公開情報をWeb検索で補う':'Supplement missing facts with public web sources',
 '不足する重要情報だけ検索し、外部資料の出典を残します。非公開の内容を含む動画ではオフにしてください。':'Search only for important missing facts and retain source links. Turn this off for videos containing private information.',
 '2. 仕上がりの希望':'2. Describe your document',
 '図表は理解に役立つ箇所に使い、必要な写真や条件も残します。':'Use diagrams where they help understanding, preserving essential photos and conditions.',
 'デザイン':'Design', 'おまかせ':'Automatic', 'デザイン重視':'Design emphasis', '図解の量':'Amount of diagrams', '多め':'More', '控えめ':'Fewer', '図解多め':'Visual emphasis', 'すっきり':'Clean and simple', '内容を保ってデザインを変更':'Change design, keep the content', '変更後のデザイン':'New design', 'このデザインで作り直す':'Recreate with this design',
 '資料の用途':'Document purpose', '動画に合わせる':'Adapt to the video', '作業手順書':'Procedure guide', 'セミナー要約':'Seminar summary', '研修資料':'Training material',
 '説明の詳しさ':'Level of detail', '簡潔':'Concise', '標準':'Standard', '詳しく':'Detailed',
 '簡潔を選んでも、作業に必要な操作や重要な条件は省きません。':'Even a concise guide keeps essential actions and conditions.',
 '内容の根拠を確認':'Check the source scenes',
 '各説明と元動画の時刻・画像を確認できます。照合済みの表示はAIによる確認結果です。':'Compare each explanation with source times and images. Review labels describe AI checks.',
 '出典情報を読み込んでいます':'Loading source references…',
 '出典情報はまだありません。内容の解析後に確認できます。':'Source references become available after content analysis.',
 '全体の内容確認は未完了です。以下の説明にも未確認の点が含まれる場合があります。':'Overall content verification is incomplete. Some explanations below may still need review.',
 '最終資料の内容照合が完了しています。':'The final document has passed the AI content check.',
 '動画の解析内容です。PDF本文の表現と異なる場合があります。':'These are the video-analysis notes; wording may differ from the PDF.',
 '確認が必要な点':'Review notes',
 'ブラウザで再生できない形式です。表示された出典時刻を元動画で確認してください。':'This video format cannot be played in this browser. Use the displayed source times in the original video.',
 'PDFの出力言語':'PDF language',
 'どんな資料にしますか？':'What would you like to create?',
 '作業動画には工程の説明、講演動画には要点・図解など、内容に合った構成を作ります。':'The structure follows the video: steps for practical tasks, or key points and illustrations for talks.',
 '生成の設定':'Generation settings',
 'モデル':'Model', '推論の深さ':'Reasoning effort', '高':'High', '超高':'Extra high', '最大':'Maximum',
 'モデルと設定はAPI側の名称です。チャットで得られた品質との一致は、これから検証します。':'These are API model names and settings. Quality compared with chat-based results is still being evaluated.',
 '今回の費用目安（米ドル）':'Estimated spending limit (USD)',
 '次の送信が目安を超える見込みなら停止します。料金は推定のため厳密な請求上限ではありません。最大12回のAI呼び出しまで。生成途中でも停止できます。':'Processing stops if the next request is estimated to exceed this amount. This is not a guaranteed billing cap. Up to 12 AI requests; you can stop further requests during generation.',
 'PDFを生成する':'Generate PDF',
 '一覧で全体を把握 → 必要な場面を詳しく確認 → 資料作成 → 本文と映像を照合。再作成は1回までです。途中再開では完了した段階を再利用します。費用目安は再開前からの累計です。':'Overview → inspect key scenes → create the document → check it against the video. One revision is allowed. Resuming reuses completed stages, and the spending estimate includes earlier requests.',
 '生成状況':'Generation status',
 '詳しい停止理由':'Technical details',
 '生成が途中で停止しました。':'Generation stopped before completion.',
 '停止しました。':'Stopped.',
 '停止要求を受け付けました。現在の応答を記録してから停止します。':'Stop requested. The current response will be recorded before further requests stop.',
 '動画とAI接続を設定すると生成できます。':'Choose a video and set up your API key to begin.',
 '途中から再開する':'Resume generation', '追加処理を止める':'Stop further processing',
 'ローカル検証用の試作品です。Web公開・利用者管理・ブラウザ上での編集は次の段階です。':'Local prototype. Account management and in-browser editing are not yet available.',
 '共有元のPCと共有処理が動いている間だけ利用できます。':'Available only while the host PC and sharing process are running.',
 '共有用の試作品':'Shared prototype',
 'ご自身のAPIキーを入力して利用してください。API料金はそのキーの残高から発生します。キーと生成結果はブラウザごとに分離されます。アップロードした動画は共有元のPCで処理され、抽出画像は選択したAIサービスへ送信されます。開発中のため、生成が途中停止する場合があります。':'Use your own API key; charges apply to that key. Keys and results are separated by browser session. Uploaded videos are processed on the host PC, and extracted images are sent to the selected AI service. This prototype is still in development and generation may stop before completion.',
 '操作に失敗しました':'The operation failed.',
 'キーを設定しました。未使用状態が30分続くと接続解除されます。':'API key set. It disconnects after 30 minutes without a generation request (once any active job has finished).',
 'APIキーの接続を解除':'Disconnect API key',
 '接続を解除しました。':'API key disconnected.',
 '共有元のPCへAPIキーが送られます。テスト用キーを使い、プロバイダー側で利用上限を設定してください。キーは接続解除、または生成していない状態で最終利用から30分後にサーバーの参照を解除します。':'Your API key is sent to the host PC. Use a test key and set spending limits with your provider. Disconnect it when finished; otherwise the server drops its reference after 30 minutes since its last use, once any active job has finished.',
 'Session verification failed. Reload the page.':'Session verification failed. Reload the page.',
 '最初に上の「AI接続の設定」を開いて設定してください。':'Open AI connection settings above and enter your API key first.',
 '準備しています':'Preparing…',
 '動画は1GB以内で選んでください。':'Choose a video no larger than 1 GB.',
 '動画は90MB以内で選んでください。':'Choose a video no larger than 90 MB.',
 '動画を処理用のPCへアップロードしています':'Uploading the video to the processing PC…',
 'AI接続：設定済み':'AI connection: key set',
 'AI接続：未設定':'AI connection: not configured',
 '画面との接続が切れました。起動し直してください。':'Connection lost. Reload the page or ask the host to restart sharing.',
 'PDFを保存':'Download PDF', '編集用Markdown':'Editable Markdown',
 '生成記録':'Generation record', 'API使用量':'API usage',
 'PDFを保存（要確認）':'Download PDF (review needed)',
 '確認が必要な点':'Review notes',
 '内容の確認は未完了です。完成版として使う前に指摘を確認してください。':'Content verification is incomplete. Read the review notes before using this as a finished document.',
 '完成しました':'Complete.',
 'PDF作成済み・内容の確認が必要です':'PDF created. Content review is needed.',
 '動画の画像と文字起こしを準備しています':'Preparing video frames and transcript…',
 '前回取得した動画と画像を再利用しています':'Reusing previously extracted video and images…',
 'PDFと編集用資料が完成しました':'PDF and editable document are ready.',
 'PDFを作成しました。内容の確認が必要な箇所があります':'PDF created. Some content needs review.',
 '別の確認処理で、説明と元映像を照合しています':'Checking the descriptions against the original video…',
 '完成した本文・写真の説明を元映像と照合しています':'Checking the final text and image captions against the video…',
 '受信した内容を保ったまま、提出形式だけを修正しています':'Repairing the response format while preserving its content…',
 '停止を受け付けました。実行中のAPI応答を記録した後、追加の送信を止めます。':'Stop requested. The current API response will be recorded, then further requests will stop.',
 'APIキーを入力してください。':'Enter your API key.',
 '最初にAI接続を設定してください。':'Set up your API key first.',
 '現在の生成が終わってから実行してください。':'Wait for the current generation to finish.',
 '動画を選ぶかYouTube・Xの動画リンクを入力してください。':'Choose a video or enter a YouTube or X video link.',
 '推論設定が正しくありません。':'Invalid reasoning effort setting.',
 'APIキーが認証されませんでした。':'The API key could not be authenticated.',
 '残高またはキーの利用上限が不足しています。':'Insufficient balance or API key allowance.',
 'このキー・地域・アカウントでは利用できません。':'Access is unavailable for this key, region or account.',
 '指定したモデルが利用できません。':'The selected model is unavailable.',
 '利用上限です。時間をおいて再実行してください。':'Rate limit reached. Try again later.',
 'モデル名・推論設定・入力容量を確認してください。':'Check the model name, reasoning setting and input size.',
 'API接続に失敗しました。':'The API connection failed.',
 'OpenRouterに接続できません。ネットワーク接続を確認してください。':'Cannot connect to OpenRouter. Check the network connection.',
 'AIの提出データをJSONとして読み取れませんでした。':'The AI response could not be parsed as JSON.',
 'AIのツール出力が不正です。':'The AI returned an invalid tool response.',
 'AIから内容のある応答を受信できませんでした。':'The AI returned an empty response.',
 'モデルの料金を確認できないため、課金処理を開始しません。':'Cannot verify model pricing. No paid request was started.',
 'Anthropic直接接続では入出力単価の設定が必要です。OpenRouterでは自動取得します。':'Direct Anthropic access requires the host to configure token prices. OpenRouter pricing is retrieved automatically.',
 '料金情報が不正なため停止しました。':'Stopped because the pricing information is invalid.',
 '停止しました。次のAPI呼び出しは行っていません。':'Stopped. No further API request was sent.',
 'API呼び出し回数の上限です。追加の自動実行を停止しました。':'API request limit reached. Further automatic requests have stopped.',
 '前回の料金が未確定のため、追加の課金処理を停止しました。':'The previous request cost is unconfirmed. Further paid requests have stopped.',
 '現在のAPI応答を記録して停止しました。追加のAPI呼び出しは行いません。':'The current response was recorded. No further API requests will be sent.',
 '映像と説明の食い違い、または確認できない箇所が残っています。plan-review.jsonを保存しました。':'Some descriptions conflict with the video or remain unverified. Review details were saved to plan-review.json.',
 '内容の提出を完了できませんでした。quality-events.jsonとquality-progress.jsonを確認してください。':'Content planning did not finish. Details are saved in quality-events.json and quality-progress.json.',
 '再作成の上限に達しました。生成済みPDFには確認が必要な指摘が残っています。':'Revision limit reached. The generated PDF still has items that need review.',
 'AI処理の回数上限に達しました。途中の資料を保存しました。':'AI processing limit reached. Partial results were saved.',
 '共有画面の処理に失敗しました。ページを開き直してください':'The shared session failed. Reopen the shared link.',
 '共有URLを開き直してください':'Reopen the shared link.',
 'YouTubeリンクかアップロードした動画を指定してください':'Use a YouTube link or an uploaded video.',
 '別のサイトから操作できません':'Requests from another website are not allowed.',
 'この共有枠のアップロード容量に達しました':'The upload allowance for this browser session has been reached.',
 'アップロードは90MB以内、設定は100KB以内です':'Uploads must be no larger than 90 MB; settings must be under 100 KB.',
 '費用目安は0.10～20ドルで指定してください。':'Enter an estimated spending limit between $0.10 and $20.',
 '処理に失敗しました。入力とローカルの実行環境を確認してください。':'Processing failed. Check the inputs and ask the host to check the runtime.',
};
Object.assign(translations,{
 '動画を資料に':'Video to PDF',
 '動画から、':'From video,', '伝わる資料へ。':'to visual documents.',
 '図解多め':'More diagrams',
 'デザイン重視で作成':'Thoughtfully designed by default',
 '内容に合った構成・配色・余白で、読みやすく整えます。':'Clear structure, color and spacing, tailored to the content.',
 '仕上がりのアレンジ':'Make it your own', '任意・複数選択OK':'Optional · Choose any combination',
 'そのままでも作れます。好みがあれば、組み合わせて選んでください。':'Ready to create as is. Select any combination to add your preferences.',
 '余白を生かして整理':'Organized, with room to breathe', '関係や流れを見える形に':'Show relationships and flows',
 '写真多め':'More photos', '実際の場面を見やすく':'Give real scenes more space',
 '比較で整理':'Side-by-side comparisons', '違いや選択肢を並べて理解':'Compare differences and options',
 '追加の希望（任意）':'Anything else? (optional)',
 '対象読者、色、強調したい内容など。空欄でも作成できます。':'Tell us about your audience, colors or key points. You can leave this blank.',
 '内容を保って仕上がりを変更':'Adjust the presentation, keep the content',
 '上のアレンジと追加の希望を使って、新しいPDFを作ります。':'Create a new PDF using the preferences and notes above.',
 'この設定で作り直す':'Recreate with these preferences'
});
const connectionJa='OpenRouterまたはAnthropicのAPIキーをこのPC内の画面で入力します。キーは保存せず、起動中だけ保持します。動画から抽出した画像・文字起こしは、生成時に選択したAPIサービスへ送信されます。OpenRouter利用時は同社を経由してモデル提供元に送信されます。API利用料金が発生します。';
translations[connectionJa]='Enter your OpenRouter or Anthropic API key. It stays in server memory and is not saved to disk. Extracted images and transcripts are sent to the selected API provider. OpenRouter requests pass through OpenRouter to the model provider. API charges apply.';
translations[connectionJa.replace('このPC内の画面','この画面').replace('キーは保存せず、起動中だけ保持します。','キーは共有元のPCのメモリにのみ保持し、共有プロセスの終了時に消えます。')]=translations[connectionJa];
const defaultPrompts={
 ja:'動画の内容を正確に読み取り、写真と説明を組み合わせたPDFにまとめて。重要な部分に詳しい説明を付け、写真を2、3枚横並びにするなど、読みやすく構成して。',
 en:'Turn this video into a clear, well-structured illustrated PDF. Adapt the structure to the content instead of using a repetitive list of steps. Give important information more emphasis, and arrange two or three images side by side where useful.'
};
let lang=document.documentElement.dataset.defaultLanguage||'ja';
try{lang=localStorage.getItem('video-pdf-ui-language')||lang;}catch{}
if(!['ja','en'].includes(lang))lang='ja';
let busy=false,configured=false,lastJob=null,lastStatus=null,modelLoaded=false;
let currentMessage={text:'動画とAI接続を設定すると生成できます。',error:false};
let settingMessage='';
let submitting=false,submissionStarted=0,clientError=null,stageSignature='';
const stageNames={prepare:['動画の準備','Prepare video'],analyze:['内容の整理','Analyze content'],document:['資料・PDFの作成','Create document'],verify:['元動画との照合','Check against video'],finish:['最終確認・保存','Finalize and save']};
const reasonNames={
 cancelled:['操作により停止しました','Stopped at your request'],budget:['費用目安を超える見込みのため停止しました','Stopped before exceeding the estimated spending limit'],
 billing_pending:['前回のAPI料金が未確定です','The previous API cost is unconfirmed'],call_limit:['今回のAI呼び出し回数の上限に達しました','The API request limit for this run was reached'],
 round_limit:['今回の処理回数の上限に達しました','The processing limit for this run was reached'],revision_limit:['修正回数の上限に達しました','The revision limit was reached'],token_limit:['設定されたトークン上限に達しました','The configured token limit was reached'],
 auth:['APIキーの認証・利用権限を確認してください','Check API key authentication and access'],credit:['APIの残高またはキーの利用上限が不足しています','Insufficient API balance or key allowance'],rate_limit:['APIの利用が一時的に制限されています','The API is temporarily rate limited'],
 output_limit:['AIの応答が出力上限で途切れました','The AI response reached its output limit'],response_format:['生成結果を読み取れませんでした','The generated response could not be read'],network:['APIとの接続を確認できませんでした','The API connection failed'],quality:['内容の確認が必要です','Content needs review'],
 request:['生成の受付を確認できませんでした','The generation request could not be confirmed'],error:['生成が途中で停止しました','Generation stopped before completion']
};
const actionNames={
 budget:['「今回の費用目安」を見直してから再開してください。金額は再開前からの累計です。','Review the estimated spending limit before resuming. Earlier charges remain included.'],
 billing_pending:['プロバイダー側で前回の利用状況を確認してください。料金が未確定の保存状態では、追加の課金を伴う再開を停止しています。','Check the previous request in your provider dashboard. Paid resumption is blocked while the saved cost is unconfirmed.'],
 call_limit:['同じ保存位置からは追加実行できません。作成済みPDFや確認事項があれば確認してください。','This run cannot make more requests. Check any saved PDF and review notes.'],
 round_limit:['この保存位置では処理回数が残っていません。途中の成果物を確認し、必要なら新しく生成してください。','No processing rounds remain at this saved position. Review partial results before starting a new generation.'],
 revision_limit:['作成済みPDFと確認事項を確認してください。同じ保存位置からの自動修正は終了しています。','Review the saved PDF and notes. Automatic revisions at this saved position are exhausted.'],
 token_limit:['この保存位置では設定された上限に達しています。途中の成果物を確認してください。','The saved run has reached its configured limit. Check any partial results.'],
 version_changed:['生成処理の仕様が更新されています。この保存位置は使わず、新しく生成してください。','Generation rules have changed. Start a new generation instead of reusing this saved position.'],
 video_incomplete:['動画の準備が完了していないため、動画を選び直して新しく生成してください。','Video preparation did not finish. Select the video and start a new generation.'],
 legacy:['この版の保存データは途中再開に対応していません。','This saved version does not support resuming.'],
 auth:['接続設定のキーと、モデルの利用権限を確認してください。','Check the configured key and its model access.'],
 credit:['プロバイダー側の残高・利用上限を確認してください。','Check your provider balance and key allowance.'],
 rate_limit:['時間をおいてから、保存された続きの再開を検討してください。','Wait before attempting to resume the saved run.'],
 request:['入力と接続を確認してください。受付済みの場合は、接続が戻ると生成状況が表示されます。','Check the inputs and connection. If the request was accepted, its status will appear once the connection returns.']
};
const pair=value=>value?.[lang==='en'?1:0]||'';
let referenceData=null,referenceFolder=null,referenceKey=null,referencePending=null;
const purposeHelp={
 auto:['動画に合った構成で、大切な内容と場面をまとめます。','Adapt the structure to the video and highlight important content and scenes.'],
 procedure:['準備・操作の順序・完了状態・注意点を整理します。','Organize preparation, actions in order, completion states and cautions.'],
 seminar:['要点・根拠・数字の条件・事例・結論を整理します。','Organize key points, supporting evidence, numerical conditions, examples and conclusions.'],
 training:['学ぶ内容・解説・注意点・振り返り問題と回答をまとめます。','Create learning goals, explanations, cautions and review questions with answers.']
};
const tr=(ja,en)=>lang==='en'?(en||translations[ja]||ja):ja;
function translatedStatus(text){
 if(lang==='ja')return text;
 if(translations[text])return translations[text];
 const patterns=[
  [/^PDFを作成して確認しています（(\d+)回目）$/,(_,n)=>`Creating and checking PDF (pass ${n})…`],
  [/^AIが内容と画像を確認しています（処理(\d+)）$/,(_,n)=>`Reviewing content and images (pass ${n})…`],
  [/^動画の内容と動作の前後関係を整理しています（(\d+)回目）$/,(_,n)=>`Mapping the content and sequence of actions (pass ${n})…`],
  [/^AI処理 (\d+)\/(\d+)回・確定額 \$(.+) \/ 費用目安 \$(.+)$/,(_,n,max,c,b)=>`AI request ${n}/${max} · Confirmed $${c} / Estimated limit $${b}`],
  [/^次の処理を含めると費用目安 \$(.+) を超える見込みのため停止しました。確定額 \$(.+)。$/,(_,b,c)=>`Stopped before the next request: estimated cost would exceed $${b}. Confirmed cost: $${c}.`],
  [/^OpenRouterから完全な生成結果を受信できませんでした（(.+)）。$/,(_,s)=>`OpenRouter did not return a complete result (${s}).`],
  [/^AIの返答が1回の出力上限（(.+)トークン）で途切れました。途中の出力は完成扱いにせず、使用量を保存しました。$/,(_,n)=>`The response reached the ${n}-token output limit. It is incomplete; usage was saved.`],
 ];
 for(const [pattern,fn] of patterns)if(pattern.test(text))return text.replace(pattern,fn);
 let result=text;
 for(const [ja,en] of Object.entries(translations))result=result.split(ja).join(en);
 // Preserve diagnostic details rather than hide an unexpected server error.
 if(/[ぁ-んァ-ヶ一-龠]/.test(result))return 'Server message (original diagnostic): '+result;
 return result;
}
const staticNodes=[];
const walker=document.createTreeWalker(document.querySelector('main'),NodeFilter.SHOW_TEXT);
while(walker.nextNode()){
 const node=walker.currentNode;
 if(node.parentElement.closest('script,style,textarea,#language,#outputLanguage'))continue;
 if(translations[node.textContent.trim()])staticNodes.push([node,node.textContent.trim()]);
}
const titleJa=document.title;
function message(text,error=false){currentMessage={text,error};paintMessage();}
function paintMessage(){
 $('message').textContent=translatedStatus(currentMessage.text);
 $('message').className=currentMessage.error?'error':'';
}
function renderLanguage(){
 document.documentElement.lang=lang;
 document.title=tr(titleJa);
 for(const [node,ja] of staticNodes)node.textContent=tr(ja);
 $('key').placeholder=tr('OpenRouter / Anthropic APIキー');
 $('prompt').placeholder=tr('例：新入社員向けに。重要な判断を大きく示し、青系でまとめて。','Example: For new employees. Highlight important decisions and use a blue palette.');
 $('settingStatus').textContent=translatedStatus(settingMessage);
 paintPurposeHelp();
 paintModeSummary();
 paintMessage();
 if(lastStatus)paintStatus(lastStatus);
 if(referenceData)renderReferenceCards();
 paintExecutionMode();
}
$('language').value=lang;
$('outputLanguage').value=lang;
$('language').onchange=()=>{
 lang=$('language').value;
 try{localStorage.setItem('video-pdf-ui-language',lang);}catch{}
 renderLanguage();
};
$('model').addEventListener('input',()=>modelLoaded=true);
$('purpose').onchange=paintPurposeHelp;
const modeNames={clean:['すっきり','Clean and simple'],diagrams:['図解多め','More diagrams'],photos:['写真多め','More photos'],comparison:['比較で整理','Side-by-side comparisons']};
function selectedModes(){return [...document.querySelectorAll('#presentationModes [data-mode][aria-pressed="true"]')].map(button=>button.dataset.mode);}
function arrangementPayload(){return {design:'editorial',visual_density:'auto',presentation_modes:selectedModes(),presentation_notes:$('prompt').value.trim()};}
function paintModeSummary(){
 const modes=selectedModes();
 $('modeSummary').textContent=modes.length?tr('選択中：','Selected: ')+modes.map(mode=>pair(modeNames[mode])).join(' · '):tr('おまかせ：動画の内容に合わせて構成します。','Automatic: the structure adapts to your video.');
}
for(const button of document.querySelectorAll('#presentationModes [data-mode]'))button.addEventListener('click',()=>{
 button.setAttribute('aria-pressed',String(button.getAttribute('aria-pressed')!=='true'));
 paintModeSummary();
});
function paintExecutionMode(){
 const manual=$('executionMode').value==='manual';
 $('manualHelp').hidden=!manual;
 $('apiOptions').hidden=manual;
 $('budget').disabled=manual;
 $('model').disabled=manual;$('effort').disabled=manual;
 $('generate').textContent=tr(manual?'テストを開始する':'PDFを生成する');
 if(manual&&!configured)$('settings').open=false;
}
$('executionMode').onchange=paintExecutionMode;
$('manualSubmit').onclick=async()=>{
 const file=$('manualAnswer').files[0];
 try{
  if(!file)throw Error(tr('回答ファイルを選んでください。'));
  if(file.size>3000000)throw Error(tr('回答ファイルは3MB以内にしてください。'));
  $('manualSubmit').disabled=true;
  const reply=JSON.parse((await file.text()).replace(/^\uFEFF/,''));
  await api('manual/respond',reply);
  $('manualAnswer').value='';$('manualError').textContent='';
  await refresh();
 }catch(error){$('manualError').textContent=translatedStatus(error.message);}
 finally{$('manualSubmit').disabled=false;}
};
function paintPurposeHelp(){const values=purposeHelp[$('purpose').value]||purposeHelp.auto;$('purposeHelp').textContent=values[lang==='en'?1:0];}
async function api(route,body){
 if(!lastStatus)await refresh();
 const r=await fetch(route,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':lastStatus?.csrf_token||''},body:JSON.stringify(body)});
 const d=await r.json();if(!r.ok)throw Error(d.error||'操作に失敗しました');return d;
}
$('save').onclick=async()=>{
 try{
  const d=await api('configure',{api_key:$('key').value});
  $('key').value='';$('model').value=d.model;modelLoaded=true;
  settingMessage='キーを設定しました。未使用状態が30分続くと接続解除されます。';
  $('settingStatus').textContent=translatedStatus(settingMessage);await refresh();
 }catch(e){settingMessage=e.message;$('settingStatus').textContent=translatedStatus(settingMessage);}
 finally{$('key').value='';}
};
$('disconnect').onclick=async()=>{
 try{
  await api('disconnect',{});$('key').value='';settingMessage='接続を解除しました。';
  $('settingStatus').textContent=translatedStatus(settingMessage);await refresh();
 }catch(e){settingMessage=e.message;$('settingStatus').textContent=translatedStatus(settingMessage);}
};
$('resume').onclick=async()=>{
 if(busy||submitting||!lastJob)return;
 submitting=true;submissionStarted=Date.now()/1000;clientError=null;$('resume').disabled=true;
 try{await api('start',{resume_folder:lastJob.folder,budget_usd:Number($('budget').value)});$('results').replaceChildren();submitting=false;await refresh();}
 catch(e){message(e.message,true);}
 finally{submitting=false;$('resume').disabled=false;}
};
$('stop').onclick=async()=>{try{const d=await api('stop',{});message(d.message);await refresh();}catch(e){message(e.message,true);}};
$('restyle').onclick=async()=>{
 if(busy||submitting||!lastJob||lastJob.status!=='complete')return;
 try{
  if(!lastJob.manual_mode&&!configured)throw Error(tr('最初にAI接続を設定してください。','Set up the AI connection first.'));
  submitting=true;submissionStarted=Date.now()/1000;clientError=null;$('restyle').disabled=true;
  await api('start',{restyle_from:lastJob.folder,...arrangementPayload(),budget_usd:Number($('budget').value)});
  submitting=false;await refresh();
 }catch(e){message(e.message,true);}
 finally{submitting=false;$('restyle').disabled=false;}
};
$('generate').onclick=async()=>{
 if(busy||submitting)return;
 try{
  if(!configured&&$('executionMode').value!=='manual')throw Error('最初に上の「AI接続の設定」を開いて設定してください。');
  submitting=true;submissionStarted=Date.now()/1000;clientError=null;
  busy=true;$('generate').disabled=true;$('results').replaceChildren();message('準備しています');
  paintSubmission();
  let upload_id;const file=$('file').files[0];
  // The shared page advertises and enforces a smaller upload size.
  const shared=document.documentElement.dataset.defaultLanguage==='en';
  if(file){
   if(file.size>(shared?90*1024**2:1024**3))throw Error(shared?'動画は90MB以内で選んでください。':'動画は1GB以内で選んでください。');
   message('動画を処理用のPCへアップロードしています');
   const r=await fetch('upload',{method:'POST',headers:{'X-Filename':encodeURIComponent(file.name),'X-CSRF-Token':lastStatus?.csrf_token||''},body:file});
   const d=await r.json();if(!r.ok)throw Error(d.error);upload_id=d.upload_id;
  }
  const prompt=defaultPrompts[lang];
  await api('start',{execution_mode:$('executionMode').value,upload_id,url:$('url').value,prompt,purpose:$('purpose').value,...arrangementPayload(),detail_level:$('detailLevel').value,output_language:$('outputLanguage').value,model:$('model').value,effort:$('effort').value,no_transcribe:$('silent').checked,external_research:$('externalResearch').checked,budget_usd:Number($('budget').value)});
  submitting=false;
  await refresh();
 }catch(e){submitting=false;busy=false;clientError={message:e.message,folder:lastJob?.folder};$('generate').disabled=false;message(e.message,true);paintProgress({status:'failed',message:e.message,report:{},progress:{available:true,current:'prepare',stages:Object.keys(stageNames).map(id=>({id,state:id==='prepare'?'stopped':'pending'})),completed_count:0,total_stages:5,stop_code:'request',resume:{available:false,reason:'request'}}});}
};
function paintStatus(d){
 $('restylePanel').hidden=true;
 $('presentationSummary').textContent='';
 configured=d.configured;
 if(d.job?.manual_mode&&d.job?.status==='running')$('executionMode').value='manual';
 const waiting=d.job?.status==='running'&&d.job?.manual_mode?d.job.manual_request:null;
 $('manualPanel').hidden=!waiting;
 $('manualJump').hidden=!waiting;
 $('executionMode').disabled=d.job?.status==='running'||submitting;
 if(waiting){
  const id=waiting.request_id;
  if($('manualPacket').dataset.request!==id){$('manualAnswer').value='';$('manualError').textContent='';}
  $('manualPacket').dataset.request=id;
  $('manualPacket').href='manual/request/'+id+'.zip';
  $('manualSequence').textContent=(lang==='en'?'Request ':'依頼 ')+waiting.sequence+' / '+pair(stageNames[waiting.phase]);
 }
 $('disconnect').disabled=!configured||d.job?.status==='running'||submitting;
 $('save').disabled=d.job?.status==='running'||submitting;
 if(!modelLoaded&&d.provider==='openrouter'){$('model').value='anthropic/claude-opus-5.5';modelLoaded=true;}
 $('connection').textContent=configured?tr('AI接続：設定済み')+' ('+(d.provider==='openrouter'?'OpenRouter':'Anthropic')+')':tr('AI接続：未設定');
 if(!configured&&$('executionMode').value!=='manual')$('settings').open=true;
 paintExecutionMode();
 if(submitting){paintSubmission();return;}
 const j=d.job;lastJob=j;
 if(!j){$('referencePanel').hidden=true;referenceData=null;referenceKey=null;referenceFolder=null;if(clientError)message(clientError.message,true);return;}
 if(clientError&&(j.status==='running'||j.folder!==clientError.folder))clientError=null;
 if(j.references_available)loadReferences(j);
 else{$('referencePanel').hidden=true;referenceData=null;referenceKey=null;referenceFolder=null;}
 $('resume').className=((j.status==='failed'||j.status==='needs_review')&&(j.progress?j.progress.resume.available:j.report?.quality_pipeline==='quality-first-v3'))?'secondary':'secondary hidden';
 $('usage').textContent=j.usage?(lang==='en'
  ?`API ${j.usage.call_count}/${j.usage.max_calls} calls / Confirmed $${j.usage.known_cost_usd.toFixed(3)} / Estimated limit $${j.usage.budget_usd.toFixed(2)}${j.usage.cost_complete?'':' (some costs unconfirmed)'}`
  :`API ${j.usage.call_count}/${j.usage.max_calls}回 / 確定額 $${j.usage.known_cost_usd.toFixed(3)} / 費用目安 $${j.usage.budget_usd.toFixed(2)}${j.usage.cost_complete?'':'（未確定分あり）'}`):'';
 if(j.manual_mode)$('usage').textContent=tr('API呼び出しなし。このチャット側の利用量は集計対象外です。');
 busy=j.status==='running';
 $('stop').className=busy?'secondary':'secondary hidden';$('generate').disabled=busy;
 $('stop').disabled=!!j.progress?.stop_requested;
 $('bar').className=busy&&!waiting?'progress busy':'progress';
 const elapsed=Math.max(0,Math.round((Date.now()/1000-j.started)/60));
 currentMessage={text:j.progress?.stop_requested?'停止要求を受け付けました。現在の応答を記録してから停止します。':j.status==='failed'?(j.progress?.stop_code==='cancelled'?'停止しました。':'生成が途中で停止しました。'):j.message,error:j.status==='failed'&&j.progress?.stop_code!=='cancelled'};paintMessage();
 if(waiting)message('この段階は、チャットで作成した回答JSONの取り込み待ちです。下の「次の操作へ」を開いてください。');
 if(busy&&!waiting)$('message').textContent+=lang==='en'?` / ${elapsed} min elapsed`:` / 約${elapsed}分経過`;
 paintProgress(j);
 if(clientError)message(clientError.message,true);
 $('results').replaceChildren();
 if(j.status!=='complete'&&j.status!=='needs_review')return;
 const presentation=j.report.presentation;
 if(presentation){
  const names={procedure:['作業手順書','Procedure guide'],seminar:['セミナー要約','Seminar summary'],training:['研修資料','Training material'],mixed:['解説と実演を組み合わせ','Explanation and demonstration'],visual:['図解多め','Visual emphasis'],editorial:['デザイン重視','Design emphasis'],plain:['すっきり','Clean and simple']};
  $('presentationSummary').textContent=tr('構成：','Structure: ')+pair(names[presentation.purpose])+' / '+tr('デザイン：','Design: ')+pair(names[presentation.design])+(presentation.requested_design==='auto'?tr('（おまかせ）',' (automatic)'):'');
  if(presentation.presentation_modes?.length)$('presentationSummary').textContent+=' / '+presentation.presentation_modes.map(mode=>pair(modeNames[mode])).filter(Boolean).join(' · ');
 }
 $('restylePanel').hidden=j.status!=='complete'||!j.report.content_verified;
 $('restyleHelp').textContent=tr('動画・画像・内容案を再利用して、新しいPDFを作ります。元のPDFは残ります。','Reuse the video, images and content plan to create a new PDF. The original PDF is preserved.')+' '+(j.manual_mode?tr('APIなしのテストは、チャットでの回答作成が必要です。','Manual mode requires chat responses.'):tr('AIによる再編集と確認にはAPI料金がかかります。','AI editing and review incur API charges.'));
 const files=[['document.pdf',j.status==='needs_review'?'PDFを保存（要確認）':'PDFを保存'],['document.md','編集用Markdown'],['run.json','生成記録']];
 if(!j.manual_mode&&['focused-evidence-v2','quality-first-v3'].includes(j.report.quality_pipeline))files.push(['usage.json','API使用量']);
 if(j.status==='needs_review')files.push(['review-notes.txt','確認が必要な点']);
 for(const [file,label] of files){
  const a=document.createElement('a');a.href='files/'+encodeURIComponent(j.folder)+'/'+file;
  a.textContent=tr(label);a.className='download'+(file.endsWith('.pdf')?'':' outline');a.download=file;$('results').appendChild(a);
 }
 const p=document.createElement('p');p.className='small';
 const minutes=Math.round(j.report.seconds/60*10)/10;
 p.textContent=(j.status==='needs_review'?tr('内容の確認は未完了です。完成版として使う前に指摘を確認してください。')+' ':'')
  +(lang==='en'?`Generation: ${minutes} min / Layout passes: ${j.report.revisions}. See the generation record and your API dashboard for costs.`:`生成時間 ${minutes}分 / 紙面作成 ${j.report.revisions}回 / 費用は生成記録とAPI管理画面で確認`);
 if(j.manual_mode)p.textContent=(lang==='en'?`Manual test: ${minutes} min / Layout passes: ${j.report.revisions}. `:`APIなしのテスト ${minutes}分 / 紙面作成 ${j.report.revisions}回。 `)+tr('API呼び出しなし。このチャット側の利用量は集計対象外です。');
 $('results').appendChild(p);
}
function paintSubmission(){
 $('generate').disabled=true;$('stop').className='secondary hidden';$('resume').className='secondary hidden';$('bar').className='progress busy';
 const progress={available:true,current:'prepare',stages:Object.keys(stageNames).map(id=>({id,state:id==='prepare'?'running':'pending'})),completed_count:0,total_stages:5,updated_at:submissionStarted,resume:{available:false}};
 paintProgress({status:'running',progress});
}
function paintProgress(job){
 const progress=job.progress;
 const stopped=job.status==='failed'||job.status==='needs_review';
 const stages=progress?.stages?.map(stage=>job.manual_request&&job.status==='running'&&stage.state==='running'?{...stage,state:'waiting'}:stopped&&stage.state==='running'?{...stage,state:'stopped'}:stage);
 const signature=JSON.stringify([lang,progress?.available,stages]);
 if(signature!==stageSignature){
  stageSignature=signature;$('stageList').replaceChildren();
  if(progress?.available)for(const [index,stage] of stages.entries()){
   const item=document.createElement('li');item.className='stage '+stage.state;
   const title=document.createElement('strong');title.textContent=(index+1)+'. '+pair(stageNames[stage.id]);
   const state=document.createElement('span');
   state.textContent=pair({complete:['完了','Done'],running:['実行中','In progress'],waiting:['回答待ち','Waiting for reply'],stopped:['停止位置','Stopped here'],pending:['待機中','Pending']}[stage.state]);
   item.append(title,state);$('stageList').appendChild(item);
  }
 }
 $('stageSummary').textContent=progress?.available?(lang==='en'?`${progress.completed_count}/${progress.total_stages} stages complete`:`${progress.total_stages}工程中 ${progress.completed_count}工程が完了`):(job.status==='running'?tr('この生成の工程記録を待っています。','Waiting for the stage record.'):tr('この生成には工程記録がありません。','This generation has no stage record.'));
 const updated=Number(progress?.updated_at);
 let meta=updated&&Number.isFinite(updated)?tr('最終更新：','Last update: ')+new Intl.DateTimeFormat(lang==='en'?'en-US':'ja-JP',{hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date(updated*1000)):'';
 if(progress?.api_wait_started_at&&job.status==='running'){
  const seconds=Math.max(0,Math.floor(Date.now()/1000-progress.api_wait_started_at));
  meta+=(meta?' / ':'')+(lang==='en'?`Waiting for the AI response: ${Math.floor(seconds/60)}m ${seconds%60}s`:`AIの応答待ち：${Math.floor(seconds/60)}分${seconds%60}秒経過`);
 }
 $('lastUpdate').textContent=meta;
 $('stopNotice').hidden=!stopped;
 if(!stopped)return;
 const reason=progress?.stop_code||'error';
 $('stopTitle').textContent=pair(reasonNames[reason]||reasonNames.error);
 const resume=progress?.resume||{};
 const action=pair(actionNames[resume.reason]||actionNames[reason]);
 const saved=resume.available?(resume.saved_checkpoint
  ?tr('保存済みの内容を使い、','Use saved content and resume from ')+pair(stageNames[resume.from_stage])+(lang==='ja'?'から再開できます。':' (local PDF rendering may be repeated).')
  :tr('再開時に保存状態を確認します。再利用できない工程は再処理されます。','Saved data will be checked on resume. Stages that cannot be reused will be processed again.')):'';
 $('stopAction').textContent=[action,saved].filter(Boolean).join(' ');
 $('resume').textContent=resume.available&&resume.saved_checkpoint?tr('続きを再開：','Resume: ')+pair(stageNames[resume.from_stage]):tr('途中から再開する');
 $('stopDetails').textContent=job.report?.review_note||job.report?.error||job.message||'';
}
function timeLabel(value){const seconds=Math.max(0,Math.floor(Number(value)||0));return String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0');}
function sourceButton(unit){
 const label=timeLabel(unit.start)+'–'+timeLabel(unit.end);
 if(unit.video_url&&/^https:\/\/www\.youtube\.com\/watch\?v=[A-Za-z0-9_-]{11}&t=\d+s$/.test(unit.video_url)){
  const link=document.createElement('a');link.href=unit.video_url;link.target='_blank';link.rel='noopener noreferrer';link.className='source-link';
  link.textContent=tr('元動画を開く','Open source video')+' '+label;return link;
 }
 const button=document.createElement('button');button.type='button';button.className='secondary';
 button.textContent=tr('動画のこの場面へ','Go to this scene')+' '+label;
 button.disabled=!referenceData.local_video_available;
 button.onclick=()=>{
  const player=$('sourcePlayer');player.hidden=false;
  const path='files/'+encodeURIComponent(referenceFolder)+'/source-video';
  const seek=()=>{player.currentTime=Math.max(0,unit.start);player.play().catch(()=>{});};
  if(player.dataset.source!==path){
   player.dataset.source=path;player.src=path;player.addEventListener('loadedmetadata',seek,{once:true});player.load();
  }else if(player.readyState>=1)seek();else player.addEventListener('loadedmetadata',seek,{once:true});
  player.scrollIntoView({behavior:'smooth',block:'center'});
 };
 return button;
}
function renderReferenceCards(){
 if(!referenceData)return;
 $('referenceSummary').textContent=tr(referenceData.document_verified?'最終資料の内容照合が完了しています。':'全体の内容確認は未完了です。以下の説明にも未確認の点が含まれる場合があります。');
 $('referenceSummary').className=referenceData.document_verified?'small':'review-warning';
 const gaps=$('referenceGaps');gaps.replaceChildren();
 if(referenceData.coverage_gaps?.length){
  const heading=document.createElement('strong');heading.textContent=tr('確認が必要な点');gaps.appendChild(heading);
  const list=document.createElement('ul');for(const text of referenceData.coverage_gaps){const li=document.createElement('li');li.textContent=text;list.appendChild(li);}gaps.appendChild(list);
 }
 const container=$('referenceList');container.replaceChildren();
 for(const unit of referenceData.units||[]){
  const card=document.createElement('article');card.className='reference-card';
  const heading=document.createElement('h3');heading.textContent=unit.title;card.appendChild(heading);
  const explanation=document.createElement('p');explanation.textContent=unit.explanation;card.appendChild(explanation);
  for(const fact of unit.external_facts||[]){
   const box=document.createElement('div');box.className='callout';
   const title=document.createElement('strong');title.textContent=lang==='en'?'External information':'外部資料による補足';box.appendChild(title);
   const statement=document.createElement('p');statement.textContent=fact.statement;box.appendChild(statement);
   const meta=document.createElement('p');meta.className='small';
   const checked=fact.status==='supported'&&fact.review?.verdict==='supported'&&fact.review.identity_matches===true&&fact.review.quote_supports_statement===true&&fact.review.source_reliable===true&&fact.review.video_consistency!=='conflict';
   meta.textContent=(lang==='en'?(checked?'Source correspondence checked':'Unresolved / needs review'):(checked?'外部資料との対応を確認':'未確定・要確認'))+' / '+(fact.basis==='corroborated'?(lang==='en'?'Also checked in video':'映像でも確認'):(lang==='en'?'Supplemented from external source':'外部資料で補完'));box.appendChild(meta);
   try{const url=new URL(fact.url);if(url.protocol==='https:'&&!url.username&&!url.password){const link=document.createElement('a');link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';link.textContent=fact.title;box.appendChild(link);}}catch{}
   card.appendChild(box);
  }
  const labels={supported:unit.review_kind==='document'?['映像との照合済み','Checked against the video']:['内容案のみ照合済み','Analysis checked; final text not yet checked'],uncertain:['映像だけでは判断できません','Unclear from the video'],revise:['説明の修正が必要','Description needs correction'],unverified:['未確認','Not yet checked']};
  const state=labels[unit.verdict]||labels.unverified;
  const badge=document.createElement('span');badge.className=unit.verdict==='supported'?'pill':'review-warning';badge.textContent=state[lang==='en'?1:0];card.appendChild(badge);
  if(unit.finding){const note=document.createElement('p');note.className='small';note.textContent=unit.finding;card.appendChild(note);}
  card.appendChild(sourceButton(unit));
  for(const pageNumber of unit.pages||[]){
   const page=document.createElement('a');page.className='pdf-page-link';page.href='files/'+encodeURIComponent(referenceFolder)+'/document.pdf#page='+Number(pageNumber);page.target='_blank';page.rel='noopener noreferrer';page.textContent='PDF p.'+pageNumber;card.appendChild(page);
  }
  const images=document.createElement('div');images.className='reference-images';
  for(const frame of unit.frames||[]){
   if(!/^assets\/[A-Za-z0-9_.-]+\.(jpg|jpeg|png)$/.test(frame.file))continue;
   const figure=document.createElement('figure'),image=document.createElement('img'),caption=document.createElement('figcaption');
   image.src='files/'+encodeURIComponent(referenceFolder)+'/'+frame.file;image.loading='lazy';image.alt=unit.title+' '+timeLabel(frame.seconds);
   caption.textContent=timeLabel(frame.seconds);figure.append(image,caption);images.appendChild(figure);
  }
  card.appendChild(images);container.appendChild(card);
 }
}
async function loadReferences(job){
 const key=job.folder+':'+job.status;
 if(referenceKey===key||referencePending===key)return;
 referencePending=key;$('referencePanel').hidden=false;
 if(referenceFolder!==job.folder){
  referenceData=null;$('referenceList').replaceChildren();$('referenceSummary').textContent=tr('出典情報を読み込んでいます');
  const player=$('sourcePlayer');player.pause();player.removeAttribute('src');delete player.dataset.source;player.hidden=true;
 }
 try{
  const response=await fetch('files/'+encodeURIComponent(job.folder)+'/source-index.json');
  if(!response.ok)throw Error('Source reference request failed.');
  const data=await response.json();
  if(lastJob?.folder!==job.folder)return;
  referenceData=data;referenceFolder=job.folder;referenceKey=key;renderReferenceCards();
 }catch(e){$('referenceSummary').textContent=tr('出典情報はまだありません。内容の解析後に確認できます。');}
 finally{if(referencePending===key)referencePending=null;}
}
$('sourcePlayer').onerror=()=>{$('referenceSummary').textContent=tr('ブラウザで再生できない形式です。表示された出典時刻を元動画で確認してください。');};
async function refresh(){
 try{
  const r=await fetch('status');const d=await r.json();if(!r.ok)throw Error(d.error);
  lastStatus=d;paintStatus(d);
 }catch(e){message('画面との接続が切れました。起動し直してください。',true);}
}
renderLanguage();refresh();setInterval(refresh,2500);
