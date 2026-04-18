/**
 * SearchForm Component
 * CSV material selector plus editable KO-filter inputs.
 */

export class SearchForm {
    constructor(container, onSearch) {
        this.container = container;
        this.onSearch = onSearch;
        this.materials = [];
        this.requirementsDefaults = {
            max_quantity: null,
            destination_country: 'DE',
            critical_certs: [],
            prohibited_allergens: [],
            allergen_policy: 'hybrid',
            max_lead_time_days: null,
            max_price_multiplier: 2.0,
        };
        this.render();
        this.attachEventListeners();
    }

    render() {
        this.container.innerHTML = `
            <form class="search-form" id="material-search-form">
                <div class="form-group">
                    <label for="selected-material-id">Original Material (from CSV)</label>
                    <select id="selected-material-id" name="selected_material_id" required>
                        <option value="">Loading materials...</option>
                    </select>
                </div>

                <div class="form-group">
                    <label for="top-n">Top N Results</label>
                    <input type="number" id="top-n" name="top_n" min="1" max="15" value="3">
                </div>

                <div class="form-group">
                    <h4>K.O. Filters (Hard Exclusion Criteria)</h4>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label for="destination-country">Destination Country</label>
                        <input type="text" id="destination-country" name="destination_country" value="DE" maxlength="8">
                    </div>
                    <div class="form-group">
                        <label for="max-quantity">Max Quantity (MOQ limit)</label>
                        <input type="number" id="max-quantity" name="max_quantity" min="1" step="1" placeholder="e.g. 200">
                    </div>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label for="max-lead-time-days">Max Lead Time (days)</label>
                        <input type="number" id="max-lead-time-days" name="max_lead_time_days" min="1" step="1" placeholder="e.g. 30">
                    </div>
                    <div class="form-group">
                        <label for="max-price-multiplier">Max Price Multiplier</label>
                        <input type="number" id="max-price-multiplier" name="max_price_multiplier" min="0.1" step="0.01" value="2.0">
                    </div>
                </div>

                <div class="form-group">
                    <label for="critical-certs">Critical Certifications (comma separated)</label>
                    <input type="text" id="critical-certs" name="critical_certs" placeholder="ISO9001, HACCP">
                </div>

                <div class="form-group">
                    <label for="prohibited-allergens">Prohibited Allergens (comma separated)</label>
                    <input type="text" id="prohibited-allergens" name="prohibited_allergens" placeholder="peanuts, tree_nuts">
                </div>

                <div class="form-actions">
                    <button type="submit" class="btn btn-primary search-btn">
                        <span class="btn-text">Run CSV Scoring</span>
                        <span class="btn-loading hidden">Scoring...</span>
                    </button>
                    <button type="button" class="btn btn-secondary clear-btn">Reset Form</button>
                </div>
            </form>
        `;
    }

    setMaterialOptions(materials) {
        this.materials = Array.isArray(materials) ? materials : [];
        const select = this.container.querySelector('#selected-material-id');
        if (!select) return;

        select.innerHTML = `
            <option value="">Select material from CSV</option>
            ${this.materials.map((m) => `<option value="${m.id}">${m.name} (${m.id})</option>`).join('')}
        `;
    }

    setRequirementsDefaults(defaults) {
        this.requirementsDefaults = {
            ...this.requirementsDefaults,
            ...(defaults || {}),
        };

        const setValue = (selector, value) => {
            const el = this.container.querySelector(selector);
            if (!el) return;
            el.value = value === null || value === undefined ? '' : String(value);
        };

        setValue('#destination-country', this.requirementsDefaults.destination_country || 'DE');
        setValue('#max-quantity', this.requirementsDefaults.max_quantity);
        setValue('#max-lead-time-days', this.requirementsDefaults.max_lead_time_days);
        setValue('#max-price-multiplier', this.requirementsDefaults.max_price_multiplier ?? 2.0);

        const certs = Array.isArray(this.requirementsDefaults.critical_certs)
            ? this.requirementsDefaults.critical_certs
            : [];
        setValue('#critical-certs', certs.join(', '));
        const allergens = Array.isArray(this.requirementsDefaults.prohibited_allergens)
            ? this.requirementsDefaults.prohibited_allergens
            : [];
        setValue('#prohibited-allergens', allergens.join(', '));
    }

    attachEventListeners() {
        const form = this.container.querySelector('#material-search-form');
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleSubmit();
        });

        const clearBtn = this.container.querySelector('.clear-btn');
        clearBtn.addEventListener('click', () => {
            this.clearForm();
        });
    }

    async handleSubmit() {
        const formData = this.getFormData();
        if (!this.validateForm(formData)) return;

        this.setLoading(true);
        try {
            await this.onSearch(formData);
        } catch (error) {
            console.error('Scoring failed:', error);
            this.showError('Scoring failed. Please try again.');
        } finally {
            this.setLoading(false);
        }
    }

    getFormData() {
        const form = this.container.querySelector('#material-search-form');
        const formData = new FormData(form);
        const topNRaw = formData.get('top_n');

        const maxQuantityRaw = String(formData.get('max_quantity') || '').trim();
        const maxLeadRaw = String(formData.get('max_lead_time_days') || '').trim();
        const maxPriceRaw = String(formData.get('max_price_multiplier') || '').trim();
        const certsRaw = String(formData.get('critical_certs') || '').trim();
        const allergensRaw = String(formData.get('prohibited_allergens') || '').trim();
        const destinationCountry = String(formData.get('destination_country') || '').trim() || 'DE';

        const criticalCerts = certsRaw
            ? certsRaw.split(',').map((item) => item.trim()).filter(Boolean)
            : [];
        const prohibitedAllergens = allergensRaw
            ? allergensRaw.split(',').map((item) => item.trim()).filter(Boolean)
            : [];

        return {
            selected_material_id: String(formData.get('selected_material_id') || '').trim(),
            top_n: topNRaw ? parseInt(String(topNRaw), 10) : 3,
            requirements_override: {
                max_quantity: maxQuantityRaw ? parseInt(maxQuantityRaw, 10) : null,
                destination_country: destinationCountry,
                critical_certs: criticalCerts,
                prohibited_allergens: prohibitedAllergens,
                allergen_policy: this.requirementsDefaults.allergen_policy || 'hybrid',
                max_lead_time_days: maxLeadRaw ? parseInt(maxLeadRaw, 10) : null,
                max_price_multiplier: maxPriceRaw ? parseFloat(maxPriceRaw) : 2.0,
            },
        };
    }

    validateForm(data) {
        if (!data.selected_material_id) {
            this.showError('Please select a material from CSV.');
            return false;
        }
        if (!Number.isInteger(data.top_n) || data.top_n < 1 || data.top_n > 15) {
            this.showError('Top N must be between 1 and 15.');
            return false;
        }

        const req = data.requirements_override;
        if (req.max_quantity !== null && (!Number.isInteger(req.max_quantity) || req.max_quantity < 1)) {
            this.showError('Max Quantity must be empty or an integer >= 1.');
            return false;
        }
        if (req.max_lead_time_days !== null && (!Number.isInteger(req.max_lead_time_days) || req.max_lead_time_days < 1)) {
            this.showError('Max Lead Time must be empty or an integer >= 1.');
            return false;
        }
        if (!Number.isFinite(req.max_price_multiplier) || req.max_price_multiplier <= 0) {
            this.showError('Max Price Multiplier must be a positive number.');
            return false;
        }

        return true;
    }

    setLoading(loading) {
        const submitBtn = this.container.querySelector('.search-btn');
        const btnText = submitBtn.querySelector('.btn-text');
        const btnLoading = submitBtn.querySelector('.btn-loading');

        if (loading) {
            submitBtn.disabled = true;
            btnText.classList.add('hidden');
            btnLoading.classList.remove('hidden');
        } else {
            submitBtn.disabled = false;
            btnText.classList.remove('hidden');
            btnLoading.classList.add('hidden');
        }
    }

    clearForm() {
        const form = this.container.querySelector('#material-search-form');
        form.reset();

        const topN = this.container.querySelector('#top-n');
        if (topN) topN.value = '3';

        const select = this.container.querySelector('#selected-material-id');
        if (select) select.value = '';

        this.setRequirementsDefaults(this.requirementsDefaults);
        this.hideError();
    }

    showError(message) {
        this.hideError();
        const errorDiv = document.createElement('div');
        errorDiv.className = 'form-error';
        errorDiv.textContent = message;
        const form = this.container.querySelector('.search-form');
        form.appendChild(errorDiv);
    }

    hideError() {
        const existingError = this.container.querySelector('.form-error');
        if (existingError) existingError.remove();
    }
}
