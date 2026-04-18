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
            </div>
        `;
    }

    /**
     * Render mini score breakdown for candidate preview
     */
    renderMiniScoreBreakdown(candidate) {
        const scores = candidate.scores;
        const dimensions = ['spec_similarity', 'compliance', 'price_delta', 'lead_time', 'quality_signals'];

        return `
            <div class="mini-scores">
                ${dimensions.map(dim => {
                    const score = scores[dim] || 0;
                    const percentage = (score * 100).toFixed(0);
                    return `
                        <div class="mini-score-item" title="${dim.replace('_', ' ')}: ${percentage}%">
                            <span class="mini-score-label">${dim.split('_')[0]}</span>
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
     * Find candidate by ID (helper method)
     * Note: In a real implementation, you'd store the candidates array
     */
    findCandidateById(id) {
        // This is a placeholder - in real implementation, store candidates array
        // For now, return null and let the parent component handle it
        return null;
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