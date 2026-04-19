/**
 * CandidateCard — improved score dimension bars
 *
 * Drop-in replacement for the mini-scores section rendering.
 * Key changes:
 *  - Each dimension is a card tile (not just a bar + label)
 *  - 100% scores → green "perfect" class with ✓
 *  - ≥80%  scores → "good" class  (accent purple)
 *  - <60%  scores → "weak" class  (amber warning)
 *  - Percentage shown as large number inside the tile
 */

/**
 * Returns the score tier class name for a 0–1 value.
 * @param {number} val  — raw score 0..1
 * @returns {'perfect'|'good'|'weak'|''}
 */
export function scoreTier(val) {
    if (val >= 0.999) return 'perfect';
    if (val >= 0.80) return 'good';
    if (val < 0.60) return 'weak';
    return '';
}

/**
 * Renders the mini-scores bar section (5 dimension tiles).
 *
 * @param {Object} scores  — e.g. { spec: 0.86, compliance: 1.0, price: 1.0, lead_time: 0.44, quality: 0.90 }
 * @param {Object} weights — e.g. { spec: 0.40, compliance: 0.25, price: 0.15, lead_time: 0.10, quality: 0.10 }
 * @returns {string}  HTML string for the .mini-scores container
 */
export function renderMiniScores(scores, weights) {
    const dimensions = [
        { key: 'spec', label: 'Spec' },
        { key: 'compliance', label: 'Compliance' },
        { key: 'price', label: 'Price' },
        { key: 'lead_time', label: 'Lead Time' },
        { key: 'quality', label: 'Quality' },
    ];

    const tiles = dimensions.map(({ key, label }) => {
        const raw = scores?.[key] ?? 0;
        const pct = Math.round(raw * 100);
        const fill = Math.max(0, Math.min(100, pct));
        const tier = scoreTier(raw);
        const wPct = weights?.[key] != null ? Math.round(weights[key] * 100) : null;

        return `
            <div class="mini-score-item${tier ? ' ' + tier : ''}">
                <span class="mini-score-label">${label}${wPct != null ? `<span style="opacity:.5;font-weight:400;margin-left:3px;">×${wPct}%</span>` : ''}</span>
                <div class="mini-score-bar">
                    <div class="mini-score-fill" style="width:${fill}%"></div>
                </div>
                <div class="mini-score-value">${pct}%</div>
            </div>`;
    }).join('');

    return `<div class="mini-scores">${tiles}</div>`;
}

/* ─── Usage example inside your existing CandidateCard / ResultsList ─────────
 *
 * Import at the top of CandidateCard.js:
 *   import { renderMiniScores } from './CandidateCard_improved.js';
 *
 * Replace the existing mini-scores HTML block with:
 *
 *   const scoresHtml = renderMiniScores(
 *       candidate.scores,          // { spec, compliance, price, lead_time, quality }
 *       activeWeights              // pass current weights from App
 *   );
 *
 * Then inject scoresHtml into the card's innerHTML where the .mini-scores div was.
 * ─────────────────────────────────────────────────────────────────────────── */