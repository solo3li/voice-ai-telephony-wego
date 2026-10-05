/**
 * Billing & Wallet JavaScript Controller
 * Handles wallet balances, instant top-ups, and financial transaction ledger.
 */

async function loadWalletData() {
  try {
    const res = await fetch('/api/billing/wallet/');
    const data = await res.json();
    if (data.status === 'success') {
      const w = data.wallet;
      const cfg = data.config;
      const sym = cfg.currency_symbol || '$';

      // Update header badge
      const hVal = document.getElementById('header-balance-val');
      const hCurr = document.getElementById('header-balance-curr');
      if (hVal) hVal.innerText = w.balance.toFixed(2);
      if (hCurr) hCurr.innerText = w.currency;

      // Update billing tab cards
      const bVal = document.getElementById('billing-wallet-balance');
      const bCurr = document.getElementById('billing-wallet-currency');
      if (bVal) bVal.innerText = w.balance.toFixed(2);
      if (bCurr) bCurr.innerText = `${w.currency} (${sym})`;

      const rPill = document.getElementById('billing-rate-pill');
      if (rPill) rPill.innerText = `${sym}${cfg.cost_per_minute.toFixed(4)} / دقيقة`;

      const sDep = document.getElementById('billing-stat-deposited');
      if (sDep) sDep.innerText = `${sym}${w.total_deposited.toFixed(2)}`;

      const sSpent = document.getElementById('billing-stat-spent');
      if (sSpent) sSpent.innerText = `${sym}${w.total_spent.toFixed(2)}`;

      // Status Badge
      const statusBadge = document.getElementById('billing-call-status-badge');
      if (statusBadge) {
        if (data.can_call) {
          statusBadge.className = 'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300 shadow-sm';
          statusBadge.innerHTML = '<span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span> جاهز للاتصال';
        } else {
          statusBadge.className = 'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-rose-100 text-rose-800 border border-rose-300 shadow-sm';
          statusBadge.innerHTML = '<span class="w-2 h-2 rounded-full bg-rose-500"></span> رصيد غير كافٍ - يرجى الشحن';
        }
      }

      if (data.recent_transactions) {
        renderTransactionsTable(data.recent_transactions, sym);
      }
    }
  } catch (err) {
    console.error('Error loading wallet data:', err);
  }
}

async function loadTransactions(type = 'all') {
  const tbody = document.getElementById('billing-transactions-tbody');
  try {
    const url = type && type !== 'all' ? `/api/billing/transactions/?type=${encodeURIComponent(type)}` : '/api/billing/transactions/';
    const res = await fetch(url);
    const data = await res.json();
    if (data.status === 'success') {
      renderTransactionsTable(data.transactions, data.wallet?.currency_symbol || '$');
    }
  } catch (err) {
    console.error('Error loading transactions:', err);
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="7" class="py-6 text-center text-rose-600">فشل تحميل سجل المعاملات.</td></tr>`;
    }
  }
}

function renderTransactionsTable(txs, sym = '$') {
  const tbody = document.getElementById('billing-transactions-tbody');
  if (!tbody) return;

  if (!txs || txs.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" class="py-8 text-center text-[#8C827A]">
          لا توجد حركات مالية مسجلة حتى الآن.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = txs.map(t => {
    const isPositive = t.amount >= 0;
    const amountBadge = isPositive 
      ? `<span class="px-2.5 py-1 rounded-lg text-xs font-mono font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">${t.amount_formatted}</span>`
      : `<span class="px-2.5 py-1 rounded-lg text-xs font-mono font-bold bg-rose-50 text-rose-700 border border-rose-200">${t.amount_formatted}</span>`;

    let typeBadge = '';
    if (t.transaction_type === 'topup') {
      typeBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">⚡ شحن رصيد</span>`;
    } else if (t.transaction_type === 'call_deduction') {
      typeBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#FAF0F2] text-[#680E23] border border-[#E8CCD2]">📞 خصم مكالمة</span>`;
    } else {
      typeBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#FAF7F2] text-[#6E645D] border border-[#DDD5C7]">${escapeHtml(t.transaction_type_display)}</span>`;
    }

    const minsDisplay = t.billed_minutes > 0
      ? `<span class="font-mono font-bold text-[#680E23]">${t.billed_minutes} د</span> <span class="text-[10px] text-[#8C827A]">(${t.actual_seconds} ث)</span>`
      : `<span class="text-[#8C827A]">-</span>`;

    const rateDisplay = t.rate_applied > 0
      ? `<span class="font-mono">${sym}${t.rate_applied.toFixed(4)}</span>`
      : `<span class="text-[#8C827A]">-</span>`;

    return `
      <tr class="hover:bg-[#F5EFE6]/50 transition">
        <td class="py-3 px-4 text-[#6E645D] font-mono text-[11px]">${t.created_at}</td>
        <td class="py-3 px-4">${typeBadge}</td>
        <td class="py-3 px-4">${amountBadge}</td>
        <td class="py-3 px-4 font-mono font-semibold text-[#1C1917]">${t.balance_after_formatted}</td>
        <td class="py-3 px-4">${minsDisplay}</td>
        <td class="py-3 px-4">${rateDisplay}</td>
        <td class="py-3 px-4 text-[#443D39] max-w-xs truncate" title="${escapeHtml(t.description || '')}">${escapeHtml(t.description || '-')}</td>
      </tr>
    `;
  }).join('');
}

function openTopupModal() {
  const m = document.getElementById('topup-modal');
  const alertBox = document.getElementById('topup-modal-alert');
  if (alertBox) alertBox.classList.add('hidden');
  if (m) m.classList.remove('hidden');
}

function closeTopupModal() {
  const m = document.getElementById('topup-modal');
  if (m) m.classList.add('hidden');
}

function setTopupAmount(amt) {
  const inp = document.getElementById('topup-amount-input');
  if (inp) inp.value = amt;
}

async function submitTopup() {
  const inp = document.getElementById('topup-amount-input');
  const btn = document.getElementById('btn-submit-topup');
  const alertBox = document.getElementById('topup-modal-alert');
  if (!inp || !btn) return;

  const amt = parseFloat(inp.value);
  if (isNaN(amt) || amt <= 0) {
    if (alertBox) {
      alertBox.className = 'p-2.5 rounded-xl text-xs bg-rose-100 text-rose-800 border border-rose-200';
      alertBox.innerText = 'يرجى إدخال مبلغ صحيح أكبر من الصفر.';
      alertBox.classList.remove('hidden');
    }
    return;
  }

  btn.disabled = true;
  btn.innerText = 'جاري الإيداع...';

  try {
    const res = await fetch('/api/billing/topup/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({ amount: amt })
    });
    const data = await res.json();
    if (data.status === 'success') {
      if (alertBox) {
        alertBox.className = 'p-2.5 rounded-xl text-xs bg-emerald-100 text-emerald-800 border border-emerald-200';
        alertBox.innerText = data.message || 'تم شحن الرصيد بنجاح!';
        alertBox.classList.remove('hidden');
      }
      showToast(data.message || 'تم شحن الرصيد بنجاح!', 'success');
      await loadWalletData();
      await loadTransactions('all');
      setTimeout(() => {
        closeTopupModal();
        btn.disabled = false;
        btn.innerText = 'تأكيد الشحن الفوري';
      }, 700);
    } else {
      if (alertBox) {
        alertBox.className = 'p-2.5 rounded-xl text-xs bg-rose-100 text-rose-800 border border-rose-200';
        alertBox.innerText = data.message || 'فشل الشحن.';
        alertBox.classList.remove('hidden');
      }
      btn.disabled = false;
      btn.innerText = 'تأكيد الشحن الفوري';
    }
  } catch (err) {
    if (alertBox) {
      alertBox.className = 'p-2.5 rounded-xl text-xs bg-rose-100 text-rose-800 border border-rose-200';
      alertBox.innerText = 'حدث خطأ في الاتصال بالخادم.';
      alertBox.classList.remove('hidden');
    }
    btn.disabled = false;
    btn.innerText = 'تأكيد الشحن الفوري';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  loadWalletData();
  loadTransactions('all');
});
