/**
 * API Client for Spherecast Material Substitute Finder
 * Handles communication with the FastAPI backend
 */

export class API {
    constructor(baseURL = 'http://localhost:8001/api') {
        this.baseURL = baseURL;
    }

    /**
     * Search for material substitutes
     * @param {Object} query - Search query object
     * @returns {Promise<Object>} Search results
     */
    async searchMaterials(query) {
        const response = await this.request('/csv/score', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(query)
        });

        return response;
    }

    async getCsvMaterials() {
        return this.request('/csv/materials');
    }

    async scoreCsvSelection(selectedMaterialId, weights = null, topN = 3, requirementsOverride = null) {
        return this.searchMaterials({
            selected_material_id: selectedMaterialId,
            weights,
            top_n: topN,
            requirements_override: requirementsOverride,
        });
    }

    async createEmailDraft(payload) {
        return this.request('/sales/email-draft', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload || {}),
        });
    }

    /**
     * Get search results by ID
     * @param {string} resultId - Result ID
     * @returns {Promise<Object>} Search results
     */
    async getResults(resultId) {
        return this.request(`/results/${resultId}`);
    }

    /**
     * Get current scoring weights
     * @returns {Promise<Object>} Current weights
     */
    async getWeights() {
        return this.request('/config');
    }

    /**
     * Update scoring weights
     * @param {Object} weights - New weights
     * @returns {Promise<Object>} Updated weights
     */
    async updateWeights(weights) {
        const response = await this.request('/config', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(weights)
        });

        return response;
    }

    /**
     * Rescore results with new weights
     * @param {string} originalId - Original material ID
     * @param {Object} weights - New weights
     * @returns {Promise<Object>} Rescored results
     */
    async rescoreWithWeights(originalId, weights) {
        const response = await this.request(`/rescore/${originalId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ weights })
        });

        return response;
    }

    /**
     * Get material details
     * @param {string} materialId - Material ID
     * @returns {Promise<Object>} Material details
     */
    async getMaterial(materialId) {
        return this.request(`/materials/${materialId}`);
    }

    /**
     * Get available categories
     * @returns {Promise<Array>} Material categories
     */
    async getCategories() {
        return this.request('/categories');
    }

    /**
     * Get available certifications
     * @returns {Promise<Array>} Certifications
     */
    async getCertifications() {
        return this.request('/certifications');
    }

    /**
     * Upload material data (for admin)
     * @param {FormData} formData - Material data
     * @returns {Promise<Object>} Upload result
     */
    async uploadMaterials(formData) {
        const response = await this.request('/upload', {
            method: 'POST',
            body: formData
        });

        return response;
    }

    /**
     * Generic request method
     * @param {string} endpoint - API endpoint
     * @param {Object} options - Fetch options
     * @returns {Promise<Object>} Response data
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;

        try {
            const response = await fetch(url, {
                ...options,
                headers: {
                    'Accept': 'application/json',
                    ...options.headers
                }
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || errorData.message || `HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            if (error.name === 'TypeError' && error.message.includes('fetch')) {
                throw new Error('Network error: Unable to connect to server');
            }
            throw error;
        }
    }

    /**
     * Set base URL
     * @param {string} baseURL - New base URL
     */
    setBaseURL(baseURL) {
        this.baseURL = baseURL;
    }

    /**
     * Check if server is available
     * @returns {Promise<boolean>} Server availability
     */
    async checkHealth() {
        try {
            await this.request('/health');
            return true;
        } catch (error) {
            return false;
        }
    }
}

// Default export
export default API;
