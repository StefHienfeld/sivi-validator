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

// Modal elements
const bulkActionModal = document.getElementById('bulkActionModal');
const bulkActionMessage = document.getElementById('bulkActionMessage');
const bulkActionDetails = document.getElementById('bulkActionDetails');
const bulkActionSingle = document.getElementById('bulkActionSingle');
const bulkActionAll = document.getElementById('bulkActionAll');

// Export buttons
const downloadJsonBtn = document.getElementById('downloadJson');
const downloadExcelBtn = document.getElementById('downloadExcel');

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
    setupExports();
    setupValidation();
    setupChat();
    setupBulkActionModal();
    setupNavigation();
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

    renderFindings();
}

function renderFindings() {
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

    const row = document.querySelector(`tr[data-finding-id="${findingId}"]`);
    if (row) {
        row.classList.remove('status-open', 'status-geaccepteerd', 'status-genegeerd', 'status-opgelost');
        row.classList.add(`status-${newStatus.toLowerCase()}`);

        const select = row.querySelector('.status-select');
        if (select) {
            select.className = `status-select status-${newStatus.toLowerCase()}`;
        }
    }

    updateOpenCount();
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

function addChatMessage(role, content, sources = null) {
    const chatMessages = document.getElementById('chatMessages');

    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${role}`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    const textSpan = document.createElement('span');
    textSpan.textContent = content;
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
