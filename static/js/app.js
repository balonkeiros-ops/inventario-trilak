// static/js/app.js
'use strict';

document.addEventListener('DOMContentLoaded', () => {
    console.log('Sistema de Inventario cargado');

    // Auto-completar fecha actual (yyyy-mm-dd)
    document.querySelectorAll('input[type="date"]').forEach(input => {
        if (!input.value) {
            input.value = new Date().toISOString().split('T')[0];
        }
    });

    // Validación de un formulario
    const attachValidation = form => {
        if (form.__validationAttached) return;
        form.__validationAttached = true;

        const markInvalid = el => el.classList.add('is-invalid');
        const clearInvalid = el => el.classList.remove('is-invalid');

        form.addEventListener('submit', e => {
            let valid = true;
            const required = Array.from(form.querySelectorAll('[required]'));
            required.forEach(field => {
                clearInvalid(field);
                const type = field.type;
                let empty = false;

                if (type === 'checkbox' || type === 'radio') {
                    // for radio/checkbox groups, check if any in group is checked
                    if (field.name) {
                        const group = form.querySelectorAll(`[name="${CSS.escape(field.name)}"]`);
                        if (![...group].some(f => f.checked)) empty = true;
                    } else {
                        if (!field.checked) empty = true;
                    }
                } else if (field.tagName.toLowerCase() === 'select') {
                    if (!field.value) empty = true;
                } else if (type === 'file') {
                    if (!field.files || field.files.length === 0) empty = true;
                } else {
                    if (!String(field.value).trim()) empty = true;
                }

                if (empty) {
                    valid = false;
                    markInvalid(field);
                }
            });

            if (!valid) {
                e.preventDefault();
                const first = form.querySelector('.is-invalid');
                if (first && typeof first.focus === 'function') first.focus();
                // fallback message
                alert('Por favor, complete todos los campos requeridos');
            }
        });

        // remove invalid class when user interacts
        form.addEventListener('input', e => clearInvalid(e.target), true);
        form.addEventListener('change', e => clearInvalid(e.target), true);
    };

    // Attach to existing forms
    document.querySelectorAll('form').forEach(attachValidation);

    // Observe for dynamically added forms
    const mo = new MutationObserver(mutations => {
        for (const m of mutations) {
            m.addedNodes.forEach(node => {
                if (node.nodeType !== 1) return;
                if (node.matches && node.matches('form')) attachValidation(node);
                node.querySelectorAll && node.querySelectorAll('form').forEach(attachValidation);
            });
        }
    });
    mo.observe(document.body, { childList: true, subtree: true });

    // Eliminar (desvanecer) mensajes después de 5 segundos
    setTimeout(() => {
        document.querySelectorAll('.alert').forEach(a => {
            a.style.transition = 'opacity 400ms ease';
            a.style.opacity = '0';
            setTimeout(() => a.remove(), 500);
        });
    }, 5000);
});