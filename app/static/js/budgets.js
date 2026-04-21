document.addEventListener("DOMContentLoaded", () => {
  const filtersForm = document.getElementById("budget-filters");
  const createForm = document.getElementById("create-budget-form");
  const editForm = document.getElementById("edit-budget-form");
  const editPlaceholder = document.getElementById("budget-edit-placeholder");
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
  initializeCategoryAllocationInputs(createForm);
  initializeCategoryAllocationInputs(editForm);

  filtersForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    await refreshBudgets();
  });

  createForm?.addEventListener("submit", async (event) => {
    event.preventDefault();

    let payload;
    try {
      payload = budgetPayloadFromForm(createForm);
    } catch (err) {
      setMessage(err.message || "Invalid budget form input.", true);
      return;
    }
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
    clearCategorySelections(createForm);
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

    let payload;
    try {
      payload = budgetPayloadFromForm(editForm);
    } catch (err) {
      setMessage(err.message || "Invalid budget form input.", true);
      return;
    }

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
        const categoryAllocations = budget.category_allocations || {};
        const categoryAllocationsEncoded = encodeURIComponent(
          JSON.stringify(categoryAllocations)
        );
        const categoriesHtml =
          Array.isArray(budget.categories) && budget.categories.length > 0
            ? `<ul class="budget-category-list">${budget.categories
                .map(
                  (cat) =>
                    `<li><span>${escapeHtml(cat.category_name || "")}</span><strong>${Number(
                      cat.allocated_limit || 0
                    ).toFixed(2)}</strong></li>`
                )
                .join("")}</ul>`
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
            data-category-allocations="${categoryAllocationsEncoded}"
          >
            <td>${escapeHtml(budgetNameRaw)}</td>
            <td>${month}</td>
            <td>${Number(budget.monthly_limit || 0).toFixed(2)}</td>
            <td>${categoriesHtml}</td>
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
    const categoryCheckboxes = Array.from(
      formEl.querySelectorAll("input[name='category_ids']:checked")
    );
    const categoryIds = categoryCheckboxes.map((checkbox) => checkbox.value);

    if (categoryIds.length === 0) {
      throw new Error("Select at least one category.");
    }

    const monthlyLimit = String(formData.get("monthly_limit") || "").trim();
    const monthlyLimitNum = Number(monthlyLimit);
    if (!Number.isFinite(monthlyLimitNum) || monthlyLimitNum < 0) {
      throw new Error("Enter a valid monthly limit.");
    }

    const categoryAllocations = {};
    let allocationSum = 0;
    for (const checkbox of categoryCheckboxes) {
      const allocationInput = formEl.querySelector(
        `input[data-category-allocation='${checkbox.value}']`
      );
      const allocationValue = String(allocationInput?.value || "").trim();
      const allocationNum = Number(allocationValue);
      if (!Number.isFinite(allocationNum) || allocationNum < 0) {
        throw new Error("Each selected category must have a valid allocation amount.");
      }
      categoryAllocations[String(checkbox.value)] = allocationValue;
      allocationSum += allocationNum;
    }

    if (Math.abs(allocationSum - monthlyLimitNum) > 0.0001) {
      throw new Error("Category allocations must add up exactly to the monthly limit.");
    }

    return {
      budget_name: String(formData.get("budget_name") || "").trim(),
      budget_month: String(formData.get("budget_month") || "").trim(),
      monthly_limit: monthlyLimit,
      category_ids: categoryIds,
      category_allocations: categoryAllocations,
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

    const selected = new Set(
      String(dataset.categoryIds || "")
        .split(",")
        .map((value) => value.trim())
        .filter((value) => value)
    );
    setCategorySelections(editForm, selected);
    setCategoryAllocations(
      editForm,
      parseCategoryAllocations(dataset.categoryAllocations)
    );

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
    clearCategorySelections(editForm);
    editForm.hidden = true;
    if (editPlaceholder) {
      editPlaceholder.hidden = false;
    }
  }

  function setCategorySelections(formEl, selectedValues) {
    Array.from(formEl.querySelectorAll("input[name='category_ids']")).forEach((checkbox) => {
      checkbox.checked = selectedValues.has(checkbox.value);
      toggleAllocationInput(formEl, checkbox);
    });
  }

  function clearCategorySelections(formEl) {
    setCategorySelections(formEl, new Set());
    setCategoryAllocations(formEl, {});
  }

  function initializeCategoryAllocationInputs(formEl) {
    if (!formEl) {
      return;
    }
    Array.from(formEl.querySelectorAll("input[name='category_ids']")).forEach((checkbox) => {
      checkbox.addEventListener("change", () => {
        toggleAllocationInput(formEl, checkbox);
      });
      toggleAllocationInput(formEl, checkbox);
    });

    Array.from(formEl.querySelectorAll("input[data-category-allocation]")).forEach((inputEl) => {
      inputEl.addEventListener("click", (event) => {
        event.stopPropagation();
      });
    });
  }

  function toggleAllocationInput(formEl, checkbox) {
    const allocationInput = formEl.querySelector(
      `input[data-category-allocation='${checkbox.value}']`
    );
    if (!allocationInput) {
      return;
    }

    if (checkbox.checked) {
      allocationInput.disabled = false;
      allocationInput.required = true;
      if (!allocationInput.value) {
        allocationInput.value = "0.00";
      }
    } else {
      allocationInput.disabled = true;
      allocationInput.required = false;
      allocationInput.value = "";
    }
  }

  function setCategoryAllocations(formEl, allocations) {
    Array.from(formEl.querySelectorAll("input[data-category-allocation]")).forEach((inputEl) => {
      const categoryId = String(inputEl.dataset.categoryAllocation || "");
      const value = allocations[categoryId];
      inputEl.value =
        value !== undefined && value !== null && value !== ""
          ? Number(value).toFixed(2)
          : "";
    });
  }

  function parseCategoryAllocations(rawValue) {
    if (!rawValue) {
      return {};
    }

    try {
      const decoded = decodeURIComponent(String(rawValue).replaceAll("+", "%20"));
      const parsed = JSON.parse(decoded);
      return typeof parsed === "object" && parsed !== null ? parsed : {};
    } catch (_err) {
      return {};
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
