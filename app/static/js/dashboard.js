document.addEventListener("DOMContentLoaded", () => {
  const filtersForm = document.getElementById("dashboard-filters");
  const monthInput = document.getElementById("dashboard-month");
  const messageEl = document.getElementById("dashboard-message");

  const incomeEl = document.getElementById("card-income");
  const expensesEl = document.getElementById("card-expenses");
  const netEl = document.getElementById("card-net");

  const spendingCanvas = document.getElementById("spending-chart");
  const budgetCanvas = document.getElementById("budget-chart");
  const budgetTableBody = document.getElementById("budget-breakdown-body");

  const initialDataEl = document.getElementById("initial-dashboard-data");

  let spendingChart;
  let budgetChart;
  let refreshTimer;

  let snapshot = {
    month: monthInput?.value || "",
    totals: { income: 0, expenses: 0, net: 0 },
    spending_by_category: [],
    budget_remaining_by_category: [],
  };

  if (initialDataEl && initialDataEl.textContent) {
    try {
      snapshot = JSON.parse(initialDataEl.textContent);
    } catch (_err) {
      // Keep fallback snapshot.
    }
  }

  renderSnapshot(snapshot);

  filtersForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    await refreshSnapshot();
  });

  monthInput?.addEventListener("change", async () => {
    await refreshSnapshot();
  });

  window.addEventListener("finance:data-changed", () => {
    scheduleRefresh(250);
  });

  window.addEventListener("storage", (event) => {
    if (event.key === "finance_data_changed_at") {
      scheduleRefresh(250);
    }
  });

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      scheduleRefresh(0);
    }
  });

  window.addEventListener("focus", () => {
    scheduleRefresh(0);
  });

  function scheduleRefresh(delayMs) {
    if (refreshTimer) {
      clearTimeout(refreshTimer);
    }
    refreshTimer = setTimeout(async () => {
      await refreshSnapshot();
    }, delayMs);
  }

  async function refreshSnapshot() {
    const month = monthInput?.value || "";
    const params = new URLSearchParams();
    if (month) {
      params.set("month", month);
    }

    const query = params.toString();
    const url = query ? `/dashboard/api/summary?${query}` : "/dashboard/api/summary";

    const response = await fetch(url, { method: "GET" });
    const data = await response.json();

    if (!response.ok) {
      setMessage(data.error || "Failed to load dashboard data.", true);
      return;
    }

    snapshot = data;
    renderSnapshot(snapshot);
    setMessage(`Dashboard updated for ${snapshot.month}.`, false);
  }

  function renderSnapshot(data) {
    if (!data) {
      return;
    }

    const totals = data.totals || {};
    if (incomeEl) {
      incomeEl.textContent = formatCurrency(totals.income || 0);
    }
    if (expensesEl) {
      expensesEl.textContent = formatCurrency(totals.expenses || 0);
    }
    if (netEl) {
      netEl.textContent = formatCurrency(totals.net || 0);
      netEl.style.color = Number(totals.net || 0) >= 0 ? "#065f46" : "#991b1b";
    }

    renderBudgetBreakdownTable(data.budget_remaining_by_category || []);
    renderSpendingChart(data.spending_by_category || []);
    renderBudgetChart(data.budget_remaining_by_category || []);
  }

  function renderBudgetBreakdownTable(rows) {
    if (!budgetTableBody) {
      return;
    }

    if (!Array.isArray(rows) || rows.length === 0) {
      budgetTableBody.innerHTML = "";
      return;
    }

    budgetTableBody.innerHTML = rows
      .map((row) => {
        return `
          <tr>
            <td>${escapeHtml(row.category_name || "")}</td>
            <td>${formatCurrency(row.budgeted || 0)}</td>
            <td>${formatCurrency(row.spent || 0)}</td>
            <td>${formatCurrency(row.remaining || 0)}</td>
          </tr>
        `;
      })
      .join("");
  }

  function renderSpendingChart(rows) {
    if (!spendingCanvas || typeof Chart === "undefined") {
      return;
    }

    const labels = rows.map((row) => row.category_name || "Uncategorized");
    const values = rows.map((row) => Number(row.total_spent || 0));

    if (spendingChart) {
      spendingChart.destroy();
    }

    spendingChart = new Chart(spendingCanvas, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: "Spent",
            data: values,
            backgroundColor: "rgba(37, 99, 235, 0.70)",
            borderColor: "rgba(37, 99, 235, 1)",
            borderWidth: 1,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: false },
        },
        scales: {
          y: {
            beginAtZero: true,
          },
        },
      },
    });
  }

  function renderBudgetChart(rows) {
    if (!budgetCanvas || typeof Chart === "undefined") {
      return;
    }

    const labels = rows.map((row) => row.category_name || "Uncategorized");
    const spentValues = rows.map((row) => Number(row.spent || 0));
    const remainingValues = rows.map((row) => Number(row.remaining || 0));

    if (budgetChart) {
      budgetChart.destroy();
    }

    budgetChart = new Chart(budgetCanvas, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: "Spent",
            data: spentValues,
            backgroundColor: "rgba(220, 38, 38, 0.70)",
            borderColor: "rgba(220, 38, 38, 1)",
            borderWidth: 1,
          },
          {
            label: "Remaining",
            data: remainingValues,
            backgroundColor: "rgba(5, 150, 105, 0.70)",
            borderColor: "rgba(5, 150, 105, 1)",
            borderWidth: 1,
          },
        ],
      },
      options: {
        responsive: true,
        scales: {
          y: {
            beginAtZero: true,
          },
        },
      },
    });
  }

  function setMessage(message, isError) {
    if (!messageEl) {
      return;
    }
    messageEl.textContent = message;
    messageEl.style.color = isError ? "#b91c1c" : "#0f766e";
  }

  function formatCurrency(amount) {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(Number(amount || 0));
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }
});
