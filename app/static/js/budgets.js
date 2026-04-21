document.addEventListener("DOMContentLoaded", () => {
  const filtersForm = document.getElementById("budget-filters");
  const createForm = document.getElementById("create-budget-form");
  const editForm = document.getElementById("edit-budget-form");
  const cancelEditBtn = document.getElementById("cancel-budget-edit");
  const tableBody = document.getElementById("budgets-table-body");
  const messageEl = document.getElementById("budgets-message");
  const initialDataEl = document.getElementById("initial-budgets-data");

  let budgets = [];
  if (initialDataEl && initialDataEl.textContent) {
    try {
      budgets = JSON.parse(initialDataEl.textContent);
    } catch (_err) {
      budgets = [];
    }
  }

  renderBudgets(budgets);

  filtersForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    await refreshBudgets();
  });

  createForm?.addEventListener("submit", async (event) => {
    event.preventDefault();

    const payload = budgetPayloadFromForm(createForm);
    const response = await fetch("/budgets/api", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (!response.ok) {
      setMessage(data.error || "Failed to create budget.", true);
      return;
    }

    createForm.reset();
    setMessage("Budget created.", false);
    notifyFinanceDataChanged("budget_created");
    await refreshBudgets();
  });

  cancelEditBtn?.addEventListener("click", () => {
    hideEditForm();
  });

  editForm?.addEventListener("submit", async (event) => {
    event.preventDefault();

    const budgetId = document.getElementById("edit-budget-id")?.value;
    if (!budgetId) {
      setMessage("No budget selected for editing.", true);
      return;
    }

    const payload = budgetPayloadFromForm(editForm);

    const response = await fetch(`/budgets/api/${budgetId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (!response.ok) {
      setMessage(data.error || "Failed to update budget.", true);
      return;
    }

    setMessage("Budget updated.", false);
    hideEditForm();
    notifyFinanceDataChanged("budget_updated");
    await refreshBudgets();
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

    const budgetId = row.dataset.budgetId;
    if (!budgetId) {
      return;
    }

    if (button.classList.contains("edit-budget")) {
      populateEditForm(row.dataset);
      return;
    }

    if (button.classList.contains("delete-budget")) {
      const confirmed = window.confirm("Delete this budget?");
      if (!confirmed) {
        return;
      }

      const response = await fetch(`/budgets/api/${budgetId}`, {
        method: "DELETE",
      });

      const data = await response.json();
      if (!response.ok) {
        setMessage(data.error || "Failed to delete budget.", true);
        return;
      }

      setMessage("Budget deleted.", false);
      row.remove();
      notifyFinanceDataChanged("budget_deleted");
    }
  });

  async function refreshBudgets() {
    const params = filtersForm
      ? new URLSearchParams(new FormData(filtersForm))
      : new URLSearchParams();
    const query = params.toString();
    const url = query ? `/budgets/api?${query}` : "/budgets/api";

    const response = await fetch(url, { method: "GET" });
    const data = await response.json();

    if (!response.ok) {
      setMessage(data.error || "Failed to load budgets.", true);
      return;
    }

    budgets = data.budgets || [];
    renderBudgets(budgets);
    setMessage(`Loaded ${budgets.length} budget(s).`, false);
  }

  function renderBudgets(items) {
    if (!tableBody) {
      return;
    }

    if (!Array.isArray(items) || items.length === 0) {
      tableBody.innerHTML = "";
      return;
    }

    tableBody.innerHTML = items
      .map((budget) => {
        const categoryIds = Array.isArray(budget.category_ids)
          ? budget.category_ids.join(",")
          : "";
        const categoryNames = Array.isArray(budget.categories)
          ? budget.categories.map((cat) => cat.category_name).join(", ")
          : "N/A";
        const budgetNameRaw = String(budget.budget_name || "");
        const budgetNameEncoded = encodeURIComponent(budgetNameRaw);
        const month = String(budget.budget_month || "").slice(0, 7);

        return `
          <tr
            data-budget-id="${budget.budget_id}"
            data-budget-name="${budgetNameEncoded}" 
            data-budget-month="${month}"
            data-monthly-limit="${Number(budget.monthly_limit || 0).toFixed(2)}"
            data-category-ids="${categoryIds}"
          >
            <td>${escapeHtml(budgetNameRaw)}</td>
            <td>${month}</td>
            <td>${Number(budget.monthly_limit || 0).toFixed(2)}</td>
            <td>${escapeHtml(categoryNames)}</td>
            <td>
              <button type="button" class="edit-budget">Edit</button>
              <button type="button" class="delete-budget">Delete</button>
            </td>
          </tr>
        `;
      })
      .join("");
  }

  function budgetPayloadFromForm(formEl) {
    const formData = new FormData(formEl);
    const categorySelect = formEl.querySelector("select[name='category_ids']");
    const categoryIds = categorySelect
      ? Array.from(categorySelect.selectedOptions).map((option) => option.value)
      : [];

    return {
      budget_name: String(formData.get("budget_name") || "").trim(),
      budget_month: String(formData.get("budget_month") || "").trim(),
      monthly_limit: String(formData.get("monthly_limit") || "").trim(),
      category_ids: categoryIds,
    };
  }

  function populateEditForm(dataset) {
    if (!editForm) {
      return;
    }

    const idEl = document.getElementById("edit-budget-id");
    const nameEl = document.getElementById("edit-budget-name");
    const monthEl = document.getElementById("edit-budget-month");
    const limitEl = document.getElementById("edit-monthly-limit");
    const categoriesEl = document.getElementById("edit-category-ids");

    if (idEl) {
      idEl.value = dataset.budgetId || "";
    }
    if (nameEl) {
      const encodedName = String(dataset.budgetName || "").replaceAll("+", "%20");
      nameEl.value = decodeURIComponent(encodedName);
    }
    if (monthEl) {
      monthEl.value = dataset.budgetMonth || "";
    }
    if (limitEl) {
      limitEl.value = dataset.monthlyLimit || "0.00";
    }

    if (categoriesEl) {
      const selected = new Set(
        String(dataset.categoryIds || "")
          .split(",")
          .map((value) => value.trim())
          .filter((value) => value)
      );
      Array.from(categoriesEl.options).forEach((option) => {
        option.selected = selected.has(option.value);
      });
    }

    editForm.hidden = false;
    editForm.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function hideEditForm() {
    if (!editForm) {
      return;
    }
    editForm.reset();
    editForm.hidden = true;
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
