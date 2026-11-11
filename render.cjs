// Offline renderer. This browser is used only for generated local artifacts.
const fs = require('fs');
const path = require('path');
const {pathToFileURL, fileURLToPath} = require('url');
const root = __dirname;
const settings = fs.existsSync(path.join(root, 'runtime.local.json'))
  ? JSON.parse(fs.readFileSync(path.join(root, 'runtime.local.json'), 'utf8').replace(/^\uFEFF/, '')) : {};
const playwright = require(settings.playwright || 'playwright');
const [input, output] = process.argv.slice(2);

async function render() {
  if (!input || !output) throw Error('HTMLと出力先が必要です');
  const out = path.resolve(output);
  const browser = await playwright.chromium.launch({headless: true,
    ...(settings.browser ? {executablePath: settings.browser} : {}),
    args: ['--disable-extensions', '--disable-background-networking']});
  try {
    const context = await browser.newContext({javaScriptEnabled: false, viewport: {width: 900, height: 1200}});
    await context.route('**/*', route => {
      const url = route.request().url();
      if (url.startsWith('data:image/')) return route.continue();
      if (url.startsWith('file:')) {
        const file = path.resolve(fileURLToPath(url));
        const relative = path.relative(out, file);
        if (relative && !relative.startsWith('..') && !path.isAbsolute(relative)) return route.continue();
      }
      return route.abort();
    });
    const page = await context.newPage();
    await page.emulateMedia({media: 'print'});
    await page.goto(pathToFileURL(path.resolve(input)).href, {waitUntil: 'load'});
    // Use a stable Latin font for the decorative numeric chapter label.
    await page.evaluate(() => { document.querySelectorAll('.section-index').forEach(el => { el.style.fontFamily = 'Arial, sans-serif'; }); });
    await page.evaluate(async () => { await document.fonts.ready; });
    const check = await page.evaluate(() => {
      const pages = Array.from(document.querySelectorAll('.page'));
      const errors = [];
      const counts = [];
      const designDiagnostics = [];
      if (!pages.length) errors.push('ページ枠がありません');
      // Never infer a colour through a background image/gradient. Critical
      // emphasis must be measurable rather than silently bypassing the check.
      const parseColor = value => {
        let m = /^rgba?\(([^)]+)\)$/.exec(value);
        if (m) { const p = m[1].split(/[\s,\/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; }
        m = /^color\(srgb\s+([^)]+)\)$/.exec(value);
        if (m) { const p = m[1].split(/[\s\/]+/).filter(Boolean).map(Number); return [p[0]*255, p[1]*255, p[2]*255, p.length > 3 ? p[3] : 1]; }
        return null;
      };
      const blend = (top, base) => [0,1,2].map(i => top[i]*top[3] + base[i]*(1-top[3]));
      const backgroundOf = el => {
        const layers = [];
        for (let e = el; e; e = e.parentElement) {
          const cs = getComputedStyle(e);
          if (cs.backgroundImage && cs.backgroundImage !== 'none') return null;
          const c = parseColor(cs.backgroundColor);
          if (c && c[3] > 0) { layers.push(c); if (c[3] >= 1) break; }
        }
        return layers.reverse().reduce((base, layer) => blend(layer, base), [255, 255, 255]);
      };
      const luminance = rgb => {
        const [r, g, b] = rgb.map(v => { v /= 255; return v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); });
        return 0.2126*r + 0.7152*g + 0.0722*b;
      };
      const contrastOf = el => {
        const bg = backgroundOf(el);
        const fg = parseColor(getComputedStyle(el).color);
        if (!bg || !fg) return null;
        let alpha = fg[3];
        for (let e = el; e && e !== document.body; e = e.parentElement) alpha *= Number(getComputedStyle(e).opacity);
        const text = blend([fg[0], fg[1], fg[2], alpha], bg);
        const [hi, lo] = [luminance(text), luminance(bg)].sort((a, b) => b - a);
        return (hi + 0.05) / (lo + 0.05);
      };
      pages.forEach((page, idx) => {
        const main = page.querySelector('.page-content');
        if (!main) {errors.push(`${idx+1}ページ: 本文枠がありません`); return;}
        const bounds = main.getBoundingClientRect();
        const images = [...main.querySelectorAll('img')];
        images.forEach(img => {
          if (!img.complete || !img.naturalWidth) errors.push(`${idx+1}ページ: 画像が読み込めません ${img.getAttribute('src')}`);
          let hidden = false;
          for (let el = img; el && el !== main.parentElement; el = el.parentElement) {
            const style = getComputedStyle(el);
            if (style.display === 'none' || style.visibility !== 'visible' || Number(style.opacity) < 0.1) hidden = true;
          }
          const box = img.getBoundingClientRect();
          if (hidden || box.width < 8 || box.height < 8)
            errors.push(`${idx+1}ページ: 根拠画像が表示されていません ${img.getAttribute('src')}`);
        });
        const walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT);
        let node;
        const textRects = [];
        const checkedContrast = new Set(), lowContrast = [];
        while (node = walker.nextNode()) {
          if (!node.textContent.trim() || node.parentElement.closest('svg')) continue;
          const style = getComputedStyle(node.parentElement);
          if (style.display === 'none') continue;
          if (parseFloat(style.fontSize) < 10) errors.push(`${idx+1}ページ: 小さすぎる文字 ${node.textContent.trim().slice(0,30)}`);
          if (!checkedContrast.has(node.parentElement)) {
            checkedContrast.add(node.parentElement);
            const ratio = contrastOf(node.parentElement);
            const critical = Boolean(node.parentElement.closest('mark'));
            const sample = node.textContent.trim().slice(0, 20);
            if (critical && ratio === null)
              errors.push(`${idx+1}ページ: 強調文字「${sample}」の背景がグラデーション・画像で配色を検査できません。単色の背景と読みやすい文字色を使ってください。`);
            if (ratio !== null) {
              const size = parseFloat(style.fontSize);
              const large = size >= 24 || (size >= 18.66 && Number(style.fontWeight) >= 700);
              const shown = Math.round(ratio * 10) / 10;
              // Clearly unreadable text blocks approval; merely low contrast is a design note.
              // Highlights use the full 3:1 / 4.5:1 target, including on dark cards.
              if (ratio < (critical ? (large ? 3 : 4.5) : (large ? 2 : 3)))
                errors.push(`${idx+1}ページ: 文字「${sample}」と背景の色が近く読めません（コントラスト比${shown}、${large ? 3 : 4.5}以上が目安）。文字色か背景色を変えてください。`);
              else if (ratio < (large ? 3 : 4.5)) lowContrast.push(sample);
            }
          }
          const range = document.createRange(); range.selectNodeContents(node);
          // A glyph box is taller than the visible ink (about 1.15em for Latin digits,
          // more for CJK), so a large number set with a tight line-height reaches a
          // few px past the area without any ink outside. Allow a quarter of the size.
          const slack = Math.max(4, parseFloat(style.fontSize) * 0.25);
          for (const rect of range.getClientRects()) {
            if (rect.width < 1 || rect.height < 1) continue;
            textRects.push({r: rect, parent: node.parentElement, slack, text: node.textContent.trim()});
          }
        }
        const imageRects = images.map(el => ({r: el.getBoundingClientRect(), el, slack: 4}));
        const label = el => el.tagName.toLowerCase() + (el.className && typeof el.className === 'string'
          ? '.' + el.className.trim().split(/\s+/).join('.') : '');
        for (const {r, parent, el, slack, text} of [...textRects, ...imageRects]) {
          const side = r.left < bounds.left - 2 ? `左に${Math.round(bounds.left-r.left)}px`
            : r.right > bounds.right + 2 ? `右に${Math.round(r.right-bounds.right)}px`
            : r.top < bounds.top - slack ? `上に${Math.round(bounds.top-r.top)}px`
            : r.bottom > bounds.bottom + slack ? `下に${Math.round(r.bottom-bounds.bottom)}px` : '';
          if (side) {
            const what = el ? `画像 ${el.getAttribute('src')}（${label(el)}）` : `文字「${text.slice(0,20)}」（${label(parent)}）`;
            errors.push(`${idx+1}ページ: ${what}が有効領域から${side}はみ出しています。余白・行の高さ・大きさを調整してください。`);
          }
        }
        for (const {r:a, parent} of textRects) for (const {r:b, el} of imageRects) {
          if (parent.contains(el)) continue;
          const w = Math.min(a.right,b.right)-Math.max(a.left,b.left);
          const h = Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top);
          if (w>3 && h>3) errors.push(`${idx+1}ページ: 文字と画像が重なっています`);
        }
        if (main.scrollHeight > main.clientHeight + 3 || main.scrollWidth > main.clientWidth + 3)
          errors.push(`${idx+1}ページ: 本文の領域を超えています`);
        const foot = page.querySelector('.page-foot');
        if (foot && foot.getBoundingClientRect().top < bounds.bottom)
          errors.push(`${idx+1}ページ: フッターと本文領域が重なっています`);
        counts.push({page: idx+1, images: images.length, characters: main.textContent.trim().length});
        if (document.body.dataset.documentDesign === 'editorial') {
          const headings = [...main.querySelectorAll('h1,h2')];
          const paragraphs = [...main.querySelectorAll('p')].filter(el => !el.closest('figcaption,.visual-note') && el.textContent.trim().length > 20);
          const sizes = paragraphs.map(el => parseFloat(getComputedStyle(el).fontSize)).sort((a,b)=>a-b);
          const bodySize = sizes.length ? sizes[Math.floor(sizes.length/2)] : 0;
          const titleSize = Math.max(0,...headings.map(el=>parseFloat(getComputedStyle(el).fontSize)));
          const bottom = Math.max(bounds.top,...textRects.map(({r})=>r.bottom),...imageRects.map(({r})=>r.bottom));
          const occupied = Math.round((bottom-bounds.top)/bounds.height*100);
          const ratio = bodySize ? Math.round(titleSize/bodySize*100)/100 : null;
          const warnings = [];
          if (ratio !== null && ratio < 1.25) warnings.push('見出しと本文の大きさが近い。実画像で主役と読み順を確認。');
          if (occupied < 40 && idx > 0) warnings.push('下部の余白が大きい。意図的な構成か、分割しすぎか確認。');
          else if (occupied < 55 && idx > 0 && idx < pages.length - 1)
            warnings.push('ページの半分近くが空いている。次の章を続けるか主役を大きくできないか確認。');
          const small = images.filter(el => el.naturalWidth > el.naturalHeight * 1.2
            && el.getBoundingClientRect().width < bounds.width * 0.45).length;
          if (lowContrast.length)
            warnings.push(`文字と背景のコントラストが低い箇所が${lowContrast.length}か所（「${lowContrast[0]}」など）。読みやすさを確認。`);
          if (small) warnings.push(`横長の画面・スライド画像${small}枚が本文幅の45%未満。文字が根拠なら読める大きさか確認。`);
          if (idx === 0 && pages.length > 2 && document.body.dataset.documentPurpose !== 'procedure'
              && !main.querySelector('.cover,.tldr,.keypoints'))
            warnings.push('1ページ目に表紙・要旨（.cover/.tldr/.keypoints）がない。全体の主張が最初に伝わるか確認。');
          const structure = [...main.children].map(el=>el.tagName.toLowerCase()+'.'+el.className).join('|');
          designDiagnostics.push({page:idx+1, heading_body_ratio:ratio, occupied_height_percent:occupied,
            structure, warnings});
        }
      });
      if (document.body.dataset.documentPurpose !== 'procedure') {
        designDiagnostics.forEach((entry,i) => {
          if (i > 1 && entry.structure === designDiagnostics[i-1].structure && entry.structure === designDiagnostics[i-2].structure)
            entry.warnings.push('同じ構造が3ページ続く。内容に必要な反復か実画像で確認。');
        });
      }
      designDiagnostics.forEach(entry=>delete entry.structure);
      return {pages: pages.length, errors: [...new Set(errors)], details: counts,
        design_diagnostics:designDiagnostics};
    });
    const dir = path.join(out, 'previews'); fs.mkdirSync(dir, {recursive:true});
    check.previews = [];
    for (let i=0; i<check.pages; i++) {
      const name = `previews/page-${String(i+1).padStart(2,'0')}.png`;
      await page.locator('.page').nth(i).screenshot({path: path.join(out, name)});
      check.previews.push(name);
    }
    // Element screenshots scroll through the document. Reload before printing so
    // Chromium does not reuse paint state that can omit repeated heading glyphs.
    await page.goto(pathToFileURL(path.resolve(input)).href, {waitUntil: 'load'});
    // Use a stable Latin font for the decorative numeric chapter label.
    await page.evaluate(() => { document.querySelectorAll('.section-index').forEach(el => { el.style.fontFamily = 'Arial, sans-serif'; }); });
    await page.evaluate(async () => { await document.fonts.ready; window.scrollTo(0, 0); });
    await page.pdf({path: path.join(out,'document.pdf'), printBackground: true, preferCSSPageSize: true,
      displayHeaderFooter: false, tagged: false});
    fs.writeFileSync(path.join(out,'layout-check.json'), JSON.stringify(check, null, 2));
    console.log(JSON.stringify({pages:check.pages, errors:check.errors}));
  } finally { await browser.close(); }
}
render().catch(error => { console.error(error.message); process.exitCode=1; });
