/**
 * RejectedList Component
 * Displays materials that were rejected during scoring
 */

export class RejectedList {
    constructor(container) {
        this.container = container;
    }

    displayRejected(rejected) {
        if (!rejected || rejected.length === 0) {
            this.container.innerHTML = '';
            return;
        }

        this.container.innerHTML = `
            <section class="rejected-section">
                <h3>Rejected Candidates (${rejected.length})</h3>
                <div class="rejected-list">
                    ${rejected.map((candidate) => this.renderRejectedCandidate(candidate)).join('')}
                </div>
                <div class="rejected-summary">
                    <p>Filtered by knockout criteria or insufficient final score for substitution safety.</p>
                </div>
            </section>
        `;

        this.attachEventListeners();
    }

    renderRejectedCandidate(candidate) {
        const material = candidate.candidate;
        const reasons = candidate.reasons || [];

        return `
            <article class="rejected-item">
                <div class="rejected-header">
                    <div>
                        <div class="rejected-name">${material.name}</div>
                        <div class="rejected-raw-id">ID: ${material.id}</div>
                    </div>
                    <div class="rejected-reasons-count">${reasons.length} reason${reasons.length !== 1 ? 's' : ''}</div>
                    <button class="expand-btn" data-expanded="false" aria-label="Expand rejected details">
                        <span class="expand-icon">▶</span>
                    </button>
                </div>

                <div class="rejected-details hidden">
                    <div class="rejected-material-info">
                        <div class="material-details">
                            <p><strong>Price:</strong> ${this.formatPrice(material.price)}</p>
                            <p><strong>Lead Time:</strong> ${material.lead_time.days} days</p>
                            <p><strong>MOQ:</strong> ${material.moq}</p>
                            <p><strong>Country:</strong> ${material.country_of_origin || 'N/A'}</p>
                        </div>
                    </div>

                    <div class="rejected-reasons">
                        <h5>Rejection Reasons</h5>
                        <ul>
                            ${reasons.map((reason) => `<li class="rejected-reason">${this.formatReason(reason)}</li>`).join('')}
                        </ul>
                    </div>

                    ${candidate.evidence ? this.renderEvidence(candidate.evidence) : ''}
                </div>
            </article>
        `;
    }

    renderEvidence(evidence) {
        if (!evidence || evidence.length === 0) return '';

        return `
            <div class="rejected-evidence ai-accent-panel">
                <h5>Evidence</h5>
                <div class="evidence-list">
                    ${evidence.map((ev) => `
                        <div class="evidence-item">
                            <span class="evidence-type">${ev.type || 'Info'}</span>
                            <span class="evidence-description">${this.formatEvidence(ev)}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    formatEvidence(ev) {
        if (typeof ev === 'string') return ev;
        if (!ev || typeof ev !== 'object') return String(ev);
        const field = ev.field || 'field';
        const value = ev.value !== undefined ? ev.value : 'n/a';
        const source = ev.source || 'unknown source';
        const notes = ev.notes ? ` (${ev.notes})` : '';
        return `${field}: ${value} from ${source}${notes}`;
    }

    formatReason(reason) {
        return reason.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
    }

    formatPrice(priceInfo) {
        const { value, unit } = priceInfo;
        if (value >= 1000) {
            return `${(value / 1000).toFixed(1)}k ${unit}`;
        }
        return `${value} ${unit}`;
    }

    attachEventListeners() {
        const expandButtons = this.container.querySelectorAll('.expand-btn');

        expandButtons.forEach((button) => {
            button.addEventListener('click', () => {
                this.toggleExpanded(button);
            });
        });
    }

    toggleExpanded(button) {
        const item = button.closest('.rejected-item');
        const details = item.querySelector('.rejected-details');
        const icon = button.querySelector('.expand-icon');
        const isExpanded = button.dataset.expanded === 'true';

        if (isExpanded) {
            details.classList.add('hidden');
            icon.textContent = '▶';
            button.dataset.expanded = 'false';
        } else {
            details.classList.remove('hidden');
            icon.textContent = '▼';
            button.dataset.expanded = 'true';
        }
    }

    expandAll() {
        const expandButtons = this.container.querySelectorAll('.expand-btn');
        expandButtons.forEach((button) => {
            if (button.dataset.expanded === 'false') {
                this.toggleExpanded(button);
            }
        });
    }

    collapseAll() {
        const expandButtons = this.container.querySelectorAll('.expand-btn');
        expandButtons.forEach((button) => {
            if (button.dataset.expanded === 'true') {
                this.toggleExpanded(button);
            }
        });
    }

    addBulkControls() {
        const header = this.container.querySelector('h3');
        if (!header) return;

        const controls = document.createElement('div');
        controls.className = 'bulk-controls';
        controls.innerHTML = `
            <button class="btn btn-sm expand-all">Expand All</button>
            <button class="btn btn-sm collapse-all">Collapse All</button>
        `;

        header.appendChild(controls);

        controls.querySelector('.expand-all').addEventListener('click', () => this.expandAll());
        controls.querySelector('.collapse-all').addEventListener('click', () => this.collapseAll());
    }
}
