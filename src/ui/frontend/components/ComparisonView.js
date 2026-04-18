/**
 * ComparisonView Component
 * Shows detailed comparison between original material and candidate
 */

import { ScoreBreakdown } from './ScoreBreakdown.js';

export class ComparisonView {
    constructor(container) {
        this.container = container;
        this.scoreBreakdown = new ScoreBreakdown(document.createElement('div'));
    }

    /**
     * Show comparison between original and candidate
     * @param {Object} original - Original CrawledMaterial
     * @param {Object} candidate - ScoredCandidate
     */
    showComparison(original, candidate, weights = null) {
        const candidateMaterial = candidate.kandidat;

        this.container.innerHTML = `
            <div class="comparison-section">
                <div class="comparison-header">
                    <h2>Material Comparison</h2>
                    <button class="btn btn-secondary close-comparison" onclick="this.closest('.comparison-section').classList.add('hidden')">
                        Close Comparison
                    </button>
                </div>

                <div class="comparison-container">
                    <div class="comparison-column">
                        <h3>Original Material</h3>
                        ${this.renderMaterialCard(original, 'original')}
                    </div>

                    <div class="comparison-column">
                        <h3>Candidate Material</h3>
                        ${this.renderMaterialCard(candidateMaterial, 'candidate')}
                        <div class="candidate-score-breakdown">
                            ${this.renderScoreBreakdown(candidate, weights)}
                        </div>
                    </div>
                </div>

                <div class="comparison-metrics">
                    <h3>Detailed Comparison</h3>
                    ${this.renderDetailedComparison(original, candidate)}
                </div>
            </div>
        `;

        // Scroll to comparison section
        this.container.scrollIntoView({ behavior: 'smooth' });
    }

    /**
     * Render material card for comparison
     */
    renderMaterialCard(material, type) {
        return `
            <div class="material-card comparison-${type}">
                <h4>${material.name}</h4>
                <div class="material-details">
                    <div class="detail-row">
                        <strong>ID:</strong> ${material.id}
                    </div>
                    <div class="detail-row">
                        <strong>Price:</strong> ${this.formatPrice(material.price)}
                    </div>
                    <div class="detail-row">
                        <strong>Lead Time:</strong> ${material.lead_time.days} days (${material.lead_time.type})
                    </div>
                    <div class="detail-row">
                        <strong>MOQ:</strong> ${material.moq}
                    </div>
                    <div class="detail-row">
                        <strong>Country:</strong> ${material.country_of_origin}
                    </div>
                    <div class="detail-row">
                        <strong>Incoterm:</strong> ${material.incoterm}
                    </div>
                    <div class="detail-row">
                        <strong>Certifications:</strong>
                        <div class="certifications-list">
                            ${material.certifications.length > 0
                                ? material.certifications.map(cert => `<span class="cert-tag">${cert}</span>`).join('')
                                : '<span class="no-certs">None</span>'
                            }
                        </div>
                    </div>
                </div>

                ${type === 'candidate' ? this.renderQualityInfo(material.quality) : ''}
            </div>
        `;
    }

    /**
     * Render quality information
     */
    renderQualityInfo(quality) {
        return `
            <div class="quality-info">
                <h5>Quality Indicators</h5>
                <div class="quality-metrics">
                    ${quality.supplier_rating ? `<div>Supplier Rating: ${JSON.stringify(quality.supplier_rating)}</div>` : ''}
                    ${quality.defect_rate ? `<div>Defect Rate: ${JSON.stringify(quality.defect_rate)}</div>` : ''}
                    ${quality.on_time_delivery ? `<div>On-time Delivery: ${JSON.stringify(quality.on_time_delivery)}</div>` : ''}
                    ${quality.years_in_business ? `<div>Years in Business: ${quality.years_in_business}</div>` : ''}
                    ${quality.audit_score ? `<div>Audit Score: ${JSON.stringify(quality.audit_score)}</div>` : ''}
                </div>
            </div>
        `;
    }

    /**
     * Render score breakdown for candidate
     */
    renderScoreBreakdown(candidate, weights = null) {
        const tempContainer = document.createElement('div');
        this.scoreBreakdown.container = tempContainer;
        this.scoreBreakdown.render(candidate, true, weights);
        return tempContainer.innerHTML;
    }

    /**
     * Render detailed comparison metrics
     */
    renderDetailedComparison(original, candidate) {
        const candidateMaterial = candidate.kandidat;
        const scores = candidate.scores;

        const comparisons = [
            {
                label: 'Price',
                original: original.price.value,
                candidate: candidateMaterial.price.value,
                unit: original.price.unit,
                higherIsBetter: false,
                score: scores.price
            },
            {
                label: 'Lead Time',
                original: original.lead_time.days,
                candidate: candidateMaterial.lead_time.days,
                unit: 'days',
                higherIsBetter: false,
                score: scores.lead_time
            },
            {
                label: 'MOQ',
                original: original.moq,
                candidate: candidateMaterial.moq,
                unit: 'units',
                higherIsBetter: false,
                score: null
            },
            {
                label: 'Spec Similarity',
                original: 'N/A',
                candidate: 'N/A',
                unit: '',
                higherIsBetter: true,
                score: scores.spec,
                isPercentage: true
            },
            {
                label: 'Compliance Match',
                original: original.certifications.length,
                candidate: this.calculateComplianceMatch(original.certifications, candidateMaterial.certifications),
                unit: 'certifications',
                higherIsBetter: true,
                score: scores.compliance,
                isPercentage: true
            }
        ];

        return `
            <div class="comparison-metrics-grid">
                ${comparisons.map(comp => this.renderComparisonMetric(comp)).join('')}
            </div>
        `;
    }

    /**
     * Render a single comparison metric
     */
    renderComparisonMetric(comparison) {
        const { label, original, candidate, unit, higherIsBetter, score, isPercentage } = comparison;

        let comparisonClass = 'equal';
        let indicator = '≈';

        if (typeof original === 'number' && typeof candidate === 'number') {
            if (higherIsBetter) {
                comparisonClass = candidate > original ? 'better' : candidate < original ? 'worse' : 'equal';
                indicator = candidate > original ? '↑' : candidate < original ? '↓' : '≈';
            } else {
                comparisonClass = candidate < original ? 'better' : candidate > original ? 'worse' : 'equal';
                indicator = candidate < original ? '↓' : candidate > original ? '↑' : '≈';
            }
        }

        const formatValue = (value) => {
            if (isPercentage && score !== null) {
                return `${(score * 100).toFixed(1)}%`;
            }
            if (typeof value === 'number') {
                if (value >= 1000) return `${(value / 1000).toFixed(1)}k`;
                return value.toLocaleString();
            }
            return value;
        };

        return `
            <div class="comparison-metric ${comparisonClass}">
                <div class="metric-header">
                    <span class="metric-label">${label}</span>
                    <span class="comparison-indicator">${indicator}</span>
                </div>
                <div class="metric-values">
                    <div class="original-value">${formatValue(original)} ${unit}</div>
                    <div class="candidate-value">${formatValue(candidate)} ${unit}</div>
                </div>
                ${score !== null ? `<div class="metric-score">Score: ${(score * 100).toFixed(1)}%</div>` : ''}
            </div>
        `;
    }

    /**
     * Calculate compliance match (number of matching certifications)
     */
    calculateComplianceMatch(originalCerts, candidateCerts) {
        const matches = originalCerts.filter(cert => candidateCerts.includes(cert));
        return matches.length;
    }

    /**
     * Format price for display
     */
    formatPrice(priceInfo) {
        const { value, unit } = priceInfo;
        if (value >= 1000) {
            return `${(value / 1000).toFixed(1)}k ${unit}`;
        }
        return `${value.toFixed(2)} ${unit}`;
    }
}
