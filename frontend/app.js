/**
 * SIVI AFD Validator - Frontend Application
 * Redesigned with WeTransfer-inspired simplicity
 */

// State
let selectedFile = null;
let validationResult = null;
let allFindings = [];
let serverHasApiKey = false;
let chatConversationId = null;
let chatFindingContext = null;

// Status management state
let findingStatuses = {};
let fileValidationId = null;

// Session & XML viewer state
let originalXmlContent = null;  // Stores the original XML content for viewing

// Grouped view state
let currentCategory = 'all';
let groupedFindings = {};
let expandedGroups = new Set();
let collapsedThemas = new Set();

// Status constants
const STATUS_OPEN = 'OPEN';
const STATUS_GEACCEPTEERD = 'GEACCEPTEERD';
const STATUS_GENEGEERD = 'GENEGEERD';
const STATUS_OPGELOST = 'OPGELOST';

// DOM Elements - Upload View
const uploadView = document.getElementById('uploadView');
const uploadZone = document.getElementById('uploadZone');
const fileInput = document.getElementById('fileInput');
const folderInput = document.getElementById('folderInput');
const addXmlBtn = document.getElementById('addXmlBtn');
const addFolderBtn = document.getElementById('addFolderBtn');
const selectedFileDiv = document.getElementById('selectedFile');
const fileNameSpan = document.getElementById('fileName');
const removeFileBtn = document.getElementById('removeFile');
const validateButton = document.getElementById('validateButton');
const uploadButtonsDiv = document.querySelector('.upload-buttons');
const optionsAccordion = document.getElementById('optionsAccordion');
const optionsToggle = document.getElementById('optionsToggle');

// Engine checkboxes
const engine1 = document.getElementById('engine1');
const engine2 = document.getElementById('engine2');
const engine3 = document.getElementById('engine3');
const apiKeySection = document.getElementById('apiKeySection');
const apiKeyInput = document.getElementById('apiKey');

// Results View
const resultsView = document.getElementById('resultsView');
const backButton = document.getElementById('backButton');
const resultsFileName = document.getElementById('resultsFileName');

// Summary elements
const kritiekCount = document.getElementById('kritiekCount');
const aandachtCount = document.getElementById('aandachtCount');
const infoCount = document.getElementById('infoCount');
const totalCount = document.getElementById('totalCount');
const openCount = document.getElementById('openCount');
const contractsInfo = document.getElementById('contractsInfo');
const enginesInfo = document.getElementById('enginesInfo');

// Filter elements
const criticalityFilter = document.getElementById('criticalityFilter');
const statusFilter = document.getElementById('statusFilter');
const severityFilter = document.getElementById('severityFilter');
const engineFilter = document.getElementById('engineFilter');
const searchFilter = document.getElementById('searchFilter');
const findingsBody = document.getElementById('findingsBody');
const noFindings = document.getElementById('noFindings');
const findingsGrouped = document.getElementById('findingsGrouped');
const findingsTableWrapper = document.getElementById('findingsTableWrapper');

// Modal elements
const bulkActionModal = document.getElementById('bulkActionModal');
const bulkActionMessage = document.getElementById('bulkActionMessage');
const bulkActionDetails = document.getElementById('bulkActionDetails');
const bulkActionSingle = document.getElementById('bulkActionSingle');
const bulkActionAll = document.getElementById('bulkActionAll');

// Export buttons
const downloadJsonBtn = document.getElementById('downloadJson');
const downloadExcelBtn = document.getElementById('downloadExcel');
const downloadSessionBtn = document.getElementById('downloadSession');
const loadSessionBtn = document.getElementById('loadSessionBtn');
const sessionFileInput = document.getElementById('sessionFileInput');

// Toast
const errorToast = document.getElementById('errorToast');
const errorText = document.getElementById('errorText');

// Initialize
document.addEventListener('DOMContentLoaded', init);

async function init() {
    await loadServerConfig();
    setupFileUpload();
    setupEngineOptions();
    setupOptionsAccordion();
    setupFilters();
    setupCategoryTabs();
    setupExports();
    setupValidation();
    setupChat();
    setupBulkActionModal();
    setupNavigation();
    setupSessionHandling();
    setupXmlViewer();
}

// Options Accordion Toggle
function setupOptionsAccordion() {
    if (optionsToggle && optionsAccordion) {
        optionsToggle.addEventListener('click', () => {
            optionsAccordion.classList.toggle('open');
        });
        // Start open by default when shown
        optionsAccordion.classList.add('open');
    }
}

async function loadServerConfig() {
    try {
        const response = await fetch('/api/config');
        if (response.ok) {
            const config = await response.json();
            serverHasApiKey = config.has_api_key || false;
        }
    } catch (error) {
        console.warn('Could not load server config:', error);
    }
}

// Navigation between views
function setupNavigation() {
    backButton.addEventListener('click', () => {
        showUploadView();
    });
}

function showUploadView() {
    // Fade out results view
    resultsView.style.opacity = '0';
    resultsView.style.transform = 'translateY(-20px)';

    setTimeout(() => {
        resultsView.hidden = true;
        resultsView.style.opacity = '';
        resultsView.style.transform = '';

        uploadView.hidden = false;
        uploadView.style.opacity = '0';
        uploadView.style.transform = 'translateY(20px)';

        // Scroll to top smoothly
        window.scrollTo({ top: 0, behavior: 'smooth' });

        // Fade in upload view
        requestAnimationFrame(() => {
            uploadView.style.transition = 'opacity 0.4s ease-out, transform 0.4s ease-out';
            uploadView.style.opacity = '1';
            uploadView.style.transform = 'translateY(0)';

            setTimeout(() => {
                uploadView.style.transition = '';
            }, 400);
        });

        hideResults();
    }, 300);
}

function showResultsView() {
    // Fade out upload view
    uploadView.style.opacity = '0';
    uploadView.style.transform = 'translateY(20px)';

    setTimeout(() => {
        uploadView.hidden = true;
        uploadView.style.opacity = '';
        uploadView.style.transform = '';

        resultsView.hidden = false;
        resultsView.style.opacity = '0';
        resultsView.style.transform = 'translateY(20px)';

        if (selectedFile) {
            resultsFileName.textContent = selectedFile.name;
        }

        // Scroll to top smoothly to show results
        window.scrollTo({ top: 0, behavior: 'smooth' });

        // Fade in results view
        requestAnimationFrame(() => {
            resultsView.style.transition = 'opacity 0.4s ease-out, transform 0.4s ease-out';
            resultsView.style.opacity = '1';
            resultsView.style.transform = 'translateY(0)';

            setTimeout(() => {
                resultsView.style.transition = '';
            }, 400);
        });
    }, 300);
}

// File Upload
function setupFileUpload() {
    // Add XML button
    addXmlBtn.addEventListener('click', () => fileInput.click());

    // Add folders button
    addFolderBtn.addEventListener('click', () => folderInput.click());

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });

    // Handle folder selection - find XML files
    folderInput.addEventListener('change', (e) => {
        const files = Array.from(e.target.files);
        const xmlFile = files.find(f => f.name.toLowerCase().endsWith('.xml'));
        if (xmlFile) {
            handleFileSelect(xmlFile);
        } else if (files.length > 0) {
            showError('Geen XML bestand gevonden in de geselecteerde map.');
        }
    });

    // Drag and drop on the card
    const cardInner = document.querySelector('.upload-card-inner');

    cardInner.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('drag-over');
    });

    cardInner.addEventListener('dragleave', (e) => {
        e.preventDefault();
        if (!cardInner.contains(e.relatedTarget)) {
            uploadZone.classList.remove('drag-over');
        }
    });

    cardInner.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('drag-over');

        if (e.dataTransfer.files.length > 0) {
            const file = e.dataTransfer.files[0];
            if (file.name.toLowerCase().endsWith('.xml')) {
                handleFileSelect(file);
            } else {
                showError('Selecteer een XML bestand.');
            }
        }
    });

    removeFileBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        clearFile();
    });
}

function handleFileSelect(file) {
    if (!file.name.toLowerCase().endsWith('.xml')) {
        showError('Selecteer een XML bestand.');
        return;
    }

    selectedFile = file;
    fileNameSpan.textContent = file.name;
    selectedFileDiv.hidden = false;
    if (uploadButtonsDiv) uploadButtonsDiv.hidden = true;

    // Show options accordion when file is selected
    if (optionsAccordion) {
        optionsAccordion.hidden = false;
        optionsAccordion.classList.add('open');
    }

    hideError();
    updateValidateButton();
}

function clearFile() {
    selectedFile = null;
    fileInput.value = '';
    if (folderInput) folderInput.value = '';
    selectedFileDiv.hidden = true;
    if (uploadButtonsDiv) uploadButtonsDiv.hidden = false;

    // Hide options accordion when file is cleared
    if (optionsAccordion) {
        optionsAccordion.hidden = true;
    }

    updateValidateButton();
}

// Engine Options
function setupEngineOptions() {
    engine3.addEventListener('change', () => {
        apiKeySection.hidden = !engine3.checked || serverHasApiKey;
        updateValidateButton();
    });

    [engine1, engine2, engine3].forEach(cb => {
        cb.addEventListener('change', updateValidateButton);
    });
}

function getSelectedEngines() {
    const engines = [];
    if (engine1.checked) engines.push(1);
    if (engine2.checked) engines.push(2);
    if (engine3.checked) engines.push(3);
    return engines;
}

function updateValidateButton() {
    const hasFile = selectedFile !== null;
    const hasEngines = getSelectedEngines().length > 0;
    const needsApiKey = engine3.checked && !serverHasApiKey && !apiKeyInput.value.trim();

    validateButton.disabled = !hasFile || !hasEngines || needsApiKey;
}

// Validation
function setupValidation() {
    validateButton.addEventListener('click', runValidation);
    if (apiKeyInput) {
        apiKeyInput.addEventListener('input', updateValidateButton);
    }
}

async function runValidation() {
    if (!selectedFile) return;

    const engines = getSelectedEngines();
    if (engines.length === 0) return;

    setLoading(true);
    hideError();

    try {
        // Read and store the original XML content for the XML viewer
        originalXmlContent = await readFileAsText(selectedFile);

        const formData = new FormData();
        formData.append('file', selectedFile);

        const headers = {};
        if (engine3.checked && apiKeyInput && apiKeyInput.value.trim()) {
            headers['X-API-Key'] = apiKeyInput.value.trim();
        }

        const response = await fetch(`/api/validate?engines=${engines.join(',')}`, {
            method: 'POST',
            headers: headers,
            body: formData
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `Server error: ${response.status}`);
        }

        validationResult = await response.json();
        allFindings = validationResult.findings || [];

        displayResults();
        showResultsView();
    } catch (error) {
        showError(error.message);
    } finally {
        setLoading(false);
    }
}

/**
 * Read a file as text
 */
function readFileAsText(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target.result);
        reader.onerror = (e) => reject(new Error('Could not read file'));
        reader.readAsText(file);
    });
}

function setLoading(loading) {
    const buttonText = validateButton.querySelector('.btn-text');

    if (loading) {
        validateButton.disabled = true;
        buttonText.textContent = 'Valideren...';
    } else {
        updateValidateButton();
        buttonText.textContent = 'Valideren';
    }
}

// Results Display
function displayResults() {
    if (!validationResult) return;

    const summary = validationResult.summary || {};
    const byCriticality = summary.by_criticality || {};
    const metadata = validationResult.metadata || {};

    generateFileValidationId();
    loadStatusesFromStorage();

    kritiekCount.textContent = byCriticality.KRITIEK || 0;
    aandachtCount.textContent = byCriticality.AANDACHT || 0;
    infoCount.textContent = byCriticality.INFO || 0;
    totalCount.textContent = summary.total || 0;

    updateOpenCount();

    const contracts = metadata.contracts_parsed || summary.contracts_with_findings || 0;
    contractsInfo.textContent = `${contracts} contract(en)`;

    const enginesUsed = metadata.engines_requested || [];
    const engineNames = { 1: 'Schema', 2: 'Rules', 3: 'AI' };
    enginesInfo.textContent = enginesUsed.map(e => engineNames[e]).join(', ');

    // Show/hide XML available badge
    const xmlBadge = document.getElementById('xmlAvailableBadge');
    if (xmlBadge) {
        xmlBadge.hidden = !originalXmlContent;
    }

    // Reset category to all
    currentCategory = 'all';
    expandedGroups.clear();

    // Update category tab visuals
    document.querySelectorAll('.category-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.category === 'all');
    });

    // Update category counts
    updateCategoryCounts();

    // Update progress bar
    updateProgressBar();

    // Render grouped view
    renderFindingGroups();
}

function renderFindings() {
    // Use the grouped view by default
    renderFindingGroups();
}

// Legacy table view (kept for reference/future use)
function renderFindingsTable() {
    const filtered = filterFindings();

    findingsBody.innerHTML = '';

    if (filtered.length === 0) {
        noFindings.hidden = false;
        document.getElementById('findingsTable').hidden = true;
        return;
    }

    noFindings.hidden = true;
    document.getElementById('findingsTable').hidden = false;

    filtered.forEach((finding, index) => {
        const row = document.createElement('tr');
        const findingId = generateFindingId(finding, index);
        const status = findingStatuses[findingId] || STATUS_OPEN;

        const severityClass = finding.severity.toLowerCase();
        const criticalityClass = (finding.criticality || 'AANDACHT').toLowerCase();

        row.classList.add(`status-${status.toLowerCase()}`);
        row.dataset.findingId = findingId;
        row.dataset.bulkKey = getBulkKey(finding);

        // Determine badge class based on criticality
        let critBadgeClass = 'badge-info';
        if (criticalityClass === 'kritiek') critBadgeClass = 'badge-critical';
        else if (criticalityClass === 'aandacht') critBadgeClass = 'badge-warning';

        // Determine badge class based on severity
        let sevBadgeClass = 'badge-info';
        if (severityClass === 'fout') sevBadgeClass = 'badge-fout';
        else if (severityClass === 'waarschuwing') sevBadgeClass = 'badge-waarschuwing';

        row.innerHTML = `
            <td><span class="badge ${critBadgeClass}">${escapeHtml(finding.criticality || 'AANDACHT')}</span></td>
            <td><span class="badge ${sevBadgeClass}">${escapeHtml(finding.severity)}</span></td>
            <td>${escapeHtml(finding.code)}</td>
            <td>${escapeHtml(finding.contract)}</td>
            <td>${escapeHtml(finding.entiteit)}</td>
            <td>${escapeHtml(finding.label)}</td>
            <td title="${escapeHtml(finding.omschrijving)}">${escapeHtml(truncate(finding.omschrijving, 60))}</td>
            <td>
                <select class="status-select status-${status.toLowerCase()}" data-finding-id="${escapeAttr(findingId)}" data-bulk-key="${escapeAttr(getBulkKey(finding))}">
                    <option value="${STATUS_OPEN}" ${status === STATUS_OPEN ? 'selected' : ''}>Open</option>
                    <option value="${STATUS_GEACCEPTEERD}" ${status === STATUS_GEACCEPTEERD ? 'selected' : ''}>Geaccepteerd</option>
                    <option value="${STATUS_GENEGEERD}" ${status === STATUS_GENEGEERD ? 'selected' : ''}>Genegeerd</option>
                    <option value="${STATUS_OPGELOST}" ${status === STATUS_OPGELOST ? 'selected' : ''}>Opgelost</option>
                </select>
            </td>
            <td class="col-action"><button class="ask-btn" title="Vraag hierover" data-finding='${escapeAttr(JSON.stringify(finding))}'>?</button></td>
        `;

        const askBtn = row.querySelector('.ask-btn');
        askBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const findingData = JSON.parse(e.target.dataset.finding);
            askAboutFinding(findingData);
        });

        const statusSelect = row.querySelector('.status-select');
        statusSelect.addEventListener('change', (e) => {
            handleStatusChange(e.target, findingId, e.target.value, e.target.dataset.bulkKey);
        });

        findingsBody.appendChild(row);
    });

    updateOpenCount();
}

function filterFindings() {
    const criticalityValue = criticalityFilter ? criticalityFilter.value : 'all';
    const statusValue = statusFilter ? statusFilter.value : 'all';
    const severityValue = severityFilter.value;
    const engineValue = engineFilter.value;
    const searchValue = searchFilter.value.toLowerCase().trim();

    return allFindings.filter((finding, index) => {
        const criticality = finding.criticality || 'AANDACHT';
        if (criticalityValue !== 'all' && criticality !== criticalityValue) {
            return false;
        }

        const findingId = generateFindingId(finding, index);
        const status = findingStatuses[findingId] || STATUS_OPEN;
        if (statusValue !== 'all' && status !== statusValue) {
            return false;
        }

        if (severityValue !== 'all' && finding.severity !== severityValue) {
            return false;
        }

        if (engineValue !== 'all' && String(finding.engine) !== engineValue) {
            return false;
        }

        if (searchValue) {
            const searchFields = [
                finding.code,
                finding.contract,
                finding.entiteit,
                finding.label,
                finding.waarde,
                finding.omschrijving,
                finding.verwacht,
                finding.bron
            ].filter(Boolean).join(' ').toLowerCase();

            if (!searchFields.includes(searchValue)) {
                return false;
            }
        }

        return true;
    });
}

// Filters
function setupFilters() {
    if (criticalityFilter) criticalityFilter.addEventListener('change', renderFindings);
    if (statusFilter) statusFilter.addEventListener('change', renderFindings);
    severityFilter.addEventListener('change', renderFindings);
    engineFilter.addEventListener('change', renderFindings);
    searchFilter.addEventListener('input', debounce(renderFindings, 300));
}

// Exports
function setupExports() {
    downloadJsonBtn.addEventListener('click', downloadJson);
    downloadExcelBtn.addEventListener('click', downloadExcel);
}

function downloadJson() {
    if (!validationResult) return;

    const enhancedResult = {
        ...validationResult,
        findings: allFindings.map((finding, index) => {
            const findingId = generateFindingId(finding, index);
            const status = findingStatuses[findingId] || STATUS_OPEN;
            return {
                ...finding,
                status: status
            };
        }),
        summary: {
            ...validationResult.summary,
            by_status: getStatusCounts()
        }
    };

    const json = JSON.stringify(enhancedResult, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const filename = `validation_${getTimestamp()}.json`;

    downloadBlob(blob, filename);
}

function getStatusCounts() {
    const counts = {
        [STATUS_OPEN]: 0,
        [STATUS_GEACCEPTEERD]: 0,
        [STATUS_GENEGEERD]: 0,
        [STATUS_OPGELOST]: 0
    };

    allFindings.forEach((finding, index) => {
        const findingId = generateFindingId(finding, index);
        const status = findingStatuses[findingId] || STATUS_OPEN;
        counts[status]++;
    });

    return counts;
}

function downloadExcel() {
    if (!validationResult || allFindings.length === 0) return;

    const headers = ['Criticality', 'Ernst', 'Engine', 'Code', 'Regeltype', 'Contract', 'Branche', 'Entiteit', 'Label', 'Waarde', 'Omschrijving', 'Verwacht', 'Bron', 'Status'];

    const rows = allFindings.map((f, index) => {
        const findingId = generateFindingId(f, index);
        const status = findingStatuses[findingId] || STATUS_OPEN;
        return [
            f.criticality || 'AANDACHT',
            f.severity,
            f.engine,
            f.code,
            f.regeltype,
            f.contract,
            f.branche,
            f.entiteit,
            f.label,
            f.waarde,
            f.omschrijving,
            f.verwacht,
            f.bron,
            status
        ];
    });

    const csvContent = [
        headers.join(';'),
        ...rows.map(row => row.map(cell => `"${String(cell || '').replace(/"/g, '""')}"`).join(';'))
    ].join('\r\n');

    const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8' });
    const filename = `validation_${getTimestamp()}.csv`;

    downloadBlob(blob, filename);
}

function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// Error handling with toast
function showError(message) {
    errorText.textContent = message;
    errorToast.hidden = false;

    setTimeout(() => {
        hideError();
    }, 5000);
}

function hideError() {
    errorToast.hidden = true;
}

function hideResults() {
    validationResult = null;
    allFindings = [];
    findingStatuses = {};
    fileValidationId = null;
    originalXmlContent = null;
    expandedGroups.clear();
    collapsedThemas.clear();
    currentCategory = 'all';

    chatConversationId = null;
    chatFindingContext = null;

    const chatMessages = document.getElementById('chatMessages');
    if (chatMessages) {
        chatMessages.innerHTML = `
            <div class="chat-welcome">
                <p>Vraag me alles over SIVI validatie.</p>
                <ul>
                    <li>Waarom is deze code ongeldig?</li>
                    <li>Welke waarden zijn toegestaan?</li>
                    <li>Wat betekent fout E2-002?</li>
                </ul>
            </div>
        `;
    }

    const chatContext = document.getElementById('chatContext');
    if (chatContext) chatContext.hidden = true;

    const chatSuggestions = document.getElementById('chatSuggestions');
    if (chatSuggestions) chatSuggestions.hidden = true;
}

// Utility functions
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

function truncate(text, maxLength) {
    if (!text) return '';
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}

function getTimestamp() {
    const now = new Date();
    return now.toISOString().replace(/[:.]/g, '-').substring(0, 19);
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function escapeAttr(text) {
    if (!text) return '';
    return text.replace(/'/g, '&#39;').replace(/"/g, '&quot;');
}

// ========================================
// CATEGORIZATION & GROUPING FUNCTIONS
// ========================================

/**
 * Categorize a finding as 'ontbrekend' (missing) or 'inhoudelijk' (content error)
 */
function categorizeFinding(finding) {
    const waarde = String(finding.waarde || '').trim().toLowerCase();
    const omschrijving = String(finding.omschrijving || '').toLowerCase();

    // Check for missing/empty values
    if (waarde === '' || waarde === '0' || waarde === '0.00' || waarde === '0,00' || waarde === 'null' || waarde === 'undefined') {
        return 'ontbrekend';
    }

    // Check description for "ontbreekt" indicators
    if (omschrijving.includes('ontbreekt') || omschrijving.includes('ontbrekend') ||
        omschrijving.includes('leeg') || omschrijving.includes('niet ingevuld') ||
        omschrijving.includes('verplicht') || omschrijving.includes('missing')) {
        return 'ontbrekend';
    }

    return 'inhoudelijk';
}

/**
 * Generate a grouping key for identical findings
 */
function getGroupKey(finding) {
    // Group by: code + label (without prefix) + description
    const labelSuffix = finding.label ? finding.label.split('_').slice(1).join('_') : '';
    return `${finding.code || ''}|${labelSuffix}|${finding.omschrijving || ''}`;
}

/**
 * Determine the thema (category theme) for a finding based on error code
 * Used for grouping related findings together visually
 */
function getThema(finding) {
    const code = finding.code || '';

    // Thema mapping based on error codes
    const themaMapping = {
        // Structuur - hiërarchie en volgorde fouten
        'E1-006': 'structuur',  // Hiërarchie fout
        'E1-008': 'structuur',  // Element volgorde incorrect
        'E2-004': 'structuur',  // XD-entiteit aanwezig

        // Labels & Attributen
        'E1-001': 'labels',     // Label niet in entiteit
        'E1-005': 'labels',     // Label van andere entiteit
        'E1-007': 'labels',     // Verplicht attribuut ontbreekt

        // Codes & Waarden
        'E1-002': 'codes',      // Ongeldige dekkingscode
        'E1-009': 'codes',      // Ongeldige codelijst waarde

        // Format & Lengte
        'E1-003': 'format',     // Veldlengte overschreden
        'E1-004': 'format',     // Formaatfout
        'E1-010': 'format',     // Decimale precisie fout
        'E2-007': 'format',     // Postcode formaat ongeldig

        // Premierekening
        'E2-002': 'premie',     // PP_BTP ≠ som dekkings-BTPs
        'E2-005': 'premie',     // BO_BRPRM ≠ PP_BTP
        'E2-010': 'premie',     // PP_TTOT ≠ som componenten

        // Datums
        'E2-006': 'datums',     // Datum logica fout
        'E2-014': 'datums',     // Ingangsdatum in verleden

        // Branche & Dekking
        'E2-013': 'branche',    // Branche-dekking mismatch
        'E2-016': 'branche',    // Ongeldige dekkingscombinatie
        'E2-017': 'branche',    // Objecttype niet passend bij branche

        // Validatie (BSN, IBAN, etc.)
        'E2-008': 'validatie',  // BSN/KVK 11-proef fout
        'E2-011': 'validatie',  // Ongeldig IBAN formaat

        // Overig
        'E2-001': 'overig',     // VOLGNUM niet sequentieel
        'E2-003': 'overig',     // Meerdere prolongatiemaanden
        'E2-009': 'overig',     // Duplicaat entiteit
        'E2-012': 'overig',     // Betaaltermijn inconsistent
        'E2-015': 'overig',     // Verzekerde som overschrijdt maximum
    };

    return themaMapping[code] || 'overig';
}

/**
 * Get display name for a thema
 */
function getThemaDisplayName(thema) {
    const displayNames = {
        'structuur': 'Structuur',
        'labels': 'Labels & Attributen',
        'codes': 'Codes & Waarden',
        'format': 'Format & Lengte',
        'premie': 'Premierekening',
        'datums': 'Datums',
        'branche': 'Branche & Dekking',
        'validatie': 'Validatie',
        'overig': 'Overig'
    };
    return displayNames[thema] || 'Overig';
}

/**
 * Get sort order for themas (lower = higher priority)
 */
function getThemaSortOrder(thema) {
    const sortOrder = {
        'structuur': 1,
        'labels': 2,
        'codes': 3,
        'format': 4,
        'premie': 5,
        'datums': 6,
        'branche': 7,
        'validatie': 8,
        'overig': 9
    };
    return sortOrder[thema] || 99;
}

/**
 * Group findings by their grouping key
 */
function groupFindings(findings) {
    const groups = {};

    findings.forEach((finding, index) => {
        const groupKey = getGroupKey(finding);
        const category = categorizeFinding(finding);
        const findingId = generateFindingId(finding, allFindings.indexOf(finding));
        const thema = getThema(finding);

        if (!groups[groupKey]) {
            groups[groupKey] = {
                key: groupKey,
                code: finding.code,
                label: finding.label,
                omschrijving: finding.omschrijving,
                severity: finding.severity,
                criticality: finding.criticality || 'AANDACHT',
                category: category,
                entiteit: finding.entiteit,
                engine: finding.engine,
                thema: thema,
                findings: []
            };
        }

        groups[groupKey].findings.push({
            ...finding,
            findingId: findingId,
            originalIndex: allFindings.indexOf(finding)
        });
    });

    return groups;
}

/**
 * Format a value based on its label/field type
 */
function formatValue(value, label) {
    if (!value || value === '' || value === '0' || value === '0.00') {
        return { formatted: value || '-', type: 'empty' };
    }

    const labelUpper = (label || '').toUpperCase();
    const valueStr = String(value);

    // Currency formatting (fields ending with _BTP, _VERZSOM, _PRE, _BEDRAG, etc.)
    if (labelUpper.includes('_BTP') || labelUpper.includes('_VERZSOM') ||
        labelUpper.includes('_PRE') || labelUpper.includes('_BEDRAG') ||
        labelUpper.includes('_SOM') || labelUpper.includes('_POLIS')) {
        const num = parseFloat(valueStr.replace(',', '.'));
        if (!isNaN(num)) {
            const formatted = new Intl.NumberFormat('nl-NL', {
                style: 'currency',
                currency: 'EUR'
            }).format(num);
            return { formatted, type: 'currency' };
        }
    }

    // Date formatting (fields ending with _DAT, _DATUM, _GEBDAT, _INGDAT, etc.)
    if (labelUpper.includes('_DAT') || labelUpper.includes('_DATUM') ||
        labelUpper.includes('_GEBDAT') || labelUpper.includes('_INGDAT')) {
        // Try to parse YYYYMMDD format
        if (/^\d{8}$/.test(valueStr)) {
            const year = valueStr.substring(0, 4);
            const month = valueStr.substring(4, 6);
            const day = valueStr.substring(6, 8);
            return { formatted: `${day}-${month}-${year}`, type: 'date' };
        }
        // Try ISO format
        if (/^\d{4}-\d{2}-\d{2}/.test(valueStr)) {
            const parts = valueStr.substring(0, 10).split('-');
            return { formatted: `${parts[2]}-${parts[1]}-${parts[0]}`, type: 'date' };
        }
    }

    // Percentage formatting (fields ending with _PERC, _PCT)
    if (labelUpper.includes('_PERC') || labelUpper.includes('_PCT')) {
        const num = parseFloat(valueStr.replace(',', '.'));
        if (!isNaN(num)) {
            return { formatted: `${num}%`, type: 'percentage' };
        }
    }

    return { formatted: valueStr, type: 'text' };
}

/**
 * Setup category tabs
 */
function setupCategoryTabs() {
    const tabs = document.querySelectorAll('.category-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            currentCategory = tab.dataset.category;
            renderFindingGroups();
        });
    });
}

/**
 * Update category counts
 */
function updateCategoryCounts() {
    let allCount = 0;
    let inhoudelijkCount = 0;
    let ontbrekendCount = 0;

    allFindings.forEach(finding => {
        const category = categorizeFinding(finding);
        allCount++;
        if (category === 'inhoudelijk') {
            inhoudelijkCount++;
        } else {
            ontbrekendCount++;
        }
    });

    const allCountEl = document.getElementById('categoryAllCount');
    const inhoudelijkCountEl = document.getElementById('categoryInhoudelijkCount');
    const ontbrekendCountEl = document.getElementById('categoryOntbrekendCount');

    if (allCountEl) allCountEl.textContent = allCount;
    if (inhoudelijkCountEl) inhoudelijkCountEl.textContent = inhoudelijkCount;
    if (ontbrekendCountEl) ontbrekendCountEl.textContent = ontbrekendCount;
}

/**
 * Update summary cards based on status - only counts OPEN findings
 */
function updateSummaryCardsFromStatus() {
    let kritiek = 0, aandacht = 0, info = 0, total = 0;

    allFindings.forEach((finding, index) => {
        const findingId = generateFindingId(finding, index);
        const status = findingStatuses[findingId] || STATUS_OPEN;

        // Only count OPEN findings
        if (status === STATUS_OPEN) {
            total++;
            const criticality = finding.criticality || 'AANDACHT';
            if (criticality === 'KRITIEK') kritiek++;
            else if (criticality === 'AANDACHT') aandacht++;
            else info++;
        }
    });

    document.getElementById('kritiekCount').textContent = kritiek;
    document.getElementById('aandachtCount').textContent = aandacht;
    document.getElementById('infoCount').textContent = info;
    document.getElementById('totalCount').textContent = total;
}

/**
 * Update progress bar
 */
function updateProgressBar() {
    const total = allFindings.length;
    let handled = 0;

    allFindings.forEach((finding, index) => {
        const findingId = generateFindingId(finding, index);
        const status = findingStatuses[findingId] || STATUS_OPEN;
        if (status !== STATUS_OPEN) {
            handled++;
        }
    });

    const percentage = total > 0 ? Math.round((handled / total) * 100) : 0;

    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');

    if (progressFill) {
        progressFill.style.width = `${percentage}%`;
    }
    if (progressText) {
        progressText.textContent = `${handled} van ${total} afgehandeld (${percentage}%)`;
    }
}

/**
 * Render grouped findings view
 */
function renderFindingGroups() {
    if (!findingsGrouped) return;

    // First filter findings based on current filters
    const filtered = filterFindings();

    // Then filter by category
    const categoryFiltered = filtered.filter(finding => {
        if (currentCategory === 'all') return true;
        return categorizeFinding(finding) === currentCategory;
    });

    // Group the filtered findings
    const groups = groupFindings(categoryFiltered);

    // Sort groups by thema first, then by count (descending) within each thema
    const sortedGroups = Object.values(groups).sort((a, b) => {
        const themaOrderA = getThemaSortOrder(a.thema);
        const themaOrderB = getThemaSortOrder(b.thema);
        if (themaOrderA !== themaOrderB) {
            return themaOrderA - themaOrderB;
        }
        return b.findings.length - a.findings.length;
    });

    if (sortedGroups.length === 0) {
        findingsGrouped.innerHTML = '';
        noFindings.hidden = false;
        return;
    }

    noFindings.hidden = true;

    let html = '';
    let currentThema = null;
    let themaIndex = 0;

    // Pre-calculate thema counts and statuses
    const themaStats = {};
    sortedGroups.forEach(group => {
        if (!themaStats[group.thema]) {
            themaStats[group.thema] = { count: 0, statuses: {} };
        }
        group.findings.forEach(f => {
            themaStats[group.thema].count++;
            const status = findingStatuses[f.findingId] || STATUS_OPEN;
            themaStats[group.thema].statuses[status] = (themaStats[group.thema].statuses[status] || 0) + 1;
        });
    });

    sortedGroups.forEach(group => {
        // Add thema header when thema changes
        if (group.thema !== currentThema) {
            currentThema = group.thema;
            themaIndex++;
            const themaDisplayName = getThemaDisplayName(currentThema);
            const themaClass = themaIndex % 2 === 0 ? 'thema-even' : 'thema-odd';
            const isCollapsed = collapsedThemas.has(currentThema);
            const collapsedClass = isCollapsed ? 'collapsed' : '';
            const themaCount = themaStats[currentThema]?.count || 0;
            const themaDominantStatus = getThemaDominantStatus(themaStats[currentThema]?.statuses || {});
            html += `
                <div class="thema-header ${themaClass} ${collapsedClass}" data-thema="${currentThema}">
                    <button class="thema-expand" title="${isCollapsed ? 'Uitklappen' : 'Inklappen'}">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M9 18l6-6-6-6"/>
                        </svg>
                    </button>
                    <span class="thema-indicator"></span>
                    <span class="thema-name">${escapeHtml(themaDisplayName)}</span>
                    <span class="thema-count">${themaCount}x</span>
                    <select class="thema-status-select status-${themaDominantStatus.toLowerCase()}" data-thema="${currentThema}">
                        <option value="${STATUS_OPEN}" ${themaDominantStatus === STATUS_OPEN ? 'selected' : ''}>Open</option>
                        <option value="${STATUS_GEACCEPTEERD}" ${themaDominantStatus === STATUS_GEACCEPTEERD ? 'selected' : ''}>Geaccepteerd</option>
                        <option value="${STATUS_GENEGEERD}" ${themaDominantStatus === STATUS_GENEGEERD ? 'selected' : ''}>Genegeerd</option>
                        <option value="${STATUS_OPGELOST}" ${themaDominantStatus === STATUS_OPGELOST ? 'selected' : ''}>Opgelost</option>
                    </select>
                </div>
            `;
        }
        const isExpanded = expandedGroups.has(group.key);
        const expandedClass = isExpanded ? 'expanded' : '';
        const groupThemaClass = themaIndex % 2 === 0 ? 'thema-even' : 'thema-odd';
        const isThemaCollapsed = collapsedThemas.has(group.thema);
        const themaCollapsedClass = isThemaCollapsed ? 'thema-collapsed' : '';

        // Determine the dominant status for the group
        const groupStatus = getGroupDominantStatus(group);

        html += `
            <div class="finding-group ${expandedClass} ${groupThemaClass} ${themaCollapsedClass}" data-group-key="${escapeAttr(group.key)}" data-category="${group.category}" data-thema="${group.thema}">
                <div class="group-header" data-group-key="${escapeAttr(group.key)}">
                    <button class="group-expand" title="Uitklappen">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M9 18l6-6-6-6"/>
                        </svg>
                    </button>
                    <span class="group-count">${group.findings.length}x</span>
                    <span class="group-code">${escapeHtml(group.code)}</span>
                    <span class="group-label" title="${escapeAttr(group.label)}">${escapeHtml(group.label || '')}</span>
                    <span class="group-description" title="${escapeAttr(group.omschrijving)}">${escapeHtml(truncate(group.omschrijving, 50))}</span>
                    <select class="group-status-select status-${groupStatus.toLowerCase()}" data-group-key="${escapeAttr(group.key)}">
                        <option value="${STATUS_OPEN}" ${groupStatus === STATUS_OPEN ? 'selected' : ''}>Open</option>
                        <option value="${STATUS_GEACCEPTEERD}" ${groupStatus === STATUS_GEACCEPTEERD ? 'selected' : ''}>Geaccepteerd</option>
                        <option value="${STATUS_GENEGEERD}" ${groupStatus === STATUS_GENEGEERD ? 'selected' : ''}>Genegeerd</option>
                        <option value="${STATUS_OPGELOST}" ${groupStatus === STATUS_OPGELOST ? 'selected' : ''}>Opgelost</option>
                    </select>
                    <button class="group-ask-btn" title="Vraag hierover" data-finding='${escapeAttr(JSON.stringify(group.findings[0]))}'>?</button>
                </div>
                <div class="group-details">
                    <table class="group-details-table">
                        <thead>
                            <tr>
                                <th>Contract</th>
                                <th>Entiteit</th>
                                <th>Waarde</th>
                                <th>Verwacht</th>
                                <th>Status</th>
                                <th class="col-xml">XML</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${group.findings.map(f => {
                                const formattedWaarde = formatValue(f.waarde, f.label);
                                const formattedVerwacht = formatValue(f.verwacht, f.label);
                                const status = findingStatuses[f.findingId] || STATUS_OPEN;
                                const lineNumber = f.regel || null;
                                return `
                                    <tr data-finding-id="${escapeAttr(f.findingId)}">
                                        <td class="detail-contract">${escapeHtml(f.contract)}</td>
                                        <td>${escapeHtml(f.entiteit)}</td>
                                        <td class="detail-value formatted-${formattedWaarde.type}">${escapeHtml(formattedWaarde.formatted)}</td>
                                        <td class="detail-value formatted-${formattedVerwacht.type}">${escapeHtml(formattedVerwacht.formatted || '-')}</td>
                                        <td>
                                            <select class="detail-status-select status-${status.toLowerCase()}" data-finding-id="${escapeAttr(f.findingId)}">
                                                <option value="${STATUS_OPEN}" ${status === STATUS_OPEN ? 'selected' : ''}>Open</option>
                                                <option value="${STATUS_GEACCEPTEERD}" ${status === STATUS_GEACCEPTEERD ? 'selected' : ''}>Geaccepteerd</option>
                                                <option value="${STATUS_GENEGEERD}" ${status === STATUS_GENEGEERD ? 'selected' : ''}>Genegeerd</option>
                                                <option value="${STATUS_OPGELOST}" ${status === STATUS_OPGELOST ? 'selected' : ''}>Opgelost</option>
                                            </select>
                                        </td>
                                        <td class="col-xml">
                                            ${lineNumber ? `<button class="xml-view-btn" data-line="${lineNumber}" title="Bekijk in XML (regel ${lineNumber})">
                                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                                    <path d="M16 18L22 12L16 6M8 6L2 12L8 18"/>
                                                </svg>
                                            </button>` : '<span class="no-line">-</span>'}
                                        </td>
                                    </tr>
                                `;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    });

    findingsGrouped.innerHTML = html;

    // Attach event listeners
    attachGroupEventListeners();

    // Update progress bar
    updateProgressBar();
    updateCategoryCounts();
    updateOpenCount();
}

/**
 * Get the dominant status for a thema based on status counts
 */
function getThemaDominantStatus(statusCounts) {
    const statuses = Object.keys(statusCounts);
    if (statuses.length === 0) return STATUS_OPEN;
    if (statuses.length === 1) return statuses[0];

    // If any are open, show as open
    if (statusCounts[STATUS_OPEN] > 0) {
        return STATUS_OPEN;
    }

    // Otherwise return most common
    return Object.entries(statusCounts).sort((a, b) => b[1] - a[1])[0][0];
}

/**
 * Get the dominant status for a group (most common status)
 */
function getGroupDominantStatus(group) {
    const statusCounts = {};

    group.findings.forEach(f => {
        const status = findingStatuses[f.findingId] || STATUS_OPEN;
        statusCounts[status] = (statusCounts[status] || 0) + 1;
    });

    // If all have same status, return that
    const statuses = Object.keys(statusCounts);
    if (statuses.length === 1) {
        return statuses[0];
    }

    // If any are open, show as open
    if (statusCounts[STATUS_OPEN] > 0) {
        return STATUS_OPEN;
    }

    // Otherwise return most common
    return Object.entries(statusCounts).sort((a, b) => b[1] - a[1])[0][0];
}

/**
 * Attach event listeners to grouped view
 */
function attachGroupEventListeners() {
    // Thema header click to expand/collapse
    document.querySelectorAll('.thema-header').forEach(header => {
        header.addEventListener('click', (e) => {
            // Don't toggle if clicking on select
            if (e.target.closest('select')) return;

            const thema = header.dataset.thema;

            if (collapsedThemas.has(thema)) {
                collapsedThemas.delete(thema);
                header.classList.remove('collapsed');
                // Show all finding groups for this thema
                document.querySelectorAll(`.finding-group[data-thema="${thema}"]`).forEach(group => {
                    group.classList.remove('thema-collapsed');
                });
            } else {
                collapsedThemas.add(thema);
                header.classList.add('collapsed');
                // Hide all finding groups for this thema
                document.querySelectorAll(`.finding-group[data-thema="${thema}"]`).forEach(group => {
                    group.classList.add('thema-collapsed');
                });
            }
        });
    });

    // Thema expand button click
    document.querySelectorAll('.thema-expand').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const header = btn.closest('.thema-header');
            header.click();
        });
    });

    // Thema status change (bulk for entire thema)
    document.querySelectorAll('.thema-status-select').forEach(select => {
        select.addEventListener('click', (e) => e.stopPropagation());
        select.addEventListener('change', (e) => {
            const thema = e.target.dataset.thema;
            const newStatus = e.target.value;
            applyThemaStatusChange(thema, newStatus);
        });
    });

    // Group header click to expand/collapse
    document.querySelectorAll('.group-header').forEach(header => {
        header.addEventListener('click', (e) => {
            // Don't toggle if clicking on select or button
            if (e.target.closest('select') || e.target.closest('button')) return;

            const groupKey = header.dataset.groupKey;
            const groupEl = header.closest('.finding-group');

            if (expandedGroups.has(groupKey)) {
                expandedGroups.delete(groupKey);
                groupEl.classList.remove('expanded');
            } else {
                expandedGroups.add(groupKey);
                groupEl.classList.add('expanded');
            }
        });
    });

    // Expand button click
    document.querySelectorAll('.group-expand').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const header = btn.closest('.group-header');
            header.click();
        });
    });

    // Group status change (bulk)
    document.querySelectorAll('.group-status-select').forEach(select => {
        select.addEventListener('click', (e) => e.stopPropagation());
        select.addEventListener('change', (e) => {
            const groupKey = e.target.dataset.groupKey;
            const newStatus = e.target.value;
            applyGroupStatusChange(groupKey, newStatus);
        });
    });

    // Individual status change
    document.querySelectorAll('.detail-status-select').forEach(select => {
        select.addEventListener('change', (e) => {
            const findingId = e.target.dataset.findingId;
            const newStatus = e.target.value;
            applyStatusChange(findingId, newStatus);

            // Update group status select
            const groupEl = e.target.closest('.finding-group');
            if (groupEl) {
                const groupKey = groupEl.dataset.groupKey;
                updateGroupStatusSelect(groupKey);
            }
        });
    });

    // Group ask button
    document.querySelectorAll('.group-ask-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const findingData = JSON.parse(e.target.dataset.finding);
            askAboutFinding(findingData);
        });
    });

    // XML view buttons
    document.querySelectorAll('.xml-view-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const lineNumber = parseInt(btn.dataset.line, 10);
            if (lineNumber) {
                showXmlPosition(lineNumber);
            }
        });
    });
}

/**
 * Apply status change to all findings in a thema
 */
function applyThemaStatusChange(thema, newStatus) {
    allFindings.forEach((finding, index) => {
        if (getThema(finding) === thema) {
            const findingId = generateFindingId(finding, index);
            findingStatuses[findingId] = newStatus;
        }
    });

    saveStatusesToStorage();
    renderFindingGroups();
    updateSummaryCardsFromStatus();
}

/**
 * Apply status change to all findings in a group
 */
function applyGroupStatusChange(groupKey, newStatus) {
    const filtered = filterFindings();
    const categoryFiltered = filtered.filter(finding => {
        if (currentCategory === 'all') return true;
        return categorizeFinding(finding) === currentCategory;
    });

    const groups = groupFindings(categoryFiltered);
    const group = groups[groupKey];

    if (!group) return;

    group.findings.forEach(f => {
        findingStatuses[f.findingId] = newStatus;
    });

    saveStatusesToStorage();

    // Update the UI
    renderFindingGroups();
    updateSummaryCardsFromStatus();
}

/**
 * Update group status select after individual change
 */
function updateGroupStatusSelect(groupKey) {
    const groupEl = document.querySelector(`.finding-group[data-group-key="${groupKey}"]`);
    if (!groupEl) return;

    const filtered = filterFindings();
    const categoryFiltered = filtered.filter(finding => {
        if (currentCategory === 'all') return true;
        return categorizeFinding(finding) === currentCategory;
    });

    const groups = groupFindings(categoryFiltered);
    const group = groups[groupKey];

    if (!group) return;

    const dominantStatus = getGroupDominantStatus(group);
    const select = groupEl.querySelector('.group-status-select');

    if (select) {
        select.value = dominantStatus;
        select.className = `group-status-select status-${dominantStatus.toLowerCase()}`;
    }

    updateProgressBar();
    updateOpenCount();
}

// Status Management Functions
function generateFindingId(finding, index) {
    const labelSuffix = finding.label ? finding.label.split('_').slice(1).join('_') : '';
    return `${finding.contract || ''}:${finding.entiteit || ''}:${finding.code || ''}:${labelSuffix}:${index}`;
}

function getBulkKey(finding) {
    const labelSuffix = finding.label ? finding.label.split('_').slice(1).join('_') : '';
    return `${finding.code || ''}:${labelSuffix}`;
}

function generateFileValidationId() {
    if (!selectedFile || !validationResult) return;

    const timestamp = validationResult.timestamp || new Date().toISOString();
    const fileName = selectedFile.name;
    fileValidationId = `${fileName}-${timestamp}`;
}

function getStorageKey() {
    return `sivi-validator-statuses-${fileValidationId}`;
}

function saveStatusesToStorage() {
    if (!fileValidationId) return;

    const data = {
        version: 1,
        fileName: selectedFile ? selectedFile.name : '',
        validationTimestamp: validationResult ? validationResult.timestamp : new Date().toISOString(),
        statuses: findingStatuses
    };

    try {
        localStorage.setItem(getStorageKey(), JSON.stringify(data));
    } catch (e) {
        console.warn('Could not save statuses to localStorage:', e);
    }
}

function loadStatusesFromStorage() {
    if (!fileValidationId) return;

    try {
        const stored = localStorage.getItem(getStorageKey());
        if (stored) {
            const data = JSON.parse(stored);
            if (data.version === 1 && data.statuses) {
                findingStatuses = data.statuses;
            }
        }
    } catch (e) {
        console.warn('Could not load statuses from localStorage:', e);
        findingStatuses = {};
    }
}

function updateOpenCount() {
    if (!openCount) return;

    let open = 0;
    allFindings.forEach((finding, index) => {
        const findingId = generateFindingId(finding, index);
        const status = findingStatuses[findingId] || STATUS_OPEN;
        if (status === STATUS_OPEN) {
            open++;
        }
    });

    openCount.textContent = `${open} open`;
}

function handleStatusChange(selectElement, findingId, newStatus, bulkKey) {
    if (newStatus === STATUS_GEACCEPTEERD || newStatus === STATUS_GENEGEERD) {
        const similarFindings = findSimilarFindings(bulkKey, findingId);

        if (similarFindings.length > 0) {
            showBulkActionModal(findingId, newStatus, bulkKey, similarFindings);
            return;
        }
    }

    applyStatusChange(findingId, newStatus);
}

function findSimilarFindings(bulkKey, excludeFindingId) {
    const similar = [];

    allFindings.forEach((finding, index) => {
        const findingId = generateFindingId(finding, index);
        if (findingId !== excludeFindingId && getBulkKey(finding) === bulkKey) {
            const status = findingStatuses[findingId] || STATUS_OPEN;
            if (status === STATUS_OPEN) {
                similar.push({ findingId, finding, index });
            }
        }
    });

    return similar;
}

function applyStatusChange(findingId, newStatus) {
    findingStatuses[findingId] = newStatus;
    saveStatusesToStorage();

    // Update table view row if it exists
    const row = document.querySelector(`tr[data-finding-id="${findingId}"]`);
    if (row) {
        row.classList.remove('status-open', 'status-geaccepteerd', 'status-genegeerd', 'status-opgelost');
        row.classList.add(`status-${newStatus.toLowerCase()}`);

        const select = row.querySelector('.status-select');
        if (select) {
            select.className = `status-select status-${newStatus.toLowerCase()}`;
        }

        // Update detail status select in grouped view
        const detailSelect = row.querySelector('.detail-status-select');
        if (detailSelect) {
            detailSelect.className = `detail-status-select status-${newStatus.toLowerCase()}`;
        }
    }

    updateOpenCount();
    updateProgressBar();
    updateSummaryCardsFromStatus();
}

function applyBulkStatusChange(findingIds, newStatus) {
    findingIds.forEach(findingId => {
        applyStatusChange(findingId, newStatus);
    });
}

// Bulk Action Modal
let pendingBulkAction = null;

function setupBulkActionModal() {
    if (!bulkActionSingle || !bulkActionAll) return;

    bulkActionSingle.addEventListener('click', () => {
        if (pendingBulkAction) {
            applyStatusChange(pendingBulkAction.findingId, pendingBulkAction.newStatus);
            hideBulkActionModal();
        }
    });

    bulkActionAll.addEventListener('click', () => {
        if (pendingBulkAction) {
            const allIds = [pendingBulkAction.findingId, ...pendingBulkAction.similarFindings.map(f => f.findingId)];
            applyBulkStatusChange(allIds, pendingBulkAction.newStatus);
            hideBulkActionModal();
        }
    });

    if (bulkActionModal) {
        bulkActionModal.addEventListener('click', (e) => {
            if (e.target === bulkActionModal) {
                if (pendingBulkAction) {
                    const select = document.querySelector(`select[data-finding-id="${pendingBulkAction.findingId}"]`);
                    if (select) {
                        const oldStatus = findingStatuses[pendingBulkAction.findingId] || STATUS_OPEN;
                        select.value = oldStatus;
                    }
                }
                hideBulkActionModal();
            }
        });
    }
}

function showBulkActionModal(findingId, newStatus, bulkKey, similarFindings) {
    pendingBulkAction = { findingId, newStatus, bulkKey, similarFindings };

    const statusText = newStatus === STATUS_GEACCEPTEERD ? 'geaccepteerd' : 'genegeerd';
    const totalCount = similarFindings.length + 1;

    if (bulkActionMessage) {
        bulkActionMessage.textContent = `Er zijn ${similarFindings.length} andere bevindingen van hetzelfde type. Wilt u ze allemaal als ${statusText} markeren?`;
    }

    if (bulkActionDetails) {
        bulkActionDetails.textContent = `Totaal: ${totalCount} bevindingen`;
    }

    if (bulkActionAll) {
        bulkActionAll.textContent = `Alle ${totalCount} toepassen`;
    }

    if (bulkActionModal) {
        bulkActionModal.hidden = false;
    }
}

function hideBulkActionModal() {
    if (bulkActionModal) {
        bulkActionModal.hidden = true;
    }
    pendingBulkAction = null;
}

// Chat functionality
function setupChat() {
    const chatWidget = document.getElementById('chatWidget');
    const chatFab = document.getElementById('chatFab');
    const chatPanel = document.getElementById('chatPanel');
    const chatClose = document.getElementById('chatClose');
    const chatInput = document.getElementById('chatInput');
    const chatSend = document.getElementById('chatSend');
    const clearContext = document.getElementById('clearContext');

    chatFab.addEventListener('click', () => {
        chatWidget.classList.add('open');
        chatPanel.hidden = false;
        chatInput.focus();
    });

    chatClose.addEventListener('click', () => {
        chatWidget.classList.remove('open');
        chatPanel.hidden = true;
    });

    chatSend.addEventListener('click', sendChatMessage);

    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendChatMessage();
        }
    });

    chatInput.addEventListener('input', () => {
        chatSend.disabled = !chatInput.value.trim();
    });

    clearContext.addEventListener('click', () => {
        chatFindingContext = null;
        document.getElementById('chatContext').hidden = true;
    });
}

function askAboutFinding(finding) {
    const chatWidget = document.getElementById('chatWidget');
    const chatPanel = document.getElementById('chatPanel');
    const chatInput = document.getElementById('chatInput');
    const chatContext = document.getElementById('chatContext');
    const contextFinding = document.getElementById('contextFinding');

    chatWidget.classList.add('open');
    chatPanel.hidden = false;

    chatFindingContext = {
        code: finding.code,
        severity: finding.severity,
        engine: finding.engine,
        regeltype: finding.regeltype,
        contract: finding.contract,
        branche: finding.branche,
        entiteit: finding.entiteit,
        label: finding.label,
        waarde: finding.waarde,
        omschrijving: finding.omschrijving,
        verwacht: finding.verwacht,
        bron: finding.bron
    };

    contextFinding.textContent = `${finding.code}: ${finding.entiteit} - ${truncate(finding.omschrijving, 40)}`;
    chatContext.hidden = false;

    chatInput.focus();

    loadSuggestions(chatFindingContext);
}

async function loadSuggestions(finding) {
    const suggestionsDiv = document.getElementById('chatSuggestions');
    const suggestionsList = document.getElementById('suggestionsList');

    try {
        const headers = { 'Content-Type': 'application/json' };
        if (apiKeyInput && apiKeyInput.value.trim()) {
            headers['X-API-Key'] = apiKeyInput.value.trim();
        }

        const response = await fetch('/api/chat/suggest', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({ finding: finding })
        });

        if (response.ok) {
            const data = await response.json();
            if (data.questions && data.questions.length > 0) {
                suggestionsList.innerHTML = '';
                data.questions.forEach(question => {
                    const btn = document.createElement('button');
                    btn.className = 'suggestion-btn';
                    btn.textContent = question;
                    btn.addEventListener('click', () => {
                        document.getElementById('chatInput').value = question;
                        document.getElementById('chatSend').disabled = false;
                        sendChatMessage();
                    });
                    suggestionsList.appendChild(btn);
                });
                suggestionsDiv.hidden = false;
            }
        }
    } catch (error) {
        console.warn('Could not load suggestions:', error);
    }
}

async function sendChatMessage() {
    const chatInput = document.getElementById('chatInput');
    const chatMessages = document.getElementById('chatMessages');
    const chatSend = document.getElementById('chatSend');
    const suggestionsDiv = document.getElementById('chatSuggestions');

    const message = chatInput.value.trim();
    if (!message) return;

    chatInput.value = '';
    chatSend.disabled = true;
    suggestionsDiv.hidden = true;

    const welcome = chatMessages.querySelector('.chat-welcome');
    if (welcome) {
        welcome.remove();
    }

    addChatMessage('user', message);

    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'chat-message assistant';
    loadingDiv.innerHTML = '<div class="chat-loading"><span></span><span></span><span></span></div>';
    chatMessages.appendChild(loadingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
        const headers = { 'Content-Type': 'application/json' };
        if (apiKeyInput && apiKeyInput.value.trim()) {
            headers['X-API-Key'] = apiKeyInput.value.trim();
        }

        const requestBody = {
            message: message,
            conversation_id: chatConversationId,
            validation_file: selectedFile ? selectedFile.name : null
        };

        if (chatFindingContext) {
            requestBody.finding_context = chatFindingContext;
        }

        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(requestBody)
        });

        loadingDiv.remove();

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'Chat request failed');
        }

        const data = await response.json();
        chatConversationId = data.conversation_id;

        addChatMessage('assistant', data.message.content, data.message.sources);

        if (data.suggested_questions && data.suggested_questions.length > 0) {
            const suggestionsList = document.getElementById('suggestionsList');
            suggestionsList.innerHTML = '';
            data.suggested_questions.forEach(question => {
                const btn = document.createElement('button');
                btn.className = 'suggestion-btn';
                btn.textContent = question;
                btn.addEventListener('click', () => {
                    chatInput.value = question;
                    chatSend.disabled = false;
                    sendChatMessage();
                });
                suggestionsList.appendChild(btn);
            });
            suggestionsDiv.hidden = false;
        }

    } catch (error) {
        loadingDiv.remove();
        addChatMessage('assistant', `Sorry, er ging iets mis: ${error.message}`);
    }
}

/**
 * Parse markdown text to HTML
 */
function parseMarkdown(text) {
    if (!text) return '';

    // Escape HTML first to prevent XSS
    let html = escapeHtml(text);

    // Code blocks (must be before inline code)
    html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');

    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Headers (process from h3 to h1 to avoid conflicts)
    html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');

    // Bold
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Italic
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // Unordered lists
    html = html.replace(/^\s*[-*]\s+(.*)$/gim, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');

    // Ordered lists
    html = html.replace(/^\s*\d+\.\s+(.*)$/gim, '<li>$1</li>');

    // Line breaks (but not inside pre/code blocks)
    html = html.replace(/\n/g, '<br>');

    // Clean up extra breaks around block elements
    html = html.replace(/<br>\s*<(h[1-3]|pre|ul|ol|li)/g, '<$1');
    html = html.replace(/<\/(h[1-3]|pre|ul|ol|li)>\s*<br>/g, '</$1>');

    return html;
}

function addChatMessage(role, content, sources = null) {
    const chatMessages = document.getElementById('chatMessages');

    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${role}`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    const textSpan = document.createElement('span');
    // Use innerHTML with parsed markdown for assistant messages
    if (role === 'assistant') {
        textSpan.innerHTML = parseMarkdown(content);
    } else {
        textSpan.textContent = content;
    }
    contentDiv.appendChild(textSpan);

    if (sources && sources.length > 0) {
        const sourcesDiv = document.createElement('div');
        sourcesDiv.className = 'message-sources';
        sources.slice(0, 3).forEach(source => {
            const sourceSpan = document.createElement('span');
            let sourceText = `[${source.document_type}] ${source.title}`;
            if (source.section) sourceText += `, sectie ${source.section}`;
            if (source.page) sourceText += `, p.${source.page}`;
            sourceSpan.textContent = sourceText;
            sourcesDiv.appendChild(sourceSpan);
        });
        contentDiv.appendChild(sourcesDiv);
    }

    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// ========================================
// SESSION HANDLING (Save/Load .sivi files)
// ========================================

/**
 * Setup session save/load functionality
 */
function setupSessionHandling() {
    // Session save button
    if (downloadSessionBtn) {
        downloadSessionBtn.addEventListener('click', downloadSession);
    }

    // Session load button and file input
    if (loadSessionBtn && sessionFileInput) {
        loadSessionBtn.addEventListener('click', () => sessionFileInput.click());
        sessionFileInput.addEventListener('change', handleSessionFileSelect);
    }
}

/**
 * Download current session as .sivi file
 */
function downloadSession() {
    if (!validationResult) {
        showError('Geen validatie resultaten om op te slaan.');
        return;
    }

    const session = {
        version: 1,
        type: 'sivi-session',
        timestamp: new Date().toISOString(),
        fileName: selectedFile?.name || validationResult.metadata?.file_name || 'unknown.xml',
        validationResult: validationResult,
        findingStatuses: findingStatuses,
        xmlContent: originalXmlContent || null
    };

    const json = JSON.stringify(session, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const filename = `sessie_${session.fileName.replace('.xml', '')}_${getTimestamp()}.sivi`;

    downloadBlob(blob, filename);
}

/**
 * Handle session file selection
 */
async function handleSessionFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Reset input so same file can be selected again
    event.target.value = '';

    if (!file.name.toLowerCase().endsWith('.sivi')) {
        showError('Selecteer een .sivi sessie bestand.');
        return;
    }

    try {
        const content = await readFileAsText(file);
        const session = JSON.parse(content);
        loadSession(session);
    } catch (error) {
        showError('Kon sessie bestand niet laden: ' + error.message);
    }
}

/**
 * Load a session from parsed session data
 */
function loadSession(session) {
    // Validate session format
    if (!session.type || session.type !== 'sivi-session') {
        showError('Ongeldig sessie bestand formaat.');
        return;
    }

    if (!session.validationResult) {
        showError('Sessie bevat geen validatie resultaten.');
        return;
    }

    // Restore state
    validationResult = session.validationResult;
    allFindings = validationResult.findings || [];
    findingStatuses = session.findingStatuses || {};
    originalXmlContent = session.xmlContent || null;

    // Create a pseudo file object for display purposes
    selectedFile = {
        name: session.fileName || 'Geladen sessie'
    };

    // Generate file validation ID for status storage
    fileValidationId = `${session.fileName}-${session.validationResult.timestamp || session.timestamp}`;

    // Reset view state
    currentCategory = 'all';
    expandedGroups.clear();
    collapsedThemas.clear();

    // Display results and switch to results view
    displayResults();
    showResultsView();

    // Show success message
    showSessionLoadedToast(session.fileName, allFindings.length);
}

/**
 * Show a toast when session is loaded
 */
function showSessionLoadedToast(fileName, findingsCount) {
    const toast = document.getElementById('errorToast');
    const text = document.getElementById('errorText');
    const icon = toast.querySelector('.toast-icon');

    // Temporarily change to success styling
    if (icon) icon.style.color = 'var(--green-500)';
    text.textContent = `Sessie "${fileName}" geladen met ${findingsCount} bevindingen`;
    toast.hidden = false;

    setTimeout(() => {
        toast.hidden = true;
        if (icon) icon.style.color = 'var(--red-500)';
    }, 3000);
}

// ========================================
// XML POSITION VIEWER
// ========================================

/**
 * Setup XML viewer modal
 */
function setupXmlViewer() {
    const modal = document.getElementById('xmlViewerModal');
    const closeBtn = document.getElementById('xmlViewerClose');

    if (modal) {
        // Close on backdrop click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeXmlViewer();
            }
        });
    }

    if (closeBtn) {
        closeBtn.addEventListener('click', closeXmlViewer);
    }

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeXmlViewer();
        }
    });
}

/**
 * Show XML position viewer for a specific line number
 */
function showXmlPosition(lineNumber, context = 5) {
    if (!originalXmlContent) {
        showError('XML content niet beschikbaar. Laad het originele bestand opnieuw.');
        return;
    }

    const modal = document.getElementById('xmlViewerModal');
    const content = document.getElementById('xmlViewerContent');
    const lineInfo = document.getElementById('xmlViewerLineInfo');

    if (!modal || !content) return;

    const lines = originalXmlContent.split('\n');
    const targetLine = parseInt(lineNumber, 10);

    // Calculate range to display
    const startLine = Math.max(1, targetLine - context);
    const endLine = Math.min(lines.length, targetLine + context);

    // Build HTML with line numbers and highlighting
    let html = '';
    for (let i = startLine; i <= endLine; i++) {
        const lineContent = escapeHtml(lines[i - 1] || '');
        const isTarget = (i === targetLine);
        const lineClass = isTarget ? 'xml-line xml-line-highlight' : 'xml-line';

        html += `<div class="${lineClass}">`;
        html += `<span class="xml-line-number">${i}</span>`;
        html += `<span class="xml-line-content">${lineContent}</span>`;
        html += `</div>`;
    }

    content.innerHTML = html;

    if (lineInfo) {
        lineInfo.textContent = `Regel ${targetLine} van ${lines.length}`;
    }

    // Show modal
    modal.hidden = false;

    // Scroll to highlighted line after modal is visible
    requestAnimationFrame(() => {
        const highlightedLine = content.querySelector('.xml-line-highlight');
        if (highlightedLine) {
            highlightedLine.scrollIntoView({ block: 'center' });
        }
    });
}

/**
 * Close XML viewer modal
 */
function closeXmlViewer() {
    const modal = document.getElementById('xmlViewerModal');
    if (modal) {
        modal.hidden = true;
    }
}
