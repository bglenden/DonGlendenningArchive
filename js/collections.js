/* Shared, keyboard-accessible controls for the collection indexes. */
function filterTable() {
    const query = document.getElementById('searchInput').value.trim().toLocaleLowerCase();
    const highlightsOnly = document.getElementById('hlFilter')?.checked || false;
    let visible = 0;
    document.querySelectorAll('#fileTable tbody tr').forEach(row => {
        const matches = (!query || row.textContent.toLocaleLowerCase().includes(query)) &&
            (!highlightsOnly || row.hasAttribute('data-highlight'));
        row.hidden = !matches;
        if (matches) visible++;
    });
    const counter = document.getElementById('rowCount');
    if (counter) {
        const unit = counter.dataset.unit || 'documents';
        counter.textContent = `${visible} ${visible === 1 ? unit.replace(/s$/, '') : unit}`;
    }
    const empty = document.getElementById('tableEmpty');
    if (empty) empty.hidden = visible !== 0;
}
function toggleHighlightsFilter() { filterTable(); }
function toggleRow(button) {
    const expanded = button.getAttribute('aria-expanded') !== 'true';
    const cell = button.parentElement;
    cell.querySelector('.short-summary').style.display = expanded ? 'none' : 'inline';
    document.getElementById(button.getAttribute('aria-controls')).style.display = expanded ? 'block' : 'none';
    button.setAttribute('aria-expanded', String(expanded));
    button.textContent = expanded ? '▾ less' : '▸ more';
}
