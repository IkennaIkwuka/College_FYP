function initTypeahead(inputEl, searchUrl) {
    const wrapper = inputEl.closest('.typeahead-wrapper');
    const dropdown = wrapper.querySelector('.typeahead-results');
    let timeout;
    let controller;

    function hide() {
        dropdown.classList.add('d-none');
        dropdown.innerHTML = '';
    }

    function renderResults(results) {
        dropdown.innerHTML = '';
        if (!results.length) {
            hide();
            return;
        }
        results.forEach(function (r) {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'list-group-item list-group-item-action';

            const label = document.createElement('div');
            label.textContent = r.label;
            item.appendChild(label);

            if (r.sublabel) {
                const sub = document.createElement('small');
                sub.className = 'text-muted';
                sub.textContent = r.sublabel;
                item.appendChild(sub);
            }

            item.addEventListener('click', function () {
                if (r.url) {
                    window.location.href = r.url;
                } else {
                    inputEl.value = r.value;
                    inputEl.form.submit();
                }
            });

            dropdown.appendChild(item);
        });
        dropdown.classList.remove('d-none');
    }

    inputEl.addEventListener('input', function () {
        clearTimeout(timeout);
        const q = inputEl.value.trim();
        if (!q) {
            hide();
            return;
        }
        timeout = setTimeout(function () {
            if (controller) controller.abort();
            controller = new AbortController();
            fetch(searchUrl + '?q=' + encodeURIComponent(q), { signal: controller.signal })
                .then(function (res) { return res.json(); })
                .then(function (data) { renderResults(data.results); })
                .catch(function (err) {
                    if (err.name !== 'AbortError') hide();
                });
        }, 250);
    });

    document.addEventListener('click', function (e) {
        if (!wrapper.contains(e.target)) hide();
    });

    inputEl.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') hide();
    });
}
