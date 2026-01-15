// Database seed script - Run with: node init-db.js
const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

// Ensure data directory exists
const dataDir = process.env.DATA_DIR || './data';
if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
}

const dbPath = path.join(dataDir, 'accounts.db');
const db = new Database(dbPath);

// Initialize tables
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

    CREATE INDEX IF NOT EXISTS idx_accounts_salesforce_id ON accounts(salesforce_id);
    CREATE INDEX IF NOT EXISTS idx_accounts_sales_rep ON accounts(sales_rep);
    CREATE INDEX IF NOT EXISTS idx_account_links_account_id ON account_links(account_id);
`);

// Initial sample account data
const accounts = [
    {
        name: "-DEMO CORP-",
        overview: "Enterprise customer using classification and detection APIs for content moderation.",
        salesforceId: "001SAMPLE00001",
        contractStart: "2025-01-01",
        contractEnd: "2026-01-01",
        engineeringEfforts: "Initial integration support completed.",
        salesRep: "Jane Smith",
        lastContactFE: "Jan 10, 2026",
        lastContactSales: "Jan 5, 2026",
        links: { 
            contract: "https://example.com/contract", 
            billing: "https://example.com/billing",
            slack: "https://slack.com/example-channel",
            gdrive: "https://drive.google.com/example-folder"
        }
    }
];

// Check if data already exists
const existingCount = db.prepare('SELECT COUNT(*) as count FROM accounts').get().count;

if (existingCount > 0) {
    console.log(`Database already contains ${existingCount} accounts. Skipping seed.`);
    console.log('To re-seed, delete the data/accounts.db file and run again.');
} else {
    console.log('Seeding database with initial accounts...');
    
    const insertAccount = db.prepare(`
        INSERT INTO accounts (
            name, overview, salesforce_id, contract_start, contract_end,
            contract_needs_verification, is_poc, engineering_efforts,
            sales_rep, last_contact_fe, last_contact_sales
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);
    
    const insertLink = db.prepare(`
        INSERT INTO account_links (account_id, link_type, link_name, link_url)
        VALUES (?, ?, ?, ?)
    `);
    
    const seedTransaction = db.transaction(() => {
        accounts.forEach(account => {
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
        });
    });
    
    seedTransaction();
    console.log(`Successfully seeded ${accounts.length} accounts!`);
}

db.close();
console.log('Database initialization complete.');
