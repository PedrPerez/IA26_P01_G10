"""Hill Climbing: melhor vizinho viável, substituindo uma onda."""
from time import perf_counter
from .informed import SearchResult

def hill_climbing(planner,initial,max_iterations=50):
    if initial.routes is None:raise ValueError('É necessária uma solução inicial')
    start=perf_counter();choices=initial.choices;cost=initial.cost_km;history=[cost];evaluated=0
    for iteration in range(max_iterations):
        best=choices;best_cost=cost
        for d,options in enumerate(planner.options):
            for option in options:
                candidate=choices[:d]+(option,)+choices[d+1:]
                value=sum(planner.option_cost(w,o) for w,o in zip(planner.waves,candidate))
                if value>=best_cost-1e-9:continue
                evaluated+=1
                state=planner.decode(candidate)
                if state is not None:best,best_cost=candidate,value
        if best==choices:break
        choices,cost=best,best_cost;history.append(cost)
    state=planner.decode(choices)
    return SearchResult('Hill Climbing',state[0],choices,cost,len(history)-1,evaluated,
                        perf_counter()-start,'ótimo local' if len(history)-1<max_iterations else 'limite de iterações'),history
