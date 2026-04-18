/**
 * ResultsList Component
 * Displays the list of top material candidates
 */

import { ScoreBreakdown } from './ScoreBreakdown.js';

export class ResultsList {
    constructor(container, onCandidateSelect) {
        this.container = container;
        this.onCandidateSelect = onCandidateSelect;
        this.scoreBreakdown = new ScoreBreakdown(document.createElement('div'));
    }

    displayCandidates(candidates) {
        if (!candidates || candidates.length === 0) {
            this.container.innerHTML = `
                <div class="no-results">
                    <h3>No suitable candidates found</h3>
                    <p>Try adjusting K.O. filters or scoring priorities.</p>
                </div>
            `;
            return;
        }

        this.container.innerHTML = `
            <div class="candidates-section">
                <h3>Top Material Candidates</h3>
                <div class="candidates-list">
                    ${candidates.map((candidate, index) => this.renderCandidate(candidate, index + 1)).join('')}
                </div>
            </div>
        `;

        this.attachEventListeners();
    }

    renderCandidate(candidate, rank) {
        const material = candidate.kandidat;
        const compositeScore = (candidate.composite_score * 100).toFixed(1);
        const uncertainty = candidate.uncertainty_report || null;

        return `
            <article class="candidate-item" data-candidate-id="${material.id}">
                <div class="candidate-header">
                    <div class="candidate-rank">#${rank}</div>
                    <div class="candidate-name-wrap">
                        <h4 class="candidate-name">${material.name}</h4>
                        <p class="candidate-raw-id">Raw ID: ${material.id}</p>
                    </div>
                    <div class="candidate-score">${compositeScore}% match</div>
                </div>

                <div class="candidate-details">
                    <div class="candidate-metrics">
                        <div class="metric">
                            <span class="metric-label">Price</span>
                            <span class="metric-value">${this.formatPrice(material.price)}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Lead Time</span>
                            <span class="metric-value">${material.lead_time.days} days</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">MOQ</span>
                            <span class="metric-value">${material.moq}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Origin</span>
                            <span class="metric-value">${material.country_of_origin || 'N/A'}</span>
                        </div>
                    </div>

                    <div class="candidate-score-breakdown">
                        ${this.renderMiniScoreBreakdown(candidate)}
                    </div>
                </div>

                <div class="candidate-actions">
                    <button class="btn btn-primary compare-btn" data-candidate-id="${material.id}">
                        Compare Details
                    </button>
                </div>

                <details class="candidate-detail-panel ai-accent-panel">
                    <summary>View Structured Explanation</summary>
                    <div class="candidate-detail-body">
                        ${this.renderExplanation(candidate)}
                        ${this.renderUncertainty(uncertainty)}
                    </div>
                </details>
            </article>
        `;
    }

    renderMiniScoreBreakdown(candidate) {
        const scores = candidate.scores;
        const dimensions = ['spec', 'compliance', 'price', 'lead_time', 'quality'];

        return `
            <div class="mini-scores">
                ${dimensions.map((dim) => {
                    const score = scores[dim] || 0;
                    const percentage = (score * 100).toFixed(0);
                    return `
                        <div class="mini-score-item" title="${dim.replace('_', ' ')}: ${percentage}%">
                            <span class="mini-score-label">${dim}</span>
                            <div class="mini-score-bar">
                                <div class="mini-score-fill" style="width: ${percentage}%"></div>
                            </div>
                            <span class="mini-score-value">${percentage}%</span>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    }

    renderExplanation(candidate) {
        const explanation = candidate?.explanation || null;
        const material = candidate?.kandidat || {};
        const allergenRisk = candidate?.details?.allergen_risk || {};

        const sellerEmail = String(material.seller_email || '').trim();
        const sellerWebsite = String(material.seller_website || material.source_url || '').trim();
        const prohibited = Array.isArray(allergenRisk.prohibited_allergens)
            ? allergenRisk.prohibited_allergens
            : [];
        const containsHits = Array.isArray(allergenRisk.contains_hits) ? allergenRisk.contains_hits : [];
        const mayContainHits = Array.isArray(allergenRisk.may_contain_hits) ? allergenRisk.may_contain_hits : [];
        const hasAllergenData = Boolean(allergenRisk.has_allergen_data);

        const strengths = explanation ? (explanation.strengths || []).map((s) => s.text).slice(0, 3) : [];
        const weaknesses = explanation ? (explanation.weaknesses || []).map((w) => w.text).slice(0, 3) : [];
        const risks = explanation
            ? (explanation.risks || []).map((r) => (typeof r === 'string' ? r : r?.text)).filter(Boolean)
            : [];
        const allergenState = this.getAllergenState(containsHits, mayContainHits, hasAllergenData);

        return `
            <div class="candidate-detail-grid">
                <section class="detail-card detail-card-highlight">
                    <h5>AI Summary</h5>
                    <p>${explanation?.summary || 'Not available'}</p>
                    <div class="detail-meta-row">
                        <span class="detail-chip">Recommendation: ${explanation?.recommendation || 'Not available'}</span>
                        <span class="detail-chip">Confidence: ${explanation?.confidence_statement || 'Not available'}</span>
                    </div>
                </section>

                ${this.renderListCard('Strengths', strengths, 'No major strengths highlighted')}
                ${this.renderListCard('Weaknesses', weaknesses, 'No major weaknesses highlighted')}
                ${this.renderListCard('Risks', risks, 'No major risks identified')}

                <section class="detail-card">
                    <h5>Contact</h5>
                    <div class="detail-kv"><span>Sales Email</span><span>${sellerEmail || 'Not available'}</span></div>
                    <div class="detail-kv"><span>Website</span><span>${sellerWebsite || 'Not available'}</span></div>
                </section>

                <section class="detail-card">
                    <h5>Allergen Check</h5>
                    <p><span class="status-pill ${allergenState.className}">${allergenState.label}</span></p>
                    <p>${allergenState.text}</p>
                    <div class="detail-kv">
                        <span>Selected Prohibited Allergens</span>
                        <span>${prohibited.length ? prohibited.join(', ') : 'None selected'}</span>
                    </div>
                </section>
            </div>
        `;
    }

    getAllergenState(containsHits, mayContainHits, hasAllergenData) {
        if (!hasAllergenData) {
            return {
                className: 'status-warning',
                label: 'Limited Data',
                text: 'Contact seller for additional allergen information.'
            };
        }
        if (containsHits.length) {
            return {
                className: 'status-danger',
                label: 'Contains Prohibited',
                text: `Contains prohibited allergens: ${containsHits.join(', ')}`
            };
        }
        if (mayContainHits.length) {
            return {
                className: 'status-warning',
                label: 'Potential Match',
                text: `May contain prohibited allergens: ${mayContainHits.join(', ')}`
            };
        }
        return {
            className: 'status-ok',
            label: 'No Match Found',
            text: 'No prohibited allergen matches found in available data.'
        };
    }

    renderUncertainty(uncertainty) {
        if (!uncertainty) {
            return `
                <section class="detail-card">
                    <h5>Uncertainty</h5>
                    <p>Not available</p>
                </section>
            `;
        }

        const suggestions = uncertainty.verification_suggestions || [];
        return `
            <section class="detail-card">
                <h5>Uncertainty</h5>
                <div class="detail-kv"><span>Overall Level</span><span>${uncertainty.overall_level || 'Not available'}</span></div>
                <div class="detail-kv"><span>Overall Confidence</span><span>${uncertainty.overall_confidence ?? 'Not available'}</span></div>
                <div class="detail-kv"><span>Warning</span><span>${uncertainty.warning_message || 'None'}</span></div>
                ${this.renderSimpleList(suggestions, 'No verification suggestions')}
            </section>
        `;
    }

    renderListCard(title, items, emptyText) {
        return `
            <section class="detail-card">
                <h5>${title}</h5>
                ${this.renderSimpleList(items, emptyText)}
            </section>
        `;
    }

    renderSimpleList(items, emptyText) {
        if (!items || !items.length) {
            return `<p class="detail-empty">${emptyText}</p>`;
        }
        return `
            <ul class="detail-list">
                ${items.map((item) => `<li>${item}</li>`).join('')}
            </ul>
        `;
    }

    formatPrice(priceInfo) {
        const { value, unit } = priceInfo;
        if (value >= 1000) {
            return `${(value / 1000).toFixed(1)}k ${unit}`;
        }
        return `${value} ${unit}`;
    }

    attachEventListeners() {
        const candidateItems = this.container.querySelectorAll('.candidate-item');
        const compareButtons = this.container.querySelectorAll('.compare-btn');

        candidateItems.forEach((item) => {
            item.addEventListener('click', (e) => {
                if (e.target.closest('.candidate-detail-panel')) {
                    return;
                }
                if (!e.target.classList.contains('compare-btn')) {
                    const candidateId = item.dataset.candidateId;
                    const candidate = this.findCandidateById(candidateId);
                    if (candidate && this.onCandidateSelect) {
                        this.onCandidateSelect(candidate);
                    }
                }
            });
        });

        compareButtons.forEach((button) => {
            button.addEventListener('click', (e) => {
                e.stopPropagation();
                const candidateId = button.dataset.candidateId;
                const candidate = this.findCandidateById(candidateId);
                if (candidate && this.onCandidateSelect) {
                    this.onCandidateSelect(candidate);
                }
            });
        });
    }

    setCandidates(candidates) {
        this.candidates = candidates;
    }

    findCandidateById(id) {
        return this.candidates?.find((candidate) => candidate.kandidat.id === id) || null;
    }
}
