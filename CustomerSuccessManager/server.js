const express = require('express');
const Database = require('better-sqlite3');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const { generateReport, generateMarkdownReport } = require('./report-generator');
const rateLimit = require('express-rate-limit');

const app = express();
const PORT = process.env.PORT || 3000;

// Rate limiter for account write operations to protect the database
const accountWriteLimiter = rateLimit({
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 100, // limit each IP to 100 write requests per window
    standardHeaders: true,
    legacyHeaders: false,
});

// Stricter rate limiter for administrative database operations (backup, clear, restore)
const adminDbLimiter = rateLimit({
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 10, // limit each IP to 10 admin DB requests per window
    standardHeaders: true,
    legacyHeaders: false,
});

// Ensure data directory exists
const dataDir = process.env.DATA_DIR || './data';
if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
}

// Initialize SQLite database
const dbPath = path.join(dataDir, 'accounts.db');
const db = new Database(dbPath);

// Enable WAL mode for better performance
db.pragma('journal_mode = WAL');

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static('public'));

// Initialize database tables
function initDatabase() {
    db.exec(`
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            overview TEXT,
            salesforce_id TEXT UNIQUE,
            contract_start TEXT,
            contract_end TEXT,
            contract_needs_verification INTEGER DEFAULT 0,
            is_poc INTEGER DEFAULT 0,
            engineering_efforts TEXT,
            sales_rep TEXT,
            last_contact_fe TEXT,
            last_contact_sales TEXT,
            cse_notes TEXT,
            needs_review INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS account_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            link_type TEXT NOT NULL,
            link_name TEXT,
            link_url TEXT,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS status_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            status_text TEXT NOT NULL,
            status_date TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_accounts_salesforce_id ON accounts(salesforce_id);
        CREATE INDEX IF NOT EXISTS idx_accounts_sales_rep ON accounts(sales_rep);
        CREATE INDEX IF NOT EXISTS idx_account_links_account_id ON account_links(account_id);
        CREATE INDEX IF NOT EXISTS idx_status_updates_account_id ON status_updates(account_id);
        CREATE INDEX IF NOT EXISTS idx_status_updates_date ON status_updates(status_date);
    `);
    
    // Run migrations to add new columns if they don't exist
    try {
        db.exec(`ALTER TABLE accounts ADD COLUMN cse_notes TEXT`);
        console.log('Added cse_notes column');
    } catch (e) {
        // Column already exists
    }
    
    try {
        db.exec(`ALTER TABLE accounts ADD COLUMN needs_review INTEGER DEFAULT 0`);
        console.log('Added needs_review column');
    } catch (e) {
        // Column already exists
    }
    
    try {
        db.exec(`ALTER TABLE accounts ADD COLUMN sentiment TEXT DEFAULT 'neutral'`);
        console.log('Added sentiment column');
    } catch (e) {
        // Column already exists
    }
    
    try {
        db.exec(`ALTER TABLE accounts ADD COLUMN engineering_status TEXT DEFAULT 'none'`);
        console.log('Added engineering_status column');
    } catch (e) {
        // Column already exists
    }
    
    try {
        db.exec(`ALTER TABLE accounts ADD COLUMN primary_poc_name TEXT`);
        console.log('Added primary_poc_name column');
    } catch (e) {
        // Column already exists
    }
    
    try {
        db.exec(`ALTER TABLE accounts ADD COLUMN primary_poc_email TEXT`);
        console.log('Added primary_poc_email column');
    } catch (e) {
        // Column already exists
    }
    
    try {
        db.exec(`ALTER TABLE accounts ADD COLUMN secondary_poc_name TEXT`);
        console.log('Added secondary_poc_name column');
    } catch (e) {
        // Column already exists
    }
    
    try {
        db.exec(`ALTER TABLE accounts ADD COLUMN secondary_poc_email TEXT`);
        console.log('Added secondary_poc_email column');
    } catch (e) {
        // Column already exists
    }
    
    console.log('Database initialized successfully');
}

// API Routes

// Get all accounts
app.get('/api/accounts', (req, res) => {
    try {
        const accounts = db.prepare(`
            SELECT * FROM accounts ORDER BY name
        `).all();
        
        // Get links for each account
        const getLinks = db.prepare(`
            SELECT * FROM account_links WHERE account_id = ?
        `);
        
        const result = accounts.map(account => {
            const links = getLinks.all(account.id);
            const linksObj = {
                contract: null,
                billing: null,
                slack: null,
                slackExternal: null,
                gdrive: null,
                fieldEng: null,
                sales: null,
                clarifaiOrg: null,
                jira: null,
                additionalDocs: []
            };
            
            links.forEach(link => {
                if (link.link_type === 'additional') {
                    linksObj.additionalDocs.push({
                        name: link.link_name,
                        url: link.link_url
                    });
                } else {
                    linksObj[link.link_type] = link.link_url;
                }
            });
            
            return {
                id: account.id,
                name: account.name,
                overview: account.overview,
                salesforceId: account.salesforce_id,
                contractStart: account.contract_start,
                contractEnd: account.contract_end,
                contractNeedsVerification: !!account.contract_needs_verification,
                isPOC: !!account.is_poc,
                engineeringEfforts: account.engineering_efforts,
                salesRep: account.sales_rep,
                lastContactFE: account.last_contact_fe,
                lastContactSales: account.last_contact_sales,
                cseNotes: account.cse_notes,
                needsReview: !!account.needs_review,
                sentiment: account.sentiment || 'neutral',
                engineeringStatus: account.engineering_status || 'none',
                primaryPocName: account.primary_poc_name,
                primaryPocEmail: account.primary_poc_email,
                secondaryPocName: account.secondary_poc_name,
                secondaryPocEmail: account.secondary_poc_email,
                links: linksObj
            };
        });
        
        res.json(result);
    } catch (error) {
        console.error('Error fetching accounts:', error);
        res.status(500).json({ error: 'Failed to fetch accounts' });
    }
});

// Get single account
app.get('/api/accounts/:id', (req, res) => {
    try {
        const account = db.prepare(`
            SELECT * FROM accounts WHERE id = ?
        `).get(req.params.id);
        
        if (!account) {
            return res.status(404).json({ error: 'Account not found' });
        }
        
        const links = db.prepare(`
            SELECT * FROM account_links WHERE account_id = ?
        `).all(account.id);
        
        const linksObj = {
            contract: null,
            billing: null,
            slack: null,
            slackExternal: null,
            gdrive: null,
            fieldEng: null,
            sales: null,
            clarifaiOrg: null,
            jira: null,
            additionalDocs: []
        };
        
        links.forEach(link => {
            if (link.link_type === 'additional') {
                linksObj.additionalDocs.push({
                    name: link.link_name,
                    url: link.link_url
                });
            } else {
                linksObj[link.link_type] = link.link_url;
            }
        });
        
        res.json({
            id: account.id,
            name: account.name,
            overview: account.overview,
            salesforceId: account.salesforce_id,
            contractStart: account.contract_start,
            contractEnd: account.contract_end,
            contractNeedsVerification: !!account.contract_needs_verification,
            isPOC: !!account.is_poc,
            engineeringEfforts: account.engineering_efforts,
            salesRep: account.sales_rep,
            lastContactFE: account.last_contact_fe,
            lastContactSales: account.last_contact_sales,
            cseNotes: account.cse_notes,
            needsReview: !!account.needs_review,
            sentiment: account.sentiment || 'neutral',
            engineeringStatus: account.engineering_status || 'none',
            primaryPocName: account.primary_poc_name,
            primaryPocEmail: account.primary_poc_email,
            secondaryPocName: account.secondary_poc_name,
            secondaryPocEmail: account.secondary_poc_email,
            links: linksObj
        });
    } catch (error) {
        console.error('Error fetching account:', error);
        res.status(500).json({ error: 'Failed to fetch account' });
    }
});

// Create new account
app.post('/api/accounts', accountWriteLimiter, (req, res) => {
    try {
        const {
            name, overview, salesforceId, contractStart, contractEnd,
            contractNeedsVerification, isPOC, engineeringEfforts, engineeringStatus,
            salesRep, lastContactFE, lastContactSales, cseNotes, needsReview, sentiment,
            primaryPocName, primaryPocEmail, secondaryPocName, secondaryPocEmail, links
        } = req.body;
        
        const result = db.prepare(`
            INSERT INTO accounts (
                name, overview, salesforce_id, contract_start, contract_end,
                contract_needs_verification, is_poc, engineering_efforts, engineering_status,
                sales_rep, last_contact_fe, last_contact_sales, cse_notes, needs_review, sentiment,
                primary_poc_name, primary_poc_email, secondary_poc_name, secondary_poc_email
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `).run(
            name, overview, salesforceId, contractStart, contractEnd,
            contractNeedsVerification ? 1 : 0, isPOC ? 1 : 0, engineeringEfforts, engineeringStatus || 'none',
            salesRep, lastContactFE, lastContactSales, cseNotes, needsReview ? 1 : 0, sentiment || 'neutral',
            primaryPocName, primaryPocEmail, secondaryPocName, secondaryPocEmail
        );
        
        const accountId = result.lastInsertRowid;
        
        // Insert links
        if (links) {
            const insertLink = db.prepare(`
                INSERT INTO account_links (account_id, link_type, link_name, link_url)
                VALUES (?, ?, ?, ?)
            `);
            
            const linkTypes = ['contract', 'billing', 'slack', 'slackExternal', 'gdrive', 'fieldEng', 'sales', 'clarifaiOrg', 'jira'];
            linkTypes.forEach(type => {
                if (links[type]) {
                    insertLink.run(accountId, type, type, links[type]);
                }
            });
            
            if (links.additionalDocs) {
                links.additionalDocs.forEach(doc => {
                    insertLink.run(accountId, 'additional', doc.name, doc.url);
                });
            }
        }
        
        res.status(201).json({ id: accountId, message: 'Account created successfully' });
    } catch (error) {
        console.error('Error creating account:', error);
        res.status(500).json({ error: 'Failed to create account' });
    }
});

// Update account
app.put('/api/accounts/:id', accountWriteLimiter, (req, res) => {
    try {
        const {
            name, overview, salesforceId, contractStart, contractEnd,
            contractNeedsVerification, isPOC, engineeringEfforts, engineeringStatus,
            salesRep, lastContactFE, lastContactSales, cseNotes, needsReview, sentiment,
            primaryPocName, primaryPocEmail, secondaryPocName, secondaryPocEmail, links
        } = req.body;
        
        const result = db.prepare(`
            UPDATE accounts SET
                name = ?, overview = ?, salesforce_id = ?, contract_start = ?,
                contract_end = ?, contract_needs_verification = ?, is_poc = ?,
                engineering_efforts = ?, engineering_status = ?, sales_rep = ?, last_contact_fe = ?,
                last_contact_sales = ?, cse_notes = ?, needs_review = ?, sentiment = ?,
                primary_poc_name = ?, primary_poc_email = ?, secondary_poc_name = ?, secondary_poc_email = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        `).run(
            name, overview, salesforceId, contractStart, contractEnd,
            contractNeedsVerification ? 1 : 0, isPOC ? 1 : 0, engineeringEfforts, engineeringStatus || 'none',
            salesRep, lastContactFE, lastContactSales, cseNotes, needsReview ? 1 : 0, sentiment || 'neutral',
            primaryPocName, primaryPocEmail, secondaryPocName, secondaryPocEmail, req.params.id
        );
        
        if (result.changes === 0) {
            return res.status(404).json({ error: 'Account not found' });
        }
        
        // Delete existing links and re-insert
        db.prepare(`DELETE FROM account_links WHERE account_id = ?`).run(req.params.id);
        
        if (links) {
            const insertLink = db.prepare(`
                INSERT INTO account_links (account_id, link_type, link_name, link_url)
                VALUES (?, ?, ?, ?)
            `);
            
            const linkTypes = ['contract', 'billing', 'slack', 'slackExternal', 'gdrive', 'fieldEng', 'sales', 'clarifaiOrg', 'jira'];
            linkTypes.forEach(type => {
                if (links[type]) {
                    insertLink.run(req.params.id, type, type, links[type]);
                }
            });
            
            if (links.additionalDocs) {
                links.additionalDocs.forEach(doc => {
                    insertLink.run(req.params.id, 'additional', doc.name, doc.url);
                });
            }
        }
        
        res.json({ message: 'Account updated successfully' });
    } catch (error) {
        console.error('Error updating account:', error);
        res.status(500).json({ error: 'Failed to update account' });
    }
});

// Delete account
app.delete('/api/accounts/:id', accountWriteLimiter, (req, res) => {
    try {
        // Delete links first
        db.prepare(`DELETE FROM account_links WHERE account_id = ?`).run(req.params.id);
        
        const result = db.prepare(`DELETE FROM accounts WHERE id = ?`).run(req.params.id);
        
        if (result.changes === 0) {
            return res.status(404).json({ error: 'Account not found' });
        }
        
        res.json({ message: 'Account deleted successfully' });
    } catch (error) {
        console.error('Error deleting account:', error);
        res.status(500).json({ error: 'Failed to delete account' });
    }
});

// Update engineering status quickly
app.patch('/api/accounts/:id/engineering-status', (req, res) => {
    try {
        const { status } = req.body;
        const validStatuses = ['none', 'active'];
        
        if (!validStatuses.includes(status)) {
            return res.status(400).json({ error: 'Invalid status. Must be: none or active' });
        }
        
        const result = db.prepare(`
            UPDATE accounts SET engineering_status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        `).run(status, req.params.id);
        
        if (result.changes === 0) {
            return res.status(404).json({ error: 'Account not found' });
        }
        
        res.json({ message: 'Engineering status updated successfully', status });
    } catch (error) {
        console.error('Error updating engineering status:', error);
        res.status(500).json({ error: 'Failed to update engineering status' });
    }
});

// Get dashboard stats
app.get('/api/stats', (req, res) => {
    try {
        const total = db.prepare(`SELECT COUNT(*) as count FROM accounts`).get().count;
        
        const today = new Date().toISOString().split('T')[0];
        const sixtyDaysLater = new Date(Date.now() + 60 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
        
        const active = db.prepare(`
            SELECT COUNT(*) as count FROM accounts 
            WHERE contract_end >= ? AND is_poc = 0 AND contract_end IS NOT NULL AND contract_end != ''
        `).get(today).count;
        
        const expiring = db.prepare(`
            SELECT COUNT(*) as count FROM accounts 
            WHERE contract_end >= ? AND contract_end <= ? AND is_poc = 0 AND contract_end IS NOT NULL AND contract_end != ''
        `).get(today, sixtyDaysLater).count;
        
        const withEngineering = db.prepare(`
            SELECT COUNT(*) as count FROM accounts 
            WHERE engineering_status = 'active'
        `).get().count;
        
        const needsReview = db.prepare(`
            SELECT COUNT(*) as count FROM accounts 
            WHERE needs_review = 1
        `).get().count;
        
        const expired = db.prepare(`
            SELECT COUNT(*) as count FROM accounts 
            WHERE contract_end < ? AND is_poc = 0 AND contract_end IS NOT NULL AND contract_end != ''
        `).get(today).count;
        
        res.json({
            total,
            active,
            expiring,
            withEngineering,
            needsReview,
            expired
        });
    } catch (error) {
        console.error('Error fetching stats:', error);
        res.status(500).json({ error: 'Failed to fetch stats' });
    }
});

// Search accounts
app.get('/api/search', (req, res) => {
    try {
        const { q } = req.query;
        if (!q) {
            return res.json([]);
        }
        
        const searchTerm = `%${q}%`;
        const accounts = db.prepare(`
            SELECT * FROM accounts 
            WHERE name LIKE ? 
            OR salesforce_id LIKE ? 
            OR sales_rep LIKE ? 
            OR overview LIKE ?
            ORDER BY name
        `).all(searchTerm, searchTerm, searchTerm, searchTerm);
        
        res.json(accounts.map(a => ({
            id: a.id,
            name: a.name,
            salesforceId: a.salesforce_id,
            salesRep: a.sales_rep
        })));
    } catch (error) {
        console.error('Error searching accounts:', error);
        res.status(500).json({ error: 'Failed to search accounts' });
    }
});

// Export all data
app.get('/api/export', (req, res) => {
    try {
        const accounts = db.prepare(`SELECT * FROM accounts ORDER BY name`).all();
        const links = db.prepare(`SELECT * FROM account_links`).all();
        
        res.json({
            exportDate: new Date().toISOString(),
            accounts,
            links
        });
    } catch (error) {
        console.error('Error exporting data:', error);
        res.status(500).json({ error: 'Failed to export data' });
    }
});

// Import data
app.post('/api/import', (req, res) => {
    try {
        const { accounts: importAccounts } = req.body;
        
        if (!Array.isArray(importAccounts)) {
            return res.status(400).json({ error: 'Invalid data format' });
        }
        
        const insertAccount = db.prepare(`
            INSERT OR REPLACE INTO accounts (
                name, overview, salesforce_id, contract_start, contract_end,
                contract_needs_verification, is_poc, engineering_efforts,
                sales_rep, last_contact_fe, last_contact_sales
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `);
        
        const insertLink = db.prepare(`
            INSERT INTO account_links (account_id, link_type, link_name, link_url)
            VALUES (?, ?, ?, ?)
        `);
        
        let imported = 0;
        
        const importTransaction = db.transaction(() => {
            importAccounts.forEach(account => {
                const result = insertAccount.run(
                    account.name,
                    account.overview,
                    account.salesforceId,
                    account.contractStart,
                    account.contractEnd,
                    account.contractNeedsVerification ? 1 : 0,
                    account.isPOC ? 1 : 0,
                    account.engineeringEfforts,
                    account.salesRep,
                    account.lastContactFE,
                    account.lastContactSales
                );
                
                const accountId = result.lastInsertRowid;
                
                if (account.links) {
                    const linkTypes = ['contract', 'billing', 'slack', 'slackExternal', 'gdrive', 'fieldEng', 'sales', 'clarifaiOrg', 'jira'];
                    linkTypes.forEach(type => {
                        if (account.links[type]) {
                            insertLink.run(accountId, type, type, account.links[type]);
                        }
                    });
                    
                    if (account.links.additionalDocs) {
                        account.links.additionalDocs.forEach(doc => {
                            insertLink.run(accountId, 'additional', doc.name, doc.url);
                        });
                    }
                }
                
                imported++;
            });
        });
        
        importTransaction();
        
        res.json({ message: `Successfully imported ${imported} accounts` });
    } catch (error) {
        console.error('Error importing data:', error);
        res.status(500).json({ error: 'Failed to import data' });
    }
});

// Health check
app.get('/api/health', (req, res) => {
    res.json({ status: 'healthy', timestamp: new Date().toISOString() });
});

// Get status history for an account
app.get('/api/accounts/:id/status-history', (req, res) => {
    try {
        const statusHistory = db.prepare(`
            SELECT * FROM status_updates 
            WHERE account_id = ? 
            ORDER BY status_date DESC, created_at DESC
        `).all(req.params.id);
        
        res.json(statusHistory.map(s => ({
            id: s.id,
            accountId: s.account_id,
            statusText: s.status_text,
            statusDate: s.status_date,
            createdAt: s.created_at
        })));
    } catch (error) {
        console.error('Error fetching status history:', error);
        res.status(500).json({ error: 'Failed to fetch status history' });
    }
});

// Add new status update
app.post('/api/accounts/:id/status-history', (req, res) => {
    try {
        const { statusText, statusDate } = req.body;
        
        if (!statusText) {
            return res.status(400).json({ error: 'Status text is required' });
        }
        
        const date = statusDate || new Date().toISOString().split('T')[0];
        
        const result = db.prepare(`
            INSERT INTO status_updates (account_id, status_text, status_date)
            VALUES (?, ?, ?)
        `).run(req.params.id, statusText, date);
        
        // Also update the engineering_efforts field on the account to the latest status
        db.prepare(`
            UPDATE accounts SET engineering_efforts = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        `).run(statusText, req.params.id);
        
        res.status(201).json({
            id: result.lastInsertRowid,
            accountId: parseInt(req.params.id),
            statusText,
            statusDate: date
        });
    } catch (error) {
        console.error('Error adding status update:', error);
        res.status(500).json({ error: 'Failed to add status update' });
    }
});

// Delete status update
app.delete('/api/status-history/:id', (req, res) => {
    try {
        const result = db.prepare(`DELETE FROM status_updates WHERE id = ?`).run(req.params.id);
        
        if (result.changes === 0) {
            return res.status(404).json({ error: 'Status update not found' });
        }
        
        res.json({ message: 'Status update deleted' });
    } catch (error) {
        console.error('Error deleting status update:', error);
        res.status(500).json({ error: 'Failed to delete status update' });
    }
});

// Get latest status for an account
app.get('/api/accounts/:id/latest-status', (req, res) => {
    try {
        const latestStatus = db.prepare(`
            SELECT * FROM status_updates 
            WHERE account_id = ? 
            ORDER BY status_date DESC, created_at DESC
            LIMIT 1
        `).get(req.params.id);
        
        if (!latestStatus) {
            return res.json(null);
        }
        
        res.json({
            id: latestStatus.id,
            accountId: latestStatus.account_id,
            statusText: latestStatus.status_text,
            statusDate: latestStatus.status_date,
            createdAt: latestStatus.created_at
        });
    } catch (error) {
        console.error('Error fetching latest status:', error);
        res.status(500).json({ error: 'Failed to fetch latest status' });
    }
});

// Generate professional report
app.get('/api/report', (req, res) => {
    try {
        const accounts = db.prepare(`
            SELECT * FROM accounts ORDER BY name
        `).all();
        
        // Get links for each account
        const getLinks = db.prepare(`
            SELECT * FROM account_links WHERE account_id = ?
        `);
        
        // Get latest status for each account
        const getLatestStatus = db.prepare(`
            SELECT * FROM status_updates 
            WHERE account_id = ? 
            ORDER BY status_date DESC, created_at DESC
            LIMIT 1
        `);
        
        const result = accounts.map(account => {
            const links = getLinks.all(account.id);
            const linksObj = {
                contract: null,
                billing: null,
                slack: null,
                slackExternal: null,
                gdrive: null,
                fieldEng: null,
                sales: null,
                clarifaiOrg: null,
                jira: null,
                additionalDocs: []
            };
            
            links.forEach(link => {
                if (link.link_type === 'additional') {
                    linksObj.additionalDocs.push({
                        name: link.link_name,
                        url: link.link_url
                    });
                } else {
                    linksObj[link.link_type] = link.link_url;
                }
            });
            
            // Get latest status
            const latestStatus = getLatestStatus.get(account.id);
            
            return {
                id: account.id,
                name: account.name,
                overview: account.overview,
                salesforceId: account.salesforce_id,
                contractStart: account.contract_start,
                contractEnd: account.contract_end,
                contractNeedsVerification: !!account.contract_needs_verification,
                isPOC: !!account.is_poc,
                engineeringEfforts: account.engineering_efforts,
                salesRep: account.sales_rep,
                lastContactFE: account.last_contact_fe,
                lastContactSales: account.last_contact_sales,
                cseNotes: account.cse_notes,
                needsReview: !!account.needs_review,
                sentiment: account.sentiment || 'neutral',
                primaryPocName: account.primary_poc_name,
                primaryPocEmail: account.primary_poc_email,
                secondaryPocName: account.secondary_poc_name,
                secondaryPocEmail: account.secondary_poc_email,
                links: linksObj,
                latestStatus: latestStatus ? {
                    statusText: latestStatus.status_text,
                    statusDate: latestStatus.status_date
                } : null
            };
        });
        
        const format = req.query.format || 'html';
        
        if (format === 'markdown') {
            const reportMd = generateMarkdownReport(result);
            res.setHeader('Content-Type', 'text/markdown');
            res.setHeader('Content-Disposition', `attachment; filename="enterprise-accounts-report-${new Date().toISOString().split('T')[0]}.md"`);
            res.send(reportMd);
        } else {
            const reportHtml = generateReport(result);
            res.setHeader('Content-Type', 'text/html');
            res.send(reportHtml);
        }
    } catch (error) {
        console.error('Error generating report:', error);
        res.status(500).json({ error: 'Failed to generate report' });
    }
});

// Database Management - Export Backup
app.get('/api/backup', adminDbLimiter, (req, res) => {
    try {
        // Get all accounts
        const accounts = db.prepare(`SELECT * FROM accounts`).all();
        
        // Get all links
        const links = db.prepare(`SELECT * FROM account_links`).all();
        
        // Get all status updates
        const statusUpdates = db.prepare(`SELECT * FROM status_updates`).all();
        
        const backup = {
            version: '1.0',
            exportDate: new Date().toISOString(),
            data: {
                accounts: accounts.map(a => ({
                    ...a,
                    contract_needs_verification: !!a.contract_needs_verification,
                    is_poc: !!a.is_poc,
                    needs_review: !!a.needs_review
                })),
                links,
                statusUpdates
            }
        };
        
        const now = new Date();
        const dateStr = now.toISOString().replace(/[:.]/g, '-').slice(0, 19);
        const filename = `account-manager-backup-${dateStr}.json`;
        
        res.setHeader('Content-Type', 'application/json');
        res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
        res.json(backup);
    } catch (error) {
        console.error('Error creating backup:', error);
        res.status(500).json({ error: 'Failed to create backup' });
    }
});

// Database Management - Clear Database
app.delete('/api/database', adminDbLimiter, (req, res) => {
    try {
        db.prepare(`DELETE FROM status_updates`).run();
        db.prepare(`DELETE FROM account_links`).run();
        db.prepare(`DELETE FROM accounts`).run();
        
        // Reset auto-increment
        db.prepare(`DELETE FROM sqlite_sequence WHERE name IN ('accounts', 'account_links', 'status_updates')`).run();
        
        res.json({ message: 'Database cleared successfully' });
    } catch (error) {
        console.error('Error clearing database:', error);
        res.status(500).json({ error: 'Failed to clear database' });
    }
});

// Database Management - Restore from Backup
app.post('/api/restore', adminDbLimiter, (req, res) => {
    try {
        const { data } = req.body;
        
        if (!data || !data.accounts) {
            return res.status(400).json({ error: 'Invalid backup file format' });
        }
        
        // Clear existing data first
        db.prepare(`DELETE FROM status_updates`).run();
        db.prepare(`DELETE FROM account_links`).run();
        db.prepare(`DELETE FROM accounts`).run();
        
        // Restore accounts
        const insertAccount = db.prepare(`
            INSERT INTO accounts (
                id, name, overview, salesforce_id, contract_start, contract_end,
                contract_needs_verification, is_poc, engineering_efforts, engineering_status,
                sales_rep, last_contact_fe, last_contact_sales, cse_notes, needs_review,
                sentiment, primary_poc_name, primary_poc_email, secondary_poc_name, secondary_poc_email,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `);
        
        for (const acc of data.accounts) {
            insertAccount.run(
                acc.id, acc.name, acc.overview, acc.salesforce_id, acc.contract_start, acc.contract_end,
                acc.contract_needs_verification ? 1 : 0, acc.is_poc ? 1 : 0,
                acc.engineering_efforts, acc.engineering_status || 'none',
                acc.sales_rep, acc.last_contact_fe, acc.last_contact_sales,
                acc.cse_notes, acc.needs_review ? 1 : 0, acc.sentiment || 'neutral',
                acc.primary_poc_name, acc.primary_poc_email, acc.secondary_poc_name, acc.secondary_poc_email,
                acc.created_at, acc.updated_at
            );
        }
        
        // Restore links
        if (data.links) {
            const insertLink = db.prepare(`
                INSERT INTO account_links (id, account_id, link_type, link_name, link_url)
                VALUES (?, ?, ?, ?, ?)
            `);
            
            for (const link of data.links) {
                insertLink.run(link.id, link.account_id, link.link_type, link.link_name, link.link_url);
            }
        }
        
        // Restore status updates
        if (data.statusUpdates) {
            const insertStatus = db.prepare(`
                INSERT INTO status_updates (id, account_id, status_text, status_date, created_at)
                VALUES (?, ?, ?, ?, ?)
            `);
            
            for (const status of data.statusUpdates) {
                insertStatus.run(status.id, status.account_id, status.status_text, status.status_date, status.created_at);
            }
        }
        
        res.json({ 
            message: 'Database restored successfully',
            accounts: data.accounts.length,
            links: data.links ? data.links.length : 0,
            statusUpdates: data.statusUpdates ? data.statusUpdates.length : 0
        });
    } catch (error) {
        console.error('Error restoring database:', error);
        res.status(500).json({ error: 'Failed to restore database: ' + error.message });
    }
});

// Serve the frontend for any other routes
app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Initialize and start server
initDatabase();

app.listen(PORT, '0.0.0.0', () => {
    console.log(`Enterprise Account Manager running on http://localhost:${PORT}`);
});

// Graceful shutdown
process.on('SIGINT', () => {
    console.log('Shutting down...');
    db.close();
    process.exit(0);
});

process.on('SIGTERM', () => {
    console.log('Shutting down...');
    db.close();
    process.exit(0);
});
