/* ============================================================
   dashboard.js
   CHANGED: Custom splits now expand inline inside the expense
            form instead of opening a separate panel.
   UNCHANGED: All validation logic, fetch calls, equal/unequal
              share calculation, selectAll, finish, bill synopsis.
   ============================================================ */

document.addEventListener("DOMContentLoaded", () => {

const addExpenseBtn       = document.getElementById("addExpenseBtn");
const finishBtn           = document.getElementById("FinishBtn");
const billBtn             = document.getElementById("billBtn");
const expenseForm         = document.getElementById("expenseForm");
const cancelExpenseBtn    = document.getElementById("cancelExpenseBtn");
const saveExpenseBtn      = document.getElementById("saveExpenseBtn");
const expenseContainer    = document.getElementById("expenseContainer");
const shareForm           = document.getElementById("shareForm");
const customSplitsSection = document.getElementById("customSplitsSection");
const splitsHint          = document.getElementById("splitsHint");
const splitsRemaining     = document.getElementById("splitsRemaining");
const synopsisContainer   = document.getElementById("synopsisContainer");
const synopsisContent     = document.getElementById("synopsisContent");
const closeBtn            = document.getElementById("closeSynopsis");
const expenseBackdrop     = document.getElementById("expenseBackdrop");
const synopsisBackdrop    = document.getElementById("synopsisBackdrop");

let paidby = "";
let tempReason = "";
let tempAmount = "";
let selectedmembers = [];

// ── Show / hide expense form ──────────────────────────────────────────────
addExpenseBtn.addEventListener("click", () => {
  expenseForm.classList.remove("hidden");
  expenseBackdrop.classList.remove("hidden");
  hideModalError(document.getElementById("expenseErrorBanner"));
});

function closeExpenseForm() {
  expenseForm.classList.add("hidden");
  expenseBackdrop.classList.add("hidden");
  collapseCustomSplits();
}
cancelExpenseBtn.addEventListener("click", closeExpenseForm);

// ── "Select All" checkbox logic (ORIGINAL — unchanged) ───────────────────
const selectAll        = document.getElementById("selectAll");
const memberCheckboxes = document.querySelectorAll('input[name="members"]');

selectAll.addEventListener("change", () => {
  memberCheckboxes.forEach(cb => cb.checked = selectAll.checked);
  if (isCustomMode()) rebuildCustomInputs();
});

memberCheckboxes.forEach(cb => {
  cb.addEventListener("change", () => {
    if (!cb.checked) {
      selectAll.checked = false;
    } else if (Array.from(memberCheckboxes).every(m => m.checked)) {
      selectAll.checked = true;
    }
    // Rebuild inputs live when member selection changes in custom mode
    if (isCustomMode()) rebuildCustomInputs();
  });
});

// ── Split type toggle ─────────────────────────────────────────────────────
document.querySelectorAll('input[name="shareType"]').forEach(radio => {
  radio.addEventListener('change', () => {
    document.querySelectorAll('.toggle-opt').forEach(l => l.classList.remove('active'));
    radio.closest('.toggle-opt').classList.add('active');
    if (radio.value === "unequal") {
      expandCustomSplits();
    } else {
      collapseCustomSplits();
    }
  });
});

function isCustomMode() {
  const checked = document.querySelector("input[name='shareType']:checked");
  return checked && checked.value === "unequal";
}

function expandCustomSplits() {
  rebuildCustomInputs();
  customSplitsSection.classList.remove("collapsed");
  customSplitsSection.classList.add("expanded");
}

function collapseCustomSplits() {
  customSplitsSection.classList.remove("expanded");
  customSplitsSection.classList.add("collapsed");
  if (shareForm) shareForm.innerHTML = "";
}

// ── Build one input row per selected member ───────────────────────────────
function rebuildCustomInputs() {
  const checkedBoxes     = document.querySelectorAll(".member-checkboxes input[name='members']:checked");
  const currentMembers   = Array.from(checkedBoxes).map(cb => cb.value);
  const amount           = parseFloat(document.getElementById("expenseAmount").value) || 0;

  if (splitsHint) {
    splitsHint.textContent = amount > 0
      ? `Shares must add up to ₹${amount.toFixed(2)}`
      : "Enter the total amount above first.";
  }

  shareForm.innerHTML = "";
  currentMembers.forEach(member => {
    const row = document.createElement("div");
    row.className = "inline-share-row";

    const avatar = document.createElement("span");
    avatar.className = "inline-share-avatar";
    avatar.textContent = member[0].toUpperCase();

    const name = document.createElement("span");
    name.className = "inline-share-name";
    name.textContent = member;

    const input = document.createElement("input");
    input.type        = "number";
    input.placeholder = "0.00";
    input.min         = "0";
    input.classList.add("share-input", "inline-share-input");
    input.addEventListener("input", updateRemaining);

    row.appendChild(avatar);
    row.appendChild(name);
    row.appendChild(input);
    shareForm.appendChild(row);
  });

  updateRemaining();
}

// ── Live remaining counter ────────────────────────────────────────────────
function updateRemaining() {
  const amount    = parseFloat(document.getElementById("expenseAmount").value) || 0;
  const inputs    = document.querySelectorAll(".inline-share-input");
  const entered   = Array.from(inputs).reduce((s, i) => s + (parseFloat(i.value) || 0), 0);
  const remaining = roundTo(amount - entered, 2);

  if (splitsRemaining) {
    splitsRemaining.textContent = `₹${remaining.toFixed(2)}`;
    splitsRemaining.className   = "splits-total-value " +
      (Math.abs(remaining) < 0.01 ? "remaining-ok" : remaining < 0 ? "remaining-over" : "");
  }
}

// Rebuild when amount field changes while in custom mode
document.getElementById("expenseAmount").addEventListener("input", () => {
  if (isCustomMode()) rebuildCustomInputs();
});

// ── Save expense (ORIGINAL validation — unchanged) ────────────────────────
saveExpenseBtn.addEventListener("click", () => {
  const reason    = document.getElementById("expenseReason").value.trim();
  const amount    = document.getElementById("expenseAmount").value;
  paidby          = document.getElementById("paidby").value.trim();
  const checkedBoxes = document.querySelectorAll(".member-checkboxes input[name='members']:checked");
  selectedmembers    = Array.from(checkedBoxes).map(cb => cb.value);
  const shareType    = document.querySelector("input[name='shareType']:checked").value;

  // Original validation (unchanged)
  if (!reason || !amount)                        { showModalError(document.getElementById("expenseErrorBanner"), "Please enter a reason and amount."); return; }
  if (amount <= 0)                               { showModalError(document.getElementById("expenseErrorBanner"), "Amount must be greater than 0."); return; }
  if (!paidby || !members.includes(paidby))      { showModalError(document.getElementById("expenseErrorBanner"), "Payer must be a member of this trip."); return; }
  if (selectedmembers.length === 0)              { showModalError(document.getElementById("expenseErrorBanner"), "Please select at least one member."); return; }

  tempReason = reason;
  tempAmount = amount;

  if (shareType === "equal") {
    // Equal split (ORIGINAL — unchanged)
    const share  = Math.round((amount / selectedmembers.length) * 100) / 100;
    const shares = Array(selectedmembers.length).fill(share);
    addExpenseCard(reason, amount, selectedmembers, shares, paidby);
    resetExpenseForm();

  } else {
    // Custom split — read inline inputs, validate (ORIGINAL logic — unchanged)
    const inputs = document.querySelectorAll(".inline-share-input");
    const shares = Array.from(inputs)
      .map(i => roundTo(Number(i.value.trim()), 2))
      .filter(v => !isNaN(v) && v >= 0);

    if (shares.length !== selectedmembers.length) {
      showModalError(document.getElementById("sharesErrorBanner"), "Please fill in all share amounts."); return;
    }

    const total = roundTo(shares.reduce((sum, v) => sum + v, 0), 2);
    // ORIGINAL check: shares must match total amount exactly
    if (total !== roundTo(Number(tempAmount), 2)) {
      showModalError(document.getElementById("sharesErrorBanner"), `Shares total ₹${total.toFixed(2)} but expense is ₹${Number(tempAmount).toFixed(2)} — they must match.`); return;
    }

    addExpenseCard(tempReason, tempAmount, selectedmembers, shares, paidby);
    resetExpenseForm();
  }
});

// ── Enter key (ORIGINAL — unchanged) ─────────────────────────────────────
document.addEventListener("keydown", function(event) {
  if (event.key === "Enter") {
    event.preventDefault();
    if (!expenseForm.classList.contains("hidden")) saveExpenseBtn.click();
  }
});

// ── Add expense card + POST to backend (ORIGINAL — unchanged) ─────────────
async function addExpenseCard(reason, amount, members, shares, whopaid) {
  try {
    const response = await fetch(`/add_expense/${tripId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason, amount, members, shares, whopaid })
    });
    const result = await response.json();

    if (result.status === "success") {
      const expenseId = result.expense_id;
      buildExpenseCard(reason, amount, members, shares, whopaid, expenseId);
    } else if (result.status === "error") {
      showToast(result.message || 'Failed to save expense.', 'error');
    } else {
      showToast('Failed to save expense. Please try again.', 'error');
    }
  } catch (error) {
    showToast('Connection error. Please check your network.', 'error');
  }
}

// ── Reset form ────────────────────────────────────────────────────────────
function resetExpenseForm() {
  closeExpenseForm();
  document.getElementById("expenseReason").value = "";
  document.getElementById("expenseAmount").value = "";
  document.getElementById("paidby").value = "";
  document.querySelectorAll(".member-checkboxes input[type='checkbox']")
    .forEach(cb => cb.checked = false);
  // Reset split toggle back to Equal
  const equalRadio = document.querySelector("input[name='shareType'][value='equal']");
  if (equalRadio) {
    equalRadio.checked = true;
    document.querySelectorAll('.toggle-opt').forEach(l => l.classList.remove('active'));
    equalRadio.closest('.toggle-opt').classList.add('active');
  }
  collapseCustomSplits();
}

// ── Helpers ───────────────────────────────────────────────────────────────
function capitalize(s) { return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase(); }
function roundTo(num, decimals) { return Math.round(num * 10 ** decimals) / 10 ** decimals; }

// ── Finish button — only rendered for creators, guard null check ──────────
if (finishBtn) {
  finishBtn.addEventListener("click", async () => {
    if (confirm("Are you sure you want to finish the trip?")) {
      await fetch(`/finish_trip/${tripId}`, { method: "POST" });
      window.location.href = `/results/${tripId}`;
    }
  });
}

// ── Bill synopsis (ORIGINAL — unchanged) ─────────────────────────────────
billBtn.addEventListener("click", async () => {
  try {
    const response = await fetch(`/get_data/${tripId}`);
    if (!response.ok) throw new Error("Network error");
    const data = await response.json();
    const listItems = data.map(item => `<li>${item}</li>`).join("");
    synopsisContent.innerHTML = `
      <h2>Wallet Drained</h2>
      <h3>Amount spent so far</h3>
      <ul style="list-style:none;padding:0">${listItems}</ul>
    `;
    synopsisContainer.classList.remove("hidden");
    synopsisBackdrop.classList.remove("hidden");
  } catch (err) {
    console.error("Failed to fetch data:", err);
    showToast('Could not load spending data.', 'error');
  }
});

closeBtn.addEventListener("click", () => {
  synopsisContainer.classList.add("hidden");
  synopsisBackdrop.classList.add("hidden");
});

// ── Second cancel button ──────────────────────────────────────────────────
const cancelBtn2 = document.getElementById('cancelExpenseBtn2');
if (cancelBtn2) cancelBtn2.addEventListener('click', closeExpenseForm);

// ── Backdrop clicks ───────────────────────────────────────────────────────
expenseBackdrop.addEventListener('click', closeExpenseForm);
synopsisBackdrop.addEventListener('click', () => {
  synopsisContainer.classList.add("hidden");
  synopsisBackdrop.classList.add("hidden");
});

// ── Escape key ────────────────────────────────────────────────────────────
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    synopsisContainer.classList.add("hidden");
    synopsisBackdrop.classList.add("hidden");
    hideConfirm();
    closeExpenseForm();
  }
});

// ── Empty feed observer ───────────────────────────────────────────────────
const feedEmpty = document.getElementById('feedEmpty');
if (feedEmpty && expenseContainer) {
  const observer = new MutationObserver(() => {
    feedEmpty.style.display = expenseContainer.children.length > 0 ? 'none' : 'flex';
  });
  observer.observe(expenseContainer, { childList: true });
}

// ── Confirm modal system ─────────────────────────────────────────────────
// Single modal reused for any delete confirmation.
const confirmModal    = document.getElementById('confirmModal');
const confirmBackdrop = document.getElementById('confirmBackdrop');
const confirmTitle    = document.getElementById('confirmTitle');
const confirmMessage  = document.getElementById('confirmMessage');
const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
const confirmCancelBtn = document.getElementById('confirmCancelBtn');

function showConfirm(title, message, onConfirm) {
  confirmTitle.textContent   = title;
  confirmMessage.textContent = message;
  confirmModal.classList.remove('hidden');
  confirmBackdrop.classList.remove('hidden');
  confirmDeleteBtn.disabled  = false;

  // Reassign onclick directly — cleanest way to swap the callback
  // without stacking multiple listeners from previous calls.
  confirmDeleteBtn.onclick = async () => {
    confirmDeleteBtn.disabled = true;   // prevent double-click
    await onConfirm();
    hideConfirm();
  };
}

function hideConfirm() {
  confirmModal.classList.add('hidden');
  confirmBackdrop.classList.add('hidden');
}

confirmCancelBtn.addEventListener('click', hideConfirm);
confirmBackdrop.addEventListener('click', hideConfirm);

// ── buildExpenseCard — shared by addExpenseCard and loadExistingExpenses ───
// Builds a card DOM element with a delete button and appends to the grid.
function buildExpenseCard(reason, amount, memberNames, shares, whopaid, expenseId) {
  const card = document.createElement("div");
  card.className = "expense-card";
  card.dataset.expenseId = expenseId;

  const membersList = memberNames
    .map((m, i) => `<li>${capitalize(m)}: <strong style="color:var(--amber)">₹${shares[i]}</strong></li>`)
    .join("");

  card.innerHTML = `
    <div class="card-top-row">
      <strong>${reason.toUpperCase()}</strong>
      <button class="card-delete-btn" title="Delete expense">🗑</button>
    </div>
    <p style="color:var(--text-secondary);font-size:0.88rem;margin:4px 0 10px">
      ₹${amount} paid by <span style="color:var(--amber);font-weight:700">${capitalize(whopaid)}</span>
    </p>
    <ul style="list-style:none;padding:0">${membersList}</ul>
  `;

  // Wire delete button
  card.querySelector('.card-delete-btn').addEventListener('click', () => {
    showConfirm(
      'Delete Expense',
      `Delete "${reason}" (₹${amount})? This cannot be undone.`,
      async () => {
        const res    = await fetch(`/delete_expense/${expenseId}`, { method: 'POST' });
        const result = await res.json();
        if (result.status === 'success') {
          card.remove();
        } else {
          showToast(result.message || 'Failed to delete expense.', 'error');
        }
      }
    );
  });

  expenseContainer.appendChild(card);
}

// ── Load existing expenses from DB on page load ───────────────────────────
// Renders cards for expenses already saved in a previous session,
// using the same HTML structure as addExpenseCard so they look identical.
async function loadExistingExpenses() {
  try {
    const response = await fetch(`/get_expenses/${tripId}`);
    if (!response.ok) return;
    const expenses = await response.json();

    expenses.forEach(exp => {
      buildExpenseCard(exp.reason, exp.amount,
        exp.splits.map(s => s.name),
        exp.splits.map(s => s.share),
        exp.whopaid, exp.id);
    });
  } catch (err) {
    console.error("Could not load existing expenses:", err);
  }
}

loadExistingExpenses();

}); // end DOMContentLoaded
