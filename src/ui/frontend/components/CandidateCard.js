/**
 * CandidateCard Component
 * Displays detailed information for a single material candidate
 */

import { ScoreBreakdown } from './ScoreBreakdown.js';

export class CandidateCard {
    constructor(container) {
        this.container = container;
        this.scoreBreakdown = new ScoreBreakdown(document.createElement('div'));
        this.candidateId = null;
    }

    render(candidate, original = null) {
        const material = candidate.kandidat;
        const compositeScore = (candidate.composite_score * 100).toFixed(1);
        this.candidateId = material.id;

        this.container.innerHTML = `
            <article class="candidate-card">
                <header class="card-header">
                    <div class="candidate-title">
                        <h3>${material.name}</h3>
                        <div class="candidate-id">ID: <span class="raw-code">${material.id}</span></div>
                    </div>
                    <div class="composite-score-display">
                        <div class="score-circle" style="background: ${this.getScoreColor(candidate.composite_score)}">
                            <span class="score-value">${compositeScore}%</span>
                            <span class="score-label">Match</span>
                        </div>
                    </div>
                </header>

                <div class="card-content">
                    <div class="material-overview">
                        ${this.renderMaterialOverview(material)}
                    </div>

                    <div class="scoring-section">
                        <h4>Scoring Analysis</h4>
                        ${this.renderScoreBreakdown(candidate)}
                    </div>

                    ${original ? this.renderComparison(original, candidate) : ''}
                    <div class="material-details">${this.renderDetailedProperties(material)}</div>
                    ${this.renderCertifications(material)}
                    ${this.renderQualitySignals(material)}
                </div>

                <footer class="card-actions">
                    <button class="btn btn-primary select-candidate" data-candidate-id="${material.id}">Select This Material</button>
                    <button class="btn btn-secondary view-details" data-candidate-id="${material.id}">View Full Details</button>
                </footer>
            </article>
        `;

        this.attachEventListeners();
    }

    renderMaterialOverview(material) {
        return `
            <div class="overview-grid">
                <div class="overview-item">
                    <span class="overview-label">Price</span>
                    <span class="overview-value">${this.formatPrice(material.price)}</span>
                </div>
                <div class="overview-item">
                    <span class="overview-label">Lead Time</span>
                    <span class="overview-value">${material.lead_time.days} days</span>
                </div>
                <div class="overview-item">
                    <span class="overview-label">MOQ</span>
                    <span class="overview-value">${material.moq}</span>
                </div>
                <div class="overview-item">
                    <span class="overview-label">Origin</span>
                    <span class="overview-value">${material.country_of_origin || 'N/A'}</span>
                </div>
            </div>
        `;
    }

    renderScoreBreakdown(candidate) {
        const tempContainer = document.createElement('div');
        this.scoreBreakdown.container = tempContainer;
        this.scoreBreakdown.render(candidate, true);
        return tempContainer.innerHTML;
    }

    renderComparison(original, candidate) {
        const material = candidate.kandidat;

        return `
            <section class="comparison-section">
                <h4>Comparison with Original</h4>
                <div class="comparison-grid">
                    ${this.renderComparisonItem('Price', original.price.value, material.price.value, original.price.unit, false)}
                    ${this.renderComparisonItem('Lead Time', original.lead_time.days, material.lead_time.days, 'days', false)}
                    ${this.renderComparisonItem('MOQ', original.moq, material.moq, 'units', false)}
                </div>
            </section>
        `;
    }

    renderComparisonItem(label, originalValue, candidateValue, unit, higherIsBetter) {
        let comparisonClass = 'neutral';
        let indicator = '→';

        if (higherIsBetter) {
            comparisonClass = candidateValue > originalValue ? 'better' : candidateValue < originalValue ? 'worse' : 'same';
            indicator = candidateValue > originalValue ? '↗' : candidateValue < originalValue ? '↘' : '→';
        } else {
            comparisonClass = candidateValue < originalValue ? 'better' : candidateValue > originalValue ? 'worse' : 'same';
            indicator = candidateValue < originalValue ? '↘' : candidateValue > originalValue ? '↗' : '→';
        }

        return `
            <div class="comparison-item ${comparisonClass}">
                <span class="comparison-label">${label}</span>
                <span class="comparison-values">${this.formatValue(originalValue)} → ${this.formatValue(candidateValue)} ${unit}</span>
                <span class="comparison-indicator">${indicator}</span>
            </div>
        `;
    }

    renderDetailedProperties(material) {
        const properties = Object.entries(material.properties || {});

        if (properties.length === 0) {
            return '<p class="no-properties">No detailed properties available</p>';
        }

        return `
            <div class="properties-section">
                <h4>Material Properties</h4>
                <div class="properties-grid">
                    ${properties.map(([key, prop]) => `
                        <div class="property-item">
                            <span class="property-name">${key}</span>
                            <span class="property-value">${prop.value} ${prop.unit}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    renderCertifications(material) {
        if (!material.certifications || material.certifications.length === 0) {
            return `
                <section class="certifications-section">
                    <h4>Certifications</h4>
                    <p class="no-certifications">No certifications listed</p>
                </section>
            `;
        }

        return `
            <section class="certifications-section">
                <h4>Certifications</h4>
                <div class="certifications-list">
                    ${material.certifications.map((cert) => `<span class="certification-tag">${cert}</span>`).join('')}
                </div>
            </section>
        `;
    }

    renderQualitySignals(material) {
        const quality = material.quality || {};

        return `
            <section class="quality-section ai-accent-panel">
                <h4>Quality Indicators</h4>
                <div class="quality-grid">
                    ${quality.supplier_rating ? `<div class="quality-item"><span>Supplier Rating:</span> <span>${JSON.stringify(quality.supplier_rating)}</span></div>` : ''}
                    ${quality.defect_rate ? `<div class="quality-item"><span>Defect Rate:</span> <span>${JSON.stringify(quality.defect_rate)}</span></div>` : ''}
                    ${quality.on_time_delivery ? `<div class="quality-item"><span>On-time Delivery:</span> <span>${JSON.stringify(quality.on_time_delivery)}</span></div>` : ''}
                    ${quality.years_in_business ? `<div class="quality-item"><span>Years in Business:</span> <span>${quality.years_in_business}</span></div>` : ''}
                    ${quality.audit_score ? `<div class="quality-item"><span>Audit Score:</span> <span>${JSON.stringify(quality.audit_score)}</span></div>` : ''}
                </div>
            </section>
        `;
    }

    getScoreColor(score) {
        if (score >= 0.8) return 'linear-gradient(135deg, #2f6b4a, #4f8b67)';
        if (score >= 0.6) return 'linear-gradient(135deg, #8a6c20, #a5852e)';
        if (score >= 0.4) return 'linear-gradient(135deg, #8a3a32, #a34c42)';
        return 'linear-gradient(135deg, #5e2521, #7a302a)';
    }

    formatValue(value) {
        if (typeof value === 'number') {
            if (value >= 1000) return `${(value / 1000).toFixed(1)}k`;
            return value.toLocaleString();
        }
        return value;
    }

    formatPrice(priceInfo) {
        const { value, unit } = priceInfo;
        if (value >= 1000) {
            return `${(value / 1000).toFixed(1)}k ${unit}`;
        }
        return `${value.toFixed(2)} ${unit}`;
    }

    attachEventListeners() {
        const selectBtn = this.container.querySelector('.select-candidate');
        const detailsBtn = this.container.querySelector('.view-details');

        if (selectBtn) {
            selectBtn.addEventListener('click', () => {
                this.handleSelect();
            });
        }

        if (detailsBtn) {
            detailsBtn.addEventListener('click', () => {
                this.handleViewDetails();
            });
        }
    }

    handleSelect() {
        const event = new CustomEvent('candidateSelected', {
            detail: { candidateId: this.candidateId }
        });
        this.container.dispatchEvent(event);
    }

    handleViewDetails() {
        const details = this.container.querySelector('.material-details');
        if (details) {
            details.classList.toggle('expanded');
        }
    }
}
