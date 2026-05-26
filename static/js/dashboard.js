/* ============================================================
   dashboard.js
   CHANGED: Custom splits now expand inline inside the expense
            form instead of opening a separate panel.
            Full polling hardening: all 7 race conditions patched.
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

// ── State flags — prevent ALL race conditions ─────────────────────────────
// isSaving  : true while a POST /add_expense is in-flight
// isDeleting: true while the confirm-delete modal is open
// isSyncing : true while forceSyncExpenses is running (prevents overlapping syncs)
let isSaving   = false;
let isDeleting = false;
let isSyncing  = false;

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
  hideModalError(document.getElementById("expenseErrorBanner"));
  hideModalError(document.getElementById("sharesErrorBanner"));
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
  hideModalError(document.getElementById("sharesErrorBanner"));
}

function collapseCustomSplits() {
  customSplitsSection.classList.remove("expanded");
  customSplitsSection.classList.add("collapsed");
  if (shareForm) shareForm.innerHTML = "";
}

// ── Build one input row per selected member ───────────────────────────────
function rebuildCustomInputs() {
  const checkedBoxes   = document.querySelectorAll(".member-checkboxes input[name='members']:checked");
  const currentMembers = Array.from(checkedBoxes).map(cb => cb.value);
  const amount         = parseFloat(document.getElementById("expenseAmount").value) || 0;

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
    input.addEventListener("input", (e) => {
      const val = e.target.value;
      if (val.includes(".")) {
        const parts = val.split(".");
        if (parts[1].length > 2) {
          e.target.value = parts[0] + "." + parts[1].slice(0, 2);
        }
      }
      updateRemaining();
    });

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

  const sharesErr = document.getElementById("sharesErrorBanner");
  if (sharesErr) hideModalError(sharesErr);
}

// Rebuild when amount field changes while in custom mode
document.getElementById("expenseAmount").addEventListener("input", () => {
  if (isCustomMode()) rebuildCustomInputs();
});

// ── Reason field: only alphanumerics and spaces allowed ──────────────────
document.getElementById("expenseReason").addEventListener("input", (e) => {
  const cleaned = e.target.value.replace(/[^a-zA-Z0-9 ]/g, "");
  if (cleaned !== e.target.value) {
    e.target.value = cleaned;
  }
  hideModalError(document.getElementById("expenseErrorBanner"));
});

// ── Clear expenseErrorBanner when user interacts with any expense field ───
["expenseAmount", "paidby"].forEach(id => {
  document.getElementById(id).addEventListener("input", () => {
    hideModalError(document.getElementById("expenseErrorBanner"));
  });
});
document.querySelectorAll('input[name="members"]').forEach(cb => {
  cb.addEventListener("change", () => {
    hideModalError(document.getElementById("expenseErrorBanner"));
  });
});

// ── Save expense (ORIGINAL validation — unchanged) ────────────────────────
saveExpenseBtn.addEventListener("click", () => {
  const reason       = document.getElementById("expenseReason").value.trim();
  const amount       = document.getElementById("expenseAmount").value;
  paidby             = document.getElementById("paidby").value.trim();
  const checkedBoxes = document.querySelectorAll(".member-checkboxes input[name='members']:checked");
  selectedmembers    = Array.from(checkedBoxes).map(cb => cb.value);
  const shareType    = document.querySelector("input[name='shareType']:checked").value;

  // Validation
  if (!reason || !amount)                        { showModalError(document.getElementById("expenseErrorBanner"), "Please enter a reason and amount."); return; }
  if (!/^[a-zA-Z0-9 ]+$/.test(reason))          { showModalError(document.getElementById("expenseErrorBanner"), "Reason can only contain letters, numbers and spaces."); return; }
  if (amount <= 0)                               { showModalError(document.getElementById("expenseErrorBanner"), "Amount must be greater than 0."); return; }
  if (!paidby || !members.includes(paidby))      { showModalError(document.getElementById("expenseErrorBanner"), "Payer must be a member of this trip."); return; }
  if (selectedmembers.length === 0)              { showModalError(document.getElementById("expenseErrorBanner"), "Please select at least one member."); return; }

  tempReason = reason;
  tempAmount = amount;

  if (shareType === "equal") {
    const share  = Math.round((amount / selectedmembers.length) * 100) / 100;
    const shares = Array(selectedmembers.length).fill(share);
    // Close form immediately for snappy UX — sync will draw the card
    resetExpenseForm();
    addExpenseCard(reason, amount, selectedmembers, shares, paidby);

  } else {
    const inputs = document.querySelectorAll(".inline-share-input");
    const shares = Array.from(inputs)
      .map(i => roundTo(Number(i.value.trim()), 2))
      .filter(v => !isNaN(v) && v >= 0);

    if (shares.length !== selectedmembers.length) {
      showModalError(document.getElementById("sharesErrorBanner"), "Please fill in all share amounts."); return;
    }
    if (shares.some(v => v <= 0)) {
      showModalError(document.getElementById("sharesErrorBanner"), "Each share amount must be greater than 0."); return;
    }

    const total = roundTo(shares.reduce((sum, v) => sum + v, 0), 2);
    if (total !== roundTo(Number(tempAmount), 2)) {
      showModalError(document.getElementById("sharesErrorBanner"), `Shares total ₹${total.toFixed(2)} but expense is ₹${Number(tempAmount).toFixed(2)} — they must match.`); return;
    }

    resetExpenseForm();
    addExpenseCard(tempReason, tempAmount, selectedmembers, shares, paidby);
  }
});

// ── Enter key (ORIGINAL — unchanged) ─────────────────────────────────────
document.addEventListener("keydown", function(event) {
  if (event.key === "Enter") {
    event.preventDefault();
    if (!expenseForm.classList.contains("hidden")) saveExpenseBtn.click();
  }
});

// ── Add expense card + POST to backend ────────────────────────────────────
// FIX (Stuck Row + 30s Lag): isSaving is released BEFORE forceSyncExpenses
// so the sync fetch is not gated by the flag itself. The form is already
// closed by the time we reach here, so no flickering can occur.
async function addExpenseCard(reason, amount, members, shares, whopaid) {
  isSaving = true;
  try {
    const response = await fetch(`/add_expense/${tripId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason, amount, members, shares, whopaid })
    });

    if (response.status === 403) {
      isSaving = false; // Release the gate immediately
      showToast('This trip has been finished. Redirecting...', 'info');
      
      // Delays navigation slightly so the user can read the toast message
      setTimeout(() => {
        window.location.href = `/results/${tripId}`;
      }, 1500);
      return;
    }

    const result = await response.json();

    if (result.status === "success") {
      // Release flag FIRST so the upcoming sync is not blocked by isSaving
      isSaving = false;
      // Then immediately sync — picks up our new card AND any concurrent
      // additions from teammates (fixes 30-second collaborative lag)
      await forceSyncExpenses();
    } else if (result.status === "error") {
      showToast(result.message || 'Failed to save expense.', 'error');
    } else {
      showToast('Failed to save expense. Please try again.', 'error');
    }
  } catch (error) {
    showToast('Connection error. Please check your network.', 'error');
  } finally {
    // Guarantee flag release even if forceSyncExpenses threw
    isSaving = false;
  }
}

// ── Reset form ────────────────────────────────────────────────────────────
// FIX (UI Flickering): resetExpenseForm is now called BEFORE addExpenseCard
// in the save handler above, so the modal is fully gone before any DOM
// card operations begin — no overlap between closing animation and grid redraw.
function resetExpenseForm() {
  closeExpenseForm();
  document.getElementById("expenseReason").value = "";
  document.getElementById("expenseAmount").value = "";
  document.getElementById("paidby").value = "";
  document.querySelectorAll(".member-checkboxes input[type='checkbox']")
    .forEach(cb => cb.checked = false);
  const equalRadio = document.querySelector("input[name='shareType'][value='equal']");
  if (equalRadio) {
    equalRadio.checked = true;
    document.querySelectorAll('.toggle-opt').forEach(l => l.classList.remove('active'));
    equalRadio.closest('.toggle-opt').classList.add('active');
  }
  const sharesErr = document.getElementById("sharesErrorBanner");
  if (sharesErr) hideModalError(sharesErr);
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

// ── Confirm modal system ──────────────────────────────────────────────────
const confirmModal     = document.getElementById('confirmModal');
const confirmBackdrop  = document.getElementById('confirmBackdrop');
const confirmTitle     = document.getElementById('confirmTitle');
const confirmMessage   = document.getElementById('confirmMessage');
const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
const confirmCancelBtn = document.getElementById('confirmCancelBtn');

function showConfirm(title, message, onConfirm) {
  confirmTitle.textContent   = title;
  confirmMessage.textContent = message;
  confirmModal.classList.remove('hidden');
  confirmBackdrop.classList.remove('hidden');
  confirmDeleteBtn.disabled  = false;
  isDeleting = true;   // block polling while confirm modal is open

  confirmDeleteBtn.onclick = async () => {
    confirmDeleteBtn.disabled = true;
    await onConfirm();
    hideConfirm();
  };
}

function hideConfirm() {
  confirmModal.classList.add('hidden');
  confirmBackdrop.classList.add('hidden');
  isDeleting = false;
}

confirmCancelBtn.addEventListener('click', hideConfirm);
confirmBackdrop.addEventListener('click', hideConfirm);

// ── buildExpenseCardElement — builds and RETURNS a card, does NOT append ──
// FIX (Out-of-Order glitch + Ghost Card Duplication): separating construction
// from insertion means diffExpenseCards controls exactly where each card
// lands in the DOM order, and delete callbacks always reference a live node.
// FIX (Ghost Modification): data-fingerprint is set here so diffExpenseCards
// can detect content changes even when the expense ID is unchanged.
function buildExpenseCardElement(reason, amount, memberNames, shares, whopaid, expenseId) {
  const card = document.createElement("div");
  card.className = "expense-card";
  card.dataset.expenseId   = String(expenseId);
  // Fingerprint covers every visible field — any server-side edit is detected
  card.dataset.fingerprint = `${reason}|${amount}|${whopaid}|${shares.join(',')}`;

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

  // FIX (Ghost Card Duplication): the delete handler calls forceSyncExpenses
  // after a confirmed delete. This guarantees the next DOM state is fetched
  // fresh from the DB — no stale card reference can survive.
  card.querySelector('.card-delete-btn').addEventListener('click', () => {
    showConfirm(
      'Delete Expense',
      `Delete "${reason}" (₹${amount})? This cannot be undone.`,
      async () => {
        const res    = await fetch(`/delete_expense/${expenseId}`, { method: 'POST' });
        const result = await res.json();
        if (result.status === 'success') {
          // Remove immediately for instant feedback, then sync to reconcile
          card.remove();
          await forceSyncExpenses();
        } else {
          showToast(result.message || 'Failed to delete expense.', 'error');
        }
      }
    );
  });

  return card;
}

// ── buildExpenseCard — convenience wrapper: build + append ────────────────
// Used only by loadExistingExpenses (initial full render).
// All other paths go through diffExpenseCards which calls buildExpenseCardElement.
function buildExpenseCard(reason, amount, memberNames, shares, whopaid, expenseId) {
  const card = buildExpenseCardElement(reason, amount, memberNames, shares, whopaid, expenseId);
  expenseContainer.appendChild(card);
}

// ── Smart Chronological DOM diff Engine ───────────────────────────────────
// FIX (Out-of-Order Insertion): instead of appendChild, every card is placed
// at its exact index position using insertBefore, matching the server order.
// FIX (Vanishing Submission race): surgical per-card ops replace innerHTML=""
// so an in-flight save never wipes a card that hasn't been persisted yet.
// FIX (Ghost Modification): fingerprint comparison detects silent edits.
// FIX (UI Flickering): no full container clear, no layout thrash.
function diffExpenseCards(expenses) {
  // Wipe only when DB confirms the trip is truly empty
  if (expenses.length === 0) {
    expenseContainer.innerHTML = "";
    return;
  }

  // 1. Remove cards that no longer exist in the DB
  //    Guard isDeleting so a mid-confirmation poll doesn't ghost the card
  const dbIds = new Set(expenses.map(e => String(e.id)));
  expenseContainer.querySelectorAll('.expense-card[data-expense-id]').forEach(card => {
    if (!dbIds.has(card.dataset.expenseId) && !isDeleting) {
      card.remove();
    }
  });

  // 2. Update any cards whose content changed (Ghost Modification fix)
  expenses.forEach(exp => {
    const id               = String(exp.id);
    const existingCard     = expenseContainer.querySelector(`.expense-card[data-expense-id="${id}"]`);
    const targetFingerprint = `${exp.reason}|${exp.amount}|${exp.whopaid}|${exp.splits.map(s => s.share).join(',')}`;

    if (!existingCard) return;  // new card — handled in step 3

    if (existingCard.dataset.fingerprint !== targetFingerprint) {
      const updated = buildExpenseCardElement(
        exp.reason, exp.amount,
        exp.splits.map(s => s.name),
        exp.splits.map(s => s.share),
        exp.whopaid, exp.id
      );
      expenseContainer.replaceChild(updated, existingCard);
    }
  });

  // 3. Insert missing cards and enforce exact chronological order
  //    insertBefore at the correct index — never appendChild (Out-of-Order fix)
  expenses.forEach((exp, index) => {
    const id = String(exp.id);
    let card = expenseContainer.querySelector(`.expense-card[data-expense-id="${id}"]`);

    if (!card) {
      card = buildExpenseCardElement(
        exp.reason, exp.amount,
        exp.splits.map(s => s.name),
        exp.splits.map(s => s.share),
        exp.whopaid, exp.id
      );
    }

    const nodeAtIndex = expenseContainer.children[index];
    if (nodeAtIndex !== card) {
      // Moves existing card or inserts new one at the correct position
      expenseContainer.insertBefore(card, nodeAtIndex || null);
    }
  });
}

// ── Initial load on page open (full rebuild) ──────────────────────────────
async function loadExistingExpenses() {
  try {
    const response = await fetch(`/get_expenses/${tripId}`);
    if (!response.ok) return;
    const data = await response.json();
    const expenses = data.expenses;
    if (data.is_finished) {
      window.location.href = `/results/${tripId}`;
      return;
    }
    expenseContainer.innerHTML = "";
    expenses.forEach(exp => {
      buildExpenseCard(
        exp.reason, exp.amount,
        exp.splits.map(s => s.name),
        exp.splits.map(s => s.share),
        exp.whopaid, exp.id
      );
    });
  } catch (err) {
    console.error("Could not load existing expenses:", err);
  }
}

// ── Force Sync Engine ─────────────────────────────────────────────────────
// isSyncing prevents two overlapping sync fetches from racing each other
// (e.g. a save-triggered sync and a poll firing at the same instant).
async function forceSyncExpenses() {
  if (isSyncing) return;
  isSyncing = true;
  try {
    const response = await fetch(`/get_expenses/${tripId}`);
    if (!response.ok) return;
    const expenses = await response.json();

    if (expenses.is_finished) {
      window.location.href = `/results/${tripId}`;
      return;
    }

    diffExpenseCards(expenses.expenses);
  } catch (err) {
    console.error("Sync tracking failure:", err);
  } finally {
    isSyncing = false;
  }
}

// ── Polling ───────────────────────────────────────────────────────────────
// Skipped while a save or delete confirmation is in-flight to avoid
// the Vanishing Submission and Ghost Card Duplication races.
// isSyncing guard prevents a timer tick from overlapping a save-triggered sync.
async function pollExpenses() {
  if (isSaving || isDeleting || isSyncing) return;

  try {
    const response = await fetch(`/get_expenses/${tripId}`);
    if (!response.ok) return;
    const data = await response.json();

    // Re-check flags: state may have changed while fetch was in-flight
    if (isSaving || isDeleting) return;

    if (data.is_finished) {
      window.location.href = `/results/${tripId}`;
      return; // Stop execution here
    }
    diffExpenseCards(data.expenses);
  } catch (err) {
    console.error("Poll failed:", err);
  }
}

loadExistingExpenses();
setInterval(pollExpenses, 30000);

// ── FAB buttons — wire to existing handlers (mobile only) ────────────────
const fabAddBtn    = document.getElementById('fabAddBtn');
const fabWalletBtn = document.getElementById('fabWalletBtn');

if (fabAddBtn)    fabAddBtn.addEventListener('click',    () => addExpenseBtn.click());
if (fabWalletBtn) fabWalletBtn.addEventListener('click', () => billBtn.click());

}); // end DOMContentLoaded