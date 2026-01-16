// Report Generator - Creates professional HTML reports
function generateReport(accounts) {
    const today = new Date().toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
    });
    
    // Sort accounts by name
    const sortedAccounts = [...accounts].sort((a, b) => a.name.localeCompare(b.name));
    
    // Group by sales rep
    const byRep = {};
    sortedAccounts.forEach(acc => {
        const rep = acc.salesRep || 'Unassigned';
        if (!byRep[rep]) byRep[rep] = [];
        byRep[rep].push(acc);
    });
    
    // Calculate stats
    const stats = {
        total: accounts.length,
        active: accounts.filter(a => getStatus(a) === 'active').length,
        expiring: accounts.filter(a => getStatus(a) === 'expiring').length,
        expired: accounts.filter(a => getStatus(a) === 'expired').length,
        poc: accounts.filter(a => getStatus(a) === 'poc').length,
        withEngineering: accounts.filter(a => hasActiveEngineering(a) || a.latestStatus).length
    };
    
    function getStatus(account) {
        if (account.isPOC) return 'poc';
        if (!account.contractEnd) return 'poc';
        const endDate = new Date(account.contractEnd);
        const today = new Date();
        const days = Math.ceil((endDate - today) / (1000 * 60 * 60 * 24));
        if (days < 0) return 'expired';
        if (days <= 60) return 'expiring';
        return 'active';
    }
    
    function hasActiveEngineering(account) {
        return account.engineeringEfforts && 
               account.engineeringEfforts.toLowerCase() !== 'none' &&
               !account.engineeringEfforts.toLowerCase().startsWith('none');
    }
    
    function formatDate(dateStr) {
        if (!dateStr) return 'TBD';
        return new Date(dateStr).toLocaleDateString('en-US', { 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric' 
        });
    }
    
    function getStatusBadge(status) {
        const colors = {
            active: '#22c55e',
            expiring: '#f59e0b',
            expired: '#ef4444',
            poc: '#8b5cf6'
        };
        const labels = {
            active: 'Active',
            expiring: 'Expiring Soon',
            expired: 'Expired',
            poc: 'POC'
        };
        return `<span style="background: ${colors[status]}; color: white; padding: 4px 12px; border-radius: 12px; font-size: 11px; font-weight: 600;">${labels[status]}</span>`;
    }
    
    function getSentimentBadge(sentiment) {
        const sentiments = {
            excellent: { dotColor: '#22c55e', label: 'Excellent' },
            good: { dotColor: '#84cc16', label: 'Good' },
            neutral: { dotColor: '#fbbf24', label: 'Neutral' },
            'at-risk': { dotColor: '#f97316', label: 'At Risk' },
            critical: { dotColor: '#ef4444', label: 'Critical' }
        };
        const s = sentiments[sentiment] || sentiments.neutral;
        return `<span style="background: rgba(0,0,0,0.05); padding: 4px 10px; border-radius: 10px; font-size: 10px; font-weight: 500; margin-left: 8px; display: inline-flex; align-items: center; gap: 5px;"><span style="width: 8px; height: 8px; border-radius: 50%; background: ${s.dotColor}; display: inline-block;"></span> ${s.label}</span>`;
    }
    
    function renderLinks(links) {
        if (!links) return '<p style="color: #64748b; font-style: italic;">No links available</p>';
        
        const linkItems = [];
        const linkLabels = {
            contract: 'Contract',
            billing: 'Billing Details',
            slack: 'Slack Channel',
            slackExternal: 'External Slack',
            gdrive: 'Google Drive',
            fieldEng: 'Field Engineering Doc',
            sales: 'Sales Doc',
            clarifaiOrg: 'Clarifai Organization',
            jira: 'Jira'
        };
        
        Object.entries(linkLabels).forEach(([key, label]) => {
            if (links[key] && links[key] !== '#') {
                linkItems.push(`<li><a href="${links[key]}" style="color: #4f46e5;">${label}</a></li>`);
            }
        });
        
        if (links.additionalDocs && links.additionalDocs.length > 0) {
            links.additionalDocs.forEach(doc => {
                if (doc.url && doc.url !== '#') {
                    linkItems.push(`<li><a href="${doc.url}" style="color: #4f46e5;">${doc.name}</a></li>`);
                }
            });
        }
        
        if (linkItems.length === 0) {
            return '<p style="color: #64748b; font-style: italic;">No links available</p>';
        }
        
        return `<ul style="margin: 0; padding-left: 20px; line-height: 1.8;">${linkItems.join('')}</ul>`;
    }
    
    // Generate the HTML report
    const html = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enterprise Account Report - ${today}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            line-height: 1.6;
            color: #1e293b;
            background: #fff;
        }
        
        .report-container {
            max-width: 1100px;
            margin: 0 auto;
            padding: 40px 60px;
        }
        
        @media print {
            .report-container {
                max-width: 100%;
                padding: 20px 40px;
            }
        }
        
        /* Cover Page */
        .cover-page {
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            text-align: center;
            page-break-after: always;
            border-bottom: 3px solid #4f46e5;
            padding-bottom: 60px;
            margin-bottom: 40px;
        }
        
        .cover-page h1 {
            font-size: 36px;
            font-weight: 700;
            color: #1e293b;
            margin-bottom: 10px;
        }
        
        .cover-page .subtitle {
            font-size: 18px;
            color: #64748b;
            margin-bottom: 40px;
        }
        
        .cover-page .date {
            font-size: 14px;
            color: #94a3b8;
        }
        
        .cover-page .logo {
            font-size: 48px;
            margin-bottom: 30px;
        }
        
        /* Stats Summary */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin: 40px 0;
        }
        
        .stat-box {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
        }
        
        .stat-box .number {
            font-size: 32px;
            font-weight: 700;
            color: #4f46e5;
        }
        
        .stat-box .label {
            font-size: 12px;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        /* Table of Contents */
        .toc {
            page-break-after: always;
            margin-bottom: 40px;
        }
        
        .toc h2 {
            font-size: 24px;
            font-weight: 700;
            color: #1e293b;
            border-bottom: 2px solid #4f46e5;
            padding-bottom: 10px;
            margin-bottom: 30px;
        }
        
        .toc-section {
            margin-bottom: 30px;
        }
        
        .toc-section h3 {
            font-size: 14px;
            font-weight: 600;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 15px;
        }
        
        .toc-list {
            list-style: none;
        }
        
        .toc-list li {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px dotted #e2e8f0;
        }
        
        .toc-list li a {
            color: #1e293b;
            text-decoration: none;
        }
        
        .toc-list li a:hover {
            color: #4f46e5;
        }
        
        .toc-list .page-num {
            color: #64748b;
            font-size: 12px;
        }
        
        /* Account Sections */
        .account-section {
            page-break-inside: avoid;
            margin-bottom: 40px;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            overflow: hidden;
        }
        
        .account-header {
            background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%);
            color: white;
            padding: 20px 25px;
        }
        
        .account-header h3 {
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 5px;
        }
        
        .account-header .overview {
            font-size: 14px;
            opacity: 0.9;
        }
        
        .account-body {
            padding: 25px;
        }
        
        .account-meta {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 1px solid #e2e8f0;
        }
        
        .account-meta .salesforce-id {
            font-family: monospace;
            font-size: 12px;
            color: #64748b;
            background: #f1f5f9;
            padding: 4px 8px;
            border-radius: 4px;
        }
        
        .detail-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .detail-item {
            display: flex;
            flex-direction: column;
        }
        
        .detail-item .label {
            font-size: 11px;
            font-weight: 600;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
        }
        
        .detail-item .value {
            font-size: 14px;
            color: #1e293b;
        }
        
        .detail-item.full-width {
            grid-column: span 2;
        }
        
        .engineering-box {
            background: #fef3c7;
            border-left: 4px solid #f59e0b;
            padding: 15px;
            margin: 20px 0;
            border-radius: 0 8px 8px 0;
        }
        
        .engineering-box h4 {
            font-size: 12px;
            font-weight: 600;
            color: #92400e;
            text-transform: uppercase;
            margin-bottom: 8px;
        }
        
        .engineering-box p {
            font-size: 14px;
            color: #78350f;
        }
        
        .links-section h4 {
            font-size: 12px;
            font-weight: 600;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 10px;
        }
        
        /* Rep Section Header */
        .rep-section {
            margin-top: 50px;
            page-break-before: always;
        }
        
        .rep-header {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 30px;
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .rep-avatar {
            width: 50px;
            height: 50px;
            background: #4f46e5;
            color: white;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 18px;
        }
        
        .rep-info h2 {
            font-size: 20px;
            font-weight: 600;
            color: #1e293b;
        }
        
        .rep-info span {
            font-size: 14px;
            color: #64748b;
        }
        
        /* Footer */
        .report-footer {
            margin-top: 60px;
            padding-top: 20px;
            border-top: 1px solid #e2e8f0;
            text-align: center;
            color: #94a3b8;
            font-size: 12px;
        }
        
        /* Print Styles */
        @media print {
            body {
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }
            
            .report-container {
                padding: 20px;
            }
            
            .account-section {
                page-break-inside: avoid;
            }
            
            .rep-section {
                page-break-before: always;
            }
            
            a {
                text-decoration: none;
            }
            
            .no-print {
                display: none;
            }
        }
        
        /* Print Button */
        .print-button {
            position: fixed;
            top: 20px;
            right: 20px;
            background: #4f46e5;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
            box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3);
            z-index: 1000;
        }
        
        .print-button:hover {
            background: #4338ca;
        }
    </style>
</head>
<body>
    <button class="print-button no-print" onclick="window.print()">
        🖨️ Print / Save as PDF
    </button>
    
    <div class="report-container">
        <!-- Cover Page -->
        <div class="cover-page">
            <div class="logo">🏢</div>
            <h1>Enterprise Account Overview</h1>
            <p class="subtitle">Comprehensive Report of All Active Enterprise Accounts</p>
            <p class="date">Generated on ${today}</p>
            
            <div class="stats-grid">
                <div class="stat-box">
                    <div class="number">${stats.total}</div>
                    <div class="label">Total Accounts</div>
                </div>
                <div class="stat-box">
                    <div class="number">${stats.active}</div>
                    <div class="label">Active Contracts</div>
                </div>
                <div class="stat-box">
                    <div class="number">${stats.expiring}</div>
                    <div class="label">Expiring Soon</div>
                </div>
                <div class="stat-box">
                    <div class="number">${stats.expired}</div>
                    <div class="label">Expired</div>
                </div>
                <div class="stat-box">
                    <div class="number">${stats.poc}</div>
                    <div class="label">POC</div>
                </div>
                <div class="stat-box">
                    <div class="number">${stats.withEngineering}</div>
                    <div class="label">Active Engineering</div>
                </div>
            </div>
        </div>
        
        <!-- Table of Contents -->
        <div class="toc">
            <h2>Table of Contents</h2>
            
            <div class="toc-section">
                <h3>Accounts by Sales Representative</h3>
                <ul class="toc-list">
                    ${Object.entries(byRep).map(([rep, accs]) => `
                        <li>
                            <a href="#rep-${rep.replace(/\s+/g, '-').toLowerCase()}">${rep}</a>
                            <span class="page-num">${accs.length} account${accs.length !== 1 ? 's' : ''}</span>
                        </li>
                    `).join('')}
                </ul>
            </div>
            
            <div class="toc-section">
                <h3>All Accounts (Alphabetical)</h3>
                <ul class="toc-list">
                    ${sortedAccounts.map(acc => `
                        <li>
                            <a href="#account-${acc.id}">${acc.name}</a>
                            <span class="page-num">${getStatus(acc) === 'poc' ? 'POC' : formatDate(acc.contractEnd)}</span>
                        </li>
                    `).join('')}
                </ul>
            </div>
        </div>
        
        <!-- Account Details by Rep -->
        ${Object.entries(byRep).map(([rep, accs]) => `
            <div class="rep-section" id="rep-${rep.replace(/\s+/g, '-').toLowerCase()}">
                <div class="rep-header">
                    <div class="rep-avatar">${rep.split(' ').map(n => n[0]).join('')}</div>
                    <div class="rep-info">
                        <h2>${rep}</h2>
                        <span>${accs.length} Account${accs.length !== 1 ? 's' : ''}</span>
                    </div>
                </div>
                
                ${accs.map(account => `
                    <div class="account-section" id="account-${account.id}">
                        <div class="account-header">
                            <h3>${account.name}</h3>
                            <p class="overview">${account.overview || 'No overview available'}</p>
                        </div>
                        <div class="account-body">
                            <div class="account-meta">
                                <span class="salesforce-id">SF ID: ${account.salesforceId || 'N/A'}</span>
                                ${getStatusBadge(getStatus(account))}
                                ${getSentimentBadge(account.sentiment || 'neutral')}
                            </div>
                            
                            <div class="detail-grid">
                                <div class="detail-item">
                                    <span class="label">Contract Start Date</span>
                                    <span class="value">${formatDate(account.contractStart)}</span>
                                </div>
                                <div class="detail-item">
                                    <span class="label">Contract End Date</span>
                                    <span class="value">${formatDate(account.contractEnd)}${account.contractNeedsVerification ? ' ⚠️ Needs Verification' : ''}</span>
                                </div>
                                <div class="detail-item">
                                    <span class="label">Last Contact (Field Engineering)</span>
                                    <span class="value">${account.lastContactFE || 'Not recorded'}</span>
                                </div>
                                <div class="detail-item">
                                    <span class="label">Last Contact (Sales)</span>
                                    <span class="value">${account.lastContactSales || 'Not recorded'}</span>
                                </div>
                                ${account.primaryPocName || account.primaryPocEmail ? `
                                <div class="detail-item">
                                    <span class="label">Primary POC</span>
                                    <span class="value">${account.primaryPocName || 'Not specified'}${account.primaryPocEmail ? `<br><a href="mailto:${account.primaryPocEmail}" style="font-size: 0.85em; color: #4f46e5;">${account.primaryPocEmail}</a>` : ''}</span>
                                </div>
                                ` : ''}
                                ${account.secondaryPocName || account.secondaryPocEmail ? `
                                <div class="detail-item">
                                    <span class="label">Secondary POC</span>
                                    <span class="value">${account.secondaryPocName || 'Not specified'}${account.secondaryPocEmail ? `<br><a href="mailto:${account.secondaryPocEmail}" style="font-size: 0.85em; color: #4f46e5;">${account.secondaryPocEmail}</a>` : ''}</span>
                                </div>
                                ` : ''}
                            </div>
                            
                            ${hasActiveEngineering(account) || account.latestStatus ? `
                                <div class="engineering-box">
                                    <h4>🔧 Current Engineering Status ${account.latestStatus ? `<span style="font-weight: normal; font-size: 11px; color: #b45309;">(Updated: ${formatDate(account.latestStatus.statusDate)})</span>` : ''}</h4>
                                    <p>${account.latestStatus ? account.latestStatus.statusText : account.engineeringEfforts}</p>
                                </div>
                            ` : ''}
                            
                            ${account.cseNotes ? `
                                <div style="background: #fefce8; border-left: 4px solid #eab308; padding: 15px; margin: 20px 0; border-radius: 0 8px 8px 0;">
                                    <h4 style="font-size: 12px; font-weight: 600; color: #713f12; text-transform: uppercase; margin-bottom: 8px;">📝 CSE Notes</h4>
                                    <p style="font-size: 14px; color: #713f12; white-space: pre-wrap;">${account.cseNotes}</p>
                                </div>
                            ` : ''}
                            
                            ${account.needsReview ? `
                                <div style="background: #fef2f2; border-left: 4px solid #ef4444; padding: 12px 15px; margin: 20px 0; border-radius: 0 8px 8px 0; display: flex; align-items: center; gap: 10px;">
                                    <span style="font-size: 16px;">🚩</span>
                                    <span style="font-size: 13px; font-weight: 600; color: #991b1b;">Flagged for Accuracy Review</span>
                                </div>
                            ` : ''}
                            
                            <div class="links-section">
                                <h4>📎 Links & Documents</h4>
                                ${renderLinks(account.links)}
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `).join('')}
        
        <!-- Footer -->
        <div class="report-footer">
            <p>Enterprise Account Manager Report</p>
            <p>Generated on ${today} • Total Accounts: ${stats.total}</p>
        </div>
    </div>
</body>
</html>
    `;
    
    return html;
}

// Markdown Report Generator
function generateMarkdownReport(accounts) {
    const today = new Date().toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
    });
    
    // Sort accounts by name
    const sortedAccounts = [...accounts].sort((a, b) => a.name.localeCompare(b.name));
    
    // Group by sales rep
    const byRep = {};
    sortedAccounts.forEach(acc => {
        const rep = acc.salesRep || 'Unassigned';
        if (!byRep[rep]) byRep[rep] = [];
        byRep[rep].push(acc);
    });
    
    // Calculate stats
    const stats = {
        total: accounts.length,
        active: accounts.filter(a => getStatusMd(a) === 'active').length,
        expiring: accounts.filter(a => getStatusMd(a) === 'expiring').length,
        expired: accounts.filter(a => getStatusMd(a) === 'expired').length,
        poc: accounts.filter(a => getStatusMd(a) === 'poc').length
    };
    
    function getStatusMd(account) {
        if (account.isPOC) return 'poc';
        if (!account.contractEnd) return 'poc';
        const endDate = new Date(account.contractEnd);
        const todayDate = new Date();
        const days = Math.ceil((endDate - todayDate) / (1000 * 60 * 60 * 24));
        if (days < 0) return 'expired';
        if (days <= 60) return 'expiring';
        return 'active';
    }
    
    function getStatusLabel(status) {
        const labels = {
            active: '✅ Active',
            expiring: '⚠️ Expiring Soon',
            expired: '❌ Expired',
            poc: '🔬 POC'
        };
        return labels[status] || 'Unknown';
    }
    
    function getSentimentLabel(sentiment) {
        const sentiments = {
            excellent: '🟢 Excellent',
            good: '🟢 Good',
            neutral: '🟡 Neutral',
            'at-risk': '🟠 At Risk',
            critical: '🔴 Critical'
        };
        return sentiments[sentiment] || sentiments.neutral;
    }
    
    function formatDateMd(dateStr) {
        if (!dateStr) return 'TBD';
        return new Date(dateStr).toLocaleDateString('en-US', { 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric' 
        });
    }
    
    function renderLinksMd(links) {
        if (!links) return '*No links available*';
        
        const linkItems = [];
        const linkLabels = {
            contract: 'Contract',
            billing: 'Billing Details',
            slack: 'Slack Channel',
            slackExternal: 'External Slack',
            gdrive: 'Google Drive',
            fieldEng: 'Field Engineering Doc',
            sales: 'Sales Doc',
            clarifaiOrg: 'Clarifai Organization',
            jira: 'Jira'
        };
        
        Object.entries(linkLabels).forEach(([key, label]) => {
            if (links[key] && links[key] !== '#') {
                linkItems.push(`- [${label}](${links[key]})`);
            }
        });
        
        if (links.additionalDocs && links.additionalDocs.length > 0) {
            links.additionalDocs.forEach(doc => {
                if (doc.url && doc.url !== '#') {
                    linkItems.push(`- [${doc.name}](${doc.url})`);
                }
            });
        }
        
        if (linkItems.length === 0) {
            return '*No links available*';
        }
        
        return linkItems.join('\n');
    }
    
    // Build Markdown
    let md = `# Enterprise Account Report\n\n`;
    md += `**Generated:** ${today}\n\n`;
    md += `---\n\n`;
    
    // Executive Summary
    md += `## Executive Summary\n\n`;
    md += `| Metric | Count |\n`;
    md += `|--------|-------|\n`;
    md += `| Total Accounts | ${stats.total} |\n`;
    md += `| Active | ${stats.active} |\n`;
    md += `| Expiring (60 days) | ${stats.expiring} |\n`;
    md += `| Expired/Closed | ${stats.expired} |\n`;
    md += `| POC/Trial | ${stats.poc} |\n\n`;
    
    // Table of Contents
    md += `## Table of Contents\n\n`;
    Object.keys(byRep).sort().forEach(rep => {
        const anchor = rep.toLowerCase().replace(/[^a-z0-9]+/g, '-');
        md += `- [${rep}](#${anchor}) (${byRep[rep].length} accounts)\n`;
    });
    md += `\n---\n\n`;
    
    // Accounts by Rep
    Object.keys(byRep).sort().forEach(rep => {
        md += `## ${rep}\n\n`;
        
        byRep[rep].forEach(account => {
            const status = getStatusMd(account);
            const statusLabel = getStatusLabel(status);
            const sentimentLabel = getSentimentLabel(account.sentiment);
            
            md += `### ${account.name}\n\n`;
            md += `**Status:** ${statusLabel} | **Sentiment:** ${sentimentLabel}\n\n`;
            
            // Contract Info
            md += `#### Contract Information\n\n`;
            md += `| Field | Value |\n`;
            md += `|-------|-------|\n`;
            md += `| Contract Start | ${formatDateMd(account.contractStart)} |\n`;
            md += `| Contract End | ${formatDateMd(account.contractEnd)} |\n`;
            if (account.salesforceId) {
                md += `| Salesforce ID | ${account.salesforceId} |\n`;
            }
            md += `\n`;
            
            // Points of Contact
            if (account.primaryPocName || account.primaryPocEmail || account.secondaryPocName || account.secondaryPocEmail) {
                md += `#### Points of Contact\n\n`;
                md += `| Role | Name | Email |\n`;
                md += `|------|------|-------|\n`;
                if (account.primaryPocName || account.primaryPocEmail) {
                    md += `| Primary POC | ${account.primaryPocName || 'Not specified'} | ${account.primaryPocEmail || 'Not specified'} |\n`;
                }
                if (account.secondaryPocName || account.secondaryPocEmail) {
                    md += `| Secondary POC | ${account.secondaryPocName || 'Not specified'} | ${account.secondaryPocEmail || 'Not specified'} |\n`;
                }
                md += `\n`;
            }
            
            // Overview
            if (account.overview) {
                md += `#### Overview\n\n`;
                md += `${account.overview}\n\n`;
            }
            
            // Engineering Status
            if (account.latestStatus) {
                md += `#### Engineering Status\n\n`;
                md += `> **${account.latestStatus.statusDate}**: ${account.latestStatus.statusText}\n\n`;
            }
            
            // CSE Notes
            if (account.cseNotes) {
                md += `#### CSE Notes\n\n`;
                md += `${account.cseNotes}\n\n`;
            }
            
            // Links
            md += `#### Links & Resources\n\n`;
            md += `${renderLinksMd(account.links)}\n\n`;
            
            md += `---\n\n`;
        });
    });
    
    return md;
}

module.exports = { generateReport, generateMarkdownReport };
