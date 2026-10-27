"""CSP de ondas: domínios finitos, backtracking e forward checking.
Restrições suaves ordenam valores por distância; não relaxam as duras.
"""
from time import perf_counter
from .informed import SearchResult

def solve_csp(planner,max_nodes=20000):
    start=perf_counter();stats={'nodes':0,'backtracks':0,'checks':0};limited=False
    def visit(state,choices):
        nonlocal limited
        d=len(choices)
        if d==len(planner.waves):
            return choices if planner.problem.validate(state[0]).feasible else None
        if stats['nodes']>=max_nodes:limited=True;return None
        stats['nodes']+=1
        # Ordem temporal obrigatória: os domínios dependem da onda anterior.
        for option in sorted(planner.options[d],key=lambda o:planner.option_cost(planner.waves[d],o)):
            stats['checks']+=1;child=planner.extend(state,d,option)
            if child is None:continue
            # Forward checking: a próxima variável mantém pelo menos um valor.
            if d+1<len(planner.waves) and not any(planner.extend(child,d+1,o) is not None for o in planner.options[d+1]):
                stats['backtracks']+=1;continue
            result=visit(child,choices+(option,))
            if result is not None:return result
            stats['backtracks']+=1
            if limited:return None
        return None
    choices=visit(planner.initial(),())
    state=planner.decode(choices) if choices is not None else None
    cost=planner.problem.cost(state[0]) if state else float('inf')
    result=SearchResult('CSP',state[0] if state else None,choices or (),cost,stats['nodes'],stats['checks'],
                        perf_counter()-start,'solução' if state else ('limite de nós' if limited else 'sem solução neste espaço'))
    return result,stats
