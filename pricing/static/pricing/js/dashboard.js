function fmt(n) {
  if (n === null || n === undefined) return "-";
  return Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function getParams() {
  return {
    period: document.getElementById("period").value,
    mode: document.getElementById("mode").value,
    q: document.getElementById("q").value || "",
    markup_sell: document.getElementById("markup_sell").value,
    markup_internal: document.getElementById("markup_internal").value,
    opex_percent: document.getElementById("opex_percent").value,
    discount_percent: document.getElementById("discount_percent").value,
    vat_percent: document.getElementById("vat_percent").value,
    min_price: document.getElementById("min_price").value,
  };
}

async function loadData() {
  const p = getParams();
  const qs = new URLSearchParams(p).toString();
  const res = await fetch(`/pricing/api/dashboard-data/?${qs}`);
  const data = await res.json();

  // KPIs
  document.getElementById("kpiCount").textContent = data.totals.count ?? "-";
  document.getElementById("kpiCost").textContent = fmt(data.totals.sum_cost);
  document.getElementById("kpiSuggested").textContent = fmt(data.totals.sum_suggested_sales);
  document.getElementById("kpiNet").textContent = fmt(data.totals.sum_net_profit_suggested);

  // Table
  const body = document.getElementById("rowsBody");
  body.innerHTML = "";

  data.rows.forEach(r => {
    const badge = r.badge === "green" ? "✅" : (r.badge === "yellow" ? "🟡" : "🔴");
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${r.code}</td>
      <td>${r.name}</td>
      <td>${r.type}</td>
      <td>${fmt(r.cost)}</td>
      <td>${fmt(r.current_price)}</td>
      <td>${fmt(r.suggested_price)}</td>
      <td>${fmt(r.gross_profit_suggested)}</td>
      <td>${fmt(r.net_profit_suggested)}</td>
      <td>${badge} ${fmt(r.margin_percent)}</td>
    `;
    body.appendChild(tr);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("applyBtn").addEventListener("click", loadData);
  loadData();
});
