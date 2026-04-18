/**
 * WeightSliders Component
 * Interactive sliders for adjusting scoring weights (demo feature)
 */

export class WeightSliders {
    constructor(container, onWeightsChange) {
        this.container = container;
        this.onWeightsChange = onWeightsChange;
        this.weights = {
            spec_similarity: 0.40,
            compliance: 0.25,
            price_delta: 0.15,
            lead_time: 0.10,
            quality_signals: 0.10
        };

        this.dimensionLabels = {
            spec_similarity: 'Spec Similarity',
            compliance: 'Compliance',
            price_delta: 'Price Delta',
            lead_time: 'Lead Time',
            quality_signals: 'Quality Signals'
        };

        this.render();
        this.attachEventListeners();
    }

    /**
     * Render the weight sliders interface
     */
    render() {
        this.container.innerHTML = `
            <div class="weight-panel">
                <div class="weight-panel-header">
                    <h4>Adjust Weights</h4>
                </div>
                <p class="weight-help">Drag the sliders to increase or decrease the importance of each scoring dimension.</p>
                <div class="weight-sliders">
                    ${Object.entries(this.weights).map(([key, weight]) =>
                        this.renderWeightSlider(key, weight)
                    ).join('')}
                </div>
                <div class="weight-presets">
                    <button class="btn btn-secondary preset-btn" data-preset="default">Default</button>
                    <button class="btn btn-secondary preset-btn" data-preset="cost">Cost-Focused</button>
                    <button class="btn btn-secondary preset-btn" data-preset="availability">Time-Sensitive</button>
                </div>
                <div class="weight-actions">
                    <button class="btn btn-secondary reset-weights">Reset to Default</button>
                    <button class="btn btn-primary apply-weights">Recalculate</button>
                </div>
                <div class="weight-total">
                    <span>Total: <span class="total-value">${this.getTotalWeight()}%</span></span>
                </div>
            </div>
        `;

        this.updateTotalDisplay();
    }

    /**
     * Render a single weight slider
     */
    renderWeightSlider(key, weight) {
        const percentage = (weight * 100).toFixed(1);
        const label = this.dimensionLabels[key];

        return `
            <div class="weight-slider" data-dimension="${key}">
                <div class="weight-label">
                    <span class="dimension-name">${label}</span>
                    <span class="weight-value">${percentage}%</span>
                </div>
                <input
                    type="range"
                    class="weight-input"
                    min="0"
                    max="1"
                    step="0.01"
                    value="${weight}"
                    data-dimension="${key}"
                >
                <div class="weight-scale">
                    <span>0%</span>
                    <span>25%</span>
                    <span>50%</span>
                    <span>75%</span>
                    <span>100%</span>
                </div>
            </div>
        `;
    }

    /**
     * Attach event listeners to sliders and buttons
     */
    attachEventListeners() {
        // Slider change events
        const sliders = this.container.querySelectorAll('.weight-input');
        sliders.forEach(slider => {
            slider.addEventListener('input', (e) => {
                this.handleSliderChange(e.target);
            });
        });

        // Reset button
        const resetBtn = this.container.querySelector('.reset-weights');
        resetBtn.addEventListener('click', () => {
            this.resetToDefault();
        });

        // Apply button
        const applyBtn = this.container.querySelector('.apply-weights');
        applyBtn.addEventListener('click', () => {
            this.applyWeights();
        });

        // Preset buttons
        const presetButtons = this.container.querySelectorAll('.preset-btn');
        presetButtons.forEach(button => {
            button.addEventListener('click', () => {
                this.applyPreset(button.dataset.preset);
            });
        });
    }

    /**
     * Handle slider value change
     */
    handleSliderChange(slider) {
        const dimension = slider.dataset.dimension;
        const newValue = parseFloat(slider.value);

        const otherDimensions = Object.keys(this.weights).filter((key) => key !== dimension);
        const remainingTotal = 1 - newValue;
        const currentRemainingSum = otherDimensions.reduce((sum, key) => sum + this.weights[key], 0);

        this.weights[dimension] = newValue;

        if (currentRemainingSum > 0) {
            const scale = remainingTotal / currentRemainingSum;
            otherDimensions.forEach((key) => {
                this.weights[key] = Math.max(0, this.weights[key] * scale);
            });
        } else {
            otherDimensions.forEach((key) => {
                this.weights[key] = remainingTotal / otherDimensions.length;
            });
        }

        const normalizedTotal = Object.values(this.weights).reduce((sum, weight) => sum + weight, 0);
        if (normalizedTotal > 0) {
            const adjustFactor = 1 / normalizedTotal;
            Object.keys(this.weights).forEach((key) => {
                this.weights[key] *= adjustFactor;
            });
        }

        this.render();
        this.attachEventListeners();
    }

    /**
     * Update the total weight display
     */
    updateTotalDisplay() {
        const total = this.getTotalWeight();
        const totalElement = this.container.querySelector('.total-value');
        if (totalElement) {
            totalElement.textContent = `${total}%`;
            totalElement.className = `total-value ${total === 100 ? 'valid' : 'invalid'}`;
        }
    }

    /**
     * Calculate total weight percentage
     */
    getTotalWeight() {
        const total = Object.values(this.weights).reduce((sum, weight) => sum + weight, 0);
        return (total * 100).toFixed(1);
    }

    /**
     * Reset weights to default values
     */
    resetToDefault() {
        this.setPreset('default');
    }

    /**
     * Apply a preset distribution
     */
    setPreset(preset) {
        const presets = {
            default: {
                spec_similarity: 0.40,
                compliance: 0.25,
                price_delta: 0.15,
                lead_time: 0.10,
                quality_signals: 0.10
            },
            cost: {
                spec_similarity: 0.25,
                compliance: 0.20,
                price_delta: 0.30,
                lead_time: 0.15,
                quality_signals: 0.10
            },
            availability: {
                spec_similarity: 0.20,
                compliance: 0.20,
                price_delta: 0.15,
                lead_time: 0.30,
                quality_signals: 0.15
            }
        };

        this.weights = presets[preset] ?? { ...this.weights };
        this.render();
        this.attachEventListeners();
    }

    applyPreset(preset) {
        this.setPreset(preset);
    }

    /**
     * Apply the current weights
     */
    applyWeights() {
        const total = Object.values(this.weights).reduce((sum, weight) => sum + weight, 0);

        if (Math.abs(total - 1.0) > 0.01) {
            this.showError('Weights must total 100%');
            return;
        }

        if (this.onWeightsChange) {
            this.onWeightsChange(this.weights);
        }
    }

    /**
     * Set weights programmatically
     */
    setWeights(weights) {
        this.weights = { ...weights };
        this.render();
        this.attachEventListeners();
    }

    /**
     * Get current weights
     */
    getWeights() {
        return { ...this.weights };
    }

    /**
     * Show error message
     */
    showError(message) {
        // Remove existing error
        const existingError = this.container.querySelector('.weight-error');
        if (existingError) existingError.remove();

        const errorDiv = document.createElement('div');
        errorDiv.className = 'weight-error';
        errorDiv.textContent = message;

        const actions = this.container.querySelector('.weight-actions');
        actions.appendChild(errorDiv);

        // Auto-remove after 3 seconds
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.remove();
            }
        }, 3000);
    }

    /**
     * Validate that weights sum to 100%
     */
    validateWeights() {
        const total = Object.values(this.weights).reduce((sum, weight) => sum + weight, 0);
        return Math.abs(total - 1.0) <= 0.01;
    }
}