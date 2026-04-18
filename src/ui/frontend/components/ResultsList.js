/**
 * ResultsList Component
 * Displays top material candidates in a dense table-first layout.
 */

import { ScoreBreakdown } from './ScoreBreakdown.js';

export class ResultsList {
    constructor(container, onCandidateSelect) {
        this.container = container;
        this.onCandidateSelect = onCandidateSelect;
        this.scoreBreakdown = new ScoreBreakdown(document.createElement('div'));
        this.candidates = [];
    }

    displayCandidates(candidates) {
        this.candidates = Array.isArray(candidates) ? candidates : [];

        if (this.candidates.length === 0) {
            this.container.innerHTML = `
                <section class="no-results">
                    <h3>No suitable candidates found</h3>
                    <p>Adjust constraints or increase result depth.</p>
                </section>
            `;
            return;
        }

        this.container.innerHTML = `
            <section class="candidates-section">
                <div class="section-headline-row">
                    <h3>Top Material Candidates</h3>
                    <p class="section-meta">Sorted by composite score</p>
                </div>

                <div class="results-table-wrap">
                    <table class="results-table" role="table" aria-label="Top material candidates">
                        <thead>
                            <tr>
                                <th class="col-expand" aria-label="Expand"></th>
                                <th>Rank</th>
                                <th>Material</th>
                                <th>Price</th>
                                <th>Lead Time</th>
                                <th>MOQ</th>
                                <th>Origin</th>
                                <th>Match</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${this.candidates.map((candidate, index) => this.renderCandidateRows(candidate, index + 1)).join('')}
                        </tbody>
                    </table>
                </div>
            </section>
        `;

        this.attachEventListeners();
    }

    renderCandidateRows(candidate, rank) {
        const material = candidate.kandidat;
        const compositeScore = (candidate.composite_score * 100).toFixed(1);
        const safeId = String(material.id).replace(/[^a-zA-Z0-9_-]/g, '-');
        const rowId = `cand-${safeId}`;

        return `
            <tr class="candidate-row" data-candidate-id="${material.id}" data-detail-id="${rowId}">
                <td class="col-expand">
                    <button class="row-expand-btn" data-expanded="false" aria-label="Expand candidate details">▸</button>
                </td>
                <td class="mono">#${rank}</td>
                <td>
                    <div class="cell-primary">${material.name}</div>
                    <div class="cell-secondary mono">${material.id}</div>
                </td>
                <td class="mono">${this.formatPrice(material.price)}</td>
                <td class="mono">${material.lead_time.days} days</td>
                <td class="mono">${material.moq}</td>
                <td>${material.country_of_origin || 'N/A'}</td>
                <td>
                    <span class="match-pill ${this.getMatchClass(candidate.composite_score)}">${compositeScore}%</span>
                </td>
                <td>
                    <button class="btn btn-primary btn-small compare-btn" data-candidate-id="${material.id}">Compare</button>
                </td>
            </tr>
            <tr class="candidate-detail-row hidden" id="${rowId}">
                <td colspan="9">
                    <div class="candidate-detail-layout">
                        <div class="candidate-detail-block">
                            ${this.renderScoreBreakdown(candidate)}
                        </div>
                        <div class="candidate-detail-block ai-accent-panel">
                            ${this.renderExplanation(candidate)}
                            ${this.renderUncertainty(candidate.uncertainty_report || null)}
                        </div>
                    </div>
                </td>
            </tr>
        `;
    }

    renderScoreBreakdown(candidate) {
        const tempContainer = document.createElement('div');
        this.scoreBreakdown.container = tempContainer;
        this.scoreBreakdown.render(candidate, true);
        return tempContainer.innerHTML;
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

    getMatchClass(score) {
        if (score >= 0.8) return 'match-ok';
        if (score >= 0.6) return 'match-warn';
        return 'match-danger';
    }

    attachEventListeners() {
        const rows = this.container.querySelectorAll('.candidate-row');
        const compareButtons = this.container.querySelectorAll('.compare-btn');
        const expandButtons = this.container.querySelectorAll('.row-expand-btn');

        rows.forEach((row) => {
            row.addEventListener('click', (e) => {
                if (e.target.closest('button')) {
                    return;
                }
                const candidateId = row.dataset.candidateId;
                const candidate = this.findCandidateById(candidateId);
                if (candidate && this.onCandidateSelect) {
                    this.onCandidateSelect(candidate);
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

        expandButtons.forEach((button) => {
            button.addEventListener('click', (e) => {
                e.stopPropagation();
                const row = button.closest('.candidate-row');
                const detailId = row.dataset.detailId;
                const detailRow = this.container.querySelector(`#${detailId}`);
                const isExpanded = button.dataset.expanded === 'true';

                if (!detailRow) return;

                if (isExpanded) {
                    detailRow.classList.add('hidden');
                    button.dataset.expanded = 'false';
                    button.textContent = '▸';
                } else {
                    detailRow.classList.remove('hidden');
                    button.dataset.expanded = 'true';
                    button.textContent = '▾';
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
