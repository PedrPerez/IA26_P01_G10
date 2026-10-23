"""Verificações reproduzíveis para a análise exploratória."""
import pandas as pd

def audit(problem):
    t = problem.tables
    rows = []
    def check(name, bad):
        rows.append({'verificação':name, 'problemas':int(bad)})
    keys = {'localities':'locality_id','producers':'producer_id','products':'product_id',
            'collection_centers':'center_id','vehicles':'vehicle_id','customers':'customer_id',
            'delivery_locations':'delivery_location_id','orders':'order_id',
            'order_items':'order_item_id','locations':'location_id','rules':'rule'}
    for name, df in t.items():
        check(name+': valores em falta', df.isna().sum().sum())
        if name in keys: check(name+': chave duplicada', df[keys[name]].duplicated().sum())
    relations = [('producers','locality_id','localities'),('collection_centers','locality_id','localities'),
                 ('customers','locality_id','localities'),('delivery_locations','locality_id','localities'),
                 ('products','producer_id','producers'),('vehicles','center_id','collection_centers'),
                 ('orders','customer_id','customers'),('orders','delivery_location_id','delivery_locations'),
                 ('order_items','order_id','orders'),('order_items','product_id','products')]
    for child,key,parent in relations:
        check(f'{child}.{key}: referência inexistente', (~t[child][key].isin(t[parent][key])).sum())
    items = t['order_items'].copy()
    for c in ['availability_start','availability_end','delivery_start','delivery_end']:
        items[c] = pd.to_datetime(items[c], errors='coerce')
        check(c+': data inválida',items[c].isna().sum())
        check(c+': fora do horizonte',((items[c]<problem.start)|(items[c]>problem.end)).sum())
    for a,b in [('availability_start','availability_end'),('delivery_start','delivery_end')]:
        check(a+': janela invertida',(items[a]>items[b]).sum())
    for name,col in [('order_items','weight_kg'),('order_items','quantity'),('products','unit_weight_kg'),
                     ('vehicles','capacity_kg'),('collection_centers','capacity_kg')]:
        check(name+'.'+col+': não positivo',(t[name][col]<=0).sum())
    joined = items.merge(t['products'][['product_id','unit_weight_kg']],on='product_id',validate='many_to_one')
    check('Peso diferente de quantidade × peso unitário',
          ((joined.weight_kg-joined.quantity*joined.unit_weight_kg).abs()>0.011).sum())
    matrix = t['distance_matrix']
    check('Matriz: pares duplicados',matrix.duplicated(['origin_location_id','destination_location_id']).sum())
    expected={(a,b) for a in problem.locations for b in problem.locations if a!=b}
    actual=set(zip(matrix.origin_location_id,matrix.destination_location_id))
    check('Matriz: pares em falta',len(expected-actual))
    check('Matriz: pares desconhecidos',len(actual-expected))
    check('Matriz: valores negativos',(matrix[['distance_km','duration_min']]<0).sum().sum())
    asym=0
    for (a,b),(d,m) in problem.distances.items():
        other=problem.distances.get((b,a))
        asym+=int(other is None or abs(d-other[0])>0.011 or abs(m-other[1])>0.11)
    check('Matriz: assimetrias',asym)
    for typ,table,key in [('producer','producers','producer_id'),
                          ('collection_center','collection_centers','center_id'),
                          ('delivery_location','delivery_locations','delivery_location_id')]:
        refs=t['locations'].loc[t['locations'].location_type==typ,'ref_id']
        check('Locations: referências '+typ,(~refs.isin(t[table][key])).sum())
    return pd.DataFrame(rows)


def individual_feasibility(problem):
    from src.model import example_route
    rows=[]
    for i,r in problem.requests.items():
        candidates=[problem.validate([example_route(problem,i,v)],require_all=False)
                    for v in problem.vehicles]
        rows.append({'item':i,'order':r.order_id,'weight_kg':r.weight,
                     'individual_feasible':any(x.feasible for x in candidates),
                     'reason': '' if any(x.feasible for x in candidates) else '; '.join(candidates[0].errors)})
    return pd.DataFrame(rows)
