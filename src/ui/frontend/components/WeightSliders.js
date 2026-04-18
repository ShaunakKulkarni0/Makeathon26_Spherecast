/**
 * WeightSliders Component
 * Independent priority sliders (0-10), normalized to scoring weights on apply.
 */

export class WeightSliders {
    constructor(container, onWeightsChange) {
        this.container = container;
        this.onWeightsChange = onWeightsChange;

        this.importance = {
            spec: 4,
            compliance: 3,
            price: 2,
            lead_time: 1,
            quality: 1
        };

        this.dimensionLabels = {
            spec: 'Spec Similarity',
            compliance: 'Compliance',
            price: 'Price Delta',
            lead_time: 'Lead Time',
            quality: 'Quality Signals'
        };

        this.render();
        this.attachEventListeners();
    }

    render() {
        this.container.innerHTML = `
            <div class="weight-panel">
                <div class="weight-panel-header">
                    <h4>Scoring Priorities</h4>
                    <span class="weight-total">Total: <strong>${this.getTotalPriority()}</strong></span>
                </div>
                <p class="weight-help">0 = ignore, 10 = critical. Weights are normalized before scoring.</p>

                <div class="weight-sliders">
                    ${Object.entries(this.importance).map(([key, value]) => this.renderImportanceSlider(key, value)).join('')}
                </div>

                <div class="weight-presets">
                    <button class="btn btn-secondary preset-btn" data-preset="default">Balanced</button>
                    <button class="btn btn-secondary preset-btn" data-preset="cost">Cost Focus</button>
                    <button class="btn btn-secondary preset-btn" data-preset="availability">Time Focus</button>
                </div>

                <div class="weight-actions">
                    <button class="btn btn-secondary reset-weights">Reset</button>
                    <button class="btn btn-primary apply-weights">Recalculate</button>
                </div>
            </div>
        `;

        this.updateSliderDisplays();
    }

    renderImportanceSlider(key, importanceValue) {
        const label = this.dimensionLabels[key];

        return `
            <div class="weight-slider" data-dimension="${key}">
                <div class="weight-label">
                    <span class="dimension-name">${label}</span>
                    <span class="weight-value-badge">${importanceValue}/10</span>
                </div>
                <input
                    type="range"
                    class="weight-input"
                    min="0"
                    max="10"
                    step="1"
                    value="${importanceValue}"
                    data-dimension="${key}"
                >
                <div class="weight-scale weight-scale-full">
                    ${Array.from({ length: 11 }, (_, i) => `<span>${i}</span>`).join('')}
                </div>
            </div>
        `;
    }

    attachEventListeners() {
        const sliders = this.container.querySelectorAll('.weight-input');
        sliders.forEach((slider) => {
            slider.addEventListener('input', (e) => {
                this.handleSliderChange(e.target);
            });
        });

        const resetBtn = this.container.querySelector('.reset-weights');
        resetBtn.addEventListener('click', () => {
            this.resetToDefault();
        });

        const applyBtn = this.container.querySelector('.apply-weights');
        applyBtn.addEventListener('click', () => {
            this.applyWeights();
        });

        const presetButtons = this.container.querySelectorAll('.preset-btn');
        presetButtons.forEach((button) => {
            button.addEventListener('click', () => {
                this.applyPreset(button.dataset.preset);
            });
        });
    }

    handleSliderChange(slider) {
        const dimension = slider.dataset.dimension;
        const newValue = Math.max(0, Math.min(10, parseInt(slider.value, 10) || 0));
        this.importance[dimension] = newValue;
        this.updateSliderDisplays();
    }

    updateSliderDisplays() {
        Object.entries(this.importance).forEach(([key, importanceValue]) => {
            const slider = this.container.querySelector(`.weight-input[data-dimension="${key}"]`);
            if (slider) {
                slider.value = String(importanceValue);
                const percent = ((importanceValue / 10) * 100).toFixed(0);
                slider.style.setProperty('--slider-fill', `${percent}%`);
            }

            const valueLabel = this.container.querySelector(`.weight-slider[data-dimension="${key}"] .weight-value-badge`);
            if (valueLabel) {
                valueLabel.textContent = `${importanceValue}/10`;
            }
        });

        const totalEl = this.container.querySelector('.weight-total strong');
        if (totalEl) {
            totalEl.textContent = String(this.getTotalPriority());
        }
    }

    getTotalPriority() {
        return Object.values(this.importance).reduce((sum, value) => sum + value, 0);
    }

    getNormalizedWeights() {
        const totalImportance = this.getTotalPriority();
        if (totalImportance <= 0) {
            return Object.fromEntries(Object.keys(this.importance).map((key) => [key, 0]));
        }

        const normalized = {};
        Object.entries(this.importance).forEach(([key, value]) => {
            normalized[key] = value / totalImportance;
        });
        return normalized;
    }

    resetToDefault() {
        this.setPreset('default');
    }

    setPreset(preset) {
        const presets = {
            default: {
                spec: 4,
                compliance: 3,
                price: 2,
                lead_time: 1,
                quality: 1
            },
            cost: {
                spec: 3,
                compliance: 2,
                price: 5,
                lead_time: 2,
                quality: 1
            },
            availability: {
                spec: 3,
                compliance: 2,
                price: 1,
                lead_time: 5,
                quality: 2
            }
        };

        this.importance = presets[preset] ? { ...presets[preset] } : { ...this.importance };
        this.render();
        this.attachEventListeners();
    }

    applyPreset(preset) {
        this.setPreset(preset);
    }

    applyWeights() {
        const totalPriority = this.getTotalPriority();
        if (totalPriority <= 0) {
            this.showError('Set at least one slider above 0 before recalculating.');
            return;
        }
        if (this.onWeightsChange) {
            this.onWeightsChange(this.getNormalizedWeights());
        }
    }

    setWeights(weights) {
        if (!weights || typeof weights !== 'object') return;

        const keys = Object.keys(this.importance);
        const mappedImportance = {};
        keys.forEach((key) => {
            const value = Number(weights[key] ?? 0);
            if (!Number.isFinite(value) || value <= 0) {
                mappedImportance[key] = 0;
                return;
            }
            mappedImportance[key] = Math.max(0, Math.min(10, Math.round(value * 10)));
        });

        this.importance = mappedImportance;
        this.render();
        this.attachEventListeners();
    }

    getWeights() {
        return this.getNormalizedWeights();
    }

    showError(message) {
        const existingError = this.container.querySelector('.weight-error');
        if (existingError) existingError.remove();

        const errorDiv = document.createElement('div');
        errorDiv.className = 'weight-error';
        errorDiv.textContent = message;

        const actions = this.container.querySelector('.weight-actions');
        actions.appendChild(errorDiv);

        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.remove();
            }
        }, 3000);
    }

    validateWeights() {
        return true;
    }
}
