// Enterprise Account Manager - Main Application (API-based)
class AccountManager {
    constructor() {
        this.accounts = [];
        this.filteredAccounts = [];
        this.currentView = 'dashboard';
        this.editingAccountId = null;
        this.deleteAccountId = null;
        this.API_BASE = '/api';
        
        this.init();
    }
    
    async init() {
        this.showLoading(true);
        this.bindEvents();
        await this.loadAccounts();
        this.showLoading(false);
        this.updateDashboard();
        this.renderAllViews();
        this.populateFilters();
    }
    
    showLoading(show) {
        const loader = document.getElementById('loading-state');
        if (show) {
            loader.classList.remove('hidden');
        } else {
            loader.classList.add('hidden');
        }
    }
    
    showToast(message, type = 'info') {
        let container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        
        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            info: 'fa-info-circle'
        };
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <i class="fas ${icons[type]}"></i>
            <span>${message}</span>
        `;
        
        container.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease forwards';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
    
    async loadAccounts() {
        try {
            const response = await fetch(`${this.API_BASE}/accounts?_=${Date.now()}`);
            if (!response.ok) throw new Error('Failed to fetch accounts');
            this.accounts = await response.json();
            this.filteredAccounts = [...this.accounts];
        } catch (error) {
            console.error('Error loading accounts:', error);
            this.showToast('Failed to load accounts', 'error');
        }
    }
    
    bindEvents() {
        // Navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const view = e.currentTarget.dataset.view;
                this.switchView(view);
            });
        });
        
        // Search
        document.getElementById('search-input').addEventListener('input', (e) => {
            this.handleSearch(e.target.value);
        });
        
        // Filters
        document.getElementById('filter-rep').addEventListener('change', () => this.applyFilters());
        document.getElementById('filter-status').addEventListener('change', () => this.applyFilters());
        
        // Add Account Button
        document.getElementById('add-account-btn').addEventListener('click', () => {
            this.openEditModal();
        });
        
        // Report Button
        document.getElementById('report-btn').addEventListener('click', () => {
            this.openModal('report-format-modal');
        });
        
        // Export Button
        document.getElementById('export-btn').addEventListener('click', () => {
            this.exportData();
        });
        
        // Database Management Button
        document.getElementById('db-management-btn').addEventListener('click', () => {
            this.openModal('db-management-modal');
        });
        
        // Backup Export Button
        document.getElementById('backup-export-btn').addEventListener('click', () => {
            this.downloadBackup();
        });
        
        // Backup Restore Button
        document.getElementById('backup-restore-btn').addEventListener('click', () => {
            document.getElementById('backup-file-input').click();
        });
        
        // Backup File Input Change
        document.getElementById('backup-file-input').addEventListener('change', (e) => {
            this.handleBackupFileSelect(e);
        });
        
        // Clear Database Button
        document.getElementById('db-clear-btn').addEventListener('click', () => {
            this.closeModal('db-management-modal');
            this.openModal('clear-db-modal');
            document.getElementById('confirm-clear-input').value = '';
            document.getElementById('confirm-clear-btn').disabled = true;
        });
        
        // Confirm Clear Input
        document.getElementById('confirm-clear-input').addEventListener('input', (e) => {
            document.getElementById('confirm-clear-btn').disabled = e.target.value !== 'DELETE ALL';
        });
        
        // Confirm Clear Button
        document.getElementById('confirm-clear-btn').addEventListener('click', () => {
            this.clearDatabase();
        });
        
        // Confirm Restore Button
        document.getElementById('confirm-restore-btn').addEventListener('click', () => {
            this.confirmRestore();
        });
        
        // Modal Close Buttons
        document.getElementById('close-modal').addEventListener('click', () => {
            this.closeModal('account-modal');
        });
        
        document.getElementById('close-edit-modal').addEventListener('click', () => {
            this.closeModal('edit-modal');
        });
        
        document.getElementById('cancel-form').addEventListener('click', () => {
            this.closeModal('edit-modal');
        });
        
        // Delete Modal
        document.getElementById('close-delete-modal').addEventListener('click', () => {
            this.closeModal('delete-modal');
        });
        
        document.getElementById('cancel-delete').addEventListener('click', () => {
            this.closeModal('delete-modal');
        });
        
        document.getElementById('confirm-delete').addEventListener('click', () => {
            this.deleteAccount();
        });
        
        // Form Submit
        document.getElementById('account-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveAccount();
        });
        
        // Add Document Button
        document.getElementById('add-doc-btn').addEventListener('click', () => {
            this.addDocumentRow();
        });
        
        // Modal backdrop click
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.closeModal(modal.id);
                }
            });
        });
        
        // Stat card click handlers
        document.querySelectorAll('.stat-card.clickable').forEach(card => {
            card.addEventListener('click', () => {
                const filter = card.dataset.filter;
                this.handleStatCardClick(filter);
            });
        });
    }
    
    handleStatCardClick(filter) {
        switch(filter) {
            case 'all':
                this.switchView('accounts');
                this.applyStatusFilter('all');
                break;
            case 'active':
                this.switchView('accounts');
                this.applyStatusFilter('active');
                break;
            case 'expiring':
                this.switchView('expiring');
                break;
            case 'engineering':
                this.switchView('active-engineering');
                break;
            case 'needs-review':
                this.switchView('needs-review');
                break;
            case 'expired':
                this.switchView('accounts');
                this.applyStatusFilter('expired');
                break;
        }
    }
    
    applyStatusFilter(status) {
        if (status === 'all') {
            this.filteredAccounts = [...this.accounts];
        } else if (status === 'active') {
            this.filteredAccounts = this.accounts.filter(a => {
                const accountStatus = this.getAccountStatus(a);
                return accountStatus === 'active' || accountStatus === 'expiring';
            });
        } else if (status === 'expired') {
            this.filteredAccounts = this.accounts.filter(a => this.getAccountStatus(a) === 'expired');
        }
        this.renderAccountsGrid();
        
        // Update the status filter dropdown to match
        const statusSelect = document.getElementById('filter-status');
        if (statusSelect) {
            statusSelect.value = status === 'all' ? '' : status;
        }
    }
    
    switchView(view) {
        // Update nav
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
            if (item.dataset.view === view) {
                item.classList.add('active');
            }
        });
        
        // Update views
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        document.getElementById(`${view}-view`).classList.add('active');
        
        this.currentView = view;
        
        // Render specific view
        if (view === 'expiring') {
            this.renderExpiringView();
        } else if (view === 'active-engineering') {
            this.renderEngineeringView();
        }
    }
    
    handleSearch(query) {
        query = query.toLowerCase().trim();
        
        if (!query) {
            this.filteredAccounts = [...this.accounts];
        } else {
            this.filteredAccounts = this.accounts.filter(account => {
                return account.name.toLowerCase().includes(query) ||
                       (account.salesforceId && account.salesforceId.toLowerCase().includes(query)) ||
                       (account.salesRep && account.salesRep.toLowerCase().includes(query)) ||
                       (account.overview && account.overview.toLowerCase().includes(query));
            });
        }
        
        this.renderAccountsGrid();
    }
    
    applyFilters() {
        const repFilter = document.getElementById('filter-rep').value;
        const statusFilter = document.getElementById('filter-status').value;
        
        this.filteredAccounts = this.accounts.filter(account => {
            let matchRep = true;
            let matchStatus = true;
            
            if (repFilter) {
                matchRep = account.salesRep === repFilter;
            }
            
            if (statusFilter) {
                const status = this.getAccountStatus(account);
                matchStatus = status === statusFilter;
            }
            
            return matchRep && matchStatus;
        });
        
        this.renderAccountsGrid();
    }
    
    populateFilters() {
        const reps = [...new Set(this.accounts.map(a => a.salesRep).filter(Boolean))];
        const repSelect = document.getElementById('filter-rep');
        
        // Clear existing options except first
        repSelect.innerHTML = '<option value="">All Sales Reps</option>';
        
        reps.forEach(rep => {
            const option = document.createElement('option');
            option.value = rep;
            option.textContent = rep;
            repSelect.appendChild(option);
        });
    }
    
    getAccountStatus(account) {
        if (account.isPOC) return 'poc';
        if (!account.contractEnd) return 'poc';
        
        const endDate = new Date(account.contractEnd);
        const today = new Date();
        const daysUntilExpiry = Math.ceil((endDate - today) / (1000 * 60 * 60 * 24));
        
        if (daysUntilExpiry < 0) return 'expired';
        if (daysUntilExpiry <= 60) return 'expiring';
        return 'active';
    }
    
    getStatusLabel(status) {
        const labels = {
            'active': 'Active',
            'expiring': 'Expiring Soon',
            'expired': 'Expired',
            'poc': 'POC'
        };
        return labels[status] || 'Unknown';
    }
    
    getDaysUntilExpiry(account) {
        if (!account.contractEnd) return null;
        const endDate = new Date(account.contractEnd);
        const today = new Date();
        return Math.ceil((endDate - today) / (1000 * 60 * 60 * 24));
    }
    
    hasActiveEngineering(account) {
        return account.engineeringStatus === 'active';
    }
    
    formatDate(dateStr) {
        if (!dateStr) return 'TBD';
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    }
    
    // Dashboard
    async updateDashboard() {
        try {
            const response = await fetch(`${this.API_BASE}/stats?_=${Date.now()}`);
            const stats = await response.json();
            
            // Update sidebar stats
            document.getElementById('total-accounts').textContent = stats.total;
            document.getElementById('active-contracts').textContent = stats.active;
            
            // Update dashboard stats
            document.getElementById('dash-total').textContent = stats.total;
            document.getElementById('dash-active').textContent = stats.active;
            document.getElementById('dash-expiring').textContent = stats.expiring;
            document.getElementById('dash-engineering').textContent = stats.withEngineering;
            document.getElementById('dash-review').textContent = stats.needsReview || 0;
            document.getElementById('dash-expired').textContent = stats.expired || 0;
        } catch (error) {
            console.error('Error fetching stats:', error);
            // Fallback to local calculation
            const total = this.accounts.length;
            const active = this.accounts.filter(a => this.getAccountStatus(a) === 'active').length;
            const expiring = this.accounts.filter(a => {
                const days = this.getDaysUntilExpiry(a);
                return days !== null && days >= 0 && days <= 60;
            }).length;
            const engineering = this.accounts.filter(a => this.hasActiveEngineering(a)).length;
            const needsReview = this.accounts.filter(a => a.needsReview).length;
            const expired = this.accounts.filter(a => this.getAccountStatus(a) === 'expired').length;
            
            document.getElementById('total-accounts').textContent = total;
            document.getElementById('active-contracts').textContent = active;
            document.getElementById('dash-total').textContent = total;
            document.getElementById('dash-active').textContent = active;
            document.getElementById('dash-expiring').textContent = expiring;
            document.getElementById('dash-engineering').textContent = engineering;
            document.getElementById('dash-review').textContent = needsReview;
            document.getElementById('dash-expired').textContent = expired;
        }
        
        // Render dashboard sections
        this.renderExpiringList();
        this.renderRecentContacts();
        this.renderRepsBreakdown();
    }
    
    renderExpiringList() {
        const container = document.getElementById('expiring-list');
        const expiringAccounts = this.accounts
            .filter(a => {
                const days = this.getDaysUntilExpiry(a);
                return days !== null && days >= -30 && days <= 90;
            })
            .sort((a, b) => new Date(a.contractEnd) - new Date(b.contractEnd))
            .slice(0, 5);
        
        if (expiringAccounts.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>No contracts expiring soon</p></div>';
            return;
        }
        
        container.innerHTML = expiringAccounts.map(account => {
            const days = this.getDaysUntilExpiry(account);
            let badgeClass = 'badge-warning';
            let badgeText = `${days} days`;
            
            if (days < 0) {
                badgeClass = 'badge-danger';
                badgeText = 'Expired';
            } else if (days <= 30) {
                badgeClass = 'badge-danger';
            }
            
            return `
                <div class="account-mini-item" onclick="app.openAccountModal(${account.id})">
                    <div class="account-mini-info">
                        <h4>${account.name}</h4>
                        <span>Ends: ${this.formatDate(account.contractEnd)}</span>
                    </div>
                    <span class="account-mini-badge ${badgeClass}">${badgeText}</span>
                </div>
            `;
        }).join('');
    }
    
    renderRecentContacts() {
        const container = document.getElementById('recent-contacts-list');
        
        // First try to show accounts with recent status updates
        const accountsWithUpdates = this.accounts
            .filter(a => a.statusHistory && a.statusHistory.length > 0)
            .map(a => ({
                ...a,
                latestUpdate: a.statusHistory.reduce((latest, update) => {
                    const updateDate = new Date(update.date);
                    return updateDate > latest ? updateDate : latest;
                }, new Date(0))
            }))
            .sort((a, b) => b.latestUpdate - a.latestUpdate)
            .slice(0, 5);
        
        // If no status updates, show accounts with contact dates
        let recentContacts = accountsWithUpdates.length > 0 ? accountsWithUpdates : 
            this.accounts
                .filter(a => a.lastContactFE || a.lastContactSales)
                .sort((a, b) => {
                    const dateA = this.parseContactDate(a.lastContactFE || a.lastContactSales);
                    const dateB = this.parseContactDate(b.lastContactFE || b.lastContactSales);
                    return dateB - dateA;
                })
                .slice(0, 5);
        
        // If still empty, show most recently added accounts
        if (recentContacts.length === 0) {
            recentContacts = this.accounts
                .sort((a, b) => b.id - a.id)
                .slice(0, 5);
        }
        
        if (recentContacts.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>No accounts recorded</p></div>';
            return;
        }
        
        container.innerHTML = recentContacts.map(account => {
            let subtitle = '';
            if (account.latestUpdate) {
                subtitle = `Updated: ${account.latestUpdate.toLocaleDateString()}`;
            } else if (account.lastContactFE || account.lastContactSales) {
                subtitle = `Contact: ${account.lastContactFE || account.lastContactSales}`;
            } else {
                subtitle = account.overview ? account.overview.substring(0, 40) + (account.overview.length > 40 ? '...' : '') : 'No overview';
            }
            return `
                <div class="account-mini-item" onclick="app.openAccountModal(${account.id})">
                    <div class="account-mini-info">
                        <h4>${account.name}</h4>
                        <span>${subtitle}</span>
                    </div>
                    <span class="account-mini-badge badge-info">${account.salesRep ? account.salesRep.split(' ')[0] : 'N/A'}</span>
                </div>
            `;
        }).join('');
    }
    
    parseContactDate(dateStr) {
        if (!dateStr || dateStr === 'Weekly') return new Date();
        if (dateStr.includes('2026') || dateStr.includes('2025')) {
            return new Date(dateStr);
        }
        return new Date(0);
    }
    
    renderRepsBreakdown() {
        const container = document.getElementById('reps-breakdown');
        const reps = {};
        
        this.accounts.forEach(account => {
            const rep = account.salesRep || 'Unassigned';
            if (!reps[rep]) {
                reps[rep] = 0;
            }
            reps[rep]++;
        });
        
        container.innerHTML = Object.entries(reps)
            .sort((a, b) => b[1] - a[1])
            .map(([rep, count]) => {
                const initials = rep.split(' ').map(n => n[0]).join('');
                return `
                    <div class="rep-item clickable" onclick="app.filterByRep('${rep.replace(/'/g, "\\'")}')"> 
                        <div class="rep-info">
                            <div class="rep-avatar">${initials}</div>
                            <span>${rep}</span>
                        </div>
                        <span class="rep-count">${count} accounts</span>
                    </div>
                `;
            }).join('');
    }
    
    filterByRep(repName) {
        this.filteredAccounts = this.accounts.filter(a => a.salesRep === repName);
        this.switchView('accounts');
        this.renderAccountsGrid();
        
        // Update the rep filter dropdown if it exists
        const repSelect = document.getElementById('filter-rep');
        if (repSelect) {
            repSelect.value = repName;
        }
    }
    
    // Render All Views
    renderAllViews() {
        this.renderAccountsGrid();
        this.renderExpiringView();
        this.renderEngineeringView();
        this.renderReviewView();
    }
    
    renderAccountsGrid() {
        const container = document.getElementById('accounts-grid');
        
        if (this.filteredAccounts.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-search"></i>
                    <h3>No accounts found</h3>
                    <p>Try adjusting your search or filters</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = this.filteredAccounts.map(account => this.renderAccountCard(account)).join('');
    }
    
    renderExpiringView() {
        const container = document.getElementById('expiring-grid');
        const expiringAccounts = this.accounts.filter(a => {
            if (a.isPOC) return false; // Exclude POC accounts
            const days = this.getDaysUntilExpiry(a);
            return days !== null && days >= 0 && days <= 60;
        }).sort((a, b) => new Date(a.contractEnd) - new Date(b.contractEnd));
        
        if (expiringAccounts.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-check-circle"></i>
                    <h3>All clear!</h3>
                    <p>No contracts expiring in the next 60 days</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = expiringAccounts.map(account => this.renderAccountCard(account)).join('');
    }
    
    renderEngineeringView() {
        const container = document.getElementById('engineering-grid');
        const engineeringAccounts = this.accounts.filter(a => this.hasActiveEngineering(a));
        
        if (engineeringAccounts.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-tools"></i>
                    <h3>No active engineering efforts</h3>
                    <p>All accounts are currently stable</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = engineeringAccounts.map(account => this.renderAccountCard(account)).join('');
    }
    
    renderReviewView() {
        const container = document.getElementById('review-grid');
        const reviewAccounts = this.accounts.filter(a => a.needsReview);
        
        if (reviewAccounts.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-check-circle"></i>
                    <h3>No accounts flagged for review</h3>
                    <p>All accounts have been reviewed</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = reviewAccounts.map(account => this.renderAccountCard(account)).join('');
    }
    
    getSentimentIcon(sentiment) {
        const icons = {
            'excellent': '<i class="fas fa-circle" style="color: #22c55e;"></i>',
            'good': '<i class="fas fa-circle" style="color: #84cc16;"></i>',
            'neutral': '<i class="fas fa-circle" style="color: #fbbf24;"></i>',
            'at-risk': '<i class="fas fa-circle" style="color: #f97316;"></i>',
            'critical': '<i class="fas fa-circle" style="color: #ef4444;"></i>'
        };
        return icons[sentiment] || '<i class="fas fa-circle" style="color: #fbbf24;"></i>';
    }
    
    getEngineeringStatusBadge(status) {
        const statuses = {
            'none': { label: 'Not Active', class: 'eng-none', icon: 'fa-stop' },
            'active': { label: 'Eng', class: 'eng-active', icon: 'fa-play' }
        };
        const s = statuses[status] || statuses.none;
        return `<span class="eng-status-badge ${s.class}"><i class="fas ${s.icon}"></i> ${s.label}</span>`;
    }
    
    renderAccountCard(account) {
        const status = this.getAccountStatus(account);
        const statusLabel = this.getStatusLabel(status);
        const links = account.links || {};
        const sentiment = account.sentiment || 'neutral';
        const engStatus = account.engineeringStatus || 'none';
        
        return `
            <div class="account-card" onclick="app.openAccountModal(${account.id})">
                <div class="account-card-header">
                    <div class="account-card-title">
                        <h3>${account.name}</h3>
                        <p>${account.overview || 'No overview available'}</p>
                    </div>
                    <div class="account-badges">
                        <span class="sentiment-badge sentiment-${sentiment}" title="Customer Sentiment: ${sentiment}">${this.getSentimentIcon(sentiment)}</span>
                        <span class="account-status status-${status}">${statusLabel}</span>
                    </div>
                </div>
                <div class="account-card-body">
                    <div class="account-details">
                        <div class="detail-item">
                            <span class="detail-label">Contract Start</span>
                            <span class="detail-value">${this.formatDate(account.contractStart)}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Contract End</span>
                            <span class="detail-value">
                                ${this.formatDate(account.contractEnd)}
                                ${account.contractNeedsVerification ? '<span class="needs-verification"><i class="fas fa-exclamation-circle"></i> Verify</span>' : ''}
                            </span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Salesforce ID</span>
                            <span class="detail-value" style="font-size: 0.8rem;">${account.salesforceId || 'N/A'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Last Contact (FE)</span>
                            <span class="detail-value">${account.lastContactFE || 'Not recorded'}</span>
                        </div>
                    </div>
                </div>
                <div class="account-card-footer">
                    <div class="account-links">
                        <a href="${links.contract || '#'}" class="link-icon ${links.contract ? 'has-link' : ''}" title="Contract" onclick="event.stopPropagation()">
                            <i class="fas fa-file-contract"></i>
                        </a>
                        <a href="${links.slack || '#'}" class="link-icon ${links.slack ? 'has-link' : ''}" title="Slack" onclick="event.stopPropagation()">
                            <i class="fab fa-slack"></i>
                        </a>
                        <a href="${links.gdrive || '#'}" class="link-icon ${links.gdrive ? 'has-link' : ''}" title="Google Drive" onclick="event.stopPropagation()">
                            <i class="fab fa-google-drive"></i>
                        </a>
                        <a href="${links.clarifaiOrg || '#'}" class="link-icon ${links.clarifaiOrg ? 'has-link' : ''}" title="Clarifai Org" onclick="event.stopPropagation()">
                            <i class="fas fa-external-link-alt"></i>
                        </a>
                    </div>
                    <div class="account-rep">
                        ${account.needsReview ? '<span class="review-flag" title="Flagged for Review"><i class="fas fa-flag"></i></span>' : ''}
                        ${engStatus !== 'none' ? this.getEngineeringStatusBadge(engStatus) : ''}
                        <i class="fas fa-user"></i>
                        ${account.salesRep || 'Unassigned'}
                    </div>
                </div>
            </div>
        `;
    }
    
    // Modal Functions
    async openAccountModal(accountId) {
        const account = this.accounts.find(a => a.id === accountId);
        if (!account) return;
        
        const modal = document.getElementById('account-modal');
        const title = document.getElementById('modal-title');
        const body = document.getElementById('modal-body');
        
        title.textContent = account.name;
        
        const links = account.links || {};
        const allLinks = [];
        
        if (links.contract) allLinks.push({ name: 'Contract', url: links.contract, icon: 'fa-file-contract' });
        if (links.billing) allLinks.push({ name: 'Billing Details', url: links.billing, icon: 'fa-credit-card' });
        if (links.slack) allLinks.push({ name: 'Slack Channel', url: links.slack, icon: 'fab fa-slack' });
        if (links.slackExternal) allLinks.push({ name: 'External Slack', url: links.slackExternal, icon: 'fab fa-slack' });
        if (links.gdrive) allLinks.push({ name: 'Google Drive', url: links.gdrive, icon: 'fab fa-google-drive' });
        if (links.fieldEng) allLinks.push({ name: 'Field Engineering Doc', url: links.fieldEng, icon: 'fa-file-alt' });
        if (links.sales) allLinks.push({ name: 'Sales Doc', url: links.sales, icon: 'fa-handshake' });
        if (links.clarifaiOrg) allLinks.push({ name: 'Clarifai Organization', url: links.clarifaiOrg, icon: 'fa-external-link-alt' });
        if (links.jira) allLinks.push({ name: 'Jira', url: links.jira, icon: 'fab fa-jira' });
        
        if (links.additionalDocs) {
            links.additionalDocs.forEach(doc => {
                allLinks.push({ name: doc.name, url: doc.url, icon: 'fa-file' });
            });
        }
        
        // Fetch status history
        let statusHistory = [];
        try {
            const response = await fetch(`${this.API_BASE}/accounts/${accountId}/status-history`);
            if (response.ok) {
                statusHistory = await response.json();
            }
        } catch (error) {
            console.error('Error fetching status history:', error);
        }
        
        body.innerHTML = `
            <div class="modal-section">
                <h3><i class="fas fa-info-circle"></i> Overview</h3>
                <p>${account.overview || 'No overview available'}</p>
            </div>
            
            <div class="modal-section">
                <h3><i class="fas fa-calendar"></i> Contract Details</h3>
                <div class="modal-details-grid">
                    <div class="modal-detail-item">
                        <span class="modal-detail-label">Salesforce ID</span>
                        <span class="modal-detail-value">${account.salesforceId || 'N/A'}</span>
                    </div>
                    <div class="modal-detail-item">
                        <span class="modal-detail-label">Sales Representative</span>
                        <span class="modal-detail-value">${account.salesRep || 'Unassigned'}</span>
                    </div>
                    <div class="modal-detail-item">
                        <span class="modal-detail-label">Contract Start</span>
                        <span class="modal-detail-value">${this.formatDate(account.contractStart)}</span>
                    </div>
                    <div class="modal-detail-item">
                        <span class="modal-detail-label">Contract End</span>
                        <span class="modal-detail-value">
                            ${this.formatDate(account.contractEnd)}
                            ${account.contractNeedsVerification ? '<span class="needs-verification"><i class="fas fa-exclamation-circle"></i> Needs Verification</span>' : ''}
                        </span>
                    </div>
                    <div class="modal-detail-item">
                        <span class="modal-detail-label">Last Contact (Field Engineering)</span>
                        <span class="modal-detail-value">${account.lastContactFE || 'Not recorded'}</span>
                    </div>
                    <div class="modal-detail-item">
                        <span class="modal-detail-label">Last Contact (Sales)</span>
                        <span class="modal-detail-value">${account.lastContactSales || 'Not recorded'}</span>
                    </div>
                </div>
            </div>
            
            ${account.cseNotes ? `
            <div class="modal-section">
                <h3><i class="fas fa-sticky-note"></i> CSE Notes</h3>
                <div class="cse-notes-box">
                    <p>${account.cseNotes}</p>
                </div>
            </div>
            ` : ''}
            
            ${account.needsReview ? `
            <div class="modal-section">
                <div class="review-alert">
                    <i class="fas fa-flag"></i>
                    <span>This account has been flagged for accuracy review</span>
                </div>
            </div>
            ` : ''}
            
            <div class="modal-section">
                <h3><i class="fas fa-wrench"></i> Engineering Work Status</h3>
                <div class="engineering-status-controls">
                    <div class="current-eng-status">
                        ${this.getEngineeringStatusBadge(account.engineeringStatus || 'none')}
                    </div>
                    <div class="eng-status-buttons">
                        ${account.engineeringStatus === 'active' ? `
                            <button class="eng-btn eng-stop" onclick="app.updateEngineeringStatus(${accountId}, 'none')">
                                <i class="fas fa-stop"></i> Stop Engineering
                            </button>
                        ` : `
                            <button class="eng-btn eng-start" onclick="app.updateEngineeringStatus(${accountId}, 'active')">
                                <i class="fas fa-play"></i> Start Engineering
                            </button>
                        `}
                    </div>
                </div>
                ${account.engineeringEfforts && account.engineeringEfforts !== 'None' ? `
                    <div class="engineering-efforts-text">
                        <strong>Current Efforts:</strong> ${account.engineeringEfforts}
                    </div>
                ` : ''}
            </div>
            
            <div class="modal-section">
                <h3><i class="fas fa-history"></i> Engineering Status History</h3>
                <div class="status-add-form">
                    <div class="status-form-row">
                        <input type="date" id="new-status-date" value="${new Date().toISOString().split('T')[0]}" class="status-date-input">
                        <input type="text" id="new-status-text" placeholder="Enter new status update..." class="status-text-input">
                        <button class="btn btn-primary btn-small" onclick="app.addStatusUpdate(${accountId})">
                            <i class="fas fa-plus"></i> Add
                        </button>
                    </div>
                </div>
                <div class="status-history-list" id="status-history-list">
                    ${statusHistory.length > 0 ? statusHistory.map((status, index) => `
                        <div class="status-item ${index === 0 ? 'status-latest' : ''}">
                            <div class="status-date">
                                <i class="fas fa-calendar-alt"></i>
                                ${this.formatDate(status.statusDate)}
                                ${index === 0 ? '<span class="status-badge-latest">Latest</span>' : ''}
                            </div>
                            <div class="status-text">${status.statusText}</div>
                            <button class="btn-icon btn-delete-status" onclick="app.deleteStatusUpdate(${status.id}, ${accountId})" title="Delete">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    `).join('') : '<p class="no-status">No status updates recorded. Add a new status above.</p>'}
                </div>
            </div>
            
            <div class="modal-section">
                <h3><i class="fas fa-link"></i> Links & Documents</h3>
                ${allLinks.length > 0 ? `
                    <div class="modal-links-list">
                        ${allLinks.map(link => `
                            <a href="${link.url}" target="_blank" class="modal-link">
                                <i class="${link.icon.startsWith('fab') ? link.icon : 'fas ' + link.icon}"></i>
                                <span>${link.name}</span>
                                <i class="fas fa-external-link-alt external-icon"></i>
                            </a>
                        `).join('')}
                    </div>
                ` : '<p style="color: var(--text-secondary);">No links available for this account</p>'}
            </div>
            
            <div class="form-actions" style="border-top: none; padding-top: 0;">
                <button class="btn btn-danger" onclick="app.confirmDelete(${account.id})">
                    <i class="fas fa-trash"></i> Delete
                </button>
                <button class="btn btn-secondary" onclick="app.openEditModal(${account.id})">
                    <i class="fas fa-edit"></i> Edit Account
                </button>
            </div>
        `;
        
        modal.classList.add('active');
    }
    
    openEditModal(accountId = null) {
        this.editingAccountId = accountId;
        const modal = document.getElementById('edit-modal');
        const title = document.getElementById('edit-modal-title');
        const form = document.getElementById('account-form');
        
        // Clear additional docs container
        document.getElementById('additional-docs-container').innerHTML = '';
        
        if (accountId) {
            const account = this.accounts.find(a => a.id === accountId);
            if (!account) return;
            
            title.textContent = 'Edit Account';
            
            // Populate form
            document.getElementById('account-name').value = account.name || '';
            document.getElementById('salesforce-id').value = account.salesforceId || '';
            document.getElementById('overview').value = account.overview || '';
            document.getElementById('contract-start').value = account.contractStart || '';
            document.getElementById('contract-end').value = account.contractEnd || '';
            document.getElementById('sales-rep').value = account.salesRep || '';
            document.getElementById('last-contact-fe').value = account.lastContactFE || '';
            document.getElementById('last-contact-sales').value = account.lastContactSales || '';
            document.getElementById('is-poc').checked = account.isPOC || false;
            document.getElementById('needs-review').checked = account.needsReview || false;
            document.getElementById('sentiment').value = account.sentiment || 'neutral';
            document.getElementById('engineering-efforts').value = account.engineeringEfforts || '';
            document.getElementById('engineering-status').value = account.engineeringStatus || 'none';
            document.getElementById('cse-notes').value = account.cseNotes || '';
            
            const links = account.links || {};
            document.getElementById('contract-link').value = links.contract || '';
            document.getElementById('billing-link').value = links.billing || '';
            document.getElementById('slack-link').value = links.slack || '';
            document.getElementById('gdrive-link').value = links.gdrive || '';
            document.getElementById('field-eng-link').value = links.fieldEng || '';
            document.getElementById('sales-link').value = links.sales || '';
            document.getElementById('clarifai-org').value = links.clarifaiOrg || '';
            document.getElementById('jira-link').value = links.jira || '';
            
            // Add additional docs
            if (links.additionalDocs) {
                links.additionalDocs.forEach(doc => {
                    this.addDocumentRow(doc.name, doc.url);
                });
            }
        } else {
            title.textContent = 'Add New Account';
            form.reset();
        }
        
        // Close detail modal if open
        this.closeModal('account-modal');
        modal.classList.add('active');
    }
    
    addDocumentRow(name = '', url = '') {
        const container = document.getElementById('additional-docs-container');
        const row = document.createElement('div');
        row.className = 'additional-doc-row';
        row.innerHTML = `
            <input type="text" placeholder="Document Name" value="${name}">
            <input type="url" placeholder="URL" value="${url}">
            <button type="button" class="remove-doc-btn" onclick="this.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        `;
        container.appendChild(row);
    }
    
    async saveAccount() {
        const formData = {
            name: document.getElementById('account-name').value,
            salesforceId: document.getElementById('salesforce-id').value,
            overview: document.getElementById('overview').value,
            contractStart: document.getElementById('contract-start').value || null,
            contractEnd: document.getElementById('contract-end').value || null,
            salesRep: document.getElementById('sales-rep').value,
            lastContactFE: document.getElementById('last-contact-fe').value || null,
            lastContactSales: document.getElementById('last-contact-sales').value || null,
            isPOC: document.getElementById('is-poc').checked,
            needsReview: document.getElementById('needs-review').checked,
            sentiment: document.getElementById('sentiment').value || 'neutral',
            engineeringEfforts: document.getElementById('engineering-efforts').value || 'None',
            engineeringStatus: document.getElementById('engineering-status').value || 'none',
            cseNotes: document.getElementById('cse-notes').value || null,
            links: {
                contract: document.getElementById('contract-link').value || null,
                billing: document.getElementById('billing-link').value || null,
                slack: document.getElementById('slack-link').value || null,
                gdrive: document.getElementById('gdrive-link').value || null,
                fieldEng: document.getElementById('field-eng-link').value || null,
                sales: document.getElementById('sales-link').value || null,
                clarifaiOrg: document.getElementById('clarifai-org').value || null,
                jira: document.getElementById('jira-link').value || null,
                additionalDocs: []
            }
        };
        
        // Collect additional docs
        const docRows = document.querySelectorAll('.additional-doc-row');
        docRows.forEach(row => {
            const inputs = row.querySelectorAll('input');
            if (inputs[0].value && inputs[1].value) {
                formData.links.additionalDocs.push({
                    name: inputs[0].value,
                    url: inputs[1].value
                });
            }
        });
        
        try {
            let response;
            if (this.editingAccountId) {
                response = await fetch(`${this.API_BASE}/accounts/${this.editingAccountId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(formData)
                });
            } else {
                response = await fetch(`${this.API_BASE}/accounts`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(formData)
                });
            }
            
            if (!response.ok) throw new Error('Failed to save account');
            
            await this.loadAccounts();
            this.updateDashboard();
            this.renderAllViews();
            this.populateFilters();
            this.closeModal('edit-modal');
            
            this.showToast(this.editingAccountId ? 'Account updated successfully' : 'Account created successfully', 'success');
        } catch (error) {
            console.error('Error saving account:', error);
            this.showToast('Failed to save account', 'error');
        }
    }
    
    confirmDelete(accountId) {
        this.deleteAccountId = accountId;
        this.closeModal('account-modal');
        document.getElementById('delete-modal').classList.add('active');
    }
    
    async deleteAccount() {
        if (!this.deleteAccountId) return;
        
        try {
            const response = await fetch(`${this.API_BASE}/accounts/${this.deleteAccountId}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) throw new Error('Failed to delete account');
            
            await this.loadAccounts();
            this.updateDashboard();
            this.renderAllViews();
            this.populateFilters();
            this.closeModal('delete-modal');
            
            this.showToast('Account deleted successfully', 'success');
        } catch (error) {
            console.error('Error deleting account:', error);
            this.showToast('Failed to delete account', 'error');
        }
        
        this.deleteAccountId = null;
    }
    
    async updateEngineeringStatus(accountId, status) {
        try {
            const response = await fetch(`${this.API_BASE}/accounts/${accountId}/engineering-status`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status })
            });
            
            if (!response.ok) throw new Error('Failed to update engineering status');
            
            // Update local data
            const account = this.accounts.find(a => a.id === accountId);
            if (account) {
                account.engineeringStatus = status;
            }
            
            // Refresh the modal
            await this.openAccountModal(accountId);
            this.renderAllViews();
            this.updateDashboard();
            
            this.showToast('Engineering status updated', 'success');
        } catch (error) {
            console.error('Error updating engineering status:', error);
            this.showToast('Failed to update engineering status', 'error');
        }
    }
    
    async addStatusUpdate(accountId) {
        const dateInput = document.getElementById('new-status-date');
        const textInput = document.getElementById('new-status-text');
        
        const statusDate = dateInput.value;
        const statusText = textInput.value.trim();
        
        if (!statusText) {
            this.showToast('Please enter a status update', 'error');
            return;
        }
        
        try {
            const response = await fetch(`${this.API_BASE}/accounts/${accountId}/status-history`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ statusText, statusDate })
            });
            
            if (!response.ok) throw new Error('Failed to add status update');
            
            // Reload the account data and refresh modal
            await this.loadAccounts();
            this.renderAllViews();
            this.showToast('Status update added successfully', 'success');
            
            // Refresh the modal to show new status
            await this.openAccountModal(accountId);
        } catch (error) {
            console.error('Error adding status update:', error);
            this.showToast('Failed to add status update', 'error');
        }
    }
    
    async deleteStatusUpdate(statusId, accountId) {
        if (!confirm('Are you sure you want to delete this status update?')) {
            return;
        }
        
        try {
            const response = await fetch(`${this.API_BASE}/status-history/${statusId}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) throw new Error('Failed to delete status update');
            
            // Reload the account data and refresh modal
            await this.loadAccounts();
            this.renderAllViews();
            this.showToast('Status update deleted', 'success');
            
            // Refresh the modal to show updated list
            await this.openAccountModal(accountId);
        } catch (error) {
            console.error('Error deleting status update:', error);
            this.showToast('Failed to delete status update', 'error');
        }
    }
    
    openModal(modalId) {
        document.getElementById(modalId).classList.add('active');
    }
    
    closeModal(modalId) {
        document.getElementById(modalId).classList.remove('active');
    }
    
    async exportData() {
        try {
            const response = await fetch(`${this.API_BASE}/accounts`);
            const data = await response.json();
            
            const dataStr = JSON.stringify(data, null, 2);
            const blob = new Blob([dataStr], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `enterprise_accounts_${new Date().toISOString().split('T')[0]}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            this.showToast('Data exported successfully', 'success');
        } catch (error) {
            console.error('Error exporting data:', error);
            this.showToast('Failed to export data', 'error');
        }
    }
    
    generateReport(format = 'html') {
        this.closeModal('report-format-modal');
        
        if (format === 'markdown') {
            // Download markdown file
            window.location.href = `${this.API_BASE}/report?format=markdown`;
            this.showToast('Markdown report downloaded', 'success');
        } else {
            // Open HTML report in new tab
            window.open(`${this.API_BASE}/report`, '_blank');
            this.showToast('Report generated - use Print to save as PDF', 'success');
        }
    }
    
    async downloadBackup() {
        try {
            this.showToast('Creating backup...', 'info');
            const response = await fetch(`${this.API_BASE}/backup`);
            
            if (!response.ok) {
                throw new Error('Backup failed');
            }
            
            const data = await response.json();
            const dataStr = JSON.stringify(data, null, 2);
            const blob = new Blob([dataStr], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            
            const now = new Date();
            const dateStr = now.toISOString().replace(/[:.]/g, '-').slice(0, 19);
            const filename = `account-manager-backup-${dateStr}.json`;
            
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            this.showToast('Backup downloaded successfully', 'success');
        } catch (error) {
            console.error('Error creating backup:', error);
            this.showToast('Failed to create backup', 'error');
        }
    }
    
    handleBackupFileSelect(event) {
        const file = event.target.files[0];
        if (!file) return;
        
        document.getElementById('selected-file-name').textContent = file.name;
        
        const reader = new FileReader();
        reader.onload = async (e) => {
            try {
                const backup = JSON.parse(e.target.result);
                
                if (!backup.data || !backup.data.accounts) {
                    this.showToast('Invalid backup file format', 'error');
                    return;
                }
                
                // Store backup for later use
                this.pendingRestore = backup;
                
                // Populate and show the confirmation modal
                const summaryEl = document.getElementById('restore-summary');
                summaryEl.innerHTML = `
                    <li><strong>${backup.data.accounts.length}</strong> accounts (with overviews, links, and all fields)</li>
                    <li><strong>${backup.data.links ? backup.data.links.length : 0}</strong> document links</li>
                    <li><strong>${backup.data.statusUpdates ? backup.data.statusUpdates.length : 0}</strong> status history updates</li>
                `;
                
                document.getElementById('restore-date').textContent = 
                    `Backup created: ${new Date(backup.exportDate).toLocaleString()}`;
                
                this.closeModal('db-management-modal');
                this.openModal('restore-confirm-modal');
                
            } catch (error) {
                console.error('Error reading backup file:', error);
                this.showToast('Failed to read backup file', 'error');
            }
        };
        reader.readAsText(file);
    }
    
    cancelRestore() {
        this.pendingRestore = null;
        document.getElementById('backup-file-input').value = '';
        document.getElementById('selected-file-name').textContent = '';
        this.closeModal('restore-confirm-modal');
    }
    
    async confirmRestore() {
        if (!this.pendingRestore) return;
        
        this.closeModal('restore-confirm-modal');
        await this.restoreBackup(this.pendingRestore);
        this.pendingRestore = null;
    }
    
    async restoreBackup(backup) {
        try {
            this.showToast('Restoring backup...', 'info');
            
            const response = await fetch(`${this.API_BASE}/restore`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(backup)
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Restore failed');
            }
            
            const result = await response.json();
            
            this.closeModal('db-management-modal');
            document.getElementById('backup-file-input').value = '';
            document.getElementById('selected-file-name').textContent = '';
            
            await this.loadAccounts();
            
            this.showToast(
                `Restored ${result.accounts} accounts, ${result.links} links, ${result.statusUpdates} status updates`,
                'success'
            );
        } catch (error) {
            console.error('Error restoring backup:', error);
            this.showToast('Failed to restore backup: ' + error.message, 'error');
        }
    }
    
    async clearDatabase() {
        try {
            this.showToast('Clearing database...', 'info');
            
            const response = await fetch(`${this.API_BASE}/database`, {
                method: 'DELETE'
            });
            
            if (!response.ok) {
                throw new Error('Failed to clear database');
            }
            
            this.closeModal('clear-db-modal');
            document.getElementById('confirm-clear-input').value = '';
            
            await this.loadAccounts();
            
            this.showToast('Database cleared successfully', 'success');
        } catch (error) {
            console.error('Error clearing database:', error);
            this.showToast('Failed to clear database', 'error');
        }
    }
}

// Initialize the application
const app = new AccountManager();
