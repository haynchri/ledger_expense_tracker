document.addEventListener('DOMContentLoaded', () => {
  initializeModal();
  initializeCsvUpload();
  initializeDashboard();
  initializeForecast();
  initializeReports();
  initializeRuleForm();
});

function initializeModal() {
  const modalRoot = document.getElementById('modal-root');
  if (!modalRoot) return;

  const modalContent = document.getElementById('modal-content');

  function closeModal() {
    modalRoot.classList.add('hidden');
    modalRoot.setAttribute('aria-hidden', 'true');
    modalContent.innerHTML = '';
  }

  function openModalFromUrl(url) {
    const modalUrl = url.includes('?') ? `${url}&modal=1` : `${url}?modal=1`;
    modalRoot.classList.remove('hidden');
    modalRoot.setAttribute('aria-hidden', 'false');

    fetch(modalUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then((response) => {
        if (!response.ok) {
          throw new Error('Failed to load modal');
        }
        return response.text();
      })
      .then((html) => {
        modalContent.innerHTML = html;
        bindModalForms();
      })
      .catch(() => {
        closeModal();
        window.location.href = url;
      });
  }

  function bindModalForms() {
    const form = modalContent.querySelector('.ajax-form');
    if (!form) return;

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const formData = new FormData(form);
      const action = form.getAttribute('action');

      const response = await fetch(action, {
        method: 'POST',
        body: formData,
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      });

      if (response.redirected) {
        window.location.reload();
        return;
      }

      const html = await response.text();
      if (html.includes('class="ajax-form"')) {
        modalContent.innerHTML = html;
        bindModalForms();
        return;
      }

      window.location.reload();
    });
  }

  document.addEventListener('click', (event) => {
    const closeTrigger = event.target.closest('[data-modal-close]');
    if (closeTrigger) {
      closeModal();
      return;
    }

    const trigger = event.target.closest('[data-modal-url]');
    if (!trigger) return;

    event.preventDefault();
    openModalFromUrl(trigger.getAttribute('data-modal-url'));
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !modalRoot.classList.contains('hidden')) {
      closeModal();
    }
  });

  modalRoot.addEventListener('click', (event) => {
    if (event.target === modalRoot) {
      closeModal();
    }
  });

  setTimeout(() => {
    const msgs = document.getElementById('messages');
    if (msgs) {
      msgs.style.opacity = '0';
      msgs.style.transition = 'opacity 0.5s';
      setTimeout(() => msgs.remove(), 500);
    }
  }, 4000);
}

function initializeCsvUpload() {
  const input = document.getElementById('csv-file-input');
  const zone = document.getElementById('upload-zone');
  const label = document.getElementById('file-chosen');

  if (!input || !zone || !label) return;

  input.addEventListener('change', () => {
    if (input.files.length) {
      label.textContent = '📄 ' + input.files[0].name;
      label.style.display = 'block';
      zone.style.borderColor = 'var(--accent)';
    }
  });

  zone.addEventListener('dragover', (event) => {
    event.preventDefault();
    zone.classList.add('dragover');
  });

  zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
  zone.addEventListener('drop', (event) => {
    event.preventDefault();
    zone.classList.remove('dragover');

    if (event.dataTransfer.files.length) {
      input.files = event.dataTransfer.files;
      label.textContent = '📄 ' + event.dataTransfer.files[0].name;
      label.style.display = 'block';
      zone.style.borderColor = 'var(--accent)';
    }
  });
}

function initializeDashboard() {
  const canvas = document.getElementById('overviewChart');
  if (!canvas) return;

  let chart = null;

  function initChart(chartData) {
    const ctx = canvas.getContext('2d');
    if (chart) {
      chart.destroy();
    }

    chart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: chartData.labels,
        datasets: [
          {
            label: 'Income',
            data: chartData.income,
            backgroundColor: 'rgba(52, 211, 153, 0.5)',
            borderColor: '#34d399',
            borderWidth: 1,
            borderRadius: 4,
          },
          {
            label: 'Expenses',
            data: chartData.expenses,
            backgroundColor: 'rgba(248, 113, 113, 0.5)',
            borderColor: '#f87171',
            borderWidth: 1,
            borderRadius: 4,
          }
        ]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { labels: { color: '#8b90b0', font: { family: 'DM Sans' } } }
        },
        scales: {
          x: { ticks: { color: '#8b90b0' }, grid: { color: '#2e3350' } },
          y: {
            ticks: { color: '#8b90b0', callback: (value) => '$' + value.toLocaleString() },
            grid: { color: '#2e3350' }
          }
        }
      }
    });
  }

  const chartData = JSON.parse(canvas.dataset.chartData || '{}');
  initChart(chartData);

  const filter = document.getElementById('categoryFilter');
  if (!filter) return;

  filter.addEventListener('change', function (event) {
    const categoryId = event.target.value;
    const baseUrl = filter.dataset.dashboardUrl;
    const url = categoryId ? `${baseUrl}?category_id=${categoryId}` : baseUrl;

    fetch(url)
      .then((response) => response.json())
      .then((data) => {
        initChart(data);
      })
      .catch((error) => console.error('Error fetching chart data:', error));
  });
}

function initializeForecast() {
  const canvas = document.getElementById('forecastChart');
  if (!canvas) return;

  const chartData = JSON.parse(canvas.dataset.chartData || '{}');

  new Chart(canvas.getContext('2d'), {
    data: {
      labels: chartData.labels,
      datasets: [
        {
          type: 'bar',
          label: 'Income',
          data: chartData.income,
          backgroundColor: 'rgba(52,211,153,0.45)',
          borderColor: '#34d399',
          borderWidth: 1,
          borderRadius: 4,
          yAxisID: 'y',
        },
        {
          type: 'bar',
          label: 'Expenses',
          data: chartData.expense,
          backgroundColor: 'rgba(248,113,113,0.45)',
          borderColor: '#f87171',
          borderWidth: 1,
          borderRadius: 4,
          yAxisID: 'y',
        },
        {
          type: 'line',
          label: 'Running Balance',
          data: chartData.balance,
          borderColor: '#a599ff',
          borderWidth: 2,
          borderDash: [5, 3],
          pointBackgroundColor: '#a599ff',
          pointRadius: 4,
          tension: 0.35,
          fill: false,
          yAxisID: 'y2',
        },
      ],
    },
    options: {
      responsive: true,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { labels: { color: '#8b90b0', font: { family: 'DM Sans', size: 11 } } },
        tooltip: {
          callbacks: {
            label: (context) => ` ${context.dataset.label}: $${context.parsed.y.toFixed(2)}`
          }
        }
      },
      scales: {
        x: { ticks: { color: '#8b90b0' }, grid: { color: '#2e3350' } },
        y: { ticks: { color: '#8b90b0', callback: (value) => '$' + value.toLocaleString() }, grid: { color: '#2e3350' }, position: 'left' },
        y2: { ticks: { color: '#a599ff', callback: (value) => '$' + value.toLocaleString() }, grid: { drawOnChartArea: false }, position: 'right' },
      },
    },
  });

  const monthTabs = document.getElementById('month-tabs');
  if (!monthTabs) return;

  monthTabs.addEventListener('click', (event) => {
    const tab = event.target.closest('.month-tab');
    if (!tab) return;

    document.querySelectorAll('.month-tab').forEach((item) => item.classList.remove('active'));
    document.querySelectorAll('.month-panel').forEach((panel) => panel.classList.remove('active'));
    tab.classList.add('active');
    const panel = document.getElementById(tab.dataset.panel);
    if (panel) {
      panel.classList.add('active');
    }
  });
}

function initializeReports() {
  const canvas = document.getElementById('donutChart');
  if (!canvas) return;

  const chartData = JSON.parse(canvas.dataset.chartData || '{}');
  if (!chartData.categories || !chartData.amounts) return;

  new Chart(canvas.getContext('2d'), {
    type: 'doughnut',
    data: {
      labels: chartData.categories,
      datasets: [{
        data: chartData.amounts,
        backgroundColor: chartData.colors.map((color) => color + 'cc'),
        borderColor: chartData.colors,
        borderWidth: 1,
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: {
          position: 'bottom',
          labels: { color: '#8b90b0', font: { family: 'DM Sans', size: 11 }, padding: 10 }
        },
        tooltip: {
          callbacks: {
            label: (context) => ` $${context.parsed.toFixed(2)}`
          }
        }
      }
    }
  });
}

function initializeRuleForm() {
  const keywordField = document.getElementById('id_keyword');
  if (!keywordField) return;

  const previewPanel = document.querySelector('.preview-panel');
  if (!previewPanel) return;

  const allDescriptions = JSON.parse(previewPanel.dataset.descriptions || '[]');

  function escapeRegex(value) {
    return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  function testRule(keyword, matchType, description) {
    if (!keyword) return false;

    const desc = description.toLowerCase();
    const kw = keyword.toLowerCase();

    switch (matchType) {
      case 'contains':
        return desc.includes(kw);
      case 'exact':
        return desc === kw;
      case 'startswith':
        return desc.startsWith(kw);
      case 'endswith':
        return desc.endsWith(kw);
      case 'regex':
        try {
          return new RegExp(keyword, 'i').test(description);
        } catch {
          return false;
        }
    }

    return false;
  }

  function updatePreview() {
    const keyword = keywordField.value.trim();
    const matchType = document.getElementById('id_match_type').value;
    const list = document.getElementById('preview-list');
    const countEl = document.getElementById('match-count');

    if (!keyword) {
      list.innerHTML = '<div class="no-matches">Enter a keyword to see matching transactions.</div>';
      countEl.textContent = '0';
      return;
    }

    const matches = allDescriptions.filter((description) => testRule(keyword, matchType, description));
    const unique = [...new Set(matches)].slice(0, 8);
    countEl.textContent = matches.length;

    if (unique.length === 0) {
      list.innerHTML = '<div class="no-matches">No existing transactions match this rule.</div>';
      return;
    }

    list.innerHTML = unique.map((description) => `
      <div class="preview-match">
        <span class="match-icon">✓</span>
        <span class="desc">${description}</span>
      </div>
    `).join('');

    if (matches.length > 8) {
      list.innerHTML += `<div style="font-size:0.75rem; color:var(--muted); margin-top:6px;">…and ${matches.length - 8} more</div>`;
    }
  }

  keywordField.addEventListener('input', updatePreview);
  document.getElementById('id_match_type').addEventListener('change', updatePreview);
  updatePreview();
}
