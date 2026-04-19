/**
 * ResultsList Component
 * Displays the list of top material candidates
 */

import { ScoreBreakdown } from './ScoreBreakdown.js';

export class ResultsList {
    constructor(container, onCandidateSelect, api, getRequirementsContext = null) {
        this.container = container;
        this.onCandidateSelect = onCandidateSelect;
        this.api = api;
        this.getRequirementsContext = getRequirementsContext;
        this.scoreBreakdown = new ScoreBreakdown(document.createElement('div'));
        this.activeDraftCandidateId = null;
        this.createModal();
    }

    displayCandidates(candidates) {
        if (!candidates || candidates.length === 0) {
            this.container.innerHTML = `
                <div class="no-results">
                    <h3>No suitable candidates found</h3>
                    <p>Try adjusting K.O. filters or scoring priorities.</p>
                </div>
            `;
            return;
        }

        this.container.innerHTML = `
            <div class="candidates-section">
                <h3>Top Material Candidates</h3>
                <div class="candidates-list">
                    ${candidates.map((candidate, index) => this.renderCandidate(candidate, index + 1)).join('')}
                </div>
            </div>
        `;

        this.attachEventListeners();
    }

    createModal() {
        if (document.getElementById('email-draft-modal')) return;

        const modal = document.createElement('div');
        modal.id = 'email-draft-modal';
        modal.className = 'email-draft-modal hidden';
        modal.innerHTML = `
            <div class="email-draft-backdrop" data-close-email-draft="true"></div>
            <div class="email-draft-card" role="dialog" aria-modal="true" aria-labelledby="email-draft-title">
                <div class="email-draft-header">
                    <h4 id="email-draft-title">Email Draft</h4>
                    <button class="btn btn-secondary btn-sm" data-close-email-draft="true" type="button">Close</button>
                </div>
                <p class="email-draft-subject"><strong>Subject:</strong> <span id="email-draft-subject"></span></p>
                <textarea id="email-draft-body" class="email-draft-textarea" readonly></textarea>
                <div class="email-draft-footer">
                    <button class="btn btn-secondary" id="email-draft-copy-btn" type="button">Copy Draft</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        modal.addEventListener('click', (event) => {
            if (event.target?.dataset?.closeEmailDraft === 'true') {
                this.closeDraftModal();
            }
        });

        const copyButton = modal.querySelector('#email-draft-copy-btn');
        copyButton?.addEventListener('click', async () => {
            const subject = modal.querySelector('#email-draft-subject')?.textContent || '';
            const body = modal.querySelector('#email-draft-body')?.value || '';
            const draft = `Subject: ${subject}\n\n${body}`;

            try {
                await navigator.clipboard.writeText(draft);
                copyButton.textContent = 'Copied';
                window.setTimeout(() => {
                    copyButton.textContent = 'Copy Draft';
                }, 1200);
            } catch (error) {
                console.error('Clipboard copy failed', error);
            }
        });
    }

    renderCandidate(candidate, rank) {
        const material = candidate.kandidat;
        const compositeScore = (candidate.composite_score * 100).toFixed(1);
        const uncertainty = candidate.uncertainty_report || null;

        return `
            <article class="candidate-item" data-candidate-id="${material.id}">
                <div class="candidate-header">
                    <div class="candidate-rank">#${rank}</div>
                    <div class="candidate-name-wrap">
                        <h4 class="candidate-name">${material.name}</h4>
                        <p class="candidate-raw-id">Raw ID: ${material.id}</p>
                    </div>
                    <div class="candidate-score">${compositeScore}% match</div>
                </div>

                <div class="candidate-details">
                    <div class="candidate-metrics">
                        <div class="metric">
                            <span class="metric-label">Price</span>
                            <span class="metric-value">${this.formatPrice(material.price)}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Lead Time</span>
                            <span class="metric-value">${material.lead_time.days} days</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">MOQ</span>
                            <span class="metric-value">${material.moq}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Origin</span>
                            <span class="metric-value">${material.country_of_origin || 'N/A'}</span>
                        </div>
                    </div>

                    <div class="candidate-score-breakdown">
                        ${this.renderMiniScoreBreakdown(candidate)}
                    </div>
                </div>

                <div class="candidate-actions">
                    <button class="btn btn-primary compare-btn" data-candidate-id="${material.id}">
                        Compare Details
                    </button>
                </div>

                <details class="candidate-detail-panel ai-accent-panel">
                    <summary>View Structured Explanation</summary>
                    <div class="candidate-detail-body">
                        ${this.renderExplanation(candidate)}
                        ${this.renderUncertainty(uncertainty)}
                    </div>
                </details>
            </article>
        `;
    }

    renderMiniScoreBreakdown(candidate) {
        const scores = candidate.scores;
        const dimensions = [
            { key: 'spec', label: 'Spec' },
            { key: 'compliance', label: 'Compliance' },
            { key: 'price', label: 'Price' },
            { key: 'lead_time', label: 'Lead Time' },
            { key: 'quality', label: 'Quality' },
        ];

        return `
            <div class="mini-scores">
                ${dimensions.map(({ key, label }) => {
            const raw = scores[key] ?? 0;
            const pct = Math.round(raw * 100);
            const tier = raw >= 0.999 ? 'perfect' : raw >= 0.80 ? 'good' : raw < 0.60 ? 'weak' : '';
            return `
                        <div class="mini-score-item${tier ? ' ' + tier : ''}">
                            <span class="mini-score-label">${label}</span>
                            <div class="mini-score-bar">
                                <div class="mini-score-fill" style="width:${pct}%"></div>
                            </div>
                            <div class="mini-score-value">${pct}%</div>
                        </div>
                    `;
        }).join('')}
            </div>
        `;
    }

    renderExplanation(candidate) {
        const explanation = candidate?.explanation || null;
        const material = candidate?.kandidat || {};
        const allergenRisk = candidate?.details?.allergen_risk || {};

        const sellerEmail = String(material.seller_email || '').trim();
        const sellerWebsite = String(material.seller_website || material.source_url || '').trim();
        const prohibited = Array.isArray(allergenRisk.prohibited_allergens)
            ? allergenRisk.prohibited_allergens
            : [];
        const containsHits = Array.isArray(allergenRisk.contains_hits) ? allergenRisk.contains_hits : [];
        const mayContainHits = Array.isArray(allergenRisk.may_contain_hits) ? allergenRisk.may_contain_hits : [];
        const hasAllergenData = Boolean(allergenRisk.has_allergen_data);

        const strengths = explanation ? (explanation.strengths || []).map((s) => s.text).slice(0, 3) : [];
        const weaknesses = explanation ? (explanation.weaknesses || []).map((w) => w.text).slice(0, 3) : [];
        const risks = explanation
            ? (explanation.risks || []).map((r) => (typeof r === 'string' ? r : r?.text)).filter(Boolean)
            : [];
        const allergenState = this.getAllergenState(containsHits, mayContainHits, hasAllergenData);
        const supplierName = this.extractSupplierName(material);
        const needsSellerContact = allergenState.needsContact;

        return `
            <div class="candidate-detail-grid">
                <section class="detail-card detail-card-highlight">
                    <h5>AI Summary</h5>
                    <p>${explanation?.summary || 'Not available'}</p>
                    <div class="detail-meta-row">
                        <span class="detail-chip">Recommendation: ${explanation?.recommendation || 'Not available'}</span>
                        <span class="detail-chip">Confidence: ${explanation?.confidence_statement || 'Not available'}</span>
                    </div>
                </section>

                ${this.renderListCard('Strengths', strengths, 'No major strengths highlighted')}
                ${this.renderListCard('Weaknesses', weaknesses, 'No major weaknesses highlighted')}
                ${this.renderListCard('Risks', risks, 'No major risks identified')}

                <section class="detail-card">
                    <h5>Contact</h5>
                    <div class="detail-kv"><span>Sales Email</span><span>${sellerEmail || 'Not available'}</span></div>
                    <div class="detail-kv"><span>Website</span><span>${sellerWebsite || 'Not available'}</span></div>
                    ${needsSellerContact ? `
                    <div class="detail-contact-actions">
                        <span class="detail-contact-hint">Contact seller</span>
                        <button
                            class="btn btn-sm btn-primary create-email-draft-btn"
                            type="button"
                            data-candidate-id="${material.id}"
                            data-supplier-name="${this.escapeHtml(supplierName)}"
                            data-seller-email="${this.escapeHtml(sellerEmail)}"
                            data-seller-website="${this.escapeHtml(sellerWebsite)}"
                            data-material-name="${this.escapeHtml(material.name || '')}"
                            data-material-id="${this.escapeHtml(material.id || '')}"
                            data-issue-summary="${this.escapeHtml(allergenState.text)}"
                            data-missing-information="${this.escapeHtml(allergenState.missingInformation.join('||'))}"
                            data-prohibited-allergens="${this.escapeHtml(prohibited.join('||'))}"
                        >
                            Create Email Draft
                        </button>
                    </div>
                    ` : ''}
                </section>

                <section class="detail-card">
                    <h5>Allergen Check</h5>
                    <p><span class="status-pill ${allergenState.className}">${allergenState.label}</span></p>
                    <p>${allergenState.text}</p>
                    <div class="detail-kv">
                        <span>Selected Prohibited Allergens</span>
                        <span>${prohibited.length ? prohibited.join(', ') : 'None selected'}</span>
                    </div>
                </section>
            </div>
        `;
    }

    getAllergenState(containsHits, mayContainHits, hasAllergenData) {
        if (!hasAllergenData) {
            return {
                className: 'status-warning',
                label: 'Limited Data',
                text: 'Contact seller for additional allergen information.',
                needsContact: true,
                missingInformation: [
                    'Complete allergen declaration',
                    'Cross-contamination / may-contain statement',
                    'Most recent specification sheet or CoA',
                ],
            };
        }
        if (containsHits.length) {
            return {
                className: 'status-danger',
                label: 'Contains Prohibited',
                text: `Contains prohibited allergens: ${containsHits.join(', ')}`,
                needsContact: false,
                missingInformation: [],
            };
        }
        if (mayContainHits.length) {
            return {
                className: 'status-warning',
                label: 'Potential Match',
                text: `May contain prohibited allergens: ${mayContainHits.join(', ')}`,
                needsContact: false,
                missingInformation: [],
            };
        }
        return {
            className: 'status-ok',
            label: 'No Match Found',
            text: 'No prohibited allergen matches found in available data.',
            needsContact: false,
            missingInformation: [],
        };
    }

    renderUncertainty(uncertainty) {
        if (!uncertainty) {
            return `
                <section class="detail-card">
                    <h5>Uncertainty</h5>
                    <p>Not available</p>
                </section>
            `;
        }

        const suggestions = uncertainty.verification_suggestions || [];
        return `
            <section class="detail-card">
                <h5>Uncertainty</h5>
                <div class="detail-kv"><span>Overall Level</span><span>${uncertainty.overall_level || 'Not available'}</span></div>
                <div class="detail-kv"><span>Overall Confidence</span><span>${uncertainty.overall_confidence ?? 'Not available'}</span></div>
                <div class="detail-kv"><span>Warning</span><span>${uncertainty.warning_message || 'None'}</span></div>
                ${this.renderSimpleList(suggestions, 'No verification suggestions')}
            </section>
        `;
    }

    renderListCard(title, items, emptyText) {
        return `
            <section class="detail-card">
                <h5>${title}</h5>
                ${this.renderSimpleList(items, emptyText)}
            </section>
        `;
    }

    renderSimpleList(items, emptyText) {
        if (!items || !items.length) {
            return `<p class="detail-empty">${emptyText}</p>`;
        }
        return `
            <ul class="detail-list">
                ${items.map((item) => `<li>${item}</li>`).join('')}
            </ul>
        `;
    }

    formatPrice(priceInfo) {
        const { value, unit } = priceInfo;
        if (value >= 1000) {
            return `${(value / 1000).toFixed(1)}k ${unit}`;
        }
        return `${value} ${unit}`;
    }

    attachEventListeners() {
        const candidateItems = this.container.querySelectorAll('.candidate-item');
        const compareButtons = this.container.querySelectorAll('.compare-btn');
        const draftButtons = this.container.querySelectorAll('.create-email-draft-btn');

        candidateItems.forEach((item) => {
            item.addEventListener('click', (e) => {
                if (e.target.closest('.candidate-detail-panel')) {
                    return;
                }
                if (!e.target.classList.contains('compare-btn')) {
                    const candidateId = item.dataset.candidateId;
                    const candidate = this.findCandidateById(candidateId);
                    if (candidate && this.onCandidateSelect) {
                        this.onCandidateSelect(candidate);
                    }
                }
            });
        });

        compareButtons.forEach((button) => {
            button.addEventListener('click', (e) => {
                e.stopPropagation();
                const candidateId = button.dataset.candidateId;
                const candidate = this.findCandidateById(candidateId);
                if (candidate && this.onCandidateSelect) {
                    this.onCandidateSelect(candidate);
                }
            });
        });

        draftButtons.forEach((button) => {
            button.addEventListener('click', async (e) => {
                e.stopPropagation();
                await this.handleEmailDraftRequest(button);
            });
        });
    }

    setCandidates(candidates) {
        this.candidates = candidates;
    }

    findCandidateById(id) {
        return this.candidates?.find((candidate) => candidate.kandidat.id === id) || null;
    }

    async handleEmailDraftRequest(button) {
        if (!this.api) return;

        const candidateId = button.dataset.candidateId || '';
        const missingInformation = (button.dataset.missingInformation || '')
            .split('||')
            .map((item) => item.trim())
            .filter(Boolean);
        const prohibitedAllergens = (button.dataset.prohibitedAllergens || '')
            .split('||')
            .map((item) => item.trim())
            .filter(Boolean);
        const requirementsContext = typeof this.getRequirementsContext === 'function'
            ? (this.getRequirementsContext() || {})
            : {};
        const destinationCountry = String(requirementsContext.destination_country || 'Germany').trim() || 'Germany';

        const payload = {
            supplier_name: button.dataset.supplierName || '',
            seller_email: button.dataset.sellerEmail || '',
            seller_website: button.dataset.sellerWebsite || '',
            material_name: button.dataset.materialName || '',
            material_id: button.dataset.materialId || '',
            issue_summary: button.dataset.issueSummary || 'Missing allergen information',
            missing_information: missingInformation,
            prohibited_allergens: prohibitedAllergens,
            destination_country: destinationCountry,
        };

        try {
            this.activeDraftCandidateId = candidateId;
            button.disabled = true;
            button.textContent = 'Creating...';
            const draft = await this.api.createEmailDraft(payload);
            this.openDraftModal(draft.subject || '', draft.body || '');
        } catch (error) {
            console.error('Email draft creation failed:', error);
            window.alert(`Failed to create email draft: ${error.message}`);
        } finally {
            button.disabled = false;
            button.textContent = 'Create Email Draft';
            this.activeDraftCandidateId = null;
        }
    }

    openDraftModal(subject, body) {
        const modal = document.getElementById('email-draft-modal');
        if (!modal) return;
        const subjectEl = modal.querySelector('#email-draft-subject');
        const bodyEl = modal.querySelector('#email-draft-body');
        if (subjectEl) subjectEl.textContent = subject || 'Supplier Information Request';
        if (bodyEl) bodyEl.value = body || '';
        modal.classList.remove('hidden');
    }

    closeDraftModal() {
        const modal = document.getElementById('email-draft-modal');
        if (!modal) return;
        modal.classList.add('hidden');
    }

    extractSupplierName(material) {
        if (!material) return '';
        const candidates = [
            material.supplier_name,
            material.seller_name,
            material.brand,
            material.manufacturer,
        ];
        return candidates.find((value) => String(value || '').trim()) || '';
    }

    escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }
}
