document.addEventListener('DOMContentLoaded', function() {
    // ========================================
    // DEFENSIVE PROGRAMMING: DOM ELEMENT VALIDATION
    // ========================================
    /**
     * Safely retrieves a DOM element by ID with null check.
     * Follows fail-fast principle - logs warning but doesn't crash.
     * @param {string} id - Element ID
     * @param {boolean} required - If true, logs error when not found
     * @returns {HTMLElement|null}
     */
    function safeGetElement(id, required = true) {
        const element = document.getElementById(id);
        if (!element && required) {
            console.warn(`[Heatmap] Required DOM element not found: #${id}`);
        }
        return element;
    }

    /**
     * Safely retrieves multiple DOM elements by selector.
     * @param {string} selector - CSS selector
     * @returns {NodeList}
     */
    function safeQueryAll(selector) {
        const elements = document.querySelectorAll(selector);
        if (elements.length === 0) {
            console.warn(`[Heatmap] No elements found for selector: ${selector}`);
        }
        return elements;
    }

    // ========================================
    // DOM ELEMENTS (with null safety)
    // ========================================
    const heatmapGrid = safeGetElement('heatmap-grid');
    const heatmapMonthsRow = safeGetElement('heatmap-months-row');
    const heatmapTooltip = safeGetElement('heatmap-tooltip');
    const heatmapTotalCountEl = safeGetElement('heatmap-total-count');
    const heatmapYearDisplayEl = safeGetElement('heatmap-year-display');
    const heatmapThemeToggle = safeGetElement('heatmap-theme-toggle');
    const heatmapYearSelector = safeGetElement('heatmap-year-selector');
    const heatmapFilterBtns = safeQueryAll('.heatmap-filter');
    const heatmapNewDropdown = safeGetElement('heatmap-new-dropdown');
    const heatmapNewBtn = safeGetElement('heatmap-new-btn');

    // ========================================
    // CONFIG (aligned with context map)
    // ========================================
    const HEATMAP_API_BASE = 'http://localhost:8000/api';  // Python FastAPI server
    const HEATMAP_START_YEAR = 2024;
    const HEATMAP_CURRENT_YEAR = new Date().getFullYear();
    const HEATMAP_TOTAL_WEEKS = 53;
    const HEATMAP_DAY_MS = 24 * 60 * 60 * 1000;
    const HEATMAP_MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const HEATMAP_STORAGE_KEY = 'heatmap-audit-data';  // Fallback for offline mode
    
    // Validation constants (aligned with backend)
    const VALIDATION = {
        MAX_TITLE_LENGTH: 255,
        VALID_AUDIT_TYPES: ['internal', 'external'],
        DATE_PATTERN: /^\d{4}-\d{2}-\d{2}$/,
        MIN_YEAR: 1900,
        MAX_YEAR: 2100
    };

    // ========================================
    // STATE
    // ========================================
    let heatmapSelectedYear = HEATMAP_CURRENT_YEAR;
    let heatmapActiveFilters = { internal: true, external: true };
    let heatmapData = {};  // Cache for heatmap data from API
    let heatmapIsOnline = true;  // Track API connection status

    // ========================================
    // INPUT VALIDATION HELPERS
    // ========================================
    /**
     * Validates audit form data before submission.
     * Mirrors backend validation for fail-fast UX.
     * @param {Object} auditData - {title, description, date}
     * @returns {{valid: boolean, errors: string[]}}
     */
    function validateAuditData(auditData) {
        const errors = [];
        
        // Title validation
        if (!auditData.title || !auditData.title.trim()) {
            errors.push('Title is required');
        } else if (auditData.title.length > VALIDATION.MAX_TITLE_LENGTH) {
            errors.push(`Title cannot exceed ${VALIDATION.MAX_TITLE_LENGTH} characters`);
        }
        
        // Date validation
        if (!auditData.date) {
            errors.push('Date is required');
        } else if (!VALIDATION.DATE_PATTERN.test(auditData.date)) {
            errors.push('Date must be in YYYY-MM-DD format');
        } else {
            // Validate actual date value
            const [year, month, day] = auditData.date.split('-').map(Number);
            const testDate = new Date(year, month - 1, day);
            if (testDate.getFullYear() !== year || 
                testDate.getMonth() !== month - 1 || 
                testDate.getDate() !== day) {
                errors.push('Invalid date value');
            }
        }
        
        return { valid: errors.length === 0, errors };
    }

    /**
     * Sanitizes user input to prevent XSS.
     * @param {string} input - Raw user input
     * @returns {string} - Sanitized string
     */
    function sanitizeInput(input) {
        if (typeof input !== 'string') return '';
        return input
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#x27;');
    }

    /**
     * Safely parses JSON with error handling.
     * @param {string} jsonString - JSON string to parse
     * @param {*} defaultValue - Default value if parsing fails
     * @returns {*} - Parsed object or default value
     */
    function safeJsonParse(jsonString, defaultValue = null) {
        try {
            return JSON.parse(jsonString);
        } catch (error) {
            console.warn('[Heatmap] JSON parse failed:', error.message);
            return defaultValue;
        }
    }

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
                // Extract error message from response if available
                let errorDetail = `API Error: ${response.status}`;
                try {
                    const errorBody = await response.json();
                    if (errorBody.detail) {
                        errorDetail = errorBody.detail;
                    }
                } catch {
                    // Ignore JSON parse errors for error response
                }
                throw new Error(errorDetail);
            }
            
            heatmapIsOnline = true;
            return await response.json();
        } catch (error) {
            console.error('[Heatmap] API request failed:', error);
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

    // UPDATE - Update an audit (with error handling)
    async function heatmapUpdateAudit(auditId, auditData) {
        // Input validation
        if (!auditId || auditId <= 0) {
            throw new Error('Invalid audit ID');
        }
        
        // Validate audit data if provided
        if (auditData.title !== undefined) {
            const validation = validateAuditData({ 
                title: auditData.title, 
                date: auditData.audit_date || '2025-01-01' // Dummy date for validation
            });
            if (!validation.valid) {
                throw new Error(validation.errors.join(', '));
            }
        }
        
        try {
            const result = await heatmapApiRequest(`/audits/${auditId}`, {
                method: 'PUT',
                body: JSON.stringify(auditData)
            });
            // Refresh heatmap data after updating
            await heatmapLoadHeatmapData(heatmapSelectedYear);
            return result;
        } catch (error) {
            console.error('[Heatmap] Update audit failed:', error);
            throw error;
        }
    }

    // DELETE - Delete an audit (with error handling)
    async function heatmapDeleteAudit(auditId) {
        // Input validation
        if (!auditId || auditId <= 0) {
            throw new Error('Invalid audit ID');
        }
        
        try {
            const result = await heatmapApiRequest(`/audits/${auditId}`, {
                method: 'DELETE'
            });
            // Refresh heatmap data after deleting
            await heatmapLoadHeatmapData(heatmapSelectedYear);
            return result;
        } catch (error) {
            console.error('[Heatmap] Delete audit failed:', error);
            throw error;
        }
    }

    // ========================================
    // OFFLINE FALLBACK (localStorage) - with safe JSON parsing
    // ========================================
    function heatmapLoadDataOffline() {
        const stored = localStorage.getItem(HEATMAP_STORAGE_KEY);
        if (stored) {
            const data = safeJsonParse(stored, { internal: [], external: [] });
            // Convert to heatmap format
            heatmapData = {};
            ['internal', 'external'].forEach(type => {
                const audits = Array.isArray(data[type]) ? data[type] : [];
                audits.forEach(audit => {
                    if (audit && audit.date) {
                        if (!heatmapData[audit.date]) {
                            heatmapData[audit.date] = { internal: 0, external: 0, total: 0 };
                        }
                        heatmapData[audit.date][type]++;
                        heatmapData[audit.date].total++;
                    }
                });
            });
        }
        return heatmapData;
    }

    function heatmapCreateAuditOffline(type, auditData) {
        // Validate type
        if (!VALIDATION.VALID_AUDIT_TYPES.includes(type)) {
            console.error('[Heatmap] Invalid audit type for offline create:', type);
            return null;
        }
        
        const stored = localStorage.getItem(HEATMAP_STORAGE_KEY);
        const data = safeJsonParse(stored, { internal: [], external: [] });
        
        // Ensure arrays exist
        if (!Array.isArray(data.internal)) data.internal = [];
        if (!Array.isArray(data.external)) data.external = [];
        
        const audit = {
            id: Date.now().toString(),
            title: sanitizeInput(auditData.title),
            description: sanitizeInput(auditData.description || ''),
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
    // DROPDOWN (with null safety)
    // ========================================
    if (heatmapNewBtn && heatmapNewDropdown) {
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
    }

    // ========================================
    // FORMS (with client-side validation)
    // ========================================
    const heatmapFormInternal = safeGetElement('heatmap-form-internal');
    const heatmapFormExternal = safeGetElement('heatmap-form-external');

    /**
     * Displays validation errors to user.
     * @param {HTMLFormElement} form - Form element
     * @param {string[]} errors - Array of error messages
     */
    function showFormErrors(form, errors) {
        // Remove existing error messages
        const existingErrors = form.querySelectorAll('.heatmap-form-error');
        existingErrors.forEach(el => el.remove());
        
        if (errors.length > 0) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'heatmap-form-error';
            errorDiv.style.cssText = 'color: #dc3545; background: #f8d7da; padding: 10px; border-radius: 4px; margin-bottom: 10px;';
            errorDiv.innerHTML = errors.map(e => `• ${sanitizeInput(e)}`).join('<br>');
            form.insertBefore(errorDiv, form.firstChild);
        }
    }

    /**
     * Generic form submission handler with validation.
     * @param {HTMLFormElement} form - Form element
     * @param {string} auditType - 'internal' or 'external'
     * @param {string} submitBtnText - Original button text
     */
    function handleFormSubmit(form, auditType, submitBtnText) {
        if (!form) return;
        
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const submitBtn = form.querySelector('button[type="submit"]');
            if (!submitBtn) return;
            
            // Get form values safely
            const titleEl = form.querySelector(`#heatmap-${auditType}-title`);
            const descEl = form.querySelector(`#heatmap-${auditType}-description`);
            const dateEl = form.querySelector(`#heatmap-${auditType}-date`);
            
            const auditData = {
                title: titleEl ? titleEl.value : '',
                description: descEl ? descEl.value : '',
                date: dateEl ? dateEl.value : ''
            };
            
            // Client-side validation (fail-fast, better UX)
            const validation = validateAuditData(auditData);
            if (!validation.valid) {
                showFormErrors(form, validation.errors);
                return;
            }
            
            // Clear any previous errors
            showFormErrors(form, []);
            
            submitBtn.disabled = true;
            submitBtn.textContent = 'Saving...';
            
            try {
                await heatmapCreateAudit(auditType, auditData);
                form.reset();
                heatmapNavigateTo('home');
            } catch (error) {
                const errorMessage = error.message || 'Failed to save audit. Please try again.';
                showFormErrors(form, [errorMessage]);
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = submitBtnText;
            }
        });
    }

    // Initialize form handlers
    handleFormSubmit(heatmapFormInternal, 'internal', 'Save Internal Audit');
    handleFormSubmit(heatmapFormExternal, 'external', 'Save External Audit');

    // ========================================
    // THEME MANAGEMENT (with null safety)
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
        if (heatmapThemeToggle) {
            heatmapThemeToggle.textContent = theme === 'dark' ? '☀️' : '🌙';
        }
    }

    // ========================================
    // YEAR SELECTOR (with null safety)
    // ========================================
    function heatmapRenderYearSelector() {
        if (!heatmapYearSelector) return;
        
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
    // RENDER HEATMAP GRID (with null safety)
    // ========================================
    function heatmapRenderGrid() {
        if (!heatmapGrid || !heatmapMonthsRow) return;
        
        heatmapGrid.innerHTML = '';
        heatmapMonthsRow.innerHTML = '';
        
        const year = heatmapSelectedYear;
        
        // Calculate exact grid boundaries for the target year only
        const yearStart = new Date(year, 0, 1);  // Jan 1
        const yearEnd = new Date(year, 11, 31);  // Dec 31
        
        // Grid starts on the Sunday of the week containing Jan 1
        const startDayOfWeek = yearStart.getDay(); // 0=Sun, 6=Sat
        const gridStartDate = new Date(yearStart);
        gridStartDate.setDate(yearStart.getDate() - startDayOfWeek);
        
        // Grid ends on the Saturday of the week containing Dec 31
        const endDayOfWeek = yearEnd.getDay();
        const gridEndDate = new Date(yearEnd);
        gridEndDate.setDate(yearEnd.getDate() + (6 - endDayOfWeek));
        
        // Calculate total days to render (always complete weeks)
        const totalDays = Math.round((gridEndDate - gridStartDate) / HEATMAP_DAY_MS) + 1;
        const totalWeeks = Math.ceil(totalDays / 7);

        let heatmapRenderedMonths = new Set();
        let heatmapTotalAudits = 0;

        for (let i = 0; i < totalWeeks * 7; i++) {
            const currentDate = new Date(gridStartDate.getTime() + (i * HEATMAP_DAY_MS));
            
            // Generate ISO date string for unique identification (YYYY-MM-DD)
            const isoDateStr = currentDate.toISOString().split('T')[0];
            
            const cell = document.createElement('div');
            cell.classList.add('heatmap-cell');
            
            // Unique identifier for each heatmap box
            cell.id = `heatmap-box-${isoDateStr}`;
            cell.setAttribute('data-heatmap-date', isoDateStr);
            
            // Check if date belongs to the target year
            const isTargetYear = currentDate.getFullYear() === year;
            
            // Hide cells outside the target year (preserve grid structure)
            if (!isTargetYear) {
                cell.classList.add('heatmap-cell-hidden');
            }
            
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
            
            // Tooltip with null safety
            cell.addEventListener('mouseenter', (e) => {
                if (heatmapTooltip) {
                    heatmapTooltip.textContent = heatmapTooltipText;
                    heatmapTooltip.style.opacity = '1';
                    
                    const rect = cell.getBoundingClientRect();
                    heatmapTooltip.style.left = `${rect.left + window.scrollX - (heatmapTooltip.offsetWidth / 2) + 7}px`;
                    heatmapTooltip.style.top = `${rect.top + window.scrollY - 35}px`;
                }
            });

            cell.addEventListener('mouseleave', () => {
                if (heatmapTooltip) {
                    heatmapTooltip.style.opacity = '0';
                }
            });

            // Month Labels (one per week column)
            if (i % 7 === 0) {
                const midWeekDate = new Date(currentDate.getTime() + (3 * HEATMAP_DAY_MS));
                const monthIndex = midWeekDate.getMonth();
                const midWeekYear = midWeekDate.getFullYear();
                
                const monthSpan = document.createElement('span');
                // Only show month label if: in target year AND first occurrence of that month
                if (midWeekYear === year && !heatmapRenderedMonths.has(monthIndex)) {
                    monthSpan.textContent = HEATMAP_MONTH_NAMES[monthIndex];
                    heatmapRenderedMonths.add(monthIndex);
                } else {
                    monthSpan.textContent = '';
                }
                heatmapMonthsRow.appendChild(monthSpan);
            }

            heatmapGrid.appendChild(cell);
        }

        // Update header (with null safety)
        if (heatmapTotalCountEl) {
            heatmapTotalCountEl.textContent = heatmapTotalAudits;
        }
        if (heatmapYearDisplayEl) {
            heatmapYearDisplayEl.textContent = year;
        }
        
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
    // EVENT LISTENERS (with null safety)
    // ========================================
    if (heatmapThemeToggle) {
        heatmapThemeToggle.addEventListener('click', heatmapToggleTheme);
    }
    
    // NodeList.forEach safely handles empty lists
    heatmapFilterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const type = btn.getAttribute('data-heatmap-type');
            heatmapToggleFilter(type);
        });
    });

    // ========================================
    // INITIALIZE (with error boundary)
    // ========================================
    async function heatmapInit() {
        try {
            heatmapInitTheme();
            heatmapRenderYearSelector();
            
            // Check API and load data
            await heatmapCheckHealth();
            await heatmapLoadHeatmapData(heatmapSelectedYear);
            heatmapRenderGrid();
        } catch (error) {
            console.error('Heatmap initialization failed:', error);
            // Graceful degradation - show offline mode
            heatmapIsOnline = false;
            heatmapRenderGrid();
        }
    }

    heatmapInit();
});
