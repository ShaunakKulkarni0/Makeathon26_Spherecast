/**
 * API Client — Spherecast Material Substitute Builder
 * Handles all communication with the FastAPI backend.
 */

export class API {
    constructor(baseURL = 'http://localhost:8001/api') {
        this.baseURL = baseURL;
    }

    /** Search / score materials */
    async searchMaterials(query) {
        return this.request('/csv/score', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(query),
        });
    }

    /** Fetch all available CSV materials + requirement defaults */
    async getCsvMaterials() {
        return this.request('/csv/materials');
    }

    /** Score a single material selection with optional overrides */
    async scoreCsvSelection(selectedMaterialId, weights = null, topN = 3, requirementsOverride = null) {
        return this.searchMaterials({
            selected_material_id: selectedMaterialId,
            weights,
            top_n: topN,
            requirements_override: requirementsOverride,
        });
    }

    /** Create a sales email draft */
    async createEmailDraft(payload) {
        return this.request('/sales/email-draft', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload || {}),
        });
    }

    /** Get search results by ID */
    async getResults(resultId) {
        return this.request(`/results/${resultId}`);
    }

    /** Get current scoring weight config */
    async getWeights() {
        return this.request('/config');
    }

    /** Update scoring weights */
    async updateWeights(weights) {
        return this.request('/config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(weights),
        });
    }

    /** Rescore results with new weights */
    async rescoreWithWeights(originalId, weights) {
        return this.request(`/rescore/${originalId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ weights }),
        });
    }

    /** Get single material details */
    async getMaterial(materialId) {
        return this.request(`/materials/${materialId}`);
    }

    /** Get available material categories */
    async getCategories() {
        return this.request('/categories');
    }

    /** Get available certifications */
    async getCertifications() {
        return this.request('/certifications');
    }

    /** Upload material data (admin) */
    async uploadMaterials(formData) {
        return this.request('/upload', { method: 'POST', body: formData });
    }

    /** Health check */
    async checkHealth() {
        try { await this.request('/health'); return true; }
        catch { return false; }
    }

    /** Set API base URL */
    setBaseURL(baseURL) { this.baseURL = baseURL; }

    /**
     * Generic request wrapper with error normalization.
     * @param {string} endpoint
     * @param {RequestInit} options
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        try {
            const response = await fetch(url, {
                ...options,
                headers: { 'Accept': 'application/json', ...options.headers },
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
}

export default API;