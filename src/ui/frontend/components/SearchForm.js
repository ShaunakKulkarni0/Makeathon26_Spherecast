/**
 * SearchForm Component
 * Material search input form
 */

export class SearchForm {
    constructor(container, onSearch) {
        this.container = container;
        this.onSearch = onSearch;
        this.render();
        this.attachEventListeners();
    }

    /**
     * Render the search form
     */
    render() {
        this.container.innerHTML = `
            <form class="search-form" id="material-search-form">
                <div class="form-group">
                    <label for="material-name">Material Name</label>
                    <input
                        type="text"
                        id="material-name"
                        name="name"
                        placeholder="e.g., Glucose, Vitamin C, Calcium Carbonate"
                        required
                    >
                </div>

                <div class="form-group">
                    <label for="material-category">Category</label>
                    <select id="material-category" name="category">
                        <option value="">Select Category</option>
                        <option value="sweetener">Sweetener</option>
                        <option value="vitamin">Vitamin</option>
                        <option value="mineral">Mineral</option>
                        <option value="amino_acid">Amino Acid</option>
                        <option value="carrier">Carrier/Filler</option>
                        <option value="preservative">Preservative</option>
                        <option value="colorant">Colorant</option>
                        <option value="flavor">Flavor</option>
                        <option value="other">Other</option>
                    </select>
                </div>

                <div class="form-group">
                    <label for="application">Application</label>
                    <input
                        type="text"
                        id="application"
                        name="application"
                        placeholder="e.g., dietary supplement, food additive"
                    >
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label for="max-quantity">Max Monthly Quantity</label>
                        <input
                            type="number"
                            id="max-quantity"
                            name="max_quantity"
                            placeholder="e.g., 10000"
                            min="1"
                        >
                    </div>

                    <div class="form-group">
                        <label for="destination-country">Destination Country</label>
                        <select id="destination-country" name="destination_country">
                            <option value="DE">Germany</option>
                            <option value="US">United States</option>
                            <option value="UK">United Kingdom</option>
                            <option value="FR">France</option>
                            <option value="IT">Italy</option>
                            <option value="ES">Spain</option>
                            <option value="NL">Netherlands</option>
                            <option value="CH">Switzerland</option>
                        </select>
                    </div>
                </div>

                <div class="form-group">
                    <label for="certifications">Required Certifications (optional)</label>
                    <div class="certification-inputs">
                        <input
                            type="text"
                            id="certifications"
                            name="certifications"
                            placeholder="e.g., GMP, ISO 22000, Halal (comma-separated)"
                        >
                    </div>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label for="max-lead-time">Max Lead Time (days)</label>
                        <input
                            type="number"
                            id="max-lead-time"
                            name="max_lead_time"
                            placeholder="e.g., 30"
                            min="1"
                        >
                    </div>

                    <div class="form-group">
                        <label for="max-price-multiplier">Max Price Multiplier</label>
                        <input
                            type="number"
                            id="max-price-multiplier"
                            name="max_price_multiplier"
                            placeholder="e.g., 2.0"
                            min="1"
                            step="0.1"
                            value="2.0"
                        >
                    </div>
                </div>

                <div class="form-actions">
                    <button type="submit" class="btn btn-primary search-btn">
                        <span class="btn-text">Find Substitutes</span>
                        <span class="btn-loading hidden">Searching...</span>
                    </button>
                    <button type="button" class="btn btn-secondary clear-btn">Clear Form</button>
                </div>
            </form>
        `;
    }

    /**
     * Attach event listeners
     */
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

        // Auto-format certifications input
        const certInput = this.container.querySelector('#certifications');
        certInput.addEventListener('blur', () => {
            this.formatCertifications(certInput);
        });
    }

    /**
     * Handle form submission
     */
    async handleSubmit() {
        const formData = this.getFormData();

        if (!this.validateForm(formData)) {
            return;
        }

        this.setLoading(true);

        try {
            await this.onSearch(formData);
        } catch (error) {
            console.error('Search failed:', error);
            this.showError('Search failed. Please try again.');
        } finally {
            this.setLoading(false);
        }
    }

    /**
     * Get form data as object
     */
    getFormData() {
        const form = this.container.querySelector('#material-search-form');
        const formData = new FormData(form);

        return {
            name: formData.get('name')?.trim(),
            category: formData.get('category')?.trim(),
            application: formData.get('application')?.trim(),
            max_quantity: formData.get('max_quantity') ? parseInt(formData.get('max_quantity')) : null,
            destination_country: formData.get('destination_country') || 'DE',
            certifications: this.parseCertifications(formData.get('certifications')),
            max_lead_time: formData.get('max_lead_time') ? parseInt(formData.get('max_lead_time')) : null,
            max_price_multiplier: formData.get('max_price_multiplier') ? parseFloat(formData.get('max_price_multiplier')) : 2.0
        };
    }

    /**
     * Parse certifications string into array
     */
    parseCertifications(certString) {
        if (!certString || !certString.trim()) return null;

        return certString.split(',')
            .map(cert => cert.trim())
            .filter(cert => cert.length > 0);
    }

    /**
     * Format certifications input
     */
    formatCertifications(input) {
        const certs = this.parseCertifications(input.value);
        if (certs) {
            input.value = certs.join(', ');
        }
    }

    /**
     * Validate form data
     */
    validateForm(data) {
        if (!data.name) {
            this.showError('Material name is required');
            return false;
        }

        if (data.max_quantity && data.max_quantity <= 0) {
            this.showError('Max quantity must be greater than 0');
            return false;
        }

        if (data.max_lead_time && data.max_lead_time <= 0) {
            this.showError('Max lead time must be greater than 0');
            return false;
        }

        if (data.max_price_multiplier && data.max_price_multiplier < 1) {
            this.showError('Max price multiplier must be at least 1.0');
            return false;
        }

        return true;
    }

    /**
     * Set loading state
     */
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

    /**
     * Clear form
     */
    clearForm() {
        const form = this.container.querySelector('#material-search-form');
        form.reset();
        this.hideError();
    }

    /**
     * Show error message
     */
    showError(message) {
        this.hideError();

        const errorDiv = document.createElement('div');
        errorDiv.className = 'form-error';
        errorDiv.textContent = message;

        const form = this.container.querySelector('.search-form');
        form.appendChild(errorDiv);
    }

    /**
     * Hide error message
     */
    hideError() {
        const existingError = this.container.querySelector('.form-error');
        if (existingError) {
            existingError.remove();
        }
    }
}