document.addEventListener('DOMContentLoaded', function() {
    // ========================================
    // DOM ELEMENTS
    // ========================================
    const heatmapGrid = document.getElementById('heatmap-grid');
    const heatmapMonthsRow = document.getElementById('heatmap-months-row');
    const heatmapTooltip = document.getElementById('heatmap-tooltip');
    const heatmapTotalCountEl = document.getElementById('heatmap-total-count');
    const heatmapYearDisplayEl = document.getElementById('heatmap-year-display');
    const heatmapThemeToggle = document.getElementById('heatmap-theme-toggle');
    const heatmapYearSelector = document.getElementById('heatmap-year-selector');
    const heatmapFilterBtns = document.querySelectorAll('.heatmap-filter');
    const heatmapNewDropdown = document.getElementById('heatmap-new-dropdown');
    const heatmapNewBtn = document.getElementById('heatmap-new-btn');

    // ========================================
    // CONFIG
    // ========================================
    const HEATMAP_API_BASE = 'http://localhost:8000/api';  // Python FastAPI server
    const HEATMAP_START_YEAR = 2024;
    const HEATMAP_CURRENT_YEAR = new Date().getFullYear();
    const HEATMAP_TOTAL_WEEKS = 53;
    const HEATMAP_DAY_MS = 24 * 60 * 60 * 1000;
    const HEATMAP_MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const HEATMAP_STORAGE_KEY = 'heatmap-audit-data';  // Fallback for offline mode

    // ========================================
    // STATE
    // ========================================
    let heatmapSelectedYear = HEATMAP_CURRENT_YEAR;
    let heatmapActiveFilters = { internal: true, external: true };
    let heatmapData = {};  // Cache for heatmap data from API
    let heatmapIsOnline = true;  // Track API connection status

    // ========================================
    // API FUNCTIONS (MSSQL via Python FastAPI)
    // ========================================
    async function heatmapApiRequest(endpoint, options = {}) {
        try {
            const response = await fetch(`${HEATMAP_API_BASE}${endpoint}`, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`API Error: ${response.status}`);
            }
            
            heatmapIsOnline = true;
            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            heatmapIsOnline = false;
            throw error;
        }
    }

    // Check API health
    async function heatmapCheckHealth() {
        try {
            const health = await heatmapApiRequest('/health');
            heatmapIsOnline = health.status === 'healthy';
            return heatmapIsOnline;
        } catch {
            heatmapIsOnline = false;
            return false;
        }
    }

    // CREATE - Add new audit to database
    async function heatmapCreateAudit(type, auditData) {
        try {
            const audit = await heatmapApiRequest('/audits', {
                method: 'POST',
                body: JSON.stringify({
                    audit_type: type,
                    title: auditData.title,
                    description: auditData.description || '',
                    audit_date: auditData.date
                })
            });
            
            // Refresh heatmap data after creating
            await heatmapLoadHeatmapData(heatmapSelectedYear);
            return audit;
        } catch (error) {
            // Fallback to localStorage if API fails
            console.warn('API unavailable, using localStorage fallback');
            return heatmapCreateAuditOffline(type, auditData);
        }
    }

    // READ - Get heatmap data for a year
    async function heatmapLoadHeatmapData(year) {
        try {
            const data = await heatmapApiRequest(`/heatmap/${year}`);
            // Convert array to object keyed by date for fast lookup
            heatmapData = {};
            data.forEach(item => {
                heatmapData[item.date] = {
                    internal: item.internal,
                    external: item.external,
                    total: item.total
                };
            });
            return heatmapData;
        } catch (error) {
            // Fallback to localStorage
            console.warn('Using localStorage data as fallback');
            return heatmapLoadDataOffline();
        }
    }

    // READ - Get yearly stats
    async function heatmapLoadYearlyStats(year) {
        try {
            return await heatmapApiRequest(`/stats/${year}`);
        } catch {
            return { total_audits: 0, internal_count: 0, external_count: 0 };
        }
    }

    // READ - Get audits for a specific date (for detail view)
    async function heatmapGetAuditsByDate(dateStr) {
        try {
            return await heatmapApiRequest(`/audits/date/${dateStr}`);
        } catch {
            return [];
        }
    }

    // UPDATE - Update an audit
    async function heatmapUpdateAudit(auditId, auditData) {
        return await heatmapApiRequest(`/audits/${auditId}`, {
            method: 'PUT',
            body: JSON.stringify(auditData)
        });
    }

    // DELETE - Delete an audit
    async function heatmapDeleteAudit(auditId) {
        return await heatmapApiRequest(`/audits/${auditId}`, {
            method: 'DELETE'
        });
    }

    // ========================================
    // OFFLINE FALLBACK (localStorage)
    // ========================================
    function heatmapLoadDataOffline() {
        const stored = localStorage.getItem(HEATMAP_STORAGE_KEY);
        if (stored) {
            const data = JSON.parse(stored);
            // Convert to heatmap format
            heatmapData = {};
            ['internal', 'external'].forEach(type => {
                (data[type] || []).forEach(audit => {
                    if (!heatmapData[audit.date]) {
                        heatmapData[audit.date] = { internal: 0, external: 0, total: 0 };
                    }
                    heatmapData[audit.date][type]++;
                    heatmapData[audit.date].total++;
                });
            });
        }
        return heatmapData;
    }

    function heatmapCreateAuditOffline(type, auditData) {
        const stored = localStorage.getItem(HEATMAP_STORAGE_KEY);
        const data = stored ? JSON.parse(stored) : { internal: [], external: [] };
        
        const audit = {
            id: Date.now().toString(),
            title: auditData.title,
            description: auditData.description,
            date: auditData.date,
            createdAt: new Date().toISOString()
        };
        
        data[type].push(audit);
        localStorage.setItem(HEATMAP_STORAGE_KEY, JSON.stringify(data));
        heatmapLoadDataOffline();
        return audit;
    }

    // ========================================
    // DATA HELPERS
    // ========================================
    function heatmapGetAuditData(date) {
        const dateStr = date.toISOString().split('T')[0];
        return heatmapData[dateStr] || { internal: 0, external: 0, total: 0 };
    }

    function heatmapGetFilteredCount(data) {
        let count = 0;
        if (heatmapActiveFilters.internal) count += data.internal;
        if (heatmapActiveFilters.external) count += data.external;
        return count;
    }

    // ========================================
    // NAVIGATION
    // ========================================
    function heatmapNavigateTo(pageId) {
        document.querySelectorAll('.heatmap-page').forEach(page => {
            page.classList.remove('heatmap-page-active');
        });
        const targetPage = document.getElementById(`heatmap-page-${pageId}`);
        if (targetPage) {
            targetPage.classList.add('heatmap-page-active');
        }
        // Re-render grid when returning home
        if (pageId === 'home') {
            heatmapRenderGrid();
        }
    }

    // Navigation event listeners
    document.querySelectorAll('[data-heatmap-nav]').forEach(el => {
        el.addEventListener('click', (e) => {
            e.preventDefault();
            const target = el.getAttribute('data-heatmap-nav');
            heatmapNavigateTo(target);
        });
    });

    // ========================================
    // DROPDOWN
    // ========================================
    heatmapNewBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        heatmapNewDropdown.classList.toggle('heatmap-dropdown-open');
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!heatmapNewDropdown.contains(e.target)) {
            heatmapNewDropdown.classList.remove('heatmap-dropdown-open');
        }
    });

    // Dropdown actions
    document.querySelectorAll('[data-heatmap-action]').forEach(el => {
        el.addEventListener('click', () => {
            const action = el.getAttribute('data-heatmap-action');
            heatmapNewDropdown.classList.remove('heatmap-dropdown-open');
            
            if (action === 'new-internal') {
                heatmapNavigateTo('internal');
            } else if (action === 'new-external') {
                heatmapNavigateTo('external');
            }
        });
    });

    // ========================================
    // FORMS
    // ========================================
    const heatmapFormInternal = document.getElementById('heatmap-form-internal');
    const heatmapFormExternal = document.getElementById('heatmap-form-external');

    heatmapFormInternal.addEventListener('submit', async (e) => {
        e.preventDefault();
        const submitBtn = heatmapFormInternal.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        submitBtn.textContent = 'Saving...';
        
        try {
            const auditData = {
                title: document.getElementById('heatmap-internal-title').value,
                description: document.getElementById('heatmap-internal-description').value,
                date: document.getElementById('heatmap-internal-date').value
            };
            await heatmapCreateAudit('internal', auditData);
            heatmapFormInternal.reset();
            heatmapNavigateTo('home');
        } catch (error) {
            alert('Failed to save audit. Please try again.');
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Save Internal Audit';
        }
    });

    heatmapFormExternal.addEventListener('submit', async (e) => {
        e.preventDefault();
        const submitBtn = heatmapFormExternal.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        submitBtn.textContent = 'Saving...';
        
        try {
            const auditData = {
                title: document.getElementById('heatmap-external-title').value,
                description: document.getElementById('heatmap-external-description').value,
                date: document.getElementById('heatmap-external-date').value
            };
            await heatmapCreateAudit('external', auditData);
            heatmapFormExternal.reset();
            heatmapNavigateTo('home');
        } catch (error) {
            alert('Failed to save audit. Please try again.');
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Save External Audit';
        }
    });

    // ========================================
    // THEME MANAGEMENT
    // ========================================
    function heatmapInitTheme() {
        const savedTheme = localStorage.getItem('heatmap-theme') || 'light';
        document.documentElement.setAttribute('data-heatmap-theme', savedTheme);
        heatmapUpdateThemeIcon(savedTheme);
    }

    function heatmapToggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-heatmap-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-heatmap-theme', newTheme);
        localStorage.setItem('heatmap-theme', newTheme);
        heatmapUpdateThemeIcon(newTheme);
    }

    function heatmapUpdateThemeIcon(theme) {
        heatmapThemeToggle.textContent = theme === 'dark' ? '☀️' : '🌙';
    }

    // ========================================
    // YEAR SELECTOR
    // ========================================
    function heatmapRenderYearSelector() {
        heatmapYearSelector.innerHTML = '';
        
        for (let year = HEATMAP_CURRENT_YEAR; year >= HEATMAP_START_YEAR; year--) {
            const btn = document.createElement('button');
            btn.className = 'heatmap-year-btn';
            btn.setAttribute('data-heatmap-year', year);
            btn.textContent = year;
            
            if (year === heatmapSelectedYear) {
                btn.classList.add('heatmap-year-active');
            }
            
            btn.addEventListener('click', () => heatmapSelectYear(year));
            heatmapYearSelector.appendChild(btn);
        }
    }

    async function heatmapSelectYear(year) {
        heatmapSelectedYear = year;
        
        document.querySelectorAll('.heatmap-year-btn').forEach(btn => {
            btn.classList.toggle('heatmap-year-active', 
                parseInt(btn.getAttribute('data-heatmap-year')) === year);
        });
        
        await heatmapLoadHeatmapData(year);
        heatmapRenderGrid();
    }

    // ========================================
    // FILTER TOGGLE
    // ========================================
    function heatmapToggleFilter(type) {
        heatmapActiveFilters[type] = !heatmapActiveFilters[type];
        
        if (!heatmapActiveFilters.internal && !heatmapActiveFilters.external) {
            heatmapActiveFilters[type] = true;
            return;
        }
        
        heatmapFilterBtns.forEach(btn => {
            const btnType = btn.getAttribute('data-heatmap-type');
            btn.classList.toggle('heatmap-filter-active', heatmapActiveFilters[btnType]);
        });
        
        heatmapRenderGrid();
    }

    // ========================================
    // RENDER HEATMAP GRID
    // ========================================
    function heatmapRenderGrid() {
        heatmapGrid.innerHTML = '';
        heatmapMonthsRow.innerHTML = '';
        
        const year = heatmapSelectedYear;
        const startDate = new Date(year, 0, 1);
        const dayOfWeek = startDate.getDay();
        const gridStartDate = new Date(startDate);
        gridStartDate.setDate(startDate.getDate() - dayOfWeek);

        let heatmapRenderedMonths = new Set();
        let heatmapTotalAudits = 0;

        for (let i = 0; i < HEATMAP_TOTAL_WEEKS * 7; i++) {
            const currentDate = new Date(gridStartDate.getTime() + (i * HEATMAP_DAY_MS));
            
            const cell = document.createElement('div');
            cell.classList.add('heatmap-cell');
            
            const isTargetYear = currentDate.getFullYear() === year;
            
            let count = 0;
            let data = { internal: 0, external: 0 };
            
            if (isTargetYear) {
                data = heatmapGetAuditData(currentDate);
                count = heatmapGetFilteredCount(data);
                heatmapTotalAudits += count;
            }

            // Assign Level Class
            if (count === 0) cell.classList.add('heatmap-l0');
            else if (count <= 2) cell.classList.add('heatmap-l1');
            else if (count <= 4) cell.classList.add('heatmap-l2');
            else if (count <= 7) cell.classList.add('heatmap-l3');
            else cell.classList.add('heatmap-l4');

            // Tooltip
            const dateStr = currentDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
            let heatmapTooltipText = count === 0 
                ? `No audits on ${dateStr}` 
                : `${count} audit${count > 1 ? 's' : ''} on ${dateStr}`;
            
            if (count > 0 && isTargetYear) {
                const details = [];
                if (heatmapActiveFilters.internal && data.internal > 0) {
                    details.push(`${data.internal} internal`);
                }
                if (heatmapActiveFilters.external && data.external > 0) {
                    details.push(`${data.external} external`);
                }
                if (details.length > 0) {
                    heatmapTooltipText += ` (${details.join(', ')})`;
                }
            }
            
            cell.addEventListener('mouseenter', (e) => {
                heatmapTooltip.textContent = heatmapTooltipText;
                heatmapTooltip.style.opacity = '1';
                
                const rect = cell.getBoundingClientRect();
                heatmapTooltip.style.left = `${rect.left + window.scrollX - (heatmapTooltip.offsetWidth / 2) + 7}px`;
                heatmapTooltip.style.top = `${rect.top + window.scrollY - 35}px`;
            });

            cell.addEventListener('mouseleave', () => {
                heatmapTooltip.style.opacity = '0';
            });

            // Month Labels
            if (i % 7 === 0) {
                const midWeekDate = new Date(currentDate.getTime() + (3 * HEATMAP_DAY_MS));
                const monthIndex = midWeekDate.getMonth();
                
                const monthSpan = document.createElement('span');
                if (!heatmapRenderedMonths.has(monthIndex) && midWeekDate.getFullYear() === year) {
                    monthSpan.textContent = HEATMAP_MONTH_NAMES[monthIndex];
                    heatmapRenderedMonths.add(monthIndex);
                } else {
                    monthSpan.textContent = "";
                }
                heatmapMonthsRow.appendChild(monthSpan);
            }

            heatmapGrid.appendChild(cell);
        }

        // Update header
        heatmapTotalCountEl.textContent = heatmapTotalAudits;
        heatmapYearDisplayEl.textContent = year;
        
        // Show connection status
        updateConnectionStatus();
    }

    // ========================================
    // CONNECTION STATUS INDICATOR
    // ========================================
    function updateConnectionStatus() {
        let statusEl = document.getElementById('heatmap-connection-status');
        if (!statusEl) {
            statusEl = document.createElement('div');
            statusEl.id = 'heatmap-connection-status';
            statusEl.style.cssText = 'position: fixed; bottom: 10px; right: 10px; padding: 8px 12px; border-radius: 4px; font-size: 12px; z-index: 1000;';
            document.body.appendChild(statusEl);
        }
        
        if (heatmapIsOnline) {
            statusEl.textContent = '🟢 Connected to Database';
            statusEl.style.background = '#d4edda';
            statusEl.style.color = '#155724';
        } else {
            statusEl.textContent = '🔴 Offline Mode (localStorage)';
            statusEl.style.background = '#f8d7da';
            statusEl.style.color = '#721c24';
        }
    }

    // ========================================
    // EVENT LISTENERS
    // ========================================
    heatmapThemeToggle.addEventListener('click', heatmapToggleTheme);
    
    heatmapFilterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const type = btn.getAttribute('data-heatmap-type');
            heatmapToggleFilter(type);
        });
    });

    // ========================================
    // INITIALIZE
    // ========================================
    async function heatmapInit() {
        heatmapInitTheme();
        heatmapRenderYearSelector();
        
        // Check API and load data
        await heatmapCheckHealth();
        await heatmapLoadHeatmapData(heatmapSelectedYear);
        heatmapRenderGrid();
    }

    heatmapInit();
});
