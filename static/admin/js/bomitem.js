document.addEventListener("DOMContentLoaded", function () {
    function updateRows() {
        document.querySelectorAll(".dynamic-items").forEach(function (row) {
            let raw = row.querySelector("select[id$='raw_material']");
            let comp = row.querySelector("select[id$='component_product']");

            if (raw && comp) {
                if (raw.value) {
                    comp.closest("td").style.display = "none";
                } else if (comp.value) {
                    raw.closest("td").style.display = "none";
                } else {
                    raw.closest("td").style.display = "";
                    comp.closest("td").style.display = "";
                }
            }
        });
    }

    updateRows();
    document.addEventListener("change", updateRows);
});
