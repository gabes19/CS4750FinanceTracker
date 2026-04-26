document.addEventListener("DOMContentLoaded", () => {
  const addFundsForm = document.getElementById("add-funds-form");
  const tableBody = document.getElementById("accounts-table-body");
  const summaryGrid = document.getElementById("accounts-summary-grid");
  const messageEl = document.getElementById("accounts-message");
  const initialDataEl = document.getElementById("initial-accounts-data");

  let accounts = [];
  let refreshTimer;

  if (initialDataEl && initialDataEl.textContent) {
    try {
      accounts = JSON.parse(initialDataEl.textContent);
    } catch (_err) {
      accounts = [];
    }
  }

  renderAccounts(accounts);

  addFundsForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = formToPayload(addFundsForm);

    const response = await fetch("/accounts/api/add-funds", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();

    if (!response.ok) {
      setMessage(data.error || "Failed to add funds.", true);
      return;
    }

    const amountInput = document.getElementById("fund-amount");
    if (amountInput) {
      amountInput.value = "";
    }

    setMessage("Funds added to account.", false);
    notifyFinanceDataChanged("account_funded");
    await refreshAccounts();
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

  async function refreshAccounts() {
    const response = await fetch("/accounts/api", { method: "GET" });
    const data = await response.json();

    if (!response.ok) {
      setMessage(data.error || "Failed to refresh accounts.", true);
      return;
    }

    accounts = data.accounts || [];
    renderAccounts(accounts);
  }

  function scheduleRefresh(delayMs) {
    if (refreshTimer) {
      clearTimeout(refreshTimer);
    }
    refreshTimer = setTimeout(async () => {
      await refreshAccounts();
    }, delayMs);
  }

  function renderAccounts(items) {
    renderSummary(items);
    renderTable(items);
  }

  function renderSummary(items) {
    if (!summaryGrid) {
      return;
    }

    if (!Array.isArray(items) || items.length === 0) {
      summaryGrid.innerHTML = "<p>No accounts available.</p>";
      return;
    }

    const total = items.reduce((sum, account) => sum + Number(account.current_balance || 0), 0);

    summaryGrid.innerHTML = `
      <article class="account-summary-card">
        <h4>Visible Accounts</h4>
        <p class="card-value">${items.length}</p>
      </article>
      <article class="account-summary-card">
        <h4>Total Balance</h4>
        <p class="card-value">${formatCurrency(total)}</p>
      </article>
    `;
  }

  function renderTable(items) {
    if (!tableBody) {
      return;
    }

    if (!Array.isArray(items) || items.length === 0) {
      tableBody.innerHTML = "";
      return;
    }

    tableBody.innerHTML = items
      .map((account) => {
        return `
          <tr>
            <td>${escapeHtml(account.account_name || "")}</td>
            <td>${escapeHtml(account.account_type || "")}</td>
            <td>${escapeHtml(account.ownership_role || "")}</td>
            <td>${account.is_active ? "Active" : "Inactive"}</td>
            <td>${formatCurrency(account.current_balance || 0)} ${escapeHtml(account.currency_code || "USD")}</td>
          </tr>
        `;
      })
      .join("");
  }

  function formToPayload(form) {
    const data = new FormData(form);
    return {
      account_id: String(data.get("account_id") || "").trim(),
      amount: String(data.get("amount") || "").trim(),
    };
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

  function notifyFinanceDataChanged(source) {
    const changedAt = Date.now();
    window.dispatchEvent(
      new CustomEvent("finance:data-changed", {
        detail: { source, changedAt },
      })
    );

    try {
      localStorage.setItem("finance_data_changed_at", String(changedAt));
    } catch (_err) {
      // Ignore storage write failures.
    }
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
