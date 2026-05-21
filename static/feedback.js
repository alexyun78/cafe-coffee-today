/* ============================================================
 * 피드백 모달 — 공유 JS (index.html, roastery.html 양쪽)
 *
 * 단순한 3단계 평가: 😞 싫어요 / 😐 중간 / 😍 좋아요
 *   - 버튼 한 번 누르면 즉시 제출 후 닫힘
 *   - rating 매핑: 싫어요=1, 중간=3, 좋아요=5 (서버 1-5 스키마 호환)
 *
 * 사용:
 *   1) <link rel="stylesheet" href="/static/feedback.css">
 *   2) <script src="/static/feedback.js" defer></script>
 *   3) 호스트 페이지에서 카드 렌더 시:
 *        window.coffeeTodayMap[coffee.id] = coffee;
 *        <button class="feedback-btn" onclick="openFeedbackModalById(${coffee.id})">💬 피드백</button>
 *   4) coffee 객체는 최소 {id, 커피} 만 있으면 됨.
 *
 * 서버측 검증:
 *   - 진행 중 OR 오늘 제공된 완료(=품절) 만 허용 (POST /api/feedback → 403 not_serving)
 *   - IP 해시당 1시간 5건 (429 rate_limited)
 * ============================================================ */
(function () {
    'use strict';

    window.coffeeTodayMap = window.coffeeTodayMap || {};

    const CHOICES = [
        { rating: 5, emoji: '😍', label: '좋아요', cls: 'fb-choice-good' },
        { rating: 3, emoji: '😐', label: '중간',   cls: 'fb-choice-mid' },
        { rating: 1, emoji: '😞', label: '싫어요', cls: 'fb-choice-bad' },
    ];

    const state = {
        coffeeId: null,
        submitting: false,
    };

    let mounted = false;

    function esc(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[c]));
    }

    function mount() {
        if (mounted) return;
        const choicesHtml = CHOICES.map(c =>
            `<button type="button" class="fb-choice ${c.cls}" data-rating="${c.rating}">
                <span class="fb-choice-emoji">${c.emoji}</span>
                <span class="fb-choice-label">${c.label}</span>
            </button>`
        ).join('');

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

                    <div class="fb-choices" id="fb-choices" role="group" aria-label="3단계 평가">
                        ${choicesHtml}
                    </div>
                </div>
            </div>
            <div class="fb-toast" id="fb-toast"></div>
        `;
        const wrap = document.createElement('div');
        wrap.innerHTML = html;
        while (wrap.firstChild) document.body.appendChild(wrap.firstChild);

        document.getElementById('fb-modal-close-btn').addEventListener('click', closeModal);

        document.querySelectorAll('#fb-choices .fb-choice').forEach(el => {
            el.addEventListener('click', () => {
                const r = parseInt(el.dataset.rating, 10);
                if (!Number.isFinite(r)) return;
                submit(r);
            });
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

    function toast(msg) {
        const el = document.getElementById('fb-toast');
        if (!el) return;
        el.textContent = msg;
        el.classList.add('show');
        clearTimeout(toast._t);
        toast._t = setTimeout(() => el.classList.remove('show'), 2200);
    }

    function setChoicesDisabled(disabled) {
        document.querySelectorAll('#fb-choices .fb-choice').forEach(el => {
            el.disabled = !!disabled;
        });
    }

    function openModal(coffeeId, coffee) {
        mount();
        const data = coffee || (window.coffeeTodayMap || {})[coffeeId];
        if (!data) return;
        state.coffeeId = coffeeId;
        state.submitting = false;
        document.getElementById('fb-modal-subtitle').textContent = data['커피'] || data.name || '';
        setChoicesDisabled(false);
        document.getElementById('fb-modal').classList.add('open');
        document.body.style.overflow = 'hidden';
    }

    function closeModal() {
        const m = document.getElementById('fb-modal');
        if (m) m.classList.remove('open');
        document.body.style.overflow = '';
    }

    async function submit(rating) {
        if (state.submitting) return;
        if (!state.coffeeId) return;
        state.submitting = true;
        setChoicesDisabled(true);
        try {
            const res = await fetch('/api/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    coffee_id: state.coffeeId,
                    rating: rating,
                    cup_notes: [],
                    nickname: '',
                    comment: '',
                }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok || !data.success) {
                if (data.error === 'rate_limited') {
                    toast('잠깐 — 너무 자주 보내고 있어요. 잠시 후 다시 시도해주세요.');
                } else if (data.error === 'not_serving') {
                    toast(data.message || '오늘 제공된 커피에만 피드백을 남길 수 있어요');
                } else {
                    toast('전송 실패: ' + (data.error || res.status));
                }
                setChoicesDisabled(false);
                state.submitting = false;
                return;
            }
            toast('피드백 감사합니다 ☕');
            closeModal();
        } catch (e) {
            toast('네트워크 오류 — 잠시 후 다시 시도해주세요');
            setChoicesDisabled(false);
            state.submitting = false;
        }
    }

    // 전역 노출
    window.openFeedbackModalById = openModal;
    window.closeFeedbackModal = closeModal;
})();
