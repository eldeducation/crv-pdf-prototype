"""Document presets applied to the existing generation request, without extra calls."""
PURPOSES = {
    'auto': '用途は動画に合わせる。内容案のkindと映像から、作業は再現できる手順、講演は論点・根拠・事例・結論を中心に構成する。混在する動画では説明と実演を章ごとに分け、全体を無理に手順化しない。',
    'procedure': '用途は作業手順書。作業の目的、映像で確認できる準備物、順序、動かす対象、向き、終了状態、必要な注意を整理する。重要な中間操作を省略しない。',
    'seminar': '用途はセミナー要約。全体像、主要な論点、根拠、数字の条件、事例、結論を整理する。話者の主張と確認済みの事実を区別し、実演以外を無理に手順化しない。',
    'training': '用途は研修資料。動画から学べる内容、重要な説明や操作、注意点、振り返りの確認問題と回答を構成する。問題の回答は動画で確かめられる内容に限り、教育用の設問だと明示する。',
}
DESIGNS = {
    'auto': 'デザインはおまかせ。動画と用途に応じて図解・数値・文章・写真を使い分ける。単なる色替えにせず、ページの中心メッセージに合わせて配置を選ぶ。',
    'visual': 'デザインは図解多め。説明の関係は関係図、比較は左右比較、数値の大小は棒グラフ、重要な成果は数値カードを使う。写真は実画面や動作の根拠として残す。図に適さない情報を装飾目的で図解しない。',
    'editorial': 'デザインはデザイン重視。見出し・重要な数字・引用・余白にメリハリをつけ、読み順が自然な冊子に編集する。ページごとに中心メッセージを決め、内容に応じて大小・段組み・配置を変える。図解の量は別の設定に従い、装飾のために図を増やさない。',
    'plain': 'デザインはすっきり。静かな配色、明確な見出し、整った余白で構成する。大きな装飾や同内容の図表の重複を避ける。図解の量は別の設定に従い、図が多くても配色と文字の整理を保つ。再現や理解に必要な説明・画像・条件は減らさない。',
}
VISUAL_DENSITIES = {
    'auto': '図解の量はおまかせ。理解が速くなる箇所だけ図表にし、文章・写真・表と使い分ける。',
    'more': '図解の量は多め。関係図・比較・棒グラフ・数値カードが理解に役立つ箇所では優先して使う。根拠のない図や同内容の画像・表の重複は作らない。',
    'fewer': '図解の量は控えめ。文章・必要な写真・簡潔な表を中心にし、理解や作業再現に必要な図だけ残す。必要な中間場面や条件は省略しない。',
}
DETAILS = {
    'compact': '説明量は簡潔。重複や周辺情報を減らすが、再現に必要な操作、条件、重要な注意は省略しない。',
    'standard': '',
    'detailed': '説明量は詳しく。映像に根拠がある前後状態、判断の条件、具体例を丁寧に説明する。ページを埋めるための水増しや映像外の補足はしない。',
}

PRESENTATION_MODES = {
    'clean': 'すっきり：静かな配色と整った余白で整理し、装飾や重複を抑える。必要な説明・条件・写真は削らない。図解多めと併用するときも図の数より整理と読み順を優先する。',
    'diagrams': '図解多め：関係・流れ・違いの理解に役立つ箇所を優先して図解する。根拠のない数値や因果を作らず、装飾のための図や同じ情報の重複を増やさない。',
    'photos': '写真多め：元動画の実際の場面を、説明との対応を保って見やすく使う。必要な細部は大きくし、不要な類似画像や無関係な写真は増やさない。',
    'comparison': '比較で整理：動画で確認できる違い・選択肢・前後状態は、対応項目をそろえた左右比較や表で整理する。動画にない比較対象や評価は作らない。',
}


def normalize_modes(modes=()):
    if not isinstance(modes, (list, tuple)) or len(modes) > len(PRESENTATION_MODES):
        raise ValueError('仕上がりのアレンジが正しくありません。')
    if any(not isinstance(mode, str) or mode not in PRESENTATION_MODES for mode in modes):
        raise ValueError('仕上がりのアレンジが正しくありません。')
    # Stable ordering keeps retries and resumed prompts identical.
    return tuple(mode for mode in PRESENTATION_MODES if mode in modes)


def validate_notes(notes=''):
    if not isinstance(notes, str) or len(notes) > 3000:
        raise ValueError('追加の希望は3000文字以内で入力してください。')
    return notes.strip()


def validate_options(purpose, detail, language, design='auto', visual_density='auto'):
    if purpose not in PURPOSES or detail not in DETAILS or language not in {'auto', 'ja', 'en'} or design not in DESIGNS or visual_density not in VISUAL_DENSITIES:
        raise ValueError('Invalid document purpose, detail level or output language.')


def build_prompt(prompt, purpose='auto', detail='standard', language='auto', design='auto', visual_density='auto', presentation_modes=(), presentation_notes=''):
    validate_options(purpose, detail, language, design, visual_density)
    modes = normalize_modes(presentation_modes)
    notes = validate_notes(presentation_notes)
    # Old visual requests remain readable, while new UI separates style/density.
    density = 'more' if design == 'visual' and visual_density == 'auto' else visual_density
    instructions = [value for value in (PURPOSES[purpose], DETAILS[detail], DESIGNS[design], VISUAL_DENSITIES[density]) if value]
    instructions.extend(PRESENTATION_MODES[mode] for mode in modes)
    if notes:
        instructions.append('利用者からの追加の希望：' + notes)
    if language != 'auto':
        instructions.append('出力言語は' + ('英語' if language == 'en' else '日本語') + '。本文、見出し、キャプション、確認事項、編集用Markdownを統一する。')
    if instructions:
        return prompt + '\n\n【選択した資料設定】\n' + '\n'.join(instructions) + '\n不明な点を推測で埋めず、根拠不足と断定できる誤りを区別する。'
    return prompt
