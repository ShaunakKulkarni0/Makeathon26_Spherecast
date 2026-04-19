/**
 * SearchForm Component
 * Hybrid searchable material selector with group/data-availability filters.
 */

export class SearchForm {
    constructor(container, onSearch) {
        this.container = container;
        this.onSearch = onSearch;

        this.materials = [];
        this.filteredMaterials = [];
        this.activeGroupFilter = 'all';
        this.activeDataFilter = 'all';
        this.selectedMaterial = null;

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
                    <label for="material-search-input">Original Material</label>
                    <input
                        type="text"
                        id="material-search-input"
                        placeholder="Type to search materials..."
                        autocomplete="off"
                    >
                    <input type="hidden" id="selected-material-id" name="selected_material_id">
                    <div class="material-dropdown hidden" id="material-dropdown"></div>
                    <div class="selected-material-meta hidden" id="selected-material-meta"></div>
                    <p class="field-hint">Search across all products. Only entries marked "Data available" can be scored.</p>
                </div>

                <div class="search-filters">
                    <div class="form-group">
                        <label for="group-filter">Group</label>
                        <select id="group-filter">
                            <option value="all">All Groups</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="data-filter">Data Availability</label>
                        <select id="data-filter">
                            <option value="all">All</option>
                            <option value="has_data">With Data</option>
                            <option value="no_data">Without Data</option>
                        </select>
                    </div>
                </div>

                <div class="form-row form-row-compact">
                    <div class="form-group">
                        <label for="top-n">Top N Results</label>
                        <input type="number" id="top-n" name="top_n" min="1" max="15" value="3">
                    </div>
                    <div class="form-group">
                        <label for="destination-country">Destination Country</label>
                        <input type="text" id="destination-country" name="destination_country" value="DE" maxlength="8">
                    </div>
                </div>

                <fieldset class="ko-fieldset">
                    <legend>K.O. Filters (Hard Exclusion)</legend>

                    <div class="form-row">
                        <div class="form-group">
                            <label for="max-quantity">Max Quantity (MOQ limit)</label>
                            <input type="number" id="max-quantity" name="max_quantity" min="1" step="1" placeholder="e.g. 200">
                        </div>
                        <div class="form-group">
                            <label for="max-lead-time-days">Max Lead Time (days)</label>
                            <input type="number" id="max-lead-time-days" name="max_lead_time_days" min="1" step="1" placeholder="e.g. 30">
                        </div>
                    </div>

                    <div class="form-group">
                        <label for="max-price-multiplier">Max Price Multiplier</label>
                        <input type="number" id="max-price-multiplier" name="max_price_multiplier" min="0.1" step="0.01" value="2.0">
                    </div>

                    <div class="form-group">
                        <label for="critical-certs">Critical Certifications (comma separated)</label>
                        <input type="text" id="critical-certs" name="critical_certs" placeholder="ISO9001, HACCP">
                    </div>

                    <div class="form-group">
                        <label for="prohibited-allergens">Prohibited Allergens (comma separated)</label>
                        <input type="text" id="prohibited-allergens" name="prohibited_allergens" placeholder="peanuts, tree_nuts">
                    </div>
                </fieldset>

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

        const groups = Array.from(new Set(
            this.materials
                .map((m) => (m.group || '').trim())
                .filter(Boolean)
        )).sort((a, b) => a.localeCompare(b));

        const groupFilter = this.container.querySelector('#group-filter');
        if (groupFilter) {
            groupFilter.innerHTML = `
                <option value="all">All Groups</option>
                ${groups.map((group) => `<option value="${this.escapeHtml(group)}">${this.escapeHtml(group)}</option>`).join('')}
            `;
        }

        this.applyFiltersAndRender();
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
        const input = this.container.querySelector('#material-search-input');
        const groupFilter = this.container.querySelector('#group-filter');
        const dataFilter = this.container.querySelector('#data-filter');

        form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleSubmit();
        });

        input.addEventListener('input', () => {
            if (this.selectedMaterial && input.value !== this.selectedMaterial.name) {
                this.clearSelectedMaterial();
            }
            this.applyFiltersAndRender();
        });

        input.addEventListener('focus', () => {
            this.applyFiltersAndRender();
        });

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.hideDropdown();
            }
            if (e.key === 'Enter' && !this.selectedMaterial && this.filteredMaterials.length > 0) {
                e.preventDefault();
                this.selectMaterial(this.filteredMaterials[0]);
            }
        });

        groupFilter.addEventListener('change', (e) => {
            this.activeGroupFilter = e.target.value || 'all';
            this.applyFiltersAndRender();
        });

        dataFilter.addEventListener('change', (e) => {
            this.activeDataFilter = e.target.value || 'all';
            this.applyFiltersAndRender();
        });

        const clearBtn = this.container.querySelector('.clear-btn');
        clearBtn.addEventListener('click', () => {
            this.clearForm();
        });

        document.addEventListener('click', (event) => {
            if (!this.container.contains(event.target)) {
                this.hideDropdown();
            }
        });
    }

    applyFiltersAndRender() {
        const input = this.container.querySelector('#material-search-input');
        const query = (input?.value || '').trim().toLowerCase();

        this.filteredMaterials = this.materials.filter((material) => {
            const group = (material.group || '').trim();
            const hasData = Boolean(material.has_data);

            if (this.activeGroupFilter !== 'all' && group !== this.activeGroupFilter) {
                return false;
            }
            if (this.activeDataFilter === 'has_data' && !hasData) {
                return false;
            }
            if (this.activeDataFilter === 'no_data' && hasData) {
                return false;
            }

            if (!query) return true;
            const searchable = [material.name, material.id, material.group, material.source]
                .filter(Boolean)
                .join(' ')
                .toLowerCase();
            return searchable.includes(query);
        });

        this.renderDropdown(this.filteredMaterials.slice(0, 40));
    }

    renderDropdown(items) {
        const dropdown = this.container.querySelector('#material-dropdown');
        if (!dropdown) return;

        if (!items.length) {
            dropdown.innerHTML = '<div class="material-option-empty">No matching products</div>';
            dropdown.classList.remove('hidden');
            return;
        }

        dropdown.innerHTML = items.map((material) => {
            const availabilityClass = material.has_data ? 'tag-ok' : 'tag-muted';
            const availabilityLabel = material.has_data ? 'Data available' : 'No data';
            return `
                <button type="button" class="material-option" data-material-id="${this.escapeHtml(material.id)}">
                    <div class="material-option-main">
                        <span class="material-option-name">${this.escapeHtml(material.name)}</span>
                        <span class="material-option-id">${this.escapeHtml(material.id)}</span>
                    </div>
                    <div class="material-option-meta">
                        <span class="material-tag">${this.escapeHtml(material.group || 'Ungrouped')}</span>
                        <span class="material-tag ${availabilityClass}">${availabilityLabel}</span>
                    </div>
                </button>
            `;
        }).join('');

        dropdown.classList.remove('hidden');

        const optionButtons = dropdown.querySelectorAll('.material-option');
        optionButtons.forEach((button) => {
            button.addEventListener('click', () => {
                const materialId = button.dataset.materialId;
                const material = this.materials.find((m) => m.id === materialId);
                if (material) this.selectMaterial(material);
            });
        });
    }

    hideDropdown() {
        const dropdown = this.container.querySelector('#material-dropdown');
        if (dropdown) dropdown.classList.add('hidden');
    }

    selectMaterial(material) {
        this.selectedMaterial = material;

        const input = this.container.querySelector('#material-search-input');
        const hiddenInput = this.container.querySelector('#selected-material-id');
        const meta = this.container.querySelector('#selected-material-meta');

        if (input) input.value = material.name;
        if (hiddenInput) hiddenInput.value = material.score_material_id || '';

        if (meta) {
            const availabilityLabel = material.has_data ? 'Data available' : 'No data';
            meta.textContent = `Selected: ${material.name} • ${material.group || 'Ungrouped'} • ${availabilityLabel}`;
            meta.classList.remove('hidden');
        }

        this.hideDropdown();
        this.hideError();
    }

    clearSelectedMaterial() {
        this.selectedMaterial = null;
        const hiddenInput = this.container.querySelector('#selected-material-id');
        const meta = this.container.querySelector('#selected-material-meta');
        if (hiddenInput) hiddenInput.value = '';
        if (meta) {
            meta.textContent = '';
            meta.classList.add('hidden');
        }
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
        if (!this.selectedMaterial) {
            this.showError('Please choose a material from the dropdown.');
            return false;
        }

        if (!this.selectedMaterial.has_data || !data.selected_material_id) {
            this.showError('Selected material has no scoring data yet. Please choose an entry marked "Data available".');
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

        const input = this.container.querySelector('#material-search-input');
        if (input) input.value = '';

        const groupFilter = this.container.querySelector('#group-filter');
        if (groupFilter) groupFilter.value = 'all';

        const dataFilter = this.container.querySelector('#data-filter');
        if (dataFilter) dataFilter.value = 'all';

        this.activeGroupFilter = 'all';
        this.activeDataFilter = 'all';
        this.clearSelectedMaterial();

        this.setRequirementsDefaults(this.requirementsDefaults);
        this.applyFiltersAndRender();
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

    escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }
}
