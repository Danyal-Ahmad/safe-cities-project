

(function () {
    'use strict';

    const scForms = {};

    scForms.csrf = function () {
        if (window.scApp && typeof window.scApp.csrfToken === 'function') {
            return window.scApp.csrfToken();
        }
        const el = document.querySelector('input[name="csrfmiddlewaretoken"]');
        return el ? el.value : '';
    };

    scForms.rules = {
        required: function (val) {
            return (val != null && String(val).trim() !== '') || 'This field is required';
        },
        email: function (val) {
            if (!val) return true;
            return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val) || 'Enter a valid email address';
        },
        minlength: function (val, len) {
            len = len || 1;
            if (!val) return true;
            return val.length >= len || ('Must be at least ' + len + ' characters');
        },
        maxlength: function (val, len) {
            if (!val) return true;
            return val.length <= len || ('Must be at most ' + len + ' characters');
        },
        password: function (val) {
            if (!val) return true;
            if (val.length < 8) return 'Password must be at least 8 characters';
            if (!/[A-Z]/.test(val)) return 'Password must contain an uppercase letter';
            if (!/[0-9]/.test(val)) return 'Password must contain a number';
            return true;
        },
        cnic: function (val) {
            if (!val) return true;
            const cleaned = String(val).replace(/[-\s]/g, '');
            return (/^\d{13}$/.test(cleaned) || 'Enter a valid CNIC (13 digits)');
        },
        phone: function (val) {
            if (!val) return true;
            const cleaned = String(val).replace(/[-\s]/g, '');
            return (/^\d{10,11}$/.test(cleaned) || 'Enter a valid phone number');
        },
        number: function (val) {
            if (!val) return true;
            return (!isNaN(parseFloat(val)) && isFinite(val) || 'Enter a valid number');
        },
        url: function (val) {
            if (!val) return true;
            try { new URL(val); return true; } catch (e) { return 'Enter a valid URL'; }
        },
        match: function (val, targetId) {
            if (!val) return true;
            const target = document.getElementById(targetId);
            return (target && val === target.value || 'Values do not match');
        }
    };

    scForms.showError = function (field, message) {
        const el = (typeof field === 'string') ? document.getElementById(field) : field;
        if (!el) return;
        el.classList.add('error');
        let err = el.parentElement.querySelector('.sc-error');
        if (!err) {
            err = document.createElement('div');
            err.className = 'sc-error';
            el.parentElement.appendChild(err);
        }
        err.textContent = message;
    };

    scForms.clearError = function (field) {
        const el = (typeof field === 'string') ? document.getElementById(field) : field;
        if (!el) return;
        el.classList.remove('error');
        const err = el.parentElement.querySelector('.sc-error');
        if (err) err.remove();
    };

    scForms.clearAllErrors = function (formEl) {
        formEl.querySelectorAll('.sc-error').forEach(function (e) { e.remove(); });
        formEl.querySelectorAll('.sc-form-control.error').forEach(function (e) { e.classList.remove('error'); });
    };

    scForms.autoFocusFirstError = function (formEl) {
        const first = formEl.querySelector('.sc-form-control.error');
        if (first) {
            first.scrollIntoView({ behavior: 'smooth', block: 'center' });
            setTimeout(function () { first.focus(); }, 400);
        }
    };

    scForms.validate = function (formId) {
        const form = typeof formId === 'string' ? document.getElementById(formId) : formId;
        if (!form) return false;
        scForms.clearAllErrors(form);
        let valid = true;
        const fields = form.querySelectorAll('[data-validate]');
        fields.forEach(function (field) {
            const rules = field.getAttribute('data-validate').split('|');
            for (let i = 0; i < rules.length; i++) {
                const parts = rules[i].split(':');
                const ruleName = parts[0];
                const ruleArg = parts[1];
                const ruleFn = scForms.rules[ruleName];
                if (!ruleFn) continue;
                const result = ruleFn(field.value, ruleArg);
                if (result !== true) {
                    scForms.showError(field, result);
                    valid = false;
                    break;
                }
            }
        });
        if (!valid) scForms.autoFocusFirstError(form);
        return valid;
    };

    scForms.submit = function (formId, options) {
        options = options || {};
        const form = typeof formId === 'string' ? document.getElementById(formId) : formId;
        if (!form) return Promise.reject(new Error('Form not found'));
        if (!scForms.validate(form)) {
            if (typeof options.onError === 'function') options.onError({ error: 'validation' });
            return Promise.resolve({ ok: false, validation: true });
        }
        const submitBtn = form.querySelector('[type="submit"]');
        if (submitBtn) submitBtn.disabled = true;
        const url = options.url || form.action || window.location.href;
        const method = (options.method || form.method || 'POST').toUpperCase();
        const data = new FormData(form);
        if (options.data) {
            Object.keys(options.data).forEach(function (k) { data.append(k, options.data[k]); });
        }
        return fetch(url, {
            method: method,
            body: data,
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': scForms.csrf(), 'X-Requested-With': 'XMLHttpRequest' }
        }).then(function (resp) {
            if (submitBtn) submitBtn.disabled = false;
            const ct = resp.headers.get('content-type') || '';
            if (ct.indexOf('application/json') !== -1) return resp.json().then(function (j) {
                if (j.errors) {
                    Object.keys(j.errors).forEach(function (k) {
                        const f = form.querySelector('[name="' + k + '"]');
                        if (f) scForms.showError(f, j.errors[k]);
                    });
                }
                if (j.ok === false && options.onError) options.onError(j);
                if (j.ok !== false && options.onSuccess) options.onSuccess(j);
                return j;
            });
            return resp.text();
        }).catch(function (err) {
            if (submitBtn) submitBtn.disabled = false;
            if (options.onError) options.onError(err);
            throw err;
        });
    };

    scForms.previewImage = function (fileInputId, imgPreviewId) {
        const input = document.getElementById(fileInputId);
        const preview = document.getElementById(imgPreviewId);
        if (!input || !preview) return;
        input.addEventListener('change', function (e) {
            const file = e.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = function (ev) {
                preview.src = ev.target.result;
                preview.style.display = '';
            };
            reader.readAsDataURL(file);
        });
    };

    scForms.togglePassword = function (inputId, toggleBtnId) {
        const input = document.getElementById(inputId);
        const btn = document.getElementById(toggleBtnId);
        if (!input || !btn) return;
        btn.addEventListener('click', function () {
            if (input.type === 'password') {
                input.type = 'text';
                btn.innerHTML = '<i class="bi bi-eye-slash"></i>';
            } else {
                input.type = 'password';
                btn.innerHTML = '<i class="bi bi-eye"></i>';
            }
        });
    };

    scForms.initPasswordStrength = function (inputId, meterId) {
        const input = document.getElementById(inputId);
        const meter = document.getElementById(meterId);
        if (!input || !meter) return;
        input.addEventListener('input', function () {
            const v = input.value;
            let score = 0;
            if (v.length >= 8) score++;
            if (v.length >= 12) score++;
            if (/[A-Z]/.test(v) && /[a-z]/.test(v)) score++;
            if (/[0-9]/.test(v)) score++;
            if (/[^A-Za-z0-9]/.test(v)) score++;

            let label = 'weak';
            let pct = 25;
            if (score <= 1) { label = 'weak'; pct = 25; }
            else if (score === 2) { label = 'fair'; pct = 50; }
            else if (score === 3) { label = 'good'; pct = 75; }
            else { label = 'strong'; pct = 100; }

            meter.style.width = pct + '%';
            meter.setAttribute('data-strength', label);
            const color = label === 'weak' ? '#b91c1c'
                : label === 'fair' ? '#b45309'
                : label === 'good' ? '#0e7490'
                : '#15803d';
            meter.style.background = color;
            meter.style.transition = 'all 200ms ease';
            if (meter.textContent !== undefined) meter.textContent = label.toUpperCase();
        });
    };

    scForms.autoFormatCNIC = function (inputId) {
        const el = document.getElementById(inputId);
        if (!el) return;
        el.addEventListener('input', function (e) {
            let v = e.target.value.replace(/\D/g, '').slice(0, 13);
            if (v.length > 5) v = v.slice(0, 5) + '-' + v.slice(5);
            if (v.length > 13) v = v.slice(0, 13) + '-' + v.slice(13);
            e.target.value = v;
        });
    };

    scForms.autoFormatPhone = function (inputId) {
        const el = document.getElementById(inputId);
        if (!el) return;
        el.addEventListener('input', function (e) {
            let v = e.target.value.replace(/\D/g, '').slice(0, 11);
            if (v.length > 4) v = v.slice(0, 4) + '-' + v.slice(4);
            e.target.value = v;
        });
    };

    function autoInit() {
        document.querySelectorAll('[data-cnic]').forEach(function (el) { scForms.autoFormatCNIC(el.id); });
        document.querySelectorAll('[data-phone]').forEach(function (el) { scForms.autoFormatPhone(el.id); });
        document.querySelectorAll('[data-password-strength]').forEach(function (el) {
            scForms.initPasswordStrength(el.id, el.getAttribute('data-password-strength'));
        });
        document.querySelectorAll('[data-toggle-password]').forEach(function (el) {
            const inputId = el.getAttribute('data-toggle-password');
            scForms.togglePassword(inputId, el.id);
        });
        document.querySelectorAll('[data-preview-image]').forEach(function (el) {
            const inputId = el.getAttribute('data-preview-image');
            scForms.previewImage(inputId, el.id);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', autoInit);
    } else {
        autoInit();
    }

    window.scForms = scForms;
})();
