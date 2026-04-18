/**
 * ScoreBreakdown Component
 * Visualizes the 5D scoring system for material candidates
 */

export class ScoreBreakdown {
    constructor(container) {
        this.container = container;
        this.dimensions = {
            'spec_similarity': {
                name: 'Spec Similarity',
                weight: 0.40,
                color: 'score-spec-similarity',
                description: 'Semantic similarity of material properties and applications'
            },
            'compliance': {
                name: 'Compliance',
                weight: 0.25,
                color: 'score-compliance',
                description: 'Certification and regulatory compliance match'
            },
            'price_delta': {
                name: 'Price Delta',
                weight: 0.15,
                color: 'score-price-delta',
                description: 'Price difference from original material'
            },
            'lead_time': {
                name: 'Lead Time',
                weight: 0.10,
                color: 'score-lead-time',
                description: 'Delivery time comparison'
            },
            'quality_signals': {
                name: 'Quality Signals',
                weight: 0.10,
                color: 'score-quality-signals',
                description: 'Supplier quality and reliability indicators'
            }
        };
    }

    /**
     * Render the score breakdown for a candidate
     * @param {Object} candidate - ScoredCandidate object
     * @param {boolean} showWeights - Whether to show dimension weights
     */
    render(candidate, showWeights = false) {
        const { scores, composite_score, confidences } = candidate;

        this.container.innerHTML = `
            <div class="score-breakdown">
                <h5>5D Score Breakdown</h5>
                <div class="score-chart">
                    ${Object.entries(this.dimensions).map(([key, dim]) =>
                        this.renderScoreItem(key, scores[key] || 0, dim, confidences[key] || 0.5)
                    ).join('')}
                </div>
                <div class="composite-score">
                    <div class="score-number">${(composite_score * 100).toFixed(1)}%</div>
                    <div>Composite Score</div>
                    ${this.renderConfidenceIndicator(candidate.overall_confidence)}
                </div>
                ${showWeights ? this.renderWeightsInfo() : ''}
            </div>
        `;

        // Animate score bars
        this.animateScoreBars();
    }

    /**
     * Render a single score dimension item
     */
    renderScoreItem(key, score, dimension, confidence) {
        const percentage = (score * 100).toFixed(1);
        const weightedScore = (score * dimension.weight * 100).toFixed(1);

        return `
            <div class="score-item ${dimension.color}" data-dimension="${key}">
                <div class="score-label" title="${dimension.description}">
                    ${dimension.name}
                    <span class="weight-indicator">(${dimension.weight * 100}%)</span>
                </div>
                <div class="score-bar-container">
                    <div class="score-bar" style="width: 0%" data-score="${percentage}%"></div>
                </div>
                <div class="score-value">
                    <div class="raw-score">${percentage}%</div>
                    <div class="weighted-score">(${weightedScore}%)</div>
                    ${this.renderMiniConfidence(confidence)}
                </div>
            </div>
        `;
    }

    /**
     * Render confidence indicator
     */
    renderConfidenceIndicator(confidence) {
        const confidenceLevel = this.getConfidenceLevel(confidence);
        return `
            <div class="confidence-indicator ${confidenceLevel.class}">
                <span class="confidence-label">Confidence: ${confidenceLevel.label}</span>
                <div class="confidence-bar">
                    <div class="confidence-fill" style="width: ${confidence * 100}%"></div>
                </div>
            </div>
        `;
    }

    /**
     * Render mini confidence indicator for individual dimensions
     */
    renderMiniConfidence(confidence) {
        const level = this.getConfidenceLevel(confidence);
        return `<span class="mini-confidence ${level.class}" title="Confidence: ${level.label}">${level.symbol}</span>`;
    }

    /**
     * Get confidence level information
     */
    getConfidenceLevel(confidence) {
        if (confidence >= 0.8) return { class: 'high', label: 'High', symbol: '●' };
        if (confidence >= 0.6) return { class: 'medium', label: 'Medium', symbol: '○' };
        return { class: 'low', label: 'Low', symbol: '◦' };
    }

    /**
     * Render weights information
     */
    renderWeightsInfo() {
        return `
            <div class="weights-info">
                <h6>Scoring Weights</h6>
                <div class="weights-grid">
                    ${Object.entries(this.dimensions).map(([key, dim]) => `
                        <div class="weight-item">
                            <span class="weight-name">${dim.name}</span>
                            <span class="weight-value">${dim.weight * 100}%</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    /**
     * Animate score bars on render
     */
    animateScoreBars() {
        // Use setTimeout to ensure DOM is updated
        setTimeout(() => {
            const scoreBars = this.container.querySelectorAll('.score-bar');
            scoreBars.forEach((bar, index) => {
                // Stagger animations
                setTimeout(() => {
                    const targetWidth = bar.getAttribute('data-score').replace('%', '');
                    bar.style.width = `${targetWidth}%`;
                }, index * 100);
            });
        }, 50);
    }

    /**
     * Update weights (for demo purposes)
     */
    updateWeights(newWeights) {
        Object.keys(this.dimensions).forEach(key => {
            if (newWeights[key] !== undefined) {
                this.dimensions[key].weight = newWeights[key];
            }
        });
    }

    /**
     * Get current weights
     */
    getWeights() {
        const weights = {};
        Object.keys(this.dimensions).forEach(key => {
            weights[key] = this.dimensions[key].weight;
        });
        return weights;
    }
}