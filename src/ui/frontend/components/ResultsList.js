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

    /**
     * Display the list of top candidates
     * @param {Array} candidates - Array of ScoredCandidate objects
     */
    displayCandidates(candidates) {
        if (!candidates || candidates.length === 0) {
            this.container.innerHTML = `
                <div class="no-results">
                    <h3>No suitable candidates found</h3>
                    <p>Try adjusting your search criteria or material requirements.</p>
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

        // Add click handlers
        this.attachEventListeners();
    }

    /**
     * Render a single candidate item
     */
    renderCandidate(candidate, rank) {
        const material = candidate.kandidat;
        const compositeScore = (candidate.composite_score * 100).toFixed(1);
        const explanation = candidate.explanation || null;
        const uncertainty = candidate.uncertainty_report || null;

        return `
            <div class="candidate-item" data-candidate-id="${material.id}">
                <div class="candidate-header">
                    <div class="candidate-rank">#${rank}</div>
                    <div class="candidate-name">${material.name}</div>
                    <div class="candidate-score">${compositeScore}% match</div>
                </div>

                <div class="candidate-details">
                    <div class="candidate-metrics">
                        <div class="metric">
                            <span class="metric-label">Price:</span>
                            <span class="metric-value">${this.formatPrice(material.price)}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Lead Time:</span>
                            <span class="metric-value">${material.lead_time.days} days</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">MOQ:</span>
                            <span class="metric-value">${material.moq}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Origin:</span>
                            <span class="metric-value">${material.country_of_origin}</span>
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

                <details class="candidate-detail-panel">
                    <summary>Show Explanation & Uncertainty</summary>
                    <div class="candidate-detail-body">
                        ${this.renderExplanation(candidate)}
                        ${this.renderUncertainty(uncertainty)}
                    </div>
                </details>
            </div>
        `;
    }

    /**
     * Render mini score breakdown for candidate preview
     */
    renderMiniScoreBreakdown(candidate) {
        const scores = candidate.scores;
        const dimensions = ['spec', 'compliance', 'price', 'lead_time', 'quality'];

        return `
            <div class="mini-scores">
                ${dimensions.map(dim => {
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
        const risks = explanation ? (explanation.risks || []) : [];

        return `
            <div class="candidate-explanation">
                <h5>Explanation</h5>
                <p><strong>Summary:</strong> ${explanation?.summary || 'not available'}</p>
                <p><strong>Recommendation:</strong> ${explanation?.recommendation || 'not available'}</p>
                <p><strong>Confidence Statement:</strong> ${explanation?.confidence_statement || 'not available'}</p>
                <p><strong>Strengths:</strong> ${strengths.length ? strengths.join(' | ') : 'none'}</p>
                <p><strong>Weaknesses:</strong> ${weaknesses.length ? weaknesses.join(' | ') : 'none'}</p>
                <p><strong>Risks:</strong> ${risks.length ? risks.join(' | ') : 'none'}</p>
                <h5>Contact & Allergen Information</h5>
                <p><strong>For more information, contact sales:</strong> ${sellerEmail || 'No email for the seller'}</p>
                <p><strong>Website:</strong> ${sellerWebsite || 'No website for the seller'}</p>
                <p><strong>Selected prohibited allergens:</strong> ${prohibited.length ? prohibited.join(', ') : 'none selected'}</p>
                <p><strong>Allergen check:</strong> ${this.renderAllergenCheck(containsHits, mayContainHits, hasAllergenData)}</p>
            </div>
        `;
    }

    renderAllergenCheck(containsHits, mayContainHits, hasAllergenData) {
        if (!hasAllergenData) {
            return 'Contact seller for better information';
        }
        if (containsHits.length) {
            return `Contains prohibited allergens: ${containsHits.join(', ')}`;
        }
        if (mayContainHits.length) {
            return `May contain prohibited allergens: ${mayContainHits.join(', ')}`;
        }
        return 'No prohibited allergen matches found in available data';
    }

    renderUncertainty(uncertainty) {
        if (!uncertainty) {
            return `<p><strong>Uncertainty:</strong> not available</p>`;
        }

        const suggestions = uncertainty.verification_suggestions || [];
        return `
            <div class="candidate-uncertainty">
                <h5>Uncertainty</h5>
                <p><strong>Overall level:</strong> ${uncertainty.overall_level || '-'}</p>
                <p><strong>Overall confidence:</strong> ${uncertainty.overall_confidence ?? '-'}</p>
                <p><strong>Warning:</strong> ${uncertainty.warning_message || 'none'}</p>
                <p><strong>Verification suggestions:</strong> ${suggestions.length ? suggestions.join(' | ') : 'none'}</p>
            </div>
        `;
    }

    /**
     * Format price for display
     */
    formatPrice(priceInfo) {
        const { value, unit } = priceInfo;
        if (value >= 1000) {
            return `${(value / 1000).toFixed(1)}k ${unit}`;
        }
        return `${value} ${unit}`;
    }

    /**
     * Attach event listeners to candidate items
     */
    attachEventListeners() {
        const candidateItems = this.container.querySelectorAll('.candidate-item');
        const compareButtons = this.container.querySelectorAll('.compare-btn');

        candidateItems.forEach(item => {
            item.addEventListener('click', (e) => {
                if (!e.target.classList.contains('compare-btn')) {
                    const candidateId = item.dataset.candidateId;
                    const candidate = this.findCandidateById(candidateId);
                    if (candidate && this.onCandidateSelect) {
                        this.onCandidateSelect(candidate);
                    }
                }
            });
        });

        compareButtons.forEach(button => {
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

    /**
     * Set candidates data for lookup
     */
    setCandidates(candidates) {
        this.candidates = candidates;
    }

    /**
     * Find candidate by ID from stored candidates
     */
    findCandidateById(id) {
        return this.candidates?.find(candidate => candidate.kandidat.id === id) || null;
    }
}
