/**
 * ScoreBreakdown Component
 * Visualizes the 5D scoring system for material candidates
 */

export class ScoreBreakdown {
    constructor(container) {
        this.container = container;
        this.dimensions = {
            spec: {
                name: 'Spec Similarity',
                weight: 0.40,
                color: 'score-spec-similarity',
                description: 'Semantic similarity of material properties and applications'
            },
            compliance: {
                name: 'Compliance',
                weight: 0.25,
                color: 'score-compliance',
                description: 'Certification and regulatory compliance match'
            },
            price: {
                name: 'Price Delta',
                weight: 0.15,
                color: 'score-price-delta',
                description: 'Price difference from original material'
            },
            lead_time: {
                name: 'Lead Time',
                weight: 0.10,
                color: 'score-lead-time',
                description: 'Delivery time comparison'
            },
            quality: {
                name: 'Quality Signals',
                weight: 0.10,
                color: 'score-quality-signals',
                description: 'Supplier quality and reliability indicators'
            }
        };
    }

    render(candidate, showWeights = false, weights = null) {
        const { scores, composite_score, confidences = {} } = candidate;

        if (weights) {
            this.updateWeights(weights);
        }

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
                    <div class="score-caption">Composite Score</div>
                    ${this.renderConfidenceIndicator(candidate.overall_confidence)}
                </div>
                ${showWeights ? this.renderWeightsInfo() : ''}
            </div>
        `;

        this.animateScoreBars();
    }

    renderScoreItem(key, score, dimension, confidence) {
        const percentage = (score * 100).toFixed(1);
        const weightedScore = (score * dimension.weight * 100).toFixed(1);

        return `
            <div class="score-item ${dimension.color}" data-dimension="${key}">
                <div class="score-label" title="${dimension.description}">
                    <span>${dimension.name}</span>
                    <span class="weight-indicator">${Math.round(dimension.weight * 100)}%</span>
                </div>
                <div class="score-bar-container">
                    <div class="score-bar" style="width: 0%" data-score="${percentage}%"></div>
                </div>
                <div class="score-value">
                    <div class="raw-score">${percentage}%</div>
                    <div class="weighted-score">Weighted ${weightedScore}%</div>
                    ${this.renderMiniConfidence(confidence)}
                </div>
            </div>
        `;
    }

    renderConfidenceIndicator(confidence = 0) {
        const safeConfidence = Number.isFinite(confidence) ? confidence : 0;
        const confidenceLevel = this.getConfidenceLevel(safeConfidence);
        return `
            <div class="confidence-indicator ${confidenceLevel.class}">
                <span class="confidence-label">Confidence: ${confidenceLevel.label}</span>
                <div class="confidence-bar">
                    <div class="confidence-fill" style="width: ${safeConfidence * 100}%"></div>
                </div>
            </div>
        `;
    }

    renderMiniConfidence(confidence) {
        const level = this.getConfidenceLevel(confidence);
        return `<span class="mini-confidence ${level.class}" title="Confidence: ${level.label}">${level.symbol}</span>`;
    }

    getConfidenceLevel(confidence = 0) {
        if (confidence >= 0.8) return { class: 'high', label: 'High', symbol: '●' };
        if (confidence >= 0.6) return { class: 'medium', label: 'Medium', symbol: '○' };
        return { class: 'low', label: 'Low', symbol: '◦' };
    }

    renderWeightsInfo() {
        return `
            <div class="weights-info">
                <h6>Scoring Weights</h6>
                <div class="weights-grid">
                    ${Object.entries(this.dimensions).map(([, dim]) => `
                        <div class="weight-item">
                            <span class="weight-name">${dim.name}</span>
                            <span class="weight-value">${Math.round(dim.weight * 100)}%</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    animateScoreBars() {
        setTimeout(() => {
            const scoreBars = this.container.querySelectorAll('.score-bar');
            scoreBars.forEach((bar, index) => {
                setTimeout(() => {
                    const targetWidth = bar.getAttribute('data-score').replace('%', '');
                    bar.style.width = `${targetWidth}%`;
                }, index * 70);
            });
        }, 30);
    }

    updateWeights(newWeights) {
        Object.keys(this.dimensions).forEach((key) => {
            if (newWeights[key] !== undefined) {
                this.dimensions[key].weight = newWeights[key];
            }
        });
    }

    getWeights() {
        const weights = {};
        Object.keys(this.dimensions).forEach((key) => {
            weights[key] = this.dimensions[key].weight;
        });
        return weights;
    }
}
