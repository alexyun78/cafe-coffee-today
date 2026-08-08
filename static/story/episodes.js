/* 92스토리 — 글 목록(제목 + 작성일) 위젯
 *
 * 사용법: 스토리 페이지 hero 아래에 아래 한 줄을 넣고 이 스크립트를 로드한다.
 *   <nav id="story-episodes" data-current="<이 글의 id>"></nav>
 *   <script src="/static/story/episodes.js" defer></script>
 *
 * static/story/index.json 을 읽어 최신순으로 렌더. 한 페이지 3편 + 페이지네이션.
 * 새 화를 추가할 때 이 파일은 건드릴 필요 없다.
 */
(function () {
    var PER_PAGE = 3;

    var CSS = '' +
        '.story-index{background:var(--canvas-warm);border-bottom:1px solid var(--line-soft)}' +
        '.story-index-inner{max-width:720px;margin:0 auto;padding:30px 24px 34px}' +
        '.story-index-head{display:flex;align-items:baseline;justify-content:space-between;gap:12px;' +
        'margin-bottom:14px;font-family:var(--font-mono);font-size:.7rem;letter-spacing:.2em;color:var(--ink-soft)}' +
        '.story-index-head b{color:var(--copper);font-weight:500}' +
        '.story-index-list{list-style:none;margin:0;padding:0;border-top:1px solid var(--line)}' +
        '.story-index-list li{border-bottom:1px solid var(--line-soft)}' +
        '.story-index-list a,.story-index-list span.row{display:flex;align-items:baseline;gap:14px;' +
        'padding:13px 4px;color:var(--ink-mute);transition:color .18s,background .18s}' +
        '.story-index-list a:hover{color:var(--copper);background:rgba(201,152,106,.08)}' +
        '.story-index-ep{flex:none;width:52px;font-family:var(--font-mono);font-size:.68rem;' +
        'letter-spacing:.1em;color:var(--copper)}' +
        '.story-index-title{flex:1 1 auto;font-size:.95rem;line-height:1.45;word-break:keep-all}' +
        '.story-index-date{flex:none;font-family:var(--font-mono);font-size:.68rem;' +
        'letter-spacing:.08em;color:var(--ink-soft)}' +
        '.story-index-list li.is-current{background:var(--canvas-stone)}' +
        '.story-index-list li.is-current .story-index-title{color:var(--ink);font-weight:700}' +
        '.story-index-now{flex:none;font-family:var(--font-mono);font-size:.6rem;letter-spacing:.12em;' +
        'color:var(--copper);border:1px solid var(--caramel);border-radius:999px;padding:2px 7px}' +
        '.story-index-pager{display:flex;align-items:center;justify-content:center;gap:16px;margin-top:16px;' +
        'font-family:var(--font-mono);font-size:.7rem;letter-spacing:.14em;color:var(--ink-soft)}' +
        '.story-index-pager button{font:inherit;color:var(--copper);background:none;cursor:pointer;' +
        'border:1px solid var(--line);border-radius:6px;padding:4px 11px;transition:border-color .18s,opacity .18s}' +
        '.story-index-pager button:hover:not(:disabled){border-color:var(--caramel)}' +
        '.story-index-pager button:disabled{opacity:.32;cursor:default}' +
        '@media(max-width:600px){' +
        '.story-index-inner{padding:24px 20px 28px}' +
        '.story-index-list a,.story-index-list span.row{flex-wrap:wrap;gap:6px 10px;padding:12px 2px}' +
        '.story-index-title{flex:1 1 100%;order:3;font-size:.92rem}' +
        '.story-index-date{margin-left:auto}}';

    function esc(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }

    function ready(fn) {
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn);
        else fn();
    }

    ready(function () {
        var root = document.getElementById('story-episodes');
        if (!root) return;
        root.classList.add('story-index');

        var style = document.createElement('style');
        style.textContent = CSS;
        document.head.appendChild(style);

        fetch('/static/story/index.json')
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (j) {
                var items = (j && j.items) || [];
                if (!items.length) return;

                var current = root.getAttribute('data-current') || '';
                var pages = Math.ceil(items.length / PER_PAGE);
                // 현재 글이 속한 페이지로 시작
                var idx = items.findIndex ? items.findIndex(function (s) { return s.id === current; }) : -1;
                var page = idx >= 0 ? Math.floor(idx / PER_PAGE) : 0;

                function render() {
                    var slice = items.slice(page * PER_PAGE, page * PER_PAGE + PER_PAGE);
                    var rows = slice.map(function (s) {
                        var ep = s.no != null ? '제 ' + s.no + ' 화' : '';
                        var date = s.date ? String(s.date).replace(/-/g, '.') : '';
                        var inner = '' +
                            '<span class="story-index-ep">' + esc(ep) + '</span>' +
                            '<span class="story-index-title">' + esc(s.title || '') + '</span>' +
                            (s.id === current ? '<span class="story-index-now">읽는 중</span>' : '') +
                            '<span class="story-index-date">' + esc(date) + '</span>';
                        return s.id === current
                            ? '<li class="is-current"><span class="row">' + inner + '</span></li>'
                            : '<li><a href="/story/' + encodeURIComponent(s.id) + '">' + inner + '</a></li>';
                    }).join('');

                    root.innerHTML = '' +
                        '<div class="story-index-inner">' +
                            '<div class="story-index-head"><span>다른 이야기</span>' +
                            '<span>전체 <b>' + items.length + '</b>편</span></div>' +
                            '<ol class="story-index-list">' + rows + '</ol>' +
                            (pages > 1
                                ? '<div class="story-index-pager">' +
                                      '<button type="button" data-go="prev"' + (page === 0 ? ' disabled' : '') + '>← 이전</button>' +
                                      '<span>' + (page + 1) + ' / ' + pages + '</span>' +
                                      '<button type="button" data-go="next"' + (page === pages - 1 ? ' disabled' : '') + '>다음 →</button>' +
                                  '</div>'
                                : '') +
                        '</div>';

                    Array.prototype.forEach.call(root.querySelectorAll('[data-go]'), function (b) {
                        b.addEventListener('click', function () {
                            page += (b.getAttribute('data-go') === 'next' ? 1 : -1);
                            page = Math.max(0, Math.min(pages - 1, page));
                            render();
                        });
                    });
                }
                render();
            })
            .catch(function () { /* 목록 실패는 조용히 무시 — 본문은 그대로 */ });
    });
})();
