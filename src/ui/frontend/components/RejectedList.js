/**
 * RejectedList Component
 * Displays materials that were rejected during scoring
 */

export class RejectedList {
    constructor(container) {
        this.container = container;
    }


    displayRejected(rejected) {
        const items = Array.isArray(rejected) ? rejected : [];
        this._allItems = items;
        this._renderList(items);
    }

    _renderList(items) {
        const hasItems = items.length > 0;
        const total = (this._allItems || items).length;
        const showing = items.length;

        this.container.innerHTML = `
        <section class="rejected-section">
            <div class="rejected-header-row">
                <h3>K.O. Filter Failed Items (${total})</h3>
                ${total > 1 ? `
                <div class="bulk-controls">
                    <button class="btn btn-sm expand-all">Expand All</button>
                    <button class="btn btn-sm collapse-all">Collapse All</button>
                </div>` : ''}
            </div>

            ${total > 5 ? `
            <div style="margin-bottom:14px;">
                <input
                    type="text"
                    class="rejected-search"
                    placeholder="Filter by name or reason…"
                    style="width:100%;background:var(--bg-surface);border:1px solid var(--border-mid);
                           border-radius:var(--radius-md);padding:9px 13px;color:var(--text-1);
                           font-size:13px;font-family:'Inter',sans-serif;outline:none;"
                >
                ${showing < total ? `<p style="font-size:12px;color:var(--text-3);margin-top:6px;">${showing} of ${total} shown</p>` : ''}
            </div>` : ''}

            ${hasItems ? `
                <div class="rejected-list">
                    ${items.map((c) => this.renderRejectedCandidate(c)).join('')}
                </div>
                <div class="rejected-summary">
                    <p>These items failed hard exclusion criteria or did not meet minimum viability constraints.</p>
                </div>
            ` : `
                <div class="rejected-empty">
                    <p>${total > 0 ? 'No items match your filter.' : 'No items failed the K.O. filter for this run.'}</p>
                </div>
            `}
        </section>
    `;

        this.attachEventListeners();

        // Search filter
        const searchInput = this.container.querySelector('.rejected-search');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                const q = e.target.value.toLowerCase().trim();
                if (!q) {
                    this._renderList(this._allItems);
                    return;
                }
                const filtered = this._allItems.filter((c) => {
                    const name = (c.candidate?.name || '').toLowerCase();
                    const id = (c.candidate?.id || '').toLowerCase();
                    const reasons = (c.reasons || []).join(' ').toLowerCase();
                    return name.includes(q) || id.includes(q) || reasons.includes(q);
                });
                this._renderList(filtered);
                // Fokus erhalten
                requestAnimationFrame(() => {
                    const newInput = this.container.querySelector('.rejected-search');
                    if (newInput) { newInput.value = e.target.value; newInput.focus(); }
                });
            });
        }

        if (items.length > 1) {
            const header = this.container.querySelector('.rejected-header-row');
            const expandAll = header?.querySelector('.expand-all');
            const collapseAll = header?.querySelector('.collapse-all');
            if (expandAll) expandAll.addEventListener('click', () => this.expandAll());
            if (collapseAll) collapseAll.addEventListener('click', () => this.collapseAll());
        }
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


}
