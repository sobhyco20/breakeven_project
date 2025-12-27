# reports/utils/bom_utils.py

from collections import defaultdict

def explode_to_raw(product, quantity, bom_map, product_type_map):
    result = defaultdict(float)

    def _walk(prod, qty):
        p_type = product_type_map.get(prod.id)
        if p_type == 'RM' or prod.id not in bom_map:
            result[prod.id] += qty
            return

        for item in bom_map[prod.id]:
            component = item['component']
            component_qty_per_unit = item['qty']
            component_total_qty = component_qty_per_unit * qty
            _walk(component, component_total_qty)

    _walk(product, quantity)
    return result
