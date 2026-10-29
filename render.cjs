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
        while (node = walker.nextNode()) {
          if (!node.textContent.trim() || node.parentElement.closest('svg')) continue;
          const style = getComputedStyle(node.parentElement);
          if (style.display === 'none') continue;
          if (parseFloat(style.fontSize) < 10) errors.push(`${idx+1}ページ: 小さすぎる文字 ${node.textContent.trim().slice(0,30)}`);
          const range = document.createRange(); range.selectNodeContents(node);
          for (const rect of range.getClientRects()) {
            if (rect.width < 1 || rect.height < 1) continue;
            textRects.push({r: rect, parent: node.parentElement});
          }
        }
        const imageRects = images.map(el => ({r: el.getBoundingClientRect(), el}));
        for (const {r} of [...textRects, ...imageRects]) {
          if (r.left < bounds.left - 2 || r.right > bounds.right + 2 || r.top < bounds.top - 4 || r.bottom > bounds.bottom + 4)
            errors.push(`${idx+1}ページ: 本文または画像が有効領域からはみ出しています (left=${Math.round(r.left-bounds.left)}, right=${Math.round(r.right-bounds.right)}, top=${Math.round(r.top-bounds.top)}, bottom=${Math.round(r.bottom-bounds.bottom)})`);
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
