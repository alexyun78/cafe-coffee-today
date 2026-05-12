/* ============================================================
 * 피드백 모달 — 공유 JS (index.html, roastery.html 양쪽)
 *
 * 사용:
 *   1) <link rel="stylesheet" href="/static/feedback.css">
 *   2) <script src="/static/feedback.js" defer></script>
 *   3) 호스트 페이지에서 카드 렌더 시:
 *        window.coffeeTodayMap[coffee.id] = coffee;
 *        <button class="feedback-btn" onclick="openFeedbackModalById(${coffee.id})">💬 피드백</button>
 *   4) coffee 객체는 최소 {id, 커피, 컵노트} 만 있으면 됨.
 *
 * 서버측 검증:
 *   - 진행 중 커피만 허용 (POST /api/feedback → 403 not_serving)
 *   - IP 해시당 1시간 5건 (429 rate_limited)
 * ============================================================ */
(function () {
    'use strict';

    const FB_MAX_NOTES = 3;
    const FB_NICK_MAX = 20;
    const FB_NOTE_MAX = 30;
    const FB_COMMENT_MAX = 500;

    window.coffeeTodayMap = window.coffeeTodayMap || {};

    const state = {
        coffeeId: null,
        rating: 0,
        selectedNotes: [],   // [{label, fromDb}]
        submitting: false,
        dbNotes: [],
    };

    let mounted = false;

    function esc(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[c]));
    }

    function parseDbNotes(raw) {
        if (!raw) return [];
        return String(raw)
            .split(/[,\/\n;|]/)
            .map(s => s.trim())
            .filter((s, i, arr) => s && arr.indexOf(s) === i);
    }

    function mount() {
        if (mounted) return;
        const html = `
            <div class="fb-modal" id="fb-modal" role="dialog" aria-modal="true" aria-labelledby="fb-modal-title">
                <div class="fb-modal-content">
                    <div class="fb-modal-header">
                        <div>
                            <div class="fb-modal-title" id="fb-modal-title">💬 이 커피 어떠셨나요?</div>
                            <div class="fb-modal-subtitle" id="fb-modal-subtitle"></div>
                        </div>
                        <button class="fb-modal-close" type="button" id="fb-modal-close-btn" aria-label="닫기">&times;</button>
                    </div>

                    <div class="fb-field">
                        <label class="fb-label">별점<span class="fb-req">*</span></label>
                        <div class="fb-stars" id="fb-stars" role="radiogroup" aria-label="별점">
                            <span class="fb-star" data-rating="1" role="radio" tabindex="0">★</span>
                            <span class="fb-star" data-rating="2" role="radio" tabindex="0">★</span>
                            <span class="fb-star" data-rating="3" role="radio" tabindex="0">★</span>
                            <span class="fb-star" data-rating="4" role="radio" tabindex="0">★</span>
                            <span class="fb-star" data-rating="5" role="radio" tabindex="0">★</span>
                        </div>
                    </div>

                    <div class="fb-field">
                        <label class="fb-label" for="fb-nickname">닉네임</label>
                        <input class="fb-input" id="fb-nickname" type="text" placeholder="익명도 OK" maxlength="${FB_NICK_MAX}" autocomplete="off">
                        <div class="fb-hint">최대 ${FB_NICK_MAX}자</div>
                    </div>

                    <div class="fb-field">
                        <label class="fb-label">컵노트 <span style="font-weight:400; color:#999;">(최대 ${FB_MAX_NOTES}개)</span></label>
                        <div class="fb-tokens" id="fb-tokens"></div>
                        <div class="fb-custom-row">
                            <input class="fb-input" id="fb-custom-note" type="text" placeholder="직접 입력 후 추가" maxlength="${FB_NOTE_MAX}" autocomplete="off">
                            <button class="fb-custom-add" type="button" id="fb-custom-add-btn">+ 추가</button>
                        </div>
                        <div class="fb-selected-count" id="fb-selected-count">선택 0/${FB_MAX_NOTES}</div>
                    </div>

                    <div class="fb-field">
                        <label class="fb-label" for="fb-comment">감상평</label>
                        <textarea class="fb-textarea" id="fb-comment" placeholder="자유롭게 한 줄 남겨주세요 (선택)" maxlength="${FB_COMMENT_MAX}"></textarea>
                        <div class="fb-hint">최대 ${FB_COMMENT_MAX}자</div>
                    </div>

                    <div class="fb-actions">
                        <button class="fb-btn fb-btn-cancel" type="button" id="fb-cancel-btn">취소</button>
                        <button class="fb-btn fb-btn-submit" type="button" id="fb-submit">보내기</button>
                    </div>
                </div>
            </div>
            <div class="fb-toast" id="fb-toast"></div>
        `;
        const wrap = document.createElement('div');
        wrap.innerHTML = html;
        while (wrap.firstChild) document.body.appendChild(wrap.firstChild);

        // 이벤트 핸들러
        document.getElementById('fb-modal-close-btn').addEventListener('click', closeModal);
        document.getElementById('fb-cancel-btn').addEventListener('click', closeModal);
        document.getElementById('fb-custom-add-btn').addEventListener('click', addCustomNote);
        document.getElementById('fb-submit').addEventListener('click', submit);

        document.querySelectorAll('#fb-stars .fb-star').forEach(el => {
            const set = () => { state.rating = parseInt(el.dataset.rating, 10); renderStars(); };
            el.addEventListener('click', set);
            el.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); set(); }
            });
        });

        document.getElementById('fb-custom-note').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') { e.preventDefault(); addCustomNote(); }
        });

        document.getElementById('fb-modal').addEventListener('click', (e) => {
            if (e.target.id === 'fb-modal') closeModal();
        });

        document.addEventListener('keydown', (e) => {
            const m = document.getElementById('fb-modal');
            if (e.key === 'Escape' && m && m.classList.contains('open')) closeModal();
        });

        mounted = true;
    }

    function renderStars() {
        document.querySelectorAll('#fb-stars .fb-star').forEach((el, i) => {
            el.classList.toggle('active', i < state.rating);
            el.setAttribute('aria-checked', i + 1 === state.rating ? 'true' : 'false');
        });
    }

    function renderTokens() {
        const container = document.getElementById('fb-tokens');
        const selectedSet = new Set(state.selectedNotes.map(n => n.label));
        const slotsLeft = FB_MAX_NOTES - state.selectedNotes.length;
        const dbSet = new Set(state.dbNotes);
        const customSelected = state.selectedNotes.filter(n => !dbSet.has(n.label));
        const allLabels = [...state.dbNotes, ...customSelected.map(n => n.label)];

        container.innerHTML = allLabels.map(label => {
            const sel = selectedSet.has(label);
            const disabled = !sel && slotsLeft <= 0;
            return `<span class="fb-token${sel ? ' selected' : ''}${disabled ? ' disabled' : ''}"
                          data-label="${esc(label)}"
                          role="button" tabindex="0">${esc(label)}</span>`;
        }).join('');

        container.querySelectorAll('.fb-token').forEach(el => {
            el.addEventListener('click', () => toggleToken(el.dataset.label));
        });
    }

    function toggleToken(label) {
        const idx = state.selectedNotes.findIndex(n => n.label === label);
        if (idx >= 0) {
            state.selectedNotes.splice(idx, 1);
        } else {
            if (state.selectedNotes.length >= FB_MAX_NOTES) return;
            state.selectedNotes.push({ label, fromDb: state.dbNotes.includes(label) });
        }
        renderTokens();
        renderSelectedCount();
    }

    function addCustomNote() {
        const input = document.getElementById('fb-custom-note');
        const val = (input.value || '').trim();
        if (!val) return;
        if (state.selectedNotes.length >= FB_MAX_NOTES) {
            toast(`최대 ${FB_MAX_NOTES}개까지 선택할 수 있어요`);
            return;
        }
        if (state.selectedNotes.some(n => n.label === val)) {
            toast('이미 추가한 컵노트예요');
            return;
        }
        state.selectedNotes.push({ label: val.slice(0, FB_NOTE_MAX), fromDb: state.dbNotes.includes(val) });
        input.value = '';
        renderTokens();
        renderSelectedCount();
    }

    function renderSelectedCount() {
        document.getElementById('fb-selected-count').textContent =
            `선택 ${state.selectedNotes.length}/${FB_MAX_NOTES}`;
    }

    function toast(msg) {
        const el = document.getElementById('fb-toast');
        if (!el) return;
        el.textContent = msg;
        el.classList.add('show');
        clearTimeout(toast._t);
        toast._t = setTimeout(() => el.classList.remove('show'), 2200);
    }

    async function fetchNoteOptions(coffeeId, fallbackRaw) {
        // 서버: 현재 커피의 노트 우선 + 전체 빈도 상위, 최대 10개.
        try {
            const r = await fetch('/api/feedback/note-options?coffee_id=' + encodeURIComponent(coffeeId));
            if (r.ok) {
                const d = await r.json();
                if (d.success && Array.isArray(d.notes)) return d.notes;
            }
        } catch (e) { /* 무시 — 로컬 fallback */ }
        return parseDbNotes(fallbackRaw);
    }

    async function openModal(coffeeId, coffee) {
        mount();
        const data = coffee || (window.coffeeTodayMap || {})[coffeeId];
        if (!data) return;
        state.coffeeId = coffeeId;
        state.rating = 0;
        state.selectedNotes = [];
        state.submitting = false;
        // 일단 현재 커피 컵노트로 즉시 그려놓고, 서버 응답 오면 교체.
        state.dbNotes = parseDbNotes(data['컵노트'] || data.cupNotes || '');

        document.getElementById('fb-modal-subtitle').textContent = data['커피'] || data.name || '';
        document.getElementById('fb-nickname').value = '';
        document.getElementById('fb-comment').value = '';
        document.getElementById('fb-custom-note').value = '';
        renderStars();
        renderTokens();
        renderSelectedCount();
        document.getElementById('fb-submit').disabled = false;
        document.getElementById('fb-modal').classList.add('open');
        document.body.style.overflow = 'hidden';

        // 서버에서 인기 노트 포함한 풀 옵션 받아 갱신
        const notes = await fetchNoteOptions(coffeeId, data['컵노트'] || data.cupNotes || '');
        // 모달이 사이에 닫혔으면 무시
        if (state.coffeeId !== coffeeId) return;
        state.dbNotes = notes;
        renderTokens();
    }

    function closeModal() {
        const m = document.getElementById('fb-modal');
        if (m) m.classList.remove('open');
        document.body.style.overflow = '';
    }

    async function submit() {
        if (state.submitting) return;
        if (!state.coffeeId) return;
        if (!state.rating) { toast('별점을 선택해주세요'); return; }
        state.submitting = true;
        const btn = document.getElementById('fb-submit');
        btn.disabled = true;
        try {
            const payload = {
                coffee_id: state.coffeeId,
                rating: state.rating,
                nickname: (document.getElementById('fb-nickname').value || '').trim().slice(0, FB_NICK_MAX),
                cup_notes: state.selectedNotes.map(n => n.label).slice(0, FB_MAX_NOTES),
                comment: (document.getElementById('fb-comment').value || '').trim().slice(0, FB_COMMENT_MAX),
            };
            const res = await fetch('/api/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok || !data.success) {
                if (data.error === 'rate_limited') {
                    toast('잠깐 — 너무 자주 보내고 있어요. 잠시 후 다시 시도해주세요.');
                } else if (data.error === 'not_serving') {
                    toast(data.message || '지금 제공 중인 커피에만 피드백을 남길 수 있어요');
                } else {
                    toast('전송 실패: ' + (data.error || res.status));
                }
                btn.disabled = false;
                state.submitting = false;
                return;
            }
            toast('피드백 감사합니다 ☕');
            closeModal();
        } catch (e) {
            toast('네트워크 오류 — 잠시 후 다시 시도해주세요');
            btn.disabled = false;
            state.submitting = false;
        }
    }

    // 전역 노출
    window.openFeedbackModalById = openModal;
    window.closeFeedbackModal = closeModal;
})();
