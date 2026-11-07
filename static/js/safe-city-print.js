

(function () {
    'use strict';

    const scPrint = {};

    scPrint._qrInstances = scPrint._qrInstances || {};
    scPrint._barcodeInstances = scPrint._barcodeInstances || {};

    function csrf() {
        if (window.scApp && typeof window.scApp.csrfToken === 'function') return window.scApp.csrfToken();
        const el = document.querySelector('input[name="csrfmiddlewaretoken"]');
        return el ? el.value : '';
    }

    scPrint.initChallan = function (psid) {
        psid = psid || window.currentPSID || '';
        const sheet = document.querySelector('.sc-print-sheet');
        if (!sheet) { console.error('[scPrint] .sc-print-sheet not found'); return; }
        sheet.style.display = 'block';

        fetch('/api/challan/' + psid + '/', { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                scPrint._populateChallan(sheet, data, psid);
            })
            .catch(function () {
                console.warn('[scPrint] Could not fetch challan data for', psid);
            });
    };

    scPrint._populateChallan = function (sheet, data, psid) {
        if (!data) return;

        function set(selector, val) {
            const el = sheet.querySelector(selector);
            if (el) el.textContent = val || '---';
        }
        set('[data-field="psid"]', data.psid || data.id || psid);
        set('[data-field="date"]', data.date || data.issue_date);
        set('[data-field="time"]', data.time || data.issue_time);
        set('[data-field="vehicle"]', data.vehicle_number);
        set('[data-field="owner"]', data.owner_name);
        set('[data-field="cnic"]', data.cnic);
        set('[data-field="violation"]', data.violation_type);
        set('[data-field="fine"]', data.fine_amount ? 'PKR ' + data.fine_amount : '');
        set('[data-field="location"]', data.location);
        set('[data-field="officer"]', data.issuing_officer);
        set('[data-field="due_date"]', data.due_date);
        set('[data-field="status"]', data.status);

        const violTable = sheet.querySelector('.sc-print-violations');
        if (violTable && Array.isArray(data.violations)) {
            const tbody = violTable.querySelector('tbody');
            if (tbody) {
                tbody.innerHTML = '';
                data.violations.forEach(function (v) {
                    const tr = document.createElement('tr');
                    tr.innerHTML = '<td>' + (v.date || '') + '</td>' +
                        '<td>' + (v.type || '') + '</td>' +
                        '<td>' + (v.location || '') + '</td>' +
                        '<td>PKR ' + (v.fine || '') + '</td>' +
                        '<td>' + (v.status || '') + '</td>';
                    tbody.appendChild(tr);
                });
            }
        }

        setTimeout(function () {
            scPrint.generateQR('scPrintQR', JSON.stringify({ psid: psid, url: window.location.origin + '/challan/' + psid + '/' }));
            scPrint.generateBarcode('scPrintBarcode', psid);
        }, 100);
    };

    scPrint.generateQR = function (containerId, data) {
        const container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = '';

        if (typeof window.Html5QRcode !== 'undefined') {

            const qr = new Html5QRcode(containerId);
            qr.generate(data).then(function () {

            }).catch(function (err) {
                container.innerHTML = '<p style="font-size:10pt;color:#999;">QR: ' + data + '</p>';
            });
            scPrint._qrInstances[containerId] = qr;
        } else if (typeof window.QRCode !== 'undefined') {

            new QRCode(container, { text: data, width: 100, height: 100 });
        } else {

            container.innerHTML = '<div style="width:100px;height:100px;display:flex;align-items:center;justify-content:center;background:#f5f5f5;border:1px solid #ddd;font-size:9pt;text-align:center;word-break:break-all;padding:4px;">' + data + '</div>';
        }
    };

    scPrint.generateBarcode = function (canvasId, data) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        if (typeof window.JsBarcode !== 'undefined') {
            try {
                JsBarcode(canvas, data, {
                    format: 'CODE128',
                    width: 1.5,
                    height: 50,
                    displayValue: true,
                    fontSize: 12,
                    margin: 4,
                });
            } catch (e) {
                canvas.parentElement.textContent = data;
            }
            scPrint._barcodeInstances[canvasId] = data;
        } else {

            canvas.parentElement.innerHTML = '<p style="font-family:monospace;font-size:14pt;font-weight:bold;">' + data + '</p>';
        }
    };

    scPrint.printChallan = function (psid) {
        psid = psid || window.currentPSID;
        if (psid && !document.querySelector('.sc-print-sheet')) {
            scPrint.initChallan(psid);
        }

        setTimeout(function () {
            window.print();
        }, 500);
    };

    scPrint.preview = function () {
        const sheet = document.querySelector('.sc-print-sheet');
        if (!sheet) return;
        sheet.style.display = 'block';
        scPrint.urduMode();

        let overlay = document.getElementById('scPrintPreviewOverlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'scPrintPreviewOverlay';
            overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:9999;display:flex;align-items:center;justify-content:center;padding:2rem;';
            overlay.addEventListener('click', function (e) {
                if (e.target === overlay) scPrint.closePreview();
            });
            document.body.appendChild(overlay);
        }
        const clone = sheet.cloneNode(true);
        clone.style.cssText = 'position:relative;max-width:210mm;max-height:90vh;overflow:auto;background:white;box-shadow:0 4px 20px rgba(0,0,0,0.3);';
        overlay.innerHTML = '';
        overlay.appendChild(clone);

        const closeBtn = document.createElement('button');
        closeBtn.textContent = 'Close Preview';
        closeBtn.className = 'sc-btn sc-btn-primary';
        closeBtn.style.cssText = 'position:absolute;top:1rem;right:1rem;z-index:10000;';
        closeBtn.addEventListener('click', scPrint.closePreview);
        overlay.appendChild(closeBtn);
    };

    scPrint.closePreview = function () {
        const overlay = document.getElementById('scPrintPreviewOverlay');
        if (overlay) overlay.style.display = 'none';
    };

    scPrint.urduMode = function () {
        const sheet = document.querySelector('.sc-print-sheet');
        if (!sheet) return;
        const urduEls = sheet.querySelectorAll('.sc-print-urdu, [data-urdu]');
        if (urduEls.length === 0) {

            sheet.querySelectorAll('*').forEach(function (el) {
                const text = el.textContent || '';
                if (/[\u0600-\u06FF\u0750-\u077F]/.test(text)) {
                    el.setAttribute('data-urdu', 'true');
                    el.style.direction = 'rtl';
                    el.style.unicodeBidi = 'embed';
                    el.style.fontFamily = "'Noto Nastaliq Urdu', 'Jameel Noori Nastaleeq', serif";
                }
            });
        } else {
            urduEls.forEach(function (el) {
                el.style.direction = 'rtl';
                el.style.unicodeBidi = 'embed';
                el.style.fontFamily = "'Noto Nastaliq Urdu', 'Jameel Noori Nastaleeq', serif";
            });
        }
    };

    function autoInit() {
        document.querySelectorAll('[data-print-challan]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                const psid = btn.getAttribute('data-print-challan');
                scPrint.printChallan(psid);
            });
        });
        document.querySelectorAll('[data-print-preview]').forEach(function (btn) {
            btn.addEventListener('click', scPrint.preview);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', autoInit);
    } else {
        autoInit();
    }

    window.scPrint = scPrint;
})();
