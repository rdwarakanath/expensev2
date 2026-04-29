/* ============================================================
   dashboard.js — ALL original logic preserved.
   Wrapped in DOMContentLoaded to guarantee DOM is ready before
   any getElementById / addEventListener calls run.
   ============================================================ */

document.addEventListener("DOMContentLoaded", () => {

const addExpenseBtn    = document.getElementById("addExpenseBtn");
const finishBtn        = document.getElementById("FinishBtn");
const billBtn          = document.getElementById("billBtn");
const expenseForm      = document.getElementById("expenseForm");
const cancelExpenseBtn = document.getElementById("cancelExpenseBtn");
const saveExpenseBtn   = document.getElementById("saveExpenseBtn");
const expenseContainer = document.getElementById("expenseContainer");
const unequalShare     = document.getElementById("unequalShare");
const shareForm        = document.getElementById("shareForm");
const prevshareBtn     = document.getElementById("prevshareBtn");
const saveshareBtn     = document.getElementById("saveshareBtn");
const synopsisContainer  = document.getElementById("synopsisContainer");
const synopsisContent    = document.getElementById("synopsisContent");
const closeBtn           = document.getElementById("closeSynopsis");
const expenseBackdrop    = document.getElementById("expenseBackdrop");
const synopsisBackdrop   = document.getElementById("synopsisBackdrop");

let paidby = "";
let tempReason = "";
let tempAmount = "";
let selectedmembers = [];

// ── Show / hide expense form (side modal + backdrop) ──────────────────────
addExpenseBtn.addEventListener("click", () => {
  expenseForm.classList.remove("hidden");
  expenseBackdrop.classList.remove("hidden");
});

function closeExpenseForm() {
  expenseForm.classList.add("hidden");
  expenseBackdrop.classList.add("hidden");
}
cancelExpenseBtn.addEventListener("click", closeExpenseForm);

// ── "Select All" checkbox logic (ORIGINAL — unchanged) ───────────────────
const selectAll       = document.getElementById("selectAll");
const memberCheckboxes = document.querySelectorAll('input[name="members"]');

selectAll.addEventListener("change", () => {
  memberCheckboxes.forEach(cb => cb.checked = selectAll.checked);
});

memberCheckboxes.forEach(cb => {
  cb.addEventListener("change", () => {
    if (!cb.checked) {
      selectAll.checked = false;
    } else if (Array.from(memberCheckboxes).every(m => m.checked)) {
      selectAll.checked = true;
    }
  });
});

// ── Save expense (ORIGINAL validation logic — unchanged) ─────────────────
saveExpenseBtn.addEventListener("click", () => {
  const reason   = document.getElementById("expenseReason").value;
  const amount   = document.getElementById("expenseAmount").value;
  paidby         = document.getElementById("paidby").value;
  const checkedboxes  = document.querySelectorAll(".member-checkboxes input[name='members']:checked");
  selectedmembers     = Array.from(checkedboxes).map(cb => cb.value);
  const shareType     = document.querySelector("input[name='shareType']:checked").value;

  // ── Original validation (unchanged) ──
  if (!reason || !amount) {
    alert("Please enter both reason and amount."); return;
  }
  if (amount <= 0) {
    alert("Please enter a valid amount."); return;
  }
  if (!paidby || !members.includes(paidby)) {
    alert("Please enter a valid member name."); return;
  }
  if (selectedmembers.length === 0) {
    alert("Please select members."); return;
  }

  tempReason = reason;
  tempAmount = amount;

  const share  = Math.round((amount / selectedmembers.length) * 100) / 100;
  const shares = Array(selectedmembers.length).fill(share);

  if (shareType === "unequal") {
    // Build unequal share inputs
    shareForm.innerHTML = "";

    // Show hint with total
    const hint = document.getElementById("unequalHint");
    if (hint) hint.textContent = `Shares must add up to ₹${amount}. Enter each person's amount.`;

    selectedmembers.forEach(member => {
      const input = document.createElement("input");
      input.type = "number";
      input.placeholder = `${member}'s share`;
      input.classList.add("share-input");
      shareForm.appendChild(input);
    });

    closeExpenseForm();
    unequalShare.classList.remove("hidden");
    expenseBackdrop.classList.remove("hidden"); // keep backdrop for unequal modal
    return;
  }

  addExpenseCard(reason, amount, selectedmembers, shares, paidby);
  resetExpenseForm();
});

// ── Enter key (ORIGINAL — unchanged) ────────────────────────────────────
document.addEventListener("keydown", function(event) {
  if (event.key === "Enter") {
    event.preventDefault();
    if (!unequalShare.classList.contains("hidden")) {
      saveshareBtn.click();
    } else if (!expenseForm.classList.contains("hidden")) {
      saveExpenseBtn.click();
    }
  }
});

// ── Unequal share navigation (ORIGINAL — unchanged) ──────────────────────
prevshareBtn.addEventListener("click", () => {
  unequalShare.classList.add("hidden");
  expenseForm.classList.remove("hidden");
});

saveshareBtn.addEventListener("click", () => {
  const inputs = document.querySelectorAll(".share-input");
  const shares = Array.from(inputs)
    .map(i => roundTo(Number(i.value.trim()), 2))
    .filter(v => !isNaN(v));

  const total = shares.reduce((sum, val) => sum + val, 0);
  if (roundTo(total, 2) !== roundTo(Number(tempAmount), 2)) {
    alert("Shares don't match the total amount."); return;
  }

  unequalShare.classList.add("hidden");
  expenseBackdrop.classList.add("hidden");
  addExpenseCard(tempReason, tempAmount, selectedmembers, shares, paidby);
  resetExpenseForm();
});

// ── Add expense card + POST to backend (ORIGINAL logic — unchanged) ───────
async function addExpenseCard(reason, amount, members, shares, whopaid) {
  try {
    const response = await fetch("/add_expense", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason, amount, members, shares, whopaid })
    });
    const result = await response.json();

    if (result.status === "success") {
      // Build card (updated HTML for dark theme — logic identical)
      const card = document.createElement("div");
      card.className = "expense-card";

      const membersList = members
        .map((m, i) => `<li>${capitalize(m)}: <strong style="color:var(--amber)">₹${shares[i]}</strong></li>`)
        .join("");

      card.innerHTML = `
        <strong>${reason.toUpperCase()}</strong>
        <p style="color:var(--text-secondary);font-size:0.88rem;margin:4px 0 10px">
          ₹${amount} paid by <span style="color:var(--amber);font-weight:700">${capitalize(whopaid)}</span>
        </p>
        <ul style="list-style:none;padding:0">${membersList}</ul>
      `;
      expenseContainer.appendChild(card);

    } else if (result.status === "error") {
      alert(`⚠ ${result.message || "Failed to save expense."}`);
    } else {
      alert("⚠ Failed to save expense. Please try again.");
    }
  } catch (error) {
    alert("❌ Error connecting to server. Please check your connection.");
  }
}

// ── Reset form (ORIGINAL — unchanged) ────────────────────────────────────
function resetExpenseForm() {
  document.getElementById("expenseReason").value = "";
  document.getElementById("expenseAmount").value = "";
  document.getElementById("paidby").value = "";
  document.querySelectorAll(".member-checkboxes input[type='checkbox']")
    .forEach(cb => cb.checked = false);
}

// ── Helpers (ORIGINAL — unchanged) ───────────────────────────────────────
function capitalize(s) {
  return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
}

function roundTo(num, decimals) {
  return Math.round(num * 10 ** decimals) / 10 ** decimals;
}

// ── Finish button (ORIGINAL — unchanged) ─────────────────────────────────
finishBtn.addEventListener("click", () => {
  if (confirm("Are you sure you want to finish the trip?")) {
    window.location.href = "/results";
  }
});

// ── Bill / wallet synopsis (ORIGINAL logic — unchanged) ──────────────────
billBtn.addEventListener("click", async () => {
  try {
    const response = await fetch("/get_data");
    if (!response.ok) throw new Error("Network response was not ok");
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
    alert("❌ Could not retrieve data from server.");
  }
});

closeBtn.addEventListener("click", () => {
  synopsisContainer.classList.add("hidden");
  synopsisBackdrop.classList.add("hidden");
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    synopsisContainer.classList.add("hidden");
    synopsisBackdrop.classList.add("hidden");
    closeExpenseForm();
  }
});

// ── Toggle split type active styling ─────────────────────────────────────
document.querySelectorAll('input[name="shareType"]').forEach(radio => {
  radio.addEventListener('change', () => {
    document.querySelectorAll('.toggle-opt').forEach(l => l.classList.remove('active'));
    radio.closest('.toggle-opt').classList.add('active');
  });
});

// ── Second cancel button wiring ───────────────────────────────────────────
const cancelBtn2 = document.getElementById('cancelExpenseBtn2');
if (cancelBtn2) {
  cancelBtn2.addEventListener('click', closeExpenseForm);
}

// ── Backdrop clicks close modals ──────────────────────────────────────────
expenseBackdrop.addEventListener('click', closeExpenseForm);
synopsisBackdrop.addEventListener('click', () => {
  synopsisContainer.classList.add("hidden");
  synopsisBackdrop.classList.add("hidden");
});

// ── Show/hide empty feed state ────────────────────────────────────────────
const feedEmpty = document.getElementById('feedEmpty');
if (feedEmpty && expenseContainer) {
  const observer = new MutationObserver(() => {
    feedEmpty.style.display = expenseContainer.children.length > 0 ? 'none' : 'flex';
  });
  observer.observe(expenseContainer, { childList: true });
}

}); // end DOMContentLoaded
