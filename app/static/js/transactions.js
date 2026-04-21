document.addEventListener("DOMContentLoaded", () => {
  const filtersForm = document.getElementById("transaction-filters");
  const resetFiltersBtn = document.getElementById("reset-filters");
  const createForm = document.getElementById("create-transaction-form");
  const editForm = document.getElementById("edit-transaction-form");
  const editPlaceholder = document.getElementById("transaction-edit-placeholder");
  const cancelEditBtn = document.getElementById("cancel-edit");
  const tableBody = document.getElementById("transactions-table-body");
  const messageEl = document.getElementById("transactions-message");
  const initialDataEl = document.getElementById("initial-transactions-data");

  let transactions = [];
  if (initialDataEl && initialDataEl.textContent) {
    try {
      transactions = JSON.parse(initialDataEl.textContent);
    } catch (_err) {
      transactions = [];
    }
  }

  renderTransactions(transactions);

  filtersForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    await refreshTransactions();
  });

  resetFiltersBtn?.addEventListener("click", async () => {
    if (!filtersForm) {
      return;
    }
    filtersForm.reset();
    await refreshTransactions();
  });

  createForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = formToPayload(createForm);

    const response = await fetch("/transactions/api", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (!response.ok) {
      setMessage(data.error || "Failed to create transaction.", true);
      return;
    }

    createForm.reset();
    const createType = document.getElementById("create-transaction-type");
    if (createType) {
      createType.value = "expense";
    }
    setMessage("Transaction created.", false);
    notifyFinanceDataChanged("transaction_created");
    await refreshTransactions();
  });

  cancelEditBtn?.addEventListener("click", () => {
    hideEditForm();
  });

  editForm?.addEventListener("submit", async (event) => {
    event.preventDefault();

    const transactionId = document.getElementById("edit-transaction-id")?.value;
    if (!transactionId) {
      setMessage("No transaction selected for editing.", true);
      return;
    }

    const payload = formToPayload(editForm);
    const response = await fetch(`/transactions/api/${transactionId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (!response.ok) {
      setMessage(data.error || "Failed to update transaction.", true);
      return;
    }

    setMessage("Transaction updated.", false);
    hideEditForm();
    notifyFinanceDataChanged("transaction_updated");
    await refreshTransactions();
  });

  tableBody?.addEventListener("click", async (event) => {
    const button = event.target.closest("button");
    if (!button) {
      return;
    }

    const row = button.closest("tr");
    if (!row) {
      return;
    }

    const transactionId = row.dataset.transactionId;
    if (!transactionId) {
      return;
    }

    if (button.classList.contains("delete-transaction")) {
      const confirmed = window.confirm("Delete this transaction?");
      if (!confirmed) {
        return;
      }

      const response = await fetch(`/transactions/api/${transactionId}`, {
        method: "DELETE",
      });
      const data = await response.json();

      if (!response.ok) {
        setMessage(data.error || "Failed to delete transaction.", true);
        return;
      }

      setMessage("Transaction deleted.", false);
      row.remove();
      notifyFinanceDataChanged("transaction_deleted");
      return;
    }

    if (button.classList.contains("edit-transaction")) {
      populateEditForm(row.dataset);
    }
  });

  async function refreshTransactions() {
    const params = filtersForm
      ? new URLSearchParams(new FormData(filtersForm))
      : new URLSearchParams();
    const query = params.toString();
    const url = query ? `/transactions/api?${query}` : "/transactions/api";

    const response = await fetch(url, { method: "GET" });
    const data = await response.json();

    if (!response.ok) {
      setMessage(data.error || "Failed to load transactions.", true);
      return;
    }

    transactions = data.transactions || [];
    renderTransactions(transactions);
    setMessage(`Loaded ${transactions.length} transaction(s).`, false);
  }

  function renderTransactions(items) {
    if (!tableBody) {
      return;
    }

    if (!Array.isArray(items) || items.length === 0) {
      tableBody.innerHTML = "";
      return;
    }

    tableBody.innerHTML = items
      .map((tx) => {
        const amount = Number(tx.amount || 0).toFixed(2);
        const descriptionRaw = String(tx.description || "");
        const description = escapeHtml(descriptionRaw);
        const descriptionEncoded = encodeURIComponent(descriptionRaw);
        const accountName = escapeHtml(tx.account_name || "N/A");
        const categoryName = escapeHtml(tx.category_name || "N/A");
        const txType = String(tx.transaction_type || "expense");
        const amountDisplay = `${txType === "income" ? "+" : "-"}${amount}`;
        const amountClass = txType === "income" ? "tx-amount-income" : "tx-amount-expense";
        const typeTagClass = txType === "income" ? "tx-type-income" : "tx-type-expense";

        return `
          <tr
            data-transaction-id="${tx.transaction_id}"
            data-transaction-type="${tx.transaction_type}"
            data-amount="${tx.amount}"
            data-date="${tx.transaction_date}"
            data-description="${descriptionEncoded}"
            data-account-id="${tx.account_id ?? ""}"
            data-category-id="${tx.category_id ?? ""}"
          >
            <td>${tx.transaction_date}</td>
            <td><span class="tx-type-tag ${typeTagClass}">${txType}</span></td>
            <td class="${amountClass}">${amountDisplay}</td>
            <td>${description}</td>
            <td>${accountName}</td>
            <td><span class="tx-category-pill">${categoryName}</span></td>
            <td class="tx-actions-cell">
              <button class="edit-transaction" type="button">Edit</button>
              <button class="delete-transaction" type="button">Delete</button>
            </td>
          </tr>
        `;
      })
      .join("");
  }

  function formToPayload(formEl) {
    const formData = new FormData(formEl);
    return {
      transaction_type: String(formData.get("transaction_type") || "").trim(),
      amount: String(formData.get("amount") || "").trim(),
      transaction_date: String(formData.get("transaction_date") || "").trim(),
      account_id: String(formData.get("account_id") || "").trim(),
      category_id: String(formData.get("category_id") || "").trim(),
      description: String(formData.get("description") || "").trim(),
    };
  }

  function populateEditForm(dataset) {
    if (!editForm) {
      return;
    }

    const idEl = document.getElementById("edit-transaction-id");
    const typeEl = document.getElementById("edit-transaction-type");
    const amountEl = document.getElementById("edit-amount");
    const dateEl = document.getElementById("edit-date");
    const accountEl = document.getElementById("edit-account");
    const categoryEl = document.getElementById("edit-category");
    const descriptionEl = document.getElementById("edit-description");

    if (idEl) {
      idEl.value = dataset.transactionId || "";
    }
    if (typeEl) {
      typeEl.value = dataset.transactionType || "expense";
    }
    if (amountEl) {
      amountEl.value = dataset.amount || "";
    }
    if (dateEl) {
      dateEl.value = dataset.date || "";
    }
    if (accountEl) {
      accountEl.value = dataset.accountId || "";
    }
    if (categoryEl) {
      categoryEl.value = dataset.categoryId || "";
    }
    if (descriptionEl) {
      const encodedDescription = String(dataset.description || "").replaceAll("+", "%20");
      descriptionEl.value = decodeURIComponent(encodedDescription);
    }

    editForm.hidden = false;
    if (editPlaceholder) {
      editPlaceholder.hidden = true;
    }
    editForm.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function hideEditForm() {
    if (!editForm) {
      return;
    }
    editForm.reset();
    editForm.hidden = true;
    if (editPlaceholder) {
      editPlaceholder.hidden = false;
    }
  }

  function setMessage(message, isError) {
    if (!messageEl) {
      return;
    }
    messageEl.textContent = message;
    messageEl.style.color = isError ? "#b91c1c" : "#0f766e";
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
